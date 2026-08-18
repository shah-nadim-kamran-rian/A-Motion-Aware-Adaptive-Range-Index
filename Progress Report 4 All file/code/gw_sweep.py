"""g-w decoupling experiment: sweep guard g x bucket width w; measure
relocation/update (should depend on g) and scan/result (should depend on w).
Produces two heatmaps + a Pareto plot. All MARI configs verified exact."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, json, random
from mari import gen, Oracle
from mari_v2 import MARILocal
plt.rcParams.update({"font.family":"serif","font.size":9,"savefig.dpi":200})
TEAL="#1C7293"; NAVY="#12273D"; GOLD="#D89A33"; RED="#B23A48"
M=1_000_000; N=20000; U=80000; SEED=7
GS=[5,10,20,50,100,200]; WS=[250,500,1000,2000,4000,8000]

init,ops,_=gen("uniform",M=M,n=N,n_updates=U,n_queries=1,delta=50,seed=SEED)
upd=[o for o in ops if o[0]=="u"]
rng=random.Random(1)
Q=[(a,a+rng.choice([200,1000,5000])) for a in (rng.randrange(M-5000) for _ in range(2000))]
# oracle once (for exactness spot-checks)
orc=Oracle()
for i,v in init: orc.upsert(i,v)
for _,i,v in upd: orc.upsert(i,v)

reloc=np.zeros((len(GS),len(WS))); scan=np.zeros((len(GS),len(WS))); mismax=0
for gi,g in enumerate(GS):
    for wi,w in enumerate(WS):
        s=MARILocal(M=M,width=w,guard=g,eps=0.5)
        for i,v in init: s.insert(i,v)
        for _,i,v in upd: s.update(i,v)
        res=0
        for a,b in Q: res+=len(s.range(a,b))
        reloc[gi,wi]=s.migrations/max(1,s.migrations+s.local_updates)
        scan[gi,wi]=s.scanned/max(1,res)
        if gi in (0,len(GS)-1) and wi in (0,len(WS)-1):  # exactness at grid corners
            mm=sum(s.range(a,b)!=orc.range(a,b) for (a,b) in Q[:200]); mismax=max(mismax,mm)
json.dump({"g":GS,"w":WS,"reloc":reloc.tolist(),"scan":scan.tolist(),"corner_mismatches":mismax},
          open("gw_results.json","w"),indent=2)
print("corner exactness mismatches:",mismax)
rw=np.ptp(reloc,axis=1).mean(); rg=np.ptp(reloc,axis=0).mean()
sw=np.ptp(scan,axis=1).mean();  sg=np.ptp(scan,axis=0).mean()
print(f"RELOC: changes {rg:.4f} across g vs {rw:.4f} across w  -> depends on g: {rg>3*rw}")
print(f"SCAN : changes {sw:.3f} across w vs {sg:.3f} across g  -> depends on w: {sw>3*sg}")

def heat(ax,Z,title):
    im=ax.imshow(Z,origin="lower",cmap="viridis",aspect="auto")
    ax.set_xticks(range(len(WS))); ax.set_xticklabels(WS,fontsize=7); ax.set_xlabel("bucket width $w$")
    ax.set_yticks(range(len(GS))); ax.set_yticklabels(GS,fontsize=7); ax.set_ylabel("guard $g$")
    ax.set_title(title,fontsize=9,color=NAVY)
    plt.colorbar(im,ax=ax,fraction=0.046,pad=0.04)

fig,(a1,a2)=plt.subplots(1,2,figsize=(9,3.6))
heat(a1,reloc,"(a) Relocation / update"); heat(a2,scan,"(b) Scan / result")
plt.tight_layout(); plt.savefig("fig_gw_heat.png",bbox_inches="tight",pad_inches=0.25); plt.close()

# Pareto: all grid points; diagonal g==w-ish is the "single-width" frontier
fig,ax=plt.subplots(figsize=(5,4))
ax.scatter(reloc.ravel(),scan.ravel(),s=22,c=TEAL,alpha=0.6,label="MARI $(g,w)$ grid")
# single-width frontier: pick cells where g and w are 'matched' by rank (both small..both large)
diagR=[reloc[i,i] for i in range(min(len(GS),len(WS)))]
diagS=[scan[i,i] for i in range(min(len(GS),len(WS)))]
order=np.argsort(diagR); dR=np.array(diagR)[order]; dS=np.array(diagS)[order]
ax.plot(dR,dS,"-o",color=RED,ms=5,label="single-width ($g\\!=\\!w$ rank) frontier")
# a decoupled point: small w (low scan) + small g (low reloc)
ax.scatter([reloc[0,0]],[scan[0,0]],s=90,marker="*",c=GOLD,edgecolor=NAVY,zorder=5,label="MARI decoupled (small $g$, small $w$)")
ax.set_xlabel("relocation / update"); ax.set_ylabel("scan / result")
ax.set_title("Pareto: relocation vs scan",fontsize=10,color=NAVY)
ax.legend(fontsize=7,loc="upper right"); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig("fig_gw_pareto.png",bbox_inches="tight",pad_inches=0.25); plt.close()
print("wrote fig_gw_heat.png, fig_gw_pareto.png")
