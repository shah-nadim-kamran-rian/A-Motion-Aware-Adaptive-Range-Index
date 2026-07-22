
import bisect
INF = float("inf")

class _B:
    __slots__ = ("id","lo","hi","smap","skeys","dmap","dkeys","dtomb","size")
    def __init__(self, bid, lo, hi):
        self.id=bid; self.lo=lo; self.hi=hi
        self.smap={}; self.skeys=[]; self.dmap={}; self.dkeys=[]; self.dtomb=set(); self.size=0

class MARIAdaptive:
    def __init__(self, M=1_000_000, tau=20, guard=50, eps=0.5, **_):
        self.M=M; self.tau=tau; self.g=guard; self.eps=eps
        self._next=0
        self.buckets={}
        self.los=[]; self.bid=[]                 # parallel sorted arrays: lo -> bucket id
        b=self._new(0, M)
        self.los=[0]; self.bid=[b.id]
        self.T={}
        self.migrations=0; self.local_updates=0; self.compactions=0
        self.splits=0; self.merges=0; self.sm_work=0
        self.scanned=0; self.verifies=0; self.max_bucket=0; self.name=f"MARIAdaptive(tau={tau},g={guard})"

    def _new(self, lo, hi):
        b=_B(self._next, lo, hi); self.buckets[b.id]=b; self._next+=1; return b

    def _pos(self, k):
        i=bisect.bisect_right(self.los, k)-1
        return i if i>=0 else 0
    def _core(self, k): return self.buckets[self.bid[self._pos(k)]]
    def _in_guard(self, B, k): return B.lo - self.g <= k <= B.hi - 1 + self.g

    def _put(self, B, i, v):
        B.dmap[i]=v; bisect.insort(B.dkeys,(v,i)); B.dtomb.discard(i)
        if len(B.dkeys) >= max(1, int(self.eps*max(1,len(B.smap)))): self._compact(B)
    def _rm(self, B, i): B.dtomb.add(i); B.dmap.pop(i,None)
    def _compact(self, B):
        st=B.smap
        for i,v in B.dmap.items(): st[i]=v
        for i in B.dtomb: st.pop(i,None)
        B.dmap.clear(); B.dkeys.clear(); B.dtomb.clear()
        B.skeys=sorted((k,i) for i,k in st.items()); self.compactions+=1

    # ---- structural maintenance ----
    def _live_items(self, B):
        self._compact(B); return B.smap            # id->key, current

    def _split(self, B):
        items=sorted((k,i) for i,k in self._live_items(B).items())
        n=len(items); 
        if n<2: return
        mu=items[n//2][0]
        if not (B.lo < mu < B.hi): return          # degenerate hotspot: cannot split by key
        L=self._new(B.lo, mu); R=self._new(mu, B.hi)
        for k,i in items:
            dst = L if k < mu else R
            dst.smap[i]=k; self.T[i]=(k, dst.id)
        L.skeys=sorted((k,i) for i,k in L.smap.items()); L.size=len(L.smap)
        R.skeys=sorted((k,i) for i,k in R.smap.items()); R.size=len(R.smap)
        # splice into arrays: replace B.lo slot with L, insert R at mu
        p=self._pos(B.lo); self.bid[p]=L.id
        ip=bisect.bisect_right(self.los, mu)
        self.los.insert(ip, mu); self.bid.insert(ip, R.id)
        del self.buckets[B.id]
        self.sm_work += n; self.splits += 1
        if L.size>2*self.tau: self._split(L)
        if R.size>2*self.tau: self._split(R)

    def _merge_at(self, p):
        # merge bucket at position p with its right neighbor p+1
        Lid=self.bid[p]; Rid=self.bid[p+1]; L=self.buckets[Lid]; R=self.buckets[Rid]
        self._live_items(L); self._live_items(R)
        m=self._new(L.lo, R.hi)
        for src in (L,R):
            for i,k in src.smap.items(): m.smap[i]=k; self.T[i]=(k,m.id)
        m.skeys=sorted((k,i) for i,k in m.smap.items()); m.size=len(m.smap)
        self.bid[p]=m.id
        del self.los[p+1]; del self.bid[p+1]
        del self.buckets[Lid]; del self.buckets[Rid]
        self.sm_work += m.size; self.merges += 1

    def _maybe_merge(self, p):
        # check (p-1,p) and (p,p+1)
        for q in (p-1, p):
            if 0 <= q and q+1 < len(self.bid):
                a=self.buckets[self.bid[q]]; b=self.buckets[self.bid[q+1]]
                if a.size + b.size < self.tau:
                    self._merge_at(q); return

    # ---- public ops ----
    def insert(self, i, v):
        B=self._core(v); self.T[i]=(v,B.id); self._put(B,i,v); B.size+=1
        if B.size>self.max_bucket: self.max_bucket=B.size
        if B.size>2*self.tau: self._split(B)
    def update(self, i, v):
        cur=self.T.get(i)
        if cur is None: return self.insert(i,v)
        ok,bsrc=cur
        if ok==v: return
        B=self.buckets.get(bsrc)
        if B is None:  # owner merged/split away; re-route by key (rare safety net)
            B=self._core(ok)
        if self._in_guard(B, v):
            self.T[i]=(v,B.id); self._put(B,i,v); self.local_updates+=1
            if B.size>self.max_bucket: self.max_bucket=B.size
        else:
            self._rm(B,i); B.size-=1
            Bd=self._core(v); self._put(Bd,i,v); Bd.size+=1; self.T[i]=(v,Bd.id); self.migrations+=1
            if Bd.size>2*self.tau: self._split(Bd)
            self._maybe_merge(self._pos(B.lo))
    def delete(self, i):
        cur=self.T.pop(i,None)
        if cur is None: return
        B=self.buckets.get(cur[1])
        if B: self._rm(B,i); B.size-=1; self._maybe_merge(self._pos(B.lo))

    def range(self, a, b):
        out=set(); g=self.g
        i0=self._pos(a-g); i1=self._pos(b+g)
        for p in range(i0, i1+1):
            B=self.buckets[self.bid[p]]
            if not (B.lo - g <= b and B.hi - 1 + g >= a): continue
            cand=set()
            for arr in (B.skeys, B.dkeys):
                lo=bisect.bisect_left(arr,(a,-1)); hi=bisect.bisect_right(arr,(b,INF))
                self.scanned += hi-lo
                for _,i in arr[lo:hi]: cand.add(i)
            for i in cand:
                self.verifies+=1; tk,tb=self.T.get(i,(None,None))
                if tb==B.id and tk is not None and a<=tk<=b: out.add(i)
        return out

    def nbuckets(self): return len(self.bid)
