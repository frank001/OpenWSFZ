#!/usr/bin/env python3
"""SUB-PROBE report builder: figures (PNG) and markdown tables from the analysis JSONs, then the report from the prose template. Aggregates only.

  <venv>\\python.exe sub_probe_report.py     (needs sub_probe_probe.json from sub_probe_analyze.py, cs_map_probe.json from cs_map.py with CS_MAP_TAG=probe, and the arm.json files)

Writes qa/rr-study/results/2026-11-26-lc-base/subprobe-figures/*.png and sub-probe-result.md (from _qa-scratch/lc-base/sp_template.md). Key numbers quoted in the prose are asserted first.
Colour: blue = classic, orange = lean (as in LC-BASE); the lean-post-DR-3 bar is the darker orange; the K classes use the reference palette slots in fixed order.
"""
import importlib.util
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SC = r"D:\Projects\claude\_qa-scratch\lc-base"
RES = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\rr-study\results\2026-11-26-lc-base"
FIGS = os.path.join(RES, "subprobe-figures")
SL = ["S40", "H40", "H20"]
LABEL = {"S40": "S40: 40 m, 15 Nov", "H40": "H40: 40 m, 29 Oct", "H20": "H20: 20 m, 8 Aug"}
BLUE, ORANGE, DORANGE, INK, INK2, GRID, BASE = "#257de0", "#f9b48f", "#f47230", "#191919", "#666666", "#e7e7e7", "#c2c2c2"
KC = {"K0": "#6a4ce2", "K1": "#00b894", "K2": "#257de0", "K3": "#f2a600", "K4": "#f47230"}
KNAME = {"K0": "K0 published something else there", "K1": "K1 decoded, then dropped", "K2": "K2 tried, decoding failed", "K3": "K3 found, not kept (search)", "K4": "K4 not found"}
DS = ["weaker>3", "within3", "stronger3-10", "stronger>10"]
DSL = {"weaker>3": "weaker by > 3 dB", "within3": "within \u00b13 dB", "stronger3-10": "stronger by 3 to 10 dB", "stronger>10": "stronger by > 10 dB"}
BANDS = ["ge-10", "-10..-15", "-15..-18", "-18..-21", "lt-21"]
BL = {"ge-10": "\u2265 \u221210", "-10..-15": "\u221210 to \u221215", "-15..-18": "\u221215 to \u221218", "-18..-21": "\u221218 to \u221221", "lt-21": "< \u221221"}
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": BASE, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})
RUNS = SC + r"\runs"


def arm(path):
    return json.load(open(os.path.join(path, "arm.json")))


def baseline():
    """rate rows: classic C, lean before DR-3, lean after DR-3 (the probe run)."""
    n = {"S40": 170, "H40": 240, "H20": 240}
    D = {}
    D["S40"] = {"C": arm(r"D:\Projects\claude\_qa-scratch\dr0\full_A6_n170"), "L0": arm(r"D:\Projects\claude\_qa-scratch\dr2e\threads16_L5_n170"), "L1": arm(RUNS + r"\probe_S40_L_n170")}
    for s in ("H40", "H20"):
        D[s] = {"C": arm(RUNS + r"\full_%s_C_n240" % s), "L0": arm(RUNS + r"\full_%s_L_n240" % s), "L1": arm(RUNS + r"\probe_%s_L_n240" % s)}
    return D


