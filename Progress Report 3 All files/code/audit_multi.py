import pandas as pd, numpy as np

def audit(name, df, idcol, valcol, ordercol, scale=1.0, unit="units"):
    d = df[[idcol, valcol, ordercol]].dropna().copy()
    d["k"] = (d[valcol]*scale).round().astype(int)
    d = d.sort_values([idcol, ordercol])
    d["delta"] = d.groupby(idcol)["k"].diff().abs()
    dd = d["delta"].dropna().to_numpy()
    keys = d[idcol].nunique()
    print(f"\n=== {name} ===")
    print(f"keys={keys}  updates={len(d):,}  transitions={len(dd):,}  key range [{d['k'].min()},{d['k'].max()}] ({unit})")
    print(f"|delta|: median={np.median(dd):.0f} mean={dd.mean():.1f} p90={np.percentile(dd,90):.0f} "
          f"p99={np.percentile(dd,99):.0f} p99.9={np.percentile(dd,99.9):.0f} max={dd.max():.0f}")
    for thr in [2,5,10,20,50]:
        print(f"   within {thr:>3} {unit}: {(dd<=thr).mean()*100:5.1f}%")
    return dict(name=name, keys=keys, updates=len(d), median=float(np.median(dd)),
                p99=float(np.percentile(dd,99)), within10=float((dd<=10).mean()*100),
                within20=float((dd<=20).mean()*100))

nba = pd.read_csv("data/nbaallelo.csv")
audit("NBA Elo ratings (FiveThirtyEight)", nba, "team_id", "elo_n", "gameorder", scale=1.0, unit="Elo")
