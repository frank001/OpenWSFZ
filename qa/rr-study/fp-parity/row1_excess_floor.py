#!/usr/bin/env python3
"""`FP-PARITY` ROW 1 -- the in-chain genuine excess floor `F`, shipped as code (HK-021(r)).

Spec: qa/rr-study/2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md sec.4 ROW 1,
corrected by Amendment 1 (2026-09-04) A1.1 (frozen S1b population) and A1.2 (the truncation is
known in advance). Execution order/scope: the P4a block of
qa/rr-study/2026-09-04-1322-architect-to-qa-execution-pack-post-shim-bump.md -- "no binary, no
dependency, can start immediately, in parallel with P1."

THIS SCRIPT COMPUTES ROW 1 ONLY. ROW 2/ROW 3 (P4b) are explicitly held per the execution pack
until ROW 0n/0o close (P3) -- `T = C + 1.0 dB` is an OFFLINE quantity and sec.3's two repairs are
what make it production-valid. This script prints the ROW 2/3 knife-edge table for context (it is
already published in Amendment 1 A1.3) but does not render a ROW 2/3 verdict.

Not a fire/no-fire row (sec.4): a measurement, reported with its own uncertainty.

Usage:
    python row1_excess_floor.py
Writes qa/rr-study/fp-parity/row1_excess_floor_results.txt alongside stdout output.
"""
from __future__ import annotations

import csv
import pathlib
import sys
from datetime import timezone

_HERE = pathlib.Path(__file__).parent.resolve()
_QA_ROOT = _HERE.parent
_RESULTS_DIR = _QA_ROOT / "results"
_RESULTS_PATH = _HERE / "row1_excess_floor_results.txt"

# ── The frozen population (Amendment 1 A1.1) -- 5 sweeps x 12 S1b slots = 60. ────────────────
# 🛑 No sweep may be added to or removed from this list after ROW 1 is read (A1.1). A sixth sweep
# run later is a NEW pre-registration, not an extension of this one.
_FROZEN_SWEEPS: list[str] = [
    "2026-08-27-22b749c",
    "2026-08-29-872ba65",
    "2026-08-30-2e60949",  # NOT 2026-08-31-2e60949 (S7-only rerun, no S1b data -- A1.1 warning)
    "2026-09-02-3b52608",
    "2026-09-03-35378b9",
]

# ROW 0q's settled rule (this session, prior run): round-half-away-from-zero, matching
# ft8_shim.c:1732's `r->snr = (int)roundf(snr)`. Not truncation -> the mechanical error is
# symmetric +-0.5 dB, not one-sided. The CONSERVATIVE correction for a floor (whichever makes F
# smaller) is to subtract 0.5 dB from every reconstructed excess (round-half-away-from-zero can
# report an excess up to 0.5 dB HIGHER than the true float excess for a negative SNR).
_ROW0Q_CONSERVATIVE_CORRECTION_DB = -0.5

_READOUT_QUANTUM_DB = 1.0  # Ft8NativeResult.Snr is int (sec.1 table, last row).

# T is unmoved by the 2026-09-03 sweep (A1.3): C = +1.622 dB offline (n=454, AWGN-FP M1-M4 sec.4),
# and this sweep's two in-chain false accepts (-26 dB @341Hz -> excess +0.5; -27 dB @2878Hz ->
# excess -0.5) are both far below C, so they add n to the false-accept population without moving
# the ceiling. Printed for context only -- ROW 2/3 verdict itself is P4b, held for P3 (0n/0o).
_C_DB = 1.622
_T_DB = _C_DB + 1.0
_ROW2_FIRE_THRESHOLD_DB = _T_DB + 6.0  # F >= this -> ROW 2; F < this -> ROW 3


