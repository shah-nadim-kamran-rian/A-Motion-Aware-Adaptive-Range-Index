#!/usr/bin/env python3
"""
Test #3 of the upgrade plan: STRESS SCAN COMPARISON (done right).

The earlier stress test used only 30 keys over a large universe, so most random
range queries returned zero results, which inflated any per-result ratio
(scan/result, verify/result). This version fixes that:

  - uses the ~200 most-volatile real S&P stocks (heavy-tailed moves),
  - draws query bands FROM the live key distribution (so queries actually return
    results and per-result metrics are meaningful),
  - reports relocation/update, scan/result, verify/result with 95% CIs across
    seeds, for MARI vs ART / PGM / Bx, all verified exact.

This lets us say honestly how MARI compares to strong baselines on BOTH relocation
AND query cost under stress -- not just relocation.

USAGE:
    pip install sortedcontainers numpy scipy
    python3 stress_scan.py                 # default 200 stocks, 8 seeds
    python3 stress_scan.py --stocks 300 --seeds 12 --guard 20

OUTPUT:
    table + stress_scan_summary.csv
Requires mari.py, mari_v2.py, competitors.py in the same folder + internet
(downloads the S&P dataset once to data/all_stocks.csv).
"""
import argparse, csv, os, urllib.request as u, statistics as st
from collections import defaultdict
import numpy as np
from mari import Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact

def load_volatile(nstocks):
    os.makedirs("data", exist_ok=True); path = "data/all_stocks.csv"
    if not os.path.exists(path):
        open(path, "wb").write(u.urlopen(
            "https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv", timeout=120).read())
    close = defaultdict(list)
    for r in csv.DictReader(open(path)):
        try: close[r["Name"]].append(int(round(float(r["close"]) * 100)))
        except Exception: pass
    close = {k: v for k, v in close.items() if len(v) > 200}
    vol = {k: st.median(abs(v[i] - v[i-1]) for i in range(1, len(v))) for k, v in close.items()}
    top = sorted(vol, key=vol.get, reverse=True)[:nstocks]
    return {k: close[k] for k in top}

def build_stream(series):
    ids = {e: i for i, e in enumerate(series)}
    init = [(ids[e], series[e][0]) for e in series]
    maxT = max(len(v) for v in series.values()); upd = []; drift = []
    for t in range(1, maxT):
        for e in series:
            if t < len(series[e]):
                upd.append((ids[e], series[e][t])); drift.append(abs(series[e][t] - series[e][t-1]))
    return init, upd, drift

def make(name, u_, M):
    if name == "MARI": return MARILocal(M=M, width=1000, guard=ARGS.guard, eps=0.5)
    if name == "ART":  return ART()
    if name == "PGM":  return PGMIndex(eps=16, buffer=2048)
    if name == "Bx":   return BxExact(n_part=4, period=max(1, u_ // 3))

def run(name, init, upd, queries, truth, M):
    s = make(name, len(upd), M)
    for i, v in init: s.insert(i, v)
    for i, v in upd:  s.update(i, v)
    res = 0; mism = 0
    for (a, b), tr in zip(queries, truth):
        out = s.range(a, b); res += len(out); mism += (out != tr)
    reloc = (s.migrations / max(1, s.migrations + s.local_updates)) if name == "MARI" \
            else s.relocations / max(1, len(upd))
    return (reloc, s.scanned / max(1, res), getattr(s, "verifies", 0) / max(1, res), mism, res)

def boot_ci(x, seed=0):
    rng = np.random.default_rng(seed); x = np.asarray(x, float)
    if len(x) < 2 or np.allclose(x, x[0]): return (float(x.mean()), float(x.mean()))
    return tuple(np.percentile([rng.choice(x, len(x), True).mean() for _ in range(10000)], [2.5, 97.5]))

def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--guard", type=int, default=20)
    ARGS = ap.parse_args()

    series = load_volatile(ARGS.stocks)
    init, upd, drift = build_stream(series)
    M = max(max(v) for v in series.values()) + 5000
    # live key positions (final state) to draw realistic query centers from
    final = {}
    for i, v in init: final[i] = v
    for i, v in upd:  final[i] = v
    keyvals = np.array(list(final.values()))
    print(f"STRESS-SCAN: {len(series)} most-volatile S&P stocks, {len(upd)} updates, "
          f"median move {int(st.median(drift))}c, guard={ARGS.guard}c\n")

    methods = ["MARI", "ART", "PGM", "Bx"]
    R = {m: [] for m in methods}; SC = {m: [] for m in methods}; VE = {m: [] for m in methods}
    exact = True; avg_res = []
    for si in range(ARGS.seeds):
        rng = np.random.default_rng(300 + si)
        # queries centered on real key density so they return results
        centers = rng.choice(keyvals, 1200)
        widths = rng.choice([500, 2000, 8000], 1200)
        queries = [(max(1, int(c - w // 2)), min(M - 2, int(c + w // 2))) for c, w in zip(centers, widths)]
        queries = [(a, b) for a, b in queries if a < b]
        orc = Oracle()
        for i, v in init: orc.upsert(i, v)
        for i, v in upd:  orc.upsert(i, v)
        truth = [orc.range(a, b) for a, b in queries]
        for m in methods:
            try:
                rl, sc, ve, mm, res = run(m, init, upd, queries, truth, M)
            except Exception as e:
                print(f"    [{m} skipped this seed: {type(e).__name__} in its reference impl]"); continue
            if mm: exact = False
            R[m].append(rl); SC[m].append(sc); VE[m].append(ve)
            if m == "MARI": avg_res.append(res / len(queries))
        print(f"  seed {si+1}/{ARGS.seeds} done")

    print(f"\nAvg results/query (MARI): {np.mean(avg_res):.1f}  (>1 means per-result metrics are meaningful)")
    print(f"Exactness: {'ALL EXACT' if exact else 'FAILURES'}\n")
    print(f"{'method':<7}{'reloc/upd (95% CI)':>26}{'scan/result (95% CI)':>26}{'verify/result':>15}")
    rows = []
    for m in [mm for mm in methods if R[mm]]:
        rl, rh = boot_ci(R[m]); sl, sh = boot_ci(SC[m]); vl, vh = boot_ci(VE[m])
        print(f"{m:<7}{f'{np.mean(R[m]):.3f} [{rl:.3f},{rh:.3f}]':>26}"
              f"{f'{np.mean(SC[m]):.2f} [{sl:.2f},{sh:.2f}]':>26}{np.mean(VE[m]):>15.2f}")
        rows.append({"method": m, "reloc_mean": round(float(np.mean(R[m])), 4),
                     "reloc_ci": f"[{rl:.4f},{rh:.4f}]",
                     "scan_mean": round(float(np.mean(SC[m])), 3), "scan_ci": f"[{sl:.3f},{sh:.3f}]",
                     "verify_mean": round(float(np.mean(VE[m])), 3)})
    with open("stress_scan_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("\nwrote stress_scan_summary.csv")

if __name__ == "__main__":
    main()
