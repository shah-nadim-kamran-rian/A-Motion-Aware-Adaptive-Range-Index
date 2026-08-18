"""Runs each method in its own process, collects RSS + CPU time, checks exactness
separately, prints and saves a fair comparison table."""
import subprocess, json, random
from mari import gen, Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact
M=1_000_000
def make(name,u):
    return {"MARI":MARILocal(M=M,width=1000,guard=50,eps=0.5),"ART":ART(),
            "PGM":PGMIndex(eps=16,buffer=2048),"Bx":BxExact(n_part=4,period=max(1,u//3))}[name]
def exact(name):  # untimed exactness check vs oracle
    init,ops,_=gen("uniform",M=M,n=20000,n_updates=120000,n_queries=1,delta=50,seed=7)
    upd=[o for o in ops if o[0]=="u"]; s=make(name,len(upd)); orc=Oracle()
    for i,v in init: s.insert(i,v); orc.upsert(i,v)
    for _,i,v in upd: s.update(i,v); orc.upsert(i,v)
    rng=random.Random(1); mism=0
    for _ in range(500):
        a=rng.randrange(M-5000); b=a+rng.choice([200,1000,5000])
        if s.range(a,b)!=orc.range(a,b): mism+=1
    return mism
rows=[]
for m in ["MARI","ART","PGM","Bx"]:
    r=json.loads(subprocess.run(["python3","run_method.py",m],capture_output=True,text=True).stdout.strip().splitlines()[-1])
    r["mismatches"]=exact(m); rows.append(r)
json.dump(rows,open("fair_results.json","w"),indent=2)
print(f"{'Method':<7}{'Peak RSS (MB)':>14}{'CPU s (U+S)':>13}{'user_s':>9}{'sys_s':>8}{'reloc/upd':>11}{'exact':>7}")
for r in rows:
    print(f"{r['method']:<7}{r['peak_rss_MB']:>14}{r['cpu_s']:>13}{r['user_s']:>9}{r['sys_s']:>8}{r['reloc_per_update']:>11}{'yes' if r['mismatches']==0 else 'NO':>7}")
