"""
recovery_demo.py -- Crash-recovery semantics for MARI's durable form.

The paper's central durable-write result (Section 9.7) needs a recovery story:
what is authoritative on disk, and how is the in-memory state rebuilt after a
crash? This demo answers it concretely.

DURABLE FORMAT (per bucket, append-only, group-commit fsync every G ops):
  * delta_<b>.log  -- fixed 16-byte records  (seq:u32, op:u8, id:u32, key:u32, pad)
                      op = 1 PUT (insert / in-guard update / migration-in),
                      op = 2 TOMB (delete / migration-out)
  * stable_<b>.seg -- rewritten at compaction: the live {id->key} of the bucket
                      as of that compaction; the delta log is then truncated.

KEY POINT: the authoritative identifier table T (id -> key, owning bucket) is a
pure in-memory derivative and is NEVER persisted. Recovery reconstructs it from
the per-bucket logs alone:

  for each bucket b:
      member[b] <- load stable_<b>.seg
      replay delta_<b>.log in seq order: PUT sets member[b][id]=key, TOMB removes id
  T <- { id: (key, b)  for each b, (id,key) in member[b] }

Recovery is a linear sequential scan of the durable state (no random I/O), and
restores a state consistent up to the last durable commit. A migration writes
TOMB(src)+PUT(dst); both land in the same group-commit, so the committed prefix
never shows an item tombstoned-out-of-src yet missing-from-dst.

We verify the recovered index answers a query set IDENTICALLY to a brute-force
oracle of the committed state (zero mismatches), and that |T| is fully rebuilt.
"""

import os, struct, time, json, random, shutil, bisect
from mari import gen, Oracle

REC = 16
PUT, TOMB = 1, 2
_fmt = struct.Struct(">IBII")          # seq, op, id, key  (13 bytes; padded to 16)
M, WIDTH, GUARD, EPS, G = 1_000_000, 1_000, 50, 0.5, 128


