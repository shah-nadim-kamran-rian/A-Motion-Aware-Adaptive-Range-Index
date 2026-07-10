"""
MARI reference implementation + baselines + workload generators + benchmark.

PURPOSE: validate the *mechanism* (exactness, migration reduction, the
guard-vs-amplification trade-off, delta boundedness) with implementation-
INDEPENDENT metrics. This is a correctness/algorithmic-behaviour harness in
Python, NOT a systems-grade throughput study. Wall-clock numbers are reported
only as same-environment relative figures and must not be read as evidence
against a production B+-tree.
"""

import bisect, random, json, time
from collections import defaultdict

TOMB = object()  # tombstone marker

# --------------------------------------------------------------------------
# Ground truth (brute-force oracle for exactness checking)
# --------------------------------------------------------------------------
class Oracle:
    def __init__(self):
        self.key = {}            # id -> current key
    def upsert(self, i, v): self.key[i] = v
    def delete(self, i): self.key.pop(i, None)
    def range(self, a, b):
        return {i for i, k in self.key.items() if a <= k <= b}

# --------------------------------------------------------------------------
# Baseline 1: ordered index (B+-tree family stand-in).
# Update = delete-then-insert => one relocation per key change (by construction).
# Range query walks exactly the queried interval => amplification ~ 1.
# --------------------------------------------------------------------------
class OrderedIndex:
    name = "OrderedIndex (delete-then-insert)"
    def __init__(self):
        self.keys = []           # sorted list of (key, id)
        self.cur = {}            # id -> key
        self.relocations = 0
        self.candidates = 0
    def _ins(self, k, i): self.keys.insert(bisect.bisect_left(self.keys, (k, i)), (k, i))
    def _rem(self, k, i):
        j = bisect.bisect_left(self.keys, (k, i))
        if j < len(self.keys) and self.keys[j] == (k, i): self.keys.pop(j)
    def insert(self, i, v): self.cur[i] = v; self._ins(v, i)
    def update(self, i, v):
        old = self.cur.get(i)
        if old is None: return self.insert(i, v)
        if old != v:
            self._rem(old, i); self._ins(v, i); self.cur[i] = v
            self.relocations += 1
    def delete(self, i):
        old = self.cur.pop(i, None)
        if old is not None: self._rem(old, i)
    def range(self, a, b):
        lo = bisect.bisect_left(self.keys, (a, -1))
        out = set()
        j = lo
        while j < len(self.keys) and self.keys[j][0] <= b:
            self.candidates += 1
            out.add(self.keys[j][1]); j += 1
        return out

