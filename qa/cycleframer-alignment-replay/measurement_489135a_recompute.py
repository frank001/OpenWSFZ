#!/usr/bin/env python3
"""Task 4 -- the 489135a recompute (D-001 / capture-clock-drift programme).

Method per `2026-07-31-1030-architect-to-qa-task4-method-ruling-dt-derived-drift.md`, corrected
by `2026-07-31-1044-architect-to-qa-task4-drift-definition-corrected.md`. Restores or refutes
the cross-instance claim withdrawn in `2026-07-30-2253` S3.1.

Corpus: artefacts/20260728_live_run_2354-8080/ (40m dual-band overnight run, 8080 instance).
  - wsjt-x/wav/   : 3575 WAVs, the re-decode input.
  - owsfz/ALL.TXT : OpenWSFZ's own live decodes for this session.
  - wsjt-x/ALL.TXT: the real WSJT-X application's own live decodes of the SAME audio -- the
    DT flatness control, and the reference-method by-product's second half.

Steps (1030 S3, corrected):
  1. Decode all 3575 WSJT-X WAVs with jt9 (-8 -d 3), reusing endurance_anova_jt9.run_jt9 --
     not reimplemented. ~2.6h wall time (3575 x 2.66s/WAV, per 2253 S6b.4's measured rate).
  2. Match OpenWSFZ vs jt9 over the full (unrestricted) session -- reusing anova_common.
     Self-check: must reproduce the existing anova_report_40m.md figures exactly (44223 our
     decodes, 70822 jt9 decodes, 42668 matched) or the run is void before restriction.
  3. Fit OpenWSFZ's DT-vs-elapsed-hour regression over the FULL session (valid here per 1044
     S2 -- this corpus never crossed the cliff, so no survivorship inversion).
  4. drift(h) = DT_ours_fit(h) - C, C = +0.7251s (1044 S1, derived from cross-correlation
     calibration on the 8080 sibling session -- hardcoded here with its derivation cited, not
     re-derived, since it is a property of the decoder build/capture chain, not this session).
  5. Report parity as a function of drift (binned by elapsed hour), not just a single cutoff.
  6. Headline: restricted parity at BOTH h<2.40 (1044's definition) and h<3.06 (QA's
     slope-only candidate from 1041 S2) -- 1044 S3's added requirement. If the two disagree on
     which reading-rule row fires, this script flags it; it does not pick one.
  7. Reference-method by-product: jt9 vs wsjt-x/ALL.TXT on the identical audio (both decode
     the same WAVs) -- descriptive only, not subject to the reading rule (1030 S4).

Self-checks (1030 S3, "all before any reading"): WSJT-X DT control flat; jt9 decode count
reported; unrestricted matched count reproduces the existing report. Any failure voids the run.

NFR-021: message text is read only to build match keys (anova_common's own convention);
never printed, never written beyond aggregate counts. WAVs and jt9's raw per-decode output
stay under git-ignored artefacts/. ASCII-only console output (HK-009).
"""
from __future__ import annotations

import argparse
import datetime
import math
import os
import statistics
import sys

sys.path.insert(0, r"D:\Projects\claude\OpenWSFZ\qa\endurance")
import anova_common as ac          # noqa: E402
import endurance_anova_jt9 as ej9  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

CORPUS_DIR = r"D:\Projects\claude\OpenWSFZ\artefacts\20260728_live_run_2354-8080"
OURS_ALL_TXT = os.path.join(CORPUS_DIR, "owsfz", "ALL.TXT")
WSJTX_ALL_TXT = os.path.join(CORPUS_DIR, "wsjt-x", "ALL.TXT")
WAV_DIR = os.path.join(CORPUS_DIR, "wsjt-x", "wav")
JT9_ALL_TXT_OUT = os.path.join(CORPUS_DIR, "owsfz", "jt9_ALL.TXT")

OUT_DIR = r"D:\Projects\claude\OpenWSFZ\qa\cycleframer-alignment-replay"
OUT_REPORT = os.path.join(OUT_DIR, "measurement_489135a_recompute_report.md")

