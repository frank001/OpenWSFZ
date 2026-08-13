#!/usr/bin/env python3
"""Smoke test for g2b_family.py (D2, 2026-08-12, fourth Architect review;
extended for E1/E2/E3, 2026-08-12 21:43Z early candidates, folded into
revision 5).

D2 originally required: "Smoke-test the family adjudicator: all-ROW_3 ->
CLOSE; one ROW_1 -> DO NOT CLOSE; two verdicts -> refuse; duplicate f_min ->
refuse; any ROW_0 -> refuse." All five are exercised below, plus two extra
fail-closed checks (four verdicts, malformed verdict file) added on the same
"REFUSE, do not guess" discipline C2/C4 already established elsewhere in this
chain, and a direct check that the adjudicator never prints anything that
reads as a recommendation among eligible rungs (the deliberate asymmetry D2
specified).

The early-candidates memo's sequencing instruction (its §7 step 2) required:
"Smoke-test each new refusal separately: band mismatch, f_max mismatch,
wav_dir mismatch, baseline-SHA mismatch, manifest-digest mismatch, and all
three exit codes." All five new refusals are exercised below as separate
checks, and every check in this file now asserts the exit code as well as
the printed text -- not just the CLOSE/DO NOT CLOSE/REFUSE cases the new
findings were about, so a regression in ANY path's exit code is caught, not
only the three E3 was filed against.

Exits non-zero and prints every mismatch if anything drifts from the
expected adjudication.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAMILY = HERE / "g2b_family.py"

FAILURES = []

# E1/E2 fix: default provenance/binary fields every verdict now carries.
# Tests that exercise E1/E2 refusals override exactly the field under test on
# exactly one verdict; every other verdict, and every other field, keeps
# these defaults, so a mismatch check is never accidentally satisfied by two
# OTHER fields also differing.
DEFAULT_WAV_DIR = "SMOKETEST_WAV_DIR"
DEFAULT_DLL_SHA256 = {"baseline": "c" * 64, "widened": "d" * 64, "repeat": "c" * 64}
DEFAULT_MANIFEST_SHA256 = "e" * 64
DEFAULT_BURNED_CORPUS = "yes"

EXIT_CLOSE, EXIT_DO_NOT_CLOSE, EXIT_REFUSE = 0, 1, 2


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def make_verdict(tmp, name, band, f_min, f_max, row, **extra):
    v = {"band": band, "f_min": f_min, "f_max": f_max, "row": row,
         "scope": "some scope", "p1_fired": False,
         "rates": {"g_low": 0.02, "g_high": 0.01, "churn_net": 0.0,
                    "churn_gross": 0.0},
         "bounds": {"g_low": 0.015, "g_high": 0.005, "churn_net": -0.001,
                     "churn_gross": 0.005},
         "bars": {"g_new_min_rate": 0.01, "g_high_min_rate": 0.005,
                   "churn_net_min_rate": -0.0025,
                   "churn_gross_max_rate": 0.02},
         "wav_dir": DEFAULT_WAV_DIR,
         "dll_sha256": dict(DEFAULT_DLL_SHA256),
         "manifest_sha256": DEFAULT_MANIFEST_SHA256,
         "burned_corpus": DEFAULT_BURNED_CORPUS}
    v.update(extra)
    path = tmp / name
    path.write_text(json.dumps(v))
    return path


def run_family(*paths):
    """Returns (combined stdout+stderr, exit code) -- E3 fix: every caller
    below now asserts the exit code alongside the printed text, not just the
    three cases E3 was filed against."""
    cmd = [sys.executable, str(FAMILY)]
    for p in paths:
        cmd += ["--verdict", str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr, result.returncode


def main():
    print("=" * 78)
    print("g2b_family.py smoke test -- D2 + E1/E2/E3, 2026-08-12")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ── CLOSE -- all three rungs read ROW_3 ──────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("all-ROW_3 -> CLOSE", "CLOSE --" in out and "DO NOT CLOSE" not in out
              and "REFUSE" not in out, out)
        check("all-ROW_3 -> exit 0 (E3)", code == EXIT_CLOSE, f"code={code}")

        # ── DO NOT CLOSE -- one rung reads ROW_1 ─────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_1")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        # NOTE: "CLOSE --" is a substring of "DO NOT CLOSE --", so the check
        # below tests for the ABSENCE of a bare "\n  CLOSE --" line instead of
        # naively excluding "CLOSE --" (which would always be present here).
        check("one ROW_1 -> DO NOT CLOSE, names the rung", "DO NOT CLOSE --" in out
              and "f_min=140 read ROW_1" in out
              and "\n  CLOSE --" not in out and "REFUSE" not in out, out)
        check("one ROW_1 -> exit 1 (E3)", code == EXIT_DO_NOT_CLOSE, f"code={code}")

        # ── DO NOT CLOSE -- one rung reads ROW_2, named alongside a ROW_1 ────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_2")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_1")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("ROW_2 + ROW_1 both named, ROW_3 rung not named as a problem",
              "f_min=180 read ROW_2" in out and "f_min=140 read ROW_1" in out
              and "f_min=100 read ROW_3" not in out, out)
        check("ROW_2 + ROW_1 -> exit 1 (E3)", code == EXIT_DO_NOT_CLOSE, f"code={code}")

        # ── REFUSE -- two verdicts only, not three ───────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out, code = run_family(v180, v140)
        check("two verdicts -> REFUSE", "REFUSE --" in out and "need exactly 3" in out, out)
        check("two verdicts -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- four verdicts, also not three ──────────────────────────
        v100b = make_verdict(tmp, "v100b.json", "20m", 60, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100, v100b)
        check("four verdicts -> REFUSE", "REFUSE --" in out and "need exactly 3" in out, out)
        check("four verdicts -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- duplicate f_min ─────────────────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140a = make_verdict(tmp, "v140a.json", "20m", 140, 3030, "ROW_3")
        v140b = make_verdict(tmp, "v140b.json", "20m", 140, 3030, "ROW_1")
        out, code = run_family(v180, v140a, v140b)
        check("duplicate f_min -> REFUSE", "REFUSE --" in out
              and "share an f_min" in out, out)
        check("duplicate f_min -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- any verdict reads ROW_0 ────────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_0",
                             scope=None, p1_fired=None, rates=None, bounds=None,
                             wav_dir=None)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("any ROW_0 -> REFUSE", "REFUSE --" in out
              and "NO READ, not evidence" in out
              and "f_min=140, ROW_0" in out, out)
        check("any ROW_0 -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- any verdict reads ROW_0d (gate defect, not ROW_0) ──────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_0d")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("any ROW_0d -> REFUSE", "REFUSE --" in out
              and "f_min=140, ROW_0d" in out, out)
        check("any ROW_0d -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- a malformed verdict file (missing required keys) ──────
        bad = tmp / "bad.json"
        bad.write_text(json.dumps({"band": "20m", "row": "ROW_3"}))  # no f_min/f_max
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out, code = run_family(v180, v140, bad)
        check("malformed verdict (missing f_min/f_max) -> REFUSE",
              "REFUSE --" in out and "missing" in out, out)
        check("malformed verdict -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- a verdict from a pre-E1/E2 revision (has band/f_min/
        # f_max/row, but none of the new fields) -- must not be silently
        # adjudicated with unknown provenance.
        old = tmp / "old.json"
        old.write_text(json.dumps({"band": "20m", "f_min": 100, "f_max": 3030,
                                    "row": "ROW_3", "scope": "x", "p1_fired": False,
                                    "rates": {}, "bounds": {}, "bars": {}}))
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out, code = run_family(v180, v140, old)
        check("pre-E1/E2 verdict (no wav_dir/dll_sha256/manifest_sha256/"
              "burned_corpus) -> REFUSE",
              "REFUSE --" in out and "wav_dir" in out and "dll_sha256" in out, out)
        check("pre-E1/E2 verdict -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── REFUSE -- a verdict path that does not exist ─────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out, code = run_family(v180, v140, tmp / "does_not_exist.json")
        check("missing verdict file -> REFUSE, no traceback",
              "REFUSE --" in out and "could not read verdict" in out
              and "Traceback" not in out, out)
        check("missing verdict file -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── E1 -- REFUSE: three ROW_3 verdicts drawn from three different
        # BANDS. This is the exact shape the memo names as near-certain given
        # the pre-reg's own S5 ladder (three rungs x three bands) -- pre-E1
        # this printed CLOSE.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "17m", 140, 3030, "ROW_3")
        v100 = make_verdict(tmp, "v100.json", "80m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E1: three different bands, all ROW_3 -> REFUSE, not CLOSE",
              "REFUSE --" in out and "one band" in out
              and "\n  CLOSE --" not in out, out)
        check("E1 band mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── E1 -- REFUSE: f_max mismatch (one rung run against a different
        # NEW_F_MAX than the other two).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3000, "ROW_3")  # differs
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E1: f_max mismatch -> REFUSE, not CLOSE",
              "REFUSE --" in out and "one f_max" in out
              and "\n  CLOSE --" not in out, out)
        check("E1 f_max mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── E1 -- REFUSE: wav_dir mismatch -- the exact "two corpora inside
        # 20m" shape the memo names (08-08 held-out remainder vs. the
        # independent 08-03 run).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             wav_dir="20260803_live_run_1713/wsjt-x/wav")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E1: wav_dir mismatch (two corpora, same band) -> REFUSE, not CLOSE",
              "REFUSE --" in out and "one wav_dir" in out
              and "\n  CLOSE --" not in out, out)
        check("E1 wav_dir mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── E2 -- REFUSE: baseline dll_sha256 differs across rungs (three
        # rungs quietly comparing against two different [200,3000) builds).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             dll_sha256={"baseline": "f" * 64, "widened": "d" * 64,
                                          "repeat": "f" * 64})
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E2: baseline SHA mismatch -> REFUSE, not CLOSE",
              "REFUSE --" in out and "BASELINE binaries differ" in out
              and "\n  CLOSE --" not in out, out)
        check("E2 baseline-SHA mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── E2 control -- WIDENED dll_sha256 is deliberately NOT checked: it
        # is expected to differ across rungs (each rung is a different
        # binary), and must not trip the baseline-SHA refusal above.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3",
                             dll_sha256={"baseline": "c" * 64, "widened": "1" * 64,
                                          "repeat": "c" * 64})
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             dll_sha256={"baseline": "c" * 64, "widened": "2" * 64,
                                          "repeat": "c" * 64})
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3",
                             dll_sha256={"baseline": "c" * 64, "widened": "3" * 64,
                                          "repeat": "c" * 64})
        out, code = run_family(v180, v140, v100)
        check("E2 control: differing WIDENED SHAs (expected) do not trip a "
              "refusal -- CLOSE as normal",
              "CLOSE --" in out and "REFUSE" not in out, out)
        check("E2 control -> exit 0 (E3)", code == EXIT_CLOSE, f"code={code}")

        # ── E2 -- REFUSE: manifest_sha256 differs across rungs (the manifest
        # was edited between rungs).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             manifest_sha256="9" * 64)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E2: manifest digest mismatch -> REFUSE, not CLOSE",
              "REFUSE --" in out and "DIFFERENT manifest file contents" in out
              and "\n  CLOSE --" not in out, out)
        check("E2 manifest-digest mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── E2 -- REFUSE: one rung's manifest file did not exist when the
        # gate ran (manifest_sha256 is None) -- must not silently compare
        # equal to another None or crash on slicing it.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             manifest_sha256=None)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E2: one manifest_sha256=None -> REFUSE, no traceback",
              "REFUSE --" in out and "FILE NOT FOUND" in out
              and "Traceback" not in out, out)
        check("E2 manifest None -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── D2's deliberate asymmetry: never a recommendation among eligible
        # (ROW_1) rungs, even when the family stays open with more than one
        # ROW_1 rung.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_1")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_1")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_2")
        out, code = run_family(v180, v140, v100)
        check("DO NOT CLOSE with two ROW_1 rungs never recommends one",
              "DO NOT CLOSE --" in out
              and "recommend" not in out.lower()
              and "choose" not in out.lower(), out)
        check("two ROW_1 + one ROW_2 -> exit 1 (E3)", code == EXIT_DO_NOT_CLOSE, f"code={code}")

    print()
    print("=" * 78)
    if FAILURES:
        print(f"SMOKE TEST FAILED -- {len(FAILURES)} check(s) did not hold:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("SMOKE TEST PASSED -- CLOSE/DO NOT CLOSE/REFUSE all verified, "
          "including the two/four-verdict, duplicate-f_min, ROW_0/ROW_0d, "
          "malformed-file, missing-file, band/f_max/wav_dir (E1), "
          "baseline-SHA/manifest-digest (E2) refusal paths, and every exit "
          "code (E3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
