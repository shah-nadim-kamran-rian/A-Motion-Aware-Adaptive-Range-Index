import pandas as pd, numpy as np
df = pd.read_csv("data/all_stocks_5yr.csv", usecols=["date","close","Name"]).dropna()
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["Name","date"])
df["cents"] = (df["close"]*100).round().astype(int)
# consecutive per-stock delta
df["d"] = df.groupby("Name")["cents"].diff().abs()
d = df["d"].dropna().to_numpy()
print(f"stocks={df['Name'].nunique()}  rows={len(df)}  transitions={len(d):,}")
print(f"price cents: min={df['cents'].min()} max={df['cents'].max()} (universe ~{df['cents'].max():,})")
print(f"|delta| cents: mean={d.mean():.1f} median={np.median(d):.0f} p90={np.percentile(d,90):.0f} "
      f"p99={np.percentile(d,99):.0f} p99.9={np.percentile(d,99.9):.0f} max={d.max():.0f}")
print("fraction of day-to-day moves within delta cents:")
for dd in [50,100,200,300,500,1000,2000]:
    print(f"   |delta| <= {dd:>5} cents (${dd/100:>5.2f}):  {(d<=dd).mean()*100:5.1f}%")
# heterogeneity by price level
print("median |delta| by price band:")
bands=[(0,2000),(2000,5000),(5000,10000),(10000,30000),(30000,10**9)]
for lo,hi in bands:
    m=(df['cents']>=lo)&(df['cents']<hi)
    sub=df.loc[m,'d'].dropna()
    if len(sub): print(f"   ${lo/100:>6.0f}-${hi/100 if hi<10**8 else 9999:>5.0f}: n={len(sub):>7,}  median|delta|={np.median(sub):>5.0f}c  p99={np.percentile(sub,99):>6.0f}c")
