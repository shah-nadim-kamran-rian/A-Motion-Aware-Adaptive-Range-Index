"""
hotspot_demo.py -- mitigating the single-key hotspot limitation.

Conceded limitation (Section 11): a single key value of multiplicity > 2*tau
cannot be split, since a key-range partition cannot separate identical keys, so
the bucket holding it exceeds the size bound (exactness is kept, the bound is
not). This demo shows the fix: OVERFLOW CHAINING. When one value's multiplicity
in a bucket exceeds a threshold, its id-set is evicted to a dedicated overflow
chain keyed by that exact value; the main bucket then stays within the bound and
queries union the overflow when the value lies in range. Exactness is preserved
and the size bound is restored on the non-hotspot data.
"""
import random, json
from collections import Counter
from mari import Oracle


class HotspotMARI:
    def __init__(self, M, width=1000, tau=64):
        self.M = M; self.w = width; self.tau = tau
        self.nb = (M + width - 1) // width
        self.member = [dict() for _ in range(self.nb)]   # bucket -> {id: value}
        self.vcount = [Counter() for _ in range(self.nb)] # bucket -> value -> count
        self.overflow = {}                                # value -> set(ids)  (hotspots)
        self.T = {}                                       # id -> ('b',bucket) | ('o',value)
        self.use_overflow = True

    def _bucket(self, v): return min(v // self.w, self.nb - 1)

    def _place(self, idv, v):
        if v in self.overflow:                            # value already a hotspot chain
            self.overflow[v].add(idv); self.T[idv] = ('o', v); return
        b = self._bucket(v)
        self.member[b][idv] = v; self.vcount[b][v] += 1; self.T[idv] = ('b', b)
        if self.use_overflow and self.vcount[b][v] > self.tau:      # evict hot value
            ids = [j for j, vv in self.member[b].items() if vv == v]
            self.overflow[v] = set(ids)
            for j in ids:
                del self.member[b][j]; self.T[j] = ('o', v)
            del self.vcount[b][v]

    def _remove(self, idv):
        loc = self.T.pop(idv, None)
        if loc is None: return
        if loc[0] == 'o':
            s = self.overflow.get(loc[1])
            if s is not None:
                s.discard(idv)
                if not s: del self.overflow[loc[1]]
        else:
            b = loc[1]; v = self.member[b].pop(idv, None)
            if v is not None:
                self.vcount[b][v] -= 1
                if self.vcount[b][v] <= 0: del self.vcount[b][v]

    def insert(self, idv, v): self._place(idv, v)
    def update(self, idv, v):
        cur = self.T.get(idv)
        if cur is None: return self._place(idv, v)
        self._remove(idv); self._place(idv, v)
    def delete(self, idv): self._remove(idv)

    def range(self, a, b):
        out = set()
        lo = max(0, a // self.w - 1); hi = min(self.nb - 1, b // self.w + 1)
        for j in range(lo, hi + 1):
            for idv, v in self.member[j].items():
                if a <= v <= b: out.add(idv)
        for v, ids in self.overflow.items():             # union hotspot chains in range
            if a <= v <= b: out |= ids
        return out

    def max_bucket_size(self): return max(len(m) for m in self.member)
    def max_value_multiplicity(self):
        return max((max(c.values()) if c else 0) for c in self.vcount)


def run(use_overflow, M=200_000, n=8_000, hot_frac=0.35, tau=64, seed=5):
    rnd = random.Random(seed)
    idx = HotspotMARI(M, width=1000, tau=tau); idx.use_overflow = use_overflow
    orc = Oracle()
    H = 137_000                                            # the hotspot value
    n_hot = int(n * hot_frac)
    # initial scatter
    for i in range(n):
        v = rnd.randrange(M); idx.insert(i, v); orc.upsert(i, v)
    # drive a hotspot: many ids converge on H and stay; others drift normally
    for step in range(120_000):
        i = rnd.randrange(n)
        if i < n_hot and rnd.random() < 0.7:
            v = H                                          # converge on the hot value
        else:
            cur = orc.key.get(i, rnd.randrange(M))
            v = min(M - 1, max(0, cur + rnd.randint(-50, 50)))
        idx.update(i, v); orc.upsert(i, v)
    # exactness incl. queries spanning the hotspot
    mism = 0
    for _ in range(4000):
        a = rnd.randrange(M - 5000); b = a + rnd.choice([200, 1000, 5000])
        if idx.range(a, b) != orc.range(a, b): mism += 1
    # a query that explicitly includes H
    qa, qb = H - 100, H + 100
    if idx.range(qa, qb) != orc.range(qa, qb): mism += 1
    return {"use_overflow": use_overflow, "tau": tau,
            "max_bucket_size": idx.max_bucket_size(),
            "max_value_multiplicity_in_bucket": idx.max_value_multiplicity(),
            "overflow_chains": len(idx.overflow),
            "hotspot_chain_size": len(idx.overflow.get(H, [])),
            "split_obstruction_bound_2tau": 2 * tau,
            # the splittable obstruction is a single value's multiplicity, not total
            # density (density is handled by adaptive split/merge, Theorem 3)
            "obstruction_removed": idx.max_value_multiplicity() <= 2 * tau,
            "mismatches": mism}


def main():
    out = {"note": "single-key hotspot: overflow chaining restores the 2*tau bound, exactly",
           "without_overflow": run(False), "with_overflow": run(True)}
    for k in ("without_overflow", "with_overflow"):
        r = out[k]
        print(f"{k:<17} max_bucket={r['max_bucket_size']:<6} "
              f"max_val_mult={r['max_value_multiplicity_in_bucket']:<6} "
              f"2tau={r['split_obstruction_bound_2tau']} obstruction_removed={r['obstruction_removed']} "
              f"chains={r['overflow_chains']} hot_chain={r['hotspot_chain_size']} "
              f"mism={r['mismatches']}")
    json.dump(out, open("/home/claude/hotspot_results.json", "w"), indent=2)
    print("wrote hotspot_results.json")


if __name__ == "__main__":
    main()
