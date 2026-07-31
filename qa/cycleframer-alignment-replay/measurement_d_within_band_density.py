#!/usr/bin/env python3
"""D-001 Measurement D -- within-band density stratification, per the Architect's spec
2026-07-31-0853-architect-to-qa-measurement-d-spec-within-band-density.md.

Purpose: Measurement A found 20m recalls 10-35 points below 10m/80m at matched reference SNR,
but band identity and band density are fully confounded across corpora (three bands = three
densities = three antennas = three propagation environments). This measurement breaks the
confound by stratifying INSIDE a single band: 20m's own cycles vary in density by p90/p10=2.23.
Comparing dense-vs-sparse 20m cycles at matched reference SNR holds every band-specific factor
constant.

  - recall falls with per-cycle density INSIDE the band -> competition is real and general,
    not about 20m specifically.
  - recall is flat across 20m's own density range -> the cross-band effect is 20m-specific;
    the density law is withdrawn entirely.

Design (spec S2, verbatim):
  1. Density(cycle) = the REFERENCE decoder's (jt9) decode count for that cycle. Never ours --
     using our own count is circular (cycles we did badly on would be labelled sparse by
     construction).
  2. Rank CYCLES (not decodes) by density. Sparse = bottom quartile of cycles, dense = top
     quartile.
  3. Bin reference decodes by the REFERENCE's own reported SNR, 2dB bins -- never OpenWSFZ's
     (the S7 gain error, slope 0.6865, would re-enter as noise).
  4. Per bin per stratum: recall = matched/total, 95% Wilson intervals.
  5. diff(b) = recall_sparse(b) - recall_dense(b), common-support bins only (n>=20 both strata).
  6. Matching reused from anova_common.py-style single-pass greedy consumption (identical to
     measurement_a_snr_recall.py's recall_by_snr_bin) -- resolved ONCE over the full corpus;
     the stratum filter only selects which reference rows enter which stratum's bins. Middle-
     quartile cycles still participate in the single matching pass (preserving global
     consumption order) but their decodes are not tallied into either stratum's bins.

The reading is taken on 20m only. 10m/80m are free replication, reported but not decisive.

Mandatory self-checks (spec S3), ALL before any reading -- a failure voids the run:
  1. Matching gate: full-corpus matched count per band reproduces the published ANOVA figure
     exactly (20m=24201, 10m=9177, 80m=8290).
  2. Density contrast: mean ref decodes/cycle per stratum, per band; <2x on 20m is too close
     to read.
  3. Duplicate-key artefact: the matcher is greedy and dense cycles carry more repeated
     messages, so a denser stratum can show lower recall for purely clerical reasons unrelated
     to the decoder. Measure the duplicate-key rate in each stratum; if the dense-minus-sparse
     gap is within an order of magnitude of the observed recall difference, the result is
     confounded and must not be read.
  4. Common support: number of usable bins (n>=20 both strata) per band; <~10 on 20m is
     insufficient support.

Reading rule (spec S4) is PRE-REGISTERED, evaluated in STRICT ORDER (first match wins -- no two
rows can both fire, unlike Measurement A's rule), and reproduced verbatim in the report. It must
not be edited after seeing results.

NFR-021: message text is read only to build the match key (identical to anova_common.py's own
match_pairs()) and is never printed or written out. Only aggregate per-bin counts survive.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import math
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
from anova_common import normalize_hash_tokens, parse_all_txt, parse_cycle_ts  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ARTEFACTS = os.path.join(ROOT, "artefacts")
CORPUS_ROOT = os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz")

# (label, our ALL.TXT, reference (jt9) ALL.TXT, expected matched count, is_decisive)
BANDS = [
    ("20m", os.path.join(CORPUS_ROOT, "20m", "ALL.TXT"),
     os.path.join(CORPUS_ROOT, "20m", "jt9_ALL.TXT"), 24201, True),
    ("10m", os.path.join(CORPUS_ROOT, "10m", "ALL.TXT"),
     os.path.join(CORPUS_ROOT, "10m", "jt9_ALL.TXT"), 9177, False),
    ("80m", os.path.join(CORPUS_ROOT, "80m", "ALL.TXT"),
     os.path.join(CORPUS_ROOT, "80m", "jt9_ALL.TXT"), 8290, False),
]

BIN_WIDTH = 2.0
MIN_N = 20  # minimum n per bin per stratum to be "usable" (common support)


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion k/n. Identical to
    measurement_a_snr_recall.py's own implementation -- reused convention."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def quartile_cutoffs(values: list[float]) -> tuple[float, float]:
    """Returns (q1, q3) using the same method as Python's statistics.quantiles (exclusive
    method, n=4) -- a single, standard, reproducible definition, not a hand-rolled one."""
    qs = statistics.quantiles(values, n=4, method="exclusive")
    return qs[0], qs[2]  # q1, q3


def stratify_cycles(ref_rows: list[dict]) -> tuple[dict[str, str], dict[str, int], float, float]:
    """Density(cycle) = reference decoder's OWN decode count for that cycle (spec S2 step 1 --
    never ours, circularity). Ranks CYCLES (not decodes) by density; bottom quartile of the
    cycle list = sparse, top quartile = dense, per spec S2 step 2. Returns
    (cycle -> stratum label ('sparse'/'dense'/'middle'), cycle -> density, q1_density,
    q3_density)."""
    density_by_cycle: dict[str, int] = Counter()
    for r in ref_rows:
        density_by_cycle[r["ts"]] += 1

    cycles = list(density_by_cycle.keys())
    densities = [density_by_cycle[c] for c in cycles]
    q1, q3 = quartile_cutoffs(densities)

    stratum: dict[str, str] = {}
    for c in cycles:
        d = density_by_cycle[c]
        if d <= q1:
            stratum[c] = "sparse"
        elif d >= q3:
            stratum[c] = "dense"
        else:
            stratum[c] = "middle"
    return stratum, dict(density_by_cycle), q1, q3


def matched_stratified_bins(
    ref_rows: list[dict], our_rows: list[dict], stratum: dict[str, str]
) -> tuple[dict[str, dict[float, list[int]]], int]:
    """Single-pass greedy matching over the FULL corpus (arrival order = ref_rows' own order),
    identical in mechanism to measurement_a_snr_recall.py's recall_by_snr_bin -- the stratum
    filter only decides which stratum's bin table a given reference row's outcome is tallied
    into; it does NOT change the global consumption order (spec S2's constraint: matching
    resolved once, not re-resolved per stratum). Middle-quartile cycles' rows still consume
    from `our_by_key` in their natural arrival position (preserving the correct global order)
    but are not tallied into either stratum's bins. Returns
    ({'sparse': {bin: [total, matched]}, 'dense': {...}}, total_matched_full_corpus).
    """
    our_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in our_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        our_by_key[key].append(r)

    consumed: Counter = Counter()
    bins: dict[str, dict[float, list[int]]] = {
        "sparse": defaultdict(lambda: [0, 0]),
        "dense": defaultdict(lambda: [0, 0]),
    }
    total_matched = 0
    for r in ref_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        avail = len(our_by_key.get(key, ()))
        is_match = consumed[key] < avail
        if is_match:
            consumed[key] += 1
            total_matched += 1

        strat = stratum.get(r["ts"])
        if strat not in ("sparse", "dense"):
            continue  # middle quartile -- still consumed above, not tallied into either bin
        b = math.floor(r["snr"] / BIN_WIDTH) * BIN_WIDTH
        bins[strat][b][0] += 1
        if is_match:
            bins[strat][b][1] += 1

    return bins, total_matched


def duplicate_key_rate(ref_rows: list[dict], stratum: dict[str, str], which: str) -> float:
    """Self-check 3 (spec S3#3): fraction of a stratum's reference rows whose (cycle,
    normalised-message) key is shared by more than one reference row WITHIN THAT STRATUM.
    Dense cycles carry more repeated messages (more traffic -> more re-transmissions of the
    same message across a QSO), and the matcher is greedy, so a denser stratum can show lower
    recall for purely clerical multiplicity reasons unrelated to the decoder itself."""
    keys_in_stratum = [
        (r["ts"], normalize_hash_tokens(r["message"]))
        for r in ref_rows if stratum.get(r["ts"]) == which
    ]
    if not keys_in_stratum:
        return float("nan")
    counts = Counter(keys_in_stratum)
    dup_rows = sum(c for c in counts.values() if c > 1)
    return dup_rows / len(keys_in_stratum)


def median_or_nan(vals: list[float]) -> float:
    return statistics.median(vals) if vals else float("nan")


def main() -> int:
    out_dir = os.path.dirname(__file__)
    report_lines: list[str] = []
    report_lines.append("# Measurement D -- within-band density stratification (D-001)\n")
    report_lines.append(
        "Spec: `2026-07-31-0853-architect-to-qa-measurement-d-spec-within-band-density.md`. "
        "Reading taken on **20m** only; 10m/80m are free replication, reported not decisive.\n")

    print("=== Measurement D: self-check 1 (matching gate) ===")
    self_check_failures: list[str] = []
    band_data = {}
    for label, our_path, ref_path, expected_matched, decisive in BANDS:
        our_rows = parse_all_txt(our_path)
        ref_rows = parse_all_txt(ref_path)
        stratum, density_by_cycle, q1, q3 = stratify_cycles(ref_rows)
        bins, total_matched = matched_stratified_bins(ref_rows, our_rows, stratum)
        status = "OK" if total_matched == expected_matched else "MISMATCH"
        if status != "OK":
            self_check_failures.append(label)
        print(f"{label:5s} ref={len(ref_rows):7d} our={len(our_rows):7d} "
              f"matched={total_matched:7d} expected={expected_matched:7d} [{status}]")
        band_data[label] = dict(
            our_rows=our_rows, ref_rows=ref_rows, stratum=stratum,
            density_by_cycle=density_by_cycle, q1=q1, q3=q3, bins=bins,
            total_matched=total_matched, decisive=decisive,
        )

    if self_check_failures:
        print("\nSELF-CHECK 1 FAILED for:", ", ".join(self_check_failures))
        print("Matching logic has drifted. RUN IS VOID. Stopping.")
        report_lines.append("## Self-check 1 (matching gate) -- FAILED\n")
        report_lines.append(f"Mismatch: {', '.join(self_check_failures)}. **RUN IS VOID. "
                             "Do not read anything below.**\n")
        with open(os.path.join(out_dir, "measurement_d_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report_lines) + "\n")
        return 1
    print("Self-check 1: all bands reproduce published ANOVA matched counts exactly. PASS.\n")
    report_lines.append("## Self-check 1 -- matching gate: PASS\n")
    report_lines.append("All three bands reproduce the published ANOVA matched counts exactly "
                         "(20m=24201, 10m=9177, 80m=8290).\n")

    # ---- self-check 2: density contrast ----
    print("=== self-check 2: density contrast ===")
    report_lines.append("## Self-check 2 -- density contrast achieved\n")
    report_lines.append("| band | sparse mean ref decodes/cycle | dense mean ref decodes/cycle "
                         "| contrast (dense/sparse) |")
    report_lines.append("|---|---:|---:|---:|")
    contrast_void = False
    for label, *_ in BANDS:
        d = band_data[label]
        sparse_cycles = [c for c, s in d["stratum"].items() if s == "sparse"]
        dense_cycles = [c for c, s in d["stratum"].items() if s == "dense"]
        sparse_mean = statistics.mean(d["density_by_cycle"][c] for c in sparse_cycles)
        dense_mean = statistics.mean(d["density_by_cycle"][c] for c in dense_cycles)
        contrast = dense_mean / sparse_mean if sparse_mean else float("nan")
        print(f"{label:5s} sparse={sparse_mean:.2f}/cyc dense={dense_mean:.2f}/cyc "
              f"contrast={contrast:.2f}x")
        report_lines.append(f"| {label} | {sparse_mean:.2f} | {dense_mean:.2f} | {contrast:.2f}x |")
        if label == "20m" and contrast < 2.0:
            contrast_void = True
        band_data[label]["contrast"] = contrast
        band_data[label]["sparse_mean_density"] = sparse_mean
        band_data[label]["dense_mean_density"] = dense_mean
    if contrast_void:
        report_lines.append("\n**20m's density contrast is below 2x -- strata too close to "
                             "read per spec S3#2. RUN IS VOID.**\n")
        print("\n20m contrast below 2x. RUN IS VOID.")
        with open(os.path.join(out_dir, "measurement_d_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report_lines) + "\n")
        return 1
    report_lines.append("")

    # ---- per-band bin tables + diff ----
    all_band_results = {}
    for label, *_ in BANDS:
        d = band_data[label]
        bins = d["bins"]
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
                              d_tot=d_tot, d_m=d_m, d_recall=d_recall, d_ci=(d_lo, d_hi),
                              diff=diff))
        all_band_results[label] = rows

    # ---- self-check 3: duplicate-key artefact ----
    print("=== self-check 3: duplicate-key artefact ===")
    report_lines.append("## Self-check 3 -- duplicate-key artefact\n")
    report_lines.append("| band | sparse dup-key rate | dense dup-key rate | gap (pts) | "
                         "median diff (pts) | confounded? |")
    report_lines.append("|---|---:|---:|---:|---:|---|")
    for label, *_ in BANDS:
        d = band_data[label]
        sparse_dup = duplicate_key_rate(d["ref_rows"], d["stratum"], "sparse")
        dense_dup = duplicate_key_rate(d["ref_rows"], d["stratum"], "dense")
        dup_gap_pts = abs(dense_dup - sparse_dup) * 100
        med_diff = median_or_nan([r["diff"] for r in all_band_results[label]])
        confounded = (not math.isnan(med_diff)) and dup_gap_pts >= abs(med_diff) / 10.0
        print(f"{label:5s} sparse_dup={sparse_dup*100:.2f}% dense_dup={dense_dup*100:.2f}% "
              f"gap={dup_gap_pts:.2f}pts median_diff={med_diff:.2f}pts "
              f"confounded={'YES' if confounded else 'no'}")
        report_lines.append(
            f"| {label} | {sparse_dup*100:.2f}% | {dense_dup*100:.2f}% | {dup_gap_pts:.2f} | "
            f"{med_diff:.2f} | {'**YES -- VOID**' if confounded else 'no'} |")
        band_data[label]["dup_gap_pts"] = dup_gap_pts
        band_data[label]["median_diff"] = med_diff
        band_data[label]["confounded"] = confounded
    report_lines.append("")

    if band_data["20m"]["confounded"]:
        report_lines.append("**20m's duplicate-key gap is within an order of magnitude of its "
                             "median diff -- per spec S3#3, the result is confounded and MUST "
                             "NOT be read. RUN IS VOID on the decisive band.**\n")
        print("\n20m CONFOUNDED per self-check 3. RUN IS VOID on the decisive band.")
        with open(os.path.join(out_dir, "measurement_d_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report_lines) + "\n")
        return 1

    # ---- self-check 4: common support ----
    print("=== self-check 4: common support ===")
    report_lines.append("## Self-check 4 -- common support (usable bins, n>=20 both strata)\n")
    report_lines.append("| band | usable bins |")
    report_lines.append("|---|---:|")
    support_void = False
    for label, *_ in BANDS:
        n_usable = len(all_band_results[label])
        print(f"{label:5s} usable_bins={n_usable}")
        report_lines.append(f"| {label} | {n_usable} |")
        if label == "20m" and n_usable < 10:
            support_void = True
    report_lines.append("")
    if support_void:
        report_lines.append("**20m has fewer than ~10 usable bins -- insufficient support per "
                             "spec S3#4. RUN IS VOID.**\n")
        print("\n20m insufficient common support. RUN IS VOID.")
        with open(os.path.join(out_dir, "measurement_d_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report_lines) + "\n")
        return 1

    print("\nAll four self-checks pass. Proceeding to the per-bin tables and the reading.\n")
    report_lines.append("**All four self-checks pass.**\n")

    # ---- per-bin tables ----
    for label, *_ in BANDS:
        d = band_data[label]
        report_lines.append(f"## {label} per-bin recall{'  (DECISIVE)' if d['decisive'] else ''}\n")
        report_lines.append(f"Sparse stratum cutoff: density <= {d['q1']:.1f} ref decodes/cycle. "
                             f"Dense stratum cutoff: density >= {d['q3']:.1f} ref decodes/cycle.\n")
        report_lines.append("| SNR bin (dB) | sparse n | sparse matched | sparse recall | "
                             "sparse 95% CI | dense n | dense matched | dense recall | "
                             "dense 95% CI | diff (pts) |")
        report_lines.append("|---:|---:|---:|---:|---|---:|---:|---:|---|---:|")
        for r in all_band_results[label]:
            report_lines.append(
                f"| [{r['b']:.0f}, {r['b']+BIN_WIDTH:.0f}) | {r['s_tot']} | {r['s_m']} | "
                f"{r['s_recall']*100:.1f}% | [{r['s_ci'][0]*100:.1f}%,{r['s_ci'][1]*100:.1f}%] | "
                f"{r['d_tot']} | {r['d_m']} | {r['d_recall']*100:.1f}% | "
                f"[{r['d_ci'][0]*100:.1f}%,{r['d_ci'][1]*100:.1f}%] | {r['diff']:+.1f} |")
        med = band_data[label]["median_diff"]
        n_ge8 = sum(1 for r in all_band_results[label] if r["diff"] >= 8.0)
        frac_ge8 = n_ge8 / len(all_band_results[label]) if all_band_results[label] else float("nan")
        report_lines.append(f"\n**Median diff: {med:+.2f} pts. {n_ge8}/{len(all_band_results[label])} "
                             f"bins ({frac_ge8*100:.0f}%) have diff >= 8 pts.**\n")
        band_data[label]["frac_ge8"] = frac_ge8

    # ---- reading rule, quoted verbatim, applied to 20m only ----
    report_lines.append("## Reading rule (spec S4, quoted verbatim)\n")
    report_lines.append("""
| # | condition | reading | consequence |
|---|---|---|---|
| 1 | median `diff` >= 8 pts AND >= 80% of usable bins have `diff >= 8` | At the same signal strength we miss more when the band is busier, with band identity held constant. | **Competition confirmed as a named, measured mechanism.** Row 4's decomposition re-scopes toward it. **Escalate to the Captain before any engineering.** |
| 2 | else if -3 < median `diff` < 3 | Density does not act within a band. | **The cross-band effect is 20m-specific and the density law is withdrawn entirely.** Row 4's target reverts to sensitivity/front-end. The 20m deficit becomes its own bounded question. |
| 3 | else if median `diff` <= -3 | Sparse recalls worse than dense. Not anticipated by any current model. | **Escalate. Do not rationalise it in the findings document.** |
| 4 | else | Partial. | **Report as ambiguous. Do not interpret.** Escalate. |

Evaluated in strict order; the first row that matches is the outcome.
""")

    m20 = band_data["20m"]["median_diff"]
    f20 = band_data["20m"]["frac_ge8"]
    if m20 >= 8.0 and f20 >= 0.8:
        outcome = ("ROW 1: median diff >= 8pts AND >= 80% of bins >= 8pts -> Competition "
                   "CONFIRMED as a named, measured mechanism. ESCALATE before any engineering.")
    elif -3.0 < m20 < 3.0:
        outcome = ("ROW 2: -3 < median diff < 3 -> Density does not act within 20m. The "
                   "cross-band effect is 20m-SPECIFIC. The density law is WITHDRAWN entirely.")
    elif m20 <= -3.0:
        outcome = ("ROW 3: median diff <= -3 -> sparse recalls WORSE than dense. Not "
                   "anticipated. ESCALATE. Do not rationalise.")
    else:
        outcome = "ROW 4: partial/ambiguous. Report as ambiguous. Do not interpret. ESCALATE."

    report_lines.append(f"\n**Mechanical outcome on 20m (decisive): {outcome}**\n")
    print(f">>> 20m median diff = {m20:+.2f} pts, frac(diff>=8pts) = {f20*100:.0f}%")
    print(f">>> MECHANICAL OUTCOME (20m, decisive): {outcome}")

    # ---- descriptive extras (not subject to the reading rule) ----
    report_lines.append("## Descriptive extras (NOT subject to the reading rule -- inform "
                         "mechanism, do not decide it)\n")

    report_lines.append("### Effect size vs density contrast, across all three bands\n")
    report_lines.append("| band | density contrast (dense/sparse) | median diff (pts) |")
    report_lines.append("|---|---:|---:|")
    for label, *_ in BANDS:
        d = band_data[label]
        report_lines.append(f"| {label} | {d['contrast']:.2f}x | {d['median_diff']:+.2f} |")
    report_lines.append(
        "\nIf the effect scales with the *ratio* between strata (contrast), it is a density "
        "law; if it scales with *absolute* density (appearing only where occupancy is high "
        "regardless of contrast), it is a threshold -- a different mechanism, a different "
        "engineering target. Descriptive only.\n")

    report_lines.append("### Our decodes per cycle vs the reference's, bucketed by reference "
                         "density (capacity-ceiling check)\n")
    report_lines.append("| band | ref decodes/cycle bucket | mean ref/cycle | mean ours/cycle |")
    report_lines.append("|---|---|---:|---:|")
    for label, *_ in BANDS:
        d = band_data[label]
        our_by_cycle: dict[str, int] = Counter()
        for r in d["our_rows"]:
            our_by_cycle[r["ts"]] += 1
        # Bucket cycles by ref density decile-ish (quartile-based, reusing q1/q3 plus a
        # top-half/bottom-half split within [q1,q3) for a 4-bucket view) -- descriptive, not
        # part of any reading rule, so a simple quartile-based bucketing is sufficient.
        cycles = list(d["density_by_cycle"].keys())
        dens_sorted = sorted(d["density_by_cycle"][c] for c in cycles)
        n = len(dens_sorted)
        cut1 = dens_sorted[n // 4]
        cut2 = dens_sorted[n // 2]
        cut3 = dens_sorted[(3 * n) // 4]
        buckets = {"Q1 (sparsest)": [], "Q2": [], "Q3": [], "Q4 (densest)": []}
        for c in cycles:
            dens = d["density_by_cycle"][c]
            ours = our_by_cycle.get(c, 0)
            if dens <= cut1:
                buckets["Q1 (sparsest)"].append((dens, ours))
            elif dens <= cut2:
                buckets["Q2"].append((dens, ours))
            elif dens <= cut3:
                buckets["Q3"].append((dens, ours))
            else:
                buckets["Q4 (densest)"].append((dens, ours))
        for bucket_name, pairs in buckets.items():
            if not pairs:
                continue
            mean_ref = statistics.mean(p[0] for p in pairs)
            mean_ours = statistics.mean(p[1] for p in pairs)
            report_lines.append(f"| {label} | {bucket_name} | {mean_ref:.2f} | {mean_ours:.2f} |")
    report_lines.append(
        "\nIf our per-cycle output flattens while the reference's keeps rising across "
        "buckets, that is a capacity ceiling, visible directly in this table. Descriptive "
        "only, not part of the reading rule.\n")

    # ---- plot (20m only, the decisive band) ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 6))
        rows20 = all_band_results["20m"]
        xs = [r["b"] + BIN_WIDTH / 2 for r in rows20]
        sparse_ys = [r["s_recall"] * 100 for r in rows20]
        dense_ys = [r["d_recall"] * 100 for r in rows20]
        sparse_lo = [r["s_ci"][0] * 100 for r in rows20]
        sparse_hi = [r["s_ci"][1] * 100 for r in rows20]
        dense_lo = [r["d_ci"][0] * 100 for r in rows20]
        dense_hi = [r["d_ci"][1] * 100 for r in rows20]
        ax.plot(xs, sparse_ys, marker="o", label="sparse (bottom quartile)", color="#2a78d6")
        ax.fill_between(xs, sparse_lo, sparse_hi, alpha=0.15, color="#2a78d6")
        ax.plot(xs, dense_ys, marker="o", label="dense (top quartile)", color="#b0392f")
        ax.fill_between(xs, dense_lo, dense_hi, alpha=0.15, color="#b0392f")
        ax.set_xlabel("Reference-reported SNR (dB), 2 dB bins")
        ax.set_ylabel("Recall (%) -- fraction of reference decodes OpenWSFZ also found")
        ax.set_title("Measurement D: 20m within-band density stratification")
        ax.legend()
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
        plot_path = os.path.join(out_dir, "measurement_d_recall_by_snr.png")
        fig.tight_layout()
        fig.savefig(plot_path, dpi=130)
        report_lines.insert(2, "\n![20m sparse vs dense recall by SNR](measurement_d_recall_by_snr.png)\n")
        print(f"Wrote plot: {plot_path}")
    except Exception as e:  # pragma: no cover
        print(f"WARNING: plotting failed ({e}), continuing without plot")

    report_path = os.path.join(out_dir, "measurement_d_report.md")
    with open(report_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(report_lines) + "\n")
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
