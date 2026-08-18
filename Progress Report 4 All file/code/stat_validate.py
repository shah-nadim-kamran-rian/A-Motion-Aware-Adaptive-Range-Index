#!/usr/bin/env python3
"""
Test #1 of the upgrade plan: STATISTICAL VALIDATION.

Runs the main MARI-vs-baselines comparison across many random seeds and reports,
for each method and metric:
    mean, 95% confidence interval (bootstrap), and -- for MARI vs each baseline --
    a paired Wilcoxon signed-rank p-value with Holm-Bonferroni correction and
    Cliff's delta effect size.

This turns the headline table from point estimates into a statistically defensible
result, which is what Q1/Q2 reviewers expect.

USAGE:
    pip install sortedcontainers numpy scipy
    python3 stat_validate.py                 # default: 15 seeds
    python3 stat_validate.py --seeds 30      # more seeds = tighter CIs (slower)
    python3 stat_validate.py --n 20000 --updates 120000 --seeds 15

OUTPUT:
    - prints a table to the terminal
    - writes stat_results_raw.csv   (one row per method x metric x seed)
    - writes stat_results_summary.csv (mean, CI, p-value, effect size)

Requires mari.py, mari_v2.py, competitors.py in the same folder.
"""
import argparse, csv, json
import numpy as np
from scipy.stats import wilcoxon
from mari import gen, Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact

M = 1_000_000
METHODS = ["MARI", "ART", "PGM", "Bx"]

def make(name, u):
    if name == "MARI": return MARILocal(M=M, width=1000, guard=50, eps=0.5)
    if name == "ART":  return ART()
    if name == "PGM":  return PGMIndex(eps=16, buffer=2048)
    if name == "Bx":   return BxExact(n_part=4, period=max(1, u // 3))

def one_run(name, init, upd, queries, truth):
    s = make(name, len(upd))
    for i, v in init: s.insert(i, v)
    for _, i, v in upd: s.update(i, v)
    res = 0; mism = 0
    for (a, b), tr in zip(queries, truth):
        out = s.range(a, b); res += len(out); mism += (out != tr)
    reloc = (s.migrations / max(1, s.migrations + s.local_updates)) if name == "MARI" \
            else s.relocations / max(1, len(upd))
    verify = getattr(s, "verifies", 0) / max(1, res)
    scan = getattr(s, "scanned", getattr(s, "scanned_entries", 0)) / max(1, res)
    return {"reloc_per_update": reloc, "verify_per_result": verify,
            "scan_per_result": scan, "mismatches": mism}

def boot_ci(x, B=10000, seed=0):
    rng = np.random.default_rng(seed); x = np.asarray(x, float)
    if len(x) < 2 or np.allclose(x, x[0]): return (float(x.mean()), float(x.mean()))
    bs = [rng.choice(x, len(x), replace=True).mean() for _ in range(B)]
    return tuple(np.percentile(bs, [2.5, 97.5]))

def cliffs_delta(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    gt = sum((ai > b).sum() for ai in a); lt = sum((ai < b).sum() for ai in a)
    return (gt - lt) / (len(a) * len(b))

def holm(pvals):
    idx = np.argsort(pvals); m = len(pvals); adj = np.empty(m); run = 0.0
    for rank, i in enumerate(idx):
        run = max(run, (m - rank) * pvals[i]); adj[i] = min(1.0, run)
    return adj

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=15)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--updates", type=int, default=120000)
    ap.add_argument("--regime", default="uniform")
    args = ap.parse_args()

    metrics = ["reloc_per_update", "verify_per_result", "scan_per_result"]
    data = {m: {k: [] for k in metrics} for m in METHODS}
    exact_all = True
    raw_rows = []

    print(f"Running {args.seeds} seeds ({args.regime}, n={args.n}, updates={args.updates})...")
    for si in range(args.seeds):
        seed = 100 + si
        init, ops, _ = gen(args.regime, M=M, n=args.n, n_updates=args.updates,
                           n_queries=1, delta=50, seed=seed)
        upd = [o for o in ops if o[0] == "u"]
        rng = np.random.default_rng(seed)
        queries = [(int(a), int(a) + int(w)) for a, w in
                   zip(rng.integers(0, M - 5000, 1000), rng.choice([200, 1000, 5000], 1000))]
        orc = Oracle()
        for i, v in init: orc.upsert(i, v)
        for _, i, v in upd: orc.upsert(i, v)
        truth = [orc.range(a, b) for a, b in queries]
        for name in METHODS:
            r = one_run(name, init, upd, queries, truth)
            if r["mismatches"] != 0: exact_all = False
            for k in metrics:
                data[name][k].append(r[k])
                raw_rows.append({"method": name, "metric": k, "seed": seed, "value": r[k]})
        print(f"  seed {si+1}/{args.seeds} done")

    with open("stat_results_raw.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["method", "metric", "seed", "value"])
        w.writeheader(); w.writerows(raw_rows)

    summary = []
    print(f"\nExactness across all runs: {'ALL EXACT (0 mismatches)' if exact_all else 'FAILURES DETECTED'}\n")
    for k in metrics:
        # paired tests: MARI vs each baseline
        pvals, deltas = {}, {}
        for b in ["ART", "PGM", "Bx"]:
            a1 = np.array(data["MARI"][k]); a2 = np.array(data[b][k])
            try:
                p = wilcoxon(a1, a2).pvalue if not np.allclose(a1, a2) else 1.0
            except ValueError:
                p = 1.0
            pvals[b] = p; deltas[b] = cliffs_delta(a1, a2)
        adj = dict(zip(pvals, holm(list(pvals.values()))))
        print(f"== {k} ==")
        print(f"{'method':<7}{'mean':>10}{'95% CI':>22}{'p(Holm) vs MARI':>18}{'effect (Cliff d)':>18}")
        for name in METHODS:
            x = data[name][k]; mean = float(np.mean(x)); lo, hi = boot_ci(x)
            pv = "" if name == "MARI" else f"{adj[name]:.4g}"
            ef = "" if name == "MARI" else f"{deltas[name]:+.2f}"
            print(f"{name:<7}{mean:>10.4f}{f'[{lo:.4f}, {hi:.4f}]':>22}{pv:>18}{ef:>18}")
            summary.append({"metric": k, "method": name, "mean": round(mean, 5),
                            "ci_low": round(lo, 5), "ci_high": round(hi, 5),
                            "p_holm_vs_mari": (None if name == "MARI" else round(adj[name], 6)),
                            "cliffs_delta_vs_mari": (None if name == "MARI" else round(deltas[name], 3))})
        print()
    with open("stat_results_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader(); w.writerows(summary)
    print("wrote stat_results_raw.csv and stat_results_summary.csv")

if __name__ == "__main__":
    main()
