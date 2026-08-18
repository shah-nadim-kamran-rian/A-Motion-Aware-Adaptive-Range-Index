import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "serif", "font.size": 10,
                     "axes.edgecolor": "#444", "axes.linewidth": 0.8,
                     "savefig.dpi": 200, "figure.dpi": 200})
NAVY = "#12273D"; TEAL = "#1C7293"; AMBER = "#D89A33"; GREY = "#888"; RED = "#B23A48"

d = json.load(open("query_bench_results.json"))
sw = d["selectivity_sweep"]
qw = sorted(int(k) for k in sw)
res = [sw[str(k)]["avg_results"] for k in qw]
p50 = [sw[str(k)]["p50_us"] for k in qw]
p99 = [sw[str(k)]["p99_us"] for k in qw]
scan = [sw[str(k)]["scanned_per_result"] for k in qw]
ver = [sw[str(k)]["verifies_per_result"] for k in qw]

fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.4, 3.0))

# (a) latency vs result size
axL.plot(res, p50, "o-", color=NAVY, lw=1.7, ms=5, label="p50")
axL.plot(res, p99, "s--", color=RED, lw=1.5, ms=5, label="p99")
axL.set_xscale("log"); axL.set_yscale("log")
axL.set_xlabel("result-set size (items returned)")
axL.set_ylabel("query latency (\u00b5s, prototype)")
axL.legend(fontsize=8.5, frameon=False, loc="upper left")
axL.set_title("(a) Latency scales with result size", fontsize=9.5)
axL.grid(True, which="both", ls=":", lw=0.5, color="#ccc")

# (b) per-result cost: amplification + verification, both ~constant
axR.plot(res, scan, "o-", color=TEAL, lw=1.7, ms=5, label="entries scanned / result")
axR.plot(res, ver, "^-", color=AMBER, lw=1.7, ms=5, label="T-verifications / result")
axR.axhline(1.0, color=GREY, ls=":", lw=0.9)
axR.set_xscale("log"); axR.set_ylim(0, 1.6)
axR.set_xlabel("result-set size (items returned)")
axR.set_ylabel("cost per result item")
axR.legend(fontsize=8.5, frameon=False, loc="center right")
axR.set_title("(b) Verification \u2248 1 lookup / result", fontsize=9.5)
axR.grid(True, which="both", ls=":", lw=0.5, color="#ccc")

plt.tight_layout()
plt.savefig("fig_query.png", bbox_inches="tight")
plt.close()
print("wrote fig_query.png")
