import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({"font.family": "serif", "font.size": 10,
                     "axes.edgecolor": "#444", "axes.linewidth": 0.8,
                     "savefig.dpi": 200, "figure.dpi": 200})
NAVY="#12273D"; TEAL="#1C7293"; AMBER="#D89A33"; RED="#B23A48"; GREY="#9aa"

d = json.load(open("baseline_results.json"))["main"]["results"]
names = ["MARI", "ART", "PGM", "BxExact"]
labels = ["MARI", "ART", "PGM", "Bx-tree"]
reloc = [d[n]["reloc_per_update"]["mean"] for n in names]
reloc_e = [d[n]["reloc_per_update"]["std"] for n in names]
writes = [d[n]["writes_per_update"]["mean"] for n in names]
verify = [d[n]["verify_per_result"]["mean"] for n in names]
cols = [NAVY, TEAL, AMBER, RED]

fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.6, 3.2))

# (a) relocations per update -- the headline (log scale)
x = np.arange(4)
axL.bar(x, reloc, yerr=reloc_e, color=cols, width=0.62, capsize=3)
axL.set_yscale("log"); axL.set_ylim(0.01, 2)
axL.set_xticks(x); axL.set_xticklabels(labels)
axL.set_ylabel("relocations per update")
axL.set_title("(a) MARI relocates ~40x less", fontsize=9.5)
for i, v in enumerate(reloc):
    axL.text(i, v*1.15, f"{v:.3f}", ha="center", fontsize=8)
axL.grid(True, axis="y", which="both", ls=":", lw=0.5, color="#ccc")

# (b) the exactness tax: structural writes/update and verifications/result
w = 0.38
axR.bar(x - w/2, writes, w, color="#5a7", label="structural writes / update")
axR.bar(x + w/2, verify, w, color="#c79", label="verifications / result")
axR.set_xticks(x); axR.set_xticklabels(labels)
axR.set_ylabel("cost")
axR.set_title("(b) Each competitor pays exactness differently", fontsize=9.0)
axR.legend(fontsize=7.6, frameon=False, loc="upper left")
for i in range(4):
    axR.text(i - w/2, writes[i]+0.12, f"{writes[i]:.1f}", ha="center", fontsize=7)
    axR.text(i + w/2, verify[i]+0.12, f"{verify[i]:.1f}", ha="center", fontsize=7)
axR.grid(True, axis="y", ls=":", lw=0.5, color="#ccc")

plt.tight_layout()
plt.savefig("fig_baseline.png", bbox_inches="tight")
print("wrote fig_baseline.png")
