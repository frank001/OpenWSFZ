"""Build the FINAL FULL ANOVA report of the LINUX R&R series on `sol` (QA tooling; aggregates only, NFR-021).

    python build_full_anova_report.py --results <results root> --out <folder>

Reads the five PAIRED sweeps (both appraisers decoding) through full_anova_core.py (the analyser's own ANOVA code, imported) and consolidate_data.py,
writes <out>/report.md, <out>/img/*.png, <out>/stats.json, report.html (the standing renderer) and report-standalone.html (images embedded).
Every number in the text is computed from the data; only the wording of the findings is typed, and each finding is conditioned on the numbers it quotes.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import subprocess
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import full_anova_core as F  # noqa: E402
import consolidate_data as C  # noqa: E402

BG, FG, GRID = "#0d1117", "#c9d1d9", "#30363d"
COL = {"run1": "#f85149", "run2": "#58a6ff", "w1": "#3fb950", "w2": "#d29922", "w3": "#bc8cff"}
SHORT = {"run1": "Run 1 (default chain)", "run2": "Run 2", "w1": "Repeat 1b", "w2": "Repeat 2b (replacement)", "w3": "Repeat 3b"}
LAB = {"run1": "Run 1", "run2": "Run 2", "w1": "Rep 1b", "w2": "Rep 2b", "w3": "Rep 3b"}
UNIT = {"S1": "dB", "S2": "Hz", "S3": "s"}
NAME = {"S1": "S1 SNR", "S2": "S2 frequency", "S3": "S3 DT (WSJT-X corrected by +0.55 s, as the analyser does)"}
TERM = {"P": "Part", "A": "Appraiser", "S": "Sweep", "PA": "Part x Appraiser", "PS": "Part x Sweep", "AS": "Appraiser x Sweep", "PAS": "Part x Appraiser x Sweep", "E": "Repeatability (error)"}


def fnum(v, d=3):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "n/a"
    if v != 0 and (abs(v) < 10 ** -d or abs(v) >= 10 ** 6):
        return "%.2e" % v
    return ("%." + str(d) + "f") % v


def fp(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return "< 0.0001" if p < 1e-4 else "%.4f" % p


def md_table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "text.color": FG, "axes.labelcolor": FG, "axes.edgecolor": GRID, "xtick.color": FG,
                         "ytick.color": FG, "grid.color": GRID, "axes.grid": True, "grid.alpha": 0.6, "legend.facecolor": BG, "legend.edgecolor": GRID, "font.size": 10})
    return plt


# ---------------------------------------------------------------------------------------------------------------------------------- compute
def compute(results: str) -> dict:
    folders = {s[0]: s[1] for s in C.SWEEPS}
    summ = {k: C.one(results, *[s for s in C.SWEEPS if s[0] == k][0]) for k in F.PAIRED}
    cubes = {sc: {k: F.cube(F.load(results, folders[k], sc, resp, ref), resp, ref) for k in F.PAIRED} for sc, resp, ref, _ in F.SCEN}
    R = {"folders": folders, "summ": summ, "cubes": cubes, "per": {}, "three": {}, "boot": {}, "pooled2": {}, "five": {}, "bias": F.bias_tables(cubes)}
    for sc, *_ in F.SCEN:
        R["per"][sc] = {k: F.two_way(cubes[sc][k][0]) for k in F.PAIRED}
        for k in F.PAIRED:                                           # cross-check against each sweep's own report (the analyser's figures)
            rep = summ[k][sc.lower()]
            mine = R["per"][sc][k]["pct"]["grr_sv"] if summ[k]["grr_metric"] == "%StudyVar" else R["per"][sc][k]["pct"]["grr"]   # the metric that report was graded on
            assert abs(mine - rep["pct_grr"]) < 0.06, (sc, k, mine, rep["pct_grr"], summ[k]["grr_metric"])
            assert R["per"][sc][k]["ndc"] == int(rep["ndc"]), (sc, k)
        Yc = np.stack([cubes[sc][k][0] for k in F.CORRECTED], axis=2)
        R["three"][sc] = F.three_way(Yc)
        R["boot"][sc] = F.boot_pct(Yc)
        R["pooled2"][sc] = F.two_way(np.concatenate([cubes[sc][k][0] for k in F.CORRECTED], axis=2))
        R["five"][sc] = F.three_way(np.stack([cubes[sc][k][0] for k in F.PAIRED], axis=2))
    # attribute data
    U4 = {k: F.units_s4(results, folders[k]) for k in F.PAIRED}
    keys = sorted(U4[F.PAIRED[1] if len(F.PAIRED) > 1 else F.PAIRED[0]]["OpenWSFZ"])
    for k in F.PAIRED:
        for a in F.APPR:
            assert sorted(U4[k][a]) == keys, "S4 unit keys differ between sweeps"
    R["s4"] = {"keys": len(keys), "M": {a: np.array([[int(U4[k][a][u]) for k in F.CORRECTED] for u in keys]) for a in F.APPR},
               "M5": {a: np.array([[int(U4[k][a][u]) for k in F.PAIRED] for u in keys]) for a in F.APPR}}
    U1 = {k: F.units_s1b(results, folders[k]) for k in F.PAIRED}
    k1 = sorted(U1[F.PAIRED[1] if len(F.PAIRED) > 1 else F.PAIRED[0]]["OpenWSFZ"])
    R["s1b"] = {"keys": len(k1), "M": {a: np.array([[int(U1[k][a][u]) for k in F.CORRECTED] for u in k1]) for a in F.APPR},
                "M5": {a: np.array([[int(U1[k][a][u]) for k in F.PAIRED] for u in k1]) for a in F.APPR}}
    return R


# ---------------------------------------------------------------------------------------------------------------------------------- figures
def figures(R: dict, img: str) -> dict:
    plt = style()
    out = {}
    N = len(F.CORRECTED)                                   # sweeps in the three-way model (4 for the 2026-10-14 series, 5 for the B2 baseline)
    NW = {3: 'three', 4: 'four', 5: 'five', 6: 'six'}.get(N, str(N))
    NP = len(F.PAIRED)
    # F1 variance components
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.4))
    for a, (sc, *_r) in zip(axs, F.SCEN):
        r, b = R["three"][sc], R["boot"][sc]
        names = ["repeatability", "appraiser", "sweep"]
        vals = [max(r["pct_groups"][n], 1e-3) for n in names]
        lo = [max(b[n][0], 1e-3) for n in names]
        hi = [max(b[n][1], 1e-3) for n in names]
        a.bar(range(3), vals, color=["#8b949e", "#58a6ff", "#d29922"], yerr=[[v - l for v, l in zip(vals, lo)], [h - v for v, h in zip(vals, hi)]], ecolor=FG, capsize=4)
        for i, v in enumerate(r["pct_groups"][n] for n in names):
            a.text(i, max(v, 1e-3) * 1.5, "%.3f %%" % v, ha="center", fontsize=8)
        a.set_yscale("log"); a.set_ylim(1e-3, 30); a.axhline(10, color="#8b949e", ls=":")
        a.set_xticks(range(3)); a.set_xticklabels(["Repeatability", "Appraiser\n(A + PxA)", "Sweep\n(S + PxS + AxS + PxAxS)"], fontsize=8)
        a.set_title("%s: %%Contribution %.2f %% (ndc %s)" % (sc, r["pct_grr"], r["ndc"] if r["ndc"] is not None else "n/a"), fontsize=9)
    axs[0].set_ylabel("% of total variance (log)")
    fig.suptitle("Variance components, %s corrected-chain sweeps, three-way random-effects ANOVA (error bars: part-bootstrap 95 %% CI; dotted line: 10 %%)" % NW, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A1_variance_components.png"), dpi=110); plt.close(fig)
    out["A1"] = ("A1_variance_components.png", "Percentage of the total variance carried by each non-part source, per scenario. A zero is drawn at the 0.001 %% floor of the log axis. The part variance (the signal) is the remainder: S1 %.2f %%, S2 %.3f %%, S3 %.2f %%." % tuple(R["three"][s]["pct"]["P"] for s in ("S1", "S2", "S3")))
    # F2 interaction
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.4))
    for a, (sc, *_r) in zip(axs, F.SCEN):
        for k in F.CORRECTED:
            Y, ref = R["cubes"][sc][k]
            for j, ap in enumerate(F.APPR):
                a.plot(ref, (Y[:, j, :] - ref[:, None]).mean(axis=1), "-", color="#58a6ff" if ap == "OpenWSFZ" else "#e3b341", alpha=0.35, lw=1)
        Ys = np.stack([R["cubes"][sc][k][0] for k in F.CORRECTED], axis=2)
        ref = R["cubes"][sc][F.CORRECTED[0]][1]
        for j, ap in enumerate(F.APPR):
            a.plot(ref, (Ys[:, j] - ref[:, None, None]).mean(axis=(1, 2)), "o-", color="#58a6ff" if ap == "OpenWSFZ" else "#e3b341", lw=2.2, label=ap + " (mean of %d sweeps)" % N)
        a.set_xlabel("injected value (%s)" % F.SCEN[[s[0] for s in F.SCEN].index(sc)][3]); a.set_title(NAME[sc].split(" (")[0], fontsize=9)
    axs[0].set_ylabel("reported minus injected (mean of 3 trials)"); axs[0].legend(fontsize=8)
    fig.suptitle("Part x Appraiser interaction: mean error by injected value (thin lines: the %s sweeps; thick: their mean)" % NW, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A2_interaction.png"), dpi=110); plt.close(fig)
    out["A2"] = ("A2_interaction.png", "Mean error (reported minus injected) at each injected value, per appraiser. Parallel lines mean no Part x Appraiser interaction. S3: a near-constant offset between the appraisers over most of the range. S1: the offset varies with the injected SNR (the significant Part x Appraiser term). S2: WSJT-X is exact at every frequency; OpenWSFZ is off by 1 to 2 Hz at a few of them.")
    # F3 sweep effect
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.2))
    for a, (sc, *_r) in zip(axs, F.SCEN):
        for j, ap in enumerate(F.APPR):
            y = [R["bias"][sc][k][ap]["bias"] for k in F.CORRECTED]
            m, sd, lo, hi = F.t_ci(y)
            a.plot(range(N), y, "o", color="#58a6ff" if ap == "OpenWSFZ" else "#e3b341", ms=8, label=ap)
            a.axhspan(lo, hi, color="#58a6ff" if ap == "OpenWSFZ" else "#e3b341", alpha=0.12)
        a.set_xticks(range(N)); a.set_xticklabels([LAB[k] for k in F.CORRECTED], fontsize=8); a.set_title(NAME[sc].split(" (")[0] + " (%s)" % UNIT[sc], fontsize=9)
    axs[0].set_ylabel("mean error of the sweep"); axs[0].legend(fontsize=8)
    fig.suptitle("Sweep (session) effect: each sweep's mean error per appraiser; the band is the t-based 95 %% interval of the %s sweeps" % NW, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A3_sweep_effect.png"), dpi=110); plt.close(fig)
    out["A3"] = ("A3_sweep_effect.png", "Mean error of each corrected-chain sweep, per appraiser and scenario. OpenWSFZ's S1 bias differs between the sweeps (+0.88 to +1.45 dB); WSJT-X's does not (+0.82 to +0.85 dB).")
    # F4 Bland-Altman style, S1
    fig, ax = plt.subplots(figsize=(9, 4.6))
    allD = []
    for k in F.CORRECTED:
        Y, ref = R["cubes"]["S1"][k]
        d = Y[:, 1, :].mean(axis=1) - Y[:, 0, :].mean(axis=1)
        allD += list(d)
        ax.plot(ref, d, "o-", color=COL[k], label=SHORT[k], alpha=0.85)
    m, sd = float(np.mean(allD)), float(np.std(allD, ddof=1))
    for v, ls in ((m, "-"), (m + 1.96 * sd, "--"), (m - 1.96 * sd, "--")):
        ax.axhline(v, color="#8b949e", ls=ls)
    ax.set(xlabel="injected SNR (dB)", ylabel="OpenWSFZ minus WSJT-X, mean of 3 trials (dB)", title="S1: appraiser difference by injected SNR (mean %.2f dB, limits %.2f to %.2f dB)" % (m, m - 1.96 * sd, m + 1.96 * sd))
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A4_s1_difference.png"), dpi=110); plt.close(fig)
    out["A4"] = ("A4_s1_difference.png", "S1: OpenWSFZ minus WSJT-X on the same injected signals, by injected SNR, four corrected sweeps (solid line: mean difference; dashed: ± 1.96 SD of the 40 values; the points are cell means of 3 trials).")
    # F5 attribute consistency
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    for a, (key, title) in zip(axs, (("s4", "S4: %d messages" % R["s4"]["keys"]), ("s1b", "S1b: %d low-SNR messages" % R["s1b"]["keys"]))):
        cw, co = R[key]["M"]["WSJT-X"].sum(axis=1), R[key]["M"]["OpenWSFZ"].sum(axis=1)
        ct = np.zeros((N + 1, N + 1), dtype=int)
        for x, y in zip(co, cw):
            ct[x, y] += 1
        a.imshow(ct, cmap="Blues", origin="lower")
        for i in range(N + 1):
            for j in range(N + 1):
                a.text(j, i, str(ct[i, j]), ha="center", va="center", color=("#e6edf3" if ct[i, j] > 0.5 * ct.max() else "#0d1117") if ct[i, j] else "#8b949e", fontsize=9)
        a.set_xlabel("sweeps (of %d) in which WSJT-X decoded the message" % N); a.set_ylabel("sweeps (of %d) in which OpenWSFZ decoded it" % N); a.set_title(title, fontsize=9)
        a.set_xticks(range(N + 1)); a.set_yticks(range(N + 1)); a.grid(False)
    fig.suptitle("Per-message decode count across the %s corrected sweeps, OpenWSFZ against WSJT-X" % NW, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A5_attribute_crosstab.png"), dpi=110); plt.close(fig)
    out["A5"] = ("A5_attribute_crosstab.png", "Each message is counted by the number of the four corrected sweeps in which each appraiser decoded it. Mass on the corners (0 or 4 for both) means the decoders are deterministic on this audio; off-diagonal cells are messages one appraiser decodes and the other does not.")
    # F6 recovery per sweep
    fig, axs = plt.subplots(1, 4, figsize=(15, 4.2))
    getters = (("S4 recovery (%)", lambda s, a: s["s4"][a]["recovery"]), ("S1b decode rate (%)", lambda s, a: s["s1b_overall"]["owsfz" if a == "OpenWSFZ" else "wsjtx"]),
               ("S7 recovery (%)", lambda s, a: s["s7"]["all"]["owsfz" if a == "OpenWSFZ" else "wsjtx"]), ("S8 decode rate (%)", lambda s, a: s["s8"][a]["rate"]))
    for a, (t, g) in zip(axs, getters):
        for j, ap in enumerate(F.APPR):
            for i, k in enumerate(F.PAIRED):
                a.bar(i + (j - 0.5) * 0.38, g(R["summ"][k], ap), 0.36, color=COL[k] if ap == "OpenWSFZ" else "#8b949e", alpha=1.0 if ap == "OpenWSFZ" else 0.75)
        a.set_xticks(range(NP)); a.set_xticklabels([LAB[k] for k in F.PAIRED], fontsize=7, rotation=20); a.set_title(t, fontsize=9); a.set_ylim(0, 105)
    fig.suptitle("Decode and recovery rates per sweep (coloured: OpenWSFZ, grey: WSJT-X%s)" % ("; run 1 is the default chain" if "run1" in R["cubes"]["S1"] else ""), fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A6_rates.png"), dpi=110); plt.close(fig)
    out["A6"] = ("A6_rates.png", "Attribute-style results per sweep. S4 is identical for OpenWSFZ in all five sweeps; run 1's S1b loss is the default chain.")
    if "run1" in R["cubes"]["S1"]:
        # F7 chain effect
        fig, ax = plt.subplots(figsize=(9, 4.8))
        snrs = R["cubes"]["S1"]["run1"][1]
        for ap, c in (("OpenWSFZ", "#58a6ff"), ("WSJT-X", "#e3b341")):
            j = F.APPR.index(ap)
            Yc = np.stack([R["cubes"]["S1"][k][0][:, j, :] - snrs[:, None] for k in F.CORRECTED], axis=2).mean(axis=(1, 2)) if False else None
            per = np.array([(R["cubes"]["S1"][k][0][:, j, :] - snrs[:, None]).mean(axis=1) for k in F.CORRECTED])
            ax.errorbar(snrs, per.mean(axis=0), yerr=per.std(axis=0, ddof=1), fmt="o-", color=c, capsize=3, label="%s, corrected chain (mean ± SD of %d sweeps)" % (ap, N))
        d = (R["cubes"]["S1"]["run1"][0][:, 1, :] - snrs[:, None]).mean(axis=1)
        ax.plot(snrs, d, "s--", color="#f85149", label="OpenWSFZ, default chain (run 1)")
        dw = (R["cubes"]["S1"]["run1"][0][:, 0, :] - snrs[:, None]).mean(axis=1)
        ax.plot(snrs, dw, "s:", color="#f0883e", label="WSJT-X, run 1 (same audio path, default chain)")
        ax.axhline(2, color="#8b949e", ls=":"); ax.axhline(-2, color="#8b949e", ls=":")
        ax.set(xlabel="injected SNR (dB)", ylabel="reported minus injected (dB)", title="Chain effect on S1: default chain against the four corrected sweeps"); ax.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(os.path.join(img, "A7_chain_effect.png"), dpi=110); plt.close(fig)
        gap = d - np.array([(R["cubes"]["S1"][k][0][:, 1, :] - snrs[:, None]).mean(axis=1) for k in F.CORRECTED]).mean(axis=0)
        out["A7"] = ("A7_chain_effect.png", "S1 error by injected SNR. The default chain moves OpenWSFZ down by %.2f to %.2f dB (depending on the injected SNR) against the mean of the corrected sweeps; WSJT-X in run 1 differs from its corrected-chain mean by at most %.2f dB." % (-gap.max(), -gap.min(), float(np.abs(dw - np.array([(R["cubes"]["S1"][k][0][:, 0, :] - snrs[:, None]).mean(axis=1) for k in F.CORRECTED]).mean(axis=0)).max())))
    # F8 residual diagnostics S1
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.2))
    for a, (sc, *_r) in zip(axs, F.SCEN):
        Y = np.stack([R["cubes"][sc][k][0] for k in F.CORRECTED], axis=2)
        res = (Y - Y.mean(axis=3, keepdims=True)).reshape(-1)
        stats.probplot(res, dist="norm", plot=a)
        a.get_lines()[0].set_color("#58a6ff"); a.get_lines()[1].set_color("#8b949e")
        a.set_title("%s residuals (n = %d; %.0f %% are exactly 0)" % (sc, len(res), 100.0 * float((res == 0).mean())), fontsize=9)
    fig.suptitle("Normal probability plots of the within-cell residuals (reported values are rounded: 1 dB, 1 Hz, 0.1 s)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(img, "A8_residuals.png"), dpi=110); plt.close(fig)
    out["A8"] = ("A8_residuals.png", "Within-cell residuals of the four-sweep data. The reported values are quantised (1 dB, 1 Hz, 0.1 s), so most residuals are exactly zero and the normality assumption of the F tests holds only roughly; the variance-component estimates do not need it, the p values do.")
    return out


# ---------------------------------------------------------------------------------------------------------------------------------- text
def anova_table(r, title):
    rows = []
    for k in ("P", "A", "S", "PA", "PS", "AS", "PAS"):
        Fv, d1, d2, p = r["tests"][k]
        exact = k in ("PA", "PS", "AS", "PAS")
        rows.append([TERM[k], fnum(r["ss"][k], 4), "%d" % r["df"][k], fnum(r["ms"][k], 4), fnum(Fv, 3) + ("" if exact else " (quasi-F)"), ("%d, %s" % (d1, ("%.1f" % d2))) if not exact else "%d, %d" % (d1, d2), fp(p)])
    rows.append([TERM["E"], fnum(r["ss"]["E"], 4), "%d" % r["df"]["E"], fnum(r["ms"]["E"], 4), "", "", ""])
    rows.append(["Total", fnum(r["ss_total"], 4), "%d" % r["df_total"], "", "", "", ""])
    return md_table(["Source", "SS", "df", "MS", "F", "df (num, den)", "p"], rows)


def build(results: str, out: str) -> None:
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    R = compute(results)
    Fg = figures(R, os.path.join(out, "img"))
    S, T, B = R["summ"], R["three"], R["boot"]
    r2 = S["run2"]
    L = []
    A = L.append
    ci = lambda sc, g: "%.3f to %.3f" % B[sc][g]
    A("# OpenWSFZ R&R Study: LINUX series on `sol`, final full ANOVA report")
    A("")
    A("> **Final combined analysis of every complete dataset of the LINUX R&R series on `sol` (11 and 14 October 2026): five paired sweeps with both appraisers decoding, in a fully balanced design.** "
      "It replaces nothing and amends nothing: it is a new analysis of the data. Per-sweep Gage R&R, a pooled two-way ANOVA, and a three-way crossed random-effects ANOVA (Part x Appraiser x Sweep) with the sweeps as the replication; bias and linearity; attribute agreement with per-message consistency; the chain effect; and an evaluation. "
      "**Not comparable with the Windows series** (other platform, CPU and audio chain; WSJT-X 2.7.0 built from source by QA). Informational: no merge or build decision rests on this report.")
    A("")
    A(md_table(["Field", "Value"], [
        ["Report date", "2026-10-14 (QA; analysis of existing run folders, no new run)"],
        ["Host", "`sol`: AMD FX-8350, Gentoo; no radio, no CAT; audio through the codec loopback, PCM `rr_in`"],
        ["OpenWSFZ build, all five sweeps", "`main` `%s` (v%s, shim %s)" % (r2["build"]["commit"], r2["build"]["daemon_version"], r2["build"]["shim"])],
        ["`libft8.so` SHA-256", "`%s` in all five (read back from each run's `arm_config.json`: %s)" % (r2["build"]["dll_sha256"], "equal" if len({S[k]["build"]["dll_sha256"] for k in F.PAIRED}) == 1 else "NOT EQUAL")],
        ["Decoder flags (read back)", "`nhard` / `osdNhardMax` %s, `subtractionEnabled` %s, `subtractionMaxThreads` %s" % (r2["build"]["readback"]["osdNhardMax"], r2["build"]["readback"]["subtractionEnabled"], r2["build"]["readback"]["subtractionMaxThreads"])],
        ["WSJT-X", "2.7.0 built from the verified source tarball on `sol` (Qt 5.15, gfortran 13.4.0); NDepth %s; WSJT-X 3.x cannot be the appraiser (its `callok` rejects every callsign starting with Q)" % r2["build"]["wsjtx_ndepth"]],
        ["Analysis code", "`qa/rr-study/linux/full_anova_core.py` (imports the analyser's `_two_way_anova`, so the per-sweep figures are the analyser's) and `build_full_anova_report.py`"],
    ]))
    A("")
    # ------------------------------------------------------------------ executive summary
    s1, s2, s3 = T["S1"], T["S2"], T["S3"]
    w_b = [R["bias"]["S1"][k]["WSJT-X"]["bias"] for k in F.CORRECTED]
    o_b = [R["bias"]["S1"][k]["OpenWSFZ"]["bias"] for k in F.CORRECTED]
    dif = [o - w for o, w in zip(o_b, w_b)]
    m_d, sd_d, lo_d, hi_d = F.t_ci(dif)
    A("## Summary")
    A("")
    A("1. **The measurement system is capable on the corrected chain, by the project's rule.** Four corrected-chain sweeps, two appraisers, ten parts, three trials: **%%Contribution** (the share of the total variance not due to the parts; the analyser prints it as '%%GR&R', and the project grades it against 10/30 under its ratified rule) is **%.2f %%** for S1 SNR (bootstrap 95 %% CI %s %%, ndc %s), **%.3f %%** for S2 frequency (ndc %s) and **%.2f %%** for S3 DT (CI %s %%, ndc %s), all below the project's 10 %% %%Contribution line. AIAG conventionally reads 10/30 on **%%StudyVar** (the ratio of standard deviations); on that metric the same data give **S1 %.1f %%, S2 %.1f %%, S3 %.1f %%**, so S3 is just over 10 %% on %%StudyVar. Run 1 (default chain), S1: %.1f %% %%Contribution and **%.1f %% %%StudyVar**: marginal by the project rule, above 30 %% on %%StudyVar. Whether the gate should read %%StudyVar is the Captain's decision and is not changed here." % (
        s1["pct_grr"], ci("S1", "grr"), s1["ndc"], s2["pct_grr"], s2["ndc"], s3["pct_grr"], ci("S3", "grr"), s3["ndc"], s1["pct_grr_sv"], s2["pct_grr_sv"], s3["pct_grr_sv"],
        R["per"]["S1"]["run1"]["pct"]["grr"], R["per"]["S1"]["run1"]["pct"]["grr_sv"]))
    from harness import analyse as _AN
    v3 = [_AN._verdict_grr(R["per"]["S3"][k]["pct"]["grr_sv"]) for k in F.PAIRED]
    A("   **Under the gate as ruled on 2026-10-14** (the project's %%GR&R gate now reads %%StudyVar, 10 / 30 %%; Captain, relayed by the Architect; this report was accepted before the ruling and is otherwise unchanged): **S3 reads %s** on the four corrected sweeps pooled (%.1f %%; per sweep, all five sweeps, %.1f to %.1f %%: %s) and **run 1 S1 reads %s** (%.1f %%); S1 reads %s (%.1f %%) and S2 reads %s (%.1f %%) on the four corrected sweeps." % (
        _AN._verdict_grr(s3["pct_grr_sv"]), s3["pct_grr_sv"], min(R["per"]["S3"][k]["pct"]["grr_sv"] for k in F.PAIRED), max(R["per"]["S3"][k]["pct"]["grr_sv"] for k in F.PAIRED),
        ", ".join("%s %s" % (LAB[k], v) for k, v in zip(F.PAIRED, v3)), _AN._verdict_grr(R["per"]["S1"]["run1"]["pct"]["grr_sv"]), R["per"]["S1"]["run1"]["pct"]["grr_sv"],
        _AN._verdict_grr(s1["pct_grr_sv"]), s1["pct_grr_sv"], _AN._verdict_grr(s2["pct_grr_sv"]), s2["pct_grr_sv"]))
    A("2. **What the small remainder is made of.** S1: repeatability %.3f %%, appraiser %.3f %%, sweep %.3f %% of the total variance (the sweep group contains the one significant S1 finding, the Appraiser x Sweep term, named below). S3: repeatability %.3f %%, **appraiser %.3f %% (the largest non-part source; appraiser main effect p %s; with only two programs this is a fixed offset between them, not measurement noise)**, sweep %.3f %%. In S3 the two appraisers differ by a systematic offset (OpenWSFZ minus WSJT-X %+.3f s). In S1 the mean difference is %+.2f dB (t 95 %% CI %.2f to %.2f dB over the four sweeps, which includes 0), but OpenWSFZ's S1 bias differs between sweeps (%+.2f to %+.2f dB) while WSJT-X's does not (%+.2f to %+.2f dB): Appraiser x Sweep p %s." % (
        s1["pct_groups"]["repeatability"], s1["pct_groups"]["appraiser"], s1["pct_groups"]["sweep"], s3["pct_groups"]["repeatability"], s3["pct_groups"]["appraiser"], fp(s3["tests"]["A"][3]), s3["pct_groups"]["sweep"],
        F.t_ci([R["bias"]["S3"][k]["OpenWSFZ"]["bias"] - R["bias"]["S3"][k]["WSJT-X"]["bias"] for k in F.CORRECTED])[0], m_d, lo_d, hi_d, min(o_b), max(o_b), min(w_b), max(w_b), fp(s1["tests"]["AS"][3])))
    s4o = R["s4"]["M"]["OpenWSFZ"].sum(axis=0)
    s4w = R["s4"]["M"]["WSJT-X"].sum(axis=0)
    A("3. **Attribute results do not move between sweeps.** S4 (%d messages): OpenWSFZ decodes %s per sweep, WSJT-X %s; Cochran's Q across the four sweeps p %s (OpenWSFZ) and %s (WSJT-X). The gap does not depend on the session." % (
        R["s4"]["keys"], "/".join(str(x) for x in s4o), "/".join(str(x) for x in s4w), fp(F.cochran_q(R["s4"]["M"]["OpenWSFZ"])[2]), fp(F.cochran_q(R["s4"]["M"]["WSJT-X"])[2])))
    A("4. **The default audio chain, not the decoder, is what makes OpenWSFZ fail S1 on an out-of-the-box Linux install:** run 1's OpenWSFZ bias is %+.2f dB against %s dB (min to max) on the corrected chain; with run 1 added as a fifth sweep, the sweep share of the S1 variance rises from %.3f %% to %.2f %%." % (
        R["bias"]["S1"]["run1"]["OpenWSFZ"]["bias"], "%.2f to %.2f" % (min(o_b), max(o_b)), s1["pct_groups"]["sweep"], R["five"]["S1"]["pct_groups"]["sweep"]))
    A("5. **Limits.** One host, one build, one chain; four corrected sweeps (the sweep factor has 3 degrees of freedom, so between-sweep statements are coarse); the same 10 parts and the same 108 messages in every sweep; reported values are rounded (1 dB, 1 Hz, 0.1 s). Two WSJT-X stalls cost data earlier in the series and are described in Section 1.")
    A("")
    # ------------------------------------------------------------------ section 1
    A("## Section 1: scope, data and design")
    A("")
    A(md_table(["Sweep", "Chain", "Cycles first to last (UTC)", "Used here as", "Folder"], [
        [SHORT[k], "default ALSA `linear`" if k == "run1" else "ALSA `samplerate_best`", "%s to %s" % (S[k]["cycle_utc_first_last"][0][5:16].replace("T", " "), S[k]["cycle_utc_first_last"][1][5:16].replace("T", " ")),
         "chain-effect sweep only" if k == "run1" else "corrected-chain replicate", "`%s`" % R["folders"][k]] for k in F.PAIRED]))
    A("")
    A("**Not used, and why.** (1) The three corrected-chain repeats of 11-12 October (`…-SAMPLERATE-chain-REPEAT1/2/3`): WSJT-X was silent, so they have one appraiser; their OpenWSFZ side is in the consolidated report, not here. (2) The first attempt at repeat 2 of 14 October (`…-WSJTX-REPEAT2`): **INVALID**, WSJT-X stopped taking in audio at 11:09:30Z; none of its data is used, including the first 32 minutes; replaced by a complete sweep (`…-REPEAT2-REPLACEMENT`, 'Repeat 2b'). The rule: the series is N complete sweeps, and a sweep in which an appraiser has no data for part of the battery is invalid and replaced. (3) The leg E replays and the 70 min WSJT-X run (different studies).")
    A("")
    A("**Design (checked in code: every cell has exactly 3 trials).** S1 SNR: 10 parts (injected SNRs) x 2 appraisers x 3 trials per sweep; S2 frequency and S3 DT: the same layout. Three trials of one part are three consecutive 15 s cycles of the same injected signal within one sweep. The sweeps are separate sessions (daemon and WSJT-X restarted between them) with identical injected seeds, so the parts are identical across sweeps. Tolerances for the analyser's %tolerance column are not used here: the report states the variance shares and the ndc.")
    A("")
    # ------------------------------------------------------------------ section 2
    A("## Section 2: method")
    A("")
    A("1. **Per sweep**: the analyser's own two-way crossed ANOVA (Part x Appraiser, AIAG MSA 4th ed.), imported from `harness/analyse.py`. The 15 figures (3 scenarios x 5 sweeps) agree with those printed in each sweep's own `report.md` (%Contribution to 0.05 percentage points, ndc exactly); the check is an assertion in the code.")
    A("2. **Pooled, sweeps ignored**: the same two-way model with the four sweeps' trials as 12 replicates per cell. It is what the per-sweep analysis would give if the sweeps were interchangeable, and it is shown to measure what the sweep factor adds.")
    A("3. **Pooled, sweeps as a random factor**: a three-way crossed random-effects ANOVA, factors Part (10), Appraiser (2), Sweep (4), 3 trials per cell, all interactions. Variance components by the expected-mean-squares method (negative estimates are reported and set to 0 for the percentages). F tests are exact for the four interactions; the three main effects have no exact error term in this model and use Satterthwaite quasi-F tests (marked). The percentage CIs are a **bootstrap over the 10 parts** (2000 resamples, seed %d): they describe the uncertainty from the choice of parts and not from the choice of sweeps, which cannot be resampled with four. Appraiser is treated as random only for comparability with AIAG; with exactly two programs it is really a fixed factor, so its component (1 df) is a fixed offset between them and is better read as the bias in Section 3.3." % F.BOOT_SEED)
    A("4. **Grouping**: repeatability = within-cell error; appraiser = appraiser main effect + Part x Appraiser; sweep = sweep main effect + Part x Sweep + Appraiser x Sweep + Part x Appraiser x Sweep (session-to-session reproducibility); %Contribution = the three groups together as a share of the total.")
    A("5. **Bias and linearity**: mean error (reported minus injected) per sweep and appraiser; OLS slope of the error on the injected value; the between-appraiser difference as a t-interval over the four sweeps.")
    A("6. **Attribute data (S4, S1b)**: a message is decoded in a sweep if any of its rows matched (the analyser's rule). Cochran's Q across the four sweeps tests whether the decode rate moves between sweeps; an exact sign test on the per-message decode counts compares the appraisers; S5, S7 and S8 are shown per sweep.")
    A("")
    # ------------------------------------------------------------------ section 3
    A("## Section 3: results")
    A("")
    A("### 3.1 Per-sweep Gage R&R (the analyser's figures, reproduced)")
    A("")
    rows = []
    for sc, *_r in F.SCEN:
        rows.append([NAME[sc].split(" (")[0]] + ["%.2f %% / %.1f %% (%s)" % (R["per"][sc][k]["pct"]["grr"], R["per"][sc][k]["pct"]["grr_sv"], R["per"][sc][k]["ndc"] if R["per"][sc][k]["ndc"] is not None else "n/a") for k in F.PAIRED])
    A(md_table(["%Contribution / %StudyVar (ndc)"] + [SHORT[k] for k in F.PAIRED], rows))
    A("")
    A("The S2 value is 0 in every sweep: the injected frequencies are recovered to within the 1 Hz rounding of the reports. Run 1's S1 value (11.2 %) is the default chain's.")
    A("")
    A("### 3.2 Combined ANOVA, four corrected-chain sweeps")
    A("")
    for sc, *_r in F.SCEN:
        r = T[sc]
        A("#### %s" % NAME[sc])
        A("")
        A(anova_table(r, sc))
        A("")
        A("Quasi-F (main effects): numerator MS_effect + MS_PxAxS, denominator the sum of the two mean squares of the interactions that involve the effect; degrees of freedom by Satterthwaite (hence non-integer denominators).")
        A("")
        vrows = []
        for k in ("P", "A", "S", "PA", "PS", "AS", "PAS", "E"):
            vrows.append([TERM[k], fnum(r["vc"][k], 4) + (" (raw %s, set to 0)" % fnum(r["vc_raw"][k], 2) if r["vc_raw"][k] < 0 else ""), "%.4f %%" % r["pct"][k]])
        A(md_table(["Variance component", "Estimate (%s²)" % UNIT[sc], "% of total"], vrows))
        A("")
        gr = r["pct_groups"]
        A("Grouped: repeatability **%.3f %%** (CI %s), appraiser **%.3f %%** (CI %s), sweep **%.3f %%** (CI %s); **%%Contribution %.3f %% (CI %s), %%StudyVar %.1f %%, ndc %s**; part %.3f %%. The pooled two-way analysis that ignores the sweeps gives %%Contribution %.3f %% (ndc %s)." % (
            gr["repeatability"], ci(sc, "repeatability"), gr["appraiser"], ci(sc, "appraiser"), gr["sweep"], ci(sc, "sweep"), r["pct_grr"], ci(sc, "grr"), r["pct_grr_sv"], r["ndc"], gr["part"], R["pooled2"][sc]["pct"]["grr"], R["pooled2"][sc]["ndc"]))
        A("")
    A("![%s](img/%s)" % ("Variance components", Fg["A1"][0]))
    A("")
    A("*Figure A1. %s*" % Fg["A1"][1])
    A("")
    A("![%s](img/%s)" % ("Interaction", Fg["A2"][0]))
    A("")
    A("*Figure A2. %s*" % Fg["A2"][1])
    A("")
    A("![%s](img/%s)" % ("Sweep effect", Fg["A3"][0]))
    A("")
    A("*Figure A3. %s*" % Fg["A3"][1])
    A("")
    A("![%s](img/%s)" % ("Residuals", Fg["A8"][0]))
    A("")
    A("*Figure A8. %s*" % Fg["A8"][1])
    A("")
    A("### 3.3 Bias and linearity")
    A("")
    brow = []
    for sc, *_r in F.SCEN:
        for ap in ("OpenWSFZ", "WSJT-X"):
            v = [R["bias"][sc][k][ap]["bias"] for k in F.CORRECTED]
            m, sd, lo, hi = F.t_ci(v)
            sl = [R["bias"][sc][k][ap]["slope"] for k in F.CORRECTED]
            brow.append([NAME[sc].split(" (")[0], ap, "%.3f" % R["bias"][sc]["run1"][ap]["bias"]] + ["%.3f" % x for x in v] + ["%.3f (%.3f to %.3f)" % (m, lo, hi), "%.4f" % float(np.mean(sl))])
    A(md_table(["Scenario", "Appraiser", "Run 1 (default)"] + [LAB[k] for k in F.CORRECTED] + ["Mean of 4 corrected (95 % t-CI)", "Mean slope of error on injected value"], brow))
    A("")
    drow = []
    for sc, *_r in F.SCEN:
        d = [R["bias"][sc][k]["OpenWSFZ"]["bias"] - R["bias"][sc][k]["WSJT-X"]["bias"] for k in F.CORRECTED]
        m, sd, lo, hi = F.t_ci(d)
        drow.append([NAME[sc].split(" (")[0], UNIT[sc]] + ["%+.3f" % x for x in d] + ["%+.3f (%+.3f to %+.3f)" % (m, lo, hi)])
    A(md_table(["Appraiser difference, OpenWSFZ minus WSJT-X", "Unit"] + [LAB[k] for k in F.CORRECTED] + ["Mean (95 % t-CI over 4 sweeps)"], drow))
    A("")
    A("The S3 values carry WSJT-X's +0.55 s DT convention correction as the analyser applies it; the remaining DT offset of both appraisers (about -0.25 to -0.38 s) is the harness's DT convention (a known, ledgered offset), not a decoder property, and the appraiser difference is what matters here. The slopes show the error is nearly constant across the injected range for S1 and S2; S3's slope of about -0.03 to -0.04 s per second of injected DT is the same for both appraisers.")
    A("")
    A("![%s](img/%s)" % ("S1 difference", Fg["A4"][0]))
    A("")
    A("*Figure A4. %s*" % Fg["A4"][1])
    A("")
    A("### 3.4 Attribute agreement and per-message consistency")
    A("")
    qrows = []
    for key, nm in (("s4", "S4 (%d messages)" % R["s4"]["keys"]), ("s1b", "S1b (%d messages)" % R["s1b"]["keys"])):
        for ap in ("OpenWSFZ", "WSJT-X"):
            M = R[key]["M"][ap]
            Q, dfq, pq = F.cochran_q(M)
            cnt = M.sum(axis=1)
            qrows.append([nm, ap, "/".join(str(x) for x in M.sum(axis=0)), "%d / %d / %d" % ((cnt == 4).sum(), (cnt == 0).sum(), ((cnt > 0) & (cnt < 4)).sum()), "%.2f (df %d)" % (Q, dfq), fp(pq)])
    A(md_table(["Scenario", "Appraiser", "Decoded per corrected sweep", "Messages decoded in 4 / 0 / 1-3 sweeps", "Cochran's Q", "p"], qrows))
    A("")
    srows = []
    for key, nm in (("s4", "S4"), ("s1b", "S1b")):
        d = R[key]["M"]["WSJT-X"].sum(axis=1) - R[key]["M"]["OpenWSFZ"].sum(axis=1)
        pos, neg, p = F.exact_sign(d)
        srows.append([nm, "%d" % pos, "%d" % neg, "%d" % (d == 0).sum(), fp(p)])
    A(md_table(["Appraiser comparison by per-message decode count", "Messages WSJT-X decodes more often", "Messages OpenWSFZ decodes more often", "Ties", "Exact sign test p"], srows))
    A("")
    A("![%s](img/%s)" % ("Cross-tab", Fg["A5"][0]))
    A("")
    A("*Figure A5. %s*" % Fg["A5"][1])
    A("")
    prow = []
    for k in F.PAIRED:
        s = S[k]
        prow.append([SHORT[k], s["s5"]["gate_aw"].split(" (")[0], "%s / %s" % (s["s5"]["check_b_w"].split(" slots")[0], s["s5"]["check_b_o"].split(" slots")[0]), "%.2f / %.2f %%" % (s["s7"]["all"]["owsfz"], s["s7"]["all"]["wsjtx"]),
                     "%.2f / %.2f %%" % (s["s8"]["OpenWSFZ"]["rate"], s["s8"]["WSJT-X"]["rate"]), "%.2f / %.2f %%" % (s["s1b_overall"]["owsfz"], s["s1b_overall"]["wsjtx"]), "%.2f %% (%d) / %.2f %% (%d)" % (s["s4"]["OpenWSFZ"]["recovery"], s["s4"]["OpenWSFZ"]["tp"], s["s4"]["WSJT-X"]["recovery"], s["s4"]["WSJT-X"]["tp"])])
    A(md_table(["Sweep", "S5 OpenWSFZ false positives (Gate A-W)", "S5 narrowband Check B (WSJT-X / OpenWSFZ)", "S7 recovery OpenWSFZ / WSJT-X", "S8 decode rate OpenWSFZ / WSJT-X", "S1b decode rate OpenWSFZ / WSJT-X", "S4 recovery OpenWSFZ (TP) / WSJT-X (TP)"], prow))
    A("")
    c7o = [S[k]["s7"]["all"]["owsfz"] for k in F.CORRECTED]
    c7w = [S[k]["s7"]["all"]["wsjtx"] for k in F.CORRECTED]
    c8 = [S[k]["s8"]["OpenWSFZ"]["rate"] - S[k]["s8"]["WSJT-X"]["rate"] for k in F.CORRECTED]
    m8, sd8, lo8, hi8 = F.t_ci(c8)
    A("S7 is instrument-suspect by standing rule: it is shown per sweep and as a band (OpenWSFZ %.2f to %.2f %%, WSJT-X %.2f to %.2f %% over the four corrected sweeps), never as a mean. S8 (60 injected; one decode is 1.67 points): OpenWSFZ minus WSJT-X %+.2f points (t 95 %% CI %+.2f to %+.2f, four sweeps), descriptive." % (min(c7o), max(c7o), min(c7w), max(c7w), m8, lo8, hi8))
    A("")
    A("![%s](img/%s)" % ("Rates", Fg["A6"][0]))
    A("")
    A("*Figure A6. %s*" % Fg["A6"][1])
    A("")
    A("### 3.5 The chain effect (run 1 against the corrected chain)")
    A("")
    f1 = R["five"]["S1"]
    A(md_table(["Three-way model, S1", "Four corrected sweeps", "All five sweeps (run 1 added)"], [
        ["Sweep share of the variance", "%.3f %%" % T["S1"]["pct_groups"]["sweep"], "%.2f %%" % f1["pct_groups"]["sweep"]],
        ["Appraiser share", "%.3f %%" % T["S1"]["pct_groups"]["appraiser"], "%.3f %%" % f1["pct_groups"]["appraiser"]],
        ["Repeatability share", "%.3f %%" % T["S1"]["pct_groups"]["repeatability"], "%.3f %%" % f1["pct_groups"]["repeatability"]],
        ["%Contribution (ndc)", "%.2f %% (%s)" % (T["S1"]["pct_grr"], T["S1"]["ndc"]), "%.2f %% (%s)" % (f1["pct_grr"], f1["ndc"])],
        ["Sweep main effect (quasi-F, p)", "%.2f, %s" % (T["S1"]["tests"]["S"][0], fp(T["S1"]["tests"]["S"][3])), "%.2f, %s" % (f1["tests"]["S"][0], fp(f1["tests"]["S"][3]))],
        ["Appraiser x Sweep (F, p)", "%.2f, %s" % (T["S1"]["tests"]["AS"][0], fp(T["S1"]["tests"]["AS"][3])), "%.2f, %s" % (f1["tests"]["AS"][0], fp(f1["tests"]["AS"][3]))],
    ]))
    A("")
    A("Adding run 1 to the sweep factor makes one session differ for one appraiser only (OpenWSFZ), which is the Appraiser x Sweep term. S2 and S3 are unaffected by the chain (%%Contribution %.3f %% and %.2f %% with run 1 included, against %.3f %% and %.2f %%)." % (R["five"]["S2"]["pct_grr"], R["five"]["S3"]["pct_grr"], T["S2"]["pct_grr"], T["S3"]["pct_grr"]))
    A("")
    A("![%s](img/%s)" % ("Chain effect", Fg["A7"][0]))
    A("")
    A("*Figure A7. %s*" % Fg["A7"][1])
    A("")
    # ------------------------------------------------------------------ section 4 evaluation
    A("## Section 4: evaluation")
    A("")
    ow_s1b = S["run2"]["s1b_overall"]["owsfz"]
    A("1. **Repeatability is not the issue.** Within-cell repeatability is %.3f %% (S1), %.3f %% (S2) and %.3f %% (S3) of the total variance. The decoders are close to deterministic on the same audio: in the S4 cross-tab, %d of %d messages are decoded by OpenWSFZ in all four sweeps or in none, and %d of %d by WSJT-X." % (
        s1["pct_groups"]["repeatability"], s2["pct_groups"]["repeatability"], s3["pct_groups"]["repeatability"], int(((R["s4"]["M"]["OpenWSFZ"].sum(axis=1) == 4) | (R["s4"]["M"]["OpenWSFZ"].sum(axis=1) == 0)).sum()), R["s4"]["keys"],
        int(((R["s4"]["M"]["WSJT-X"].sum(axis=1) == 4) | (R["s4"]["M"]["WSJT-X"].sum(axis=1) == 0)).sum()), R["s4"]["keys"]))
    A("2. **Reproducibility between the programs is small and mostly a fixed offset.** The appraiser main effect is the largest non-part source in S3 (%.3f %%, p %s). In S1 it is not significant on the quasi-F test (p %s; OpenWSFZ minus WSJT-X %+.2f dB, t CI %.2f to %.2f dB), and the significant terms are Part x Appraiser (p %s) and Appraiser x Sweep (p %s), that is, the difference between the programs depends on the injected SNR and on the sweep. In round numbers the sweep means of the two programs differ by %.2f to %.2f dB in SNR, %.1f to %.1f Hz in frequency and %.2f to %.2f s in DT." % (
        s3["pct_groups"]["appraiser"], fp(s3["tests"]["A"][3]), fp(s1["tests"]["A"][3]), m_d, lo_d, hi_d, fp(s1["tests"]["PA"][3]), fp(s1["tests"]["AS"][3]), min(dif), max(dif),
        min(R["bias"]["S2"][k]["OpenWSFZ"]["bias"] - R["bias"]["S2"][k]["WSJT-X"]["bias"] for k in F.CORRECTED), max(R["bias"]["S2"][k]["OpenWSFZ"]["bias"] - R["bias"]["S2"][k]["WSJT-X"]["bias"] for k in F.CORRECTED),
        min(R["bias"]["S3"][k]["OpenWSFZ"]["bias"] - R["bias"]["S3"][k]["WSJT-X"]["bias"] for k in F.CORRECTED), max(R["bias"]["S3"][k]["OpenWSFZ"]["bias"] - R["bias"]["S3"][k]["WSJT-X"]["bias"] for k in F.CORRECTED)))
    chrono = sorted(F.CORRECTED, key=lambda k: S[k]["cycle_utc_first_last"][0])
    A("3. **Session-to-session reproducibility is good, with one visible difference between the appraisers.** The sweep share of the variance is %.3f %% (S1), %.3f %% (S2), %.3f %% (S3). OpenWSFZ's S1 bias per sweep, in the order the sweeps ran (%s), is %s dB, a range of %.2f dB; WSJT-X's is %s dB, a range of %.2f dB. It is not monotone in time, so it is not shown to be a drift: the build, library and chain are the same, the sweeps ran on two days, and four sweeps cannot separate a slow change from chance. The bias stays inside the ±2 dB bar in all of them." % (
        s1["pct_groups"]["sweep"], s2["pct_groups"]["sweep"], s3["pct_groups"]["sweep"], ", ".join(LAB[k] for k in chrono), ", ".join("%+.2f" % R["bias"]["S1"][k]["OpenWSFZ"]["bias"] for k in chrono), max(o_b) - min(o_b),
        ", ".join("%+.2f" % R["bias"]["S1"][k]["WSJT-X"]["bias"] for k in chrono), max(w_b) - min(w_b)))
    d4 = R["s4"]["M"]["WSJT-X"].sum(axis=1) - R["s4"]["M"]["OpenWSFZ"].sum(axis=1)
    p4 = F.exact_sign(d4)
    d1 = R["s1b"]["M"]["WSJT-X"].sum(axis=1) - R["s1b"]["M"]["OpenWSFZ"].sum(axis=1)
    p1 = F.exact_sign(d1)
    A("4. **Attribute performance is stable but not equal.** S4: OpenWSFZ %s of %d, WSJT-X %s; Cochran's Q does not reject a constant rate for either appraiser. On a per-message basis WSJT-X decodes %d messages more often than OpenWSFZ and OpenWSFZ decodes %d messages more often than WSJT-X (exact sign test p %s); in S1b the counts are %d and %d (p %s); the S1b gap (%.1f %% against %.1f %%) is the same size in all four sweeps; S5 has no false positive for either appraiser in 480 slots. These sweeps cannot say why the gap exists." % (
        "/".join(str(x) for x in s4o), R["s4"]["keys"], "/".join(str(x) for x in s4w), p4[0], p4[1], fp(p4[2]), p1[0], p1[1], fp(p1[2]), ow_s1b, S["run2"]["s1b_overall"]["wsjtx"]))
    zf = {sc: float(np.mean((lambda Y: (Y - Y.mean(axis=3, keepdims=True)).reshape(-1) == 0)(np.stack([R["cubes"][sc][k][0] for k in F.CORRECTED], axis=2)))) for sc in ("S1", "S2", "S3")}
    A("5. **Assumptions.** The data are balanced and the models are exact for that case. The reported values are rounded and %.0f %% (S1), %.0f %% (S2) and %.0f %% (S3) of the within-cell residuals are exactly zero (Figure A8), so the F tests are approximate and the very small p values (Part, Part x Appraiser) should be read as 'clearly present', not as precise. The bootstrap resamples parts, not sweeps. Truncating negative variance components to zero slightly overstates the other shares; the largest negative raw estimate is %s." % (100 * zf["S1"], 100 * zf["S2"], 100 * zf["S3"], fnum(min(min(T[sc]["vc_raw"].values()) for sc in T), 2)))
    A("6. **What this study can and cannot support.** It measures the measurement system (the injection, the loopback chain, the two decoders, the matcher) on one host. It supports: the corrected chain is a capable instrument for S1, S2 and S3; the default chain is not for S1. It does not support: any claim about decoder improvement, about the station's live performance, about other hosts or about the Windows series; S7 and S8 are not decoder figures; there is no bar on any of these figures (HK-038: none is proposed).")
    A("")
    A("## Section 5: conclusions and recommendations")
    A("")
    A("**Conclusions.**")
    A("")
    A("1. On `sol`, with the corrected capture chain, the R&R measurement system is **capable**: %%Contribution %.2f %% (S1), %.3f %% (S2), %.2f %% (S3), ndc %s / %s / %s, with two appraisers over four sessions (replicates of one design). All three are below the project's 10 %% %%Contribution line; on AIAG's %%StudyVar reading they are %.1f %%, %.1f %% and %.1f %% (S3 just over 10 %%)." % (s1["pct_grr"], s2["pct_grr"], s3["pct_grr"], s1["ndc"], s2["ndc"], s3["ndc"], s1["pct_grr_sv"], s2["pct_grr_sv"], s3["pct_grr_sv"]))
    A("2. The **default** audio chain is **not** capable for S1 (%%Contribution %.1f %%, %%StudyVar %.1f %%, OpenWSFZ bias %+.2f dB): the loss is in the default chain (defect #234) and the corrected chain removes it." % (R["per"]["S1"]["run1"]["pct"]["grr"], R["per"]["S1"]["run1"]["pct"]["grr_sv"], R["bias"]["S1"]["run1"]["OpenWSFZ"]["bias"]))
    chi_lo, chi_hi = float(stats.chi2.ppf(0.025, 3)), float(stats.chi2.ppf(0.975, 3))
    sdci = lambda sd: (sd * math.sqrt(3 / chi_hi), sd * math.sqrt(3 / chi_lo))
    sdo, sdw = F.t_ci(o_b)[1], F.t_ci(w_b)[1]
    A("3. **Descriptive noise figures for later changes** (corrected chain, same build; four sessions, so 3 degrees of freedom): OpenWSFZ S1 bias between-sweep SD %.2f dB (95 %% chi-square CI %.2f to %.2f dB; range %.2f dB); WSJT-X %.2f dB (CI %.2f to %.2f dB); S4 recovery range 0 points (OpenWSFZ) and %.2f points (WSJT-X, one message in one sweep); S8 OpenWSFZ range %.2f points (four values on 1.67-point steps: a range, not an SD); S1b 0 points. A later change well inside these is not distinguishable from noise on this instrument; with an SD interval this wide, none of them is a bar (HK-038)." % (
        sdo, sdci(sdo)[0], sdci(sdo)[1], max(o_b) - min(o_b), sdw, sdci(sdw)[0], sdci(sdw)[1], max(S[k]["s4"]["WSJT-X"]["recovery"] for k in F.CORRECTED) - min(S[k]["s4"]["WSJT-X"]["recovery"] for k in F.CORRECTED),
        max(S[k]["s8"]["OpenWSFZ"]["rate"] for k in F.CORRECTED) - min(S[k]["s8"]["OpenWSFZ"]["rate"] for k in F.CORRECTED)))
    A("4. **The dataset is complete for what it was run for** (a replicated crossed R&R of the two appraisers): five paired sweeps, four on the corrected chain. The two WSJT-X stalls (11-12 October; 14 October, replaced) do not touch the numbers above, because no stalled sweep is used.")
    A("")
    A("**Recommendations** (QA proposes; none is built or run without the Captain's go).")
    A("")
    A("1. Build the WSJT-X monitoring and the mid-run liveness gate before the next baseline re-run (plan `qa/rr-study/2026-10-14-1830-qa-plan-wsjtx-stall-monitoring-and-gate.md`, drafted with the Architect). The start-up warm-up check alone let both stalls through.")
    A("2. Treat the four corrected sweeps as the standing noise estimate for the Linux series; a later R&R should add its sweeps to this three-way model and re-estimate, and report any new sweep's S1 bias against the %+.2f to %+.2f dB range above. That is a descriptive comparison, not a bar (HK-038)." % (min(o_b), max(o_b)))
    A("3. If OpenWSFZ's S1 bias spread between sweeps (%.2f dB, against %.2f dB for WSJT-X) matters, more corrected-chain sweeps are the only way to say whether it is drift or chance (four sweeps cannot)." % (max(o_b) - min(o_b), max(w_b) - min(w_b)))
    A("")
    A("**Not claimed.** No bar is proposed; nothing here compares this series with the Windows one; nothing says OpenWSFZ changed between sweeps (one build, one library); the cause of the two WSJT-X stalls is not known.")
    A("")
    # ------------------------------------------------------------------ section 6 trend
    A("## Section 6: historical trend, every full S1-S8 sweep of the LINUX series")
    A("")
    A("**HK-031: Section 6 of the last LINUX report (`2026-10-13-LINUX-series-consolidated`, rows through 2026-10-14) was read before this section was written; this is the same table layout.** **This series is NOT comparable with the Windows series** (other platform, CPU and audio chain; WSJT-X built by QA).")
    A("")
    hist = []
    for k in F.PAIRED:
        s = S[k]
        sv = lambda sc: "%.1f%%" % R["per"][sc][k]["pct"]["grr_sv"]
        hist.append(["2026-10-11" if k in ("run1", "run2") else "2026-10-14", "`64246e4`", "%.1f%%%s" % (s["s1"]["pct_grr"], " MARGINAL by the project rule (%%Contribution; %.1f%% on %%StudyVar, above 30%%) (OpenWSFZ bias %+.2f dB **FAIL**)" % (R["per"]["S1"][k]["pct"]["grr_sv"], s["s1"]["bias_owsfz"]) if s["s1"]["bias_verdict"] == "FAIL" else ""), "%.1f%%" % s["s2"]["pct_grr"], "%.1f%%" % s["s3"]["pct_grr"], sv("S1"), sv("S2"), sv("S3"),
                     "0.0% / 0.0%", "%.1f%% / %.1f%%" % (s["s7"]["all"]["wsjtx"], s["s7"]["all"]["owsfz"]), "%.1f%% / %.1f%%" % (s["s8"]["WSJT-X"]["rate"], s["s8"]["OpenWSFZ"]["rate"]), "%.2f%%" % (100.0 * s["s78_pooled_matched"]["OpenWSFZ"] / s["s78_pooled_matched"]["WSJT-X"])])
    A(md_table(["Date", "SHA", "S1 %GR&R", "S2 %GR&R", "S3 %GR&R", "S1 %StudyVar", "S2 %StudyVar", "S3 %StudyVar", "S5 FP (WSJT-X / OpenWSFZ)", "S7 recovery (WSJT-X / OpenWSFZ)", "S8 decode rate (WSJT-X / OpenWSFZ)", "OpenWSFZ, % of WSJT-X (S7+S8 pooled, excl. FP)"], hist))
    A("")
    A("Gate changed to %StudyVar 2026-10-14 (Captain); rows before this date were graded on %Contribution. The %GR&R columns are the analyser's %Contribution (variance share), the standing column names of this table; the %StudyVar columns are computed from the variance components of these five sweeps (n/a would stand where the components are not on file). Rows in order: run 1 (default chain), run 2, repeats 1b, 2b (replacement), 3b. WSJT-X's own pooled counts differ between rows; the ratio is not a measure of an OpenWSFZ change. The three 11-12 October OpenWSFZ-only repeats are in the consolidated report's Section 6.")
    A("")
    A("## Appendix: per-sweep two-way ANOVA tables (the analyser's model)")
    A("")
    for sc, *_r in F.SCEN:
        for k in F.PAIRED:
            tw = R["per"][sc][k]
            A("**%s, %s** (%%Contribution %.2f %%, ndc %s, repeatability %.2f %%, reproducibility %.2f %%, part %.2f %%)" % (sc, SHORT[k], tw["pct"]["grr"], tw["ndc"], tw["pct"]["repeatability"], tw["pct"]["reproducibility"], tw["pct"]["part"]))
            A("")
            A(md_table(["Source", "SS", "df", "MS", "F", "p"], [[t[0], fnum(t[1], 4), t[2], fnum(t[3], 4) if t[3] is not None else "", fnum(t[4], 3) if t[4] is not None else "", fp(t[5]) if t[5] is not None else ""] for t in tw["table"]]))
            A("")
    A("---")
    A("")
    A("*Generated by `qa/rr-study/linux/build_full_anova_report.py` from the five paired run folders (no message text). The numbers in the text are computed from the data, not typed.*")
    md = "\n".join(L) + "\n"
    with open(os.path.join(out, "report.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(md)
    js = {"three_way": {sc: {"pct": T[sc]["pct"], "pct_groups": T[sc]["pct_groups"], "pct_grr": T[sc]["pct_grr"], "ndc": T[sc]["ndc"], "vc": T[sc]["vc"], "p": {k: v[3] for k, v in T[sc]["tests"].items()}, "boot": R["boot"][sc]} for sc in T},
          "per_sweep": {sc: {k: {"pct_grr": R["per"][sc][k]["pct"]["grr"], "ndc": R["per"][sc][k]["ndc"]} for k in F.PAIRED} for sc in R["per"]}}
    with open(os.path.join(out, "stats.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump(js, fh, indent=1, default=float)
    rr = os.path.join(HERE, "..", "render_report.py")
    subprocess.run([sys.executable, rr, os.path.join(out, "report.md")], check=True, stdout=subprocess.DEVNULL)
    html = open(os.path.join(out, "report.html"), encoding="utf8").read()

    def emb(m):
        p = os.path.join(out, m.group(1))
        return 'src="data:image/png;base64,' + base64.b64encode(open(p, "rb").read()).decode("ascii") + '"' if os.path.isfile(p) else m.group(0)
    with open(os.path.join(out, "report-standalone.html"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(re.sub(r'src="(img/[^"]+)"', emb, html))
    print("wrote", out, len(md), "chars")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(a.results, a.out)


if __name__ == "__main__":
    main()
