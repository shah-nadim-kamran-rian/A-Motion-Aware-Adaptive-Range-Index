"""
tuning_bench.py -- a concrete rule for setting the guard, validated on real data.

Corollary 4 ties the per-step relocation probability to the drift mass beyond the
guard: Pr[migrate] <= Pr[|delta| > g]. That suggests a tuning rule:

    to target a migration rate ~= rho, set the guard g to the (1 - rho) quantile
    of the audited per-key drift |delta k|.

We test this directly. For each real domain we (i) compute the exact per-key
drift quantiles from the audit, (ii) set g to the q-quantile, (iii) replay the
real stream through MARI and measure the REALIZED migration rate, and compare it
to the target tail (1 - q). The bucket width is held at the value each domain's
benchmark uses (the width is chosen from the memory / query-amplification budget,
Sections 9.2 and 9.11; the guard is what this rule sets).

Honest expectation: finite bucket width adds boundary crossings, so realized
migration is NOT exactly (1 - q). We report the actual ratio rather than assert
equality, and read off how usable the rule is.
"""
import pandas as pd, numpy as np, glob, random, json
from mari_v2 import MARILocal

QS = [90, 95, 99]


def per_key_drift(ids, vals):
    """abs consecutive difference within each key, in stream order grouped by id."""
    df = pd.DataFrame({"id": ids, "v": vals})
    d = df.groupby("id")["v"].diff().abs().dropna().to_numpy()
    return d


def measure(stream, M, width, guard, eps=0.5, check=False):
    m = MARILocal(M=M, width=width, guard=int(guard), eps=eps)
    cur = {}; seen = set(); mism = 0; ch = 0; rng = random.Random(5)
    step = max(1, len(stream) // 1500)
    for n, (i, v) in enumerate(stream):
        if i in seen: m.update(i, v)
        else: m.insert(i, v); seen.add(i)
        if check:
            cur[i] = v
            if n % step == 0 and len(cur) > 3:
                a = rng.randint(0, M - 1); b = a + rng.randint(1, max(2, M // 50))
                if m.range(a, b) != {j for j, c in cur.items() if a <= c <= b}: mism += 1
                ch += 1
    tot = m.local_updates + m.migrations
    return {"migrations": m.migrations,
            "migration_rate_pct": round(100 * m.migrations / max(1, tot), 3),
            "mismatch": mism, "checks": ch}


def load_sp500():
    df = pd.read_csv("data/all_stocks_5yr.csv", usecols=["date", "close", "Name"]).dropna()
    df["date"] = pd.to_datetime(df["date"]); df["cents"] = (df["close"] * 100).round().astype(int)
    names = sorted(df["Name"].unique()); idof = {n: k for k, n in enumerate(names)}
    df["id"] = df["Name"].map(idof)
    order = df.sort_values(["Name", "date"])               # per-key order for drift audit
    drift = per_key_drift(order["id"].to_numpy(), order["cents"].to_numpy())
    s = df.sort_values(["date", "id"])                      # chronological global stream
    stream = list(zip(s["id"].to_numpy(), s["cents"].to_numpy()))
    M = int(df["cents"].max()) + 5000
    return dict(name="S&P 500 prices (cents)", unit="c", stream=stream, drift=drift,
                M=M, width=1000, keys=len(names))


def load_nba():
    nba = pd.read_csv("data/nbaallelo.csv", usecols=["gameorder", "team_id", "elo_n"]).dropna()
    tids = sorted(nba["team_id"].unique()); tid = {c: k for k, c in enumerate(tids)}
    nba["id"] = nba["team_id"].map(tid); nba["k"] = nba["elo_n"].round().astype(int)
    order = nba.sort_values(["id", "gameorder"])
    drift = per_key_drift(order["id"].to_numpy(), order["k"].to_numpy())
    s = nba.sort_values("gameorder")
    stream = list(zip(s["id"].to_numpy(), s["k"].to_numpy()))
    M = int(nba["k"].max()) + 50
    return dict(name="NBA Elo ratings", unit="Elo", stream=stream, drift=drift,
                M=M, width=50, keys=len(tids))


def load_temps():
    rows = []
    for f in glob.glob("data/wx_*.csv"):
        df = pd.read_csv(f, usecols=["Date", "Mean.TemperatureF", "city"],
                         dtype={"Mean.TemperatureF": str})
        df["t"] = pd.to_numeric(df["Mean.TemperatureF"], errors="coerce")
        df = df[(df.t >= -50) & (df.t <= 130)].dropna(subset=["t", "Date"])
        df["date"] = pd.to_datetime(df["Date"], errors="coerce")
        rows.append(df.dropna(subset=["date"])[["date", "city", "t"]])
    wx = pd.concat(rows, ignore_index=True)
    cities = sorted(wx["city"].unique()); cid = {c: k for k, c in enumerate(cities)}
    wx["id"] = wx["city"].map(cid); wx["k"] = wx["t"].round().astype(int) + 60   # shift >=0
    order = wx.sort_values(["id", "date"])
    drift = per_key_drift(order["id"].to_numpy(), order["k"].to_numpy())
    s = wx.sort_values(["date", "id"])
    stream = list(zip(s["id"].to_numpy(), s["k"].to_numpy()))
    M = int(wx["k"].max()) + 10
    return dict(name="US city temperatures (deg F)", unit="F", stream=stream, drift=drift,
                M=M, width=10, keys=len(cities))


def main():
    out = {"rule": "guard = (1-rho) quantile of per-key |delta k|; target migration ~= rho",
           "domains": {}}
    for loader in (load_sp500, load_nba, load_temps):
        ds = loader()
        d = ds["drift"]
        quant = {q: float(np.percentile(d, q)) for q in QS}
        med = float(np.median(d))
        print(f"\n=== {ds['name']}  (keys={ds['keys']}, updates={len(ds['stream']):,}, "
              f"width={ds['width']}) ===")
        print(f"  per-key |delta|: median={med:.0f}{ds['unit']}  "
              + "  ".join(f"p{q}={quant[q]:.0f}{ds['unit']}" for q in QS))
        rows = []
        for q in QS:
            g = max(0, round(quant[q]))
            target = round(100 * (1 - q / 100), 2)
            tail = round(100 * float((d > g).mean()), 3)     # actual mass beyond g
            res = measure(ds["stream"], ds["M"], ds["width"], g, check=True)
            ratio = round(res["migration_rate_pct"] / target, 2) if target else None
            row = {"quantile_q": q, "guard": g, "target_migration_pct": target,
                   "drift_mass_beyond_guard_pct": tail,
                   "measured_migration_pct": res["migration_rate_pct"],
                   "measured_over_target": ratio,
                   "exactness_mismatches": res["mismatch"], "checks": res["checks"]}
            rows.append(row)
            print(f"  q={q}: guard={g:<5} target(1-q)={target:<5}%  "
                  f"tail>g={tail:<6}%  measured_migration={res['migration_rate_pct']:<6}%  "
                  f"ratio={ratio}  mism={res['mismatch']}")
        out["domains"][ds["name"]] = {"keys": ds["keys"], "updates": len(ds["stream"]),
                                      "width": ds["width"], "median_drift": med,
                                      "quantiles": quant, "settings": rows}
    json.dump(out, open("/home/claude/tuning_results.json", "w"), indent=2)
    print("\nwrote tuning_results.json")


if __name__ == "__main__":
    main()
