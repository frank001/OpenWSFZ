#!/usr/bin/env python3
"""CS-MAP report builder: figures and markdown tables from cs_map.json (counts only), then the report from the prose template.

  <venv>\\python.exe cs_map_report.py     (matplotlib needed; reads _qa-scratch/lc-base/cs_map.json and cs_template.md)

Writes qa/rr-study/results/2026-11-26-lc-base/cs-map-figures/*.png and cs-map-result.md. The key figures quoted in the prose are asserted first.
Colour follows the entity: blue = classic (C), orange = lean (L); the heat map uses one hue, light to dark (miss share).
"""
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SC = r"D:\Projects\claude\_qa-scratch\lc-base"
RES = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\rr-study\results\2026-11-26-lc-base"
FIGS = os.path.join(RES, "cs-map-figures")
SL = ["S40", "H40", "H20"]
LABEL = {"S40": "S40: 40 m, 15 Nov", "H40": "H40: 40 m, 29 Oct", "H20": "H20: 20 m, 8 Aug"}
DF = ["<6.25", "6.25-12.5", "12.5-25", "25-50"]
DFL = {"<6.25": "< 6.25", "6.25-12.5": "6.25 to 12.5", "12.5-25": "12.5 to 25", "25-50": "25 to 50"}
DS = ["weaker>3", "within3", "stronger3-10", "stronger>10"]
DSL = {"weaker>3": "weaker by\n> 3 dB", "within3": "within\n\u00b13 dB", "stronger3-10": "stronger by\n3 to 10 dB", "stronger>10": "stronger by\n> 10 dB"}
DSL1 = {k: v.replace("\n", " ") for k, v in DSL.items()}
DT = ["<0.16", "0.16-0.5", ">0.5"]
N50 = ["1", "2", "3+"]
BLUE, ORANGE, INK, INK2, GRID, BASE = "#257de0", "#f47230", "#191919", "#666666", "#e7e7e7", "#c2c2c2"
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def save(fig, name):
    os.makedirs(FIGS, exist_ok=True)
    fig.savefig(os.path.join(FIGS, name), dpi=150, bbox_inches="tight")
    plt.close(fig)


def grouped(D, key, order, labels, name, xlabel):
    fig, axs = plt.subplots(1, 3, figsize=(11.0, 3.7), sharey=True)
    for ax, s in zip(axs, SL):
        t = D[s][key]
        x = np.arange(len(order))
        w = 0.38
        vl = [pct(t[k]["missL"], t[k]["n"]) for k in order]
        vc = [pct(t[k]["missC"], t[k]["n"]) for k in order]
        b1 = ax.bar(x - w / 2, vc, w, color=BLUE, label="Classic (C)")
        b2 = ax.bar(x + w / 2, vl, w, color=ORANGE, label="Lean (L)")
        for bars in (b1, b2):
            for b in bars:
                ax.annotate("%.0f" % b.get_height(), (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom", fontsize=7.5, xytext=(0, 2), textcoords="offset points")
        ax.set_xticks(x)
        ax.set_xticklabels(["%s\nn=%d" % (labels[k], t[k]["n"]) for k in order], fontsize=7)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, 60)
    axs[0].set_ylabel("% of crowded WSJT-X decodes NOT decoded")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8.5, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.07))
    fig.text(0.5, -0.04, xlabel, ha="center", fontsize=8.5, color=INK2)
    save(fig, name)


def fig_heat(D):
    fig, axs = plt.subplots(1, 3, figsize=(11.5, 3.6))
    for ax, s in zip(axs, SL):
        t = D[s]["dF_x_dSNR"]
        m = np.array([[pct(t.get("%s|%s" % (a, b), {"missL": 0, "n": 0})["missL"], t.get("%s|%s" % (a, b), {"n": 0})["n"]) for b in DS] for a in DF])
        n = np.array([[t.get("%s|%s" % (a, b), {"n": 0})["n"] for b in DS] for a in DF])
        im = ax.imshow(m, cmap="Blues", vmin=0, vmax=80, aspect="auto")
        for i in range(len(DF)):
            for j in range(len(DS)):
                ax.text(j, i, "%.0f %%\nn=%d" % (m[i, j], n[i, j]), ha="center", va="center", fontsize=7.5, color="white" if m[i, j] > 45 else INK)
        ax.set_xticks(range(len(DS)))
        ax.set_xticklabels([DSL[k] for k in DS], fontsize=7)
        ax.set_yticks(range(len(DF)))
        ax.set_yticklabels([DFL[k] for k in DF] if s == SL[0] else [], fontsize=8)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
    axs[0].set_ylabel("|dF| to the nearest neighbour (Hz)")
    fig.text(0.5, -0.05, "Neighbour's SNR relative to the missed signal's. Cell = share of lean's crowded decodes in that cell that lean did not decode.", ha="center", fontsize=8.5, color=INK2)
    save(fig, "cs3_heatmap_dF_dSNR_lean.png")


