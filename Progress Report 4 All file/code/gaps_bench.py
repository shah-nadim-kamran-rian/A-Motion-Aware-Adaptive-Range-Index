"""
gaps_bench.py -- close remaining reviewer gaps:
  (A) adversarial/clustered/directional drift at LARGER scale
  (B) more seeds -> visible (non-zero) confidence intervals
  (C) hotspot overflow-chain QUERY cost (characterize the chains)
All configurations checked exact against the oracle.
"""
import time, random, json, statistics
from collections import Counter
from mari import gen, Oracle
from mari_v2 import MARILocal
from competitors import ART, PGMIndex, BxExact
from hotspot_demo import HotspotMARI

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


def exact_sample(s, oracle, k=400, seed=1):
    rng = random.Random(seed); mism = 0
    for _ in range(k):
        a = rng.randrange(M - 5000); b = a + rng.choice([200, 1000, 5000])
        if s.range(a, b) != oracle.range(a, b): mism += 1
    return mism


def main():
    out = {"A_adversarial_at_scale": {}, "B_seeded_CIs": {}, "C_hotspot_chain_query": {}}

    # ---------- (A) MARI at large scale under the guard's worst regimes ----------
    print("=== (A1) MARI at n=500k, 2,000,000 updates, worst-case regimes ===")
    for reg in ["clustered", "directional", "adversarial"]:
        init, ops, _ = gen(reg, M=M, n=500_000, n_updates=2_000_000, n_queries=1, delta=50, seed=11)
        upd = [o for o in ops if o[0] == "u"]
        s = build("MARI", init, upd)
        orc = Oracle()
        for i, v in init: orc.upsert(i, v)
        for _, i, v in upd: orc.upsert(i, v)
        m = exact_sample(s, orc)
        out["A_adversarial_at_scale"].setdefault("MARI_500k_2M", {})[reg] = {
            "reloc_per_update": round(reloc(s, "MARI", len(upd)), 4), "mismatches": m}
        print(f"  MARI {reg:<12} reloc/upd={reloc(s,'MARI',len(upd)):.4f}  mism={m}")

    # ---------- (A2) all four under ADVERSARIAL drift at scale ----------
    print("=== (A2) all structures at n=300k, 1,000,000 updates, adversarial ===")
    init, ops, _ = gen("adversarial", M=M, n=300_000, n_updates=1_000_000, n_queries=1, delta=50, seed=13)
    upd = [o for o in ops if o[0] == "u"]
    orc = Oracle()
    for i, v in init: orc.upsert(i, v)
    for _, i, v in upd: orc.upsert(i, v)
    out["A_adversarial_at_scale"]["all_300k_1M_adversarial"] = {}
    for name in NAMES:
        s = build(name, init, upd); m = exact_sample(s, orc)
        out["A_adversarial_at_scale"]["all_300k_1M_adversarial"][name] = {
            "reloc_per_update": round(reloc(s, name, len(upd)), 4), "mismatches": m}
        print(f"  {name:<8} reloc/upd={reloc(s,name,len(upd)):.4f}  mism={m}")

    # ---------- (B) 8 seeds -> visible CIs (reloc + query throughput) ----------
    print("=== (B) regime robustness, 8 seeds, reloc (4 dp) + query throughput ===")
    for reg in ["uniform", "clustered", "directional", "adversarial"]:
        rr, qq = [], []
        for seed in range(8):
            init, ops, _ = gen(reg, M=M, n=20_000, n_updates=80_000, n_queries=1, delta=50, seed=300 + seed)
            upd = [o for o in ops if o[0] == "u"]
            s = build("MARI", init, upd)
            rr.append(reloc(s, "MARI", len(upd)))
            rng = random.Random(seed)
            q = [(a, a + rng.choice([200, 1000, 5000])) for a in (rng.randrange(M - 5000) for _ in range(1500))]
            t0 = time.perf_counter()
            for a, b in q: s.range(a, b)
            qq.append(len(q) / (time.perf_counter() - t0))
        out["B_seeded_CIs"][reg] = {
            "reloc_mean": round(statistics.fmean(rr), 5), "reloc_std": round(statistics.pstdev(rr), 5),
            "qps_mean": round(statistics.fmean(qq)), "qps_std": round(statistics.pstdev(qq))}
        r = out["B_seeded_CIs"][reg]
        print(f"  {reg:<12} reloc={r['reloc_mean']:.5f}±{r['reloc_std']:.5f}  qps={r['qps_mean']}±{r['qps_std']}")

    # ---------- (C) hotspot overflow-chain QUERY cost ----------
    print("=== (C) hotspot chain query cost: entries examined near the hot value ===")
    H = 137_000
    def build_hot(use_ovf, n=8000, tau=64, seed=5):
        rnd = random.Random(seed)
        idx = HotspotMARI(M, width=1000, tau=tau); idx.use_overflow = use_ovf
        orc = Oracle()
        for i in range(n):
            v = rnd.randrange(M); idx.insert(i, v); orc.upsert(i, v)
        for _ in range(120_000):
            i = rnd.randrange(n)
            if i < int(n * 0.35) and rnd.random() < 0.7: v = H
            else:
                cur = orc.key.get(i, rnd.randrange(M)); v = min(M - 1, max(0, cur + rnd.randint(-50, 50)))
            idx.update(i, v); orc.upsert(i, v)
        return idx, orc
    def counted_query(idx, a, b):
        examined = 0; res = set()
        lo = max(0, a // idx.w - 1); hi = min(idx.nb - 1, b // idx.w + 1)
        for j in range(lo, hi + 1):
            for id_, v in idx.member[j].items():
                examined += 1
                if a <= v <= b: res.add(id_)
        for v, ids in idx.overflow.items():
            if a <= v <= b: res |= ids
        return res, examined
    for use_ovf in (False, True):
        idx, orc = build_hot(use_ovf)
        # queries that OVERLAP the hotspot bucket but EXCLUDE the hot value H
        near = [(H + 200, H + 900)]
        # a query that INCLUDES H
        incl = [(H - 100, H + 100)]
        def avg_examined(qs):
            tot = 0; res_tot = 0; mism = 0
            for (a, b) in qs:
                r, ex = counted_query(idx, a, b); tot += ex; res_tot += len(r)
                if r != orc.range(a, b): mism += 1
            return tot / len(qs), res_tot / len(qs), mism
        near_ex, near_res, m1 = avg_examined(near)
        incl_ex, incl_res, m2 = avg_examined(incl)
        out["C_hotspot_chain_query"]["with_overflow" if use_ovf else "without_overflow"] = {
            "near_hotspot_examined": round(near_ex, 1), "near_hotspot_results": round(near_res, 1),
            "incl_hotspot_examined": round(incl_ex, 1), "incl_hotspot_results": round(incl_res, 1),
            "overflow_chains": len(idx.overflow), "mismatches": m1 + m2}
        tag = "with_overflow" if use_ovf else "without_overflow"
        r = out["C_hotspot_chain_query"][tag]
        print(f"  {tag:<16} near-hotspot examined={r['near_hotspot_examined']} (results {r['near_hotspot_results']}) "
              f"| incl-hotspot examined={r['incl_hotspot_examined']} (results {r['incl_hotspot_results']}) mism={r['mismatches']}")

    json.dump(out, open("/home/claude/gaps_results.json", "w"), indent=2)
    print("\nwrote gaps_results.json")


if __name__ == "__main__":
    main()
