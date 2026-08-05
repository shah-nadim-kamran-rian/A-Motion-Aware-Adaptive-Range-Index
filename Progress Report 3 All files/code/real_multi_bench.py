import pandas as pd, numpy as np, glob, random, json
from mari_v2 import MARILocal

def mari_run(stream, M, guards, width, delta_for_guard=None, label=""):
    """stream: list of (id,intvalue) chronological. Returns exactness + migration sweep."""
    rng = random.Random(5); out=[]
    span = M
    for guard in guards:
        m = MARILocal(M=M, width=width, guard=guard, eps=0.5); cur={}; seen=set(); mism=ch=0
        for n,(i,v) in enumerate(stream):
            if i in seen: m.update(i,v)
            else: m.insert(i,v); seen.add(i)
            cur[i]=v
            if n % max(1,len(stream)//2500) == 0 and len(cur)>3:
                a=rng.randint(0,M-1); b=a+rng.randint(1, max(2,span//20))
                if m.range(a,b) != {j for j,c in cur.items() if a<=c<=b}: mism+=1
                ch+=1
        tot=m.local_updates+m.migrations
        out.append(dict(guard=guard, migrations=m.migrations,
                        migration_rate_pct=round(100*m.migrations/max(1,tot),2),
                        mismatch=mism, checks=ch))
    return out

# ---------- US city daily temperatures ----------
rows=[]
for f in glob.glob("data/wx_*.csv"):
    df=pd.read_csv(f, usecols=["Date","Mean.TemperatureF","city"], dtype={"Mean.TemperatureF":str})
    df["t"]=pd.to_numeric(df["Mean.TemperatureF"], errors="coerce")
    df=df[(df.t>=-50)&(df.t<=130)].dropna(subset=["t","Date"]); df["date"]=pd.to_datetime(df["Date"], errors="coerce")
    df=df.dropna(subset=["date"]); df["city"]=df["city"].astype(str)
    rows.append(df[["date","city","t"]])
wx=pd.concat(rows, ignore_index=True)
cities=sorted(wx["city"].unique()); cid={c:k for k,c in enumerate(cities)}
wx["id"]=wx["city"].map(cid); wx["k"]=(wx["t"]).round().astype(int)
OFF=60; wx["k"]=wx["k"]+OFF                      # shift to non-negative
wx=wx.sort_values(["date","id"])
# audit
a=wx.sort_values(["id","date"]); a["d"]=a.groupby("id")["k"].diff().abs(); dd=a["d"].dropna().to_numpy()
Mtemp=int(wx["k"].max())+10
print(f"US CITY TEMPS: cities={len(cities)} updates={len(wx):,} key range[{wx['k'].min()},{wx['k'].max()}](F+{OFF})")
print(f"  |delta|F: median={np.median(dd):.0f} p90={np.percentile(dd,90):.0f} p99={np.percentile(dd,99):.0f} max={dd.max():.0f}")
print("  within: " + "  ".join(f"{t}F:{(dd<=t).mean()*100:.1f}%" for t in (2,5,10,20)))
tstream=list(zip(wx["id"].to_numpy(), wx["k"].to_numpy()))
twx=mari_run(tstream, Mtemp, guards=[3,5,10], width=10)
print("  MARI:", [(r['guard'],r['migration_rate_pct'],r['mismatch']) for r in twx])

# ---------- NBA Elo ----------
nba=pd.read_csv("data/nbaallelo.csv", usecols=["gameorder","team_id","elo_n"]).dropna()
tids=sorted(nba["team_id"].unique()); tid={c:k for k,c in enumerate(tids)}
nba["id"]=nba["team_id"].map(tid); nba["k"]=nba["elo_n"].round().astype(int)
nba=nba.sort_values("gameorder"); Melo=int(nba["k"].max())+50
a=nba.sort_values(["id","gameorder"]); a["d"]=a.groupby("id")["k"].diff().abs(); dd=a["d"].dropna().to_numpy()
print(f"\nNBA ELO: teams={len(tids)} updates={len(nba):,} key range[{nba['k'].min()},{nba['k'].max()}]")
print(f"  |delta|Elo: median={np.median(dd):.0f} p90={np.percentile(dd,90):.0f} p99={np.percentile(dd,99):.0f} max={dd.max():.0f}")
print("  within: " + "  ".join(f"{t}:{(dd<=t).mean()*100:.1f}%" for t in (5,10,20,50)))
estream=list(zip(nba["id"].to_numpy(), nba["k"].to_numpy()))
enba=mari_run(estream, Melo, guards=[10,20,40], width=50)
print("  MARI:", [(r['guard'],r['migration_rate_pct'],r['mismatch']) for r in enba])

json.dump({"temps":{"cities":len(cities),"updates":len(wx),"runs":twx},
           "nba":{"teams":len(tids),"updates":len(nba),"runs":enba}},
          open("real_multi_results.json","w"), indent=2)
print("\ntotal mismatches:", sum(r['mismatch'] for r in twx)+sum(r['mismatch'] for r in enba))
print("wrote real_multi_results.json")
