"""
MARI v2: per-bucket REAL local range indexes (sorted stable + sorted delta,
binary-search queries, merge compaction), benchmarked against four baselines:
  (1) OrderedList   - pure-Python bisect-on-list sorted index (delete+insert)
  (2) SortedListIdx - sortedcontainers.SortedList (delete+insert)
  (3) LSMIndex      - tiered buffer + sorted runs, verify-against-authoritative
  (4) RadixSorted   - radix-partitioned sorted leaves (a 'radix baseline';
                      NOT the C++ ART of Leis et al., which needs a native impl)

Update phase and query phase are timed SEPARATELY so the write/read crossover
is visible. All structures are exact and are checked against a brute-force
oracle. All are Python, so absolute throughput is not a cross-system claim;
the RELATIVE comparison within one runtime is what speaks to algorithmic cost.
"""

import bisect, random, time, json
from sortedcontainers import SortedList
from mari import gen, Oracle, clamp   # reuse generators + oracle

INF = float("inf")
TOMB = object()

# ==========================================================================
# Baseline 1: pure-Python sorted list (bisect on a Python list)
# ==========================================================================
class OrderedList:
    name = "OrderedList(bisect)"
    def __init__(self, **_):
        self.keys = []; self.cur = {}
        self.relocations = 0; self.scanned = 0
    def insert(self, i, v):
        self.cur[i] = v; bisect.insort(self.keys, (v, i))
    def update(self, i, v):
        old = self.cur.get(i)
        if old is None: return self.insert(i, v)
        if old == v: return
        j = bisect.bisect_left(self.keys, (old, i))
        if j < len(self.keys) and self.keys[j] == (old, i): self.keys.pop(j)
        bisect.insort(self.keys, (v, i)); self.cur[i] = v; self.relocations += 1
    def delete(self, i):
        old = self.cur.pop(i, None)
        if old is not None:
            j = bisect.bisect_left(self.keys, (old, i))
            if j < len(self.keys) and self.keys[j] == (old, i): self.keys.pop(j)
    def range(self, a, b):
        lo = bisect.bisect_left(self.keys, (a, -1)); out = set(); j = lo
        while j < len(self.keys) and self.keys[j][0] <= b:
            self.scanned += 1; out.add(self.keys[j][1]); j += 1
        return out

# ==========================================================================
# Baseline 2: sortedcontainers.SortedList (delete-then-insert)
# ==========================================================================
class SortedListIdx:
    name = "SortedListIdx(sortedcontainers)"
    def __init__(self, **_):
        self.sl = SortedList(); self.cur = {}
        self.relocations = 0; self.scanned = 0
    def insert(self, i, v): self.cur[i] = v; self.sl.add((v, i))
    def update(self, i, v):
        old = self.cur.get(i)
        if old is None: return self.insert(i, v)
        if old == v: return
        self.sl.remove((old, i)); self.sl.add((v, i)); self.cur[i] = v
        self.relocations += 1
    def delete(self, i):
        old = self.cur.pop(i, None)
        if old is not None: self.sl.remove((old, i))
    def range(self, a, b):
        lo = self.sl.bisect_left((a, -1)); hi = self.sl.bisect_right((b, INF))
        self.scanned += hi - lo
        return {i for _, i in self.sl[lo:hi]}

# ==========================================================================
# Baseline 3: tiered LSM (buffer + immutable sorted runs), exact via authoritative
# ==========================================================================
class LSMIndex:
    name = "LSMIndex(tiered)"
    def __init__(self, flush=4096, max_runs=4, **_):
        self.mem = SortedList(); self.runs = []; self.cur = {}
        self.F = flush; self.R = max_runs
        self.relocations = 0; self.scanned = 0; self.merges = 0
    def insert(self, i, v):
        self.cur[i] = v; self.mem.add((v, i))
        if len(self.mem) >= self.F: self._flush()
    def update(self, i, v):
        old = self.cur.get(i)
        if old == v: return
        self.cur[i] = v; self.mem.add((v, i))     # append-only; stale stays till merge
        if old is not None: self.relocations += 0  # no in-place relocation (LSM strength)
        if len(self.mem) >= self.F: self._flush()
    def delete(self, i): self.cur.pop(i, None)
    def _flush(self):
        self.runs.append(self.mem); self.mem = SortedList()
        if len(self.runs) > self.R: self._merge()
    def _merge(self):
        merged = SortedList()
        seen = set()
        # newest first so latest version wins; keep only entries matching cur
        for run in [self.mem] + list(reversed(self.runs)):
            for k, i in run:
                if i in seen: continue
                if self.cur.get(i) == k:
                    merged.add((k, i)); seen.add(i)
        self.runs = [merged]; self.mem = SortedList(); self.merges += 1
    def range(self, a, b):
        cand = set()
        for run in [self.mem] + self.runs:
            lo = run.bisect_left((a, -1)); hi = run.bisect_right((b, INF))
            self.scanned += hi - lo
            for _, i in run[lo:hi]: cand.add(i)
        out = set()
        for i in cand:
            k = self.cur.get(i)
            if k is not None and a <= k <= b: out.add(i)
        return out

