#!/usr/bin/env python3
"""`FP-PARITY` Amendment 3 (P3) -- pre-registered rows 0s, 0n, 0n-C, shipped as code (HK-021(r)).

Spec: qa/rr-study/2026-09-06-0951-architect-to-qa-spec-fp-parity-p3-normalisation-and-param-parity.md
-- "FP-PARITY Amendment 3" (a document distinct from AWGN-FP's own A3.1-A3.4; name the spec when
citing either). ROW 0o and ROW 0p are asserted in FpParityP3Tests.cs (C#, no native call needed for
either is false for 0p -- it scans WAVs -- but both run BEFORE any decode); this script covers the
three rows that are pure analysis over already-produced CSVs:

  - ROW 0s: recompute the un-normalised 20260050 baseline (4,000 slots / 435 events / 10.875%) as a
    CODE ASSERTION from the committed m1m4_s5_20260050_slots.csv -- not inherited from the
    Architect's reading of the ROW 0r report (spec section 4, ROW 0s).
  - ROW 0n: pair ROW 0s's baseline against FpParityP3Tests' fresh normalised decode
    (_out/p3_norm_slots.csv) slot-by-slot over all 4,000 slots. Exact McNemar (binomial) two-sided
    p-value and a 95% exact conditional CI on the signed rate difference Delta, split at
    +/-2.0 pp (derived from the in-chain comparator's own CP95, pre-registered in the spec, not
    from this data).
  - ROW 0n-C: the false-accept ceiling under the production input contract -- excess = signal_db -
    local_noise_db for every decode row in the normalised leg (every row is a false accept; S5 is
    noise-only), FIRES iff any exceeds T = C + 1.0 = 2.622 dB (C = +1.622 dB, offline, un-normalised,
    20260049).

Usage:
    python p3_parity.py
Writes qa/rr-study/fp-parity/p3_parity_results.txt alongside stdout output.
"""
from __future__ import annotations

import csv
import pathlib
import sys
from fractions import Fraction

from scipy.stats import binomtest

_HERE = pathlib.Path(__file__).parent.resolve()
_RESULTS_PATH = _HERE / "p3_parity_results.txt"

_BASELINE_SLOTS = _HERE / "results" / "m1m4_s5_20260050_slots.csv"
_NORM_SLOTS = _HERE / "_out" / "p3_norm_slots.csv"
_NORM_DECODES = _HERE / "_out" / "p3_norm_decodes.csv"

# ── Pre-registered constants (spec §1.2, §1.3, §4) ─────────────────────────────────────
_EXPECTED_SLOTS = 4000
_EXPECTED_EVENTS = 435
_EXPECTED_RATE_PCT = Fraction(10875, 1000)  # 10.875%, exact

_DELTA_BAND_PP = 2.0  # +/- 2.0 percentage points, derived from the in-chain comparator's CP95
_ROW_0N_C_C_DB = 1.622  # offline, un-normalised, 20260049 (FP-PARITY §1.3 / P2)
_ROW_0N_C_CEILING_DB = _ROW_0N_C_C_DB + 1.0  # T = C + 1.0 = 2.622 dB


def _log(lines: list, msg: str) -> None:
    print(msg)
    lines.append(msg)


def _load_slots(path: pathlib.Path) -> dict[tuple, int]:
    """slot key (scenario,part,trial,seed) -> n_decodes."""
    out: dict[tuple, int] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row["scenario"], int(row["part"]), int(row["trial"]), int(row["seed"]))
            out[key] = int(row["n_decodes"])
    return out


def row0s_baseline_assertion(lines: list) -> tuple[bool, dict[tuple, int]]:
    """ROW 0s -- recompute the 20260050 un-normalised baseline from the committed CSV alone.
    Returns (fires, baseline_slots_by_key). FIRES -> STOP, no downstream row may run."""
    _log(lines, "=== ROW 0s -- un-normalised 20260050 baseline, recomputed as an assertion ===")
    _log(lines, f"Source: {_BASELINE_SLOTS}")

    baseline = _load_slots(_BASELINE_SLOTS)
    slots = len(baseline)
    events = sum(1 for n in baseline.values() if n >= 1)
    rate = Fraction(events, slots) * 100 if slots else Fraction(0)

    _log(lines, f"slots = {slots}  (expected {_EXPECTED_SLOTS})")
    _log(lines, f"events (n_decodes>=1) = {events}  (expected {_EXPECTED_EVENTS})")
    _log(lines, f"event rate = {float(rate):.3f}%  (expected {float(_EXPECTED_RATE_PCT):.3f}%, exact fraction compare)")

    fires = (slots != _EXPECTED_SLOTS) or (events != _EXPECTED_EVENTS) or (rate != _EXPECTED_RATE_PCT)
    _log(lines, f"ROW 0s FIRES = {fires}")
    if fires:
        _log(lines, "STOP -- the paired design has no baseline; ROW 0n must be re-scoped to decode "
                     "both legs fresh (a different row, not this one).")
    else:
        _log(lines, "Does not fire -> this file is P3's un-normalised leg and 10.875% is a 20260050 "
                     "figure, not merely a carried-over one.")
        _log(lines, "What this row cannot detect (HK-022): whether ROW 0r's own decode was correctly "
                     "configured -- that is ROW 0p/0o's job, both already run and both non-firing, "
                     "before this row, in FpParityP3Tests.cs. It also cannot detect a per-slot numeric "
                     "(freq_hz/dt_s/reported_snr_db) change against 20260049 -- that is ROW 0r's own "
                     "claim (0/435 differ), already run and landed; this row never opens decodes.csv "
                     "and does not re-verify it (Architect-ratified defect #4, spec section 0.1).")
    return fires, baseline


