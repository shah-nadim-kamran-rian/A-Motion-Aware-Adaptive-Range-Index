"""
query_bench.py -- Query-side characterization of MARI (the paper was update-heavy).

Measures, against the REAL MARILocal implementation, the quantities Section 8.4
promises but the original Section 9 never reported:

  * query latency p50 / p99 / mean
  * verification cost: T-lookups (verifies) per result item  -- the cost Section
    4.3 / Section 7 flags as "central to the evaluation"
  * scan amplification: entries scanned per result item
  * query throughput vs. two same-runtime baselines (RadixSorted, SortedList)

swept across (a) query SELECTIVITY (result size) and (b) GUARD width.

Honesty scope: this is one Python runtime, so ABSOLUTE microseconds are
prototype-bound and not a cross-system claim. The implementation-INDEPENDENT
quantities -- verifies/result and scanned/result -- and the SHAPE of the curves
(how cost grows with selectivity and guard) are what the section reports.
Every configuration is checked exact against a brute-force oracle.
"""

import time, random, json, statistics
from mari import gen, Oracle
from mari_v2 import MARILocal, RadixSorted, SortedListIdx

M, N, U, DELTA, WIDTH = 1_000_000, 20_000, 200_000, 50, 1_000


def build(struct, init, updates, oracle=None):
    for i, v in init:
        struct.insert(i, v)
        if oracle: oracle.upsert(i, v)
    for _, i, v in updates:
        struct.update(i, v)
        if oracle: oracle.upsert(i, v)
    return struct


def make_queries(qwidth, nq, seed):
    rnd = random.Random(seed)
    return [(a, a + qwidth) for a in
            (rnd.randrange(max(1, M - qwidth)) for _ in range(nq))]


def profile(struct, queries, oracle=None, check_frac=0.1):
    """Per-query latency + verification/scan deltas. Returns aggregates."""
    lat = []
    tot_res = tot_scan = tot_ver = 0
    mism = 0
    chk_every = max(1, int(1 / check_frac))
    s0 = getattr(struct, "scanned", 0)
    v0 = getattr(struct, "verifies", 0)
    for n, (a, b) in enumerate(queries):
        ps, pv = struct.scanned, getattr(struct, "verifies", 0)
        t0 = time.perf_counter()
        r = struct.range(a, b)
        lat.append((time.perf_counter() - t0) * 1e6)  # microseconds
        tot_res += len(r)
        tot_scan += struct.scanned - ps
        tot_ver += getattr(struct, "verifies", 0) - pv
        if oracle and (n % chk_every == 0) and r != oracle.range(a, b):
            mism += 1
    lat.sort()
    qps = len(queries) / (sum(lat) / 1e6) if lat else 0
    return {
        "queries": len(queries),
        "avg_results": round(tot_res / len(queries), 2),
        "p50_us": round(statistics.median(lat), 2),
        "p99_us": round(lat[min(len(lat) - 1, int(0.99 * len(lat)))], 2),
        "mean_us": round(statistics.fmean(lat), 2),
        "qps": round(qps),
        "scanned_per_result": round(tot_scan / tot_res, 3) if tot_res else None,
        "verifies_per_result": round(tot_ver / tot_res, 3) if tot_res else None,
        "mismatches": mism,
    }


def main():
    out = {"config": {"M": M, "n": N, "updates": U, "drift_delta": DELTA,
                      "bucket_width": WIDTH, "guard_default": DELTA},
           "selectivity_sweep": {}, "guard_sweep": {}, "baseline_throughput": {}}

    # one workload stream; build state + oracle once, reuse across query sets
    init, ops, audit = gen("uniform", M=M, n=N, n_updates=U, n_queries=1,
                           delta=DELTA, seed=7)
    updates = [o for o in ops if o[0] == "u"]
    out["config"]["drift_audit"] = audit

    # ---- (1) selectivity sweep: vary query width -> result size ----
    print("=== selectivity sweep (MARI, guard=delta) ===")
    oracle = Oracle()
    mari = build(MARILocal(M=M, width=WIDTH, guard=DELTA, eps=0.5), init, updates, oracle)
    for qw in [100, 500, 2_000, 10_000, 50_000]:
        qs = make_queries(qw, 4000, seed=100 + qw)
        prof = profile(mari, qs, oracle, check_frac=0.1)
        out["selectivity_sweep"][qw] = prof
        print(f"  qwidth={qw:>6}  res~{prof['avg_results']:>7}  "
              f"p50={prof['p50_us']:>8} us  p99={prof['p99_us']:>9} us  "
              f"scan/res={prof['scanned_per_result']:<6} ver/res={prof['verifies_per_result']:<6} "
              f"mism={prof['mismatches']}")

    # ---- (2) guard sweep at fixed mid selectivity -> verification cost vs guard ----
    print("\n=== guard sweep (qwidth=2000) ===")
    QW = 2_000
    qs = make_queries(QW, 4000, seed=999)
    for g in [0, 50, 250, 1_000]:
        orc = Oracle()
        s = build(MARILocal(M=M, width=WIDTH, guard=g, eps=0.5), init, updates, orc)
        prof = profile(s, qs, orc, check_frac=0.1)
        prof["migration_rate"] = round(s.migrations / U, 4)
        out["guard_sweep"][g] = prof
        print(f"  guard={g:>5}  mig={prof['migration_rate']:<7} "
              f"p50={prof['p50_us']:>8} us  scan/res={prof['scanned_per_result']:<6} "
              f"ver/res={prof['verifies_per_result']:<6} mism={prof['mismatches']}")

    # ---- (3) query throughput vs same-runtime baselines (matched query set) ----
    print("\n=== query throughput vs baselines (qwidth=2000) ===")
    for nm, mk in [("MARI(guard)", lambda: MARILocal(M=M, width=WIDTH, guard=DELTA, eps=0.5)),
                   ("RadixSorted", lambda: RadixSorted(M=M, fanout=WIDTH)),
                   ("SortedList",  lambda: SortedListIdx())]:
        orc = Oracle()
        s = build(mk(), init, updates, orc)
        prof = profile(s, qs, orc, check_frac=0.1)
        out["baseline_throughput"][nm] = prof
        print(f"  {nm:<12} p50={prof['p50_us']:>8} us  qps={prof['qps']:>7}  "
              f"scan/res={prof['scanned_per_result']:<6} "
              f"ver/res={prof['verifies_per_result']} mism={prof['mismatches']}")

    with open("/home/claude/query_bench_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote query_bench_results.json")


if __name__ == "__main__":
    main()
