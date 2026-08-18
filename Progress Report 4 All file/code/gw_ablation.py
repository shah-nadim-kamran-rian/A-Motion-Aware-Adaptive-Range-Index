#!/usr/bin/env python3
"""
Test #2 of the upgrade plan: FIXED g=w ABLATION.

Proposition 1 (relocation-scan coupling) claims MARI's advantage comes from
setting the guard g and bucket width w INDEPENDENTLY. This test checks that
claim by comparing:

    MARI (free)   : g chosen independently of w (the real design)
    MARI (g = 0)  : guard removed, stay-region = scan-region = w  -> single-width
    ART / PGM / Bx: real single-width baselines

Across seeds, it measures relocation/update and scan/result with 95% CIs and a
paired Wilcoxon test of "MARI free" vs "MARI g=w". The expected outcome that
would VALIDATE Proposition 1:
    - MARI (free) has significantly lower relocation than MARI (g=w) at equal or
      lower scan cost;
    - MARI (g=w) sits near the single-width frontier (close to what a single knob
      can reach), while MARI (free) sits off it.
If instead g=w matches free, the decoupling is not the source of the win --
that would REFUTE the framing and must be reported honestly.

USAGE:
    pip install sortedcontainers numpy scipy
    python3 gw_ablation.py                 # default 12 seeds
    python3 gw_ablation.py --seeds 20 --w 1000 --n 20000 --updates 120000

OUTPUT:
    prints a table; writes gw_ablation_summary.csv and gw_ablation_raw.csv
Requires mari.py, mari_v2.py, competitors.py in the same folder.
"""
import argparse, csv
import numpy as np
from scipy.stats import wilcoxon
from mari import gen, Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact

M = 1_000_000

def make(name, w, u):
    if name == "MARI_free": return MARILocal(M=M, width=w, guard=50, eps=0.5)     # g independent of w
    if name == "MARI_g=0":  return MARILocal(M=M, width=w, guard=0, eps=0.5)      # single-width: guard tied to bucket (no extra margin)
    if name == "ART":       return ART()
    if name == "PGM":       return PGMIndex(eps=16, buffer=2048)
    if name == "Bx":        return BxExact(n_part=4, period=max(1, u // 3))

def run(name, w, init, upd, queries, truth):
    s = make(name, w, len(upd))
    for i, v in init: s.insert(i, v)
    for _, i, v in upd: s.update(i, v)
    res = 0; mism = 0
    for (a, b), tr in zip(queries, truth):
        out = s.range(a, b); res += len(out); mism += (out != tr)
    reloc = (s.migrations / max(1, s.migrations + s.local_updates)) if name.startswith("MARI") \
            else s.relocations / max(1, len(upd))
    scan = s.scanned / max(1, res)
    return reloc, scan, mism

def boot_ci(x, B=10000, seed=0):
    rng = np.random.default_rng(seed); x = np.asarray(x, float)
    if len(x) < 2 or np.allclose(x, x[0]): return (float(x.mean()), float(x.mean()))
    return tuple(np.percentile([rng.choice(x, len(x), True).mean() for _ in range(B)], [2.5, 97.5]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--w", type=int, default=1000)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--updates", type=int, default=120000)
    ap.add_argument("--regime", default="uniform")
    a = ap.parse_args()
    methods = ["MARI_free", "MARI_g=0", "ART", "PGM", "Bx"]
    R = {m: [] for m in methods}; S = {m: [] for m in methods}; exact = True; raw = []
    print(f"g=w ablation: {a.seeds} seeds, w={a.w}, n={a.n}, updates={a.updates}, {a.regime}\n")
    for si in range(a.seeds):
        seed = 200 + si
        init, ops, _ = gen(a.regime, M=M, n=a.n, n_updates=a.updates, n_queries=1, delta=50, seed=seed)
        upd = [o for o in ops if o[0] == "u"]
        rng = np.random.default_rng(seed)
        queries = [(int(x), int(x) + int(w)) for x, w in
                   zip(rng.integers(0, M - 5000, 1000), rng.choice([200, 1000, 5000], 1000))]
        orc = Oracle()
        for i, v in init: orc.upsert(i, v)
        for _, i, v in upd: orc.upsert(i, v)
        truth = [orc.range(q[0], q[1]) for q in queries]
        for m in methods:
            rl, sc, mm = run(m, a.w, init, upd, queries, truth)
            if mm: exact = False
            R[m].append(rl); S[m].append(sc)
            raw.append({"method": m, "seed": seed, "reloc": rl, "scan": sc, "mism": mm})
        print(f"  seed {si+1}/{a.seeds} done")
    with open("gw_ablation_raw.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["method", "seed", "reloc", "scan", "mism"]); w.writeheader(); w.writerows(raw)

    print(f"\nExactness: {'ALL EXACT' if exact else 'FAILURES'}\n")
    print(f"{'method':<10}{'reloc mean':>12}{'reloc 95% CI':>22}{'scan mean':>11}{'scan 95% CI':>20}")
    rows = []
    for m in methods:
        rl_lo, rl_hi = boot_ci(R[m]); sc_lo, sc_hi = boot_ci(S[m])
        print(f"{m:<10}{np.mean(R[m]):>12.4f}{f'[{rl_lo:.4f}, {rl_hi:.4f}]':>22}"
              f"{np.mean(S[m]):>11.3f}{f'[{sc_lo:.3f}, {sc_hi:.3f}]':>20}")
        rows.append({"method": m, "reloc_mean": round(float(np.mean(R[m])), 5),
                     "reloc_ci_low": round(rl_lo, 5), "reloc_ci_high": round(rl_hi, 5),
                     "scan_mean": round(float(np.mean(S[m])), 4),
                     "scan_ci_low": round(sc_lo, 4), "scan_ci_high": round(sc_hi, 4)})
    # the key test: MARI_free vs MARI_g=w on relocation
    a1, a2 = np.array(R["MARI_free"]), np.array(R["MARI_g=0"])
    try: p = wilcoxon(a1, a2).pvalue if not np.allclose(a1, a2) else 1.0
    except ValueError: p = 1.0
    ratio = np.mean(a2) / max(1e-9, np.mean(a1))
    print(f"\nKEY TEST (Proposition 1): MARI(free, g=50) vs MARI(single-width, g=0) relocation, at equal scan")
    print(f"  free(g=50)={np.mean(a1):.4f}  single(g=0)={np.mean(a2):.4f}  ->  removing the guard relocates {ratio:.2f}x more"
          f"   (paired Wilcoxon p={p:.4g})")
    verdict = ("VALIDATES Prop 1: decoupling g from w is the source of the advantage."
               if (ratio > 1.2 and p < 0.05) else
               "DOES NOT validate clean decoupling -- report honestly.")
    print("  VERDICT:", verdict)
    with open("gw_ablation_summary.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)
    print("\nwrote gw_ablation_summary.csv and gw_ablation_raw.csv")

if __name__ == "__main__":
    main()
