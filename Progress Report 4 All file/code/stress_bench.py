import urllib.request as u, csv, os, random, json, statistics as st
from collections import defaultdict
from mari import Oracle
from mari_v2 import MARILocal
def dl(url,path):
    if not os.path.exists(path): open(path,"wb").write(u.urlopen(url,timeout=120).read())
    return path
# --- most-volatile real equities as a heavy-tailed stress set ---
p=dl("https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv","data/all_stocks.csv")
close=defaultdict(list)
for r in csv.DictReader(open(p)):
    try: close[r["Name"]].append(int(round(float(r["close"])*100)))
    except: pass
close={k:v for k,v in close.items() if len(v)>200}
vol={k:st.median(abs(v[i]-v[i-1]) for i in range(1,len(v))) for k,v in close.items()}
top=sorted(vol,key=vol.get,reverse=True)[:30]           # 30 most volatile
series={k:close[k] for k in top}
ids={e:i for i,e in enumerate(series)}
init=[(ids[e],series[e][0]) for e in series]
maxT=max(len(v) for v in series.values()); upd=[]; drift=[]
for t in range(1,maxT):
    for e in series:
        if t<len(series[e]): upd.append((ids[e],series[e][t])); drift.append(abs(series[e][t]-series[e][t-1]))
M=max(max(v) for v in series.values())+5000
print(f"STRESS set: 30 most-volatile S&P stocks, {len(upd)} updates, median move {int(st.median(drift))}c, "
      f"95th pct move {int(sorted(drift)[int(0.95*len(drift))])}c, key range ~{M}")
def trial(guard,width=1000):
    s=MARILocal(M=M,width=width,guard=guard,eps=0.5); orc=Oracle()
    for i,v in init: s.insert(i,v); orc.upsert(i,v)
    for i,v in upd:  s.update(i,v); orc.upsert(i,v)
    rng=random.Random(1); mism=0
    for _ in range(1000):
        a=rng.randrange(max(1,M-5000)); b=a+rng.choice([200,1000,5000])
        if s.range(a,b)!=orc.range(a,b): mism+=1
    within=sum(d<=guard for d in drift)/len(drift)
    return {"guard":guard,"within_guard_pct":round(100*within,1),
            "reloc_per_update":round(s.migrations/max(1,s.migrations+s.local_updates),4),"mismatches":mism}
rows=[trial(g) for g in (100,50,20,10,5,2)]  # graceful-degradation curve: tighter guard = more stress
json.dump({"stress":"top30_volatile_equities","median_drift":int(st.median(drift)),"rows":rows},
          open("stress_results.json","w"),indent=2)
print("\n=== STRESS TEST: graceful degradation vs delete-insert baseline (0.9900) ===")
print(f"{'guard(c)':>9}{'within%':>9}{'MARI reloc/upd':>16}{'exact':>7}{'  vs baseline':>14}")
for r in rows:
    print(f"{r['guard']:>9}{r['within_guard_pct']:>9}{r['reloc_per_update']:>16}"
          f"{'yes' if r['mismatches']==0 else 'NO':>7}{'0.9900':>14}")