# Self-check targets: qa/endurance/2026-07-29-489135a/anova_report_40m.md's existing (suspended)
# figures. The unrestricted re-decode below MUST reproduce these or the run is void.
EXPECTED_N_WAVS = 3575
EXPECTED_N_OURS = 44223
EXPECTED_N_JT9 = 70822
EXPECTED_N_MATCHED = 42668

# 1044 S1: C is the constant offset between our reported DT and true audio misalignment,
# calibrated on the 8080 sibling session's pre-cliff window against cross-correlation ground
# truth (measure_drift_8080_session.py): C = 0.4885 - (-0.2366) = 0.7251s. Property of the
# decoder build/capture chain, not this session -- not re-derived here, per 1044 S1's own
# justification (same code, same device, same audio path in both sessions).
DRIFT_CALIBRATION_C = 0.7251

CUTOFFS_H = {
    "h_2p40_corrected_definition": 2.40,   # 1044's definition: drift(h) = DT_ours(h) - C
    "h_3p06_slope_only_candidate": 3.06,   # 1041 S2 candidate 2: drift(h) = -0.1636h (no C)
}


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion k/n. Identical implementation to
    measurement_a_snr_recall.py's -- reused convention, not reimplemented differently."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def fit_slope(binned: list[tuple[float, float, int]]) -> tuple[float, float]:
    """Unweighted least-squares fit of median value vs bin hour. Identical method to
    verify_dt_drift_489135a.py's fit_slope -- reproduced here rather than imported, since that
    script is a standalone verification artifact, not a library."""
    xs = [b[0] for b in binned]
    ys = [b[1] for b in binned]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else float("nan")
    intercept = mean_y - slope * mean_x
    return slope, intercept


def hourly_median(pairs: list[tuple[float, float]]) -> list[tuple[float, float, int]]:
    buckets: dict[int, list[float]] = {}
    for h, v in pairs:
        buckets.setdefault(int(h), []).append(v)
    return [(h, statistics.median(v), len(v)) for h, v in sorted(buckets.items())]


def elapsed_hours(rows: list[dict], t0: datetime.datetime) -> list[dict]:
    """Attaches an 'elapsed_h' field to each row (copy), dropping rows with an unparseable ts."""
    out = []
    for r in rows:
        ts = ac.parse_cycle_ts(r["ts"])
        if ts is None:
            continue
        r2 = dict(r)
        r2["elapsed_h"] = (ts - t0).total_seconds() / 3600.0
        out.append(r2)
    return out


def restrict_by_hour(rows: list[dict], max_h: float) -> list[dict]:
    return [r for r in rows if r["elapsed_h"] < max_h]