def fig_key(D):
    fig, ax = plt.subplots(figsize=(9.4, 3.0))
    cats = [("1", "Neighbour decoded by L in round 0", "#257de0"), ("2", "… in rounds 1 to 3", "#00b894"), ("3", "… by the cross-cycle stage", "#6a4ce2"), ("none", "Neighbour not decoded by L", "#f47230")]
    for i, s in enumerate(SL):
        k = D[s]["key"]
        tot = k["crowded_missed_by_L"]
        vals = [k["by_batch"].get("1", 0), k["by_batch"].get("2", 0), k["by_batch"].get("3", 0), tot - k["neighbour_decoded_by_L"]]
        left = 0.0
        for (cid, name, col), v in zip(cats, vals):
            w = 100.0 * v / tot
            ax.barh(i, w, left=left, color=col, edgecolor="white", linewidth=1.2, height=0.55, label=name if i == 0 else None)
            if w >= 6:
                ax.text(left + w / 2, i, "%.0f %%\n%d" % (w, v), ha="center", va="center", fontsize=8, color="#0b0b0b" if cid == "none" and False else "white")
            left += w
        base = 100.0 * sum(v["n"] for kk, v in D[s]["by_N_decoded"].items() if kk.startswith("N decoded")) / D[s]["crowded"]
        ax.plot([base, base], [i - 0.34, i + 0.34], color=INK, linewidth=1.6)
        ax.annotate("neighbour decoded for %.0f %%\nof ALL crowded signals" % base, (base, i - 0.34), ha="left", va="bottom", fontsize=7, xytext=(3, 1), textcoords="offset points", color=INK)
    ax.set_yticks(range(3))
    ax.set_yticklabels([LABEL[s] for s in SL], fontsize=8.5)
    ax.set_ylim(2.6, -0.95)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the crowded WSJT-X decodes that lean missed (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, ncol=2, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.30))
    save(fig, "cs1_key_number.png")