def save(fig, name):
    os.makedirs(FIGS, exist_ok=True)
    fig.savefig(os.path.join(FIGS, name), dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_baseline(B):
    fig, ax = plt.subplots(figsize=(9.2, 3.8))
    x = np.arange(3)
    w = 0.26
    for k, (key, col, name) in enumerate((("C", BLUE, "Classic"), ("L0", ORANGE, "Lean before DR-3"), ("L1", DORANGE, "Lean with DR-3"))):
        v = [B[s][key]["rate_pct"] for s in SL]
        bars = ax.bar(x + (k - 1) * w, v, w, color=col, label=name)
        for b in bars:
            ax.annotate("%.1f" % b.get_height(), (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom", fontsize=8, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL[s] for s in SL])
    ax.set_ylim(70, 90)
    ax.set_ylabel("% of WSJT-X decodes decoded (axis starts at 70)")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.13), fontsize=8.5)
    save(fig, "sp1_baseline.png")


def fig_classes(A):
    fig, ax = plt.subplots(figsize=(9.2, 3.2))
    for i, s in enumerate(SL):
        c = A[s]["counts"]
        tot = A[s]["classified"]
        left = 0.0
        for k in ("K0", "K1", "K2", "K3", "K4"):
            v = 100.0 * c[k] / tot
            ax.barh(i, v, left=left, color=KC[k], edgecolor="white", linewidth=1.2, height=0.55, label=KNAME[k] if i == 0 else None)
            if v >= 5:
                ax.text(left + v / 2, i, "%.0f %%\n%d" % (v, c[k]), ha="center", va="center", fontsize=8, color="#0b0b0b" if k in ("K3",) else "white")
            left += v
    ax.set_yticks(range(3))
    ax.set_yticklabels([LABEL[s] for s in SL], fontsize=8.5)
    ax.set_ylim(2.6, -0.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the crowded WSJT-X decodes that lean missed although it decoded their nearest neighbour (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, ncol=3, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.28))
    save(fig, "sp2_classes.png")


def fig_by_dsnr(A):
    fig, axs = plt.subplots(1, 3, figsize=(11.0, 3.6), sharey=True)
    for ax, s in zip(axs, SL):
        bd = A[s]["by_dsnr"]
        x = np.arange(len(DS))
        bottom = np.zeros(len(DS))
        for k in ("K0", "K1", "K2", "K3", "K4"):
            v = np.array([bd.get(k, {}).get(d, 0) for d in DS], dtype=float)
            ax.bar(x, v, 0.6, bottom=bottom, color=KC[k], edgecolor="white", linewidth=0.8, label=KNAME[k] if s == SL[0] else None)
            bottom += v
        for xi, t in zip(x, bottom):
            ax.annotate("%d" % t, (xi, t), ha="center", va="bottom", fontsize=8, xytext=(0, 2), textcoords="offset points")
        ax.set_xticks(x)
        ax.set_xticklabels([DSL[d].replace(" by ", "\n").replace("within", "within\n") for d in DS], fontsize=7)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("number of missed signals")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, ncol=3, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.08))
    fig.text(0.5, -0.05, "The neighbour's SNR relative to the missed signal's", ha="center", fontsize=8.5, color=INK2)
    save(fig, "sp3_classes_by_dSNR.png")


def fig_supp(A):
    fig, axs = plt.subplots(1, 3, figsize=(11.0, 3.4), sharey=True)
    for ax, s in zip(axs, SL):
        ns = A[s]["n_supp"]
        ks = [k for k in ("K0", "K1", "K2", "K3", "K4") if ns.get(k)]
        for i, k in enumerate(ks):
            q = ns[k]
            ax.barh(i, q["q3"] - q["q1"], left=q["q1"], color=KC[k], height=0.5)
            ax.plot([q["median"]] * 2, [i - 0.25, i + 0.25], color="white", linewidth=2)
            ax.annotate("median %.1f dB (n=%d)" % (q["median"], q["n"]), (q["q3"], i), ha="left", va="center", fontsize=7.5, xytext=(4, 0), textcoords="offset points")
        ax.set_yticks(range(len(ks)))
        ax.set_yticklabels(ks, fontsize=8.5)
        ax.set_ylim(len(ks) - 0.5, -0.7)
        ax.set_xlim(0, 28)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="y", visible=False)
    fig.text(0.5, -0.04, "How far the strong neighbour was suppressed when lean subtracted it (dB): bar = quartiles, white tick = median", ha="center", fontsize=8.5, color=INK2)
    save(fig, "sp4_neighbour_suppression.png")