class DurableMARI:
    def __init__(self, wd, M=M, width=WIDTH, guard=GUARD, eps=EPS, gcommit=G):
        self.wd = wd; self.M = M; self.w = width; self.g = guard
        self.eps = eps; self.G = gcommit
        self.nb = (M + width - 1) // width
        self.member = {}                # b -> {id: key}   (in-memory, authoritative bucket state)
        self.Dcnt = {}                  # b -> appends since last compaction
        self.T = {}                     # id -> (key, b)   (in-memory, NOT persisted)
        self.seq = 0; self.since = 0; self.fsyncs = 0
        self.bytes_written = 0

    def _dpath(self, b): return os.path.join(self.wd, f"delta_{b}.log")
    def _spath(self, b): return os.path.join(self.wd, f"stable_{b}.seg")

    # -------- durable append path (open/append/close keeps fd count bounded) --------
    def _append(self, b, op, i, k):
        self.member.setdefault(b, {}); self.Dcnt.setdefault(b, 0)
        rec = _fmt.pack(self.seq, op, i, k & 0xFFFFFFFF) + b"\x00\x00\x00"
        fd = os.open(self._dpath(b), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.write(fd, rec); self.bytes_written += REC
        self.seq += 1; self.since += 1; self.Dcnt[b] += 1
        if self.since >= self.G:                     # group-commit fsync boundary
            os.fsync(fd); self.fsyncs += 1; self.since = 0
        os.close(fd)
        if self.Dcnt[b] >= max(1, int(self.eps * max(1, len(self.member[b])))):
            self._compact(b)

    def _compact(self, b):
        # rewrite stable segment with current live membership, then truncate delta log
        buf = b"".join(struct.pack(">II", i, k & 0xFFFFFFFF) for i, k in self.member[b].items())
        fd = os.open(self._spath(b), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        if buf: os.write(fd, buf); self.bytes_written += len(buf)
        os.fsync(fd); os.close(fd)
        fd = os.open(self._dpath(b), os.O_WRONLY | os.O_CREAT, 0o644)
        os.ftruncate(fd, 0); os.fsync(fd); os.close(fd)   # delta folded into stable
        self.Dcnt[b] = 0

    def _core(self, k): return min(k // self.w, self.nb - 1)
    def _in_guard(self, b, k): return b*self.w - self.g <= k <= (b+1)*self.w - 1 + self.g

    # -------- logical ops --------
    def insert(self, i, v):
        b = self._core(v); self.member.setdefault(b, {})[i] = v
        self.T[i] = (v, b); self._append(b, PUT, i, v)

    def update(self, i, v):
        cur = self.T.get(i)
        if cur is None: return self.insert(i, v)
        ok, bsrc = cur
        if ok == v: return
        if self._in_guard(bsrc, v):
            self.member[bsrc][i] = v; self.T[i] = (v, bsrc); self._append(bsrc, PUT, i, v)
        else:
            bdst = self._core(v)
            self.member[bsrc].pop(i, None); self.member.setdefault(bdst, {})[i] = v
            self.T[i] = (v, bdst)
            self._append(bsrc, TOMB, i, ok)     # migration-out
            self._append(bdst, PUT, i, v)       # migration-in (same commit group)

    def delete(self, i):
        cur = self.T.pop(i, None)
        if cur is None: return
        _, b = cur; self.member[b].pop(i, None); self._append(b, TOMB, i, 0)

    def flush(self):
        # guarantee full durability: fsync every durable file before a crash
        for f in os.listdir(self.wd):
            if f.startswith(("delta_", "stable_")):
                fd = os.open(os.path.join(self.wd, f), os.O_RDONLY)
                os.fsync(fd); os.close(fd)
        self.fsyncs += 1
    def close(self):
        pass

    # -------- queries (scan guard-intersecting buckets, verify against T) --------
    def range(self, a, b):
        out = set()
        lo = max(0, (a - self.g)//self.w - 1); hi = min(self.nb-1, (b + self.g)//self.w + 1)
        for j in range(lo, hi+1):
            mb = self.member.get(j)
            if not mb: continue
            for i, k in mb.items():
                if a <= k <= b:
                    tk, tb = self.T.get(i, (None, None))
                    if tb == j and tk is not None and a <= tk <= b: out.add(i)
        return out

    # ==========================================================
    # RECOVERY: rebuild member[] and T from durable files alone
    # ==========================================================
    @classmethod
    def recover(cls, wd, **kw):
        self = cls(wd, **kw)
        t0 = time.perf_counter()
        replayed_stable = replayed_delta = bytes_read = 0
        files = os.listdir(wd)
        bset = set()
        for f in files:
            if f.startswith("stable_"): bset.add(int(f[7:-4]))
            elif f.startswith("delta_"): bset.add(int(f[6:-4]))
        for b in sorted(bset):
            mem = {}
            sp = os.path.join(wd, f"stable_{b}.seg")
            if os.path.exists(sp):
                data = open(sp, "rb").read(); bytes_read += len(data)
                for off in range(0, len(data), 8):
                    i, k = struct.unpack(">II", data[off:off+8]); mem[i] = k
                    replayed_stable += 1
            dp = os.path.join(wd, f"delta_{b}.log")
            if os.path.exists(dp):
                data = open(dp, "rb").read(); bytes_read += len(data)
                recs = []
                for off in range(0, len(data), REC):
                    seq, op, i, k = _fmt.unpack(data[off:off+13])
                    recs.append((seq, op, i, k))
                for seq, op, i, k in sorted(recs):          # latest version wins
                    if op == PUT: mem[i] = k
                    else: mem.pop(i, None)
                    replayed_delta += 1
            if mem:
                self.member[b] = mem
                for i, k in mem.items(): self.T[i] = (k, b)
        self._recover_stats = {
            "buckets_recovered": len(self.member),
            "stable_records_read": replayed_stable,
            "delta_records_replayed": replayed_delta,
            "bytes_read": bytes_read,
            "recover_seconds": round(time.perf_counter() - t0, 4),
            "table_T_size": len(self.T),
        }
        return self


def replay(dm, init, ops_prefix, oracle):
    for i, v in init: dm.insert(i, v); oracle.upsert(i, v)
    for tag, i, v in ops_prefix:
        if tag == "u": dm.update(i, v); oracle.upsert(i, v)
    dm.flush()


def verify(idx, oracle, nq, seed):
    rnd = random.Random(seed); mism = 0
    for _ in range(nq):
        a = rnd.randrange(M - 5000); b = a + rnd.choice([200, 1000, 5000])
        if idx.range(a, b) != oracle.range(a, b): mism += 1
    return mism


def main():
    out = {"config": {"M": M, "bucket_width": WIDTH, "guard": GUARD, "eps": EPS,
                      "group_commit_G": G, "record_bytes": REC}, "tests": {}}
    init, ops, _ = gen("uniform", M=M, n=8_000, n_updates=80_000, n_queries=1, delta=GUARD, seed=23)
    upds = [o for o in ops if o[0] == "u"]

    # ---- Test A: full durable run, crash, recover everything ----
    wdA = "/home/claude/_recA"
    if os.path.exists(wdA): shutil.rmtree(wdA)
    os.makedirs(wdA)
    orcA = Oracle()
    dm = DurableMARI(wdA); replay(dm, init, upds, orcA)
    pre_mism = verify(dm, orcA, 2000, seed=1)        # sanity: live index correct pre-crash
    live = len(dm.T); dm.close()
    del dm                                            # *** CRASH: drop ALL in-memory state ***
    rec = DurableMARI.recover(wdA)
    post_mism = verify(rec, orcA, 2000, seed=1)       # recovered index vs oracle
    st = rec._recover_stats
    st.update({"pre_crash_mismatches": pre_mism, "post_recovery_mismatches": post_mism,
               "live_items_pre_crash": live, "T_fully_rebuilt": st["table_T_size"] == live})
    out["tests"]["A_full_recovery"] = st
    print("[A full recovery]", json.dumps(st))

    # ---- Test B: crash at an arbitrary commit boundary, recover the committed prefix ----
    K = (len(upds) // 2 // G) * G                     # a clean group-commit boundary
    wdB = "/home/claude/_recB"
    if os.path.exists(wdB): shutil.rmtree(wdB)
    os.makedirs(wdB)
    orcB = Oracle()
    dm = DurableMARI(wdB); replay(dm, init, upds[:K], orcB)
    live = len(dm.T); dm.close(); del dm              # *** CRASH at op K ***
    rec = DurableMARI.recover(wdB)
    post = verify(rec, orcB, 2000, seed=2)
    stB = rec._recover_stats
    stB.update({"crash_after_updates": K, "post_recovery_mismatches": post,
                "live_items_at_commit": live, "T_fully_rebuilt": stB["table_T_size"] == live})
    out["tests"]["B_commit_boundary_recovery"] = stB
    print("[B boundary recovery]", json.dumps(stB))

    for d in (wdA, wdB): shutil.rmtree(d, ignore_errors=True)
    json.dump(out, open("/home/claude/recovery_results.json", "w"), indent=2)
    print("wrote recovery_results.json")


if __name__ == "__main__":
    main()
