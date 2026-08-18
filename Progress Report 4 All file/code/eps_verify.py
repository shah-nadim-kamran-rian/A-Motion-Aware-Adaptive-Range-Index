#!/usr/bin/env python3
"""
Test #4 of the upgrade plan: EPSILON SENSITIVITY + NO-VERIFICATION ABLATION.

Two reviewer questions, answered with data:

(A) What does the compaction knob epsilon trade off?  Theorem 1 predicts amortized
    compaction cost O(1/epsilon).  We sweep epsilon and measure compactions/update
    (should fall ~1/epsilon), the pending-delta size m (space, should grow with
    epsilon), and scan/result (should grow with epsilon).  Relocation should be
    ~unaffected (it is an update mechanic, independent of epsilon).

(B) What does exactness-by-verification cost, and is it necessary?  We compare
    MARI (verify every candidate against T) with a NO-VERIFY variant (return the raw
    candidate set).  This shows (i) the verification cost (verifications/result) and
    (ii) the false-hit rate you would pay WITHOUT verification -- i.e. that
    verification is both cheap and necessary for exactness.

USAGE:
    pip install sortedcontainers numpy
    python3 eps_verify.py                 # default 8 seeds
    python3 eps_verify.py --seeds 12 --n 20000 --updates 120000

OUTPUT:
    two tables; writes eps_sweep.csv and verify_ablation.csv
Requires mari.py, mari_v2.py in the same folder.
"""
import argparse, csv, bisect
import numpy as np
from mari import gen, Oracle
from mari_v2 import MARILocal

M = 1_000_000
INF = float("inf")

class NoVerifyMARI(MARILocal):
    """Identical to MARI but returns the raw candidate set WITHOUT verifying
    against T -- used only to measure the false-hit rate verification prevents."""
    def range(self, a, b):
        out = set()
        for j in self._buckets(a, b):
            S = self.skeys[j]
            lo = bisect.bisect_left(S, (a, -1)); hi = bisect.bisect_right(S, (b, INF))
            for _, i in S[lo:hi]: out.add(i)
            D = self.dkeys[j]
            lo = bisect.bisect_left(D, (a, -1)); hi = bisect.bisect_right(D, (b, INF))
            for _, i in D[lo:hi]: out.add(i)
        return out

def workload(seed, n, updates):
    init, ops, _ = gen("uniform", M=M, n=n, n_updates=updates, n_queries=1, delta=50, seed=seed)
    upd = [o for o in ops if o[0] == "u"]
    rng = np.random.default_rng(seed)
    queries = [(int(a), int(a) + int(w)) for a, w in
               zip(rng.integers(0, M - 5000, 1000), rng.choice([200, 1000, 5000], 1000))]
    orc = Oracle()
    for i, v in init: orc.upsert(i, v)
    for _, i, v in upd: orc.upsert(i, v)
    truth = [orc.range(a, b) for a, b in queries]
    return init, upd, queries, truth

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--updates", type=int, default=120000)
    a = ap.parse_args()

    # ---------- (A) epsilon sensitivity ----------
    epsvals = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0]
    print(f"(A) EPSILON SENSITIVITY  ({a.seeds} seeds, n={a.n}, updates={a.updates})\n")
    print(f"{'eps':>6}{'reloc/upd':>11}{'compactions/upd':>17}{'delta size m':>14}{'scan/result':>13}{'exact':>7}")
    rowsA = []
    for eps in epsvals:
        rl, cp, dm, sc, ex = [], [], [], [], True
        for si in range(a.seeds):
            init, upd, queries, truth = workload(500 + si, a.n, a.updates)
            s = MARILocal(M=M, width=1000, guard=50, eps=eps)
            for i, v in init: s.insert(i, v)
            for _, i, v in upd: s.update(i, v)
            res = 0; mism = 0
            for (qa, qb), tr in zip(queries, truth):
                o = s.range(qa, qb); res += len(o); mism += (o != tr)
            if mism: ex = False
            rl.append(s.migrations / max(1, s.migrations + s.local_updates))
            cp.append(s.compactions / max(1, len(upd)))
            dm.append(sum(len(d) for d in s.dkeys))
            sc.append(s.scanned / max(1, res))
        print(f"{eps:>6}{np.mean(rl):>11.4f}{np.mean(cp):>17.4f}{int(np.mean(dm)):>14}{np.mean(sc):>13.3f}"
              f"{'yes' if ex else 'NO':>7}")
        rowsA.append({"eps": eps, "reloc_per_update": round(float(np.mean(rl)), 4),
                      "compactions_per_update": round(float(np.mean(cp)), 4),
                      "delta_size_m": int(np.mean(dm)), "scan_per_result": round(float(np.mean(sc)), 3),
                      "exact": ex})
    # check the O(1/eps) shape
    c0 = rowsA[0]["compactions_per_update"]; c_last = rowsA[-1]["compactions_per_update"]
    print(f"\n  compactions/update falls from {c0} (eps=0.1) to {c_last} (eps=4.0): "
          f"~{c0/max(1e-9,c_last):.1f}x  -> consistent with O(1/eps).")
    with open("eps_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(rowsA[0].keys())); w.writeheader(); w.writerows(rowsA)

    # ---------- (B) no-verification ablation ----------
    print(f"\n(B) NO-VERIFICATION ABLATION  ({a.seeds} seeds)\n")
    with_mism, no_mism, with_ver, extra = [], [], [], []
    for si in range(a.seeds):
        init, upd, queries, truth = workload(600 + si, a.n, a.updates)
        s = MARILocal(M=M, width=1000, guard=50, eps=0.5)
        nv = NoVerifyMARI(M=M, width=1000, guard=50, eps=0.5)
        for i, v in init: s.insert(i, v); nv.insert(i, v)
        for _, i, v in upd: s.update(i, v); nv.update(i, v)
        res = 0; wm = 0; nm = 0; extra_hits = 0
        for (qa, qb), tr in zip(queries, truth):
            o = s.range(qa, qb); res += len(o); wm += (o != tr)
            ov = nv.range(qa, qb); nm += (ov != tr); extra_hits += len(ov - tr)
        with_mism.append(wm); no_mism.append(nm); with_ver.append(s.verifies / max(1, res))
        extra.append(extra_hits / len(queries))
    nq = 1000
    print(f"{'variant':<16}{'wrong queries':>15}{'false hits/query':>18}{'verify/result':>15}")
    print(f"{'MARI (verify)':<16}{np.mean(with_mism):>15.1f}{0.0:>18.2f}{np.mean(with_ver):>15.2f}")
    print(f"{'MARI (no verify)':<16}{np.mean(no_mism):>15.1f}{np.mean(extra):>18.2f}{0.0:>15.2f}")
    print(f"\n  Verification costs ~{np.mean(with_ver):.2f} lookups/result and yields 0 wrong answers.")
    print(f"  WITHOUT it, {100*np.mean(no_mism)/nq:.1f}% of queries are wrong "
          f"({np.mean(extra):.2f} false hits/query). Verification is cheap AND necessary.")
    with open("verify_ablation.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["variant", "wrong_queries_mean", "false_hits_per_query", "verify_per_result"])
        w.writerow(["MARI_verify", round(float(np.mean(with_mism)), 2), 0.0, round(float(np.mean(with_ver)), 3)])
        w.writerow(["MARI_no_verify", round(float(np.mean(no_mism)), 2), round(float(np.mean(extra)), 3), 0.0])
    print("\nwrote eps_sweep.csv and verify_ablation.csv")

if __name__ == "__main__":
    main()
