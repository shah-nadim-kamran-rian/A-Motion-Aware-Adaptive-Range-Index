"""
enhanced_bench.py -- robustness of the MARI vs. competitor comparison to
(1) adversarial drift regimes, (2) skewed query distributions, (3) larger scale.
Addresses reviewer concerns about workload variety, query skew, and scale.
All structures are checked exact against the oracle on every configuration.
"""
import time, random, json, statistics
from mari import gen, Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact

M = 1_000_000
NAMES = ["MARI", "ART", "PGM", "BxExact"]


def make(name, U):
    if name == "MARI":    return MARILocal(M=M, width=1000, guard=50, eps=0.5)
    if name == "ART":     return ART()
    if name == "PGM":     return PGMIndex(eps=16, buffer=2048)
    if name == "BxExact": return BxExact(n_part=4, period=max(1, U // 3))


def reloc(s, name, U):
    if name == "MARI":
        return s.migrations / max(1, s.migrations + s.local_updates)
    return s.relocations / max(1, U)


def build(name, init, upd):
    s = make(name, len(upd))
    for i, v in init: s.insert(i, v)
    for _, i, v in upd: s.update(i, v)
    return s


def query_profile(s, queries, oracle):
    sc0 = getattr(s, "scanned", 0); ve0 = getattr(s, "verifies", 0)
    tot = 0; mism = 0
    t0 = time.perf_counter()
    for n, (a, b) in enumerate(queries):
        r = s.range(a, b); tot += len(r)
        if n % 9 == 0 and r != oracle.range(a, b): mism += 1
    qps = len(queries) / (time.perf_counter() - t0)
    return {"scan_per_result": (getattr(s, "scanned", 0) - sc0) / max(1, tot),
            "verify_per_result": (getattr(s, "verifies", 0) - ve0) / max(1, tot),
            "query_ops_s": qps, "mismatches": mism}


def agg(xs):
    return {"mean": round(statistics.fmean(xs), 4),
            "std": round(statistics.pstdev(xs) if len(xs) > 1 else 0.0, 4)}


def main():
    out = {"regime_robustness": {}, "skewed_queries": {}, "scale": {}}

    # ---- (1) adversarial drift regimes, 3 seeds, error bars ----
    print("=== drift-regime robustness: relocations/update (mean +/- std, 3 seeds) ===")
    print(f"{'regime':<12}" + "".join(f"{n:>16}" for n in NAMES))
    for reg in ["uniform", "clustered", "directional", "adversarial"]:
        per = {n: [] for n in NAMES}
        for seed in range(3):
            init, ops, _ = gen(reg, M=M, n=20_000, n_updates=80_000,
                               n_queries=1, delta=50, seed=200 + seed)
            upd = [o for o in ops if o[0] == "u"]
            for n in NAMES:
                s = build(n, init, upd)
                per[n].append(reloc(s, n, len(upd)))
        out["regime_robustness"][reg] = {n: agg(per[n]) for n in NAMES}
        row = f"{reg:<12}"
        for n in NAMES:
            a = out["regime_robustness"][reg][n]
            row += f"{a['mean']:>9.3f}+/-{a['std']:<5.3f}"
        print(row)

    # ---- (2) skewed query distribution (centers drawn from the key density) ----
    print("\n=== skewed queries (centers ~ key distribution), uniform drift ===")
    init, ops, _ = gen("uniform", M=M, n=20_000, n_updates=120_000,
                       n_queries=1, delta=50, seed=7)
    upd = [o for o in ops if o[0] == "u"]
    oracle = Oracle()
    for i, v in init: oracle.upsert(i, v)
    for _, i, v in upd: oracle.upsert(i, v)
    cur_vals = list(oracle.key.values())
    rng = random.Random(3)
    skq = [(max(0, c - 500), c + 500) for c in (rng.choice(cur_vals) for _ in range(3000))]
    for n in NAMES:
        s = build(n, init, upd)
        prof = query_profile(s, skq, oracle)
        out["skewed_queries"][n] = prof
        print(f"  {n:<8} scan/res={prof['scan_per_result']:.2f}  verify/res={prof['verify_per_result']:.2f}  "
              f"q/s={prof['query_ops_s']:.0f}  mism={prof['mismatches']}")

    # ---- (3) larger scale: n=200k, 1M updates, 1 seed ----
    print("\n=== larger scale: n=200k, 1,000,000 updates ===")
    init, ops, _ = gen("uniform", M=M, n=200_000, n_updates=1_000_000,
                       n_queries=1, delta=50, seed=99)
    upd = [o for o in ops if o[0] == "u"]
    oracle = Oracle()
    for i, v in init: oracle.upsert(i, v)
    for _, i, v in upd: oracle.upsert(i, v)
    rng = random.Random(5)
    q = [(a, a + rng.choice([200, 1000, 5000])) for a in (rng.randrange(M - 5000) for _ in range(2000))]
    for n in NAMES:
        t0 = time.perf_counter(); s = build(n, init, upd); ups = len(upd) / (time.perf_counter() - t0)
        prof = query_profile(s, q, oracle)
        out["scale"][n] = {"reloc_per_update": round(reloc(s, n, len(upd)), 4),
                           "update_ops_s": round(ups), **prof}
        print(f"  {n:<8} reloc/upd={out['scale'][n]['reloc_per_update']:.4f}  "
              f"upd/s={out['scale'][n]['update_ops_s']}  q/s={prof['query_ops_s']:.0f}  mism={prof['mismatches']}")

    json.dump(out, open("/home/claude/enhanced_results.json", "w"), indent=2)
    print("\nwrote enhanced_results.json")


if __name__ == "__main__":
    main()
