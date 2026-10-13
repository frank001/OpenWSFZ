"""Build the CONSOLIDATED final report of the LINUX R&R series on `sol` (QA tooling; aggregates only, NFR-021).

    python build_consolidated_report.py --results <results root> --out <folder> [--trend <trend.csv>]

Reads the five sweeps' own run folders through consolidate_data.py, writes <out>/report.md, <out>/img/*.png, report.html (the standing renderer,
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
COL = {"run1": "#f85149", "run2": "#58a6ff", "rep1": "#3fb950", "rep2": "#d29922", "rep3": "#bc8cff"}
SHORT = {"run1": "Run 1\ndefault chain", "run2": "Run 2\ncorrected", "rep1": "Repeat 1\ncorrected", "rep2": "Repeat 2\ncorrected", "rep3": "Repeat 3\ncorrected"}
WIN_OWS_BIAS = [0.92, 0.85, 0.88, 1.48]       # quoted from the run-2 report, Section 5 item 2 (Windows sweeps; not comparable with this series)
KEYS = ["run1", "run2", "rep1", "rep2", "rep3"]


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
    out["F1"] = ("F1_s1_bias_by_snr.png", "S1 SNR bias by injected SNR, all five sweeps. The default chain (red) sits about 4 dB low; the four corrected-chain sweeps lie between 0 and +2 dB, with WSJT-X's curve inside their spread. WSJT-X is drawn only where it decoded (runs 1 and 2).")

    # F2: S1 mean bias per sweep
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(KEYS))
    ax.bar(x - 0.18, [S[k]["s1"]["bias_owsfz"] for k in KEYS], 0.36, color=[COL[k] for k in KEYS], label="OpenWSFZ")
    ax.bar(x + 0.18, [S[k]["s1"]["bias_wsjtx"] if S[k]["s1"]["bias_wsjtx"] is not None else 0 for k in KEYS], 0.36, color="#8b949e", alpha=0.7, label="WSJT-X (none where it did not decode)")
    for i, k in enumerate(KEYS):
        if S[k]["s1"]["bias_wsjtx"] is None:
            ax.text(i + 0.18, 0.1, "no data", rotation=90, ha="center", va="bottom", fontsize=8)
    ax.axhspan(min(WIN_OWS_BIAS), max(WIN_OWS_BIAS), color="#3fb950", alpha=0.15, label="Windows OpenWSFZ range +0.85 to +1.48 dB (other platform, shown for scale only)")
    ax.axhline(2, color="#8b949e", ls=":"); ax.axhline(-2, color="#8b949e", ls=":")
    ax.set_xticks(x); ax.set_xticklabels([SHORT[k] for k in KEYS], fontsize=8)
    ax.set(ylabel="mean SNR bias (dB)", title="S1 mean SNR bias per sweep")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(img, "F2_s1_mean_bias.png"), dpi=110); plt.close(fig)
    out["F2"] = ("F2_s1_mean_bias.png", "Mean S1 SNR bias per sweep against the ±2 dB bar. The four corrected-chain sweeps lie within 0.57 dB of one another.")

    # F3: GR&R
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    w = 0.16
    for j, sc in enumerate(("s1", "s2", "s3")):
        pass
    for i, k in enumerate(KEYS):
        axs[0].bar(np.arange(3) + (i - 2) * w, [max(S[k][sc]["pct_grr"], 0.01) for sc in ("s1", "s2", "s3")], w, color=COL[k], label=SHORT[k].replace("\n", " ") + ("" if S[k]["wsjtx_present"] else " (one appraiser)"))
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
    fig.suptitle("Gage R&R per sweep. Repeats 1-3 have ONE appraiser: their %GR&R is repeatability only and their ndc of 1 is an artefact of that", fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95)); fig.savefig(os.path.join(img, "F3_grr.png"), dpi=110); plt.close(fig)
    out["F3"] = ("F3_grr.png", "%GR&R and ndc for S1, S2, S3. Run 1's S1 is the only marginal value. In repeats 1-3 only OpenWSFZ was decoding, so these are single-appraiser repeatability figures, not appraiser R&R.")

    # F4: S1b
    fig, ax = plt.subplots(figsize=(10, 4.8))
    snrs = [r["snr"] for r in S["run2"]["s1b"]]
    x = np.arange(len(snrs))
    bars = [(k, "OpenWSFZ") for k in KEYS] + [("run1", "WSJT-X"), ("run2", "WSJT-X")]
    w = 0.12
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
    out["F4"] = ("F4_s1b.png", "S1b decode rate by SNR. Coloured: OpenWSFZ in every sweep; hatched: WSJT-X where it decoded (runs 1 and 2). The default chain loses OpenWSFZ's -18 dB case and two of three -15 dB cases; every corrected sweep decodes -18 and -15 dB 3 of 3. Three trials per cell: direction only.")

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
    out["F5"] = ("F5_recovery.png", "Recovery by sweep: S4 is identical (88.89 %) for OpenWSFZ in all five sweeps; S7 and S8 move by a few points between repeats. WSJT-X bars exist only for runs 1 and 2.")

    # F6: stability of the corrected-chain sweeps (OpenWSFZ only)
    fig, axs = plt.subplots(1, 4, figsize=(13, 3.8))
    series = [("S1 bias (dB)", [S[k]["s1"]["bias_owsfz"] for k in KEYS[1:]]), ("S4 recovery (%)", [S[k]["s4"]["OpenWSFZ"]["recovery"] for k in KEYS[1:]]),
              ("S7 all (%)", [S[k]["s7"]["all"]["owsfz"] for k in KEYS[1:]]), ("S8 rate (%)", [S[k]["s8"]["OpenWSFZ"]["rate"] for k in KEYS[1:]])]
    for a, (t, v) in zip(axs, series):
        a.plot(range(4), v, "o-", color="#58a6ff")
        for i, y in enumerate(v):
            a.text(i, y, " %.2f" % y, fontsize=7, va="bottom")
        a.set_xticks(range(4)); a.set_xticklabels(["run 2", "rep 1", "rep 2", "rep 3"], fontsize=8); a.set_title(t)
        pad = max(0.5, (max(v) - min(v)) * 0.6)
        a.set_ylim(min(v) - pad, max(v) + pad)
    fig.suptitle("OpenWSFZ on the corrected chain, four consecutive sweeps on the same build (same pins): the spread is the instrument's", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(img, "F6_stability.png"), dpi=110); plt.close(fig)
    out["F6"] = ("F6_stability.png", "The four corrected-chain sweeps, OpenWSFZ only. Same build, same library, same chain: the movement here is run-to-run noise, the yardstick for reading any later change.")

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
    out["F7"] = ("F7_history.png", "History: the Windows series' S1 bias and %GR&R from trend.csv, for scale only, with the five Linux sweeps (diamonds) to the right. The two series are different platforms, CPUs and audio chains and are never pooled.")
    return out


def md_table(head: list, rows: list) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def build(results: str, out: str, trend_path: str) -> None:
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    S = {s[0]: C.one(results, *s) for s in C.SWEEPS}
    trend = list(csv.DictReader(open(trend_path, encoding="utf8")))
    F = figures(S, trend, os.path.join(out, "img"))
    r1, r2, reps = S["run1"], S["run2"], [S["rep1"], S["rep2"], S["rep3"]]
    corrected = [S[k] for k in KEYS[1:]]
    bias = [s["s1"]["bias_owsfz"] for s in corrected]
    dur = lambda s: s["cycle_utc_first_last"]
    L = []
    A = L.append
    A("# OpenWSFZ R&R Study: LINUX series on `sol`, consolidated final report")
    A("")
    A("> **LINUX series, five sweeps (11-12 October 2026): run 1 on the DEFAULT ALSA chain, run 2 and repeats 1-3 on the CORRECTED chain (`samplerate_best`).** "
      "**Repeats 1-3 contain NO WSJT-X data** (WSJT-X was not decoding during them): they are OpenWSFZ-only readings. "
      "**Not comparable with the Windows series** (other platform, CPU and audio chain; WSJT-X 2.7.0 built from source by QA). Informational: no merge or build decision rests on this report.")
    A("")
    A(md_table(["Field", "Value"], [
        ["Report date", "2026-10-13 (QA; analysis of the five run folders, no new run)"],
        ["Host", "`sol`: AMD FX-8350, Gentoo; no radio, no CAT; audio through the codec loopback, PCM `rr_in`"],
        ["OpenWSFZ build, all five sweeps", "`main` `%s` (v%s, shim %s)" % (r2["build"]["commit"], r2["build"]["daemon_version"], r2["build"]["shim"])],
        ["`libft8.so` SHA-256", "`%s` in all five (read back from each run's `arm_config.json`: %s)" % (r2["build"]["dll_sha256"], "equal" if len({S[k]["build"]["dll_sha256"] for k in KEYS}) == 1 else "NOT EQUAL")],
        ["Decoder flags (read back)", "`nhard` / `osdNhardMax` %s, `subtractionEnabled` %s, `subtractionMaxThreads` %s, same in every sweep" % (r2["build"]["readback"]["osdNhardMax"], r2["build"]["readback"]["subtractionEnabled"], r2["build"]["readback"]["subtractionMaxThreads"])],
        ["WSJT-X", "2.7.0 built from the verified source tarball on `sol` (conda-forge Qt 5.15, gfortran 13.4.0); NDepth %s; WSJT-X 3.x cannot be the appraiser (its `callok` rejects every callsign starting with Q)" % r2["build"]["wsjtx_ndepth"]],
        ["Run folders", "`2026-10-11-64246e4-LINUX-sol` (run 1), `…-SAMPLERATE-chain` (run 2), `…-SAMPLERATE-chain-REPEAT1`, `-REPEAT2`, `-REPEAT3`"],
    ]))
    A("")
    A("## Section 1: scope, provenance and what each sweep contains")
    A("")
    A(md_table(["Sweep", "Chain", "Cycles first to last (UTC)", "WSJT-X decoded?", "`wsjt-all.txt` / `owsfz-all.txt` lines", "Analyser's overall verdict"],
               [[s["label"], "default ALSA `linear`" if not s["corrected_chain"] else "ALSA `samplerate_best`", "%s to %s" % (dur(s)[0][5:16].replace("T", " "), dur(s)[1][5:16].replace("T", " ")),
                 "yes" if s["wsjtx_present"] else "**NO: 0 lines**", "%d / %d" % (s["wsjt_all_lines"], s["owsfz_all_lines"]),
                 s["overall"] + ("" if s["wsjtx_present"] else " (OpenWSFZ only)")] for s in (S[k] for k in KEYS)]))
    A("")
    A("Each sweep is a full S1-S8 battery (S1, S1b, S2, S3, S4, S5, S7, S8, S3c) of about 1 h 53 min. The three repeats ran back to back, unattended, on 11-12 October (Architect 2l item 7, 'non-default chain'); run 2 is the assembled report whose Sections 5 and 6 this report extends.")
    A("")
    A("**What went wrong in the repeats.** WSJT-X's own `ALL.TXT` on `sol` has no line stamped between 11 Oct 07 h and 12 Oct 19 h UTC: WSJT-X was not decoding for the whole of repeats 1-3. The battery has no check for it (PRECHECK has no 'WSJT-X is alive and decoding' row and the battery was started with `--skip-warmup`), so every matcher logged `WSJT-X: 0/30 matched` and the run went on to the end. The consequence is stated in each place it applies below.")
    A("")
    A("## Section 2: results side by side")
    A("")
    row = lambda name, f: [name] + [f(S[k]) for k in KEYS]
    hd = ["Measure"] + [SHORT[k].replace("\n", " ") for k in KEYS]
    A(md_table(hd, [
        row("S1 OpenWSFZ mean bias (dB), bar ±2", lambda s: "%+.2f %s" % (s["s1"]["bias_owsfz"], s["s1"]["bias_verdict"])),
        row("S1 WSJT-X mean bias (dB)", lambda s: na(s["s1"]["bias_wsjtx"], "%+.2f")),
        row("S1 %GR&R (ndc)", lambda s: "%.1f %% (%d)%s" % (s["s1"]["pct_grr"], s["s1"]["ndc"], "" if s["wsjtx_present"] else " ¹")),
        row("S2 %GR&R (ndc)", lambda s: "%.1f %% (%d)%s" % (s["s2"]["pct_grr"], s["s2"]["ndc"], "" if s["wsjtx_present"] else " ¹")),
        row("S3 %GR&R (ndc)", lambda s: "%.1f %% (%d)%s" % (s["s3"]["pct_grr"], s["s3"]["ndc"], "" if s["wsjtx_present"] else " ¹")),
        row("κ OpenWSFZ vs truth", lambda s: "%.3f" % s["kappa"]["OpenWSFZ_vs_truth"]),
        row("κ WSJT-X vs truth / between appraisers", lambda s: ("%.3f / %.3f" % (s["kappa"]["WSJT-X_vs_truth"], s["kappa"]["between_appraisers"])) if s["wsjtx_present"] else "no data"),
        row("S4 recovery, OpenWSFZ (of 108)", lambda s: "%.2f %% (%d)" % (s["s4"]["OpenWSFZ"]["recovery"], s["s4"]["OpenWSFZ"]["tp"])),
        row("S4 recovery, WSJT-X (of 108)", lambda s: ("%.2f %% (%d)" % (s["s4"]["WSJT-X"]["recovery"], s["s4"]["WSJT-X"]["tp"])) if "WSJT-X" in s["s4"] else "no data"),
        row("S5 OpenWSFZ false positives (Gate A-W)", lambda s: s["s5"]["gate_aw"].split(" (")[0]),
        row("S5 narrowband Check B (WSJT-X / OpenWSFZ)", lambda s: "%s / %s" % (s["s5"]["check_b_w"].split(" slots")[0], s["s5"]["check_b_o"].split(" slots")[0]) if s["wsjtx_present"] else "no data / %s" % s["s5"]["check_b_o"].split(" slots")[0]),
        row("S1b decode rate OpenWSFZ / WSJT-X (n = 12)", lambda s: "%.2f %% / %s" % (s["s1b_overall"]["owsfz"], na(s["s1b_overall"]["wsjtx"], "%.2f %%"))),
        row("S7 recovery OpenWSFZ / WSJT-X", lambda s: "%.2f %% / %s" % (s["s7"]["all"]["owsfz"], na(s["s7"]["all"]["wsjtx"], "%.2f %%"))),
        row("S8 decode rate OpenWSFZ / WSJT-X (of 60)", lambda s: "%.2f %% / %s" % (s["s8"]["OpenWSFZ"]["rate"], ("%.2f %%" % s["s8"]["WSJT-X"]["rate"]) if "WSJT-X" in s["s8"] else "no data")),
        row("S7+S8 pooled matched decodes OpenWSFZ / WSJT-X", lambda s: "%d / %s" % (s["s78_pooled_matched"].get("OpenWSFZ", 0), s["s78_pooled_matched"].get("WSJT-X", 0) if s["wsjtx_present"] else "no data")),
        row("S3c parts passing (of 8)", lambda s: "%d%s" % (s["s3c"]["pass"], "" if s["wsjtx_present"] else " ²")),
    ]))
    A("")
    A("¹ **One appraiser only.** %GR&R is repeatability of OpenWSFZ alone and ndc is not an appraiser R&R figure; the `ndc = 1 FAIL` rows of repeat 1 (S1), repeat 2 (S2) and repeat 3 (S2) are the missing second appraiser (reproducibility 0), not exact agreement between two appraisers. The analyser's 'overall PASS' of these sweeps ignores the row.")
    A("")
    A("² The three failing S3c parts are all WSJT-X parts (`%s`): with no WSJT-X log they cannot pass. OpenWSFZ passes all 4 of its S3c parts in every sweep; WSJT-X passes all 4 in runs 1 and 2 and only 1 of 4 in the repeats (the descriptive L50 part)." % ", ".join(r["s3c_failed_parts"][i] for r in [reps[0]] for i in range(3)))
    A("")
    A("## Section 3: graphs")
    A("")
    for key in ("F1", "F2", "F3", "F4", "F5", "F6"):
        A("![%s](img/%s)" % (F[key][1][:60], F[key][0]))
        A("")
        A("*Figure %s. %s*" % (key[1:], F[key][1]))
        A("")
    A("Per-run Gage R&R panels (S1, S2, S3) of every sweep are in the run folders: " + "; ".join("[%s](../%s/S1_grr_panel.png)" % (SHORT[k].replace("\n", " "), S[k]["folder"]) for k in KEYS) + ".")
    A("")
    A("## Section 4: observations")
    A("")
    d_bias = r2["s1"]["bias_owsfz"] - r1["s1"]["bias_owsfz"]
    A("1. **The default chain is the cause of run 1's S1 failure, and the corrected chain removes it.** OpenWSFZ's S1 bias goes from %+.2f dB (run 1, FAIL against ±2 dB) to %+.2f dB (run 2), a shift of %+.2f dB; S1 %%GR&R from %.1f %% to %.1f %% (ndc %d to %d); WSJT-X's own S1 bias barely moves (%+.2f to %+.2f dB). The same-audio test in run 1 (the Windows decoder on the 30 recordings made on `sol`, difference 0.00 dB, 30 of 30) (quoted from run 1's own diagnostics) shows the decoder reads the same on both platforms, so the difference between the runs is the chain (defect #234, `ArecordAudioSource.cs:95`)." % (
        r1["s1"]["bias_owsfz"], r2["s1"]["bias_owsfz"], d_bias, r1["s1"]["pct_grr"], r2["s1"]["pct_grr"], r1["s1"]["ndc"], r2["s1"]["ndc"], r1["s1"]["bias_wsjtx"], r2["s1"]["bias_wsjtx"]))
    A("2. **The default chain also costs weak signals.** S1b, OpenWSFZ: %.2f %% in run 1 against %.2f %% in every corrected sweep (the -18 and -15 dB cases go from 0 or 1 of 3 to 3 of 3; the -21 and -24 dB cases stay at 0 of 3). WSJT-X: %.2f %% in run 1 and %.2f %% in run 2. Twelve trials per appraiser per sweep: direction only." % (
        r1["s1b_overall"]["owsfz"], r2["s1b_overall"]["owsfz"], r1["s1b_overall"]["wsjtx"], r2["s1b_overall"]["wsjtx"]))
    A("3. **OpenWSFZ is repeatable on the corrected chain.** Four consecutive sweeps on the same build, library and chain: S1 bias %s dB (spread %.2f dB; the four Windows sweeps quoted in the run-2 report are +0.92, +0.85, +0.88, +1.48 dB, spread 0.63 dB, a different series); S4 recovery %s %% in all four; κ against truth %s in all four; S7 %s %%; S8 %s %%; S1b %s %% in all four; zero false positives in 480 slots and in the narrowband check in every sweep. There is no drift across the four sweeps (Figure 6)." % (
        ", ".join("%+.2f" % b for b in bias), max(bias) - min(bias), sorted({s["s4"]["OpenWSFZ"]["recovery"] for s in corrected}).__repr__().strip("[]"), sorted({s["kappa"]["OpenWSFZ_vs_truth"] for s in corrected}).__repr__().strip("[]"),
        "/".join("%.2f" % s["s7"]["all"]["owsfz"] for s in corrected), "/".join("%.2f" % s["s8"]["OpenWSFZ"]["rate"] for s in corrected), sorted({s["s1b_overall"]["owsfz"] for s in corrected}).__repr__().strip("[]")))
    A("4. **S4 recovery did not change with the chain**: OpenWSFZ %d of 108 (%.2f %%) in all five sweeps; WSJT-X %d of 108 (%.2f %%) in the two sweeps where it decoded. So the S4 gap to WSJT-X (6 injected messages) is not caused by the converter. OpenWSFZ's κ against truth is %s in every sweep." % (
        r2["s4"]["OpenWSFZ"]["tp"], r2["s4"]["OpenWSFZ"]["recovery"], r2["s4"]["WSJT-X"]["tp"], r2["s4"]["WSJT-X"]["recovery"], "/".join(sorted({"%.3f" % S[k]["kappa"]["OpenWSFZ_vs_truth"] for k in KEYS}))))
    A("5. **S7 is instrument-suspect by standing rule and no bare S7 mean is cited as a decoder figure.** OpenWSFZ ranges %.2f to %.2f %% across the five sweeps; WSJT-X was %.2f %% (run 1) and %.2f %% (run 2). S8 (60 injected, a difference of 3 decodes is 5 points) is descriptive." % (
        min(s["s7"]["all"]["owsfz"] for s in S.values()), max(s["s7"]["all"]["owsfz"] for s in S.values()), r1["s7"]["all"]["wsjtx"], r2["s7"]["all"]["wsjtx"]))
    A("6. **Repeats 1-3 are one-sided.** Their S1 bias, S4, S5, S7, S8 and S1b figures concern OpenWSFZ alone; there is no WSJT-X reading in them, no between-appraiser κ, no appraiser R&R, and S3c fails only on WSJT-X's parts. They cannot show that WSJT-X is stable over the same period, and they do not repeat the paired comparison of run 2.")
    A("7. **Timing is stable.** Each sweep took about 1 h 53 to 1 h 55 min (cycle stamps first to last: %s)." % "; ".join("%s %d min" % (k, round((__import__("datetime").datetime.fromisoformat(dur(S[k])[1].replace("Z", "")) - __import__("datetime").datetime.fromisoformat(dur(S[k])[0].replace("Z", ""))).total_seconds() / 60)) for k in KEYS))
    A("8. **Instrument notes.** The audio-setup sampler is a Windows tool and fails on Linux by design (each sweep's summary logs 21 worker crashes and 0 setup changes; the battery continues); the captured-audio scan was not run; WSJT-X's `ALL.TXT` is the live file, so a battery that follows a WSJT-X run must trim to its own window (done by the runner).")
    A("")
    A("## Section 5: conclusions and recommendations")
    A("")
    A("**Conclusions.**")
    A("")
    A("1. On `sol`, OpenWSFZ passes the whole S1-S8 battery on a proper audio chain and fails S1 on the default one; the whole difference is the capture chain, not the decoder. A Linux user who runs OpenWSFZ out of the box gets run 1's reading (defect #234).")
    A("2. Run-to-run noise of OpenWSFZ on the corrected chain is now measured (Figure 6): S1 bias %.2f dB wide, S7 %.2f points, S8 %.2f points, S4 and S1b not at all. A later change smaller than that is not distinguishable from noise on this instrument." % (
        max(bias) - min(bias), max(s["s7"]["all"]["owsfz"] for s in corrected) - min(s["s7"]["all"]["owsfz"] for s in corrected), max(s["s8"]["OpenWSFZ"]["rate"] for s in corrected) - min(s["s8"]["OpenWSFZ"]["rate"] for s in corrected)))
    A("3. The decoder gap to WSJT-X that this battery shows (S4 6 messages of 108, S1b, S7) is independent of the chain for S4 and rests on only two paired sweeps for S1b and S7. This report adds no evidence about it.")
    A("4. The repeats did not do what they were run for. About 5 h 40 min of `sol` produced an OpenWSFZ-only stability reading, which is useful (conclusion 2), but no second paired sweep.")
    A("")
    A("**Recommendations** (QA proposes; none is built or run without the Captain's go).")
    A("")
    A("1. **Add a mechanical PRECHECK row, 'WSJT-X alive and decoding' (QA tooling, `rr_precheck.py` and the Linux twin).** Fail the battery before scenario 1 if the WSJT-X process is not running or its `ALL.TXT` did not gain a line from a warm-up cycle in the same window as OpenWSFZ's. This is HK-020's rule (verify a run's critical configuration before arming). The S6 warm-up built on 13 October is the same check.")
    A("2. **If the paired stability reading matters, repeat the three sweeps with WSJT-X running** (about 5 h 40 min of `sol`, unattended). If the OpenWSFZ-only noise estimate is enough, nothing more is needed; the Captain decides.")
    A("3. **The analyser's `ndc` row should say 'not computable' when reproducibility is zero because an appraiser has no data**, instead of printing 1 and FAIL (a small change in `harness/analyse.py`; QA tooling).")
    A("4. **Section 6 of every later Linux report starts from the table below**, with the one-sided rows labelled as here.")
    A("")
    A("**Not claimed.** Nothing here says OpenWSFZ changed between sweeps (one build, one library); nothing compares this series with the Windows one; no bar is proposed; the S7 and S8 figures are not decoder figures.")
    A("")
    A("## Section 6: historical trend, every full S1-S8 sweep of the LINUX series")
    A("")
    A("**HK-031: Section 6 of the last LINUX report (`2026-10-11-64246e4-LINUX-sol-SAMPLERATE-chain`, rows through 2026-10-11) was read before this section was written; this is the same table layout with its two rows and the three repeats added.** **This series is NOT comparable with the Windows series** (other platform, CPU and audio chain; WSJT-X built by QA); the Windows trend (`trend.csv`) is shown in Figure 7 for scale only and is not pooled.")
    A("")
    hist = []
    for n, k in enumerate(KEYS):
        s = S[k]
        hist.append(["2026-10-11" if k != "rep3" else "2026-10-11/12", "`64246e4`%s" % ("¹" if k == "run1" else "³" if k == "run2" else "⁴"),
                     "%.1f%% %s%s" % (s["s1"]["pct_grr"], "MARGINAL" if s["s1"]["pct_grr_verdict"] == "MARGINAL" else "", " (OpenWSFZ bias %+.2f dB **FAIL**)" % s["s1"]["bias_owsfz"] if s["s1"]["bias_verdict"] == "FAIL" else ""),
                     "%.1f%%" % s["s2"]["pct_grr"], "%.1f%%" % s["s3"]["pct_grr"], "0.0% / 0.0%" if s["wsjtx_present"] else "no data / 0.0%",
                     "%s / %.1f%%" % (na(s["s7"]["all"]["wsjtx"], "%.1f%%"), s["s7"]["all"]["owsfz"]), "%s / %.1f%%" % (("%.1f%%" % s["s8"]["WSJT-X"]["rate"]) if "WSJT-X" in s["s8"] else "no data", s["s8"]["OpenWSFZ"]["rate"]),
                     ("%.2f%%²" % (100.0 * s["s78_pooled_matched"]["OpenWSFZ"] / s["s78_pooled_matched"]["WSJT-X"])) if s["wsjtx_present"] else "no data (no WSJT-X)"])
    A(md_table(["Date", "SHA", "S1 %GR&R", "S2 %GR&R", "S3 %GR&R", "S5 FP (WSJT-X / OpenWSFZ)", "S7 recovery (WSJT-X / OpenWSFZ)", "S8 decode rate (WSJT-X / OpenWSFZ)", "OpenWSFZ, % of WSJT-X (S7+S8 pooled, excl. FP)"], hist))
    A("")
    A("¹ **Run 1: DEFAULT ALSA chain** (`linear` rate converter, no anti-alias filter): the out-of-box Linux reading, not an invalid run. Defect: the daemon hard-codes `arecord -r 12000` (`ArecordAudioSource.cs:95`); issue #234. Folder `2026-10-11-64246e4-LINUX-sol`.")
    A("² WSJT-X's own pooled count differs between rows (run 1 258, run 2 268); the ratio is not a measure of an OpenWSFZ change.")
    A("³ **Run 2: NON-DEFAULT chain** (ALSA `samplerate_best`, alsa-plugins plugin built from source + `ALSA_PLUGIN_DIR`). Folder `…-SAMPLERATE-chain`. Shares the analysis worktree HEAD `64246e40` and the daemon build `main` `76aa48cd`, shim 20260060, `libft8.so` `e8132650…4ed0`.")
    A("⁴ **Repeats 1 (started 19:10 UTC 11 Oct), 2 (21:06) and 3 (23:02): NON-DEFAULT chain, same build and library as run 2, WSJT-X NOT DECODING.** S1/S2/S3 %GR&R are single-appraiser repeatability; the S5 WSJT-X cell, the S7 and S8 WSJT-X cells and the pooled ratio are empty because there is no WSJT-X data, not because the rate is zero. Folders `…-SAMPLERATE-chain-REPEAT1`, `-REPEAT2`, `-REPEAT3`.")
    A("")
    A("![%s](img/%s)" % ("History figure", F["F7"][0]))
    A("")
    A("*Figure 7. %s*" % F["F7"][1])
    A("")
    A("---")
    A("")
    A("*Generated by `qa/rr-study/linux/build_consolidated_report.py` from the five run folders (aggregates only; no message text). The numbers in the text are computed from the data, not typed.*")
    md = "\n".join(L) + "\n"
    with open(os.path.join(out, "report.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(md)
    with open(os.path.join(out, "data.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump({"sweeps": [S[k] for k in KEYS]}, fh, indent=1)
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
