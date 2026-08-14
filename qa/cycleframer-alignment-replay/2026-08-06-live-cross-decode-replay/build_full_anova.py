#!/usr/bin/env python3
"""Full ANOVA over the 5-run live cross-decode replay series -- WSJT-X vs OpenWSFZ.

The Captain's instruction (2026-08-06, following the single clean run): "turn this test
into a real anova, we have done one run already. Do another 4 and create a full ANOVA
report." Five independent live replays of the SAME 20-cycle window (same underlying
real off-air content every time) give a genuine trial/replicate axis -- exactly the case
`qa/endurance/anova_common.py`'s own module docstring says a live off-air session normally
CANNOT provide ("each real transmission happens once. There is no trial axis") and which
`qa/rr-study/harness/anova_compute.py` was built for instead (its synthetic corpus could
construct repeated independent draws of the same nominal condition). This script reuses
THAT design -- a full two-way ANOVA WITH replication and interaction -- generalised from
anova_compute.py's hardcoded a=2/b=10/n=3 Gauge-R&R study to a=2 (decoder) / b=20 (cycle,
i.e. which of the 20 original archived cycles) / n=5 (run/trial), for decode COUNT, run
separately per source pass. It does NOT carry over anova_compute.py's bias/linearity/
%Tolerance sections -- those need an external ground-truth reference (the synthetic
corpus's known injected SNR) that this live replay has no equivalent of.

For SNR/DT/DT/frequency (continuous responses on MATCHED decode pairs, not counts), this
script instead pools all 5 runs' matched pairs into `qa/endurance/anova_common.py`'s
established randomized-complete-block design (Part = one matched decode, Appraiser =
decoder) -- unchanged machinery, just fed a 5x bigger Part set than any single run could
give. A cycle can carry many distinct messages, so "cycle" is not a clean single-valued
Part for these responses the way it is for decode count; message-level blocking remains
the right design here, same as every other live-corpus ANOVA in this project.

Both analyses run once per source pass (wsjtx-source WAVs / owsfz-source WAVs), so the
report can also show whether source matters at all -- expected small, per the earlier
single-run finding.

NFR-021: message text is read only to build match keys; never printed or written.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "endurance"))
import anova_common as ac  # noqa: E402
from anova_common import parse_all_txt, parse_cycle_ts  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
WSJTX_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
N_RUNS = 5
N_CYCLES = 20
SLOT_SECONDS = 15
OUR_SLACK_S = 1.0
WX_SLACK_S = 4.0
UTC = datetime.timezone.utc

PASSES = [
    ("pass1_wsjtx_source", "WSJT-X-source WAVs", "our_p1", "wx_p1", "p1_start"),
    ("pass2_owsfz_source", "OpenWSFZ-source WAVs", "our_p2", "wx_p2", "p2_start"),
]


def filt(rows: list[dict], start: datetime.datetime, end: datetime.datetime,
         slack: float) -> list[dict]:
    lo, hi = start - datetime.timedelta(seconds=slack), end + datetime.timedelta(seconds=slack)
    out = []
    for r in rows:
        dt = parse_cycle_ts(r["ts"])
        if dt is None:
            continue
        dt = dt.replace(tzinfo=UTC)
        if lo <= dt <= hi:
            out.append(r)
    return out


def bucket_counts(rows: list[dict], pass_start: datetime.datetime,
                   n: int = N_CYCLES, slot: int = SLOT_SECONDS) -> list[int]:
    """Assigns each row to a cycle-position bucket (0..n-1) by elapsed time from
    pass_start, NOT by distinct ts value -- a cycle with zero decodes on one side must
    still show up as 0 in that bucket, not silently shift every later cycle's index."""
    counts = [0] * n
    for r in rows:
        dt = parse_cycle_ts(r["ts"])
        if dt is None:
            continue
        dt = dt.replace(tzinfo=UTC)
        idx = round((dt - pass_start).total_seconds() / slot)
        if 0 <= idx < n:
            counts[idx] += 1
    return counts


def load_run(i: int) -> tuple[list[dict], dict]:
    run_dir = BASE / "_work" / f"run{i}"
    our_rows = parse_all_txt(str(run_dir / "our_ALL.TXT"))
    windows = json.loads((run_dir / "pass_windows.json").read_text())
    return our_rows, windows


