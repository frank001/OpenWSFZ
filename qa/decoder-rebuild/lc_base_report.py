#!/usr/bin/env python3
"""LC-BASE report builder: figures (PNG) and markdown tables from the score files. Aggregates only (HK-037); reads no per-row files.

  <venv>\\python.exe lc_base_report.py            (needs matplotlib; reads _qa-scratch/lc-base/score_{reuse_S40,full_H40,full_H20}.json)

Writes qa/decoder-rebuild/lc-base/fig*.png and _qa-scratch/lc-base/tables.json (markdown fragments keyed T1..T7 for the report template).
Colour follows the entity: blue = classic (arm C), orange = lean (arm L), grey = found by both. Palette checked with the dataviz validator
(2 slots: worst CVD dE 26.6, normal-vision dE 35.2; orange is 2.88:1 on white, so every bar carries a direct value label and every figure has a table).
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SC = r"D:\Projects\claude\_qa-scratch\lc-base"
OUT = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\rr-study\results\2026-11-26-lc-base\figures"
FILES = [("S40", "score_reuse_S40.json"), ("H40", "score_full_H40.json"), ("H20", "score_full_H20.json")]
LABEL = {"S40": "S40: 40 m, 15 Nov", "H40": "H40: 40 m, 29 Oct", "H20": "H20: 20 m, 8 Aug"}
BANDS = ["ge-10", "-10..-15", "-15..-18", "-18..-21", "lt-21"]
BAND_LABEL = {"ge-10": "\u2265 \u221210", "-10..-15": "\u221210 to \u221215", "-15..-18": "\u221215 to \u221218", "-18..-21": "\u221218 to \u221221", "lt-21": "< \u221221"}

BAND_SHORT = {"ge-10": "≥ −10", "-10..-15": "−10 to\n−15", "-15..-18": "−15 to\n−18", "-18..-21": "−18 to\n−21", "lt-21": "< −21"}
BLUE, ORANGE, GREY, GRID, INK, INK2, BASE ="#257de0", "#f47230", "#9c9c9c", "#e7e7e7", "#191919", "#666666", "#c2c2c2"
CAT = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2"]       # reference palette slots 1 to 7 (fixed order)

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": BASE,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white", "hatch.linewidth": 0.8})


def load():
    return {k: json.load(open(os.path.join(SC, f))) for k, f in FILES}


def cell(d, band, crowd):
    return d["cells"].get("%s|%s" % (band, crowd), {"both": 0, "c_only": 0, "l_only": 0, "neither": 0})


def band_totals(d, band):
    out = {"both": 0, "c_only": 0, "l_only": 0, "neither": 0}
    for crowd in ("alone", "crowded"):
        for k, v in cell(d, band, crowd).items():
            out[k] += v
    return out


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name), dpi=150, bbox_inches="tight")
    plt.close(fig)


def bar_labels(ax, bars, fmt="{:.1f}", dy=0.0, color=INK):
    for b in bars:
        h = b.get_height()
        if np.isnan(h):
            continue
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), ha="center", va="bottom", fontsize=8, color=color, xytext=(0, 2 + dy), textcoords="offset points")


def fig_headline(D):
    fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for ax, key, title, fmt in ((axs[0], "rate_pct", "Decoded WSJT-X decodes (%)", "{:.1f}"), (axs[1], "ours_only_pct", "Decodes WSJT-X did not corroborate (% of WSJT-X count)", "{:.2f}")):
        x = np.arange(3)
        w = 0.36
        vc = [D[s]["arm"]["C"][key] for s, _ in FILES]
        vl = [D[s]["arm"]["L"][key] for s, _ in FILES]
        b1 = ax.bar(x - w / 2, vc, w, color=BLUE, label="Classic (C)")
        b2 = ax.bar(x + w / 2, vl, w, color=ORANGE, label="Lean (L)")
        bar_labels(ax, b1, fmt)
        bar_labels(ax, b2, fmt)
        ax.set_xticks(x)
        ax.set_xticklabels([LABEL[s] for s, _ in FILES], fontsize=8)
        ax.set_title(title, fontsize=9.5, loc="left", color=INK)
        ax.set_ylim(0, max(vc + vl) * 1.18)
        ax.grid(axis="x", visible=False)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8.5, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.07))
    save(fig, "fig1_headline.png")


def fig_cost(D):
    fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for ax, key, title, fmt, div in ((axs[0], "cpu_s_per_cycle", "CPU per cycle (s)", "{:.1f}", 1.0), (axs[1], "last_p95_ms", "Last batch, p95 over cycles (s)", "{:.1f}", 1000.0)):
        x = np.arange(3)
        w = 0.36
        vc = [D[s]["arm"]["C"][key] / div for s, _ in FILES]
        vl = [D[s]["arm"]["L"][key] / div for s, _ in FILES]
        b1 = ax.bar(x - w / 2, vc, w, color=BLUE, label="Classic (C), 8 threads")
        b2 = ax.bar(x + w / 2, vl, w, color=ORANGE, label="Lean (L), 16 threads")
        bar_labels(ax, b1, fmt)
        bar_labels(ax, b2, fmt)
        ax.set_xticks(x)
        ax.set_xticklabels([LABEL[s] for s, _ in FILES], fontsize=8)
        ax.set_title(title, fontsize=9.5, loc="left", color=INK)
        ax.set_ylim(0, max(vc + vl) * 1.18)
        ax.grid(axis="x", visible=False)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8.5, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.07))
    save(fig, "fig2_cost.png")


def fig_overlap(D):
    fig, ax = plt.subplots(figsize=(9.2, 2.9))
    cats = [("both", "Found by both", GREY), ("c_only", "Classic only", BLUE), ("l_only", "Lean only", ORANGE), ("neither", "Neither", "white")]
    for i, (s, _) in enumerate(FILES):
        d = D[s]["overlap"]
        n = sum(d.values())
        left = 0.0
        for k, name, col in cats:
            v = 100.0 * d[k] / n
            ax.barh(i, v, left=left, color=col, edgecolor="white" if k != "neither" else BASE, linewidth=1.2 if k != "neither" else 0.8, height=0.55,
                    label=name if i == 0 else None)
            if v >= 9:
                ax.text(left + v / 2, i, "%.1f %%\n%d" % (v, d[k]), ha="center", va="center", fontsize=8, color="white" if k in ("c_only", "l_only") else INK)
            else:
                up = 0.33 if k == "c_only" else 0.62                          # narrow segment: label above the bar; the two neighbours at different heights
                ax.annotate("%.1f %% (%d)" % (v, d[k]), (left + v / 2, i - 0.275), (left + v / 2, i - up - 0.05), ha="center", va="bottom", fontsize=7.5, color=INK,
                            arrowprops={"arrowstyle": "-", "color": col if col != "white" else INK2, "linewidth": 0.8})
            left += v
    ax.set_yticks(range(3))
    ax.set_yticklabels([LABEL[s] for s, _ in FILES], fontsize=8.5)
    ax.set_ylim(2.6, -1.0)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the WSJT-X decodes in the slice (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    save(fig, "fig3_overlap.png")


def fig_snr(D):
    fig, axs = plt.subplots(1, 3, figsize=(11.5, 3.9), sharey=True)
    for ax, (s, _) in zip(axs, FILES):
        d = D[s]
        x = np.arange(len(BANDS))
        w = 0.38
        rc, rl, ns = [], [], []
        for b in BANDS:
            t = band_totals(d, b)
            n = sum(t.values())
            ns.append(n)
            rc.append(pct(t["both"] + t["c_only"], n))
            rl.append(pct(t["both"] + t["l_only"], n))
        b1 = ax.bar(x - w / 2, rc, w, color=BLUE, label="Classic (C)")
        b2 = ax.bar(x + w / 2, rl, w, color=ORANGE, label="Lean (L)")
        bar_labels(ax, b1, "{:.0f}")
        bar_labels(ax, b2, "{:.0f}")
        ax.set_xticks(x)
        ax.set_xticklabels(["%s\nn=%d" % (BAND_SHORT[b], n) for b, n in zip(BANDS, ns)], fontsize=7)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.set_ylim(0, 112)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("% of WSJT-X decodes decoded")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8.5, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.06))
    fig.text(0.5, -0.04, "WSJT-X's own SNR band (dB); n = WSJT-X decodes in the band", ha="center", fontsize=8.5, color=INK2)
    save(fig, "fig4_rate_by_snr.png")


def fig_crowding(D):
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.8), sharey=True)
    for ax, (s, _) in zip(axs, FILES):
        d = D[s]
        x = np.arange(len(BANDS))
        w = 0.2
        for j, (arm, col, hatch, crowd) in enumerate((("C", BLUE, None, "alone"), ("C", BLUE, "////", "crowded"), ("L", ORANGE, None, "alone"), ("L", ORANGE, "////", "crowded"))):
            vals = []
            for b in BANDS:
                c = cell(d, b, crowd)
                n = sum(c.values())
                found = c["both"] + (c["c_only"] if arm == "C" else c["l_only"])
                vals.append(pct(n - found, n) if n >= 10 else float("nan"))
            bars = ax.bar(x + (j - 1.5) * w, vals, w, color=col, hatch=hatch, edgecolor="white" if hatch is None else "white", linewidth=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels([BAND_SHORT[b] for b in BANDS], fontsize=7)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("% of WSJT-X decodes NOT decoded")
    from matplotlib.patches import Patch
    axs[0].legend(handles=[Patch(color=BLUE, label="C, alone"), Patch(facecolor=BLUE, hatch="////", edgecolor="white", label="C, crowded"),
                           Patch(color=ORANGE, label="L, alone"), Patch(facecolor=ORANGE, hatch="////", edgecolor="white", label="L, crowded")],
                  frameon=False, fontsize=7.5, loc="upper left")
    fig.text(0.5, -0.05, "WSJT-X's own SNR (dB); crowded = another WSJT-X decode within \u00b150 Hz in the same cycle (cells under 10 decodes left blank)", ha="center", fontsize=8, color=INK2)
    save(fig, "fig5_miss_by_snr_and_crowding.png")


L_ORIGIN = [("1/0/0", "Round 0, tier A"), ("1/0/1", "Round 0, CQ-AP"), ("1/2/0", "Round 0, tier B"), ("2/0/0", "Rounds 1-3, tier A"), ("2/0/1", "Rounds 1-3, CQ-AP"), ("2/2/0", "Rounds 1-3, tier B"), ("3/3/0", "Cross-cycle (XC)")]
C_ORIGIN = [("1", "Primary (pass 0)"), ("2", "Residual pass"), ("3", "Third pass (Deep)"), ("4", "Coherent fallback"), ("5", "Late round"), ("6", "Cross-cycle (XC)")]


def l_origin_counts(d):
    o = d["origin_kind_path_ap"]["L"]
    known = {k for k, _ in L_ORIGIN}
    out = {k: o.get(k, 0) for k, _ in L_ORIGIN}
    out["other"] = sum(v for k, v in o.items() if k not in known)
    return out


def fig_origin(D):
    fig, axs = plt.subplots(1, 2, figsize=(10.0, 3.6))
    for ax, arm, spec in ((axs[0], "C", C_ORIGIN), (axs[1], "L", L_ORIGIN)):
        for i, (s, _) in enumerate(FILES):
            d = D[s]
            if arm == "C":
                counts = [d["matched_by_batch_kind"]["C"].get(k, 0) for k, _ in spec]
            else:
                oc = l_origin_counts(d)
                counts = [oc[k] for k, _ in spec]
            tot = sum(counts)
            left = 0.0
            for j, v in enumerate(counts):
                w = 100.0 * v / tot
                ax.barh(i, w, left=left, color=CAT[j], edgecolor="white", linewidth=1.2, height=0.55, label=spec[j][1] if i == 0 else None)
                if w >= 4:
                    ax.text(left + w / 2, i, "%.0f" % w, ha="center", va="center", fontsize=8, color="#0b0b0b" if j in (2, 3, 4) else "white")
                left += w
        ax.set_yticks(range(3))
        ax.set_yticklabels([s for s, _ in FILES], fontsize=8.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("% of this arm's corroborated decodes")
        ax.set_title("Classic (C): by pass" if arm == "C" else "Lean (L): by round and tier", fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="y", visible=False)
        ax.legend(frameon=False, fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    save(fig, "fig6_origin.png")


def fig_ours_only(D):
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.6), sharey=True)
    for ax, (s, _) in zip(axs, FILES):
        d = D[s]
        x = np.arange(len(BANDS))
        w = 0.38
        for j, (arm, col) in enumerate((("C", BLUE), ("L", ORANGE))):
            cells = d["ours_only"][arm]["cells"]
            alone = [cells.get("%s|alone" % b, 0) for b in BANDS]
            crowd = [cells.get("%s|crowded" % b, 0) for b in BANDS]
            ax.bar(x + (j - 0.5) * w, alone, w, color=col, edgecolor="white", linewidth=0.6)
            ax.bar(x + (j - 0.5) * w, crowd, w, bottom=alone, color=col, hatch="////", edgecolor="white", linewidth=0.6)
            for xi, a, c in zip(x, alone, crowd):
                ax.annotate("%d" % (a + c), (xi + (j - 0.5) * w, a + c), ha="center", va="bottom", fontsize=7, xytext=(0, 1.5), textcoords="offset points")
        ax.set_xticks(x)
        ax.set_xticklabels([BAND_SHORT[b] for b in BANDS], fontsize=7)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("decodes WSJT-X did not corroborate (count)")
    from matplotlib.patches import Patch
    axs[0].legend(handles=[Patch(color=BLUE, label="C"), Patch(color=ORANGE, label="L"), Patch(facecolor="white", edgecolor=INK2, label="solid: no WSJT-X decode within \u00b150 Hz"),
                           Patch(facecolor="white", hatch="////", edgecolor=INK2, label="hatched: a WSJT-X decode within \u00b150 Hz")], frameon=False, fontsize=7, loc="upper right")
    fig.text(0.5, -0.05, "OpenWSFZ's own SNR estimate for the decode (dB)", ha="center", fontsize=8, color=INK2)
    save(fig, "fig7_ours_only.png")


def fig_latency(D):
    fig, axs = plt.subplots(1, 3, figsize=(10.0, 3.4), sharey=True)
    for ax, (s, _) in zip(axs, FILES):
        d = D[s]
        data, cols = [], []
        for arm, col in (("C", BLUE), ("L", ORANGE)):
            data.append([v / 1000.0 for v in d["last_ms"][arm].values() if v >= 0])
            cols.append(col)
        bp = ax.boxplot(data, widths=0.5, patch_artist=True, showfliers=False, medianprops={"color": "white", "linewidth": 1.6},
                        whiskerprops={"color": INK2}, capprops={"color": INK2})
        for patch, col in zip(bp["boxes"], cols):
            patch.set_facecolor(col)
            patch.set_edgecolor(col)
        for i, v in enumerate(data):
            ax.annotate("median %.1f s\np95 %.1f s" % (np.median(v), np.percentile(v, 95)), (i + 1, max(v)), ha="center", va="bottom", fontsize=7.5, xytext=(0, 4), textcoords="offset points")
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Classic (C)\n8 threads", "Lean (L)\n16 threads"], fontsize=8)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, 11)
    axs[0].set_ylabel("last batch published, seconds after the decode starts")
    save(fig, "fig8_latency.png")


def fig_cycle_gap(D):
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.6), sharey=True)
    for ax, (s, _) in zip(axs, FILES):
        pc = D[s]["per_cycle"]
        w = np.array([v["w"] for v in pc.values()])
        gap = np.array([v["l"] - v["c"] for v in pc.values()])
        order = np.argsort(w, kind="stable")
        quarters = np.array_split(order, 4)                                    # four equal groups of cycles, quietest to busiest
        means = [gap[q].mean() for q in quarters]
        sems = [gap[q].std(ddof=1) / np.sqrt(len(q)) for q in quarters]
        bars = ax.bar(range(4), means, 0.55, color=[ORANGE if m >= 0 else BLUE for m in means], yerr=sems, error_kw={"ecolor": INK2, "elinewidth": 0.9, "capsize": 3})
        for xi, m, e in zip(range(4), means, sems):
            ax.annotate("%+.2f" % m, (xi, m), ha="center", va="bottom" if m >= 0 else "top", fontsize=8, xytext=(0, 5 if m >= 0 else -5), textcoords="offset points")
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_xticks(range(4))
        ax.set_xticklabels(["%d to %d" % (w[q].min(), w[q].max()) for q in quarters], fontsize=8)
        ax.set_title(LABEL[s], fontsize=9.5, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("lean minus classic, decodes per cycle (mean ± s.e.)")
    fig.text(0.5, -0.07, "x: WSJT-X decodes in the cycle; the cycles are ordered by that count and cut into four equal-sized groups, quietest to busiest.\nOrange: lean ahead; blue: classic ahead.", ha="center", fontsize=8, color=INK2)
    save(fig, "fig9_gap_vs_activity.png")


def md_table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def tables(D):
    T = {}
    rows = []
    for s, _ in FILES:
        a = D[s]["arm"]
        for arm, name in (("C", "classic"), ("L", "lean")):
            x = a[arm]
            rows.append([s if arm == "C" else "", "%s (%s)" % (arm, name), D[s]["cycles"] if arm == "C" else "", x["wsjtx_decodes"], x["matched"], x["ours"], "%.2f" % x["rate_pct"],
                         "%.2f" % x["ours_only_pct"], "%.2f" % x["cpu_s_per_cycle"], "{:,}".format(x["last_p95_ms"]), x["abandoned_cycles"]])
        c, l = a["C"], a["L"]
        rows.append(["", "**L \u2212 C**", "", "", l["matched"] - c["matched"], l["ours"] - c["ours"], "**%+.2f pp**" % (l["rate_pct"] - c["rate_pct"]),
                     "%+.2f pp" % (l["ours_only_pct"] - c["ours_only_pct"]), "%+.2f" % (l["cpu_s_per_cycle"] - c["cpu_s_per_cycle"]), "{:+,}".format(l["last_p95_ms"] - c["last_p95_ms"]), ""])
    T["T1"] = md_table(["Slice", "Arm", "Cycles", "WSJT-X decodes", "matched", "ours", "rate %", "ours_only %", "cpu_net (CPU-s/cycle)", "last_p95 (ms)", "abandoned"], rows)

    rows = []
    for s, _ in FILES:
        o = D[s]["overlap"]
        n = sum(o.values())
        rows.append([s, n] + ["%d (%.1f %%)" % (o[k], 100.0 * o[k] / n) for k in ("both", "c_only", "l_only", "neither")] + ["%d (%.1f %%)" % (o["c_only"] + o["neither"], 100.0 * (o["c_only"] + o["neither"]) / n)])
    T["T2"] = md_table(["Slice", "WSJT-X decodes", "Found by both", "Classic only", "Lean only", "Neither", "WSJT-X-only for L (= C only + neither)"], rows)

    for s, _ in FILES:
        rows = []
        for b in BANDS:
            for crowd in ("alone", "crowded"):
                c = cell(D[s], b, crowd)
                n = sum(c.values())
                rows.append([BAND_LABEL[b] if crowd == "alone" else "", crowd, n, "%.1f" % pct(c["both"] + c["c_only"], n) if n else "", "%.1f" % pct(c["both"] + c["l_only"], n) if n else "",
                             c["c_only"], c["l_only"], c["neither"], c["c_only"] + c["neither"]])
        t = {"both": 0, "c_only": 0, "l_only": 0, "neither": 0}
        for b in BANDS:
            for k, v in band_totals(D[s], b).items():
                t[k] += v
        n = sum(t.values())
        rows.append(["**all**", "", n, "**%.1f**" % pct(t["both"] + t["c_only"], n), "**%.1f**" % pct(t["both"] + t["l_only"], n), t["c_only"], t["l_only"], t["neither"], t["c_only"] + t["neither"]])
        T["T3_" + s] = md_table(["SNR band (dB)", "Crowding", "WSJT-X decodes", "C decoded %", "L decoded %", "C only", "L only", "Neither", "WSJT-X-only for L"], rows)

    rows = []
    for s, _ in FILES:
        d = D[s]
        oc = l_origin_counts(d)
        tot = sum(oc.values())
        rows.append([s] + ["%d (%.1f %%)" % (oc[k], 100.0 * oc[k] / tot) for k, _ in L_ORIGIN] + [oc["other"]])
    T["T4_L"] = md_table(["Slice"] + [n for _, n in L_ORIGIN] + ["other"], rows)
    rows = []
    for s, _ in FILES:
        m = D[s]["matched_by_batch_kind"]["C"]
        tot = sum(m.get(k, 0) for k, _ in C_ORIGIN)
        rows.append([s] + ["%d (%.1f %%)" % (m.get(k, 0), 100.0 * m.get(k, 0) / tot) for k, _ in C_ORIGIN])
    T["T4_C"] = md_table(["Slice"] + [n for _, n in C_ORIGIN], rows)

    rows = []
    for s, _ in FILES:
        for arm in ("C", "L"):
            o = D[s]["ours_only"][arm]
            row = [s if arm == "C" else "", arm, o["n"], o["same_text_decoded_elsewhere_by_wsjtx"]]
            for b in BANDS:
                a = o["cells"].get("%s|alone" % b, 0)
                c = o["cells"].get("%s|crowded" % b, 0)
                row.append("%d / %d" % (a, c))
            rows.append(row)
    T["T5"] = md_table(["Slice", "Arm", "ours_only", "WSJT-X decoded the same text at another frequency"] + ["%s (alone / crowded)" % BAND_LABEL[b] for b in BANDS], rows)
    return T


def main():
    D = load()
    for s, _ in FILES:                                                         # cross-checks as assertions, not prose
        d = D[s]
        o = d["overlap"]
        assert o["both"] + o["c_only"] == d["arm"]["C"]["matched"] or abs(o["both"] + o["c_only"] - d["arm"]["C"]["matched"]) <= 3, (s, "C matched")
        assert o["both"] + o["l_only"] == d["arm"]["L"]["matched"] or abs(o["both"] + o["l_only"] - d["arm"]["L"]["matched"]) <= 3, (s, "L matched")
    for f in (fig_headline, fig_cost, fig_overlap, fig_snr, fig_crowding, fig_origin, fig_ours_only, fig_latency, fig_cycle_gap):
        f(D)
    json.dump(tables(D), open(os.path.join(SC, "tables.json"), "w"), indent=1)
    print("figures and tables written")


if __name__ == "__main__":
    main()
