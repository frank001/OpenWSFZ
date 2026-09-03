#!/usr/bin/env python3
"""S5-LEVEL ROW 0 -- mechanical scope checks for the `level_dbfs` normalisation defect.

Spec: qa/rr-study/2026-09-02-2002-architect-to-qa-spec-s5-level-normalisation-scope-and-repair.md
(Architect -> QA, 2026-09-02 20:02Z). Ships ROW 0's four predicates as code (HK-021(r)) rather
than hand-computing them, and prints/writes each row's evaluation before any repair is proposed.

Every row is a hard predicate on data:

  ROW 0f -- enumerate every qa/rr-study/scenarios/*.json containing "level_dbfs"; for each,
            collect the distinct declared values across its parts.
            PASS iff exactly 4 files, and exactly 1 of them has >1 distinct value.
  ROW 0g -- for the one varying file, measure actual RMS dBFS per part from the REAL,
            already-rendered `harness/run_scenario.py --dry-run --dump-wav-dir` baseline
            (qa/rr-study/awgn-fp-replay/_work/row0b_baseline/, the AWGN-FP arm's own ROW 0b
            population -- same scenario, same seeds, same unmodified normalising code path;
            re-used rather than re-rendered so this check cannot itself introduce a second,
            possibly-divergent noise source).
            PASS iff all parts land within 2.0 dB of each other (the peak-normalisation
            cancellation the spec's Sec.0 claim 1 predicts).
  ROW 0h -- same measurement on the level-preserving re-render
            (qa/rr-study/awgn-fp-replay/_work/row0c_lp_baseline/, produced by
            render_row0c_level_preserving.py, which skips the peak-renormalise step).
            PASS iff part1 - part0 = 10.0 +/- 1.0 dB (the declared step, actually delivered).
  ROW 0i -- grep the shipped harness/run_scenario.py for `_finalize_playback_samples` and the
            main-loop call site, and confirm both apply `_PLAYBACK_PEAK_LEVEL`.
            PASS iff both present and both apply the same constant.

ROW 0f is the one that can overturn the spec (its own Sec.0 claim 1) -- it is evaluated first and
its failure branch is STOP, not a patched threshold (HK-021(k)).

Usage:
    python s5_level_scope.py
Writes qa/rr-study/s5_level_scope_results.txt (verdict lines) alongside stdout output.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import wave

import numpy as np

_HERE = pathlib.Path(__file__).parent.resolve()
_SCENARIOS_DIR = _HERE / "scenarios"
_ROW0B_BASELINE_DIR = _HERE / "awgn-fp-replay" / "_work" / "row0b_baseline"
_ROW0C_LP_BASELINE_DIR = _HERE / "awgn-fp-replay" / "_work" / "row0c_lp_baseline"
_RUN_SCENARIO_PY = _HERE / "harness" / "run_scenario.py"
_RESULTS_PATH = _HERE / "s5_level_scope_results.txt"

_SLOT_FILENAME_RE = re.compile(r"^S5_p(?P<part>\d+)_t(?P<trial>\d+)_s(?P<seed>\d+)\.wav$")

_ROW0G_MAX_SPREAD_DB = 2.0
_ROW0H_TARGET_STEP_DB = 10.0
_ROW0H_TOLERANCE_DB = 1.0


def _log(lines: list, msg: str) -> None:
    print(msg)
    lines.append(msg)


# ── ROW 0f ──────────────────────────────────────────────────────────────────

def row0f_enumerate_level_dbfs_files(lines: list) -> tuple[bool, pathlib.Path | None]:
    _log(lines, "\n=== ROW 0f: enumerate scenarios/*.json containing level_dbfs ===")
    hits: dict[pathlib.Path, list] = {}
    for path in sorted(_SCENARIOS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        values = []
        for part in data.get("parts", []):
            if "level_dbfs" in part:
                values.append(part["level_dbfs"])
        if values:
            hits[path] = values

    varying = []
    for path, values in hits.items():
        distinct = sorted(set(values))
        _log(lines, f"  {path.name}: values={values} distinct={distinct}")
        if len(distinct) > 1:
            varying.append(path)

    n_files = len(hits)
    n_varying = len(varying)
    passed = (n_files == 4) and (n_varying == 1)
    _log(lines, f"ROW 0f: files_with_level_dbfs={n_files} (expect 4)  "
                f"files_with_gt1_distinct_value={n_varying} (expect 1)  PASS={passed}")
    if not passed:
        _log(lines, "ROW 0f FAILED -> spec Sec.0 claim 1 is wrong. STOP, do not evaluate "
                     "further rows; the scope is wider than the spec assumes and the spec "
                     "must be re-drafted, not patched.")
        return False, None
    return True, varying[0]


# ── shared WAV RMS helper ───────────────────────────────────────────────────

def _rms_dbfs_per_part(wav_dir: pathlib.Path) -> dict[int, list]:
    """Returns {part_index: [rms_dbfs, ...]} over every S5_p*_t*_s*.wav in wav_dir."""
    by_part: dict[int, list] = {}
    files = sorted(wav_dir.glob("*.wav"))
    if not files:
        raise FileNotFoundError(f"no WAVs found under {wav_dir}")
    for path in files:
        m = _SLOT_FILENAME_RE.match(path.name)
        if not m:
            continue
        part = int(m.group("part"))
        with wave.open(str(path), "rb") as wf:
            assert wf.getsampwidth() == 2, f"expected 16-bit PCM, got {wf.getsampwidth()} bytes: {path}"
            n = wf.getnframes()
            raw = wf.readframes(n)
        samples = np.frombuffer(raw, dtype="<i2").astype("float64") / 32768.0
        rms = np.sqrt(np.mean(samples ** 2))
        rms_dbfs = 20.0 * np.log10(rms) if rms > 0 else float("-inf")
        by_part.setdefault(part, []).append(rms_dbfs)
    return by_part


# ── ROW 0g ──────────────────────────────────────────────────────────────────

def row0g_baseline_normalised_rms(lines: list) -> bool:
    _log(lines, "\n=== ROW 0g: actual RMS dBFS per part, REAL run_scenario.py "
                 "--dry-run --dump-wav-dir baseline render (peak-normalised) ===")
    if not _ROW0B_BASELINE_DIR.is_dir():
        _log(lines, f"ROW 0g: FAILED -- population directory missing: {_ROW0B_BASELINE_DIR} "
                     "(re-render with harness/run_scenario.py --dry-run --dump-wav-dir "
                     "against the real scenarios/s5-noise.json first)")
        return False
    by_part = _rms_dbfs_per_part(_ROW0B_BASELINE_DIR)
    means = {}
    for part in sorted(by_part):
        vals = by_part[part]
        mean = float(np.mean(vals))
        means[part] = mean
        _log(lines, f"  part {part}: n={len(vals)}  mean_rms_dbfs={mean:.2f}  "
                     f"min={min(vals):.2f}  max={max(vals):.2f}")
    spread = max(means.values()) - min(means.values())
    passed = spread <= _ROW0G_MAX_SPREAD_DB
    _log(lines, f"ROW 0g: per-part mean spread = {spread:.2f} dB "
                 f"(threshold <= {_ROW0G_MAX_SPREAD_DB} dB)  PASS={passed}")
    if not passed:
        _log(lines, "ROW 0g FAILED -> parts differ by >= 2 dB in the normalised render: the "
                     "cancellation mechanism in Sec.0 claim 1 is wrong. STOP and escalate.")
    else:
        _log(lines, "ROW 0g PASSED -> confirms the declared 10 dB step (part0 -20 dBFS / "
                     "part1 -10 dBFS) is NOT what the normalised, actually-shipped render "
                     "delivers: both land within 2 dB of each other.")
    return passed


# ── ROW 0h ──────────────────────────────────────────────────────────────────

def row0h_level_preserving_rms(lines: list) -> bool:
    _log(lines, "\n=== ROW 0h: actual RMS dBFS per part, level-preserving re-render "
                 "(render_row0c_level_preserving.py, no peak-renormalise) ===")
    if not _ROW0C_LP_BASELINE_DIR.is_dir():
        _log(lines, f"ROW 0h: FAILED -- population directory missing: {_ROW0C_LP_BASELINE_DIR} "
                     "(run awgn-fp-replay/render_row0c_level_preserving.py first)")
        return False
    by_part = _rms_dbfs_per_part(_ROW0C_LP_BASELINE_DIR)
    if 0 not in by_part or 1 not in by_part:
        _log(lines, f"ROW 0h: FAILED -- expected parts {{0,1}}, found {sorted(by_part)}")
        return False
    mean0 = float(np.mean(by_part[0]))
    mean1 = float(np.mean(by_part[1]))
    _log(lines, f"  part 0 (declared -20 dBFS): n={len(by_part[0])}  mean_rms_dbfs={mean0:.2f}")
    _log(lines, f"  part 1 (declared -10 dBFS): n={len(by_part[1])}  mean_rms_dbfs={mean1:.2f}")
    step = mean1 - mean0
    passed = abs(step - _ROW0H_TARGET_STEP_DB) <= _ROW0H_TOLERANCE_DB
    _log(lines, f"ROW 0h: part1 - part0 = {step:.2f} dB "
                 f"(target {_ROW0H_TARGET_STEP_DB} +/- {_ROW0H_TOLERANCE_DB} dB)  PASS={passed}")
    if not passed:
        _log(lines, "ROW 0h FAILED -> the level-preserving workaround does not actually "
                     "restore the declared step. ROW 0c's own validity is in question. "
                     "STOP and escalate.")
    else:
        _log(lines, "ROW 0h PASSED -> the level-preserving path DOES deliver the declared "
                     "10 dB step; AWGN-FP ROW 0c's reading (rendered via this same path) "
                     "stands as a genuine +/-10 dB level-dependence check.")
    return passed


# ── ROW 0i ──────────────────────────────────────────────────────────────────

def row0i_normalisation_call_sites(lines: list) -> bool:
    _log(lines, "\n=== ROW 0i: grep run_scenario.py for the two normalisation call sites ===")
    if not _RUN_SCENARIO_PY.is_file():
        _log(lines, f"ROW 0i: FAILED -- {_RUN_SCENARIO_PY} not found")
        return False
    text = _RUN_SCENARIO_PY.read_text(encoding="utf-8")
    src_lines = text.splitlines()

    def_hits = [i + 1 for i, l in enumerate(src_lines) if "_finalize_playback_samples" in l]
    peak_hits = [i + 1 for i, l in enumerate(src_lines) if "_PLAYBACK_PEAK_LEVEL" in l]

    _log(lines, f"  '_finalize_playback_samples' occurs on lines: {def_hits}")
    _log(lines, f"  '_PLAYBACK_PEAK_LEVEL' occurs on lines: {peak_hits}")

    # Both the helper function's own body and the main-loop inline application (spec's
    # ":1156" call site -- the spec's own line number, code has since drifted slightly)
    # must apply _PLAYBACK_PEAK_LEVEL. Find the helper's def line and confirm the constant
    # is used inside its body; separately confirm a second, independent application in the
    # main loop (i.e. more than one non-definition occurrence of _PLAYBACK_PEAK_LEVEL).
    def_line = next((i + 1 for i, l in enumerate(src_lines)
                      if l.startswith("def _finalize_playback_samples")), None)
    const_def_line = next((i + 1 for i, l in enumerate(src_lines)
                            if l.startswith("_PLAYBACK_PEAK_LEVEL")), None)

    helper_present = def_line is not None
    # occurrences of _PLAYBACK_PEAK_LEVEL other than its own declaration line
    usage_lines = [n for n in peak_hits if n != const_def_line]
    helper_uses_it = any(def_line is not None and n > def_line and n < def_line + 20
                          for n in usage_lines)
    # a usage strictly outside the helper's own small body counts as the second, main-loop
    # call site
    main_loop_uses_it = any(not (def_line is not None and def_line <= n < def_line + 20)
                             for n in usage_lines)

    passed = helper_present and helper_uses_it and main_loop_uses_it
    _log(lines, f"ROW 0i: helper_present={helper_present}  "
                 f"helper_applies_constant={helper_uses_it}  "
                 f"second_independent_call_site_applies_constant={main_loop_uses_it}  "
                 f"PASS={passed}")
    if not passed:
        _log(lines, "ROW 0i FAILED -> only one path normalises; live and offline renders "
                     "would differ. This is a SEPARATE, WORSE finding. STOP and report it "
                     "as such -- do not fold it into the S5-LEVEL scope statement.")
    else:
        _log(lines, "ROW 0i PASSED -> both the helper function and the main render loop "
                     "apply the same _PLAYBACK_PEAK_LEVEL constant; offline "
                     "(--dump-wav-dir) and live-playback renders normalise identically.")
    return passed


def main() -> int:
    lines: list = []
    _log(lines, "S5-LEVEL ROW 0 -- mechanical scope checks")
    _log(lines, "Spec: qa/rr-study/2026-09-02-2002-architect-to-qa-spec-s5-level-"
                 "normalisation-scope-and-repair.md")

    ok_0f, varying_file = row0f_enumerate_level_dbfs_files(lines)
    if not ok_0f:
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    _log(lines, f"\nROW 0f identifies the sole varying file: {varying_file.name}")

    ok_0g = row0g_baseline_normalised_rms(lines)
    ok_0h = row0h_level_preserving_rms(lines)
    ok_0i = row0i_normalisation_call_sites(lines)

    _log(lines, "\n=== SUMMARY ===")
    _log(lines, f"ROW 0f (exactly 4 files, exactly 1 varying): PASS")
    _log(lines, f"ROW 0g (normalised render cancels the step, spread <= 2 dB): "
                 f"{'PASS' if ok_0g else 'FAIL'}")
    _log(lines, f"ROW 0h (level-preserving render restores 10 +/- 1 dB step): "
                 f"{'PASS' if ok_0h else 'FAIL'}")
    _log(lines, f"ROW 0i (both normalisation call sites present and consistent): "
                 f"{'PASS' if ok_0i else 'FAIL'}")

    all_pass = ok_0g and ok_0h and ok_0i
    _log(lines, f"\nALL ROW 0 CHECKS: {'PASS' if all_pass else 'AT LEAST ONE FAILED'}")

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
