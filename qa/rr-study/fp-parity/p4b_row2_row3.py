#!/usr/bin/env python3
"""`FP-PARITY` P4b -- the ROW 2 / ROW 3 verdict, shipped as code (HK-021(r), A1.3, Amendment 4).

Spec: qa/rr-study/2026-09-06-1436-architect-to-qa-spec-fp-parity-p4b-row2-row3-verdict.md
Executes the ROW 2/ROW 3 predicate from the base spec
(2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md sec.4), whose knife-edge shape
and reporting obligation (lowest-5 with per-decode binary, four-sweep leave-one-out F) were
disclosed in advance by Amendment 1 A1.3 (2026-09-04). Held for P3 twice in writing; P3 closed
without firing on any row (e813801, 2026-09-06 10:25Z) -- both of P4b's frozen inputs are now
confirmed:
  F = +8.00 dB  (ROW 1, Amendment 1 A1.1's frozen 5-sweep/60-slot population)
  T = 2.622 dB  (base spec sec.2/4, C=1.622 dB, confirmed production-valid by P3 ROW 0n-C)

THIS SCRIPT DOES NOT RE-MEASURE F OR T (spec sec.0.1). It re-derives F mechanically from the same
raw truth.csv/owsfz-all.txt files row1_excess_floor.py already reads (HK-026: never matcher.py),
cross-checks the result against the already-committed row1_excess_floor_results.txt (mismatch is a
STOP, not a ROW -- ROW 1's frozen result would have moved since it was landed), computes the
four-sweep leave-one-out F mandated by A1.3, and renders the ROW 2/ROW 3 verdict -- UNLESS the
leave-one-out F disagrees with the five-sweep F about which side of the 6.0 dB bar the margin falls
on, in which case this script renders NO verdict and STOPs for Architect/PO adjudication
(HK-021(k)/HK-025 -- not a script's tie-break to make).

No new decode, no new sweep, no src/ or native/ change. A ROW 2 fire authorises QA to *author* an
emission-side filter dev-task in a separate artefact (HK-011: author, then stop) -- it does not
license writing filter code in this script or this session.

Usage:
    python p4b_row2_row3.py
Writes qa/rr-study/fp-parity/p4b_row2_row3_results.txt alongside stdout output.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys
from datetime import timezone

_HERE = pathlib.Path(__file__).parent.resolve()
_QA_ROOT = _HERE.parent
_RESULTS_DIR = _QA_ROOT / "results"
_RESULTS_PATH = _HERE / "p4b_row2_row3_results.txt"
_ROW1_COMMITTED_PATH = _HERE / "row1_excess_floor_results.txt"

# ── The frozen population (Amendment 1 A1.1) -- 5 sweeps x 12 S1b slots = 60. ────────────────
# 🛑 Identical list to row1_excess_floor.py -- this script re-derives ROW 1's F as a cross-check,
# it does not define a new population. No sweep may be added or removed after ROW 1 is read (A1.1).
_FROZEN_SWEEPS: list[str] = [
    "2026-08-27-22b749c",
    "2026-08-29-872ba65",
    "2026-08-30-2e60949",  # NOT 2026-08-31-2e60949 (S7-only rerun, no S1b data -- A1.1 warning)
    "2026-09-02-3b52608",
    "2026-09-03-35378b9",
]

# Binary era per sweep, per AWGN-FP ROW 0r (2026-09-04) + FP-PARITY Amendment 2 Ruling 2
# (2026-09-04 14:11Z): 2026-09-03-35378b9 is the first sweep ever run on 20260050;
# the other four sweeps in the Amendment 1 A1.1 frozen population are all <=20260049.
_SWEEP_BINARY_ERA: dict[str, str] = {
    "2026-08-27-22b749c": "<=20260049",
    "2026-08-29-872ba65": "<=20260049",
    "2026-08-30-2e60949": "<=20260049",
    "2026-09-02-3b52608": "<=20260049",
    "2026-09-03-35378b9": "20260050",
}

# ROW 0q's settled rule (round-half-away-from-zero, ft8_shim.c:1732), identical to row1's.
_ROW0Q_CONSERVATIVE_CORRECTION_DB = -0.5
_READOUT_QUANTUM_DB = 1.0  # Ft8NativeResult.Snr is int (sec.1 table, last row).

# T, cited not recomputed (spec sec.2): C = +1.622 dB (base FP-PARITY spec sec.2, citing
# M1-M4-report.md sec.4), confirmed production-valid by FP-PARITY P3 ROW 0n-C (e813801 sec.2.4,
# C'=+1.652 dB, C'-C=+0.030 dB, 0 of 432 rows exceed T -- non-fire).
_C_DB = 1.622
_T_DB = _C_DB + 1.0  # 2.622
_ROW2_FIRE_MARGIN_DB = 6.0
_ROW2_FIRE_THRESHOLD_DB = _T_DB + _ROW2_FIRE_MARGIN_DB  # 8.622, context only (near-line window)


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


def _load_sweep(harness_common, sweep_dir_name: str, lines: list):
    """Identical method to row1_excess_floor.py's per-sweep block. Returns
    (matched_records, per_rung_delta, n_records_parsed, n_skipped) or None on missing data."""
    run_dir = _RESULTS_DIR / sweep_dir_name
    truth_path = run_dir / "truth.csv"
    alltxt_path = run_dir / "owsfz-all.txt"
    if not truth_path.is_file() or not alltxt_path.is_file():
        _log(lines, f"P4b: FAILED -- missing data for {sweep_dir_name} "
                     f"(truth.csv={truth_path.is_file()} owsfz-all.txt={alltxt_path.is_file()})")
        return None

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
    by_utc: dict = {}
    for rec in records:
        by_utc.setdefault(rec.utc, []).append(rec)

    matched: list[tuple[float, int, float, str, str]] = []
    per_rung: dict[float, list[int]] = {}
    for dt, (rung, truth_msg) in s1b_slots.items():
        per_rung.setdefault(rung, [0, 0])
        per_rung[rung][1] += 1
        decodes_here = by_utc.get(dt, [])
        truth_matching = [r for r in decodes_here if r.message == truth_msg]
        if not truth_matching:
            continue
        per_rung[rung][0] += 1
        for rec in truth_matching:
            reported_snr = int(rec.snr_db)
            excess = reported_snr + 26.5
            corrected = excess + _ROW0Q_CONSERVATIVE_CORRECTION_DB
            matched.append((corrected, reported_snr, rung, sweep_dir_name, dt.strftime("%Y-%m-%dT%H:%M:%SZ")))

    _log(lines, f"  {sweep_dir_name} [{_SWEEP_BINARY_ERA[sweep_dir_name]}]: 12 S1b slots, "
                 f"{len(matched)} truth-matching decodes, ALLTXT_lines_parsed={len(records)} "
                 f"skipped={skipped}")
    return matched, per_rung, len(records), skipped


def _compute_population(harness_common, sweep_names: list[str], lines: list, label: str):
    """Same method as row1_excess_floor.py's main(), parameterised over which sweeps are pooled."""
    all_matched: list[tuple[float, int, float, str, str]] = []
    per_rung: dict[float, list[int]] = {}
    for sweep_dir_name in sweep_names:
        result = _load_sweep(harness_common, sweep_dir_name, lines)
        if result is None:
            return None
        matched, sweep_per_rung, _n, _skip = result
        all_matched.extend(matched)
        for rung, (k, tot) in sweep_per_rung.items():
            per_rung.setdefault(rung, [0, 0])
            per_rung[rung][0] += k
            per_rung[rung][1] += tot

    n_slots = sum(v[1] for v in per_rung.values())
    n_matched = len(all_matched)
    _log(lines, f"{label}: pooled population {n_slots} S1b slots across {len(sweep_names)} sweep(s), "
                 f"n={n_matched} truth-matching decodes")
    if n_matched == 0:
        _log(lines, f"{label}: NO truth-matching decodes -- F undefined for this population.")
        return None

    excesses = sorted(m[0] for m in all_matched)
    F = excesses[0]
    p01 = _percentile(excesses, 1)
    p05 = _percentile(excesses, 5)
    return {
        "matched": all_matched,
        "per_rung": per_rung,
        "n_slots": n_slots,
        "n_matched": n_matched,
        "F": F,
        "p01": p01,
        "p05": p05,
    }


