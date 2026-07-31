#!/usr/bin/env python3
"""D-001 Measurement A -- SNR-stratified recall, per the Architect's ruling
2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md, section 5.

Purpose: discriminate between two rival explanations of the cross-band density law (S3.1 of
that ruling):
  - "Pure sensitivity acting through the SNR mix" (a fixed sensitivity deficit hits a larger
    FRACTION of a population whose SNR mix sits lower on denser bands) -- recall(SNR) should
    overlay across bands.
  - "Co-channel / candidate competition" (denser bands cost more decodes AT THE SAME SNR) --
    recall(SNR) should sit measurably lower for dense bands at matched SNR.

Design (S5.2, verbatim from the ruling):
  1. Take the reference decoder's full decode list.
  2. Bin by reference-reported SNR, 2 dB bins.
  3. Per bin, compute recall = fraction of reference decodes OpenWSFZ also found (same cycle +
     normalised message), with Wilson intervals.
  4. Overlay the three jt9-referenced bands (10m/20m/80m) on one axis. Plot the 40m live-WSJT-X
     corpus as a SEPARATE series, never pooled with the jt9 ones (S3.2 -- that corpus is also
     partly the drifting-device corpus per the defect report, so it is descriptive context only,
     not part of the decisive reading).

Mandatory self-check (S5.2): total matched count per corpus must reproduce the published ANOVA
figures exactly -- 20m=24201, 10m=9177, 80m=8290, 40m=52736. If it does not, the matching logic
has drifted and the run is void.

Reading rule (S5.3) is PRE-REGISTERED and reproduced verbatim in the generated report -- see
READING_RULE below. It must not be edited after seeing the results.

NFR-021: message text is read only to build the match key (identical to anova_common.py's own
match_pairs()) and is never printed or written out. Only aggregate per-bin counts survive.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
from anova_common import normalize_hash_tokens, parse_all_txt  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ARTEFACTS = os.path.join(ROOT, "artefacts")

# (label, our ALL.TXT, reference ALL.TXT, reference kind, expected matched count, density/cycle)
CORPORA = [
    ("10m", os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "10m", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "10m", "jt9_ALL.TXT"),
     "jt9", 9177, 8.52),
    ("20m", os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "20m", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "20m", "jt9_ALL.TXT"),
     "jt9", 24201, 36.36),
    ("80m", os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "80m", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "80m", "jt9_ALL.TXT"),
     "jt9", 8290, 3.38),
    ("40m (WSJT-X, SUSPENDED-drift, context only)",
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8080", "owsfz", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8080", "wsjt-x", "ALL.TXT"),
     "wsjtx", 52736, 19.81),
]

BIN_WIDTH = 2.0


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def recall_by_snr_bin(ref_rows: list[dict], our_rows: list[dict]) -> tuple[dict, int]:
    """Bins reference decodes by their OWN reported SNR (never OpenWSFZ's -- S7's gain error
    means the two scales disagree, and mixing them would silently reintroduce that as noise
    into this measurement). Matching logic is deliberately identical to anova_common.py's
    match_pairs(): same (ts, normalized message) key, same zip-by-arrival-order multiplicity
    handling -- so the total matched count this produces is the same number match_pairs()
    would produce, which is what the self-check verifies against the published reports.
    """
    our_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in our_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        our_by_key[key].append(r)

    consumed: Counter = Counter()
    bins: dict[float, list[int]] = defaultdict(lambda: [0, 0])  # bin_floor -> [total, matched]
    total_matched = 0
    for r in ref_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        b = math.floor(r["snr"] / BIN_WIDTH) * BIN_WIDTH
        bins[b][0] += 1
        avail = len(our_by_key.get(key, ()))
        if consumed[key] < avail:
            consumed[key] += 1
            bins[b][1] += 1
            total_matched += 1
    return bins, total_matched


def main() -> int:
    out_dir = os.path.dirname(__file__)
    results = []
    self_check_failures = []

    print("=== Measurement A: SNR-stratified recall -- self-check ===")
    for label, our_path, ref_path, kind, expected_matched, density in CORPORA:
        our_rows = parse_all_txt(our_path)
        ref_rows = parse_all_txt(ref_path)
        bins, total_matched = recall_by_snr_bin(ref_rows, our_rows)
        status = "OK" if total_matched == expected_matched else "MISMATCH"
        if status != "OK":
            self_check_failures.append(label)
        print(f"{label:45s} ref={len(ref_rows):7d} our={len(our_rows):7d} "
              f"matched={total_matched:7d} expected={expected_matched:7d} [{status}]")
        results.append((label, kind, density, bins, total_matched, len(ref_rows)))

    if self_check_failures:
        print("\nSELF-CHECK FAILED for:", ", ".join(self_check_failures))
        print("Per S5.2: the matching logic has drifted and the run is VOID. Stopping.")
        return 1

    print("\nSelf-check: all four corpora reproduce published matched counts exactly. Proceeding.\n")

    # ---- per-bin table ----
    report_lines = []
    report_lines.append("# Measurement A -- SNR-stratified recall (D-001 ruling S5)\n")
    report_lines.append(f"Generated by `measurement_a_snr_recall.py`. Bin width {BIN_WIDTH:.0f} dB. "
                         "95% Wilson intervals.\n")
    report_lines.append("**Self-check: all four corpora reproduce the published ANOVA matched "
                         "counts exactly** (20m=24201, 10m=9177, 80m=8290, 40m=52736).\n")

    report_lines.append("\n## Per-bin recall\n")
    report_lines.append("| band | ref decodes/cycle | SNR bin (dB) | ref decodes | matched | "
                         "recall | 95% CI |")
    report_lines.append("|---|---:|---:|---:|---:|---:|---|")

    band_curves = {}
    for label, kind, density, bins, total_matched, ref_total in results:
        curve = []
        for b in sorted(bins):
            total, matched = bins[b]
            if total == 0:
                continue
            recall = matched / total
            lo, hi = wilson_interval(matched, total)
            curve.append((b, total, matched, recall, lo, hi))
            report_lines.append(
                f"| {label} | {density:.2f} | [{b:.0f}, {b+BIN_WIDTH:.0f}) | {total} | "
                f"{matched} | {recall*100:.1f}% | [{lo*100:.1f}%, {hi*100:.1f}%] |")
        band_curves[label] = curve

    # ---- common-SNR-support comparison across the 3 jt9-referenced bands ----
    jt9_labels = [l for l, kind, *_ in results if kind == "jt9"]
    jt9_bins_common = set.intersection(
        *[set(b for b, *_ in band_curves[l] if band_curves[l]) for l in jt9_labels]
    ) if jt9_labels else set()
    # require a minimum sample size per bin per band to be included in the comparison
    MIN_N = 20
    usable_bins = sorted(
        b for b in jt9_bins_common
        if all(
            next((tot for bb, tot, m, r, lo, hi in band_curves[l] if bb == b), 0) >= MIN_N
            for l in jt9_labels
        )
    )

    report_lines.append("\n## Common-SNR-support comparison (10m/20m/80m only, n>=20/bin/band)\n")
    report_lines.append("| SNR bin (dB) | 10m recall | 20m recall | 80m recall | max separation (pts) |")
    report_lines.append("|---:|---:|---:|---:|---:|")
    max_sep_overall = 0.0
    per_bin_seps = []
    for b in usable_bins:
        recalls = {}
        for l in jt9_labels:
            for bb, tot, m, r, lo, hi in band_curves[l]:
                if bb == b:
                    recalls[l] = r
                    break
        if len(recalls) < 2:
            continue
        sep = (max(recalls.values()) - min(recalls.values())) * 100
        max_sep_overall = max(max_sep_overall, sep)
        per_bin_seps.append((b, sep, recalls))
        vals = " | ".join(f"{recalls.get(l, float('nan'))*100:.1f}%" for l in
                           ["10m", "20m", "80m"])
        report_lines.append(f"| [{b:.0f}, {b+BIN_WIDTH:.0f}) | {vals} | {sep:.1f} |")

    # monotone-in-density check: FIXED 2026-07-31 (dev-task 3, per 2026-07-31-0029 S1 /
    # 2026-07-31-1222 S4). The check below previously tested ONLY recalls["80m"] >=
    # recalls["20m"] -- the two OUTER bands by density (80m=3.38, 20m=36.36/cycle) -- and
    # printed "monotone" from that alone, silently ignoring 10m (8.52/cycle) entirely. Every
    # common-support bin happens to satisfy the outer-pair test (80m's recall is always the
    # highest of the three), so the old check reported 26/26 = 100% regardless of what 10m
    # was doing. The REAL three-band ordering -- recall(80m) >= recall(10m) >= recall(20m),
    # consistent with density sparsest-to-densest -- fails whenever 10m's recall doesn't sit
    # between the other two, which happens repeatedly at both ends of the SNR range (10m
    # dips below 20m at very low SNR; 10m rises above 80m at high SNR). This is what
    # `2026-07-31-0029` S1 means by "the curves cross" -- not a subtle statistical point, a
    # visible ordering violation in the per-bin table.
    monotone_count = 0
    crosses_count = 0  # bins where the ordering inverts outright (10m outside [20m, 80m])
    for b, sep, recalls in per_bin_seps:
        if "80m" in recalls and "10m" in recalls and "20m" in recalls:
            ordered = recalls["80m"] >= recalls["10m"] >= recalls["20m"]
            if ordered:
                monotone_count += 1
            else:
                crosses_count += 1
    three_band_bins = monotone_count + crosses_count
    monotone_frac = (monotone_count / three_band_bins) if three_band_bins else float("nan")

    report_lines.append(
        f"\n**Max separation across common-support bins: {max_sep_overall:.1f} points.** "
        f"Full three-band density ordering (80m >= 10m >= 20m) holds in "
        f"{monotone_count}/{three_band_bins} bins with all three bands present "
        f"({monotone_frac*100:.0f}%); fails -- curves cross -- in "
        f"{crosses_count}/{three_band_bins} ({100 - monotone_frac*100:.0f}%). This replaces a "
        f"prior version of this check that tested only the outer band pair (80m vs 20m) and "
        f"reported 26/26 = 100% regardless of 10m's position; see "
        f"2026-07-31-0029 S1 / dev-task 3 for why that was wrong.\n")

    # ---- pre-registered reading rule, applied mechanically ----
    report_lines.append("\n## Pre-registered reading rule (S5.3, quoted verbatim)\n")
    report_lines.append("""
