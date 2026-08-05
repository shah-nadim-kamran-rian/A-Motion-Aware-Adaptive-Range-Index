"""
MARI on a REAL bounded-drift workload: S&P 500 daily closing prices.
Key = price in integer cents (range queries: 'which stocks trade in [a,b]?').
Update stream = date-ordered daily closes (618k updates over 505 keys).
We verify exactness against a brute-force oracle and measure migration behaviour
at several guard widths, on real data rather than a synthetic generator.
"""
import pandas as pd, numpy as np, json, random
from mari_v2 import MARILocal

df = pd.read_csv("data/all_stocks_5yr.csv", usecols=["date","close","Name"]).dropna()
df["date"] = pd.to_datetime(df["date"])
df["cents"] = (df["close"]*100).round().astype(int)
names = sorted(df["Name"].unique()); idof = {n:k for k,n in enumerate(names)}
df["id"] = df["Name"].map(idof)
df = df.sort_values(["date","id"])                 # chronological global stream
stream = list(zip(df["id"].to_numpy(), df["cents"].to_numpy()))
MAXC = int(df["cents"].max()); M = MAXC + 5000
print(f"real stream: {len(stream):,} updates over {len(names)} keys; price universe 0..{MAXC:,} cents")

rng = random.Random(7)
def run(width, guard, eps=0.5, check_every=300, nqueries_cap=2500):
    mari = MARILocal(M=M, width=width, guard=guard, eps=eps)
    cur = {}                       # oracle: id -> current cents
    seen = set(); mism = 0; checks = 0
    for n,(i,v) in enumerate(stream):
        if i in seen: mari.update(i, v)
        else: mari.insert(i, v); seen.add(i)
        cur[i] = v
        if n % check_every == 0 and len(cur) > 5 and checks < nqueries_cap:
            a = rng.randint(0, MAXC); b = a + rng.randint(200, 5000)
            got = mari.range(a, b)
            exp = {i for i,c in cur.items() if a <= c <= b}
            if got != exp: mism += 1
            checks += 1
    tot = mari.local_updates + mari.migrations
    return {
        "width": width, "guard": guard,
        "updates": len(stream), "inserts": len(seen),
        "local_updates": mari.local_updates, "migrations": mari.migrations,
        "migration_rate_pct": round(100*mari.migrations/max(1,tot), 2),
        "compactions": mari.compactions, "max_delta": mari.max_delta,
        "queries_checked": checks, "exactness_mismatches": mism,
        "scanned_per_result": round(mari.scanned / max(1, mari.verifies), 2),
    }

results = []
print(f"\n{'width':>6} {'guard':>6} {'mig%':>7} {'local':>9} {'migr':>7} {'mismatch':>9} {'compactions':>11}")
for width, guard in [(1000,200),(1000,500),(1000,1000),(1000,2000),(500,500)]:
    r = run(width, guard); results.append(r)
    print(f"{r['width']:>6} {r['guard']:>6} {r['migration_rate_pct']:>6}% {r['local_updates']:>9,} "
          f"{r['migrations']:>7,} {r['exactness_mismatches']:>9} {r['compactions']:>11,}")

out = {"dataset":"S&P500 all_stocks_5yr (plotly/datasets)", "keys":len(names),
       "updates":len(stream), "price_universe_cents":MAXC, "runs":results}
json.dump(out, open("real_data_results.json","w"), indent=2)
print("\ntotal exactness mismatches across all runs:", sum(r["exactness_mismatches"] for r in results))
print("wrote real_data_results.json")