def row0n_paired_mcnemar(lines: list, baseline: dict[tuple, int]) -> None:
    """ROW 0n -- exactly paired McNemar over all 4,000 slots. Three mutually exclusive,
    exhaustive verdicts fixed in the spec before this data existed."""
    _log(lines, "\n=== ROW 0n -- normalisation parity, exactly paired, N=4,000 ===")
    _log(lines, f"Source (normalised leg): {_NORM_SLOTS}")

    normalised = _load_slots(_NORM_SLOTS)

    base_keys = set(baseline.keys())
    norm_keys = set(normalised.keys())
    _log(lines, f"baseline slots = {len(base_keys)}  normalised slots = {len(norm_keys)}")
    if base_keys != norm_keys:
        missing_norm = base_keys - norm_keys
        missing_base = norm_keys - base_keys
        _log(lines, f"STOP -- population mismatch: {len(missing_norm)} in baseline-not-normalised, "
                     f"{len(missing_base)} in normalised-not-baseline. Cannot pair; do not proceed.")
        return

    n = len(base_keys)
    b = 0  # event un-normalised only (lost under normalisation)
    c = 0  # event normalised only (gained under normalisation)
    both = 0
    neither = 0
    for key in base_keys:
        event_un = baseline[key] >= 1
        event_norm = normalised[key] >= 1
        if event_un and not event_norm:
            b += 1
        elif event_norm and not event_un:
            c += 1
        elif event_un and event_norm:
            both += 1
        else:
            neither += 1

    n_disc = b + c
    rate_un = 100.0 * (b + both) / n
    rate_norm = 100.0 * (c + both) / n
    delta_pp = (c - b) / n * 100.0  # Delta = normalised rate - un-normalised rate, signed, never |Delta| (HK-021(l))

    _log(lines, f"n (paired slots) = {n}  readout quantum = {100.0 / n:.3f}%")
    _log(lines, f"both-event = {both}  neither = {neither}  b (un-only, lost) = {b}  c (norm-only, gained) = {c}  "
                 f"n_discordant = {n_disc}")
    _log(lines, f"un-normalised rate = {rate_un:.3f}%   normalised rate = {rate_norm:.3f}%")
    _log(lines, f"Delta (signed, normalised - un-normalised) = {delta_pp:+.3f} pp")

    if n_disc == 0:
        p_value = 1.0
        ci_lo_pp = ci_hi_pp = 0.0
    else:
        # Exact McNemar two-sided p-value: b ~ Binomial(n_disc, 0.5) under H0.
        p_value = binomtest(min(b, c), n_disc, p=0.5, alternative="two-sided").pvalue
        # Exact conditional 95% CI on Delta: Clopper-Pearson CI on p = c / n_disc, transformed.
        ci = binomtest(c, n_disc).proportion_ci(confidence_level=0.95, method="exact")
        ci_lo_pp = (2 * ci.low - 1) * n_disc / n * 100.0
        ci_hi_pp = (2 * ci.high - 1) * n_disc / n * 100.0

    _log(lines, f"Exact McNemar two-sided p-value = {p_value:.4g}")
    _log(lines, f"95% exact conditional CI on Delta = [{ci_lo_pp:+.3f}, {ci_hi_pp:+.3f}] pp")

    ci_excludes_zero = ci_lo_pp > 0.0 or ci_hi_pp < 0.0
    abs_delta = abs(delta_pp)

    if ci_excludes_zero and abs_delta >= _DELTA_BAND_PP:
        verdict = "0n-i"
        consequence = ("The offline seam has been measuring a materially different instrument. "
                        "10.875% is RETIRED OUTRIGHT; the offline-vs-in-chain gap must be "
                        "recomputed and re-reported before any P4b work.")
    elif ci_excludes_zero and abs_delta < _DELTA_BAND_PP:
        verdict = "0n-ii"
        consequence = ("Real but immaterial. The normalised figure becomes the citable offline "
                        "rate; the gap conclusion stands, with Delta and its sign disclosed in "
                        "every future citation.")
    else:
        verdict = "0n-iii"
        consequence = ("The two agree. The normalised figure still becomes the citable offline "
                        "rate (it is the only one under the production contract), and the "
                        "~6.9 dB offline/production level difference is excluded as an "
                        "explanation of the gap.")

    _log(lines, f"CI excludes zero = {ci_excludes_zero}  |Delta| >= {_DELTA_BAND_PP}pp = {abs_delta >= _DELTA_BAND_PP}")
    _log(lines, f"ROW 0n VERDICT = {verdict}")
    _log(lines, f"Consequence: {consequence}")
    _log(lines, "Binding in all three branches: the normalised figure is the only citable offline "
                 "absolute rate from this day forward -- a non-fire does not restore 10.875%, it "
                 "means the two agree.")


