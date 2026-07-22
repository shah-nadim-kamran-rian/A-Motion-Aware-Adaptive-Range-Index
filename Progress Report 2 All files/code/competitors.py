

# ======================================================================
# ART -- Adaptive Radix Tree over fixed 4-byte big-endian keys (value order)
# ======================================================================
KEYW = 4  # bytes; supports values up to 2^32-1


def _k2b(k):
    return ((k >> 24) & 0xFF, (k >> 16) & 0xFF, (k >> 8) & 0xFF, k & 0xFF)


class _Leaf:
    __slots__ = ("key", "ids")
    def __init__(self, key):
        self.key = key
        self.ids = set()


class _Node:
    """Adaptive inner node. typ tracks logical ART node size (4/16/48/256)."""
    __slots__ = ("typ", "n", "keys", "kids", "idx256")
    def __init__(self, typ=4):
        self.typ = typ
        self.n = 0
        if typ == 48:
            self.idx256 = [-1] * 256
            self.kids = [None] * 48
            self.keys = None
        elif typ == 256:
            self.kids = [None] * 256
            self.keys = None; self.idx256 = None
        else:  # 4 or 16
            self.keys = [0] * typ
            self.kids = [None] * typ
            self.idx256 = None

    def child(self, b):
        t = self.typ
        if t == 256:
            return self.kids[b]
        if t == 48:
            s = self.idx256[b]
            return self.kids[s] if s >= 0 else None
        for i in range(self.n):
            if self.keys[i] == b:
                return self.kids[i]
        return None

    def children_sorted(self):
        """(byte, child) pairs in ascending byte order -- for range traversal."""
        t = self.typ
        if t == 256:
            return [(b, self.kids[b]) for b in range(256) if self.kids[b] is not None]
        if t == 48:
            return [(b, self.kids[self.idx256[b]]) for b in range(256) if self.idx256[b] >= 0]
        pairs = [(self.keys[i], self.kids[i]) for i in range(self.n)]
        pairs.sort()
        return pairs


class ART:
    def __init__(self, **_):
        self.root = _Node(4)
        self.relocations = 0
        self.node_writes = 0      # node allocations + type upgrades
        self.scanned = 0
        self.verifies = 0         # ART answers are exact without verification
        self.cur = {}             # id -> value (authoritative, for update bookkeeping)

    # ---- node child insertion with adaptive growth ----
    def _add_child(self, node, b, kid):
        t = node.typ
        if t == 256:
            node.kids[b] = kid; node.n += 1; return node
        if t == 48:
            if node.n < 48:
                node.idx256[b] = node.n; node.kids[node.n] = kid; node.n += 1; return node
            grown = _Node(256); self.node_writes += 1
            for bb in range(256):
                s = node.idx256[bb]
                if s >= 0: grown.kids[bb] = node.kids[s]
            grown.n = node.n; grown.kids[b] = kid; grown.n += 1
            return grown
        # type 4 or 16
        if node.n < t:
            node.keys[node.n] = b; node.kids[node.n] = kid; node.n += 1; return node
        if t == 4:
            grown = _Node(16); self.node_writes += 1
            for i in range(node.n):
                grown.keys[i] = node.keys[i]; grown.kids[i] = node.kids[i]
            grown.n = node.n
            grown.keys[grown.n] = b; grown.kids[grown.n] = kid; grown.n += 1
            return grown
        grown = _Node(48); self.node_writes += 1   # 16 -> 48
        for i in range(node.n):
            grown.idx256[node.keys[i]] = i; grown.kids[i] = node.kids[i]
        grown.n = node.n
        grown.idx256[b] = grown.n; grown.kids[grown.n] = kid; grown.n += 1
        return grown

    def _set_child(self, parent, b, newkid):
        """Replace the child pointer for byte b in parent (parent type fixed)."""
        t = parent.typ
        if t == 256:
            parent.kids[b] = newkid; return
        if t == 48:
            parent.kids[parent.idx256[b]] = newkid; return
        for i in range(parent.n):
            if parent.keys[i] == b:
                parent.kids[i] = newkid; return

    def _insert_key(self, key, idv):
        bs = _k2b(key)
        node = self.root; parent = None; pb = 0
        for d in range(KEYW):
            b = bs[d]
            kid = node.child(b)
            if d == KEYW - 1:
                if kid is None:
                    leaf = _Leaf(key); leaf.ids.add(idv); self.node_writes += 1
                    grown = self._add_child(node, b, leaf)
                    if grown is not node:
                        if parent is None: self.root = grown
                        else: self._set_child(parent, pb, grown)
                    return
                kid.ids.add(idv); return
            if kid is None:
                kid = _Node(4); self.node_writes += 1
                grown = self._add_child(node, b, kid)
                if grown is not node:
                    if parent is None: self.root = grown
                    else: self._set_child(parent, pb, grown)
                    node = grown
            parent = node; pb = b; node = kid

    def _delete_key(self, key, idv):
        bs = _k2b(key); node = self.root
        path = []
        for d in range(KEYW):
            b = bs[d]; kid = node.child(b)
            if kid is None: return
            path.append((node, b)); node = kid
        node.ids.discard(idv)   # node is the leaf
        # (we keep empty leaves/nodes; emptiness is handled by value bookkeeping)

    # ---- public interface ----
    def insert(self, idv, value):
        self.cur[idv] = value
        self._insert_key(value, idv)

    def update(self, idv, value):
        old = self.cur.get(idv)
        if old is None: return self.insert(idv, value)
        if old == value: return
        self._delete_key(old, idv)      # relocation: remove from old position ...
        self._insert_key(value, idv)    # ... insert at new position
        self.cur[idv] = value
        self.relocations += 1

    def delete(self, idv):
        old = self.cur.pop(idv, None)
        if old is not None: self._delete_key(old, idv)

    def range(self, a, b):
        out = set()
        self._range_rec(self.root, 0, 0, a, b, out)
        return out

    def _range_rec(self, node, depth, prefix, a, b, out):
        if isinstance(node, _Leaf):
            self.scanned += 1
            if a <= node.key <= b:
                out |= node.ids
            return
        shift = 8 * (KEYW - 1 - depth)
        for byte, kid in node.children_sorted():
            lo = prefix | (byte << shift)
            hi = lo | ((1 << shift) - 1)          # subtree covers [lo, hi]
            if hi < a or lo > b:
                continue                           # prune: outside [a,b]
            self._range_rec(kid, depth + 1, lo, a, b, out)


