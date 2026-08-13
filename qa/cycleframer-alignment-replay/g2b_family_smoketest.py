#!/usr/bin/env python3
"""Smoke test for g2b_family.py (D2, 2026-08-12, fourth Architect review;
extended for E1/E2/E3, 2026-08-12 21:43Z early candidates, folded into
revision 5; extended again for REVISION 6, 2026-08-13, fifth Architect
review plus the Captain's rulings).

REVISION 6 additions (J1, J2/F7, F8, F9, J5, J6):
  J1  ROW_INDETERMINATE (the new row g2b_gate.py's J1 fix introduces for an
      underpowered rung) must REFUSE exactly like ROW_0/ROW_0d -- both a
      single occurrence and a same-row control (all three
      ROW_INDETERMINATE) are exercised, so this cannot silently be read as
      an all-ROW_3 CLOSE.
  J2/F7  make_verdict() now defaults `bars` to
      family.PRE_REGISTERED_BARS[f_min] (imported directly, not re-typed)
      instead of one hard-coded dict every f_min used to share -- the OLD
      default happened to equal rung 140's real bars, which would have made
      every v180/v100 fixture in this file spuriously trip F7 the moment it
      was added. All four bar fields are exercised independently.
  F8  window/start_cycle mismatch (absorbs J3): two rungs may share one
      wav_dir (F5) yet run on different slices of it.
  F9  gate_sha256 mismatch: three rungs must have been read by the SAME
      evaluator.
  J5  burned_corpus joins F5's identity set: two rungs may share one
      wav_dir yet disagree on whether it was DECLARED burned.
  J6  a baseline dll_sha256=None must REFUSE without raising (the mirror
      case of the pre-existing manifest_sha256=None check) -- and the null
      text for BOTH is now the shared 'MISSING', not the manifest-specific
      'FILE NOT FOUND' REVISION 5 used.

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

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAMILY = HERE / "g2b_family.py"

# REVISION 6: PRE_REGISTERED_BARS is imported directly, not re-typed here --
# F7 checks a verdict's `bars` against this table by f_min, so a fixture
# whose default bars silently drifted from the real constant would make
# every existing v180/v100 test spuriously REFUSE (only the v140 default
# happened to already match by coincidence -- see make_verdict() below).
spec = importlib.util.spec_from_file_location("g2b_family", FAMILY)
family = importlib.util.module_from_spec(spec)
spec.loader.exec_module(family)

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
# REVISION 6 (F8/F9): default slice-identity and evaluator-identity fields.
DEFAULT_WINDOW = ["SMOKETEST_LO", "SMOKETEST_HI"]
DEFAULT_START_CYCLE = 1
DEFAULT_GATE_SHA256 = "f" * 64

EXIT_CLOSE, EXIT_DO_NOT_CLOSE, EXIT_REFUSE = 0, 1, 2


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def make_verdict(tmp, name, band, f_min, f_max, row, **extra):
    """REVISION 6: `bars` defaults to family.PRE_REGISTERED_BARS[f_min] --
    the REAL pre-registered table for whichever rung this verdict claims to
    be, not a single hard-coded dict every f_min used to share. Before F7
    existed that coincidence was harmless (nothing checked bars against
    anything); now a v180/v100 fixture built with rung 140's bars would
    spuriously trip F7 on every single test in this file. A caller
    exercising F7 itself overrides `bars` explicitly via **extra, exactly
    like every other field this function defaults."""
    default_bars = family.PRE_REGISTERED_BARS.get(f_min, {
        "g_new_min_rate": 0.01, "g_high_min_rate": 0.005,
        "churn_net_min_rate": -0.0025, "churn_gross_max_rate": 0.02})
    v = {"band": band, "f_min": f_min, "f_max": f_max, "row": row,
         "scope": "some scope", "p1_fired": False,
         "rates": {"g_low": 0.02, "g_high": 0.01, "churn_net": 0.0,
                    "churn_gross": 0.0},
         "bounds": {"g_low": 0.015, "g_low_hi": 0.025, "g_high": 0.005,
                     "churn_net": -0.001, "churn_gross": 0.005},
         "bars": dict(default_bars),
         "wav_dir": DEFAULT_WAV_DIR,
         "dll_sha256": dict(DEFAULT_DLL_SHA256),
         "manifest_sha256": DEFAULT_MANIFEST_SHA256,
         "burned_corpus": DEFAULT_BURNED_CORPUS,
         "window": list(DEFAULT_WINDOW), "start_cycle": DEFAULT_START_CYCLE,
         "gate_sha256": DEFAULT_GATE_SHA256}
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
    print("g2b_family.py smoke test -- D2 + E1/E2/E3 + REVISION 6 "
          "(J1/J2/F7/F8/F9/J5/J6)")
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

        # ── J1 -- REFUSE: any verdict reads ROW_INDETERMINATE. This is the
        # new row g2b_gate.py's J1 fix introduces (an underpowered rung is
        # not evidence of absence) -- it must be refused on exactly like
        # ROW_0/ROW_0d, the finding this whole review was about: three
        # underpowered ROW_3-that-should-have-been-INDETERMINATE rungs
        # silently CLOSEd the family before this fix existed.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_INDETERMINATE")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("J1: any ROW_INDETERMINATE -> REFUSE, not silently CLOSE",
              "REFUSE --" in out and "f_min=140, ROW_INDETERMINATE" in out
              and "\n  CLOSE --" not in out, out)
        check("J1 ROW_INDETERMINATE -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── J1 control -- three genuine ROW_INDETERMINATE verdicts must NOT
        # silently read as an all-ROW_3 CLOSE either -- the refusal fires on
        # EVERY occurrence, not merely "at least one real row present".
        v180i = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_INDETERMINATE")
        v140i = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_INDETERMINATE")
        v100i = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_INDETERMINATE")
        out, code = run_family(v180i, v140i, v100i)
        check("J1: all three ROW_INDETERMINATE -> REFUSE, not CLOSE",
              "REFUSE --" in out and "\n  CLOSE --" not in out, out)
        check("J1 all-ROW_INDETERMINATE -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

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
        # equal to another None or crash on slicing it. J6 unifies the null
        # formatting across F6's two blocks via _fmt_sha() -- the text is
        # now 'MISSING' (shared with the baseline-SHA block below), not the
        # manifest-specific 'FILE NOT FOUND' REVISION 5 used.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             manifest_sha256=None)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("E2: one manifest_sha256=None -> REFUSE, no traceback",
              "REFUSE --" in out and "MISSING" in out
              and "Traceback" not in out, out)
        check("E2 manifest None -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── J6 -- REFUSE: one rung's baseline dll_sha256 is None (the mirror
        # case of manifest_sha256=None above). Previously `sha[:16]` would
        # have raised TypeError here -- the exact asymmetry J6 fixes, even
        # though this specific input should not reach g2b_family.py in
        # practice (the gate itself dies earlier on a None baseline SHA).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             dll_sha256={"baseline": None, "widened": "d" * 64,
                                          "repeat": "c" * 64})
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("J6: one baseline dll_sha256=None -> REFUSE, no traceback "
              "(previously sha[:16] would have raised TypeError)",
              "REFUSE --" in out and "MISSING" in out
              and "Traceback" not in out, out)
        check("J6 baseline SHA None -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── J2/F7 -- REFUSE: a rung's `bars` do not match the pre-registered
        # ladder table for its own f_min. This is THE finding: one mistyped
        # bar, applied to all three rungs identically, converted a ladder
        # where every rung was eligible into a CLOSEd family before this
        # check existed, and no instrument said a word. Each of the four
        # bar fields is exercised independently, on rung 140 (bar 1.00%),
        # inflated to 50% so it cannot accidentally still match.
        for bar_field in ("g_new_min_rate", "g_high_min_rate",
                           "churn_net_min_rate", "churn_gross_max_rate"):
            v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
            bad_bars = dict(family.PRE_REGISTERED_BARS[140])
            bad_bars[bar_field] = 0.50
            v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                                 bars=bad_bars)
            v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
            out, code = run_family(v180, v140, v100)
            check(f"J2/F7: {bar_field} mismatched against the "
                  f"pre-registered ladder -> REFUSE, not CLOSE",
                  "REFUSE --" in out and bar_field in out
                  and "\n  CLOSE --" not in out, out)
            check(f"J2/F7: {bar_field} mismatch -> exit 2 (E3)",
                  code == EXIT_REFUSE, f"code={code}")

        # ── J2/F7 control -- bars that DO match the pre-registered ladder
        # for EACH rung's own f_min (180/140/100 each have a DIFFERENT
        # g_new_min_rate -- §4.2 of the pre-reg) must NOT trip F7. This is
        # what make_verdict()'s own default now provides for every fixture
        # in this file; this control makes that explicit and checks it does
        # not accidentally regress into a REFUSE.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("J2/F7 control: each rung's OWN pre-registered bars (180 != "
              "140 != 100's g_new_min_rate) do not trip F7 -- CLOSE as normal",
              "CLOSE --" in out and "REFUSE" not in out, out)
        check("J2/F7 control -> exit 0 (E3)", code == EXIT_CLOSE, f"code={code}")

        # ── F8 (absorbs J3) -- REFUSE: window differs across rungs even
        # though wav_dir (F5) is shared. Three rungs may point at one
        # directory and still run on DIFFERENT SLICES of it.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             window=["DIFFERENT_LO", "DIFFERENT_HI"])
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("F8/J3: window mismatch (same wav_dir, different slice) -> "
              "REFUSE, not CLOSE",
              "REFUSE --" in out and "one window" in out
              and "\n  CLOSE --" not in out, out)
        check("F8 window mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── F8 -- REFUSE: start_cycle differs across rungs (same window,
        # different starting point within it).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             start_cycle=251)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("F8: start_cycle mismatch -> REFUSE, not CLOSE",
              "REFUSE --" in out and "one start_cycle" in out
              and "\n  CLOSE --" not in out, out)
        check("F8 start_cycle mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── F9 -- REFUSE: gate_sha256 differs across rungs -- the three
        # rungs were read by DIFFERENT evaluators (g2b_gate.py changed
        # between rungs).
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             gate_sha256="9" * 64)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("F9: gate_sha256 mismatch (different evaluators) -> REFUSE, "
              "not CLOSE",
              "REFUSE --" in out and "DIFFERENT evaluators" in out
              and "\n  CLOSE --" not in out, out)
        check("F9 gate_sha256 mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

        # ── J5 -- REFUSE: burned_corpus differs across rungs even though
        # wav_dir (F5) is shared -- three rungs sharing one directory could
        # previously still disagree on whether that corpus was DECLARED
        # burned, meaning one rung applied the held-out floor and another
        # did not, on the same corpus.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3",
                             burned_corpus="no")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out, code = run_family(v180, v140, v100)
        check("J5: burned_corpus mismatch (same wav_dir) -> REFUSE, not CLOSE",
              "REFUSE --" in out and "one burned_corpus" in out
              and "\n  CLOSE --" not in out, out)
        check("J5 burned_corpus mismatch -> exit 2 (E3)", code == EXIT_REFUSE, f"code={code}")

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
          "including the two/four-verdict, duplicate-f_min, "
          "ROW_0/ROW_0d/ROW_INDETERMINATE (J1), malformed-file, "
          "missing-file, band/f_max/wav_dir/burned_corpus (E1/J5), "
          "baseline-SHA/manifest-digest (E2, null-safe both ways -- J6), "
          "pre-registered-bars (F7/J2, all four fields), window/start_cycle "
          "(F8/J3) and gate_sha256 (F9) refusal paths, and every exit code "
          "(E3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
