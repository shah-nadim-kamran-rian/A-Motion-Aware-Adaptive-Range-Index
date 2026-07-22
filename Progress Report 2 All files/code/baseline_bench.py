
import time, random, json, statistics
from mari import gen, Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact

M = 1_000_000


def make(name, U):
    if name == "MARI":    return MARILocal(M=M, width=1000, guard=50, eps=0.5)
    if name == "ART":     return ART()
    if name == "PGM":     return PGMIndex(eps=16, buffer=2048)
    if name == "BxExact": return BxExact(n_part=4, period=max(1, U // 3))


def reloc_rate(s, name, U):
    if name == "MARI":
        tot = s.migrations + s.local_updates
        return s.migrations / max(1, tot)
    return s.relocations / max(1, U)


def writes_per_update(s, name, U):
    if name == "MARI":
        # MARI: each update appends ~1 delta record; compaction rewrites amortized
        return (s.migrations + s.local_updates + getattr(s, "compactions", 0)) / max(1, U)
    return s.node_writes / max(1, U)


def run_one(name, init, upd, queries, oracle):
    s = make(name, len(upd))
    t0 = time.perf_counter()
    for i, v in init: s.insert(i, v)
    for _, i, v in upd: s.update(i, v)
    upd_s = len(upd) / (time.perf_counter() - t0)

    sc0 = getattr(s, "scanned", 0); ve0 = getattr(s, "verifies", 0)
    tot_res = 0; mism = 0
    t0 = time.perf_counter()
    for n, (a, b) in enumerate(queries):
        r = s.range(a, b); tot_res += len(r)
        if n % 7 == 0 and r != oracle.range(a, b): mism += 1
    q_s = len(queries) / (time.perf_counter() - t0)
    scanned = getattr(s, "scanned", 0) - sc0
    verifies = getattr(s, "verifies", 0) - ve0
    return {
        "reloc_per_update": reloc_rate(s, name, len(upd)),
        "writes_per_update": writes_per_update(s, name, len(upd)),
        "scan_per_result": scanned / max(1, tot_res),
        "verify_per_result": verifies / max(1, tot_res),
        "update_ops_s": upd_s, "query_ops_s": q_s, "mismatches": mism,
    }


def agg(runs, key):
    xs = [r[key] for r in runs]
    return {"mean": statistics.fmean(xs),
            "std": statistics.pstdev(xs) if len(xs) > 1 else 0.0}


def main():
    NAMES = ["MARI", "ART", "PGM", "BxExact"]
    out = {"problem": "exact range reporting under bounded drift",
           "main": {"n": 20_000, "updates": 120_000, "seeds": 5, "queries": 3000, "results": {}},
           "scale": {"n": 100_000, "updates": 600_000, "queries": 3000, "results": {}}}

    # ---- main: 5 seeds, error bars ----
    print("=== main comparison (n=20k, 120k updates, 5 seeds) ===")
    per = {nm: [] for nm in NAMES}
    for seed in range(5):
        init, ops, _ = gen("uniform", M=M, n=20_000, n_updates=120_000,
                           n_queries=1, delta=50, seed=100 + seed)
        upd = [o for o in ops if o[0] == "u"]
        oracle = Oracle()
        for i, v in init: oracle.upsert(i, v)
        for _, i, v in upd: oracle.upsert(i, v)
        rng = random.Random(7 + seed)
        queries = [(a, a + rng.choice([200, 1000, 5000]))
                   for a in (rng.randrange(M - 5000) for _ in range(3000))]
        for nm in NAMES:
            per[nm].append(run_one(nm, init, upd, queries, oracle))
    for nm in NAMES:
        runs = per[nm]
        out["main"]["results"][nm] = {k: agg(runs, k) for k in
            ["reloc_per_update", "writes_per_update", "scan_per_result",
             "verify_per_result", "update_ops_s", "query_ops_s"]}
        out["main"]["results"][nm]["mismatches_total"] = sum(r["mismatches"] for r in runs)
        r = out["main"]["results"][nm]
        print(f"  {nm:<8} reloc/upd={r['reloc_per_update']['mean']:.3f}"
              f"+/-{r['reloc_per_update']['std']:.3f}  "
              f"writes/upd={r['writes_per_update']['mean']:.2f}  "
              f"verify/res={r['verify_per_result']['mean']:.2f}  "
              f"q/s={r['query_ops_s']['mean']:.0f}  mism={r['main' if False else 'mismatches_total']}")

    # ---- scale: single larger run ----
    print("\n=== scale run (n=100k, 600k updates, 1 seed) ===")
    init, ops, _ = gen("uniform", M=M, n=100_000, n_updates=600_000,
                       n_queries=1, delta=50, seed=42)
    upd = [o for o in ops if o[0] == "u"]
    oracle = Oracle()
    for i, v in init: oracle.upsert(i, v)
    for _, i, v in upd: oracle.upsert(i, v)
    rng = random.Random(13)
    queries = [(a, a + rng.choice([200, 1000, 5000]))
               for a in (rng.randrange(M - 5000) for _ in range(3000))]
    for nm in NAMES:
        r = run_one(nm, init, upd, queries, oracle)
        out["scale"]["results"][nm] = r
        print(f"  {nm:<8} reloc/upd={r['reloc_per_update']:.3f}  writes/upd={r['writes_per_update']:.2f}  "
              f"verify/res={r['verify_per_result']:.2f}  upd/s={r['update_ops_s']:.0f}  "
              f"q/s={r['query_ops_s']:.0f}  mism={r['mismatches']}")

    json.dump(out, open("/home/claude/baseline_results.json", "w"), indent=2)
    print("\nwrote baseline_results.json")


if __name__ == "__main__":
    main()
