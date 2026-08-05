"""
Native-baseline durable-write benchmark.

Same bounded-drift workload, indexed BY THE MOVING VALUE (score) so that range
queries over the value are possible. In a plain key-value store that means each
value change is a delete(old)+put(new) -- a relocation -- which is exactly the
cost MARI's guarded ownership avoids. We measure REAL bytes written to disk via
/proc/self/io (wchar = bytes issued to write(); write_bytes = bytes to storage)
over the update phase, under group-commit durability (fsync every G updates).

Engines:
  lmdb    - LMDB, a native copy-on-write B+-tree (relocate-in-place baseline)
  rocksdb - RocksDB via rocksdict, a native production LSM (append+compact)
  mari    - MARI's durable discipline: in-guard update = 1 append; migration = 2;
            periodic compaction. (Python, but the BYTES are engine-independent.)

Run:  python native_bench.py <engine>     (prints one JSON line)
"""
import sys, os, struct, json, tempfile, time
from mari import gen

N, U, DELTA, G = 20_000, 100_000, 50, 128
M, WIDTH, EPS = 1_000_000, 1_000, 0.5
REC = 16  # MARI delta record bytes

def io():
    d = {}
    for ln in open("/proc/self/io"):
        k, v = ln.split(":"); d[k.strip()] = int(v)
    return d

def key(score, pid):
    return struct.pack(">II", score, pid)   # ordered by score then id (range-capable)

def workload():
    init, ops, _ = gen("uniform", M=M, n=N, n_updates=U, n_queries=1, delta=DELTA, seed=31)
    upds = [(i, v) for tag, i, v in ops if tag == "u"]
    return init, upds

# ----------------------------------------------------------- LMDB (B+-tree)
def run_lmdb(wd):
    import lmdb
    cur = {}
    env = lmdb.open(os.path.join(wd, "l"), map_size=8 << 30, sync=True, metasync=True,
                    writemap=False, max_dbs=1)
    init, upds = workload()
    with env.begin(write=True) as t:
        for i, v in init:
            t.put(key(v, i), b"\x01"); cur[i] = v
    env.sync(True)
    a = io(); t0 = time.perf_counter(); fsyncs = 0
    txn = env.begin(write=True); c = 0
    for i, v in upds:
        old = cur.get(i)
        if old is None:
            txn.put(key(v, i), b"\x01"); cur[i] = v
        elif old != v:
            txn.delete(key(old, i)); txn.put(key(v, i), b"\x01"); cur[i] = v
        c += 1
        if c % G == 0:
            txn.commit(); fsyncs += 1; txn = env.begin(write=True)
    txn.commit(); fsyncs += 1
    b = io(); dt = time.perf_counter() - t0
    size = sum(os.path.getsize(os.path.join(wd, "l", f)) for f in os.listdir(os.path.join(wd, "l")))
    env.close()
    return a, b, dt, fsyncs, size

# --------------------------------------------------------- RocksDB (LSM)
def run_rocksdb(wd):
    from rocksdict import Rdict, Options
    cur = {}
    opt = Options(); opt.create_if_missing(True)
    rd = Rdict(os.path.join(wd, "r"), opt)
    init, upds = workload()
    for i, v in init:
        rd[key(v, i)] = b"\x01"; cur[i] = v
    rd.flush(); rd.flush_wal(True)
    a = io(); t0 = time.perf_counter(); fsyncs = 0
    c = 0
    for i, v in upds:
        old = cur.get(i)
        if old is None:
            rd[key(v, i)] = b"\x01"; cur[i] = v
        elif old != v:
            del rd[key(old, i)]; rd[key(v, i)] = b"\x01"; cur[i] = v
        c += 1
        if c % G == 0:
            rd.flush_wal(True); fsyncs += 1
    rd.flush_wal(True); rd.flush(); fsyncs += 1
    b = io(); dt = time.perf_counter() - t0
    path = os.path.join(wd, "r")
    size = sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path)
               if os.path.isfile(os.path.join(path, f)))
    rd.close()
    return a, b, dt, fsyncs, size

# --------------------------------------------------------- MARI discipline
def run_mari(wd):
    nb = (M + WIDTH - 1) // WIDTH
    member = [set() for _ in range(nb)]; Dcnt = [0] * nb
    cur = {}
    b_of = lambda k: min(k // WIDTH, nb - 1)
    in_guard = lambda bb, k: bb * WIDTH - DELTA <= k <= (bb + 1) * WIDTH - 1 + DELTA
    dlog = os.open(os.path.join(wd, "delta.log"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    sseg = os.open(os.path.join(wd, "stable.seg"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    init, upds = workload()
    since = [0]; fsyncs = [0]
    def commit():
        if since[0] >= G:
            os.fsync(dlog); os.fsync(sseg); fsyncs[0] += 1; since[0] = 0
    def append(bb):
        os.write(dlog, b"d" * REC); since[0] += 1; Dcnt[bb] += 1
        if Dcnt[bb] >= max(1, int(EPS * max(1, len(member[bb])))):
            seg = len(member[bb]) * REC
            if seg: os.write(sseg, b"s" * seg)
            Dcnt[bb] = 0
        commit()
    for i, v in init:
        bb = b_of(v); member[bb].add(i); cur[i] = (v, bb); append(bb)
    os.fsync(dlog); os.fsync(sseg)
    a = io(); t0 = time.perf_counter(); since[0] = 0; fsyncs[0] = 0
    for i, v in upds:
        old = cur.get(i)
        if old is None:
            bb = b_of(v); member[bb].add(i); cur[i] = (v, bb); append(bb); continue
        ok, bsrc = old
        if ok == v: continue
        if in_guard(bsrc, v):                      # in guard -> ONE append
            cur[i] = (v, bsrc); append(bsrc)
        else:                                      # leaves guard -> migration (two appends)
            bd = b_of(v); member[bsrc].discard(i); member[bd].add(i); cur[i] = (v, bd)
            append(bsrc); append(bd)
    os.fsync(dlog); os.fsync(sseg); fsyncs[0] += 1
    b = io(); dt = time.perf_counter() - t0
    size = os.path.getsize(os.path.join(wd, "delta.log")) + os.path.getsize(os.path.join(wd, "stable.seg"))
    os.close(dlog); os.close(sseg)
    return a, b, dt, fsyncs[0], size

def main():
    eng = sys.argv[1]
    fn = {"lmdb": run_lmdb, "rocksdb": run_rocksdb, "mari": run_mari}[eng]
    with tempfile.TemporaryDirectory(dir="/home/claude") as wd:
        a, b, dt, fsyncs, size = fn(wd)
    out = {
        "engine": eng, "updates": U,
        "wchar_total": b["wchar"] - a["wchar"],
        "write_bytes_total": b["write_bytes"] - a["write_bytes"],
        "wchar_per_update": round((b["wchar"] - a["wchar"]) / U, 1),
        "write_bytes_per_update": round((b["write_bytes"] - a["write_bytes"]) / U, 1),
        "fsyncs": fsyncs, "disk_bytes": size, "wall_s": round(dt, 2),
    }
    print(json.dumps(out))

if __name__ == "__main__":
    main()
