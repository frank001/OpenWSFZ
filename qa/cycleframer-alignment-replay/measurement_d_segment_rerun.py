#!/usr/bin/env python3
"""D-001 Measurement D -- per-segment re-run, per the Architect's ruling
2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md (R3/R4).

Why this script exists: the ruling found the 20m corpus in
artefacts/20260729_live_run_1831-8081/owsfz/20m/ is not one session but two, 18h28m apart
(2026-07-29 18:31:30-21:14:30, then 2026-07-30 15:42:15-18:40:00), and that Measurement D's
sparse/dense strata are substantially a segment split (sparse 90.1% segment 1, dense 65.4%
segment 2). R3 orders the matched-SNR analysis re-run on each segment separately, quoting both,
rather than pooled. R4 is a note for arm S.1 (not yet run) to partition on the same boundary,
segment 1 primary -- this script does not touch S.1.

This deliberately does NOT reimplement Measurement D's machinery. Per the work order's own
instruction ("needs only a segment filter"), it reuses:
  - anova_common.filter_rows_by_window  -- the existing window filter (by cycle ts token),
    already used elsewhere in this programme; not reinvented here.
  - measurement_d_within_band_density.stratify_cycles / matched_stratified_bins /
    duplicate_key_rate / wilson_interval / median_or_nan / quartile_cutoffs / BIN_WIDTH / MIN_N
    -- identical stratification, matching, self-check and binning logic, unmodified.

Scope: 20m only. Per the ruling's own Self-check 5 sweep (SPEC.md 1530 sec1.1), 10m and 80m are
each a single contiguous segment already -- there is nothing to split there, and Measurement D
never read them as decisive.

Segment boundary: cut at 2026-07-30T00:00:00Z. The measured gap (18:31:30-21:14:30 on 07-29 to
15:42:15-18:40:00 on 07-30) straddles this cleanly with no cycle within several hours of the
cut on either side, so the exact cut point within the 18.46h gap is immaterial to which cycles
land in which segment.

The reading rule applied per segment is Measurement D's own (spec S4), quoted verbatim and
unmodified -- per the ruling's R4, "the rule is not being edited after seeing data, only the
corpus partition it is applied to."

NFR-021: message text is read only to build the match key, never printed or written out.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import math
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
from anova_common import filter_rows_by_window, parse_all_txt  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from measurement_d_within_band_density import (  # noqa: E402
    BIN_WIDTH,
    MIN_N,
    duplicate_key_rate,
    matched_stratified_bins,
    median_or_nan,
    stratify_cycles,
    wilson_interval,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ARTEFACTS = os.path.join(ROOT, "artefacts")
CORPUS_ROOT = os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz")
OUR_PATH = os.path.join(CORPUS_ROOT, "20m", "ALL.TXT")
REF_PATH = os.path.join(CORPUS_ROOT, "20m", "jt9_ALL.TXT")

CUT = datetime.datetime(2026, 7, 30, 0, 0, 0)
SEGMENTS = [
    ("segment 1", None, CUT),
    ("segment 2", CUT, None),
]


def run_segment(label: str, start, end, ref_rows_all, our_rows_all) -> dict:
    ref_rows = filter_rows_by_window(ref_rows_all, start, end)
    our_rows = filter_rows_by_window(our_rows_all, start, end)

    stratum, density_by_cycle, q1, q3 = stratify_cycles(ref_rows)
    bins, total_matched = matched_stratified_bins(ref_rows, our_rows, stratum)

    sparse_cycles = [c for c, s in stratum.items() if s == "sparse"]
    dense_cycles = [c for c, s in stratum.items() if s == "dense"]
    sparse_mean = statistics.mean(density_by_cycle[c] for c in sparse_cycles) if sparse_cycles else float("nan")
    dense_mean = statistics.mean(density_by_cycle[c] for c in dense_cycles) if dense_cycles else float("nan")
    contrast = dense_mean / sparse_mean if sparse_cycles and sparse_mean else float("nan")

    sparse_dup = duplicate_key_rate(ref_rows, stratum, "sparse")
    dense_dup = duplicate_key_rate(ref_rows, stratum, "dense")

    common_bins = sorted(set(bins["sparse"]) & set(bins["dense"]))
    usable = [b for b in common_bins
              if bins["sparse"][b][0] >= MIN_N and bins["dense"][b][0] >= MIN_N]
    rows = []
    for b in usable:
        s_tot, s_m = bins["sparse"][b]
        d_tot, d_m = bins["dense"][b]
        s_recall = s_m / s_tot
        d_recall = d_m / d_tot
        s_lo, s_hi = wilson_interval(s_m, s_tot)
        d_lo, d_hi = wilson_interval(d_m, d_tot)
        diff = (s_recall - d_recall) * 100
        rows.append(dict(b=b, s_tot=s_tot, s_m=s_m, s_recall=s_recall, s_ci=(s_lo, s_hi),
                          d_tot=d_tot, d_m=d_m, d_recall=d_recall, d_ci=(d_lo, d_hi), diff=diff))

    dup_gap_pts = abs(dense_dup - sparse_dup) * 100
    med_diff = median_or_nan([r["diff"] for r in rows])
    confounded = (not math.isnan(med_diff)) and dup_gap_pts >= abs(med_diff) / 10.0
    n_ge8 = sum(1 for r in rows if r["diff"] >= 8.0)
    frac_ge8 = n_ge8 / len(rows) if rows else float("nan")

    return dict(
        label=label, n_cycles=len(density_by_cycle), n_sparse=len(sparse_cycles),
        n_dense=len(dense_cycles), q1=q1, q3=q3, sparse_mean=sparse_mean, dense_mean=dense_mean,
        contrast=contrast, sparse_dup=sparse_dup, dense_dup=dense_dup, dup_gap_pts=dup_gap_pts,
        total_matched=total_matched, rows=rows, median_diff=med_diff, confounded=confounded,
        n_usable=len(rows), frac_ge8=frac_ge8, n_ge8=n_ge8,
    )


def reading_rule(median_diff: float, frac_ge8: float) -> str:
    """Measurement D's own spec S4 reading rule, quoted verbatim and unmodified -- only the
    corpus partition changes (ruling R4)."""
    if median_diff >= 8.0 and frac_ge8 >= 0.8:
        return ("ROW 1: median diff >= 8pts AND >= 80% of bins >= 8pts -> Competition "
                "CONFIRMED as a named, measured mechanism.")
    elif -3.0 < median_diff < 3.0:
        return ("ROW 2: -3 < median diff < 3 -> Density does not act within this segment. ")
    elif median_diff <= -3.0:
        return "ROW 3: median diff <= -3 -> sparse recalls WORSE than dense. Not anticipated."
    return "ROW 4: partial/ambiguous. Report as ambiguous. Do not interpret."


def main() -> int:
    out_dir = os.path.dirname(__file__)
    our_rows_all = parse_all_txt(OUR_PATH)
    ref_rows_all = parse_all_txt(REF_PATH)

    report = []
    report.append("# Measurement D -- per-segment re-run (R3/R4 of the 1530 ruling)\n")
    report.append(
        "Per `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md` R3: "
        "the pooled 18.21-point figure is suspended because the 20m corpus is two sessions "
        "18h28m apart, not one. This re-runs Measurement D's matched-SNR analysis on each "
        "segment separately, using the identical stratification, matching and reading-rule "
        "logic (`measurement_d_within_band_density.py`), quoting both rather than pooling.\n")
    report.append(
        "**Note on self-check 1 (matching gate):** that check validates against the "
        "*full-corpus* published ANOVA count (24201) and does not apply per segment by "
        "construction -- each segment's total matched count is reported below as descriptive, "
        "not as a pass/fail gate.\n")

    results = {}
    for label, start, end in SEGMENTS:
        r = run_segment(label, start, end, ref_rows_all, our_rows_all)
        results[label] = r
        print(f"=== {label} ===")
        print(f"cycles={r['n_cycles']} sparse_n={r['n_sparse']} dense_n={r['n_dense']} "
              f"matched={r['total_matched']}")
        print(f"density contrast={r['contrast']:.2f}x  dup gap={r['dup_gap_pts']:.2f}pts  "
              f"usable bins={r['n_usable']}  median diff={r['median_diff']:+.2f}pts")

    report.append("## Segment composition\n")
    report.append("| segment | cycles | sparse n (cycles) | dense n (cycles) | "
                   "sparse cutoff | dense cutoff | total matched |")
    report.append("|---|---:|---:|---:|---:|---:|---:|")
    for label, *_ in SEGMENTS:
        r = results[label]
        report.append(f"| {label} | {r['n_cycles']} | {r['n_sparse']} | {r['n_dense']} | "
                       f"<= {r['q1']:.1f} | >= {r['q3']:.1f} | {r['total_matched']} |")
    report.append("")

    report.append("## Self-check 2 (density contrast) per segment\n")
    report.append("| segment | sparse mean ref decodes/cycle | dense mean ref decodes/cycle | "
                   "contrast |")
    report.append("|---|---:|---:|---:|")
    for label, *_ in SEGMENTS:
        r = results[label]
        report.append(f"| {label} | {r['sparse_mean']:.2f} | {r['dense_mean']:.2f} | "
                       f"{r['contrast']:.2f}x |")
    report.append("")

    report.append("## Self-check 3 (duplicate-key artefact) per segment\n")
    report.append("| segment | sparse dup-key rate | dense dup-key rate | gap (pts) | "
                   "median diff (pts) | confounded? |")
    report.append("|---|---:|---:|---:|---:|---|")
    for label, *_ in SEGMENTS:
        r = results[label]
        report.append(
            f"| {label} | {r['sparse_dup']*100:.2f}% | {r['dense_dup']*100:.2f}% | "
            f"{r['dup_gap_pts']:.2f} | {r['median_diff']:+.2f} | "
            f"{'**YES -- VOID**' if r['confounded'] else 'no'} |")
    report.append("")

    report.append("## Self-check 4 (common support, n>=20 both strata) per segment\n")
    report.append("| segment | usable bins | verdict |")
    report.append("|---|---:|---|")
    for label, *_ in SEGMENTS:
        r = results[label]
        verdict = "insufficient (<10)" if r["n_usable"] < 10 else "OK"
        report.append(f"| {label} | {r['n_usable']} | {verdict} |")
    report.append("")

    for label, *_ in SEGMENTS:
        r = results[label]
        report.append(f"## {label} per-bin recall\n")
        if r["confounded"]:
            report.append("**Duplicate-key gap is within an order of magnitude of the median "
                           "diff -- per spec S3#3 this segment is confounded and MUST NOT be "
                           "read.**\n")
            continue
        if r["n_usable"] < 10:
            report.append(f"**Only {r['n_usable']} usable bins (< 10) -- insufficient common "
                           "support per spec S3#4. Reporting the table below for the record, "
                           "but this segment's reading is not to be relied on alone.**\n")
        report.append("| SNR bin (dB) | sparse n | sparse matched | sparse recall | "
                       "sparse 95% CI | dense n | dense matched | dense recall | "
                       "dense 95% CI | diff (pts) |")
        report.append("|---:|---:|---:|---:|---|---:|---:|---:|---|---:|")
        for row in r["rows"]:
            report.append(
                f"| [{row['b']:.0f}, {row['b']+BIN_WIDTH:.0f}) | {row['s_tot']} | {row['s_m']} | "
                f"{row['s_recall']*100:.1f}% | [{row['s_ci'][0]*100:.1f}%,{row['s_ci'][1]*100:.1f}%] | "
                f"{row['d_tot']} | {row['d_m']} | {row['d_recall']*100:.1f}% | "
                f"[{row['d_ci'][0]*100:.1f}%,{row['d_ci'][1]*100:.1f}%] | {row['diff']:+.1f} |")
        report.append(f"\n**Median diff: {r['median_diff']:+.2f} pts. {r['n_ge8']}/{r['n_usable']} "
                       f"bins ({r['frac_ge8']*100:.0f}%) have diff >= 8 pts.**\n")
        outcome = reading_rule(r["median_diff"], r["frac_ge8"])
        report.append(f"**Mechanical outcome ({label}), Measurement D's spec S4 rule, "
                       f"unmodified: {outcome}**\n")
        print(f">>> {label}: {outcome}")

    report.append("## Summary\n")
    report.append("| | segment 1 | segment 2 |")
    report.append("|---|---:|---:|")
    r1, r2 = results["segment 1"], results["segment 2"]
    report.append(f"| cycles | {r1['n_cycles']} | {r2['n_cycles']} |")
    report.append(f"| usable bins | {r1['n_usable']} | {r2['n_usable']} |")
    report.append(f"| median diff (pts) | {r1['median_diff']:+.2f} | {r2['median_diff']:+.2f} |")
    report.append(f"| frac bins >= 8pts | {r1['frac_ge8']*100:.0f}% | {r2['frac_ge8']*100:.0f}% |")
    report.append("")
    report.append(
        "**Per R3, segment 1 is the better test** (larger sparse/dense stratum sizes) and is "
        "primary. If segment 2 shows `insufficient (<10)` above, that is reported as-is per "
        "the ruling's instruction, not pooled to rescue it.\n")

    report_path = os.path.join(out_dir, "measurement_d_segment_rerun_report.md")
    with open(report_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(report) + "\n")
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
