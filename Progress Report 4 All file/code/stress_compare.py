import urllib.request as u, csv, os, random, json, statistics as st
from collections import defaultdict
from mari import Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact
def dl(url,path):
    if not os.path.exists(path): open(path,"wb").write(u.urlopen(url,timeout=120).read())
    return path
p=dl("https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv","data/all_stocks.csv")
close=defaultdict(list)
for r in csv.DictReader(open(p)):
    try: close[r["Name"]].append(int(round(float(r["close"])*100)))
    except: pass
close={k:v for k,v in close.items() if len(v)>200}
vol={k:st.median(abs(v[i]-v[i-1]) for i in range(1,len(v))) for k,v in close.items()}
top=sorted(vol,key=vol.get,reverse=True)[:30]
series={k:close[k] for k in top}; ids={e:i for i,e in enumerate(series)}
init=[(ids[e],series[e][0]) for e in series]
maxT=max(len(v) for v in series.values()); upd=[]; drift=[]
for t in range(1,maxT):
    for e in series:
        if t<len(series[e]): upd.append((ids[e],series[e][t])); drift.append(abs(series[e][t]-series[e][t-1]))
M=max(max(v) for v in series.values())+5000
orc=Oracle()
for i,v in init: orc.upsert(i,v)
for i,v in upd:  orc.upsert(i,v)
rng=random.Random(1); QS=[(a,a+rng.choice([200,1000,5000])) for a in (rng.randrange(max(1,M-5000)) for _ in range(1000))]
truth=[orc.range(a,b) for a,b in QS]
def build(name):
    if name=="MARI": return MARILocal(M=M,width=1000,guard=20,eps=0.5)
    if name=="ART":  return ART()
    if name=="PGM":  return PGMIndex(eps=16,buffer=2048)
    if name=="Bx":   return BxExact(n_part=4,period=max(1,len(upd)//3))
def run(name):
    s=build(name)
    for i,v in init: s.insert(i,v)
    for i,v in upd:  s.update(i,v)
    res=0; mism=0
    for (a,b),tr in zip(QS,truth):
        out=s.range(a,b); res+=len(out); mism+=(out!=tr)
    reloc=(s.migrations/max(1,s.migrations+s.local_updates)) if name=="MARI" else s.relocations/max(1,len(upd))
    ver=getattr(s,"verifies",0)/max(1,res); scan=s.scanned/max(1,res)
    return {"method":name,"reloc_per_update":round(reloc,4),"verify_per_result":round(ver,2),
            "scan_per_result":round(scan,2),"mismatches":mism}
rows=[run(m) for m in ["MARI","ART","PGM","Bx"]]
json.dump({"stress":"top30_volatile_equities","median_drift":int(st.median(drift)),"updates":len(upd),"rows":rows},
          open("stress_compare.json","w"),indent=2)
print(f"STRESS: 30 most-volatile S&P stocks, {len(upd)} updates, median move {int(st.median(drift))}c (guard=20c)\n")
print(f"{'Method':<7}{'reloc/upd':>11}{'verify/result':>15}{'scan/result':>13}{'exact':>7}")
for r in rows:
    print(f"{r['method']:<7}{r['reloc_per_update']:>11}{r['verify_per_result']:>15}{r['scan_per_result']:>13}{'yes' if r['mismatches']==0 else 'NO':>7}")