def mdt(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def side_table(D, key, order, labels, title):
    head = [title] + sum([["%s n" % s, "%s L miss %%" % s, "%s C miss %%" % s] for s in SL], [])
    rows = []
    for k in order:
        r = [labels[k]]
        for s in SL:
            t = D[s][key].get(k, {"n": 0, "missL": 0, "missC": 0})
            r += [t["n"], "%.1f" % pct(t["missL"], t["n"]), "%.1f" % pct(t["missC"], t["n"])]
        rows.append(r)
    r = ["**all crowded**"]
    for s in SL:
        t = D[s][key]
        n = sum(v["n"] for v in t.values())
        r += ["**%d**" % n, "**%.1f**" % pct(sum(v["missL"] for v in t.values()), n), "**%.1f**" % pct(sum(v["missC"] for v in t.values()), n)]
    rows.append(r)
    return mdt(head, rows)


def tables(D):
    T = {}
    T["TDF"] = side_table(D, "by_dF", DF, DFL, "\\|dF\\| (Hz)")
    T["TDS"] = side_table(D, "by_dSNR", DS, DSL1, "Neighbour's SNR minus T's")
    nk = ["N decoded by L, batch 1", "N decoded by L, batch 2", "N decoded by L, batch 3", "N not decoded by L"]
    T["TNL"] = side_table(D, "by_N_decoded", nk, {"N decoded by L, batch 1": "Neighbour decoded by L, round 0 (batch 1)", "N decoded by L, batch 2": "Neighbour decoded by L, rounds 1 to 3 (batch 2)",
                                                  "N decoded by L, batch 3": "Neighbour decoded by L, cross-cycle (batch 3)", "N not decoded by L": "Neighbour not decoded by L"}, "Neighbour")
    T["TDT"] = side_table(D, "by_dDT", DT, {"<0.16": "< 0.16 s", "0.16-0.5": "0.16 to 0.5 s", ">0.5": "> 0.5 s"}, "\\|dDT\\|")
    T["TN50"] = side_table(D, "by_n50", N50, {"1": "1", "2": "2", "3+": "3 or more"}, "Other WSJT-X decodes within \u00b150 Hz (n50)")
    for s in SL:
        t = D[s]["dF_x_dSNR"]
        rows = []
        for a in DF:
            rows.append([DFL[a]] + ["%d / %.1f %%" % (t.get("%s|%s" % (a, b), {"n": 0})["n"], pct(t.get("%s|%s" % (a, b), {"missL": 0})["missL"], t.get("%s|%s" % (a, b), {"n": 0})["n"])) for b in DS])
        T["T2D_" + s] = mdt(["\\|dF\\| (Hz)"] + [DSL1[b] for b in DS], rows)
    rows = []
    for s in SL:
        k = D[s]["key"]
        base = sum(v["n"] for kk, v in D[s]["by_N_decoded"].items() if kk.startswith("N decoded"))
        rows.append([s, D[s]["crowded"], k["crowded_missed_by_L"], k["neighbour_decoded_by_L"], "**%.1f %%**" % pct(k["neighbour_decoded_by_L"], k["crowded_missed_by_L"]),
                     "%d / %d / %d" % (k["by_batch"].get("1", 0), k["by_batch"].get("2", 0), k["by_batch"].get("3", 0)), "%.1f %%" % pct(base, D[s]["crowded"])])
    T["TKEY"] = mdt(["Slice", "Crowded WSJT-X decodes", "Missed by L", "of those, nearest neighbour decoded by L", "Share", "by batch 1 / 2 / 3", "For comparison: neighbour decoded by L over ALL crowded decodes"], rows)
    return T


def main():
    D = json.load(open(os.path.join(SC, "cs_map.json")))
    # ---- the prose's key numbers, asserted --------------------------------------------------------------------------------------------------------------------
    assert [D[s]["crowded"] for s in SL] == [5060, 6402, 6348] and [D[s]["wsjtx_decodes"] for s in SL] == [6773, 8983, 9154]
    assert [D[s]["key"]["crowded_missed_by_L"] for s in SL] == [1133, 1213, 1411] and [D[s]["key"]["neighbour_decoded_by_L"] for s in SL] == [789, 832, 965]
    assert [round(100 * D[s]["key"]["neighbour_decoded_by_L"] / D[s]["key"]["crowded_missed_by_L"], 1) for s in SL] == [69.6, 68.6, 68.4]
    strong = {s: sum(D[s]["by_dSNR"][k]["missL"] for k in ("stronger3-10", "stronger>10")) for s in SL}
    assert [round(100 * strong[s] / D[s]["key"]["crowded_missed_by_L"], 1) for s in SL] == [70.3, 66.7, 64.4], [round(100 * strong[s] / D[s]["key"]["crowded_missed_by_L"], 1) for s in SL]
    mp = lambda s, key, k, a: round(pct(D[s][key][k]["miss" + a], D[s][key][k]["n"]), 1)
    assert [mp("H40", "by_dF", k, "L") for k in DF] == [36.3, 18.5, 16.8, 13.1] and [mp("H20", "by_dF", k, "L") for k in DF] == [32.0, 28.4, 22.8, 15.0]
    assert [mp("S40", "by_dF", k, "L") for k in DF] == [33.1, 23.7, 24.7, 16.5]
    assert [mp(s, "by_dSNR", "weaker>3", "L") for s in SL] == [6.1, 6.4, 6.6] and [mp(s, "by_dSNR", "stronger>10", "L") for s in SL] == [51.1, 42.6, 45.3]
    assert max(abs(mp(s, "by_dF", k, "L") - mp(s, "by_dF", k, "C")) for s in ("H40", "H20") for k in DF) < 2.85
    assert max(abs(mp(s, "by_dSNR", k, "L") - mp(s, "by_dSNR", k, "C")) for s in ("H40", "H20") for k in DS) < 6.5
    assert [round(pct(sum(D[s]["dF_x_dSNR"][a + "|" + b]["missL"] for a in DF[:2] for b in DS[2:]), D[s]["key"]["crowded_missed_by_L"]), 1) for s in SL] == [32.7, 32.2, 33.2]
    assert [round(pct(sum(D[s]["key"]["nbr_decoded_by_dSNR"][k] for k in ("stronger3-10", "stronger>10")), D[s]["key"]["neighbour_decoded_by_L"]), 1) for s in SL] == [86.6, 80.9, 79.5]
    for f in (lambda: grouped(D, "by_dF", DF, DFL, "cs2_miss_by_dF.png", "|dF| to the nearest WSJT-X neighbour (Hz); crowded signals only"),
              lambda: grouped(D, "by_dSNR", DS, DSL, "cs2_miss_by_dSNR.png", "Neighbour's SNR relative to the missed signal's; crowded signals only"), lambda: fig_heat(D), lambda: fig_key(D)):
        f()
    T = tables(D)
    text = open(os.path.join(SC, "cs_template.md"), encoding="utf-8").read()
    for key in re.findall(r"\{\{(\w+)\}\}", text):
        assert key in T, key
        text = text.replace("{{%s}}" % key, T[key])
    open(os.path.join(RES, "cs-map-result.md"), "w", encoding="utf-8", newline="\n").write(text)
    json.dump(D, open(os.path.join(RES, "cs_map.json"), "w"))
    print("written")


if __name__ == "__main__":
    main()