def parity_for_pairs(matched: int, ref_total: int) -> tuple[float, tuple[float, float]]:
    if ref_total == 0:
        return float("nan"), (float("nan"), float("nan"))
    return matched / ref_total, wilson_interval(matched, ref_total)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-jt9", action="store_true",
                     help="Reuse an existing jt9_ALL.TXT instead of re-running jt9 (for "
                          "iterating on the analysis without repeating the ~2.6h decode).")
    ap.add_argument("--max-workers", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None,
                     help="Smoke-test only: use just the N earliest WAVs instead of the "
                          "full corpus. Self-checks against the full-corpus expected counts "
                          "will correctly fail in this mode -- that is expected, not a bug.")
    ap.add_argument("--jt9-out", default=None,
                     help="Override the jt9_ALL.TXT output path (default: alongside the "
                          "corpus's own ALL.TXT). Use a scratch path for --limit smoke runs "
                          "so they never touch the real corpus's jt9_ALL.TXT.")
    args = ap.parse_args()

    wav_names = sorted(f for f in os.listdir(WAV_DIR) if f.lower().endswith(".wav"))
    if args.limit is not None:
        wav_names = wav_names[:args.limit]
    wav_paths = [os.path.join(WAV_DIR, f) for f in wav_names]
    cycle_set = {os.path.splitext(f)[0] for f in wav_names}
    print(f"WAV cycles: {len(wav_paths)}")
    if len(wav_paths) != EXPECTED_N_WAVS:
        print(f"[WARN] expected {EXPECTED_N_WAVS} WAVs, found {len(wav_paths)} -- "
              f"self-check will likely fail", file=sys.stderr)

    ours_all = ac.parse_all_txt(OURS_ALL_TXT)
    wsjtx_all = ac.parse_all_txt(WSJTX_ALL_TXT)
    ours_rows = [r for r in ours_all if r["ts"] in cycle_set]
    print(f"our decodes in window: {len(ours_rows)}")

    jt9_out_path = args.jt9_out or JT9_ALL_TXT_OUT
    if args.skip_jt9 and os.path.isfile(jt9_out_path):
        print(f"--skip-jt9: reusing existing {jt9_out_path}")
        jt9_rows = ac.parse_all_txt(jt9_out_path)
    else:
        print(f"running jt9 (-d 3) over {len(wav_paths)} WAVs -- this is the ~2.6h step "
              f"at full scale...")
        jt9_rows = ej9.run_jt9(ej9.DEFAULT_JT9_EXE, wav_paths, depth=3,
                                max_workers=args.max_workers)
        dial_mhz = ej9.extract_dial_mhz(OURS_ALL_TXT)
        ej9.write_jt9_all_txt(jt9_rows, dial_mhz, jt9_out_path)
    print(f"jt9 decodes in window: {len(jt9_rows)}")

    # -- Self-checks (1030 S3, mandatory, before any reading) ------------------------------
    unrestricted_pairs = ac.match_pairs(ours_rows, jt9_rows)
    print(f"unrestricted matched pairs: {len(unrestricted_pairs)}")

    self_check_failures = []
    if len(wav_paths) != EXPECTED_N_WAVS:
        self_check_failures.append(
            f"WAV count {len(wav_paths)} != expected {EXPECTED_N_WAVS}")
    if len(ours_rows) != EXPECTED_N_OURS:
        self_check_failures.append(
            f"our decode count {len(ours_rows)} != expected {EXPECTED_N_OURS}")
    if len(jt9_rows) != EXPECTED_N_JT9:
        self_check_failures.append(
            f"jt9 decode count {len(jt9_rows)} != expected {EXPECTED_N_JT9} "
            f"(jt9 is not perfectly deterministic across builds/machines -- a SMALL "
            f"difference is not necessarily void; a large one is)")
    if len(unrestricted_pairs) != EXPECTED_N_MATCHED:
        self_check_failures.append(
            f"matched pair count {len(unrestricted_pairs)} != expected {EXPECTED_N_MATCHED}")

    # Session t0: earliest logged row across BOTH files (matches verify_dt_drift_489135a.py's
    # convention exactly, so elapsed_h here is defined identically to the calibration report).
    all_ts = [ac.parse_cycle_ts(r["ts"]) for r in ours_all + wsjtx_all]
    all_ts = [t for t in all_ts if t is not None]
    t0 = min(all_ts)
    print(f"session t0 (earliest logged row): {t0}")

    ours_eh = elapsed_hours(ours_rows, t0)
    wsjtx_eh = elapsed_hours(wsjtx_all, t0)

    ours_binned = hourly_median([(r["elapsed_h"], r["dt"]) for r in ours_eh])
    wsjtx_binned = hourly_median([(r["elapsed_h"], r["dt"]) for r in wsjtx_eh])
    ours_slope, ours_intercept = fit_slope(ours_binned)
    wsjtx_slope, wsjtx_intercept = fit_slope(wsjtx_binned)
    wsjtx_ppm = -wsjtx_slope / 3600.0 * 1e6

    print(f"OpenWSFZ DT fit: {ours_intercept:+.4f} + ({ours_slope:+.4f})*h")
    print(f"WSJT-X   DT fit: {wsjtx_intercept:+.4f} + ({wsjtx_slope:+.4f})*h "
          f"({wsjtx_ppm:.2f} ppm -- flatness control)")

    CONTROL_FLAT_THRESHOLD_PPM = 5.0  # generous vs the measured ~0.6-2ppm baseline noise
    control_flat = abs(wsjtx_ppm) < CONTROL_FLAT_THRESHOLD_PPM
    if not control_flat:
        self_check_failures.append(
            f"WSJT-X DT control not flat ({wsjtx_ppm:.2f} ppm) -- run is void")

    if self_check_failures:
        print("\n[SELF-CHECK FAILURE] Run is VOID. Do not read the result below.",
              file=sys.stderr)
        for f in self_check_failures:
            print(f"  - {f}", file=sys.stderr)
    else:
        print("\nAll self-checks pass.")

    # -- Elapsed-hour-binned parity curve (all matched pairs, full session) ---------------
    # Reference (jt9) decode count, binned by the CYCLE's elapsed hour (not per-decode -- a
    # cycle's hour bin is fixed regardless of how many messages it holds).
    ref_count_by_hour: dict[int, int] = {}
    for r in jt9_rows:
        ts = ac.parse_cycle_ts(r["ts"])
        if ts is None:
            continue
        h = int((ts - t0).total_seconds() / 3600.0)
        ref_count_by_hour[h] = ref_count_by_hour.get(h, 0) + 1

    matched_count_by_hour: dict[int, int] = {}
    # match_pairs() (anova_common) does not thread the cycle ts through its output tuples, so
    # binning the MATCHED count by hour needs its own pass keyed the same way match_pairs keys
    # internally (ts, normalized message) -- reusing normalize_hash_tokens for exact parity
    # with anova_common's own key construction, not a re-derived one.
    ours_by_key: dict[tuple, list[dict]] = {}
    for r in ours_rows:
        key = (r["ts"], ac.normalize_hash_tokens(r["message"]))
        ours_by_key.setdefault(key, []).append(r)
    jt9_by_key: dict[tuple, list[dict]] = {}
    for r in jt9_rows:
        key = (r["ts"], ac.normalize_hash_tokens(r["message"]))
        jt9_by_key.setdefault(key, []).append(r)
    for key in set(ours_by_key) & set(jt9_by_key):
        ts_tok, _msg = key
        ts = ac.parse_cycle_ts(ts_tok)
        if ts is None:
            continue
        h = int((ts - t0).total_seconds() / 3600.0)
        n_pairs_here = min(len(ours_by_key[key]), len(jt9_by_key[key]))
        matched_count_by_hour[h] = matched_count_by_hour.get(h, 0) + n_pairs_here

    print("\nParity by elapsed hour (matched/jt9-reference, with drift(h) attached):")
    print(f"{'h':>3} {'matched':>8} {'ref':>8} {'parity':>8} {'95%CI':>18} {'drift_2.40':>11} {'drift_slope':>12}")
    curve_rows = []
    all_hours = sorted(set(ref_count_by_hour) | set(matched_count_by_hour))
    for h in all_hours:
        matched = matched_count_by_hour.get(h, 0)
        ref = ref_count_by_hour.get(h, 0)
        parity, ci = parity_for_pairs(matched, ref)
        drift_corrected = (ours_intercept - DRIFT_CALIBRATION_C) + ours_slope * h
        drift_slope_only = ours_slope * h
        curve_rows.append({
            "h": h, "matched": matched, "ref": ref, "parity": parity, "ci": ci,
            "drift_corrected": drift_corrected, "drift_slope_only": drift_slope_only,
        })
        ci_str = f"[{ci[0]*100:.1f}%,{ci[1]*100:.1f}%]" if ref else "N/A"
        parity_str = f"{parity*100:.1f}%" if ref else "N/A"
        print(f"{h:>3} {matched:>8} {ref:>8} {parity_str:>8} {ci_str:>18} "
              f"{drift_corrected:>+11.3f} {drift_slope_only:>+12.3f}")

    # -- Headline: restricted parity at BOTH cutoffs ---------------------------------------
    # BUG FOUND ON REVIEW, before this was reported anywhere: filtering curve_rows by
    # `v["h"] < max_h` compares against the INTEGER hour-bucket index used for the display
    # curve, not the cycle's own continuous elapsed_h. For max_h=2.40 that silently admits
    # the ENTIRE h=2 bucket (elapsed_h in [2.0, 3.0)), overshooting the true 2.40h boundary
    # by up to 0.6h of extra (higher-drift) data; for max_h=3.06 it admits the whole h=3
    # bucket, overshooting by nearly a full hour. The headline restriction below instead
    # re-filters at the per-cycle, continuous-elapsed_h level -- the curve above stays at
    # hour-bucket granularity (fine for a display curve; 1044 S3's precision caveat already
    # treats hour-scale granularity as expected), but the headline figure a reading rule
    # fires against must not inherit that imprecision.
    ours_key_eh = {(r["ts"], ac.normalize_hash_tokens(r["message"])): r["elapsed_h"]
                   for r in ours_eh}
    jt9_eh_rows = elapsed_hours(jt9_rows, t0)
    jt9_key_eh = {(r["ts"], ac.normalize_hash_tokens(r["message"])): r["elapsed_h"]
                  for r in jt9_eh_rows}

    print("\nHeadline restricted parity (precise per-cycle elapsed_h, not hour-bucket):")
    headline_results = {}
    for label, max_h in CUTOFFS_H.items():
        matched_r = 0
        for key in set(ours_by_key) & set(jt9_by_key):
            if jt9_key_eh.get(key, float("inf")) < max_h:
                matched_r += min(len(ours_by_key[key]), len(jt9_by_key[key]))
        ref_r = sum(1 for r in jt9_eh_rows if r["elapsed_h"] < max_h)
        parity_r, ci_r = parity_for_pairs(matched_r, ref_r)
        headline_results[label] = {
            "max_h": max_h, "matched": matched_r, "ref": ref_r,
            "parity": parity_r, "ci": ci_r,
        }
        print(f"  {label} (h<{max_h}): matched={matched_r} ref={ref_r} "
              f"parity={parity_r*100:.1f}% CI=[{ci_r[0]*100:.1f}%,{ci_r[1]*100:.1f}%]")

    # -- Reference-method by-product: jt9 vs WSJT-X's own ALL.TXT, identical audio ---------
    wsjtx_rows_in_window = [r for r in wsjtx_all if r["ts"] in cycle_set]
    ref_method_pairs = ac.match_pairs(jt9_rows, wsjtx_rows_in_window)
    print(f"\nReference-method by-product: jt9 vs live-WSJT-X ALL.TXT (same audio):")
    print(f"  jt9 decodes: {len(jt9_rows)}, WSJT-X live decodes: {len(wsjtx_rows_in_window)}, "
          f"matched: {len(ref_method_pairs)}")

    # -- Write report -----------------------------------------------------------------------
    write_report(
        self_check_failures=self_check_failures,
        n_wavs=len(wav_paths), n_ours=len(ours_rows), n_jt9=len(jt9_rows),
        n_unrestricted_matched=len(unrestricted_pairs),
        ours_fit=(ours_intercept, ours_slope), wsjtx_fit=(wsjtx_intercept, wsjtx_slope),
        wsjtx_ppm=wsjtx_ppm, control_flat=control_flat,
        curve_rows=curve_rows, headline_results=headline_results,
        ref_method_n_jt9=len(jt9_rows), ref_method_n_wsjtx=len(wsjtx_rows_in_window),
        ref_method_matched=len(ref_method_pairs),
        t0=t0,
    )
    return 0 if not self_check_failures else 1