def _fmt_decode(m: tuple, with_era: bool = True) -> str:
    corrected, reported_snr, rung, sweep_id, cycle_utc = m
    era = f"  binary={_SWEEP_BINARY_ERA[sweep_id]}" if with_era else ""
    return (f"  excess={corrected:+.2f} dB  reported_snr={reported_snr:+d} dB  "
            f"injected_rung={rung:+.0f} dB  sweep={sweep_id}{era}  cycle_utc={cycle_utc}")


# ── Cross-check parsing of the already-committed row1_excess_floor_results.txt ──────────────────
_RE_F = re.compile(r"F \(min corrected excess\) = ([+-]?\d+\.\d+) dB")
_RE_P = re.compile(r"p01 = ([+-]?\d+\.\d+) dB\s+p05 = ([+-]?\d+\.\d+) dB")
_RE_DECODE = re.compile(
    r"excess=([+-]?\d+\.\d+) dB\s+reported_snr=([+-]?\d+) dB\s+injected_rung=([+-]?\d+) dB\s+"
    r"sweep=(\S+)\s+cycle_utc=(\S+)"
)


def _parse_committed_row1(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    f_match = _RE_F.search(text)
    p_match = _RE_P.search(text)
    if not f_match or not p_match:
        raise ValueError(f"Could not locate F/p01/p05 lines in {path} -- committed format changed?")
    committed_F = float(f_match.group(1))
    committed_p01 = float(p_match.group(1))
    committed_p05 = float(p_match.group(2))

    def _extract_block(header: str) -> list[tuple]:
        idx = text.index(header)
        block = text[idx:]
        end = block.find("\n\n", len(header))
        if end == -1:
            end = block.find("\n===", len(header))
        block = block[:end] if end != -1 else block
        out = []
        for dm in _RE_DECODE.finditer(block):
            corrected, reported_snr, rung, sweep_id, cycle_utc = dm.groups()
            out.append((float(corrected), int(reported_snr), float(rung), sweep_id, cycle_utc))
        return out

    committed_lowest5 = _extract_block("Lowest 5 reconstructed (corrected) excess values:")
    committed_near_line = _extract_block("Distinct decodes within")
    return {
        "F": committed_F,
        "p01": committed_p01,
        "p05": committed_p05,
        "lowest5": committed_lowest5,
        "near_line": committed_near_line,
    }


def main() -> int:
    lines: list = []
    _log(lines, "FP-PARITY P4b -- ROW 2 / ROW 3 verdict (Amendment 4)")
    _log(lines, "Spec: qa/rr-study/2026-09-06-1436-architect-to-qa-spec-fp-parity-p4b-row2-row3-verdict.md")
    _log(lines, "Method: identical to row1_excess_floor.py (harness.common.parse_all_txt against raw "
                 "owsfz-all.txt + truth.csv, NEVER matcher.py -- HK-026), parameterised over which "
                 "sweeps are pooled.")

    # §1 mandatory guard: the era table must exactly match the frozen population before anything else.
    if set(_SWEEP_BINARY_ERA) != set(_FROZEN_SWEEPS):
        _log(lines, "\n🛑 STOP: set(_SWEEP_BINARY_ERA) != set(_FROZEN_SWEEPS) -- the frozen population "
                     "and the binary-era table have drifted apart. This is a bigger finding than P4b. "
                     f"era keys={sorted(_SWEEP_BINARY_ERA)} frozen={sorted(_FROZEN_SWEEPS)}")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    sys.path.insert(0, str(_QA_ROOT / "harness"))
    import common as harness_common  # noqa: E402

    # ── Five-sweep F (cross-check against ROW 1's committed, frozen result) ─────────────────────
    _log(lines, "\n=== Five-sweep F (Amendment 1 A1.1 frozen population, cross-check) ===")
    five = _compute_population(harness_common, _FROZEN_SWEEPS, lines, "Five-sweep")
    if five is None:
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    if not _ROW1_COMMITTED_PATH.is_file():
        _log(lines, f"\n🛑 STOP: committed reference {_ROW1_COMMITTED_PATH} not found -- cannot "
                     "cross-check, refusing to proceed without it (spec sec.1's mandatory guard).")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    committed = _parse_committed_row1(_ROW1_COMMITTED_PATH)
    fresh_lowest5 = sorted(five["matched"], key=lambda m: m[0])[:5]
    fresh_near_line = [m for m in five["matched"] if abs(m[0] - _ROW2_FIRE_THRESHOLD_DB) <= 1.0]
    fresh_near_line_sorted = sorted(fresh_near_line, key=lambda m: m[0])

    mismatches = []
    if abs(five["F"] - committed["F"]) > 1e-9:
        mismatches.append(f"F: fresh={five['F']:+.2f} vs committed={committed['F']:+.2f}")
    if abs(five["p01"] - committed["p01"]) > 1e-9:
        mismatches.append(f"p01: fresh={five['p01']:+.2f} vs committed={committed['p01']:+.2f}")
    if abs(five["p05"] - committed["p05"]) > 1e-9:
        mismatches.append(f"p05: fresh={five['p05']:+.2f} vs committed={committed['p05']:+.2f}")
    committed_lowest5_vals = [(round(c[0], 2), c[1], c[2], c[3], c[4]) for c in committed["lowest5"]]
    fresh_lowest5_vals = [(round(c[0], 2), c[1], c[2], c[3], c[4]) for c in fresh_lowest5]
    if committed_lowest5_vals != fresh_lowest5_vals:
        mismatches.append(f"lowest5: fresh={fresh_lowest5_vals} vs committed={committed_lowest5_vals}")
    committed_near_vals = [(round(c[0], 2), c[1], c[2], c[3], c[4]) for c in committed["near_line"]]
    fresh_near_vals = [(round(c[0], 2), c[1], c[2], c[3], c[4]) for c in fresh_near_line_sorted]
    if committed_near_vals != fresh_near_vals:
        mismatches.append(f"near_line: fresh={fresh_near_vals} vs committed={committed_near_vals}")

    if mismatches:
        _log(lines, "\n🛑 STOP: fresh re-derivation disagrees with the committed "
                     "row1_excess_floor_results.txt -- ROW 1's frozen result has moved since it was "
                     "landed. This voids this spec until explained on its own terms (spec sec.1).")
        for m in mismatches:
            _log(lines, f"  MISMATCH: {m}")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    _log(lines, f"Cross-check vs committed row1_excess_floor_results.txt: IDENTICAL "
                 f"(F, p01, p05, lowest-5, near-line all match exactly). {_ROW1_COMMITTED_PATH.name} "
                 "unmodified by this run's re-derivation.")

    F_FIVE_SWEEP = five["F"]

    # ── Four-sweep leave-one-out F (A1.3's mandatory disclosure) ────────────────────────────────
    _log(lines, "\n=== Four-sweep leave-one-out F (drops every sweep labelled \"20260050\") ===")
    loo_sweeps = [s for s in _FROZEN_SWEEPS if _SWEEP_BINARY_ERA[s] != "20260050"]
    _log(lines, f"Dropped (derived from the era table, not hardcoded): "
                 f"{[s for s in _FROZEN_SWEEPS if s not in loo_sweeps]}")
    four = _compute_population(harness_common, loo_sweeps, lines, "Four-sweep LOO")
    if four is None:
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    F_FOUR_SWEEP_LOO = four["F"]

    # ── T, cited, and the mechanical predicate ──────────────────────────────────────────────────
    _log(lines, "\n=== T (cited, not recomputed) ===")
    _log(lines, f"C = {_C_DB:.3f} dB (base FP-PARITY spec sec.2, citing "
                 "qa/rr-study/awgn-fp-replay/results/M1-M4-report.md sec.4, n=454 offline false accepts)")
    _log(lines, f"T = C + 1.0 = {_T_DB:.3f} dB (base spec sec.4)")
    _log(lines, "Confirmed production-valid by FP-PARITY P3 ROW 0n-C "
                 "(2026-09-06-1025-architect-to-qa-ruling-p3-adjudication.md sec.2.4): "
                 "C' = +1.652 dB, C'-C = +0.030 dB, 0 of 432 rows exceed T -- non-fire. "
                 "This script does not re-open that measurement.")

    _log(lines, "\n=== ROW 2 / ROW 3 -- the verdict ===")
    _log(lines, f"F (five-sweep, A1.1 frozen population)        = {F_FIVE_SWEEP:+.2f} dB")
    _log(lines, f"F (four-sweep leave-one-out, A1.3 disclosure) = {F_FOUR_SWEEP_LOO:+.2f} dB")
    _log(lines, f"T                                             = {_T_DB:.3f} dB")
    margin_five = F_FIVE_SWEEP - _T_DB
    margin_loo = F_FOUR_SWEEP_LOO - _T_DB
    fire_five = margin_five >= _ROW2_FIRE_MARGIN_DB
    fire_loo = margin_loo >= _ROW2_FIRE_MARGIN_DB
    _log(lines, f"F - T (five-sweep)      = {margin_five:+.3f} dB  vs {_ROW2_FIRE_MARGIN_DB:.1f} dB bar "
                 f"=> {'ROW 2' if fire_five else 'ROW 3'}")
    _log(lines, f"F - T (four-sweep LOO)  = {margin_loo:+.3f} dB  vs {_ROW2_FIRE_MARGIN_DB:.1f} dB bar "
                 f"=> {'ROW 2' if fire_loo else 'ROW 3'}")

    _log(lines, "\n=== A1.3 disclosure block, five-sweep population, binary-attributed ===")
    _log(lines, "Lowest 5 reconstructed (corrected) excess values:")
    for m in fresh_lowest5:
        _log(lines, _fmt_decode(m))
    _log(lines, f"\nDistinct decodes within +-1 dB of the ROW2/3 fire line "
                 f"({_ROW2_FIRE_THRESHOLD_DB:.2f} dB, T={_T_DB:.3f} dB, now confirmed production-valid): "
                 f"{len(fresh_near_line_sorted)}")
    for m in fresh_near_line_sorted:
        _log(lines, _fmt_decode(m))

    if fire_five != fire_loo:
        _log(lines, "\n🛑 STOP: the four-sweep leave-one-out F flips the verdict against the five-sweep "
                     "F. The pre-registered population for ROW 1/2/3 is the frozen five-sweep set "
                     "(A1.1); the four-sweep figure is a disclosure, not an alternate predicate. This "
                     "is HK-021(k)/HK-025 territory -- reporting to the Architect for adjudication, "
                     "rendering NO verdict from this script.")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 2

    _log(lines, f"\nBoth five-sweep and four-sweep-LOO F agree on which side of the "
                 f"{_ROW2_FIRE_MARGIN_DB:.1f} dB bar the margin falls -- rendering the verdict.")

    if fire_five:
        _log(lines, "\n=== VERDICT: ROW 2 FIRES ===")
        _log(lines, "ROW 2 -- the emission floor is viable, and the dev-task is authorised. "
                     "T = C + 1.0 dB (one in-chain readout quantum above the highest false accept "
                     "measured anywhere). FIRES iff F - T >= 6.0 dB. => QA authors the emission-side "
                     "filter dev-task (HK-011: authors and stops) at that T, with acceptance criteria "
                     "measured in-chain, and the rule-of-three 95% upper bound on genuine loss -- "
                     "never \"costs nothing.\"")
        _log(lines, "\nPer spec sec.0(2): no filter is built by this script or this session. QA "
                     "authors a separate dev-task artefact and stops (HK-011); a Developer session "
                     "builds it later, on the Captain's initiative.")
    else:
        _log(lines, "\n=== VERDICT: ROW 3 FIRES ===")
        _log(lines, "ROW 3 -- the margin is not there. FIRES iff F - T < 6.0 dB. => No dev-task is "
                     "authored. State plainly: the emission-side floor cannot be set with the "
                     "project's required margin on the evidence available, because the genuine "
                     "population reaches down to within F - T dB of the false-accept ceiling. "
                     "PARKED, not closed -- closing the route requires a population that reaches the "
                     "decoder's true floor, which S1b's bottom rung may not. Do not soften this into "
                     "\"needs more data\" and do not re-run with a smaller margin.")
        _log(lines, "\nROW 2 and ROW 3 are exact complements by construction; exactly one fires.")

    _log(lines, "\n=== Standing disclosures, restated (spec sec.3) ===")
    _log(lines, "F stays labelled an UPPER BOUND, not the floor: bottom-rung (-18 dB) decodes at "
                 "100% pooled (15/15) => the true floor is demonstrably lower and unmeasured by this "
                 "instrument (HK-026).")
    _log(lines, "No new decode, no new sweep, no src/ or native/ change. Every input is a re-read of "
                 "truth.csv/owsfz-all.txt already on disk for the five frozen sweeps (A1.1).")

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