# ---------------------------------------------------------------------------
# Generalised two-way ANOVA WITH replication and interaction (port of
# qa/rr-study/harness/anova_compute.py's Gauge-R&R math, parameterised over a/b/n instead
# of hardcoded 2/10/3; no bias/linearity/tolerance sections, no ground-truth reference).
# ---------------------------------------------------------------------------

def two_way_anova_with_replication(Y: dict, appraisers: list[str], parts: list,
                                    n: int) -> dict:
    from scipy.stats import f as fdist

    a, b = len(appraisers), len(parts)
    N = a * b * n
    all_vals = [Y[ap][p][t] for ap in appraisers for p in parts for t in range(n)]
    grand_mean = sum(all_vals) / N

    cell_mean = {(ap, p): sum(Y[ap][p]) / n for ap in appraisers for p in parts}
    op_mean = {ap: sum(Y[ap][p][t] for p in parts for t in range(n)) / (b * n)
               for ap in appraisers}
    part_mean = {p: sum(Y[ap][p][t] for ap in appraisers for t in range(n)) / (a * n)
                 for p in parts}

    ss_part = a * n * sum((part_mean[p] - grand_mean) ** 2 for p in parts)
    ss_op = b * n * sum((op_mean[ap] - grand_mean) ** 2 for ap in appraisers)
    ss_inter = n * sum(
        (cell_mean[(ap, p)] - op_mean[ap] - part_mean[p] + grand_mean) ** 2
        for ap in appraisers for p in parts)
    ss_error = sum(
        (Y[ap][p][t] - cell_mean[(ap, p)]) ** 2
        for ap in appraisers for p in parts for t in range(n))
    ss_total = sum((v - grand_mean) ** 2 for v in all_vals)

    df_part, df_op = b - 1, a - 1
    df_inter, df_error, df_total = (a - 1) * (b - 1), a * b * (n - 1), N - 1

    ms_part, ms_op = ss_part / df_part, ss_op / df_op
    ms_inter = ss_inter / df_inter
    ms_error = ss_error / df_error

    # AIAG convention: Part and Appraiser main effects tested against the interaction MS
    # (the correct error term once interaction is in the model); interaction itself is
    # tested against the residual/repeatability MS.
    f_part = ms_part / ms_inter if ms_inter > 0 else float("nan")
    f_op = ms_op / ms_inter if ms_inter > 0 else float("nan")
    f_inter = ms_inter / ms_error if ms_error > 0 else float("nan")
    p_part = 1 - fdist.cdf(f_part, df_part, df_inter) if not math.isnan(f_part) else float("nan")
    p_op = 1 - fdist.cdf(f_op, df_op, df_inter) if not math.isnan(f_op) else float("nan")
    p_inter = 1 - fdist.cdf(f_inter, df_inter, df_error) if not math.isnan(f_inter) else float("nan")

    var_repeat = ms_error
    var_op_x_part = max(0.0, (ms_inter - ms_error) / n)
    var_operator = max(0.0, (ms_op - ms_inter) / (b * n))
    var_part = max(0.0, (ms_part - ms_inter) / (a * n))
    var_reprod = var_operator + var_op_x_part
    var_grr = var_repeat + var_reprod
    var_total = var_grr + var_part

    return dict(
        a=a, b=b, n=n, N=N, grand_mean=grand_mean, op_mean=op_mean,
        ss_part=ss_part, ss_op=ss_op, ss_inter=ss_inter, ss_error=ss_error, ss_total=ss_total,
        df_part=df_part, df_op=df_op, df_inter=df_inter, df_error=df_error, df_total=df_total,
        ms_part=ms_part, ms_op=ms_op, ms_inter=ms_inter, ms_error=ms_error,
        f_part=f_part, f_op=f_op, f_inter=f_inter,
        p_part=p_part, p_op=p_op, p_inter=p_inter,
        var_repeat=var_repeat, var_op_x_part=var_op_x_part, var_operator=var_operator,
        var_part=var_part, var_reprod=var_reprod, var_grr=var_grr, var_total=var_total,
    )


