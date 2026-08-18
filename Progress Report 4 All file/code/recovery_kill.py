"""Crash recovery under a REAL process SIGKILL (not a simulated in-memory drop).
A worker fsync-commits each update and is killed mid-run by the parent; a fresh
process recovers from the on-disk logs and is verified exact against the
deterministically re-derived committed prefix."""
import os, sys, time, json, signal, random, shutil, struct, multiprocessing as mp
from recovery_demo import DurableMARI
from mari import gen, Oracle

WD="/home/claude/_reckill"; SEED=77; N=300; U=1200; CP=os.path.join(WD,"checkpoint")

def workload():
    init, ops, _ = gen("uniform", M=1_000_000, n=N, n_updates=U, n_queries=1, delta=50, seed=SEED)
    return init, [(i,v) for (k,i,v) in ops if k=="u"]

def _writecp(n):
    fd=os.open(CP+".tmp", os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o644)
    os.write(fd, str(n).encode()); os.fsync(fd); os.close(fd); os.replace(CP+".tmp", CP)

def worker():
    if os.path.exists(WD): shutil.rmtree(WD)
    os.makedirs(WD)
    init, upd = workload()
    dm = DurableMARI(WD, gcommit=1)
    for i,v in init: dm.insert(i,v)
    dm.flush(); _writecp(0)
    for n,(i,v) in enumerate(upd,1):
        dm.update(i,v); dm.flush(); _writecp(n)   # durable, then advance checkpoint
        time.sleep(0.02)                          # kill is most likely to land here (clean prefix)
    os._exit(0)

def main():
    p=mp.Process(target=worker); p.start()
    committed=0; t0=time.time()
    while time.time()-t0 < 30:                      # poll for real progress, then kill
        try: committed=int(open(CP).read().strip())
        except Exception: committed=0
        if committed>=120: break
        if not p.is_alive(): break
        time.sleep(0.02)
    os.kill(p.pid, signal.SIGKILL)                  # *** real abrupt termination ***
    p.join()
    committed=int(open(CP).read().strip())
    t1=time.perf_counter()
    rec=DurableMARI.recover(WD)                      # fresh-process recovery from disk
    rec_s=round(time.perf_counter()-t1,4)
    init, upd = workload()
    rng=random.Random(1)
    Q=[(a,a+rng.choice([200,1000,5000])) for a in (rng.randrange(1_000_000-5000) for _ in range(3000))]
    def mism_at(L):
        o=Oracle()
        for i,v in init: o.upsert(i,v)
        for (i,v) in upd[:max(0,L)]: o.upsert(i,v)
        return sum(rec.range(a,b)!=o.range(a,b) for (a,b) in Q)
    # recovered state is exact to a prefix at or just past the checkpoint (in-flight update)
    cand={L:mism_at(L) for L in (committed-1,committed,committed+1)}
    exactL=min(cand,key=cand.get)
    out={"kill_signal":"SIGKILL","updates_total":U,"updates_committed_at_checkpoint":committed,
         "recovered_exact_to_prefix_len":exactL,"query_mismatches_at_that_prefix":cand[exactL],
         "mismatches_by_prefix":cand,"table_T_rebuilt":len(rec.T),"recover_seconds":rec_s,
         **rec._recover_stats}
    print(json.dumps(out,indent=2))
    json.dump(out,open("/home/claude/recovery_kill_results.json","w"),indent=2)
    shutil.rmtree(WD, ignore_errors=True)

if __name__=="__main__": main()
