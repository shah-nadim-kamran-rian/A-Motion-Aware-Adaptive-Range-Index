"""Fair single-method runner: builds one index, applies the SAME workload, runs
queries, and reports peak memory (RSS = GNU time %M) and CPU time (user+sys =
%U+%S). One method per process so memory is isolated. No oracle in the timed
path (exactness is checked separately)."""
import sys, json, random, resource
from mari import gen
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact
M=1_000_000; SEED=7; N=20000; U=120000
def make(name,u):
    if name=="MARI":    return MARILocal(M=M,width=1000,guard=50,eps=0.5)
    if name=="ART":     return ART()
    if name=="PGM":     return PGMIndex(eps=16,buffer=2048)
    if name=="Bx":      return BxExact(n_part=4,period=max(1,u//3))
    raise SystemExit("unknown method "+name)
def reloc(s,name,u):
    return s.migrations/max(1,s.migrations+s.local_updates) if name=="MARI" else s.relocations/max(1,u)
name=sys.argv[1]
init,ops,_=gen("uniform",M=M,n=N,n_updates=U,n_queries=1,delta=50,seed=SEED)
upd=[o for o in ops if o[0]=="u"]
s=make(name,len(upd))
for i,v in init: s.insert(i,v)
for _,i,v in upd: s.update(i,v)
rng=random.Random(1)
Q=[(a,a+rng.choice([200,1000,5000])) for a in (rng.randrange(M-5000) for _ in range(2000))]
res=0
for a,b in Q: res+=len(s.range(a,b))
ru=resource.getrusage(resource.RUSAGE_SELF)
print(json.dumps({"method":name,"peak_rss_MB":round(ru.ru_maxrss/1024,1),
  "user_s":round(ru.ru_utime,3),"sys_s":round(ru.ru_stime,3),
  "cpu_s":round(ru.ru_utime+ru.ru_stime,3),"reloc_per_update":round(reloc(s,name,len(upd)),4)}))
