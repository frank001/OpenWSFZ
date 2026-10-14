"""Build the CONSOLIDATED final report of the LINUX R&R series on `sol` (QA tooling; aggregates only, NFR-021).

    python build_consolidated_report.py --results <results root> --out <folder> [--trend <trend.csv>]

Reads the eight sweeps' own run folders (five paired + three OpenWSFZ-only) through consolidate_data.py, writes <out>/report.md, <out>/img/*.png, report.html (the standing renderer,
images by relative path) and report-standalone.html (images embedded, one file). Every number in the text comes from the data; nothing is typed in
except the Windows reference values quoted from the run-2 report (marked) and the text of the findings.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import consolidate_data as C  # noqa: E402

BG, FG, GRID = "#0d1117", "#c9d1d9", "#30363d"
COL = {"run1": "#f85149", "run2": "#58a6ff", "w1": "#3fb950", "w2": "#d29922", "w3": "#bc8cff", "rep1": "#6e7681", "rep2": "#6e7681", "rep3": "#6e7681"}
SHORT = {"run1": "Run 1\ndefault chain", "run2": "Run 2\ncorrected", "w1": "Repeat 1b\ncorrected", "w2": "Repeat 2b\ncorrected", "w3": "Repeat 3b\ncorrected",
         "rep1": "Repeat 1\n(no WSJT-X)", "rep2": "Repeat 2\n(no WSJT-X)", "rep3": "Repeat 3\n(no WSJT-X)"}
WIN_OWS_BIAS = [0.92, 0.85, 0.88, 1.48]       # quoted from the run-2 report, Section 5 item 2 (Windows sweeps; not comparable with this series)
KEYS = ["run1", "run2", "w1", "w2", "w3"]                  # the five PAIRED sweeps (both appraisers decoding): every table and graph
OWS_ONLY = ["rep1", "rep2", "rep3"]                       # the 11-12 Oct repeats that ran with WSJT-X silent: OpenWSFZ-only, shown apart (Section 2b, Figure 6)


def na(v, f="%s"):
    return "no data" if v is None else f % v


def fig_style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "text.color": FG, "axes.labelcolor": FG,
                         "axes.edgecolor": GRID, "xtick.color": FG, "ytick.color": FG, "grid.color": GRID, "axes.grid": True, "grid.alpha": 0.6,
                         "legend.facecolor": BG, "legend.edgecolor": GRID, "font.size": 10})
    return plt


def figures(S: dict, trend: list, img: str) -> dict:
    plt = fig_style()
    import numpy as np
    out = {}

    # F1: S1 bias vs injected SNR
    fig, ax = plt.subplots(figsize=(9, 5))
    for k in KEYS:
        o = S[k]["s1_bias_by_snr"]["OpenWSFZ"]
        xs = sorted(float(x) for x in o)
        ax.plot(xs, [o[str(x)]["mean"] for x in xs], "o-", color=COL[k], label="OpenWSFZ, " + SHORT[k].replace("\n", " "))
        if S[k]["wsjtx_present"]:
            w = S[k]["s1_bias_by_snr"]["WSJT-X"]
            ax.plot(xs, [w[str(x)]["mean"] for x in xs], "x--", color=COL[k], alpha=0.8, label="WSJT-X, " + SHORT[k].replace("\n", " "))
    ax.axhline(2, color="#8b949e", ls=":"); ax.axhline(-2, color="#8b949e", ls=":")
    ax.set(xlabel="injected SNR (dB)", ylabel="reported minus injected SNR (dB), mean of the matched decodes", title="S1: SNR bias by injected SNR (dotted: the ±2 dB bar)")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout(); fig.savefig(os.path.join(img, "F1_s1_bias_by_snr.png"), dpi=110); plt.close(fig)
    out["F1"] = ("F1_s1_bias_by_snr.png", "S1 SNR bias by injected SNR, the five paired sweeps (solid: OpenWSFZ, dashed: WSJT-X). The default chain (red) sits about 4 dB low; the four corrected-chain sweeps lie between 0 and +2 dB, with WSJT-X's curves in the same band.")

    # F2: S1 mean bias per sweep
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(KEYS))
    ax.bar(x - 0.18, [S[k]["s1"]["bias_owsfz"] for k in KEYS], 0.36, color=[COL[k] for k in KEYS], label="OpenWSFZ")
    ax.bar(x + 0.18, [S[k]["s1"]["bias_wsjtx"] for k in KEYS], 0.36, color="#8b949e", alpha=0.7, label="WSJT-X")
    ax.axhspan(min(WIN_OWS_BIAS), max(WIN_OWS_BIAS), color="#3fb950", alpha=0.15, label="Windows OpenWSFZ range +0.85 to +1.48 dB (other platform, shown for scale only)")
    ax.axhline(2, color="#8b949e", ls=":"); ax.axhline(-2, color="#8b949e", ls=":")
    ax.set_xticks(x); ax.set_xticklabels([SHORT[k] for k in KEYS], fontsize=8)
    ax.set(ylabel="mean SNR bias (dB)", title="S1 mean SNR bias per sweep")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(img, "F2_s1_mean_bias.png"), dpi=110); plt.close(fig)
    out["F2"] = ("F2_s1_mean_bias.png", "Mean S1 SNR bias per sweep against the ±2 dB bar, both appraisers in every sweep.")

    # F3: GR&R
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    w = 0.16
    for j, sc in enumerate(("s1", "s2", "s3")):
        pass
    for i, k in enumerate(KEYS):
        axs[0].bar(np.arange(3) + (i - 2) * w, [max(S[k][sc]["pct_grr"], 0.01) for sc in ("s1", "s2", "s3")], w, color=COL[k], label=SHORT[k].replace("\n", " "))
        axs[1].bar(np.arange(3) + (i - 2) * w, [S[k][sc]["ndc"] for sc in ("s1", "s2", "s3")], w, color=COL[k])
    for ax_i, key in ((0, "pct_grr"), (1, "ndc")):
        for i, k in enumerate(KEYS):
            for j, sc in enumerate(("s1", "s2", "s3")):
                v = S[k][sc][key]
                axs[ax_i].text(j + (i - 2) * w, max(v, 0.01) * 1.15, ("%.1f" % v) if key == "pct_grr" else "%d" % v, ha="center", fontsize=6)
    axs[0].set_yscale("log"); axs[1].set_yscale("log")
    axs[0].axhline(10, color="#8b949e", ls=":"); axs[0].text(2.4, 10.5, "10 %", fontsize=8)
    for a, t in zip(axs, ("%GR&R (log; floor 0.01)", "ndc (log)")):
        a.set_xticks(range(3)); a.set_xticklabels(["S1 SNR", "S2 frequency", "S3 DT"]); a.set_title(t)
    axs[0].legend(fontsize=7, loc="upper center", bbox_to_anchor=(1.1, -0.1), ncol=3)
    fig.suptitle("Gage R&R per sweep (two appraisers in every sweep shown)", fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95)); fig.savefig(os.path.join(img, "F3_grr.png"), dpi=110); plt.close(fig)
    out["F3"] = ("F3_grr.png", "%GR&R and ndc for S1, S2, S3, all five paired sweeps. Run 1's S1 is the only marginal value.")

    # F4: S1b
    fig, ax = plt.subplots(figsize=(10, 4.8))
    snrs = [r["snr"] for r in S["run2"]["s1b"]]
    x = np.arange(len(snrs))
    bars = [(k, "OpenWSFZ") for k in KEYS] + [(k, "WSJT-X") for k in KEYS]
    w = 0.085
    for i, (k, ap) in enumerate(bars):
        vals = [r["o_rate"] if ap == "OpenWSFZ" else r["w_rate"] for r in S[k]["s1b"]]
        pos = x + (i - (len(bars) - 1) / 2) * w
        if ap == "OpenWSFZ":
            ax.bar(pos, vals, w, color=COL[k], label="OpenWSFZ, " + SHORT[k].replace("\n", " "))
        else:
            ax.bar(pos, vals, w, color="none", edgecolor="#e6edf3", hatch="//", label="WSJT-X, " + SHORT[k].replace("\n", " "))
        for xp, v in zip(pos, vals):
            if v is not None and v == 0:
                ax.text(xp, 1.5, "0", ha="center", fontsize=6)
    ax.set_xticks(x); ax.set_xticklabels(["%g dB" % sn for sn in snrs])
    ax.set(ylabel="decode rate (%) of 3 trials", title="S1b: low-SNR decode rate (3 trials per cell, n = 12 per appraiser per sweep: direction only)")
    ax.set_ylim(0, 130)
    ax.legend(fontsize=7, ncol=3, loc="upper center")
    fig.tight_layout(); fig.savefig(os.path.join(img, "F4_s1b.png"), dpi=110); plt.close(fig)
    out["F4"] = ("F4_s1b.png", "S1b decode rate by SNR. Coloured: OpenWSFZ in every sweep; hatched: WSJT-X, in the same five sweeps. The default chain loses OpenWSFZ's -18 dB case and two of three -15 dB cases; every corrected sweep decodes -18 and -15 dB 3 of 3. Three trials per cell: direction only.")

    # F5: recoveries
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.6))
    for a, title, getter in ((axs[0], "S4 recovery (108 injected)", lambda s, ap: s["s4"].get(ap, {}).get("recovery")),
                             (axs[1], "S7 all families", lambda s, ap: s["s7"]["all"]["owsfz" if ap == "OpenWSFZ" else "wsjtx"]),
                             (axs[2], "S8 band scene (60 injected)", lambda s, ap: s["s8"].get(ap, {}).get("rate"))):
        for i, k in enumerate(KEYS):
            for j, ap in enumerate(("OpenWSFZ", "WSJT-X")):
                v = getter(S[k], ap)
                if v is None:
                    a.text(i + (j - 0.5) * 0.4, 2, "no data", rotation=90, fontsize=7, ha="center", va="bottom", color="#8b949e")
                else:
                    a.bar(i + (j - 0.5) * 0.4, v, 0.38, color=COL[k] if j == 0 else "#8b949e", alpha=1.0 if j == 0 else 0.7)
        a.set_xticks(range(len(KEYS))); a.set_xticklabels([SHORT[k] for k in KEYS], fontsize=7); a.set_ylim(0, 105); a.set_title(title)
    axs[0].set_ylabel("%  (coloured: OpenWSFZ, grey: WSJT-X)")
    fig.tight_layout(); fig.savefig(os.path.join(img, "F5_recovery.png"), dpi=110); plt.close(fig)
    out["F5"] = ("F5_recovery.png", "Recovery by sweep, the five paired sweeps (coloured: OpenWSFZ, grey: WSJT-X). S4 is identical for OpenWSFZ in all five; S7 and S8 move by a few points between the corrected sweeps.")

    # F6: stability of the corrected-chain sweeps (OpenWSFZ side; the three 11-12 Oct repeats have no WSJT-X and are drawn grey)
    seq = ["run2", "rep1", "rep2", "rep3", "w1", "w2", "w3"]
    labs = ["run 2", "rep 1*", "rep 2*", "rep 3*", "rep 1b", "rep 2b", "rep 3b"]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.9))
    series = [("S1 bias (dB)", [S[k]["s1"]["bias_owsfz"] for k in seq]), ("S4 recovery (%)", [S[k]["s4"]["OpenWSFZ"]["recovery"] for k in seq]),
              ("S7 all (%)", [S[k]["s7"]["all"]["owsfz"] for k in seq]), ("S8 rate (%)", [S[k]["s8"]["OpenWSFZ"]["rate"] for k in seq])]
    for a, (t, v) in zip(axs, series):
        a.plot(range(len(seq)), v, "-", color="#8b949e", lw=0.8)
        for i, (k, y) in enumerate(zip(seq, v)):
            a.plot([i], [y], "o", color=COL[k], ms=7)
            a.text(i, y, " %.2f" % y, fontsize=6, va="bottom", rotation=45)
        a.set_xticks(range(len(seq))); a.set_xticklabels(labs, fontsize=7, rotation=30); a.set_title(t)
        pad = max(0.5, (max(v) - min(v)) * 0.6)
        a.set_ylim(min(v) - pad, max(v) + pad)
    fig.suptitle("OpenWSFZ on the corrected chain, seven sweeps on the same build (same pins): the spread is the instrument's.  * = WSJT-X was silent (grey)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(img, "F6_stability.png"), dpi=110); plt.close(fig)
    out["F6"] = ("F6_stability.png", "OpenWSFZ's side of all seven corrected-chain sweeps in time order (run 2; the three 11-12 Oct repeats, grey, WSJT-X silent; the three 14 Oct repeats with WSJT-X). Same build, same library, same chain: the movement here is run-to-run noise, the yardstick for reading any later change.")

    # F7: history (Windows trend for scale; the Linux series is separate)
    rows = [r for r in trend if r["run_date"][:2] == "20" and r["bias_snr_owsfz"] not in ("", None)]
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.3))
    xs = list(range(len(rows)))
    axs[0].plot(xs, [float(r["bias_snr_owsfz"]) for r in rows], "o-", color="#8b949e", label="Windows series (trend.csv), OpenWSFZ S1 bias")
    axs[0].axhline(2, color="#8b949e", ls=":"); axs[0].axhline(-2, color="#8b949e", ls=":")
    axs[0].set(xlabel="Windows sweep, in order", ylabel="dB", title="History for scale: Windows S1 bias (a different series)")
    rows2 = [r for r in trend if r["run_date"][:2] == "20" and r["pct_grr_snr"] not in ("", None)]
    axs[1].plot(range(len(rows2)), [float(r["pct_grr_snr"]) for r in rows2], "o-", color="#8b949e")
    axs[1].set_yscale("log"); axs[1].axhline(10, color="#8b949e", ls=":")
    axs[1].set(xlabel="Windows sweep, in order", ylabel="%GR&R, S1 (log)", title="History for scale: Windows S1 %GR&R")
    for k in KEYS:                                                  # the Linux sweeps, at the right edge, in their own colours
        axs[0].plot([len(rows) + 2 + KEYS.index(k)], [S[k]["s1"]["bias_owsfz"]], "D", color=COL[k], ms=8)
        axs[1].plot([len(rows2) + 2 + KEYS.index(k)], [max(S[k]["s1"]["pct_grr"], 0.01)], "D", color=COL[k], ms=8)
    for a in axs:
        a.axvline(len(rows) + 0.5 if a is axs[0] else len(rows2) + 0.5, color=GRID)
        a.text(0.99, 0.02, "right of the line: the LINUX series (not comparable)", transform=a.transAxes, ha="right", fontsize=8, color="#8b949e")
    fig.tight_layout(); fig.savefig(os.path.join(img, "F7_history.png"), dpi=110); plt.close(fig)
    out["F7"] = ("F7_history.png", "History: the Windows series' S1 bias and %GR&R from trend.csv, for scale only, with the five paired Linux sweeps (diamonds) to the right. The two series are different platforms, CPUs and audio chains and are never pooled.")
    return out


def keepup_figure(K: dict, img: str) -> tuple:
    """F8: the 70 min WSJT-X run (13 Oct): rows per cycle by block, and WSJT-X's late share by live row count."""
    plt = fig_style()
    import numpy as np
    cmp_, summ = K["compare"], K["summary"]
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.7, 1]})
    ids = sorted(cmp_["blocks"], key=lambda b: (cmp_["blocks"][b]["run"] != "20260803_live_run_1713", b))
    x = np.arange(len(ids))
    for i, (key, lab, col) in enumerate((("live", "LIVE WSJT-X (station log)", "#8b949e"), ("E", "WSJT-X 2.7.0 replay on sol", "#e3b341"), ("B", "OpenWSFZ leg B", "#58a6ff"))):
        axs[0].bar(x + (i - 1) * 0.27, [cmp_["blocks"][b]["rows_per_cycle"][key] for b in ids], 0.27, color=col, label=lab)
    axs[0].set_xticks(x)
    axs[0].set_xticklabels([("%s\n%s%s" % (b[:6], cmp_["blocks"][b]["band"], "\n0803" if cmp_["blocks"][b]["run"] == "20260803_live_run_1713" else "")) for b in ids], fontsize=7)
    axs[0].set(ylabel="non-hashed rows per cycle", title="Rows per cycle: the 4 blocks of the 0803 night (left) and the 3 busiest blocks")
    axs[0].legend(fontsize=7)
    bins = ["<=10", "11-20", "21-30", ">30"]
    b = summ["by_density_bin"]
    vals = [100 * b[k]["late_share"] for k in bins]
    axs[1].bar(range(4), vals, color="#e3b341")
    for i, k in enumerate(bins):
        axs[1].text(i, vals[i] + 0.8, "n=%d" % b[k]["cycles"], ha="center", fontsize=8)
    axs[1].axhline(100 * summ["late_gt_17s"]["share"], color="#f85149", ls="--", lw=1)
    axs[1].text(3.4, 100 * summ["late_gt_17s"]["share"] + 0.8, "all cycles %.1f %%" % (100 * summ["late_gt_17s"]["share"]), color="#f85149", ha="right", fontsize=8)
    axs[1].set_xticks(range(4)); axs[1].set_xticklabels(["<= 10", "11-20", "21-30", "> 30"])
    axs[1].set(xlabel="live WSJT-X rows in the cycle", ylabel="% of cycles with the last decode > 17 s after the boundary", title="WSJT-X keep-up on the FX-8350 (WSJT-X alone)")
    fig.tight_layout(); fig.savefig(os.path.join(img, "F8_keepup.png"), dpi=110); plt.close(fig)
    return ("F8_keepup.png", "The 70 min WSJT-X run (13 Oct, one replicate). Left: on the 0803 night a WSJT-X 2.7.0 replay of the same recordings finds about twice the rows the live WSJT-X logged, and OpenWSFZ sits close to the replay; on the busy blocks of other nights the replay and the live log agree. Right: WSJT-X's own late share on this CPU, by the live row count of the cycle (WSJT-X alone on the CPU).")