# ======================================================================
# PGMIndex -- dynamic PGM-style learned index
#   * query path: piecewise-linear segments with +/- eps_pgm position error
#     (the defining PGM mechanism), built per sorted run
#   * update path: logarithmic method (leveled sorted runs) + tombstones,
#     i.e. a drift update = tombstone(old value,id) + insert(new value,id)
# ======================================================================
import bisect


def _build_pgm_segments(values, eps):
    """Optimal-ish piecewise-linear segments: position(value) within +/- eps.
    Returns list of (start_value, slope, intercept_pos, start_index)."""
    segs = []
    n = len(values)
    i = 0
    while i < n:
        x0 = values[i]; y0 = i
        lo_slope = -float("inf"); hi_slope = float("inf")
        j = i + 1
        while j < n:
            dx = values[j] - x0
            if dx == 0:
                j += 1; continue
            # need |slope*dx - (j - y0)| <= eps  ->  slope in [(j-y0-eps)/dx,(j-y0+eps)/dx]
            s_lo = (j - y0 - eps) / dx
            s_hi = (j - y0 + eps) / dx
            nlo = max(lo_slope, s_lo); nhi = min(hi_slope, s_hi)
            if nlo > nhi:
                break
            lo_slope, hi_slope = nlo, nhi
            j += 1
        slope = 0.0 if lo_slope == -float("inf") else (lo_slope + hi_slope) / 2
        segs.append((x0, slope, y0, i))
        i = j
    return segs


class _Run:
    """A sorted run of (value, id), with a PGM segment index for lookups."""
    __slots__ = ("vals", "items", "segs", "eps")
    def __init__(self, items, eps):
        items.sort()
        self.items = items                       # sorted [(value, id)]
        self.vals = [v for v, _ in items]
        self.eps = eps
        self.segs = _build_pgm_segments(self.vals, eps) if self.vals else []

    def _predict(self, key):
        segs = self.segs
        si = bisect.bisect_right(segs, (key, float("inf"))) - 1
        if si < 0:
            return 0
        x0, slope, y0, _ = segs[si]
        return int(y0 + slope * (key - x0))

    def lower_bound(self, key):
        """First index with value >= key. PGM predict localizes to +/- eps; we
        resolve exactly (falling back to a full bisect if the window misses, so
        correctness never depends on the model)."""
        if not self.vals:
            return 0
        p = self._predict(key)
        lo = max(0, p - self.eps - 1); hi = min(len(self.vals), p + self.eps + 1)
        if (lo == 0 or self.vals[lo - 1] < key) and (hi == len(self.vals) or self.vals[hi - 1] >= key):
            return lo + bisect.bisect_left(self.vals[lo:hi], key)
        return bisect.bisect_left(self.vals, key)