def fig_supp_band(A):
    fig, axs = plt.subplots(1, 3, figsize=(11.0, 3.4), sharey=True)
    for ax, s in zip(axs, SL):
        sb = A[s]["sub_by_snr_band"]
        ks = [b for b in BANDS if sb.get(b)]
        for i, b in enumerate(ks):
            q = sb[b]
            ax.barh(i, q["q3"] - q["q1"], left=q["q1"], color=DORANGE, height=0.5)
            ax.plot([q["median"]] * 2, [i - 0.25, i + 0.25], color="white", linewidth=2)
            ax.annotate("median %.1f dB (n=%d)" % (q["median"], q["n"]), (q["q3"], i), ha="left", va="center", fontsize=7.5, xytext=(4, 0), textcoords="offset points")
        ax.set_yticks(range(len(ks)))
        ax.set_yticklabels([BL[b] for b in ks], fontsize=8)
        ax.set_ylim(len(ks) - 0.5, -0.7)
        ax.set_xlim(0, 30)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="y", visible=False)
    axs[0].set_ylabel("WSJT-X SNR of the subtracted signal (dB)")
    fig.text(0.5, -0.04, "Suppression of every subtracted signal that matches a WSJT-X decode (dB): bar = quartiles, white tick = median", ha="center", fontsize=8.5, color=INK2)
    save(fig, "sp5_suppression_by_snr.png")


def fig_gap(A):
    fig, axs = plt.subplots(1, 3, figsize=(11.0, 3.4), sharey=True)
    for ax, s in zip(axs, SL):
        g = A[s]["gap_by_snr_band"]
        ks = [b for b in BANDS if g.get(b)]
        for i, b in enumerate(ks):
            q = g[b]
            ax.barh(i, q["q3"] - q["q1"], left=q["q1"], color=DORANGE, height=0.5)
            ax.plot([q["median"]] * 2, [i - 0.25, i + 0.25], color="white", linewidth=2)
            ax.annotate("median %+.1f dB (n=%d)" % (q["median"], q["n"]), (max(q["q3"], 0), i), ha="left", va="center", fontsize=7.5, xytext=(4, 0), textcoords="offset points")
        ax.axvline(0, color=INK2, linewidth=0.9)
        ax.set_yticks(range(len(ks)))
        ax.set_yticklabels([BL[b] for b in ks], fontsize=8)
        ax.set_ylim(len(ks) - 0.5, -0.7)
        ax.set_xlim(-6, 22)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="y", visible=False)
    axs[0].set_ylabel("WSJT-X SNR of the subtracted signal (dB)")
    fig.text(0.5, -0.05, "Gap to the noise ceiling (dB): how far short of a perfect subtraction (the most the noise allows) the measured suppression is. 0 = at the ceiling.\nBar = quartiles, white tick = median. The ceiling is an approximation good to about ±2.5 dB (the bands below −10 dB sit at 0 ± 2.5 dB: no room).", ha="center", fontsize=8, color=INK2)
    save(fig, "sp6_gap_to_ceiling.png")