def render_count_anova_md(stats: dict, title: str, appraisers: list[str]) -> str:
    lines = [f"### {title}\n"]
    lines.append(f"Design: Decoder (a={stats['a']}) x Cycle (b={stats['b']}, which of the "
                 f"20 original archived cycles) x Run (n={stats['n']} replicate live "
                 f"sessions). Response: decode count in that cycle.\n")
    lines.append("| Source | DF | SS | MS | F | P |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(f"| Cycle (Part) | {stats['df_part']} | {stats['ss_part']:.3f} | "
                 f"{stats['ms_part']:.3f} | {stats['f_part']:.3f} | {stats['p_part']:.5f} |")
    lines.append(f"| Decoder (Appraiser) | {stats['df_op']} | {stats['ss_op']:.3f} | "
                 f"{stats['ms_op']:.3f} | {stats['f_op']:.3f} | {stats['p_op']:.5f} |")
    lines.append(f"| Decoder x Cycle | {stats['df_inter']} | {stats['ss_inter']:.3f} | "
                 f"{stats['ms_inter']:.3f} | {stats['f_inter']:.3f} | {stats['p_inter']:.5f} |")
    lines.append(f"| Repeatability (run-to-run) | {stats['df_error']} | "
                 f"{stats['ss_error']:.3f} | {stats['ms_error']:.3f} | | |")
    lines.append(f"| Total | {stats['df_total']} | {stats['ss_total']:.3f} | | | |")
    lines.append("")
    lines.append(f"Grand mean: {stats['grand_mean']:.2f} decodes/cycle. "
                 f"Decoder means: " + ", ".join(
                     f"{ap}={stats['op_mean'][ap]:.2f}" for ap in appraisers) + "\n")
    lines.append("| Variance component | Value | % of total |")
    lines.append("|---|---:|---:|")
    vt = stats["var_total"] if stats["var_total"] > 0 else float("nan")
    for label, key in [("Repeatability (run-to-run)", "var_repeat"),
                        ("Reproducibility (decoder)", "var_reprod"),
                        ("  Decoder", "var_operator"),
                        ("  Decoder x Cycle", "var_op_x_part"),
                        ("Cycle-to-cycle", "var_part"),
                        ("Total", "var_total")]:
        v = stats[key]
        lines.append(f"| {label} | {v:.3f} | {100*v/vt:.1f}% |")
    lines.append("")
    verdict = ("Decoder main effect: **" +
               ("SIGNIFICANT" if stats["p_op"] < 0.05 else "not significant") +
               f"** (p={stats['p_op']:.5f}). Cycle main effect: **" +
               ("significant" if stats["p_part"] < 0.05 else "not significant") +
               f"** (p={stats['p_part']:.5f}). Interaction: **" +
               ("significant" if stats["p_inter"] < 0.05 else "not significant") +
               f"** (p={stats['p_inter']:.5f}).\n")
    lines.append(verdict)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3-way ANOVA: Decoder x Source x Cycle, Run as replicate -- added 2026-08-06 at the
# Captain's request, to answer directly "does the design separate the two decoders'
# samples from the two sources' samples, or is something confounded?"
#
# The 2-way tables above (one per source pass) never test Source itself: each is a
# separate Decoder x Cycle ANOVA, run twice, compared only by eye. This function instead
# fits ONE model with Source as an explicit factor, giving real F/p values for the Source
# main effect and the Decoder x Source interaction -- the two numbers "are we
# confounding things?" actually resolves to.
#
# Convention differs from render_count_anova_md's AIAG-style table on purpose: this is a
# FIXED-EFFECTS 3-way model, every term tested against the pure residual (run-to-run
# replicate) MS, not against a higher-order interaction. That AIAG convention (main
# effects vs interaction MS) is standard specifically when the blocking factor is a
# RANDOM sample from a larger population you want the test to generalise beyond (Gauge
# R&R's Parts, a random draw of production output) -- Cycle here is the opposite: 20
# SPECIFIC, deliberately chosen (busiest-window) cycles we replay identically every run,
# not a random sample standing in for "cycles in general". Decoder and Source are
# likewise fixed, not sampled. Standard fixed-effects practice for that case tests every
# term against the true residual, which n=5 replicate runs per cell actually provides.
#
# STILL NOT A FIX FOR THE ORDER CONFOUND: every run played WSJT-X-source WAVs first,
# OpenWSFZ-source WAVs second, always in that order -- Source is perfectly aliased with
# within-run pass order across all 5 runs. Whatever the Source main effect or the
# Decoder x Source interaction says below, it cannot distinguish "source" from "which
# pass of the run this was" -- flagged wherever this function's output is read, not
# something this analysis can resolve after the fact.
# ---------------------------------------------------------------------------