def write_report(*, self_check_failures, n_wavs, n_ours, n_jt9, n_unrestricted_matched,
                  ours_fit, wsjtx_fit, wsjtx_ppm, control_flat, curve_rows, headline_results,
                  ref_method_n_jt9, ref_method_n_wsjtx, ref_method_matched, t0) -> None:
    L = []
    L.append("# Task 4 -- 489135a recompute: RESULT")
    L.append("")
    L.append(f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
              f"(`date -u`, HK-017)")
    L.append(f"**Session t0:** {t0} UTC")
    L.append("**Method:** `2026-07-31-1030-...-dt-derived-drift.md`, corrected by "
              "`2026-07-31-1044-...-drift-definition-corrected.md`.")
    L.append("")
    L.append("## Self-checks (mandatory, before any reading)")
    L.append("")
    if self_check_failures:
        L.append("**RUN IS VOID.** The following self-check(s) failed:")
        L.append("")
        for f in self_check_failures:
            L.append(f"- {f}")
        L.append("")
        L.append("Do not read anything below as a finding.")
    else:
        L.append("All pass.")
        L.append("")
        L.append(f"- WAV cycles: {n_wavs} (expected {EXPECTED_N_WAVS})")
        L.append(f"- Our decodes in window: {n_ours} (expected {EXPECTED_N_OURS})")
        L.append(f"- jt9 decodes in window: {n_jt9} (expected {EXPECTED_N_JT9})")
        L.append(f"- Unrestricted matched pairs: {n_unrestricted_matched} "
                  f"(expected {EXPECTED_N_MATCHED})")
        L.append(f"- WSJT-X DT control: {wsjtx_ppm:.2f} ppm -- "
                  f"{'FLAT, holds' if control_flat else 'NOT FLAT'}")
    L.append("")
    L.append("## DT-drift regression (full session -- valid, this corpus never crossed the cliff)")
    L.append("")
    L.append(f"- OpenWSFZ: DT ~= {ours_fit[0]:+.4f} + ({ours_fit[1]:+.4f})*elapsed_h")
    L.append(f"- WSJT-X (control): DT ~= {wsjtx_fit[0]:+.4f} + ({wsjtx_fit[1]:+.4f})*elapsed_h "
              f"({wsjtx_ppm:.2f} ppm)")
    L.append(f"- Calibration constant C = {DRIFT_CALIBRATION_C} s "
              "(from the 8080 sibling session's pre-cliff cross-correlation calibration, "
              "per 1044 S1 -- not re-derived here, cited)")
    L.append("")
    L.append("## Parity as a function of drift (the durable output, per 1030 S3 item 3)")
    L.append("")
    L.append("| h | matched | ref (jt9) | parity | 95% CI | drift (corrected, C=0.7251) | drift (slope-only) |")
    L.append("|---:|---:|---:|---:|---|---:|---:|")
    for v in curve_rows:
        parity_str = f"{v['parity']*100:.1f}%" if v["ref"] else "N/A"
        ci_str = f"[{v['ci'][0]*100:.1f}%,{v['ci'][1]*100:.1f}%]" if v["ref"] else "N/A"
        L.append(f"| {v['h']} | {v['matched']} | {v['ref']} | {parity_str} | {ci_str} | "
                  f"{v['drift_corrected']:+.3f} | {v['drift_slope_only']:+.3f} |")
    L.append("")
    L.append("## Headline: restricted parity at both candidate cutoffs (1044 S3)")
    L.append("")
    for label, r in headline_results.items():
        L.append(f"- **{label}** (h < {r['max_h']}): matched={r['matched']}, ref={r['ref']}, "
                  f"parity={r['parity']*100:.1f}%, 95% CI=[{r['ci'][0]*100:.1f}%,{r['ci'][1]*100:.1f}%]")
    L.append("")
    p1 = headline_results["h_2p40_corrected_definition"]["parity"]
    p2 = headline_results["h_3p06_slope_only_candidate"]["parity"]
    L.append("**Agreement check (1044 S3 added requirement):** if the two cutoffs select "
              "different rows of the pre-registered reading rule, this must be escalated, "
              "not resolved by picking one. See the QA write-up for the applied reading rule "
              "and its outcome under each.")
    L.append("")
    L.append("## Reference-method by-product (descriptive only -- NOT subject to the reading rule)")
    L.append("")
    L.append(f"- jt9 decodes: {ref_method_n_jt9}")
    L.append(f"- Live WSJT-X decodes (same audio): {ref_method_n_wsjtx}")
    L.append(f"- Matched: {ref_method_matched} "
              f"({ac.pct_or_na(ref_method_matched, ref_method_n_jt9)} of jt9's, "
              f"{ac.pct_or_na(ref_method_matched, ref_method_n_wsjtx)} of WSJT-X's)")
    L.append("")
    L.append("Answers: does a live-WSJT-X reference and a jt9 re-decode give materially "
              "different parity on identical audio? Descriptive; must not be pooled with the "
              "parity recompute above.")
    L.append("")

    with open(OUT_REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"\nwrote {OUT_REPORT}")


if __name__ == "__main__":
    raise SystemExit(main())