class PGMIndex:
    """Dynamic PGM-style learned index under drift.
    Query path: piecewise-linear segments localize the lower bound to +/- eps,
    resolved exactly. Update path: logarithmic-method leveled runs; because a
    drifting key revisits values, exactness is preserved by VERIFYING each
    candidate against the authoritative current value (stale copies are also
    dropped during merges). This is the cost a learned index pays under drift."""
    def __init__(self, eps=16, buffer=2048, **_):
        self.eps = eps; self.B = buffer
        self.buf = []                 # level-0 buffer of (value, id), kept SORTED
        self.levels = []              # list of _Run (or None), geometric growth
        self.cur = {}                 # id -> current value (authoritative)
        self.relocations = 0
        self.node_writes = 0          # merge / rebuild work (entries rewritten)
        self.scanned = 0
        self.verifies = 0

    def _live(self, items):
        cur = self.cur
        return [(v, i) for (v, i) in items if cur.get(i) == v]   # drop stale

    def _flush(self):
        run = _Run(list(self.buf), self.eps); self.buf = []
        self.node_writes += len(run.items)
        carry = run; i = 0
        while i < len(self.levels) and self.levels[i] is not None:
            merged = self._live(self.levels[i].items + carry.items)   # GC stale on merge
            self.node_writes += len(merged)
            carry = _Run(merged, self.eps); self.levels[i] = None; i += 1
        if i == len(self.levels): self.levels.append(carry)
        else: self.levels[i] = carry

    def insert(self, idv, value):
        self.cur[idv] = value
        self.buf.insert(bisect.bisect_left(self.buf, (value, idv)), (value, idv))
        if len(self.buf) >= self.B: self._flush()

    def update(self, idv, value):
        old = self.cur.get(idv)
        if old is None: return self.insert(idv, value)
        if old == value: return
        self.cur[idv] = value
        self.buf.insert(bisect.bisect_left(self.buf, (value, idv)), (value, idv))
        self.relocations += 1
        if len(self.buf) >= self.B: self._flush()

    def delete(self, idv):
        self.cur.pop(idv, None)

    def range(self, a, b):
        out = set(); cur = self.cur
        k = bisect.bisect_left(self.buf, (a, -1)); nb = len(self.buf)
        while k < nb and self.buf[k][0] <= b:
            v, i = self.buf[k]; self.scanned += 1; self.verifies += 1
            if cur.get(i) == v: out.add(i)
            k += 1
        for run in self.levels:
            if run is None or not run.vals: continue
            k = run.lower_bound(a); items = run.items; n = len(items)
            while k < n and items[k][0] <= b:
                v, i = items[k]; self.scanned += 1; self.verifies += 1
                if cur.get(i) == v: out.add(i)
                k += 1
        return out


# ======================================================================
# BxExact -- Bx-tree (time-partitioned moving-object index) + EXACTNESS ADAPTER
#   * objects are indexed by value within the time partition of their last
#     update; a query scans all live partitions, gathers value-in-[a,b]
#     candidates, and VERIFIES each against the authoritative current value
#     (the adapter that turns the Bx-tree's over-approximate answer exact).
#   * partitions roll over: when the current partition is recycled, still-current
#     entries are re-indexed (classic Bx-tree periodic re-insertion) and stale
#     ones dropped.
# ======================================================================
import bisect as _bx_bisect


class BxExact:
    def __init__(self, n_part=4, period=20_000, **_):
        self.np = n_part
        self.period = period
        self.parts = [[] for _ in range(n_part)]   # each: sorted [(value, id)]
        self.cur = {}                               # id -> current value
        self.t = 0                                  # update counter
        self.p = 0                                  # current partition
        self.relocations = 0
        self.node_writes = 0                        # inserts + re-index writes
        self.scanned = 0
        self.verifies = 0

    def _insert(self, part, v, i):
        lst = self.parts[part]
        lst.insert(_bx_bisect.bisect_left(lst, (v, i)), (v, i))
        self.node_writes += 1

    def _advance(self):
        self.p = (self.p + 1) % self.np
        recycled = self.parts[self.p]
        if recycled:                                # re-index still-current entries, drop stale
            keep = [(v, i) for (v, i) in recycled if self.cur.get(i) == v]
            self.parts[self.p] = []
            tgt = self.p                            # they land back in the (now empty) current partition
            for v, i in keep:
                self.parts[tgt].insert(_bx_bisect.bisect_left(self.parts[tgt], (v, i)), (v, i))
                self.node_writes += 1

    def insert(self, idv, value):
        self.cur[idv] = value
        self._insert(self.p, value, idv)
        self.t += 1
        if self.t % self.period == 0:
            self._advance()

    def update(self, idv, value):
        old = self.cur.get(idv)
        if old is None:
            return self.insert(idv, value)
        if old == value:
            return
        self.cur[idv] = value
        self._insert(self.p, value, idv)            # insert current entry into current partition
        self.relocations += 1                       # old entry left stale (lazy), handled by verify
        self.t += 1
        if self.t % self.period == 0:
            self._advance()

    def delete(self, idv):
        self.cur.pop(idv, None)

    def range(self, a, b):
        out = set(); cur = self.cur
        for part in self.parts:
            lo = _bx_bisect.bisect_left(part, (a, -1))
            k = lo; n = len(part)
            while k < n and part[k][0] <= b:
                v, i = part[k]; self.scanned += 1; self.verifies += 1
                if cur.get(i) == v: out.add(i)      # exactness adapter: verify current value
                k += 1
        return out
