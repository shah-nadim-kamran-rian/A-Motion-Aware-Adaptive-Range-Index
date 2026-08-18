import urllib.request as u, csv, os, random, json, statistics as st
from collections import defaultdict
from mari import Oracle
from mari_v2 import MARILocal
def dl(url,path):
    if not os.path.exists(path): open(path,"wb").write(u.urlopen(url,timeout=60).read())
    return path
def build(series,M):
    ids={e:i for i,e in enumerate(series)}
    init=[(ids[e],series[e][0]) for e in series]
    maxT=max(len(v) for v in series.values()); upd=[]; drift=[]
    for t in range(1,maxT):
        for e in series:
            v=series[e]
            if t<len(v): upd.append((ids[e],v[t])); drift.append(abs(v[t]-v[t-1]))
    return init,upd,drift
def run(name,series,M,guard,width=1000,qn=1500):
    init,upd,drift=build(series,M)
    s=MARILocal(M=M,width=width,guard=guard,eps=0.5); orc=Oracle()
    for i,v in init: s.insert(i,v); orc.upsert(i,v)
    for i,v in upd:  s.update(i,v); orc.upsert(i,v)
    rng=random.Random(1); mism=0
    for _ in range(qn):
        a=rng.randrange(max(1,M-5000)); b=a+rng.choice([200,1000,5000])
        if s.range(a,b)!=orc.range(a,b): mism+=1
    return {"dataset":name,"entities":len(series),"updates":len(upd),
            "median_drift":int(st.median(drift)) if drift else 0,"guard":guard,
            "within_guard_pct":round(100*sum(d<=guard for d in drift)/max(1,len(drift)),1),
            "reloc_per_update":round(s.migrations/max(1,s.migrations+s.local_updates),4),"mismatches":mism}
res=[]
# NEW CLEAN 1: Forex — rate x100 (cents), filter sane rates, cap keys
p=dl("https://raw.githubusercontent.com/datasets/exchange-rates/main/data/daily.csv","data/forex.csv")
fx=defaultdict(list)
for row in csv.DictReader(open(p)):
    try:
        r=float(row["Exchange rate"])
        if 0.05<=r<=2000: fx[row["Country"]].append(int(round(r*100)))
    except: pass
fx={k:v for k,v in fx.items() if len(v)>100}
M=max(max(v) for v in fx.values())+5000
print(f"forex: {len(fx)} currencies, keymax~{M}")
res.append(run("Forex (exchange rates)",fx,M,guard=30)); print("  ->",res[-1]["reloc_per_update"],"reloc, mism",res[-1]["mismatches"])
# NEW CLEAN 2: Oil Brent single series drift profile
p=dl("https://raw.githubusercontent.com/datasets/oil-prices/main/data/brent-daily.csv","data/oil.csv")
vals=[int(round(float(r["Price"])*100)) for r in csv.DictReader(open(p)) if r.get("Price")]
drift=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals))]
res.append({"dataset":"Oil Brent (single series)","entities":1,"updates":len(vals)-1,
    "median_drift":int(st.median(drift)),"guard":50,
    "within_guard_pct":round(100*sum(d<=50 for d in drift)/len(drift),1),
    "reloc_per_update":None,"mismatches":"n/a"})
print("oil: median drift",res[-1]["median_drift"],"cents,",res[-1]["within_guard_pct"],"% within 50c")
json.dump(res,open("new_real_results.json","w"),indent=2)
print("\n=== NEW REAL DATASETS ===")
for r in res:
    print(f"{r['dataset']:<26} entities={r['entities']:<5} upd={r['updates']:<7} medΔ={r['median_drift']:<5} "
          f"guard={r['guard']} within={r['within_guard_pct']}% reloc={r['reloc_per_update']} exact={'yes' if r['mismatches']==0 else r['mismatches']}")