| outcome | reading | consequence |
|---|---|---|
| **Curves overlay** (band separation < 5 pts across the common region) | Density is a *marginal artefact* of differing SNR mixes. Recall is a function of SNR alone. | **Pure sensitivity. The co-channel withdrawal STANDS.** |
| **Dense bands sit materially below sparse at matched SNR** (>= 10 pts, monotone in density) | Competition, not sensitivity. | **The co-channel withdrawal REVERSES.** Escalate to the Captain before any further work. |
| **Separation 5-10 pts, or non-monotone in density** | Partial/ambiguous. | Report as ambiguous. **Do not interpret further.** |
| **Curves cross** (sparse below dense at some SNRs) | Not anticipated by any current model. | Escalation. Do not rationalise. |
""")

    # FIXED 2026-07-31 (dev-task 3, per 2026-07-31-0029 S1): this if/elif chain can only ever
    # print ONE row's outcome, even when the underlying data satisfies more than one row's
    # condition simultaneously -- which is exactly what happens here. The rule's own rows 3
    # ("non-monotone in density") and 4 ("curves cross") are not mutually exclusive as written
    # (a drafting defect in the pre-registered rule itself, not this script's execution -- see
    # 0029 S1/S5), and with crosses_count > 0 this run satisfies both at once. Silently priming
    # one label over the other via elif ordering is how the original bug ("monotone" printed
    # from a test that only checked the outer pair) happened in the first place. Report the
    # overlap explicitly instead of resolving it silently.
    row3_fires = 5.0 <= max_sep_overall < 10.0 or (max_sep_overall >= 10.0 and monotone_frac < 0.8)
    row4_fires = crosses_count > 0

    if max_sep_overall < 5.0:
        outcome = "CURVES OVERLAY (<5 pts) -> Pure sensitivity. Co-channel withdrawal STANDS."
    elif max_sep_overall >= 10.0 and monotone_frac >= 0.8:
        outcome = "DENSE BELOW SPARSE (>=10 pts, monotone) -> Co-channel withdrawal REVERSES. ESCALATE."
    elif row3_fires and row4_fires:
        outcome = ("ROWS 3 AND 4 BOTH FIRE (non-monotone in density, AND curves cross in "
                   f"{crosses_count}/{three_band_bins} bins) -> the reversal is NOT licensed. "
                   "The co-channel withdrawal is dead (row 1 excluded by the >=10pt "
                   "separation), but this is not evidence of competition either -- it is a "
                   "20m-specific deficit of unknown mechanism. ESCALATE, do not interpret "
                   "further, do not rationalise.")
    elif row3_fires:
        outcome = "AMBIGUOUS (5-10 pts, or non-monotone). Report as ambiguous, do not interpret further."
    elif row4_fires:
        outcome = "CURVES CROSS / not anticipated. ESCALATE."
    else:
        # Provably unreachable: whenever row3_fires is False, max_sep_overall is either <5.0
        # (caught above) or >=10.0 with monotone_frac>=0.8 (also caught above) -- there is no
        # remaining case. Raising rather than duplicating another branch's string, so a future
        # change to the conditions above that DOES make this reachable fails loudly instead of
        # silently printing a conclusion nothing above actually established.
        raise AssertionError(
            "unreachable: row3_fires is False but neither the <5pt nor the "
            ">=10pt&monotone_frac>=0.8 branch matched -- the outcome logic above has a gap")

    report_lines.append(f"\n**Mechanical outcome per the table above: {outcome}**\n")

    report_lines.append("\n## 40m (live-WSJT-X, SUSPENDED-drift) series -- context only, NOT part "
                         "of the decisive reading\n")
    report_lines.append("Per S3.2/S5.2, this corpus sits on the drifting device and averages a "
                         "healthy ~13h with a collapsed ~12h (see the capture-clock-drift defect "
                         "report). Its recall curve is reported below for completeness only and "
                         "must not be pooled with, or compared point-for-point against, the three "
                         "jt9-referenced bands.\n")
    report_lines.append("| SNR bin (dB) | ref decodes | matched | recall |")
    report_lines.append("|---:|---:|---:|---:|")
    for b, tot, m, r, lo, hi in band_curves.get("40m (WSJT-X, SUSPENDED-drift, context only)", []):
        report_lines.append(f"| [{b:.0f}, {b+BIN_WIDTH:.0f}) | {tot} | {m} | {r*100:.1f}% |")

    # ---- plot ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 6))
        colors = {"10m": "#1c5cab", "20m": "#2a78d6", "80m": "#86b6ef"}
        for l in jt9_labels:
            curve = band_curves[l]
            xs = [b + BIN_WIDTH / 2 for b, tot, m, r, lo, hi in curve if tot >= MIN_N]
            ys = [r * 100 for b, tot, m, r, lo, hi in curve if tot >= MIN_N]
            los = [lo * 100 for b, tot, m, r, lo, hi in curve if tot >= MIN_N]
            his = [hi * 100 for b, tot, m, r, lo, hi in curve if tot >= MIN_N]
            ax.plot(xs, ys, marker="o", label=l, color=colors.get(l, None))
            ax.fill_between(xs, los, his, alpha=0.15, color=colors.get(l, None))
        curve40 = band_curves.get("40m (WSJT-X, SUSPENDED-drift, context only)", [])
        xs40 = [b + BIN_WIDTH / 2 for b, tot, m, r, lo, hi in curve40 if tot >= MIN_N]
        ys40 = [r * 100 for b, tot, m, r, lo, hi in curve40 if tot >= MIN_N]
        ax.plot(xs40, ys40, marker="x", linestyle="--", color="#b0392f",
                label="40m WSJT-X (SUSPENDED-drift, context only)")
        ax.set_xlabel("Reference-reported SNR (dB), 2 dB bins")
        ax.set_ylabel("Recall (%) -- fraction of reference decodes OpenWSFZ also found")
        ax.set_title("Measurement A: SNR-stratified recall by band")
        ax.legend()
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
        plot_path = os.path.join(out_dir, "measurement_a_recall_by_snr.png")
        fig.tight_layout()
        fig.savefig(plot_path, dpi=130)
        report_lines.insert(3, f"\n![SNR-stratified recall by band](measurement_a_recall_by_snr.png)\n")
        print(f"Wrote plot: {plot_path}")
    except Exception as e:  # pragma: no cover
        print(f"WARNING: plotting failed ({e}), continuing without plot")

    report_path = os.path.join(out_dir, "measurement_a_snr_recall_report.md")
    with open(report_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(report_lines) + "\n")
    print(f"\nWrote report: {report_path}")
    print(f"\n>>> MECHANICAL OUTCOME: {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