def row0n_c_false_accept_ceiling(lines: list) -> None:
    """ROW 0n-C -- the false-accept ceiling under the production contract, over decode ROWS."""
    _log(lines, "\n=== ROW 0n-C -- false-accept ceiling under the production contract ===")
    _log(lines, f"Source: {_NORM_DECODES}")
    _log(lines, f"Standing ceiling T = C + 1.0 = {_ROW_0N_C_CEILING_DB} dB (C = {_ROW_0N_C_C_DB} dB, "
                 "offline, un-normalised, 20260049)")

    excess_values: list[float] = []
    with open(_NORM_DECODES, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            signal_db = float(row["signal_db"])
            local_noise_db = float(row["local_noise_db"])
            excess_values.append(signal_db - local_noise_db)

    n = len(excess_values)
    if n == 0:
        _log(lines, "n = 0 -- no decode rows in the normalised leg; nothing to report.")
        return

    excess_sorted = sorted(excess_values)
    min_excess = excess_sorted[0]
    max_excess = excess_sorted[-1]
    mid = n // 2
    median_excess = excess_sorted[mid] if n % 2 == 1 else (excess_sorted[mid - 1] + excess_sorted[mid]) / 2.0
    diff_from_c = max_excess - _ROW_0N_C_C_DB

    _log(lines, f"n (decode rows, all treated as false accepts -- S5 is noise-only) = {n}")
    _log(lines, f"excess (signal_db - local_noise_db): min = {min_excess:.3f} dB, "
                 f"median = {median_excess:.3f} dB, max C' = {max_excess:.3f} dB")
    _log(lines, f"Signed C' - 1.622 dB = {diff_from_c:+.3f} dB")

    fires = any(e > _ROW_0N_C_CEILING_DB for e in excess_values)
    n_over = sum(1 for e in excess_values if e > _ROW_0N_C_CEILING_DB)
    _log(lines, f"ROW 0n-C FIRES (any normalised-leg false accept has excess > {_ROW_0N_C_CEILING_DB} dB) = {fires}"
                 f"  ({n_over} of {n} rows exceed T)")

    if fires:
        _log(lines, "STOP -- T is not conservative and must be re-derived before P4b runs at all. "
                     "ROW 2/ROW 3 may not be evaluated against a ceiling the production contract "
                     "has moved past.")
    else:
        _log(lines, f"Does not fire -> T = {_ROW_0N_C_CEILING_DB} dB carries forward to 20260050, "
                     "normalised, and P4b may proceed on this ground.")
        _log(lines, "Honest limit of the non-fire branch (HK-021(t)): shows no false accept on this "
                     "4,000-slot noise-only population exceeded T. Does NOT show C is stable -- a "
                     f"sample maximum over n={n} is not a stable statistic.")


def main() -> int:
    lines: list = []
    _log(lines, "FP-PARITY Amendment 3 (P3) -- ROW 0s, ROW 0n, ROW 0n-C")
    _log(lines, "Spec: qa/rr-study/2026-09-06-0951-architect-to-qa-spec-fp-parity-p3-normalisation-and-param-parity.md")
    _log(lines, "Every P3 figure below: offline, 20260050 (A3.2). Pooling with any <=20260049 "
                 "offline figure is a NEW pre-registration, not an extension.\n")

    fires_0s, baseline = row0s_baseline_assertion(lines)
    if fires_0s:
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nWrote {_RESULTS_PATH}")
        return 1

    row0n_paired_mcnemar(lines, baseline)
    row0n_c_false_accept_ceiling(lines)

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
