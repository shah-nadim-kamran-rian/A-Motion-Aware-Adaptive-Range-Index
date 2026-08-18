"""
hetero_demo.py -- the heteroscedastic per-region drift model, on real data.

The clean model assumes one global drift bound delta. Real drift is
HETEROSCEDASTIC: on S&P prices, dollar moves grow with the price level, so a
single global guard is mis-provisioned -- too tight for expensive stocks (they
over-migrate), too loose for cheap ones. MARI's adaptive widths permit a
per-region guard delta(.) set from each region's own drift. We formalize that
here and measure it: partition stocks into price bands, set (a) one global guard
vs (b) a per-region guard from each band's drift quantile, and compare the
realized migration rate per band.

Model. Replace the single bound by a region map delta : R -> R+, where region r
(a bucket or band) has its own bound. Setting the per-region guard
  g(r) = Q_{|delta k| in r}(1 - rho)
targets the same migration rho in every region; a global g = Q_all(1-rho) does
not, because the per-region tails differ.
"""
import pandas as pd, numpy as np, json
from mari_v2 import MARILocal


def load_sp_bands():
    df = pd.read_csv("data/all_stocks_5yr.csv", usecols=["date", "close", "Name"]).dropna()
    df["date"] = pd.to_datetime(df["date"])
    df["cents"] = (df["close"] * 100).round().astype(int)
    names = sorted(df["Name"].unique()); idof = {n: k for k, n in enumerate(names)}
    df["id"] = df["Name"].map(idof)
    # per-stock median price -> price band (terciles)
    med = df.groupby("id")["cents"].median()
    q1, q2 = med.quantile([1/3, 2/3])
    band = med.apply(lambda m: "low" if m <= q1 else ("mid" if m <= q2 else "high"))
    df["band"] = df["id"].map(band)
    # per-key drift
    order = df.sort_values(["id", "date"])
    order["d"] = order.groupby("id")["cents"].diff().abs()
    return df, order, band


def band_drift_quantiles(order, band, q=95):
    out = {}
    for bnd in ("low", "mid", "high"):
        ids = set(band[band == bnd].index)
        d = order[order["id"].isin(ids)]["d"].dropna().to_numpy()
        out[bnd] = {"median": float(np.median(d)), "p95": float(np.percentile(d, q)),
                    "p99": float(np.percentile(d, 99))}
    alld = order["d"].dropna().to_numpy()
    out["__global_p95__"] = float(np.percentile(alld, q))
    return out


def migration(df, band, bnd, guard, M, width=1000):
    ids = set(band[band == bnd].index)
    s = df[df["id"].isin(ids)].sort_values(["date", "id"])
    stream = list(zip(s["id"].to_numpy(), s["cents"].to_numpy()))
    idx = MARILocal(M=M, width=width, guard=int(guard), eps=0.5)
    seen = set()
    for i, v in stream:
        if i in seen: idx.update(i, v)
        else: idx.insert(i, v); seen.add(i)
    tot = idx.migrations + idx.local_updates
    return round(100 * idx.migrations / max(1, tot), 3)


def main():
    df, order, band = load_sp_bands()
    M = int(df["cents"].max()) + 5000
    q = band_drift_quantiles(order, band)
    g_global = max(1, round(q["__global_p95__"]))
    out = {"model": "per-region guard g(r) = (1-rho) quantile of region r's drift",
           "target_rho_pct": 5.0, "global_guard_cents": g_global,
           "band_drift": {b: q[b] for b in ("low", "mid", "high")}, "bands": {}}
    print(f"global p95 guard = {g_global}c   (target migration ~5%)")
    print(f"{'band':<6}{'median|d|':>10}{'p95|d|':>9}{'g_global->mig%':>16}{'g_region':>10}{'g_region->mig%':>16}")
    for bnd in ("low", "mid", "high"):
        g_region = max(1, round(q[bnd]["p95"]))
        m_global = migration(df, band, bnd, g_global, M)
        m_region = migration(df, band, bnd, g_region, M)
        out["bands"][bnd] = {"median_drift": q[bnd]["median"], "p95_drift": q[bnd]["p95"],
                             "global_guard": g_global, "migration_global_guard_pct": m_global,
                             "region_guard": g_region, "migration_region_guard_pct": m_region}
        print(f"{bnd:<6}{q[bnd]['median']:>10.0f}{q[bnd]['p95']:>9.0f}"
              f"{m_global:>15.2f}%{g_region:>10}{m_region:>15.2f}%")
    json.dump(out, open("/home/claude/hetero_results.json", "w"), indent=2)
    print("wrote hetero_results.json")


if __name__ == "__main__":
    main()