# ==========================================================================
# Baseline 4: radix-partitioned sorted leaves (a 'radix baseline')
# ==========================================================================
class RadixSorted:
    name = "RadixSorted(partitioned)"
    def __init__(self, M=1_000_000, fanout=1000, **_):
        self.w = (M + fanout - 1) // fanout; self.nb = fanout
        self.leaf = [[] for _ in range(self.nb)]   # each: sorted [(key,id)]
        self.cur = {}; self.relocations = 0; self.scanned = 0
    def _b(self, k): return min(k // self.w, self.nb - 1)
    def insert(self, i, v):
        self.cur[i] = v; bisect.insort(self.leaf[self._b(v)], (v, i))
    def update(self, i, v):
        old = self.cur.get(i)
        if old is None: return self.insert(i, v)
        if old == v: return
        b0 = self._b(old); L = self.leaf[b0]
        j = bisect.bisect_left(L, (old, i))
        if j < len(L) and L[j] == (old, i): L.pop(j)
        bisect.insort(self.leaf[self._b(v)], (v, i)); self.cur[i] = v
        self.relocations += 1                       # every key change relocates a leaf entry
    def delete(self, i):
        old = self.cur.pop(i, None)
        if old is None: return
        L = self.leaf[self._b(old)]; j = bisect.bisect_left(L, (old, i))
        if j < len(L) and L[j] == (old, i): L.pop(j)
    def range(self, a, b):
        out = set()
        for bb in range(self._b(a), self._b(b) + 1):
            L = self.leaf[bb]
            lo = bisect.bisect_left(L, (a, -1)); hi = bisect.bisect_right(L, (b, INF))
            self.scanned += hi - lo
            for _, i in L[lo:hi]: out.add(i)
        return out

# ==========================================================================
# MARI v2: guarded buckets with REAL local sorted indexes + delta + compaction
# ==========================================================================
class MARILocal:
    def __init__(self, M=1_000_000, width=1000, guard=50, eps=0.5, **_):
        self.M = M; self.w = width; self.g = guard; self.m = (M + width - 1)//width
        self.eps = eps
        self.smap = [dict() for _ in range(self.m)]   # stable: id->key (compacted)
        self.skeys = [[] for _ in range(self.m)]      # stable sorted [(key,id)]
        self.dmap = [dict() for _ in range(self.m)]   # delta: id->latest pending key
        self.dkeys = [[] for _ in range(self.m)]      # delta sorted [(key,id)] (may hold stale)
        self.dtomb = [set() for _ in range(self.m)]   # pending removals
        self.T = {}                                   # id -> (key, bucket) AUTHORITATIVE
        self.migrations = 0; self.local_updates = 0
        self.compactions = 0; self.scanned = 0; self.verifies = 0
        self.max_delta = 0
        self.name = f"MARI(w={width},g={guard})"

    def _core(self, k): return min(k // self.w, self.m - 1)
    def _in_guard(self, b, k):
        return b*self.w - self.g <= k <= (b+1)*self.w - 1 + self.g

    def _put(self, b, i, v):
        self.dmap[b][i] = v
        bisect.insort(self.dkeys[b], (v, i))
        self.dtomb[b].discard(i)
        dl = len(self.dkeys[b])
        if dl > self.max_delta: self.max_delta = dl
        if dl >= max(1, int(self.eps * max(1, len(self.smap[b])))):
            self._compact(b)

    def _rm(self, b, i):
        self.dtomb[b].add(i); self.dmap[b].pop(i, None)

    def _compact(self, b):
        st = self.smap[b]
        for i, v in self.dmap[b].items(): st[i] = v
        for i in self.dtomb[b]: st.pop(i, None)
        self.dmap[b].clear(); self.dkeys[b].clear(); self.dtomb[b].clear()
        self.skeys[b] = sorted((k, i) for i, k in st.items())
        self.compactions += 1

    def insert(self, i, v):
        b = self._core(v); self.T[i] = (v, b); self._put(b, i, v)
    def update(self, i, v):
        cur = self.T.get(i)
        if cur is None: return self.insert(i, v)
        ok, bsrc = cur
        if ok == v: return
        if self._in_guard(bsrc, v):
            self.T[i] = (v, bsrc); self._put(bsrc, i, v); self.local_updates += 1
        else:
            bdst = self._core(v); self._rm(bsrc, i); self._put(bdst, i, v)
            self.T[i] = (v, bdst); self.migrations += 1
    def delete(self, i):
        cur = self.T.pop(i, None)
        if cur is None: return
        self._rm(cur[1], i)

    def _buckets(self, a, b):
        lo = max(0, (a - self.g)//self.w - 1); hi = min(self.m-1, (b + self.g)//self.w + 1)
        for j in range(lo, hi+1):
            if (j+1)*self.w - 1 + self.g >= a and j*self.w - self.g <= b:
                yield j

    def range(self, a, b):
        out = set()
        for j in self._buckets(a, b):
            cand = set()
            S = self.skeys[j]
            lo = bisect.bisect_left(S, (a, -1)); hi = bisect.bisect_right(S, (b, INF))
            self.scanned += hi - lo
            for _, i in S[lo:hi]: cand.add(i)
            D = self.dkeys[j]
            lo = bisect.bisect_left(D, (a, -1)); hi = bisect.bisect_right(D, (b, INF))
            self.scanned += hi - lo
            for _, i in D[lo:hi]: cand.add(i)
            for i in cand:
                self.verifies += 1
                tk, tb = self.T.get(i, (None, None))
                if tb == j and tk is not None and a <= tk <= b: out.add(i)
        return out

# ==========================================================================
# Efficiency harness: time update phase and query phase separately
# ==========================================================================
def bench(struct, init, updates, queries, oracle=None, check=False):
    for i, v in init: struct.insert(i, v)
    if oracle:
        for i, v in init: oracle.upsert(i, v)
    t0 = time.perf_counter()
    for _, i, v in updates:
        struct.update(i, v)
        if oracle: oracle.upsert(i, v)
    t_upd = time.perf_counter() - t0
    t1 = time.perf_counter(); mism = 0; nres = 0
    for _, a, b in queries:
        r = struct.range(a, b); nres += len(r)
        if check and oracle and r != oracle.range(a, b): mism += 1
    t_qry = time.perf_counter() - t1
    return {"upd_s": round(t_upd, 3), "qry_s": round(t_qry, 3),
            "upd_ops_s": round(len(updates)/t_upd), "qry_ops_s": round(len(queries)/t_qry),
            "results": nres, "mismatches": mism,
            "scanned_per_result": round(struct.scanned/nres, 2) if nres else None,
            "relocations": getattr(struct, "relocations", None),
            "migrations": getattr(struct, "migrations", None)}

def split_ops(ops):
    return [o for o in ops if o[0]=="u"], [o for o in ops if o[0]=="q"]

def main():
    M, n, U, delta, width = 1_000_000, 20_000, 200_000, 50, 1_000
    out = {"config": {"M":M,"n":n,"updates":U,"drift_delta":delta,"bucket_width":width}, "runs": {}}
    for reg, qw, qlabel in [("uniform", 5000, "wide"), ("uniform", 200, "narrow")]:
        init, ops, audit = gen(reg, M=M, n=n, n_updates=U, n_queries=2000,
                               delta=delta, qwidth=qw, seed=7)
        upds, qrys = split_ops(ops)
        key = f"{reg}_{qlabel}q"
        out["runs"][key] = {"drift_audit": audit, "queries": len(qrys), "structs": {}}
        builders = [
            ("MARI",         lambda: MARILocal(M=M, width=width, guard=delta, eps=0.5)),
            ("OrderedList",  lambda: OrderedList()),
            ("SortedList",   lambda: SortedListIdx()),
            ("LSM",          lambda: LSMIndex()),
            ("RadixSorted",  lambda: RadixSorted(M=M, fanout=width)),
        ]
        for nm, mk in builders:
            s = mk(); orc = Oracle()
            r = bench(s, init, upds, qrys, oracle=orc, check=True)
            out["runs"][key]["structs"][nm] = r
            print(f"[{key:16s}] {nm:12s} upd={r['upd_ops_s']:>9,}/s qry={r['qry_ops_s']:>8,}/s "
                  f"scan/res={r['scanned_per_result']} reloc={r['relocations']} mig={r['migrations']} "
                  f"mism={r['mismatches']}")
        print()
    # ---- R5: update-throughput vs bucket width (cost decoupling) ----
    init, ops, _ = gen("uniform", M=M, n=n, n_updates=U, n_queries=1000,
                       delta=delta, qwidth=5000, seed=7)
    upds, qrys = split_ops(ops)
    out["width_sweep"] = {}
    for w in [1000, 5000, 20000, 50000, 100000]:
        rM = bench(MARILocal(M=M, width=w, guard=delta, eps=0.5), init, upds, qrys)
        rR = bench(RadixSorted(M=M, fanout=M // w), init, upds, qrys)
        out["width_sweep"][w] = {"MARI_upd_ops_s": rM["upd_ops_s"],
                                 "Radix_upd_ops_s": rR["upd_ops_s"],
                                 "entries_per_bucket_approx": n // (M // w)}
        print(f"[width {w:>6}] MARI={rM['upd_ops_s']:>9,}/s  Radix={rR['upd_ops_s']:>9,}/s")

    with open("mari_efficiency.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote mari_efficiency.json")

if __name__ == "__main__":
    main()
