#!/usr/bin/env python3
"""T4 / Angle 1 -- step 3: leg B (jt9 re-decode of 8080's OWN +0s WAVs).

Identical audio bytes to leg A (8080's own live decode) -- the whole point of the design
(2026-08-02-1813 pre-registration, section 3): comparing leg A (ours/ours) against leg B
(ours/theirs) isolates the decoder, holding capture framing fixed.

jt9's raw decode output is written as an ALL.TXT-format file into
artefacts/20260731_live_run_2004-8080/owsfz/ alongside the ALL.TXT it is compared against
(Captain's 2026-07-30 instruction, repeated mid-turn 2026-08-03).

N4 (jt9 output carries zero duplicate (ts, message) pairs) is checked here too, since it is
evaluated on this jt9 output as well as N3's.

Usage: python measurement_angle1_legb.py [--jt9-depth 3] [--limit N]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
import anova_common as ac  # noqa: E402
import endurance_anova_jt9 as eaj  # noqa: E402

CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts",
                       "20260731_live_run_2004-8080")
OWSFZ_ALL_TXT = os.path.join(CORPUS, "owsfz", "ALL.TXT")
OWSFZ_WAV_DIR = os.path.join(CORPUS, "owsfz", "wav")
OWSFZ_JT9_OUT = os.path.join(CORPUS, "owsfz", "jt9_ALL_legB.TXT")

POP_JSON = os.path.join(os.path.dirname(__file__), "_work", "angle1_population.json")
OUT_JSON = os.path.join(os.path.dirname(__file__), "_work", "angle1_legb_result.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jt9-depth", type=int, default=3)
    ap.add_argument("--jt9-exe", default=eaj.DEFAULT_JT9_EXE)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-workers", type=int, default=None)
    args = ap.parse_args()

    with open(POP_JSON, encoding="utf-8") as fh:
        pop_data = json.load(fh)
    population = pop_data["population"]
    if args.limit is not None:
        population = population[:args.limit]
    print(f"leg B population size: {len(population)}")

    wav_paths = [os.path.join(OWSFZ_WAV_DIR, f"{ts}.wav") for ts in population]
    missing = [p for p in wav_paths if not os.path.isfile(p)]
    if missing:
        print(f"[ERROR] {len(missing)} population WAVs missing from {OWSFZ_WAV_DIR}, "
              f"e.g. {missing[:3]}", file=sys.stderr)
        return 2

    print(f"running jt9 (-d {args.jt9_depth}) over {len(wav_paths)} 8080 WAVs (leg B)...")
    jt9_rows = eaj.run_jt9(args.jt9_exe, wav_paths, args.jt9_depth,
                            max_workers=args.max_workers)
    print(f"jt9 decode lines: {len(jt9_rows)}")

    seen = set()
    dup_count = 0
    for r in jt9_rows:
        key = (r["ts"], ac.normalize_hash_tokens(r["message"]))
        if key in seen:
            dup_count += 1
        seen.add(key)
    n4_pass = dup_count == 0
    print(f"N4 (dedup on leg B's jt9 output): {dup_count} duplicate pairs -> "
          f"{'PASS' if n4_pass else 'VOID'}")

    dial_mhz = eaj.extract_dial_mhz(OWSFZ_ALL_TXT)
    eaj.write_jt9_all_txt(jt9_rows, dial_mhz, OWSFZ_JT9_OUT)

    out = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jt9_depth": args.jt9_depth,
        "n_population": len(population),
        "leg_b_count": len(jt9_rows),
        "n4_dup_count": dup_count,
        "n4_verdict": "PASS" if n4_pass else "VOID",
        "jt9_all_txt_path": OWSFZ_JT9_OUT,
        "jt9_rows": jt9_rows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