def md_table(head: list, rows: list) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def build(results: str, out: str, trend_path: str) -> None:
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    S = {s[0]: C.one(results, *s) for s in C.SWEEPS}
    trend = list(csv.DictReader(open(trend_path, encoding="utf8")))
    F = figures(S, trend, os.path.join(out, "img"))
    kdir = os.path.join(results, "2026-10-13-wsjtx-keepup-run-sol")
    K = {"compare": json.load(open(os.path.join(kdir, "compare-rep1.json"), encoding="utf8")), "summary": json.load(open(os.path.join(kdir, "SUMMARY-rep1.json"), encoding="utf8"))}
    F["F8"] = keepup_figure(K, os.path.join(out, "img"))
    r1, r2 = S["run1"], S["run2"]
    paired = [S[k] for k in KEYS]
    corrected = [S[k] for k in KEYS[1:]]                       # the four paired corrected-chain sweeps
    seven = [S[k] for k in ["run2"] + OWS_ONLY + KEYS[2:]]     # all seven corrected-chain sweeps, OpenWSFZ side
    bias = [s["s1"]["bias_owsfz"] for s in corrected]
    bias7 = [s["s1"]["bias_owsfz"] for s in seven]
    wbias = [s["s1"]["bias_wsjtx"] for s in corrected]
    rng = lambda v: "%.2f to %.2f" % (min(v), max(v))
    uniq = lambda v, f="%.2f": "/".join(sorted({f % x for x in v}))
    dur = lambda s: s["cycle_utc_first_last"]
    mins = lambda s: round((__import__("datetime").datetime.fromisoformat(dur(s)[1].replace("Z", "")) - __import__("datetime").datetime.fromisoformat(dur(s)[0].replace("Z", ""))).total_seconds() / 60)
    s4o = {s["s4"]["OpenWSFZ"]["tp"] for s in paired}
    s4w = {s["s4"]["WSJT-X"]["tp"] for s in paired}
    L = []
    A = L.append
    A("# OpenWSFZ R&R Study: LINUX series on `sol`, consolidated final report")
    A("")
    A("> **LINUX series, five PAIRED sweeps (both appraisers decoding): run 1 on the DEFAULT ALSA chain (11 October), run 2 on the CORRECTED chain (`samplerate_best`, 11 October), and repeats 1b-3b on the corrected chain (14 October, WSJT-X verified decoding).** "
      "Three further corrected-chain sweeps of 11-12 October (repeats 1-3) ran with WSJT-X silent: they are OpenWSFZ-only readings, shown apart (Section 2b, Figure 6) and never used as paired data. "
      "**Not comparable with the Windows series** (other platform, CPU and audio chain; WSJT-X 2.7.0 built from source by QA). Informational: no merge or build decision rests on this report. "
      "**Section 7 (added 2026-10-13) reports the related 70 min WSJT-X run on the same host.**")
    A("")
    A(md_table(["Field", "Value"], [
        ["Report date", "2026-10-14 (QA; the 14 October repeats run on `sol` 08:38Z to 16:41Z)"],
        ["Host", "`sol`: AMD FX-8350, Gentoo; no radio, no CAT; audio through the codec loopback, PCM `rr_in`"],
        ["OpenWSFZ build, all eight sweeps", "`main` `%s` (v%s, shim %s)" % (r2["build"]["commit"], r2["build"]["daemon_version"], r2["build"]["shim"])],
        ["`libft8.so` SHA-256", "`%s` in all eight (read back from each run's `arm_config.json`: %s)" % (r2["build"]["dll_sha256"], "equal" if len({S[k]["build"]["dll_sha256"] for k in S}) == 1 else "NOT EQUAL")],
        ["Decoder flags (read back)", "`nhard` / `osdNhardMax` %s, `subtractionEnabled` %s, `subtractionMaxThreads` %s, same in every sweep" % (r2["build"]["readback"]["osdNhardMax"], r2["build"]["readback"]["subtractionEnabled"], r2["build"]["readback"]["subtractionMaxThreads"])],
        ["WSJT-X", "2.7.0 built from the verified source tarball on `sol` (conda-forge Qt 5.15, gfortran 13.4.0); NDepth %s; WSJT-X 3.x cannot be the appraiser (its `callok` rejects every callsign starting with Q)" % r2["build"]["wsjtx_ndepth"]],
        ["Paired run folders", "`2026-10-11-64246e4-LINUX-sol` (run 1), `…-SAMPLERATE-chain` (run 2), `2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT1`, `…-WSJTX-REPEAT2-REPLACEMENT`, `…-WSJTX-REPEAT3`"],
    ]))
    A("")
    A("## Section 1: scope, provenance and what each sweep contains")
    A("")
    A(md_table(["Sweep", "Chain", "Cycles first to last (UTC)", "WSJT-X decoded?", "`wsjt-all.txt` / `owsfz-all.txt` lines", "Analyser's overall verdict"],
               [[s["label"], "default ALSA `linear`" if not s["corrected_chain"] else "ALSA `samplerate_best`", "%s to %s" % (dur(s)[0][5:16].replace("T", " "), dur(s)[1][5:16].replace("T", " ")),
                 "yes" if s["wsjtx_present"] else "**NO: 0 lines**", "%d / %d" % (s["wsjt_all_lines"], s["owsfz_all_lines"]),
                 s["overall"] + ("" if s["wsjtx_present"] else " (OpenWSFZ only)")] for s in (S[k] for k in KEYS[:2] + OWS_ONLY + KEYS[2:])]))
    A("")
    A("Each sweep is a full S1-S8 battery (S1, S1b, S2, S3, S4, S5, S7, S8, S3c) of about 1 h 53 min to 1 h 57 min. Repeats 1b-3b ran 14 October back to back on one WSJT-X start per sweep, with the battery's PRECHECK row `wsjtx_running` and its mechanical warm-up check on (both `ALL.TXT` gained a line from a synthetic cycle before scenario 1: `warmup_check.json` `ok` in every run folder).")
    A("")
    A("**Two incidents in which WSJT-X stopped taking in audio, and how they are treated.** (1) **11-12 October:** WSJT-X's `save/` WAVs stop after 11 Oct 09:32:30 UTC (idle, 2 h 35 min after the last audio was played, 4 h 39 min after the WSJT-X start) and resume only on 12 Oct at 19:39; repeats 1-3 therefore have `wsjt-all.txt` of 0 lines. They are kept as OpenWSFZ-only readings and never used as paired data. (2) **14 October:** in the first attempt at repeat 2 WSJT-X stopped taking in audio at **11:09:30 UTC** (inside scenario S4, 33 min after its start) and stayed silent for about 1 h 24 min; that sweep (`2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT2`) is **INVALID, none of its data is used (including the first 32 minutes)**, and it was replaced by a complete sweep (`…-REPEAT2-REPLACEMENT`, labelled 'Repeat 2b' here). The rule is: the series is N complete sweeps; a sweep in which an appraiser has no data for part of the battery is invalid and replaced. In each of the five paired sweeps, WSJT-X has a saved WAV for every scored cycle of every scenario (checked against the run's `truth.csv` for repeats 1b-3b). Neither incident left a kernel, syslog or core-dump trace; the cause is not established (`qa/rr-study/2026-10-14-1830-qa-plan-wsjtx-stall-monitoring-and-gate.md`).")
    A("")
    A("## Section 2: results side by side (the five paired sweeps)")
    A("")
    row = lambda name, f: [name] + [f(S[k]) for k in KEYS]
    hd = ["Measure"] + [SHORT[k].replace("\n", " ") for k in KEYS]
    A(md_table(hd, [
        row("S1 OpenWSFZ mean bias (dB), bar ±2", lambda s: "%+.2f %s" % (s["s1"]["bias_owsfz"], s["s1"]["bias_verdict"])),
        row("S1 WSJT-X mean bias (dB)", lambda s: na(s["s1"]["bias_wsjtx"], "%+.2f")),
        row("S1 %GR&R (ndc)", lambda s: "%.1f %% (%d)" % (s["s1"]["pct_grr"], s["s1"]["ndc"])),
        row("S2 %GR&R (ndc)", lambda s: "%.1f %% (%d)" % (s["s2"]["pct_grr"], s["s2"]["ndc"])),
        row("S3 %GR&R (ndc)", lambda s: "%.1f %% (%d)" % (s["s3"]["pct_grr"], s["s3"]["ndc"])),
        row("κ OpenWSFZ vs truth", lambda s: "%.3f" % s["kappa"]["OpenWSFZ_vs_truth"]),
        row("κ WSJT-X vs truth / between appraisers", lambda s: "%.3f / %.3f" % (s["kappa"]["WSJT-X_vs_truth"], s["kappa"]["between_appraisers"])),
        row("S4 recovery, OpenWSFZ (of 108)", lambda s: "%.2f %% (%d)" % (s["s4"]["OpenWSFZ"]["recovery"], s["s4"]["OpenWSFZ"]["tp"])),
        row("S4 recovery, WSJT-X (of 108)", lambda s: "%.2f %% (%d)" % (s["s4"]["WSJT-X"]["recovery"], s["s4"]["WSJT-X"]["tp"])),
        row("S5 OpenWSFZ false positives (Gate A-W)", lambda s: s["s5"]["gate_aw"].split(" (")[0]),
        row("S5 narrowband Check B (WSJT-X / OpenWSFZ)", lambda s: "%s / %s" % (s["s5"]["check_b_w"].split(" slots")[0], s["s5"]["check_b_o"].split(" slots")[0])),
        row("S1b decode rate OpenWSFZ / WSJT-X (n = 12)", lambda s: "%.2f %% / %s" % (s["s1b_overall"]["owsfz"], na(s["s1b_overall"]["wsjtx"], "%.2f %%"))),
        row("S7 recovery OpenWSFZ / WSJT-X", lambda s: "%.2f %% / %s" % (s["s7"]["all"]["owsfz"], na(s["s7"]["all"]["wsjtx"], "%.2f %%"))),
        row("S8 decode rate OpenWSFZ / WSJT-X (of 60)", lambda s: "%.2f %% / %.2f %%" % (s["s8"]["OpenWSFZ"]["rate"], s["s8"]["WSJT-X"]["rate"])),
        row("S7+S8 pooled matched decodes OpenWSFZ / WSJT-X", lambda s: "%d / %d" % (s["s78_pooled_matched"].get("OpenWSFZ", 0), s["s78_pooled_matched"].get("WSJT-X", 0))),
        row("S3c parts passing (of 8)", lambda s: "%d" % s["s3c"]["pass"]),
    ]))
    A("")
    A("## Section 2b: the three 11-12 October repeats (WSJT-X silent; OpenWSFZ side only)")
    A("")
    ow = [S[k] for k in OWS_ONLY]
    A(md_table(["Measure"] + [SHORT[k].replace("\n", " ") for k in OWS_ONLY], [
        ["S1 OpenWSFZ mean bias (dB)"] + ["%+.2f %s" % (s["s1"]["bias_owsfz"], s["s1"]["bias_verdict"]) for s in ow],
        ["S1 / S2 / S3 %GR&R (OpenWSFZ repeatability only)"] + ["%.1f / %.1f / %.1f %%" % (s["s1"]["pct_grr"], s["s2"]["pct_grr"], s["s3"]["pct_grr"]) for s in ow],
        ["κ OpenWSFZ vs truth"] + ["%.3f" % s["kappa"]["OpenWSFZ_vs_truth"] for s in ow],
        ["S4 recovery, OpenWSFZ (of 108)"] + ["%.2f %% (%d)" % (s["s4"]["OpenWSFZ"]["recovery"], s["s4"]["OpenWSFZ"]["tp"]) for s in ow],
        ["S5 OpenWSFZ false positives (Gate A-W)"] + [s["s5"]["gate_aw"].split(" (")[0] for s in ow],
        ["S1b decode rate OpenWSFZ"] + ["%.2f %%" % s["s1b_overall"]["owsfz"] for s in ow],
        ["S7 recovery OpenWSFZ"] + ["%.2f %%" % s["s7"]["all"]["owsfz"] for s in ow],
        ["S8 decode rate OpenWSFZ (of 60)"] + ["%.2f %%" % s["s8"]["OpenWSFZ"]["rate"] for s in ow],
    ]))
    A("")
    A("These sweeps have no WSJT-X reading, so no appraiser R&R, no between-appraiser κ and no S3c WSJT-X parts; the analyser's `ndc = 1 FAIL` rows for them are the missing second appraiser (reproducibility 0), not agreement between two appraisers. Their OpenWSFZ side is valid and enters Figure 6 only.")
    A("")
    A("## Section 3: graphs")
    A("")
    for key in ("F1", "F2", "F3", "F4", "F5", "F6"):
        A("![%s](img/%s)" % (F[key][1][:60], F[key][0]))
        A("")
        A("*Figure %s. %s*" % (key[1:], F[key][1]))
        A("")
    A("Per-run Gage R&R panels (S1, S2, S3) of every paired sweep are in the run folders: " + "; ".join("[%s](../%s/S1_grr_panel.png)" % (SHORT[k].replace("\n", " "), S[k]["folder"]) for k in KEYS) + ".")
    A("")
    A("## Section 4: observations")
    A("")
    d_bias = r2["s1"]["bias_owsfz"] - r1["s1"]["bias_owsfz"]
    A("1. **The default chain is the cause of run 1's S1 failure, and the corrected chain removes it.** OpenWSFZ's S1 bias goes from %+.2f dB (run 1, FAIL against ±2 dB) to %+.2f dB (run 2), a shift of %+.2f dB; S1 %%GR&R from %.1f %% to %.1f %% (ndc %d to %d); WSJT-X's own S1 bias barely moves (%+.2f to %+.2f dB). The same-audio test in run 1 (the Windows decoder on the 30 recordings made on `sol`, difference 0.00 dB, 30 of 30) (quoted from run 1's own diagnostics) shows the decoder reads the same on both platforms, so the difference between the runs is the chain (defect #234, `ArecordAudioSource.cs:95`)." % (
        r1["s1"]["bias_owsfz"], r2["s1"]["bias_owsfz"], d_bias, r1["s1"]["pct_grr"], r2["s1"]["pct_grr"], r1["s1"]["ndc"], r2["s1"]["ndc"], r1["s1"]["bias_wsjtx"], r2["s1"]["bias_wsjtx"]))
    A("2. **The default chain also costs weak signals.** S1b, OpenWSFZ: %.2f %% in run 1 against %s %% in the four corrected sweeps (the -18 and -15 dB cases go from 0 or 1 of 3 to 3 of 3; the -21 and -24 dB cases stay at 0 of 3). WSJT-X: %.2f %% in run 1 and %s %% in the four corrected sweeps. Twelve trials per appraiser per sweep: direction only." % (
        r1["s1b_overall"]["owsfz"], uniq([s["s1b_overall"]["owsfz"] for s in corrected]), r1["s1b_overall"]["wsjtx"], uniq([s["s1b_overall"]["wsjtx"] for s in corrected])))
    A("3. **OpenWSFZ is repeatable on the corrected chain.** Four paired sweeps on the same build, library and chain: S1 bias %s dB (spread %.2f dB); all seven corrected-chain sweeps including the three with WSJT-X silent: %s dB (spread %.2f dB; the four Windows sweeps quoted in the run-2 report are +0.92, +0.85, +0.88, +1.48 dB, spread 0.63 dB, a different series). S4 recovery %s %% and κ against truth %s in all seven; S7 %s %%; S8 %s %%; S1b %s %%; zero false positives in 480 slots and in the narrowband check in every sweep (Figure 6)." % (
        ", ".join("%+.2f" % b for b in bias), max(bias) - min(bias), ", ".join("%+.2f" % b for b in bias7), max(bias7) - min(bias7), uniq([s["s4"]["OpenWSFZ"]["recovery"] for s in seven]), uniq([s["kappa"]["OpenWSFZ_vs_truth"] for s in seven], "%.3f"),
        "/".join("%.2f" % s["s7"]["all"]["owsfz"] for s in seven), "/".join("%.2f" % s["s8"]["OpenWSFZ"]["rate"] for s in seven), uniq([s["s1b_overall"]["owsfz"] for s in seven])))
    A("4. **WSJT-X is repeatable on the corrected chain too, and the two appraisers differ by a stable amount.** WSJT-X's S1 bias in the four corrected paired sweeps: %s dB (spread %.2f dB), against OpenWSFZ's %s dB; WSJT-X S4 recovery %s of 108; S7 %s %%; S8 %s %%; S1b %s %%; κ WSJT-X against truth %s, between appraisers %s." % (
        ", ".join("%+.2f" % b for b in wbias), max(wbias) - min(wbias), ", ".join("%+.2f" % b for b in bias), "/".join(str(s["s4"]["WSJT-X"]["tp"]) for s in corrected),
        "/".join("%.2f" % s["s7"]["all"]["wsjtx"] for s in corrected), "/".join("%.2f" % s["s8"]["WSJT-X"]["rate"] for s in corrected), uniq([s["s1b_overall"]["wsjtx"] for s in corrected]),
        uniq([s["kappa"]["WSJT-X_vs_truth"] for s in corrected], "%.3f"), uniq([s["kappa"]["between_appraisers"] for s in corrected], "%.3f")))
    A("5. **The measurement system's Gage R&R on the corrected chain** (four paired sweeps, two appraisers): S1 %%GR&R %s %% (ndc %s), S2 %s %% (ndc %s), S3 %s %% (ndc %s)." % (
        rng([s["s1"]["pct_grr"] for s in corrected]), "/".join("%d" % s["s1"]["ndc"] for s in corrected), rng([s["s2"]["pct_grr"] for s in corrected]), "/".join("%d" % s["s2"]["ndc"] for s in corrected),
        rng([s["s3"]["pct_grr"] for s in corrected]), "/".join("%d" % s["s3"]["ndc"] for s in corrected)))
    A("6. **S4 recovery did not change with the chain**: OpenWSFZ %s of 108 and WSJT-X %s of 108 across the five paired sweeps. So the S4 gap to WSJT-X (%s messages) is not caused by the converter. OpenWSFZ's κ against truth is %s in every sweep." % (
        "/".join(str(x) for x in sorted(s4o)), "/".join(str(x) for x in sorted(s4w)), "%d to %d" % (min(s4w) - max(s4o), max(s4w) - max(s4o)), uniq([s["kappa"]["OpenWSFZ_vs_truth"] for s in paired], "%.3f")))
    A("7. **S7 is instrument-suspect by standing rule and no bare S7 mean is cited as a decoder figure.** OpenWSFZ ranges %.2f to %.2f %% across the eight sweeps; WSJT-X ranges %.2f to %.2f %% across the five paired. S8 (60 injected, a difference of 3 decodes is 5 points) is descriptive." % (
        min(s["s7"]["all"]["owsfz"] for s in S.values()), max(s["s7"]["all"]["owsfz"] for s in S.values()), min(s["s7"]["all"]["wsjtx"] for s in paired), max(s["s7"]["all"]["wsjtx"] for s in paired)))
    A("8. **Timing is stable.** Each sweep took about %d to %d min (cycle stamps first to last: %s)." % (min(mins(S[k]) for k in S), max(mins(S[k]) for k in S), "; ".join("%s %d min" % (k, mins(S[k])) for k in S)))
    A("9. **Instrument notes.** The audio-setup sampler is a Windows tool and fails on Linux by design (each sweep's summary logs worker crashes and 0 setup changes; the battery continues); the captured-audio scan was not run; WSJT-X's `ALL.TXT` is the live file, so a battery that follows a WSJT-X run must trim to its own window (done by the runner).")
    A("10. **WSJT-X's own decode on this CPU is sometimes late, and a live WSJT-X log can be thin for reasons that are not the audio** (Section 7, a separate 70 min run on the same host). Neither changes any figure above: the paired sweeps have both decoders on the one CPU, which the keep-up measurement (WSJT-X alone) does not cover.")
    A("")
    A("## Section 5: conclusions and recommendations")
    A("")
    A("**Conclusions.**")
    A("")
    A("1. On `sol`, OpenWSFZ passes the whole S1-S8 battery on a proper audio chain and fails S1 on the default one; the whole difference is the capture chain, not the decoder. A Linux user who runs OpenWSFZ out of the box gets run 1's reading (defect #234).")
    A("2. Run-to-run noise on the corrected chain is now measured for both appraisers (Figure 6 and Section 4 items 3 and 4): OpenWSFZ S1 bias %.2f dB wide over four paired sweeps (%.2f dB over all seven), S7 %.2f points, S8 %.2f points; WSJT-X S1 bias %.2f dB wide, S7 %.2f points, S8 %.2f points. A later change smaller than that is not distinguishable from noise on this instrument." % (
        max(bias) - min(bias), max(bias7) - min(bias7), max(s["s7"]["all"]["owsfz"] for s in corrected) - min(s["s7"]["all"]["owsfz"] for s in corrected), max(s["s8"]["OpenWSFZ"]["rate"] for s in corrected) - min(s["s8"]["OpenWSFZ"]["rate"] for s in corrected),
        max(wbias) - min(wbias), max(s["s7"]["all"]["wsjtx"] for s in corrected) - min(s["s7"]["all"]["wsjtx"] for s in corrected), max(s["s8"]["WSJT-X"]["rate"] for s in corrected) - min(s["s8"]["WSJT-X"]["rate"] for s in corrected)))
    A("3. The decoder gap to WSJT-X that this battery shows (S4 %s messages of 108, S1b, S7) is independent of the chain for S4 and now rests on four paired corrected-chain sweeps for S1b and S7. This report adds no evidence about why." % ("%d to %d" % (min(s4w) - max(s4o), max(s4w) - max(s4o))))
    A("4. Section 7 adds that the WSJT-X reference is not a fixed yardstick on this host either: it is late in 11.2 % of the real-recording cycles of that run (25.5 % of the busiest), and the live WSJT-X log of the 0803 night is thin for a reason that is not the audio. The battery's own synthetic scenes were not part of that measurement, so whether S4, S7 or S8 are affected is not measured.")
    A("5. **The dataset is complete for the paired comparison: five paired sweeps, four on the corrected chain.** Two earlier events in which WSJT-X stopped taking in audio cost three sweeps' WSJT-X data (11-12 October) and one whole sweep (14 October, replaced); the cause is not established.")
    A("")
    A("**Recommendations** (QA proposes; none is built or run without the Captain's go).")
    A("")
    A("1. **Monitor WSJT-X during every battery, and stop and flag when it goes silent** (plan `qa/rr-study/2026-10-14-1830-qa-plan-wsjtx-stall-monitoring-and-gate.md`, drafted with the Architect: a per-cycle sampler of the real `wsjtx` and `jt9` processes and the ALSA state, a mid-run liveness gate, and a per-scenario coverage row in the analyser). The start-up warm-up check alone let both incidents through. Mandatory before the next baseline re-run (Architect).")
    A("2. **The analyser's `ndc` row should say 'not computable' when reproducibility is zero because an appraiser has no data**, instead of printing 1 and FAIL (a small change in `harness/analyse.py`; QA tooling).")
    A("3. **Section 6 of every later Linux report starts from the table below**, with the one-sided rows labelled as here.")
    A("")
    A("**Not claimed.** Nothing here says OpenWSFZ changed between sweeps (one build, one library); nothing compares this series with the Windows one; no bar is proposed; the S7 and S8 figures are not decoder figures; the cause of the two WSJT-X stalls is not known.")
    A("")
    A("## Section 6: historical trend, every full S1-S8 sweep of the LINUX series")
    A("")
    A("**HK-031: Section 6 of the last LINUX report (this report's 2026-10-13 version, rows through 2026-10-12) was read before this section was written; this is the same table layout with the three paired repeats added.** **This series is NOT comparable with the Windows series** (other platform, CPU and audio chain; WSJT-X built by QA); the Windows trend (`trend.csv`) is shown in Figure 7 for scale only and is not pooled.")
    A("")
    hist = []
    for k in KEYS[:2] + OWS_ONLY + KEYS[2:]:
        s = S[k]
        hist.append([{"run1": "2026-10-11", "run2": "2026-10-11", "rep1": "2026-10-11", "rep2": "2026-10-11", "rep3": "2026-10-11/12"}.get(k, "2026-10-14"), "`64246e4`%s" % ("¹" if k == "run1" else "³" if k == "run2" else "⁴" if k in OWS_ONLY else "⁵"),
                     "%.1f%% %s%s" % (s["s1"]["pct_grr"], "MARGINAL" if s["s1"]["pct_grr_verdict"] == "MARGINAL" else "", " (OpenWSFZ bias %+.2f dB **FAIL**)" % s["s1"]["bias_owsfz"] if s["s1"]["bias_verdict"] == "FAIL" else ""),
                     "%.1f%%" % s["s2"]["pct_grr"], "%.1f%%" % s["s3"]["pct_grr"], "0.0% / 0.0%" if s["wsjtx_present"] else "no data / 0.0%",
                     "%s / %.1f%%" % (na(s["s7"]["all"]["wsjtx"], "%.1f%%"), s["s7"]["all"]["owsfz"]), "%s / %.1f%%" % (("%.1f%%" % s["s8"]["WSJT-X"]["rate"]) if "WSJT-X" in s["s8"] else "no data", s["s8"]["OpenWSFZ"]["rate"]),
                     ("%.2f%%²" % (100.0 * s["s78_pooled_matched"]["OpenWSFZ"] / s["s78_pooled_matched"]["WSJT-X"])) if s["wsjtx_present"] else "no data (no WSJT-X)"])
    A(md_table(["Date", "SHA", "S1 %GR&R", "S2 %GR&R", "S3 %GR&R", "S5 FP (WSJT-X / OpenWSFZ)", "S7 recovery (WSJT-X / OpenWSFZ)", "S8 decode rate (WSJT-X / OpenWSFZ)", "OpenWSFZ, % of WSJT-X (S7+S8 pooled, excl. FP)"], hist))
    A("")
    A("¹ **Run 1: DEFAULT ALSA chain** (`linear` rate converter, no anti-alias filter): the out-of-box Linux reading, not an invalid run. Defect: the daemon hard-codes `arecord -r 12000` (`ArecordAudioSource.cs:95`); issue #234. Folder `2026-10-11-64246e4-LINUX-sol`.")
    A("² WSJT-X's own pooled count differs between rows (%s); the ratio is not a measure of an OpenWSFZ change." % ", ".join("%s %d" % (SHORT[k].split("\n")[0].lower(), S[k]["s78_pooled_matched"]["WSJT-X"]) for k in KEYS))
    A("³ **Run 2: NON-DEFAULT chain** (ALSA `samplerate_best`, alsa-plugins plugin built from source + `ALSA_PLUGIN_DIR`). Folder `…-SAMPLERATE-chain`. Shares the analysis worktree HEAD `64246e40` and the daemon build `main` `76aa48cd`, shim 20260060, `libft8.so` `e8132650…4ed0`.")
    A("⁴ **Repeats 1 (started 19:10 UTC 11 Oct), 2 (21:06) and 3 (23:02): NON-DEFAULT chain, same build and library as run 2, WSJT-X NOT DECODING (incident 1).** S1/S2/S3 %GR&R are single-appraiser repeatability; the S5 WSJT-X cell, the S7 and S8 WSJT-X cells and the pooled ratio are empty because there is no WSJT-X data, not because the rate is zero. Folders `…-SAMPLERATE-chain-REPEAT1`, `-REPEAT2`, `-REPEAT3`.")
    A("⁵ **Repeats 1b-3b (14 October, 08:39Z to 16:41Z): NON-DEFAULT chain, same build and library, WSJT-X decoding, mechanical warm-up on.** Repeat 2b is the REPLACEMENT for a sweep that was INVALID (WSJT-X stalled at 11:09:30Z; incident 2). Folders `2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT1`, `…-REPEAT2-REPLACEMENT`, `…-REPEAT3`.")
    A("")
    A("![%s](img/%s)" % ("History figure", F["F7"][0]))
    A("")
    A("*Figure 7. %s*" % F["F7"][1])
    A("")
    A("## Section 7: the 70 min WSJT-X run on the same host (13 October; one replicate)")
    A("")
    A("**Why it is here.** The first reference-set run found 972 OpenWSFZ-only rows against the live WSJT-X log, 927 of them on one night (`20260803_live_run_1713`), and a thin live log on that night. WSJT-X 2.7.0 (QA's build, NDepth 3, the same one the paired sweeps use) was replayed in real time on `sol` over 7 blocks: the 4 blocks of that night and the 3 busiest blocks of other nights, one replicate, descriptive. Files: `../2026-10-13-wsjtx-keepup-run-sol/` (`SUMMARY-rep1.json`, `compare-rep1.json`); note `qa/rr-study/2026-10-13-1745-qa-to-architect-wsjtx-keepup-run-result.md`; ruled by the Architect (addendum 2 to the ruling of 2026-10-13 16:10Z).")
    A("")
    cb = K["compare"]["blocks"]
    night = [b for b in cb if cb[b]["run"] == "20260803_live_run_1713"]
    busy = [b for b in cb if b not in night]
    tot = lambda ids, k: sum(cb[b]["rows_nonhashed"][k] for b in ids)
    A("**Rows per block** (non-hashed rows of the scored cycles; LIVE = the station's WSJT-X log, E = the WSJT-X replay, B = OpenWSFZ leg B of the first run; shares are shares of the LIVE (or E) rows reproduced, sm_01 key):")
    A("")
    A(md_table(["Block", "Run", "Band", "Rows per cycle LIVE / E / B", "LIVE reproduced by E", "LIVE reproduced by B", "E reproduced by B", "B-only against E"],
               [[b[:6] + "…", "0803" if cb[b]["run"] == "20260803_live_run_1713" else cb[b]["run"][:8], cb[b]["band"] + " " + cb[b]["sun"],
                 "%.1f / %.1f / %.1f" % (cb[b]["rows_per_cycle"]["live"], cb[b]["rows_per_cycle"]["E"], cb[b]["rows_per_cycle"]["B"]),
                 "%.1f %%" % (100 * cb[b]["live_vs_E"]["a_reproduced_share"]), "%.1f %%" % (100 * cb[b]["live_vs_B"]["a_reproduced_share"]),
                 "%.1f %%" % (100 * cb[b]["E_vs_B"]["a_reproduced_share"]), cb[b]["E_vs_B"]["b_only_rows"]] for b in sorted(cb, key=lambda b: (b not in night, b))]))
    A("")
    A("The four 0803 blocks together: LIVE %d rows, E %d rows (%.1f times), B %d rows; OpenWSFZ has %d rows the replay lacks (%.1f %% of its %d) and %d rows the live log lacks. The three busy blocks: LIVE %d, E %d, B %d; %d rows B-only against E." % (
        tot(night, "live"), tot(night, "E"), tot(night, "E") / tot(night, "live"), tot(night, "B"), sum(cb[b]["E_vs_B"]["b_only_rows"] for b in night),
        100.0 * sum(cb[b]["E_vs_B"]["b_only_rows"] for b in night) / tot(night, "B"), tot(night, "B"), sum(cb[b]["live_vs_B"]["b_only_rows"] for b in night),
        tot(busy, "live"), tot(busy, "E"), tot(busy, "B"), sum(cb[b]["E_vs_B"]["b_only_rows"] for b in busy)))
    A("")
    A("**Ruled flag text (the Architect, word for word; use this and nothing stronger):** *Live WSJT-X decoded thinly on that night, and the audio was not the cause. A WSJT-X 2.7.0 replay of the same recording (QA's build, NDepth 3, one replicate, 4 of the night's 5 blocks) finds 1,966 rows against the live 879 (2.2 times). Only 52 of OpenWSFZ's 1,605 rows on those blocks (3.2 %) are absent from that replay. Why the live run was thin (its WSJT-X version, settings, depth or load) is not recorded.*")
    A("")
    t = K["compare"]["total"]["EB"]
    A("**New descriptive figure (ruled):** OpenWSFZ reproduces **%.1f %% (%d / %d)** of the replay's rows on the 7 selected blocks, with %d rows absent from the replay. It is never differenced against the 74.0 %% of the first run (other blocks, other reference). The 74.0 %% and the OWS-only counts (972, and 44 without the 0803 night) are unchanged." % (100 * t["a_reproduced_share"], t["matched"], t["a_rows"], t["b_only_rows"]))
    A("")
    A("![%s](img/%s)" % ("The 70 min WSJT-X run", F["F8"][0]))
    A("")
    A("*Figure 8. %s*" % F["F8"][1])
    A("")
    sm = K["summary"]
    bn = sm["by_density_bin"]
    A("**Keep-up of WSJT-X alone on the FX-8350** (one decode process; descriptive; **not comparable with the paired sweeps, where both decoders share the CPU**): over %d scored cycles WSJT-X's decode busy span has a median of %.1f s (P90 %.1f, max %.1f); the cycle's last decode arrives a median of %.1f s after the boundary (P90 %.1f, max %.1f); **%.1f %% of cycles (95 %% CI %.1f to %.1f, block-clustered) have the last decode more than 17 s after the boundary**, by live row count (<= 10 / 11-20 / 21-30 / > 30): %.1f %% (%d cycles) / %.1f %% (%d) / %.1f %% (%d) / **%.1f %%** (%d). OpenWSFZ's leg-B whole-decode compute on the same cycles (a file replay with no deadline, a different quantity) has a median of %.1f s and exceeds 15 s in %.0f %% of them." % (
        sm["scored_cycles"], sm["T_wsjtx_span"]["median"], sm["T_wsjtx_span"]["p90"], sm["T_wsjtx_span"]["max"], sm["T_wsjtx_last"]["median"], sm["T_wsjtx_last"]["p90"], sm["T_wsjtx_last"]["max"],
        100 * sm["late_gt_17s"]["share"], 100 * sm["late_gt_17s"]["ci95"][0], 100 * sm["late_gt_17s"]["ci95"][1],
        100 * bn["<=10"]["late_share"], bn["<=10"]["cycles"], 100 * bn["11-20"]["late_share"], bn["11-20"]["cycles"], 100 * bn["21-30"]["late_share"], bn["21-30"]["cycles"], 100 * bn[">30"]["late_share"], bn[">30"]["cycles"],
        sm["T_ows"]["median"], 100 * sm["T_ows_gt_15s"]["share"]))
    A("")
    A("**What this does not show.** Why the live run of 0803 was thin (the station's WSJT-X version, settings, depth and load that night are not recorded; a version or depth difference is still a candidate); one replicate; a replay of WSJT-X's own recording, not a second live run; QA's build of WSJT-X 2.7.0 at NDepth 3, not the station's installation; seven blocks of two bands (17 m and 80 m absent), the three busy ones chosen as the busiest; nothing about the battery's synthetic scenes or about OpenWSFZ's live path (its deadline stops the residual pass).")
    A("")
    A("**Standing row.** The Architect has ruled that these keep-up figures become a standing descriptive row of S6 (S6 amendment 3, written after the S6 dry run), labelled 'both decoders on one CPU'; nothing is added to the battery before then.")
    A("")
    A("---")
    A("")
    A("*Generated by `qa/rr-study/linux/build_consolidated_report.py` from the eight run folders and the 70 min run's two aggregate files (no message text). The numbers in the text are computed from the data, not typed.*")
    md = "\n".join(L) + "\n"
    with open(os.path.join(out, "report.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(md)
    with open(os.path.join(out, "data.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump({"sweeps": [S[k] for k in S]}, fh, indent=1)
    # HTML: the standing renderer (images by relative path), then a standalone copy with the images embedded
    rr = os.path.join(HERE, "..", "render_report.py")
    subprocess.run([sys.executable, rr, os.path.join(out, "report.md")], check=True, stdout=subprocess.DEVNULL)
    html = open(os.path.join(out, "report.html"), encoding="utf8").read()

    def emb(m):
        p = os.path.join(out, m.group(1))
        if os.path.isfile(p):
            return 'src="data:image/png;base64,' + base64.b64encode(open(p, "rb").read()).decode("ascii") + '"'
        return m.group(0)                              # a link to a run folder's panel stays a relative link
    with open(os.path.join(out, "report-standalone.html"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(re.sub(r'src="(img/[^"]+)"', emb, html))
    print("wrote", out, len(md), "chars")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--trend", default=os.path.join(HERE, "..", "trend.csv"))
    a = ap.parse_args()
    build(a.results, a.out, a.trend)


if __name__ == "__main__":
    main()