def three_way_anova_with_replication(Y: dict, A: list, B: list, C: list, n: int) -> dict:
    """Y[a][b][c] = list of n replicate values. a=Decoder, b=Source, c=Cycle by this
    script's convention, but the function itself is generic over what A/B/C mean."""
    from scipy.stats import f as fdist

    def cellvals(i, j, k):
        return Y[i][j][k]

    N = len(A) * len(B) * len(C) * n
    all_vals = [v for i in A for j in B for k in C for v in cellvals(i, j, k)]
    grand = sum(all_vals) / N

    mean_a = {i: sum(v for j in B for k in C for v in cellvals(i, j, k)) / (len(B) * len(C) * n)
              for i in A}
    mean_b = {j: sum(v for i in A for k in C for v in cellvals(i, j, k)) / (len(A) * len(C) * n)
              for j in B}
    mean_c = {k: sum(v for i in A for j in B for v in cellvals(i, j, k)) / (len(A) * len(B) * n)
              for k in C}
    mean_ab = {(i, j): sum(v for k in C for v in cellvals(i, j, k)) / (len(C) * n)
               for i in A for j in B}
    mean_ac = {(i, k): sum(v for j in B for v in cellvals(i, j, k)) / (len(B) * n)
               for i in A for k in C}
    mean_bc = {(j, k): sum(v for i in A for v in cellvals(i, j, k)) / (len(A) * n)
               for j in B for k in C}
    mean_abc = {(i, j, k): sum(cellvals(i, j, k)) / n for i in A for j in B for k in C}

    ss_a = len(B) * len(C) * n * sum((mean_a[i] - grand) ** 2 for i in A)
    ss_b = len(A) * len(C) * n * sum((mean_b[j] - grand) ** 2 for j in B)
    ss_c = len(A) * len(B) * n * sum((mean_c[k] - grand) ** 2 for k in C)
    ss_ab = len(C) * n * sum(
        (mean_ab[(i, j)] - mean_a[i] - mean_b[j] + grand) ** 2 for i in A for j in B)
    ss_ac = len(B) * n * sum(
        (mean_ac[(i, k)] - mean_a[i] - mean_c[k] + grand) ** 2 for i in A for k in C)
    ss_bc = len(A) * n * sum(
        (mean_bc[(j, k)] - mean_b[j] - mean_c[k] + grand) ** 2 for j in B for k in C)
    ss_abc = n * sum(
        (mean_abc[(i, j, k)] - mean_ab[(i, j)] - mean_ac[(i, k)] - mean_bc[(j, k)]
         + mean_a[i] + mean_b[j] + mean_c[k] - grand) ** 2
        for i in A for j in B for k in C)
    ss_error = sum(
        (v - mean_abc[(i, j, k)]) ** 2
        for i in A for j in B for k in C for v in cellvals(i, j, k))
    ss_total = sum((v - grand) ** 2 for v in all_vals)

    df = {
        "A": len(A) - 1, "B": len(B) - 1, "C": len(C) - 1,
        "AB": (len(A) - 1) * (len(B) - 1), "AC": (len(A) - 1) * (len(C) - 1),
        "BC": (len(B) - 1) * (len(C) - 1),
        "ABC": (len(A) - 1) * (len(B) - 1) * (len(C) - 1),
        "error": len(A) * len(B) * len(C) * (n - 1),
        "total": N - 1,
    }
    ss = dict(A=ss_a, B=ss_b, C=ss_c, AB=ss_ab, AC=ss_ac, BC=ss_bc, ABC=ss_abc,
              error=ss_error, total=ss_total)
    ms = {k: (ss[k] / df[k] if df[k] > 0 else float("nan")) for k in ss if k != "total"}

    f_stat, p_stat = {}, {}
    for k in ["A", "B", "C", "AB", "AC", "BC", "ABC"]:
        if ms.get("error", 0) and ms["error"] > 0 and df["error"] > 0:
            f_stat[k] = ms[k] / ms["error"]
            p_stat[k] = 1 - fdist.cdf(f_stat[k], df[k], df["error"])
        else:
            f_stat[k] = float("nan")
            p_stat[k] = float("nan")

    return dict(ss=ss, df=df, ms=ms, f=f_stat, p=p_stat, grand_mean=grand,
                mean_a=mean_a, mean_b=mean_b, mean_ab=mean_ab)


