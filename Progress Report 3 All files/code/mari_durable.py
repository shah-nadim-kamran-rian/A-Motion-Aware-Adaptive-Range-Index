"""
Where does MARI's relocation-cost decoupling actually pay off?
Two cost-model experiments (NOT wall-clock; single-thread Python can't show
concurrency speedup, and durable I/O isn't present -- so we model both):

  A. DURABLE WRITE AMPLIFICATION (page model, page = P entries):
     - relocate-in-place (B+-tree / SortedList / radix leaves): an update is a
       delete + insert that dirties the leaf page(s) holding the old and new
       positions -> RANDOM read-modify-write page flushes.
     - MARI: a local update appends one record to a per-bucket SEQUENTIAL delta
       log; migrations append two; compaction rewrites a bucket's stable
       sequentially. We count sequential vs random page-writes per update.

  B. CONTENTION (sharded-lock model):
     - global ordered index: every update contends on one structure -> serialized.
     - partitioned (radix / MARI): an update locks the bucket(s) it touches;
       a cross-partition op locks two. We report the cross-partition (2-lock)
       rate, which a sharded-lock scheme must serialize.

All counts are implementation-independent. Same update stream for every method.
"""

import bisect, math, json
from sortedcontainers import SortedList
from mari import gen

def ceil_div(a, b): return -(-a // b)

# ---------------------------------------------------------------- A: page model
def acct_inplace_global(init, upds, P):
    sl = SortedList(); cur = {}
    for i, v in init: cur[i] = v; sl.add((v, i))
    random_pages = 0
    for _, i, v in upds:
        old = cur.get(i)
        if old is None: cur[i] = v; sl.add((v, i)); continue
        if old == v: continue
        r_old = sl.index((old, i)); sl.remove((old, i))
        r_new = sl.bisect_left((v, i)); sl.add((v, i)); cur[i] = v
        random_pages += 1 if (r_old // P) == (r_new // P) else 2
    return {"random_pages": random_pages, "sequential_pages": 0}

def acct_inplace_radix(init, upds, P, M, width):
    nb = ceil_div(M, width); w = width
    leaf = [SortedList() for _ in range(nb)]; cur = {}
    b = lambda k: min(k // w, nb - 1)
    for i, v in init: cur[i] = v; leaf[b(v)].add((v, i))
    random_pages = 0; cross = 0
    for _, i, v in upds:
        old = cur.get(i)
        if old is None: cur[i] = v; leaf[b(v)].add((v, i)); continue
        if old == v: continue
        bo, bn = b(old), b(v)
        Lo = leaf[bo]; r_old = Lo.index((old, i)); Lo.remove((old, i))
        Ln = leaf[bn]; r_new = Ln.bisect_left((v, i)); Ln.add((v, i)); cur[i] = v
        if bo == bn:
            random_pages += 1 if (r_old // P) == (r_new // P) else 2
        else:
            random_pages += 2; cross += 1
    return {"random_pages": random_pages, "sequential_pages": 0, "cross_partition": cross}

def acct_mari(init, upds, P, M, width, guard, eps):
    nb = ceil_div(M, width); w = width
    member = [set() for _ in range(nb)]      # authoritative membership per bucket
    Dcnt = [0] * nb                          # appends since last compaction
    cur = {}                                 # id -> (key, bucket)
    b = lambda k: min(k // w, nb - 1)
    in_guard = lambda bb, k: bb * w - guard <= k <= (bb + 1) * w - 1 + guard
    seq_delta = 0; seq_compact = 0
    migrations = 0; locals_ = 0

    def append(bb):
        nonlocal seq_delta, seq_compact
        Dcnt[bb] += 1
        if Dcnt[bb] % P == 0: seq_delta += 1
        if Dcnt[bb] >= max(1, int(eps * max(1, len(member[bb])))):
            if Dcnt[bb] % P != 0: seq_delta += 1            # flush partial delta page
            seq_compact += ceil_div(len(member[bb]), P)      # rewrite stable sequentially
            Dcnt[bb] = 0

    for i, v in init:
        bb = b(v); member[bb].add(i); cur[i] = (v, bb); append(bb)
    for _, i, v in upds:
        old = cur.get(i)
        if old is None:
            bb = b(v); member[bb].add(i); cur[i] = (v, bb); append(bb); continue
        ok, bsrc = old
        if ok == v: continue
        if in_guard(bsrc, v):
            cur[i] = (v, bsrc); append(bsrc); locals_ += 1
        else:
            bdst = b(v)
            member[bsrc].discard(i); member[bdst].add(i); cur[i] = (v, bdst)
            append(bsrc); append(bdst); migrations += 1
    return {"random_pages": 0, "sequential_pages": seq_delta + seq_compact,
            "seq_delta": seq_delta, "seq_compact": seq_compact,
            "migrations": migrations, "locals": locals_}

# ----------------------------------------------------------- B: contention model
def contention(init, upds, M, width, guard):
    """cross-partition (2-lock) op rate for radix(g=0) and MARI(guard)."""
    nb = ceil_div(M, width); w = width
    b = lambda k: min(k // w, nb - 1)
    in_guard = lambda bb, k: bb * w - guard <= k <= (bb + 1) * w - 1 + guard
    cur = {i: v for i, v in init}
    radix_cross = 0; mari_cross = 0; mari_loc = {i: b(v) for i, v in init}; n_upd = 0
    for _, i, v in upds:
        old = cur.get(i)
        if old is None or old == v:
            cur[i] = v; continue
        n_upd += 1
        if b(old) != b(v): radix_cross += 1            # radix locks 2 leaves
        bsrc = mari_loc[i]
        if in_guard(bsrc, v):
            pass                                       # MARI: 1 lock
        else:
            mari_cross += 1; mari_loc[i] = b(v)        # MARI: 2 locks
        cur[i] = v
    return {"updates": n_upd,
            "global_serialized_rate": 1.0,
            "radix_2lock_rate": round(radix_cross / n_upd, 4),
            "mari_2lock_rate": round(mari_cross / n_upd, 4)}

# ----------------------------------------------------------------------- driver
def main():
    M, n, U, delta, width, P, eps = 1_000_000, 20_000, 200_000, 50, 1_000, 256, 0.5
    out = {"config": {"M": M, "n": n, "updates": U, "drift_delta": delta,
                      "bucket_width": width, "page_entries_P": P, "eps": eps}, "regimes": {}}
    for reg in ["uniform", "clustered", "directional"]:
        init, ops, _ = gen(reg, M=M, n=n, n_updates=U, n_queries=1, delta=delta, seed=11)
        upds = [o for o in ops if o[0] == "u"]
        g = acct_inplace_global(init, upds, P)
        rx = acct_inplace_radix(init, upds, P, M, width)
        mr = acct_mari(init, upds, P, M, width, guard=delta, eps=eps)
        ct = contention(init, upds, M, width, guard=delta)
        nU = len(upds)
        out["regimes"][reg] = {
            "per_update_page_writes": {
                "InPlace_global (random)": round(g["random_pages"] / nU, 3),
                "InPlace_radix (random)": round(rx["random_pages"] / nU, 3),
                "MARI (sequential)": round(mr["sequential_pages"] / nU, 4),
            },
            "mari_seq_breakdown": {"delta_pages": mr["seq_delta"], "compact_pages": mr["seq_compact"],
                                   "migrations": mr["migrations"], "locals": mr["locals"]},
            "contention": ct,
        }
        print(f"[{reg}]")
        print(f"   page-writes/update  global(random)={g['random_pages']/nU:.3f}  "
              f"radix(random)={rx['random_pages']/nU:.3f}  MARI(sequential)={mr['sequential_pages']/nU:.4f}")
        print(f"   2-lock op rate      radix={ct['radix_2lock_rate']}  MARI={ct['mari_2lock_rate']}  "
              f"(global serializes all)\n")
    with open("/home/claude/mari_durable.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote mari_durable.json")

if __name__ == "__main__":
    main()