# --------------------------------------------------------------------------
# MARI: guarded bucket ownership + identifier table + stable/delta + compaction
# --------------------------------------------------------------------------
class MARI:
    def __init__(self, M, width, guard, compact_threshold=64, policy="fixed", eps=0.5):
        self.M = M
        self.w = width
        self.g = guard
        self.m = (M + width - 1) // width
        self.tau = compact_threshold
        self.policy = policy        # "fixed" (|D|>=tau) or "ratio" (|D|>=eps*|S|)
        self.eps = eps
        self.stable = [dict() for _ in range(self.m)]   # bucket -> {id: key}
        self.delta  = [[] for _ in range(self.m)]       # bucket -> [(id, key|TOMB)]
        self.T = {}                                     # id -> (key, bucket)  AUTHORITATIVE
        # instrumentation
        self.migrations = 0
        self.local_updates = 0
        self.compactions = 0
        self.compaction_work = 0   # sum of (|S|+|D|) merged, the amortized quantity
        self.max_delta = 0
        self.candidates = 0       # ids T-verified during queries
        self.scanned_entries = 0  # entries examined during queries
        self.name = f"MARI(w={width},g={guard},{policy})"

    def _trigger(self, b):
        if self.policy == "ratio":
            import math
            return len(self.delta[b]) >= max(1, math.ceil(self.eps * max(1, len(self.stable[b]))))
        return len(self.delta[b]) >= self.tau

    def _core(self, key): return min(key // self.w, self.m - 1)
    def _in_guard(self, b, key):
        lo = b * self.w - self.g
        hi = (b + 1) * self.w - 1 + self.g
        return lo <= key <= hi

    def _append_delta(self, b, i, val):
        d = self.delta[b]; d.append((i, val))
        if len(d) > self.max_delta: self.max_delta = len(d)
        if self._trigger(b): self._compact(b)

    def _compact(self, b):
        st = self.stable[b]
        self.compaction_work += len(st) + len(self.delta[b])
        for i, val in self.delta[b]:
            if val is TOMB: st.pop(i, None)
            else: st[i] = val
        self.delta[b].clear()
        self.compactions += 1

    def insert(self, i, v):
        b = self._core(v)
        self.T[i] = (v, b)
        self._append_delta(b, i, v)

    def update(self, i, v):
        cur = self.T.get(i)
        if cur is None: return self.insert(i, v)
        ok, bsrc = cur
        if ok == v: return
        if self._in_guard(bsrc, v):              # stay -> local, no migration
            self.T[i] = (v, bsrc)
            self._append_delta(bsrc, i, v)
            self.local_updates += 1
        else:                                    # leave guard -> migrate
            bdst = self._core(v)
            self._append_delta(bsrc, i, TOMB)
            self._append_delta(bdst, i, v)
            self.T[i] = (v, bdst)
            self.migrations += 1

    def delete(self, i):
        cur = self.T.pop(i, None)
        if cur is None: return
        _, b = cur
        self._append_delta(b, i, TOMB)

    def _buckets_intersecting(self, a, b):
        lo = max(0, (a - self.g) // self.w - 1)
        hi = min(self.m - 1, (b + self.g) // self.w + 1)
        for j in range(lo, hi + 1):
            blo = j * self.w - self.g
            bhi = (j + 1) * self.w - 1 + self.g
            if bhi >= a and blo <= b:
                yield j

    def range(self, a, b):
        out = set()
        for j in self._buckets_intersecting(a, b):
            # merged latest view of this bucket (stable overridden by delta)
            view = dict(self.stable[j])
            for i, val in self.delta[j]:
                if val is TOMB: view.pop(i, None)
                else: view[i] = val
            for i, k in view.items():
                self.scanned_entries += 1
                if a <= k <= b:
                    self.candidates += 1
                    tk, tb = self.T.get(i, (None, None))   # authoritative verify
                    if tb == j and tk is not None and a <= tk <= b:
                        out.add(i)
        return out

# --------------------------------------------------------------------------
# Workload generators. Each returns (init_pairs, ops) where ops is a list of
# ("u", id, newkey) updates and ("q", a, b) queries interleaved. Bounded drift
# delta is enforced and reported so the assumption is auditable.
# --------------------------------------------------------------------------
def clamp(v, M): return max(0, min(M - 1, v))

def gen(regime, M=1_000_000, n=20_000, n_updates=200_000, n_queries=2_000,
        delta=50, qwidth=5_000, seed=0):
    rnd = random.Random(seed)
    key = [rnd.randrange(M) for _ in range(n)]
    init = [(i, key[i]) for i in range(n)]
    ops = []
    realized = []                      # observed |dv| to audit bounded drift
    q_every = max(1, n_updates // n_queries)

    # cluster setup
    ncl = 20
    centers = [rnd.randrange(M) for _ in range(ncl)]
    cl_of = [rnd.randrange(ncl) for _ in range(n)]
    # adversarial: pick keys near a boundary
    boundary = (M // 2 // 1000) * 1000  # a bucket boundary
    adv_ids = list(range(min(2000, n)))
    for a in adv_ids: key[a] = boundary + rnd.choice([-1, 1])

    for step in range(n_updates):
        i = rnd.randrange(n)
        old = key[i]
        if regime == "uniform":
            dv = rnd.randint(-delta, delta)
            nv = clamp(old + dv, M)
        elif regime == "clustered":
            c = centers[cl_of[i]] + rnd.randint(-delta, delta)   # center drifts a bit
            centers[cl_of[i]] = clamp(c, M)
            target = centers[cl_of[i]]
            step_to = max(-delta, min(delta, target - old))
            nv = clamp(old + step_to, M)
        elif regime == "directional":
            dv = rnd.randint(0, delta)                            # upward trend
            nv = old + dv
            if nv >= M: nv = clamp(2 * M - 2 - nv, M)             # reflect at top
        elif regime == "adversarial":
            if i < 2000:                                          # oscillate across boundary, |dv|<=delta
                nv = clamp(old + (delta if old < boundary else -delta), M)
            else:
                nv = clamp(old + rnd.randint(-delta, delta), M)
        else:
            nv = clamp(old + rnd.randint(-delta, delta), M)
        realized.append(abs(nv - old))
        key[i] = nv
        ops.append(("u", i, nv))
        if (step + 1) % q_every == 0:
            if regime == "adversarial" or regime == "hotspot":
                a = clamp(boundary - qwidth // 2, M)
            else:
                a = rnd.randrange(max(1, M - qwidth))
            ops.append(("q", a, a + qwidth))
    audit = {
        "delta_bound": delta,
        "max_observed_dv": max(realized) if realized else 0,
        "mean_observed_dv": round(sum(realized) / len(realized), 2) if realized else 0,
        "within_bound": (max(realized) if realized else 0) <= delta,
    }
    return init, ops, audit

# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def run_struct(struct, init, ops, oracle=None, check=False):
    for i, v in init: struct.insert(i, v)
    if oracle:
        for i, v in init: oracle.upsert(i, v)
    n_queries = 0; n_results = 0; mismatches = 0
    t0 = time.perf_counter()
    for op in ops:
        if op[0] == "u":
            _, i, v = op; struct.update(i, v)
            if oracle: oracle.upsert(i, v)
        else:
            _, a, b = op
            res = struct.range(a, b)
            n_queries += 1; n_results += len(res)
            if check and oracle:
                truth = oracle.range(a, b)
                if res != truth: mismatches += 1
    dt = time.perf_counter() - t0
    return {"queries": n_queries, "results": n_results, "mismatches": mismatches,
            "wall_s": round(dt, 3)}

def amplification(cand, results):
    return round(cand / results, 3) if results else float("nan")

# --------------------------------------------------------------------------
# Experiments
# --------------------------------------------------------------------------
def main():
    M, n, U, Q, delta = 1_000_000, 20_000, 200_000, 2_000, 50
    width = 1_000
    regimes = ["uniform", "clustered", "directional", "adversarial", "hotspot"]
    out = {"config": {"M": M, "n": n, "updates": U, "queries": Q,
                      "drift_delta": delta, "bucket_width": width}, "regimes": {}, "guard_sweep": {}}

    # ---- per-regime: MARI (g=delta) vs OrderedIndex, with exactness check ----
    for reg in regimes:
        init, ops, audit = gen(reg, M=M, n=n, n_updates=U, n_queries=Q, delta=delta, seed=1)
        # MARI with exactness verification against an oracle
        mari = MARI(M, width, guard=delta)
        orc = Oracle()
        rm = run_struct(mari, init, list(ops), oracle=orc, check=True)
        # Ordered baseline
        oi = OrderedIndex()
        ro = run_struct(oi, init, list(ops), oracle=None, check=False)
        upd_total = U
        out["regimes"][reg] = {
            "drift_audit": audit,
            "MARI": {
                "migration_rate": round(mari.migrations / upd_total, 4),
                "local_update_rate": round(mari.local_updates / upd_total, 4),
                "query_amplification": amplification(mari.scanned_entries, rm["results"]),
                "verify_amplification": amplification(mari.candidates, rm["results"]),
                "max_delta_len": mari.max_delta,
                "compactions": mari.compactions,
                "exactness_mismatches": rm["mismatches"],
                "wall_s": rm["wall_s"],
            },
            "OrderedIndex": {
                "relocation_rate": round(oi.relocations / upd_total, 4),
                "query_amplification": amplification(oi.candidates, ro["results"]),
                "wall_s": ro["wall_s"],
            },
        }
        print(f"[{reg}] MARI mig={mari.migrations/upd_total:.3f} "
              f"amp={amplification(mari.scanned_entries, rm['results'])} "
              f"mismatch={rm['mismatches']} | OI reloc={oi.relocations/upd_total:.3f} "
              f"amp={amplification(oi.candidates, ro['results'])}")

    # ---- guard sweep on uniform: the central trade-off curve (+ g=0 ablation) ----
    # Run with WIDE queries (qwidth=5000, ~5 buckets) and NARROW queries
    # (qwidth=200, sub-bucket) to expose where guard cost concentrates.
    for label, qw in [("wide_q", 5_000), ("narrow_q", 200)]:
        init, ops, audit = gen("uniform", M=M, n=n, n_updates=U, n_queries=Q,
                               delta=delta, qwidth=qw, seed=2)
        out["guard_sweep"][label] = {}
        for g in [0, 25, 50, 100, 250, 500]:
            mari = MARI(M, width, guard=g)
            orc = Oracle()
            rm = run_struct(mari, init, list(ops), oracle=orc, check=True)
            out["guard_sweep"][label][g] = {
                "migration_rate": round(mari.migrations / U, 4),
                "query_amplification": amplification(mari.scanned_entries, rm["results"]),
                "max_delta_len": mari.max_delta,
                "exactness_mismatches": rm["mismatches"],
            }
            print(f"[sweep {label} g={g}] mig={mari.migrations/U:.4f} "
                  f"amp={amplification(mari.scanned_entries, rm['results'])} "
                  f"mismatch={rm['mismatches']}")

    with open("mari_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote mari_results.json")

if __name__ == "__main__":
    main()