def mdt(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def tables(B, A, CM):
    T = {}
    rows = []
    for s in SL:
        for key, name in (("C", "classic (C)"), ("L0", "lean before DR-3"), ("L1", "**lean with DR-3 (probe run)**")):
            x = B[s][key]
            rows.append([s if key == "C" else "", name, x["cycles"] if key == "C" else "", x["wsjtx_decodes"], x["matched"], x["ours"], "%.2f" % x["rate_pct"], "%.2f" % x["ours_only_pct"]])
        c, l0, l1 = B[s]["C"], B[s]["L0"], B[s]["L1"]
        rows.append(["", "**DR-3 effect on lean**", "", "", l1["matched"] - l0["matched"], l1["ours"] - l0["ours"], "**%+.2f pp**" % (l1["rate_pct"] - l0["rate_pct"]), "%+.2f pp" % (l1["ours_only_pct"] - l0["ours_only_pct"])])
        rows.append(["", "**lean with DR-3 minus classic**", "", "", l1["matched"] - c["matched"], l1["ours"] - c["ours"], "**%+.2f pp**" % (l1["rate_pct"] - c["rate_pct"]), "%+.2f pp" % (l1["ours_only_pct"] - c["ours_only_pct"])])
    T["TBASE"] = mdt(["Slice", "Arm", "Cycles", "WSJT-X decodes", "matched", "ours", "rate %", "ours_only %"], rows)
    rows = []
    for s in SL:
        a, b = B[s]["L1"], B[s]["L0"]
        rows.append([s, "%.2f" % a["cpu_s_per_cycle"], "{:,}".format(a["last_p95_ms"]), a["abandoned_cycles"], a.get("lean_error_cycles", 0), "%.2f" % b["cpu_s_per_cycle"], "{:,}".format(b["last_p95_ms"])])
    T["TCOST"] = mdt(["Slice", "Probe run CPU (CPU-s per cycle)", "Probe run last_p95 (ms)", "abandoned", "native errors", "Lean before DR-3: CPU", "last_p95 (ms)"], rows)
    rows = []
    for s in SL:
        a = A[s]
        r = [s, a["crowded_missed_by_L"], a["classified"]]
        for k in ("K0", "K1", "K2", "K3", "K4"):
            r.append("%d (%.1f %%)" % (a["counts"][k], 100.0 * a["counts"][k] / a["classified"]))
        rows.append(r)
    T["TK"] = mdt(["Slice", "Crowded WSJT-X decodes missed by lean", "of those, neighbour decoded by lean (classified)", "K0", "K1", "K2", "K3", "K4"], rows)
    for s in SL:
        rows = []
        for k in ("K0", "K1", "K2", "K3", "K4"):
            r = [KNAME[k]] + [A[s]["by_dsnr"].get(k, {}).get(d, 0) for d in DS] + [A[s]["counts"][k]]
            rows.append(r)
        T["TKD_" + s] = mdt(["Class"] + [DSL[d] for d in DS] + ["all"], rows)
    rows = []
    for s in SL:
        for k in ("K0", "K1", "K2", "K3", "K4"):
            q = A[s]["n_supp"].get(k)
            rows.append([s if k == "K0" else "", k, A[s]["counts"][k], A[s]["n_not_subtracted"][k], A[s]["n_supp_not_measured"][k],
                         "%d / %.1f / %.1f / %.1f" % (q["n"], q["q1"], q["median"], q["q3"]) if q else ""])
    T["TSUPP"] = mdt(["Slice", "Class", "classified", "neighbour not subtracted (no SUB row)", "suppression not measured", "neighbour suppression dB: n / Q1 / median / Q3"], rows)
    rows = []
    for s in SL:
        sb = A[s]["sub_by_snr_band"]
        r = [s, "%d / %.1f / %.1f / %.1f" % (A[s]["sub_all"]["n"], A[s]["sub_all"]["q1"], A[s]["sub_all"]["median"], A[s]["sub_all"]["q3"])]
        for b in BANDS:
            q = sb.get(b)
            r.append("%d / %.1f / %.1f / %.1f" % (q["n"], q["q1"], q["median"], q["q3"]) if q else "")
        rows.append(r)
    T["TSUBALL"] = mdt(["Slice", "All subtracted signals"] + [BL[b] for b in BANDS], rows)
    rows = []
    for s in SL:
        for k in ("K2", "K1", "K0", "K3", "K4"):
            c, m, g = A[s]["n_ceiling"].get(k), A[s]["n_supp"].get(k), A[s]["n_gap_to_ceiling"].get(k)
            if c and m and g:
                rows.append([s if k == "K2" else "", k, m["n"], "%.1f" % c["median"], "%.1f" % m["median"], "%.1f / %.1f / %.1f" % (g["q1"], g["median"], g["q3"])])
    T["TGAPK"] = mdt(["Slice", "Class", "neighbours subtracted (n)", "ceiling, median (dB)", "measured suppression, median (dB)", "gap to the ceiling: Q1 / median / Q3 (dB)"], rows)
    rows = []
    for s in SL:
        r = [s]
        for b in BANDS:
            g = A[s]["gap_by_snr_band"].get(b)
            r.append("%+.1f / %+.1f / %+.1f" % (g["q1"], g["median"], g["q3"]) if g else "")
        rows.append(r)
    T["TGAPB"] = mdt(["Slice"] + [BL[b] for b in BANDS], rows)
    rows = []
    for s in SL:
        q = A[s]["k2_unsat_best"]
        rows.append([s, A[s]["counts"]["K2"], "%d / %d / %d / %d" % (q["n"], q["q1"], q["median"], q["q3"]) if q else ""])
    T["TUNSAT"] = mdt(["Slice", "K2 signals", "Unsatisfied parity checks of the best failed attempt: n / Q1 / median / Q3"], rows)
    return T


def main():
    A = json.load(open(os.path.join(SC, "sub_probe_probe.json")))
    CM = json.load(open(os.path.join(SC, "cs_map_probe.json")))
    B = baseline()
    assert set(A) == set(SL) and set(CM) == set(SL)
    for s in SL:                                                                 # the probe must not have changed what was published: S40 equals the DR-3 run
        assert A[s]["overflow_cycles"] == 0, (s, "overflow")
    assert (B["S40"]["L1"]["matched"], B["S40"]["L1"]["ours"]) == (5737, 6009)
    # the prose's key numbers, asserted
    assert [round(B[s]["L1"]["rate_pct"] - B[s]["L0"]["rate_pct"], 2) for s in SL] == [3.19, 2.0, 0.85]
    assert [round(B[s]["L1"]["rate_pct"] - B[s]["C"]["rate_pct"], 2) for s in SL] == [0.31, 0.98, 1.63]
    assert [A[s]["counts"]["K2"] for s in SL] == [436, 495, 686] and [A[s]["classified"] for s in SL] == [667, 696, 914]
    assert [round(100.0 * A[s]["counts"]["K2"] / A[s]["classified"], 1) for s in SL] == [65.4, 71.1, 75.1]
    assert [round(100.0 * A[s]["counts"]["K4"] / A[s]["classified"], 1) for s in SL] == [6.4, 5.5, 6.1]
    assert [A[s]["n_supp"]["K2"]["median"] for s in SL] == [6.8, 6.3, 6.5] and [A[s]["sub_all"]["median"] for s in SL] == [8.0, 6.5, 6.5]
    assert [A[s]["n_not_subtracted"]["K2"] for s in SL] == [157, 105, 266] and [A[s]["n_not_subtracted_by_batch"]["K2"]["1"] for s in SL] == [110, 36, 143]
    assert [A[s]["k2_round0_neighbour_never_subtracted"]["with_round0_candidate"] for s in SL] == [91, 28, 124]
    assert [A[s]["k2_unsat_best"]["median"] for s in SL] == [5, 5, 6]
    assert [CM[s]["key"]["crowded_missed_by_L"] for s in SL] == [925, 1046, 1336] and [CM[s]["key"]["neighbour_decoded_by_L"] for s in SL] == [667, 696, 914]
    assert [A[s]["n_gap_to_ceiling"]["K2"]["median"] for s in SL] == [5.5, 3.9, 4.2] and [A[s]["n_gap_to_ceiling"]["K2"]["q3"] for s in SL] == [10.7, 8.2, 8.6]
    assert [A[s]["gap_by_snr_band"]["ge-10"]["median"] for s in SL] == [5.8, 5.7, 4.8]
    assert all(abs(A[s]["gap_by_snr_band"][b]["median"]) <= 2.5 for s in SL for b in ("-10..-15", "-15..-18", "-18..-21", "lt-21"))
    for f in (lambda: fig_baseline(B), lambda: fig_classes(A), lambda: fig_by_dsnr(A), lambda: fig_supp(A), lambda: fig_supp_band(A), lambda: fig_gap(A)):
        f()
    T = tables(B, A, CM)
    spec = importlib.util.spec_from_file_location("cmr", r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\decoder-rebuild\cs_map_report.py")
    cmr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cmr)
    CT = cmr.tables(CM)
    T["TCSKEY"], T["TCSDF"], T["TCSDS"], T["TCSNL"] = CT["TKEY"], CT["TDF"], CT["TDS"], CT["TNL"]
    tp = os.path.join(SC, "sp_template.md")
    if os.path.exists(tp):
        text = open(tp, encoding="utf-8").read()
        for key in re.findall(r"\{\{(\w+)\}\}", text):
            assert key in T, key
            text = text.replace("{{%s}}" % key, T[key])
        open(os.path.join(RES, "sub-probe-result.md"), "w", encoding="utf-8", newline="\n").write(text)
    json.dump(T, open(os.path.join(SC, "sp_tables.json"), "w"), indent=1)
    print("figures and tables written")


if __name__ == "__main__":
    main()
