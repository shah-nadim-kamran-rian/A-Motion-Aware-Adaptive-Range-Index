# Empirical sanity check of Theorem 2: under MARI's ownership, the number of
# relocations equals the number of updates that move a key outside its current
# owner's guard interval -- i.e. exactly the forced-relocation set. We recompute
# the "forced" count independently of MARI's migration counter and compare.
import pandas as pd, numpy as np
from mari_v2 import MARILocal
df = pd.read_csv("data/all_stocks_5yr.csv", usecols=["date","close","Name"]).dropna()
df["date"]=pd.to_datetime(df["date"]); df["cents"]=(df["close"]*100).round().astype(int)
names=sorted(df["Name"].unique()); idof={n:k for k,n in enumerate(names)}
df["id"]=df["Name"].map(idof); df=df.sort_values(["date","id"])
stream=list(zip(df["id"].to_numpy(), df["cents"].to_numpy()))
MAXC=int(df["cents"].max()); M=MAXC+5000
for guard in (500, 1000):
    mari=MARILocal(M=M, width=1000, guard=guard, eps=0.5)
    forced=0; owner={}
    w,g=1000,guard
    inG=lambda b,k: b*w-g<=k<=(b+1)*w-1+g
    seen=set()
    for i,v in stream:
        if i in seen:
            b=owner[i]
            if not inG(b,v):           # Theorem 2: this update is FORCED to relocate
                forced+=1; owner[i]=min(v//w, M//w-1) if M%w==0 else min(v//w,(M+w-1)//w-1)
            mari.update(i,v)
        else:
            seen.add(i); owner[i]=min(v//w,(M+w-1)//w-1); mari.insert(i,v)
    print(f"guard={guard}: MARI migrations={mari.migrations:,}  independently-counted forced relocations={forced:,}  match={mari.migrations==forced}")
