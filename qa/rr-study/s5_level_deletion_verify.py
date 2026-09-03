#!/usr/bin/env python3
"""S5-LEVEL Amendment 1, A1.3 -- pre-registered checks on the `level_dbfs` DELETION itself.

Spec: qa/rr-study/2026-09-02-2002-architect-to-qa-spec-s5-level-normalisation-scope-and-repair.md
AMENDMENT 1 (2026-09-03 16:16Z, PO ruling -- Option 2). Ships ROW 0j/0k/0l's predicates as code
(HK-021(r)) rather than hand-computing them.

  ROW 0j -- delivered audio unchanged, byte level. SHA256 every WAV in the pre-deletion baseline
            population (awgn-fp-replay/_work/row0b_baseline/, rendered from the REAL, unmodified
            scenarios/s5-noise.json before this arm's deletion) against the post-deletion
            population (awgn-fp-replay/_work/row0j_after/, rendered from the same file after the
            key was deleted, same 60 (part,trial,seed) seeds). PASS iff 60/60 pairs identical.
            Both directories are pre-existing, frozen renders -- this script does not re-render
            anything (re-rendering the "before" population is no longer possible once the live
            scenario file has been edited; the frozen row0b_baseline/ directory IS the "before"
            record, produced by the AWGN-FP arm's own ROW 0b anchor render).
  ROW 0k -- fires only if ROW 0j fails: is the byte difference decode-invisible? Answered
            separately, in code, by tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs's
            Row0k_S5LevelDeletion_DecodeSetsIdenticalBeforeAfter Fact (HK-015: the decode seam is
            internal to OpenWSFZ.Ft8, only reachable from a test assembly with
            InternalsVisibleTo -- same reasoning as every other AWGN-FP decode check). This script
            reads that Fact's own verdict line from row0_verdicts.txt rather than re-implementing
            the decode comparison in Python (HK-022: one implementation of the join, not two).
  ROW 0l -- truth.csv consumers survive the empty true_snr_db. Copies an existing S5 matched CSV +
            truth.csv (from a historical, already-run sweep) into a gitignored scratch directory,
            runs harness/analyse.py once against the copy UNMODIFIED (baseline), blanks S5's
            true_snr_db column in both files (simulating exactly what a real regeneration with the
            key deleted produces), reruns analyse.py, and diffs stdout + report.md byte-for-byte.
            PASS iff no exception is raised in either run and the two outputs are identical.

Usage:
    python s5_level_deletion_verify.py
Writes qa/rr-study/s5_level_deletion_verify_results.txt alongside stdout output.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_BEFORE_DIR = _HERE / "awgn-fp-replay" / "_work" / "row0b_baseline"
_AFTER_DIR = _HERE / "awgn-fp-replay" / "_work" / "row0j_after"
_VERDICTS_TXT = _HERE / "awgn-fp-replay" / "results" / "row0_verdicts.txt"
_HISTORICAL_RUN_DIR = _HERE / "results" / "2026-09-02-3b52608"
_SCRATCH_DIR = _HERE / "awgn-fp-replay" / "_work" / "row0l_scratch"  # gitignored (_work/)
_ANALYSE_PY = _HERE / "harness" / "analyse.py"
_RESULTS_PATH = _HERE / "s5_level_deletion_verify_results.txt"
_TREND_CSV = _HERE / "trend.csv"  # analyse.py appends to this unconditionally on every run;
                                   # snapshot/restore around ROW 0l's two scratch-dir runs so this
                                   # verification script never pollutes the real trend history.


def _log(lines: list, msg: str) -> None:
    print(msg)
    lines.append(msg)


# ── ROW 0j ──────────────────────────────────────────────────────────────────

def row0j_byte_identity(lines: list) -> bool:
    _log(lines, "\n=== ROW 0j: SHA256 byte-identity, row0b_baseline (before) vs row0j_after (after) ===")
    if not _BEFORE_DIR.is_dir() or not _AFTER_DIR.is_dir():
        _log(lines, f"ROW 0j: FAILED -- missing population directory "
                     f"(before={_BEFORE_DIR.is_dir()}, after={_AFTER_DIR.is_dir()})")
        return False

    def sha_by_name(d: pathlib.Path) -> dict[str, str]:
        out = {}
        for p in sorted(d.glob("*.wav")):
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    before = sha_by_name(_BEFORE_DIR)
    after = sha_by_name(_AFTER_DIR)

    if set(before) != set(after):
        _log(lines, f"ROW 0j: FAILED -- filename sets differ: "
                     f"before-only={sorted(set(before) - set(after))} "
                     f"after-only={sorted(set(after) - set(before))}")
        return False

    matches = sum(1 for name in before if before[name] == after[name])
    mismatches = [name for name in before if before[name] != after[name]]
    total = len(before)
    passed = matches == total

    _log(lines, f"ROW 0j: total_pairs={total}  identical={matches}  mismatched={len(mismatches)}  PASS={passed}")
    if mismatches:
        by_part = {}
        for name in mismatches:
            part = re.match(r"^S5_p(\d+)_", name).group(1)
            by_part[part] = by_part.get(part, 0) + 1
        _log(lines, f"ROW 0j: mismatches by part_index: {by_part}")
    if not passed:
        _log(lines, "ROW 0j FAILED -> not byte-identical. ROW 0k (decode-invisibility) is the "
                     "next gate, per spec A1.3 -- see the C# Fact's own verdict, read below.")
    else:
        _log(lines, "ROW 0j PASSED -> the deletion is a fully free edit, byte-identical audio.")
    return passed


# ── ROW 0k ──────────────────────────────────────────────────────────────────

def row0k_decode_invisible(lines: list) -> bool | None:
    _log(lines, "\n=== ROW 0k: decode-invisibility (read from tests/.../AwgnFpReplayTests.cs's own verdict) ===")
    if not _VERDICTS_TXT.is_file():
        _log(lines, f"ROW 0k: verdict file not found: {_VERDICTS_TXT} -- run "
                     f"`dotnet test --filter FullyQualifiedName~Row0k_S5LevelDeletion` first")
        return None
    text = _VERDICTS_TXT.read_text(encoding="utf-8")
    row0k_lines = [l for l in text.splitlines() if "row0k_s5_level_deletion" in l]
    if not row0k_lines:
        _log(lines, "ROW 0k: no row0k_s5_level_deletion verdict line found -- Fact not yet run")
        return None
    last = row0k_lines[-1]
    _log(lines, f"ROW 0k: {last}")
    passed = "PASS=True" in last
    if passed:
        _log(lines, "ROW 0k PASSED -> the 1-LSB byte difference from ROW 0j is decode-invisible: "
                     "Option 2 lands, disclosed, not silently.")
    else:
        _log(lines, "ROW 0k FAILED -> real STOP branch per spec A1.3: revert the deletion, "
                     "record-correction-only, escalate to the Architect.")
    return passed


# ── ROW 0l ──────────────────────────────────────────────────────────────────

def row0l_truth_csv_consumers_survive(lines: list) -> bool:
    _log(lines, "\n=== ROW 0l: truth.csv consumers (analyse.py, render_report.py) survive the empty true_snr_db ===")
    if not _HISTORICAL_RUN_DIR.is_dir():
        _log(lines, f"ROW 0l: FAILED -- historical run dir not found: {_HISTORICAL_RUN_DIR}")
        return False
    if not (_HISTORICAL_RUN_DIR / "S5_matched.csv").is_file():
        _log(lines, f"ROW 0l: FAILED -- no S5_matched.csv under {_HISTORICAL_RUN_DIR}")
        return False

    if _SCRATCH_DIR.exists():
        shutil.rmtree(_SCRATCH_DIR)
    _SCRATCH_DIR.mkdir(parents=True)
    for csv_path in _HISTORICAL_RUN_DIR.glob("*.csv"):
        shutil.copy2(csv_path, _SCRATCH_DIR / csv_path.name)

    # analyse.py appends a row to trend.csv on every run (unconditionally, no --run-dir-based
    # opt-out) -- snapshot it now and restore verbatim after both scratch runs below, so this
    # verification script leaves no trace in the real trend history (caught once already: the
    # first draft of this script polluted trend.csv with "row0l_scratch"/"_work_row0l_scratch"
    # rows before this snapshot/restore was added).
    trend_before_bytes = _TREND_CSV.read_bytes() if _TREND_CSV.is_file() else None

    def run_analyse() -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(_ANALYSE_PY), "--run-dir", str(_SCRATCH_DIR)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return proc.returncode, proc.stdout + proc.stderr

    rc_before, out_before = run_analyse()
    report_path = _SCRATCH_DIR / "report.md"
    report_before = report_path.read_text(encoding="utf-8") if report_path.is_file() else None

    _log(lines, f"ROW 0l: baseline run (unmodified copy) exit_code={rc_before}")
    s5_lines_before = [l for l in out_before.splitlines() if "S5" in l]
    for l in s5_lines_before:
        _log(lines, f"  {l}")

    if rc_before != 0:
        _log(lines, "ROW 0l: FAILED -- baseline run itself did not exit 0; cannot proceed")
        return False

    # Blank true_snr_db on every S5 row of both S5_matched.csv and truth.csv, exactly what a real
    # regeneration with the key deleted produces (run_scenario.py:1113 default becomes "").
    def blank_s5_true_snr_db(path: pathlib.Path, scenario_col: str) -> int:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames
        n = 0
        for r in rows:
            if r.get(scenario_col) == "S5":
                r["true_snr_db"] = ""
                n += 1
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return n

    n1 = blank_s5_true_snr_db(_SCRATCH_DIR / "S5_matched.csv", "scenario_id")
    n2 = blank_s5_true_snr_db(_SCRATCH_DIR / "truth.csv", "scenario_id") if (_SCRATCH_DIR / "truth.csv").is_file() else 0
    _log(lines, f"ROW 0l: blanked true_snr_db on {n1} S5_matched.csv rows, {n2} truth.csv rows")

    rc_after, out_after = run_analyse()
    report_after = report_path.read_text(encoding="utf-8") if report_path.is_file() else None

    _log(lines, f"ROW 0l: post-deletion-simulation run exit_code={rc_after}")
    s5_lines_after = [l for l in out_after.splitlines() if "S5" in l]
    for l in s5_lines_after:
        _log(lines, f"  {l}")

    no_exception = rc_after == 0
    stdout_identical = out_before == out_after
    report_identical = report_before == report_after

    passed = no_exception and stdout_identical and report_identical
    _log(lines, f"ROW 0l: no_exception={no_exception}  stdout_byte_identical={stdout_identical}  "
                 f"report_md_byte_identical={report_identical}  PASS={passed}")

    # Render pipeline sanity (render_report.py) -- part of A1.3's "and render_report.py".
    render_rc = subprocess.run(
        [sys.executable, str(_HERE / "render_report.py"), str(report_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).returncode
    _log(lines, f"ROW 0l: render_report.py exit_code={render_rc} (must be 0)")
    passed = passed and (render_rc == 0)

    shutil.rmtree(_SCRATCH_DIR, ignore_errors=True)
    _log(lines, f"ROW 0l: scratch dir {_SCRATCH_DIR} removed (was gitignored under _work/, "
                 f"contained a copy of a real historical results dir -- not left on disk)")

    if trend_before_bytes is not None:
        _TREND_CSV.write_bytes(trend_before_bytes)
    elif _TREND_CSV.is_file():
        _TREND_CSV.unlink()
    _log(lines, f"ROW 0l: {_TREND_CSV} restored to its pre-run state "
                 f"(analyse.py's two scratch-dir runs above each appended a row to it)")

    if not passed:
        _log(lines, "ROW 0l FAILED -> a downstream consumer chokes on or is changed by the empty "
                     "true_snr_db column. STOP and investigate before trusting the deletion.")
    else:
        _log(lines, "ROW 0l PASSED -> analyse.py and render_report.py are provably inert to the "
                     "empty S5 true_snr_db column, not merely 'should be' inert by code reading.")
    return passed


def main() -> int:
    lines: list = []
    _log(lines, "S5-LEVEL Amendment 1 A1.3 -- pre-registered checks on the deletion itself")
    _log(lines, "Spec: qa/rr-study/2026-09-02-2002-architect-to-qa-spec-s5-level-"
                 "normalisation-scope-and-repair.md (AMENDMENT 1)")

    ok_0j = row0j_byte_identity(lines)
    ok_0k = row0k_decode_invisible(lines)
    ok_0l = row0l_truth_csv_consumers_survive(lines)

    _log(lines, "\n=== SUMMARY ===")
    _log(lines, f"ROW 0j (byte-identical before/after): {'PASS' if ok_0j else 'FAIL'}")
    _log(lines, f"ROW 0k (decode-invisible, fires only because 0j failed): "
                 f"{'PASS' if ok_0k else ('FAIL' if ok_0k is False else 'NOT RUN')}")
    _log(lines, f"ROW 0l (truth.csv consumers survive): {'PASS' if ok_0l else 'FAIL'}")

    if ok_0j:
        verdict = "Option 2 lands, byte-identical, no disclosure needed beyond the record correction."
    elif ok_0k:
        verdict = ("Option 2 lands: not byte-identical (1-LSB quantisation, S5 part 1 only) but "
                    "decode-invisible -- disclosed, not silent, per spec A1.3.")
    elif ok_0k is False:
        verdict = "STOP BRANCH: revert the deletion, record-correction-only. Escalate to the Architect."
    else:
        verdict = "INCOMPLETE: ROW 0k has not been run (see the C# Fact)."
    _log(lines, f"\nVERDICT: {verdict}")

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    return 0 if (ok_0j or ok_0k) and ok_0l else 1


if __name__ == "__main__":
    sys.exit(main())
