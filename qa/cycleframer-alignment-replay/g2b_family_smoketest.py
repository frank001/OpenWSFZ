#!/usr/bin/env python3
"""Smoke test for g2b_family.py (D2, 2026-08-12, fourth Architect review).

Required by the Architect's D2 finding
(`2026-08-12-2052-architect-to-qa-g2b-review-4.md`): "Smoke-test the family
adjudicator: all-ROW_3 -> CLOSE; one ROW_1 -> DO NOT CLOSE; two verdicts ->
refuse; duplicate f_min -> refuse; any ROW_0 -> refuse." Every one of those
five is exercised below, plus two extra fail-closed checks (four verdicts,
malformed verdict file) added on the same "REFUSE, do not guess" discipline
C2/C4 already established elsewhere in this chain, and a direct check that
the adjudicator never prints anything that reads as a recommendation among
eligible rungs (the deliberate asymmetry D2 specified).

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
                   "churn_gross_max_rate": 0.02}}
    v.update(extra)
    path = tmp / name
    path.write_text(json.dumps(v))
    return path


def run_family(*paths):
    cmd = [sys.executable, str(FAMILY)]
    for p in paths:
        cmd += ["--verdict", str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def main():
    print("=" * 78)
    print("g2b_family.py smoke test -- D2, 2026-08-12 (fourth Architect review)")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ── CLOSE -- all three rungs read ROW_3 ──────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out = run_family(v180, v140, v100)
        check("all-ROW_3 -> CLOSE", "CLOSE --" in out and "DO NOT CLOSE" not in out
              and "REFUSE" not in out, out)

        # ── DO NOT CLOSE -- one rung reads ROW_1 ─────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_1")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out = run_family(v180, v140, v100)
        # NOTE: "CLOSE --" is a substring of "DO NOT CLOSE --", so the check
        # below tests for the ABSENCE of a bare "\n  CLOSE --" line instead of
        # naively excluding "CLOSE --" (which would always be present here).
        check("one ROW_1 -> DO NOT CLOSE, names the rung", "DO NOT CLOSE --" in out
              and "f_min=140 read ROW_1" in out
              and "\n  CLOSE --" not in out and "REFUSE" not in out, out)

        # ── DO NOT CLOSE -- one rung reads ROW_2, named alongside a ROW_1 ────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_2")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_1")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out = run_family(v180, v140, v100)
        check("ROW_2 + ROW_1 both named, ROW_3 rung not named as a problem",
              "f_min=180 read ROW_2" in out and "f_min=140 read ROW_1" in out
              and "f_min=100 read ROW_3" not in out, out)

        # ── REFUSE -- two verdicts only, not three ───────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out = run_family(v180, v140)
        check("two verdicts -> REFUSE", "REFUSE --" in out and "need exactly 3" in out, out)

        # ── REFUSE -- four verdicts, also not three ──────────────────────────
        v100b = make_verdict(tmp, "v100b.json", "20m", 60, 3030, "ROW_3")
        out = run_family(v180, v140, v100, v100b)
        check("four verdicts -> REFUSE", "REFUSE --" in out and "need exactly 3" in out, out)

        # ── REFUSE -- duplicate f_min ─────────────────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140a = make_verdict(tmp, "v140a.json", "20m", 140, 3030, "ROW_3")
        v140b = make_verdict(tmp, "v140b.json", "20m", 140, 3030, "ROW_1")
        out = run_family(v180, v140a, v140b)
        check("duplicate f_min -> REFUSE", "REFUSE --" in out
              and "share an f_min" in out, out)

        # ── REFUSE -- any verdict reads ROW_0 ────────────────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_0",
                             scope=None, p1_fired=None, rates=None, bounds=None)
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out = run_family(v180, v140, v100)
        check("any ROW_0 -> REFUSE", "REFUSE --" in out
              and "NO READ, not evidence" in out
              and "f_min=140, ROW_0" in out, out)

        # ── REFUSE -- any verdict reads ROW_0d (gate defect, not ROW_0) ──────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_0d")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_3")
        out = run_family(v180, v140, v100)
        check("any ROW_0d -> REFUSE", "REFUSE --" in out
              and "f_min=140, ROW_0d" in out, out)

        # ── REFUSE -- a malformed verdict file (missing required keys) ──────
        bad = tmp / "bad.json"
        bad.write_text(json.dumps({"band": "20m", "row": "ROW_3"}))  # no f_min/f_max
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out = run_family(v180, v140, bad)
        check("malformed verdict (missing f_min/f_max) -> REFUSE",
              "REFUSE --" in out and "missing" in out, out)

        # ── REFUSE -- a verdict path that does not exist ─────────────────────
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_3")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_3")
        out = run_family(v180, v140, tmp / "does_not_exist.json")
        check("missing verdict file -> REFUSE, no traceback",
              "REFUSE --" in out and "could not read verdict" in out
              and "Traceback" not in out, out)

        # ── D2's deliberate asymmetry: never a recommendation among eligible
        # (ROW_1) rungs, even when the family stays open with more than one
        # ROW_1 rung.
        v180 = make_verdict(tmp, "v180.json", "20m", 180, 3030, "ROW_1")
        v140 = make_verdict(tmp, "v140.json", "20m", 140, 3030, "ROW_1")
        v100 = make_verdict(tmp, "v100.json", "20m", 100, 3030, "ROW_2")
        out = run_family(v180, v140, v100)
        check("DO NOT CLOSE with two ROW_1 rungs never recommends one",
              "DO NOT CLOSE --" in out
              and "recommend" not in out.lower()
              and "choose" not in out.lower(), out)

    print()
    print("=" * 78)
    if FAILURES:
        print(f"SMOKE TEST FAILED -- {len(FAILURES)} check(s) did not hold:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("SMOKE TEST PASSED -- CLOSE/DO NOT CLOSE/REFUSE all verified, "
          "including the two/four-verdict, duplicate-f_min, ROW_0/ROW_0d, "
          "malformed-file and missing-file refusal paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