def _log(lines: list, msg: str) -> None:
    print(msg)
    lines.append(msg)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interpolation percentile (numpy 'linear' default), 0 <= pct <= 100."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def main() -> int:
    lines: list = []
    _log(lines, "FP-PARITY ROW 1 -- in-chain genuine excess floor F (P4a, no binary, no dependency)")
    _log(lines, "Spec: qa/rr-study/2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md sec.4 ROW 1 + Amendment 1")
    _log(lines, "Method: harness.common.parse_all_txt against raw owsfz-all.txt + truth.csv. "
                 "NEVER matcher.py (HK-026 -- its FP column is still unscoped).")

    sys.path.insert(0, str(_QA_ROOT / "harness"))
    import common as harness_common  # noqa: E402

    # (corrected_excess, reported_snr, injected_rung, sweep_id, cycle_utc)
    matched: list[tuple[float, int, float, str, str]] = []
    # rung -> [matched_count, total_trials], pooled across all 5 sweeps
    per_rung: dict[float, list[int]] = {}

    for sweep_dir_name in _FROZEN_SWEEPS:
        run_dir = _RESULTS_DIR / sweep_dir_name
        truth_path = run_dir / "truth.csv"
        alltxt_path = run_dir / "owsfz-all.txt"
        if not truth_path.is_file() or not alltxt_path.is_file():
            _log(lines, f"ROW 1: FAILED -- missing data for {sweep_dir_name} "
                         f"(truth.csv={truth_path.is_file()} owsfz-all.txt={alltxt_path.is_file()})")
            return 1

        # S1b truth rows for this sweep: cycle_utc -> (true_snr_db, message_text)
        s1b_slots: dict = {}
        with open(truth_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("scenario_id") == "S1b":
                    dt = harness_common.datetime.strptime(
                        row["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    s1b_slots[dt] = (float(row["true_snr_db"]), row["message_text"].strip())

        if len(s1b_slots) != 12:
            _log(lines, f"  {sweep_dir_name}: WARNING -- expected 12 S1b slots, found {len(s1b_slots)}")

        records, skipped = harness_common.parse_all_txt(alltxt_path)
        # Index decode records by slot utc (a slot can carry >1 decode record).
        by_utc: dict = {}
        for rec in records:
            by_utc.setdefault(rec.utc, []).append(rec)

        sweep_matched = 0
        for dt, (rung, truth_msg) in s1b_slots.items():
            per_rung.setdefault(rung, [0, 0])
            per_rung[rung][1] += 1  # total trials at this rung
            decodes_here = by_utc.get(dt, [])
            truth_matching = [r for r in decodes_here if r.message == truth_msg]
            if not truth_matching:
                continue
            per_rung[rung][0] += 1
            sweep_matched += 1
            for rec in truth_matching:
                reported_snr = int(rec.snr_db)  # already integer-valued from ALL.TXT (Ft8NativeResult.Snr is int)
                excess = reported_snr + 26.5
                corrected = excess + _ROW0Q_CONSERVATIVE_CORRECTION_DB
                matched.append((corrected, reported_snr, rung, sweep_dir_name, dt.strftime("%Y-%m-%dT%H:%M:%SZ")))

        _log(lines, f"  {sweep_dir_name}: 12 S1b slots, {sweep_matched} truth-matching decodes, "
                     f"ALLTXT_lines_parsed={len(records)} skipped={skipped}")

    n_slots = sum(v[1] for v in per_rung.values())
    n_matched = len(matched)
    _log(lines, f"\nPooled population: {n_slots} S1b slots across {len(_FROZEN_SWEEPS)} sweeps "
                 f"(pre-registered, frozen, Amendment 1 A1.1)")
    _log(lines, f"Truth-matching decodes: n={n_matched}")

    _log(lines, "\nPer-rung decode rate (pooled across all 5 sweeps):")
    for rung in sorted(per_rung, reverse=True):
        k, tot = per_rung[rung]
        pct = 100.0 * k / tot if tot else float("nan")
        _log(lines, f"  {rung:+.0f} dB injected: {k}/{tot} ({pct:.1f}%)")

    if n_matched == 0:
        _log(lines, "\nROW 1: NO truth-matching decodes at all in the frozen S1b population -- "
                     "F is undefined. This would itself be a major finding; STOP and report to the "
                     "Architect rather than proceeding.")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    excesses = sorted(m[0] for m in matched)
    F = excesses[0]
    p01 = _percentile(excesses, 1)
    p05 = _percentile(excesses, 5)

    # "Weakest" = the lowest-SNR (most negative) rung that still produced >=1 truth-matching decode.
    weakest_rung = min(rung for rung in per_rung if per_rung[rung][0] > 0)
    rate_at_weakest = 100.0 * per_rung[weakest_rung][0] / per_rung[weakest_rung][1]

    _log(lines, f"\n=== ROW 1 RESULT ===")
    _log(lines, f"F (min corrected excess) = {F:+.2f} dB")
    _log(lines, f"p01 = {p01:+.2f} dB   p05 = {p05:+.2f} dB")
    _log(lines, f"n = {n_matched} truth-matching decodes over {n_slots} slots")
    _log(lines, f"Readout quantum: {_READOUT_QUANTUM_DB:.1f} dB (Ft8NativeResult.Snr is int)")
    _log(lines, f"Weakest injected rung producing any truth-matching decode: {weakest_rung:+.0f} dB, "
                 f"decode rate at that rung = {per_rung[weakest_rung][0]}/{per_rung[weakest_rung][1]} "
                 f"({rate_at_weakest:.1f}%)")

    truncation_upper_bound = rate_at_weakest > 50.0
    _log(lines, f"\nTruncation statement (sec.2.3, mandatory alongside any F): bottom-rung decode "
                 f"rate is {rate_at_weakest:.1f}% ({'> 50%' if truncation_upper_bound else '<= 50%'}) "
                 f"=> F {'MUST be reported as an UPPER BOUND on the true floor, never as the floor' if truncation_upper_bound else 'may be reported as the floor'}.")
    if truncation_upper_bound:
        _log(lines, "🛑 F is an UPPER BOUND, not the floor. Matches A1.2's advance disclosure: "
                     "OpenWSFZ's S1b ladder produces 0/15 pooled at -24 dB and -21 dB (see per-rung "
                     "table above); the true floor is demonstrably lower (WSJT-X took 2/3 at -21 dB "
                     "on the 2026-09-03 sweep alone) -- the instrument's response is flat where the "
                     "boundary sits (HK-026).")

    _log(lines, "\n=== A1.3 disclosure block -- required whenever this table lands near the fire line ===")
    _log(lines, f"Lowest 5 reconstructed (corrected) excess values:")
    for corrected, reported_snr, rung, sweep_id, cycle_utc in sorted(matched, key=lambda m: m[0])[:5]:
        _log(lines, f"  excess={corrected:+.2f} dB  reported_snr={reported_snr:+d} dB  "
                     f"injected_rung={rung:+.0f} dB  sweep={sweep_id}  cycle_utc={cycle_utc}")

    near_line = [m for m in matched if abs(m[0] - _ROW2_FIRE_THRESHOLD_DB) <= 1.0]
    _log(lines, f"\nDistinct decodes within +-1 dB of the ROW2/3 fire line "
                 f"({_ROW2_FIRE_THRESHOLD_DB:.2f} dB, using T={_T_DB:.3f} dB which is NOT yet "
                 f"confirmed production-valid -- printed for context only, see note below): "
                 f"{len(near_line)}")
    for corrected, reported_snr, rung, sweep_id, cycle_utc in sorted(near_line, key=lambda m: m[0]):
        _log(lines, f"  excess={corrected:+.2f} dB  reported_snr={reported_snr:+d} dB  "
                     f"injected_rung={rung:+.0f} dB  sweep={sweep_id}  cycle_utc={cycle_utc}")

    _log(lines, "\n=== ROW 2 / ROW 3 -- NOT DECIDED HERE (P4b holds for P3 / ROW 0n, 0o) ===")
    _log(lines, f"T = C + 1.0 = {_C_DB:.3f} + 1.0 = {_T_DB:.3f} dB is an OFFLINE-anchored quantity; "
                 "sec.3's two repairs (NormalisePcm parity ROW 0n, decode-param parity ROW 0o) are "
                 "what make it production-valid, per the execution pack's explicit P4a/P4b split. "
                 f"F = {F:+.2f} dB is reported now because it needs no binary at all.")
    _log(lines, f"For context only (already published in Amendment 1 A1.3, NOT re-derived, NOT a "
                 f"verdict): ROW 2 fires iff F >= {_ROW2_FIRE_THRESHOLD_DB:.3f} dB. This run's F = "
                 f"{F:+.2f} dB {'>=' if F >= _ROW2_FIRE_THRESHOLD_DB else '<'} {_ROW2_FIRE_THRESHOLD_DB:.3f} dB "
                 f"=> would currently land on {'ROW 2' if F >= _ROW2_FIRE_THRESHOLD_DB else 'ROW 3'} "
                 f"IF T were already confirmed production-valid, which it is not yet (P3 not run).")

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