def render_3way_anova_md(stats: dict, a_labels: dict, b_labels: dict) -> str:
    lines = ["## 3-way ANOVA: does the design separate Decoder from Source?\n"]
    lines.append(
        "Fixed-effects 3-way factorial with replication: Decoder (A, 2 levels) x Source "
        "(B, 2 levels) x Cycle (C, 20 levels, which of the 20 original archived cycles) "
        "x Run (5 replicates/cell). Every term tested against the pure run-to-run "
        "residual MS -- see this function's header comment for why that convention (not "
        "the AIAG main-effect-vs-interaction convention used for the per-source 2-way "
        "tables) is the right one here.\n")
    lines.append(
        "**Order confound, stated again because it matters for how to read this table**: "
        "every run played WSJT-X-source WAVs first, OpenWSFZ-source WAVs second, always "
        "in that order. The Source term and the Decoder x Source interaction below cannot "
        "distinguish a genuine source effect from a within-run pass-order effect -- read "
        "both as 'Source-or-order', not 'Source'.\n")

    ss_total = stats["ss"]["total"]
    names = {"A": "Decoder", "B": "Source", "C": "Cycle",
              "AB": "Decoder x Source", "AC": "Decoder x Cycle", "BC": "Source x Cycle",
              "ABC": "Decoder x Source x Cycle"}
    lines.append("| Source | DF | SS | MS | F | P | %SS |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for key in ["A", "B", "C", "AB", "AC", "BC", "ABC"]:
        lines.append(
            f"| {names[key]} | {stats['df'][key]} | {stats['ss'][key]:.3f} | "
            f"{stats['ms'][key]:.3f} | {stats['f'][key]:.3f} | {stats['p'][key]:.6f} | "
            f"{100*stats['ss'][key]/ss_total:.1f}% |")
    lines.append(
        f"| Residual (run-to-run) | {stats['df']['error']} | {stats['ss']['error']:.3f} | "
        f"{stats['ms']['error']:.3f} | | | {100*stats['ss']['error']/ss_total:.1f}% |")
    lines.append(f"| Total | {stats['df']['total']} | {ss_total:.3f} | | | | 100.0% |")
    lines.append("")

    lines.append(f"Grand mean: {stats['grand_mean']:.2f} decodes/cycle.")
    lines.append("Decoder means: " + ", ".join(
        f"{a_labels.get(i, i)}={stats['mean_a'][i]:.2f}" for i in stats["mean_a"]) + "  ")
    lines.append("Source means: " + ", ".join(
        f"{b_labels.get(j, j)}={stats['mean_b'][j]:.2f}" for j in stats["mean_b"]) + "\n")

    def verdict(key, label):
        p = stats["p"][key]
        if p != p:  # nan -- zero residual variance, F undefined, not the same as "not significant"
            return f"**{label}**: UNDETERMINED (zero residual variance, F undefined)"
        sig = "SIGNIFICANT" if p < 0.05 else "not significant"
        return f"**{label}**: {sig} (p={p:.6f})"

    lines.append("- " + verdict("A", "Decoder main effect"))
    lines.append("- " + verdict("B", "Source main effect (read as Source-or-order)"))
    lines.append("- " + verdict("AB", "Decoder x Source interaction (read as "
                                        "Decoder x [Source-or-order])"))
    lines.append("- " + verdict("C", "Cycle main effect"))
    lines.append("- " + verdict("AC", "Decoder x Cycle interaction"))
    lines.append("- " + verdict("BC", "Source x Cycle interaction"))
    lines.append("- " + verdict("ABC", "3-way interaction"))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    wx_rows_all = parse_all_txt(str(WSJTX_ALL_TXT))
    print(f"WSJT-X ALL.TXT total rows (all-time file): {len(wx_rows_all)}")

    runs: dict[int, dict] = {}
    for i in range(1, N_RUNS + 1):
        our_rows, windows = load_run(i)
        p1s, p1e = [datetime.datetime.fromisoformat(x) for x in windows["pass1_wsjtx_source"]]
        p2s, p2e = [datetime.datetime.fromisoformat(x) for x in windows["pass2_owsfz_source"]]
        runs[i] = dict(
            our_p1=filt(our_rows, p1s, p1e, OUR_SLACK_S),
            our_p2=filt(our_rows, p2s, p2e, OUR_SLACK_S),
            wx_p1=filt(wx_rows_all, p1s, p1e, WX_SLACK_S),
            wx_p2=filt(wx_rows_all, p2s, p2e, WX_SLACK_S),
            p1_start=p1s, p2_start=p2s,
        )
        print(f"run {i}: our_p1={len(runs[i]['our_p1'])} wx_p1={len(runs[i]['wx_p1'])} "
              f"our_p2={len(runs[i]['our_p2'])} wx_p2={len(runs[i]['wx_p2'])}")

    # Y3[decoder][source][cycle] = [n=N_RUNS replicate counts] -- built alongside the
    # per-pass 2-way tables below, feeds the combined 3-way ANOVA after the loop.
    SOURCES = ["wsjtx_source", "owsfz_source"]
    Y3 = {"OpenWSFZ": {s: {c: [] for c in range(N_CYCLES)} for s in SOURCES},
          "WSJT-X": {s: {c: [] for c in range(N_CYCLES)} for s in SOURCES}}

    report_sections = []
    all_count_stats = {}
    for (pass_key, pass_label, our_key, wx_key, start_key), source_id in zip(PASSES, SOURCES):
        print(f"\n=== {pass_label} ===")
        Y = {"OpenWSFZ": {c: [] for c in range(N_CYCLES)},
             "WSJT-X": {c: [] for c in range(N_CYCLES)}}
        for i in range(1, N_RUNS + 1):
            our_counts = bucket_counts(runs[i][our_key], runs[i][start_key])
            wx_counts = bucket_counts(runs[i][wx_key], runs[i][start_key])
            for c in range(N_CYCLES):
                Y["OpenWSFZ"][c].append(our_counts[c])
                Y["WSJT-X"][c].append(wx_counts[c])
                Y3["OpenWSFZ"][source_id][c].append(our_counts[c])
                Y3["WSJT-X"][source_id][c].append(wx_counts[c])

        count_stats = two_way_anova_with_replication(
            Y, ["OpenWSFZ", "WSJT-X"], list(range(N_CYCLES)), N_RUNS)
        all_count_stats[pass_key] = count_stats
        print(f"decode-count ANOVA: F(decoder)={count_stats['f_op']:.2f} "
              f"p={count_stats['p_op']:.6f}")

        all_pairs = []
        for i in range(1, N_RUNS + 1):
            pairs = ac.match_pairs(runs[i][our_key], runs[i][wx_key])
            all_pairs.extend(pairs)
        for idx, p in enumerate(all_pairs, start=1):
            p["part"] = idx
        print(f"pooled matched pairs across {N_RUNS} runs: {len(all_pairs)}")

        out_stem = f"anova_{pass_key}"
        response_results = ac.run_responses(all_pairs, str(BASE), out_stem,
                                             "OpenWSFZ", "WSJT-X")

        n_our_total = sum(len(runs[i][our_key]) for i in range(1, N_RUNS + 1))
        n_wx_total = sum(len(runs[i][wx_key]) for i in range(1, N_RUNS + 1))
        meta = {
            "run_label": f"5-run live cross-decode replay -- {pass_label}",
            "generated_utc": datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "a_label": "OpenWSFZ", "b_label": "WSJT-X",
            "n_a": n_our_total, "n_b": n_wx_total, "n_pairs": len(all_pairs),
            "method_note": (
                f"{N_RUNS} independent live replays of the same 20-cycle window "
                f"(260804_085845-260804_090330, {pass_label}), both decoders decoding "
                f"the same real-time audio simultaneously via VB-CABLE loopback. Parts "
                f"pooled across all {N_RUNS} runs (not one run's matched decodes)."
            ),
        }
        snr_dt_freq_report = ac.render_report(response_results, meta)

        section = f"## {pass_label}\n\n"
        section += render_count_anova_md(
            count_stats, f"Decode-count ANOVA ({pass_label})", ["OpenWSFZ", "WSJT-X"])
        section += "\n" + snr_dt_freq_report
        report_sections.append(section)

    print("\n=== 3-way ANOVA: Decoder x Source x Cycle ===")
    stats3 = three_way_anova_with_replication(
        Y3, ["OpenWSFZ", "WSJT-X"], SOURCES, list(range(N_CYCLES)), N_RUNS)
    print(f"F(Decoder)={stats3['f']['A']:.2f} p={stats3['p']['A']:.6f}   "
          f"F(Source)={stats3['f']['B']:.2f} p={stats3['p']['B']:.6f}   "
          f"F(Decoder x Source)={stats3['f']['AB']:.2f} p={stats3['p']['AB']:.6f}")
    three_way_section = render_3way_anova_md(
        stats3,
        a_labels={"OpenWSFZ": "OpenWSFZ", "WSJT-X": "WSJT-X"},
        b_labels={"wsjtx_source": "WSJT-X-source WAVs", "owsfz_source": "OpenWSFZ-source WAVs"},
    )

    generated = datetime.datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    header = f"""# Live cross-decode replay -- full ANOVA report (n={N_RUNS} runs)

Generated {generated}. `qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/build_full_anova.py`.

{N_RUNS} independent live replays of the identical 20-cycle window from
`20260803_live_run_1713` (260804_085845 -> 260804_090330), both decoders decoding the
same real-time audio simultaneously via VB-CABLE loopback (no offline `jt9`). Two designs:

1. **3-way decode-count ANOVA (Decoder x Source x Cycle)**: answers directly whether
   Decoder and Source are confounded -- they are not, but Source is perfectly aliased
   with within-run pass order (see the section itself). Fixed-effects model, all terms
   tested against the pure run-to-run residual.
2. **Per-source decode-count ANOVA**: two-way ANOVA WITH replication and interaction
   (Decoder x Cycle x Run), generalised from `qa/rr-study/harness/anova_compute.py`'s
   Gauge-R&R design, run separately per source pass (AIAG convention: main effects tested
   against the Decoder x Cycle interaction). Superseded by #1 for any claim about Source
   itself; kept as the simpler within-source view of Decoder alone.
3. **SNR / DT / frequency**: `qa/endurance/anova_common.py`'s established randomized-
   complete-block design (Part = one matched decode, Appraiser = decoder), Parts pooled
   across all {N_RUNS} runs' matched pairs -- same machinery as every other live-corpus
   ANOVA in this project, just fed a bigger pooled Part set. Also run separately per source.

NFR-021: message text read only to build match keys, never printed or written. Aggregate
statistics only below.

"""
    full_report = header + three_way_section + "\n---\n\n" + "\n---\n\n".join(report_sections)
    out_path = BASE / "full_anova_report.md"
    out_path.write_text(full_report, encoding="utf-8")
    print(f"\nwrote {out_path}")
    ac.render_markdown_html(str(out_path))

    summary_path = BASE / "full_anova_summary.json"
    summary_path.write_text(json.dumps({
        "per_source_2way": {k: v for k, v in all_count_stats.items()},
        "3way_decoder_source_cycle": {
            "f": stats3["f"], "p": stats3["p"], "df": stats3["df"],
            "ss": stats3["ss"], "ms": stats3["ms"],
            "grand_mean": stats3["grand_mean"],
            "mean_a": stats3["mean_a"], "mean_b": stats3["mean_b"],
        },
    }, indent=2))
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
