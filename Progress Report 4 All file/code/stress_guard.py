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
def exact_run(s):
    for i,v in init: s.insert(i,v)
    for i,v in upd:  s.update(i,v)
    mism=sum(s.range(a,b)!=tr for (a,b),tr in zip(QS,truth))
    return mism
# competitors (guard-independent): run once
comp={}
for name,ctor in [("ART",ART),("PGM",lambda:PGMIndex(eps=16,buffer=2048)),("Bx",lambda:BxExact(n_part=4,period=max(1,len(upd)//3)))]:
    s=ctor() if name!="ART" else ART()
    mm=exact_run(s); comp[name]=(round(s.relocations/max(1,len(upd)),4), mm)
# MARI at shrinking guards (bucket width also tightened so the guard actually bites)
print(f"STRESS: 30 most-volatile S&P stocks, {len(upd)} updates, median move {int(st.median(drift))}c\n")
print(f"{'config':<22}{'reloc/upd':>11}{'exact':>7}{'  vs ART/PGM/Bx (~0.998, exact)':>34}")
rows=[]
for w,g in [(1000,20),(1000,5),(1000,1),(200,5),(200,1),(50,1)]:
    s=MARILocal(M=M,width=w,guard=g,eps=0.5); mm=exact_run(s)
    rl=round(s.migrations/max(1,s.migrations+s.local_updates),4)
    rows.append({"width":w,"guard":g,"reloc":rl,"mism":mm})
    print(f"MARI w={w:<5} g={g:<4}{'':<6}{rl:>11}{'yes' if mm==0 else 'NO':>7}")
print()
for n,(rl,mm) in comp.items(): print(f"{n:<6} reloc/upd={rl}  exact={'yes' if mm==0 else 'NO'}")
json.dump({"mari":rows,"competitors":comp,"median_drift":int(st.median(drift))},open("stress_guard.json","w"),indent=2)
