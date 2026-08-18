"""
memory_bench.py -- how much memory does the authoritative table T actually cost?

The paper claims O(n + m) space but never measures MARI's footprint, leaving open
the worry that T (a full id->key map) quietly cancels the durable-write win. We
quantify it two ways on the same bounded-drift workload:

  (1) implementation-INDEPENDENT record count: how many stored (id,key)-equivalent
      entries each structure holds per live item. This is the robust metric.
  (2) measured RETAINED memory (tracemalloc, after gc) as a concrete but
      prototype-bound figure.

What lives in each structure, per live item:
  SortedListIdx / RadixSorted : cur dict (id->key) + sorted (key,id)        = 2x
  MARILocal (as implemented)  : T (id->key,bucket) + smap (id->key)
                                 + skeys (key,id) + eps-bounded delta        ~ 3x + delta
  MARILocal (lean)            : T + skeys + delta   (smap is redundant with
                                 T and can be dropped; skeys rebuilt from T)  ~ 2x + delta

So MARI's INHERENT overhead over a plain ordered index is the per-item bucket
field in T plus the eps-bounded delta tail -- not a multiplicative blow-up.
"""
import gc, tracemalloc, json
from mari import gen
from mari_v2 import MARILocal, SortedListIdx, RadixSorted

M, N, U, DELTA, WIDTH, EPS = 1_000_000, 20_000, 200_000, 50, 1_000, 0.5


def build(maker):
    s = maker()
    for i, v in INIT: s.insert(i, v)
    for _, i, v in UPD: s.update(i, v)
    return s


def measure(maker):
    gc.collect(); tracemalloc.start()
    s = build(maker)
    gc.collect()
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return s, cur


def mari_records(s):
    T = len(s.T)
    smap = sum(len(d) for d in s.smap)
    skeys = sum(len(x) for x in s.skeys)
    dmap = sum(len(d) for d in s.dmap)
    dkeys = sum(len(x) for x in s.dkeys)
    dtomb = sum(len(x) for x in s.dtomb)
    return {"T": T, "stable_dict": smap, "stable_sorted": skeys,
            "delta_dict": dmap, "delta_sorted": dkeys, "delta_tomb": dtomb,
            "total_records": T + smap + skeys + dmap + dkeys + dtomb,
            "lean_records": T + skeys + dmap + dkeys}   # drop redundant smap


def base_records(s, leaves=False):
    cur = len(s.cur)
    if leaves: sorted_n = sum(len(L) for L in s.leaf)
    else:      sorted_n = len(s.sl)
    return {"cur_dict": cur, "sorted": sorted_n, "total_records": cur + sorted_n}


def main():
    global INIT, UPD
    init, ops, _ = gen("uniform", M=M, n=N, n_updates=U, n_queries=1, delta=DELTA, seed=17)
    INIT = init; UPD = [o for o in ops if o[0] == "u"]

    out = {"config": {"M": M, "n": N, "updates": U, "bucket_width": WIDTH, "eps": EPS},
           "structures": {}}

    # MARI
    s, mem = measure(lambda: MARILocal(M=M, width=WIDTH, guard=DELTA, eps=EPS))
    live = len(s.T); rec = mari_records(s)
    out["structures"]["MARI (reference)"] = {
        "live_items": live, "records": rec,
        "records_per_item": round(rec["total_records"] / live, 3),
        "retained_bytes": mem, "bytes_per_item": round(mem / live, 1)}
    out["structures"]["MARI (lean, T+skeys+delta)"] = {
        "live_items": live, "total_records": rec["lean_records"],
        "records_per_item": round(rec["lean_records"] / live, 3)}
    del s

    # SortedList baseline
    s, mem = measure(lambda: SortedListIdx())
    live = len(s.cur); rec = base_records(s)
    out["structures"]["SortedList (baseline)"] = {
        "live_items": live, "records": rec,
        "records_per_item": round(rec["total_records"] / live, 3),
        "retained_bytes": mem, "bytes_per_item": round(mem / live, 1)}
    del s

    # Radix baseline
    s, mem = measure(lambda: RadixSorted(M=M, fanout=WIDTH))
    live = len(s.cur); rec = base_records(s, leaves=True)
    out["structures"]["RadixSorted (baseline)"] = {
        "live_items": live, "records": rec,
        "records_per_item": round(rec["total_records"] / live, 3),
        "retained_bytes": mem, "bytes_per_item": round(mem / live, 1)}
    del s

    base = out["structures"]["SortedList (baseline)"]["records_per_item"]
    for nm in ["MARI (reference)", "MARI (lean, T+skeys+delta)"]:
        out["structures"][nm]["x_over_ordered_index"] = round(
            out["structures"][nm]["records_per_item"] / base, 2)

    json.dump(out, open("/home/claude/memory_results.json", "w"), indent=2)
    for nm, v in out["structures"].items():
        rpi = v["records_per_item"]; bpi = v.get("bytes_per_item", "-")
        xo = v.get("x_over_ordered_index", "")
        print(f"  {nm:<34} records/item={rpi:<6} bytes/item={bpi:<7} "
              f"{('('+str(xo)+'x ordered index)') if xo else ''}")
    print("\nwrote memory_results.json")


if __name__ == "__main__":
    main()
