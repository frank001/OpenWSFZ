#!/usr/bin/env python3
"""T4 / Angle 1 -- step 2: N3 instrument calibration.

Runs jt9 over WSJT-X's OWN WAVs (wsjt-x/wav/<ts>.wav) for the +0s population cycles
(qa/cycleframer-alignment-replay/_work/angle1_population.json, built by
measurement_angle1_population.py) and compares the resulting decode count against
WSJT-X's own live ALL.TXT count on the identical population -- the N3 mandatory null from
the 2026-08-02-1813 pre-registration section 5:

    N3  INSTRUMENT: jt9 must be calibrated against live WSJT-X before leg B is
                   comparable to leg C. Run jt9 over WSJT-X's OWN WAVs for the same
                   cycles; it must reproduce WSJT-X's live count within +/-5%.
                   NOT isfinite(|jt9(WSJTX wav) - C| / C)   => VOID.
                   |jt9(WSJTX wav) - C| / C > 0.05          => VOID.

jt9's raw decode output is written as an ALL.TXT-format file into
artefacts/20260731_live_run_2004-8080/wsjt-x/ alongside the ALL.TXT it is compared
against (Captain's 2026-07-30 instruction, and repeated mid-turn 2026-08-03: raw re-decode
output belongs in the artefact folder, not discarded once stats are computed).

N4 (jt9 output carries zero duplicate (ts, message) pairs) is also checked here, since it
is evaluated on this same jt9 output.

Usage: python measurement_angle1_n3_calibration.py [--jt9-depth 3] [--limit N]
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
import anova_common as ac  # noqa: E402
import endurance_anova_jt9 as eaj  # noqa: E402

CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts",
                       "20260731_live_run_2004-8080")
WSJTX_ALL_TXT = os.path.join(CORPUS, "wsjt-x", "ALL.TXT")
WSJTX_WAV_DIR = os.path.join(CORPUS, "wsjt-x", "wav")
WSJTX_JT9_OUT = os.path.join(CORPUS, "wsjt-x", "jt9_ALL_n3_calibration.TXT")

POP_JSON = os.path.join(os.path.dirname(__file__), "_work", "angle1_population.json")
OUT_JSON = os.path.join(os.path.dirname(__file__), "_work", "angle1_n3_result.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jt9-depth", type=int, default=3)
    ap.add_argument("--jt9-exe", default=eaj.DEFAULT_JT9_EXE)
    ap.add_argument("--limit", type=int, default=None,
                     help="Only use the first N population cycles (smoke test)")
    ap.add_argument("--max-workers", type=int, default=None)
    args = ap.parse_args()

    with open(POP_JSON, encoding="utf-8") as fh:
        pop_data = json.load(fh)
    population = pop_data["population"]
    if args.limit is not None:
        population = population[:args.limit]
    print(f"N3 population size: {len(population)}")

    wav_paths = [os.path.join(WSJTX_WAV_DIR, f"{ts}.wav") for ts in population]
    missing = [p for p in wav_paths if not os.path.isfile(p)]
    if missing:
        print(f"[ERROR] {len(missing)} population WAVs missing from {WSJTX_WAV_DIR}, "
              f"e.g. {missing[:3]}", file=sys.stderr)
        return 2

    print(f"running jt9 (-d {args.jt9_depth}) over {len(wav_paths)} WSJT-X WAVs "
          f"(N3 calibration)...")
    jt9_rows = eaj.run_jt9(args.jt9_exe, wav_paths, args.jt9_depth,
                            max_workers=args.max_workers)
    print(f"jt9 decode lines: {len(jt9_rows)}")

    # N4: zero duplicate (ts, message) pairs in jt9's own output.
    seen = set()
    dup_count = 0
    for r in jt9_rows:
        key = (r["ts"], ac.normalize_hash_tokens(r["message"]))
        if key in seen:
            dup_count += 1
        seen.add(key)
    n4_pass = dup_count == 0
    print(f"N4 (dedup on N3's jt9 output): {dup_count} duplicate pairs -> "
          f"{'PASS' if n4_pass else 'VOID'}")

    # Write jt9's raw decode output into the artefact folder, ALL.TXT-format, per
    # convention (endurance_anova_jt9.write_jt9_all_txt) and the Captain's instruction.
    dial_mhz = eaj.extract_dial_mhz(WSJTX_ALL_TXT)
    eaj.write_jt9_all_txt(jt9_rows, dial_mhz, WSJTX_JT9_OUT)

    # C on this same population, for the calibration check.
    wsjtx_rows = ac.parse_all_txt(WSJTX_ALL_TXT)
    pop_set = set(population)
    c_rows = [r for r in wsjtx_rows if r["ts"] in pop_set]
    c_count = len(c_rows)
    jt9_count = len(jt9_rows)
    print(f"WSJT-X live count (C) on population: {c_count}")
    print(f"jt9(WSJT-X wav) count on population: {jt9_count}")

    if c_count == 0:
        rel_diff = float("nan")
    else:
        rel_diff = abs(jt9_count - c_count) / c_count

    # Mechanical evaluation, per the prereg's own literal form, non-finite guard first.
    if not math.isfinite(rel_diff):
        n3_verdict = "VOID"
        n3_reason = "NOT isfinite(rel_diff) -- degenerate denominator (C == 0)"
    elif rel_diff > 0.05:
        n3_verdict = "VOID"
        n3_reason = f"|jt9 - C| / C = {rel_diff:.4f} > 0.05"
    else:
        n3_verdict = "PASS"
        n3_reason = f"|jt9 - C| / C = {rel_diff:.4f} <= 0.05"
    print(f"N3 verdict: {n3_verdict} ({n3_reason})")

    out = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jt9_depth": args.jt9_depth,
        "n_population": len(population),
        "n4_dup_count": dup_count,
        "n4_verdict": "PASS" if n4_pass else "VOID",
        "c_count": c_count,
        "jt9_wsjtx_count": jt9_count,
        "rel_diff": rel_diff,
        "n3_verdict": n3_verdict,
        "n3_reason": n3_reason,
        "jt9_all_txt_path": WSJTX_JT9_OUT,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
