#!/usr/bin/env python3
"""T4 / Angle 1 -- step 1: define the +0s population and pull legs A and C.

Per the 2026-08-02-1813 pre-registration (AUTHORISED 2026-08-02 23:45 UTC), population is
"cycles present in all three legs, offset == 0 on 8080, both 8080 segments pooled." The
prereg does not spell out the exact mechanics of "present in all three legs" -- it hands
that to QA (its own T1 note: "the population of record is yours to set with
apply_grid_snap"). This script makes the definition explicit and mechanical, per HK-021:

    A cycle timestamp `ts` is in the population iff:
      1. `ts` names a WAV file physically on disk in 8080's own WAV archive
         (owsfz/wav/<ts>.wav) -- WAV capture happens every cycle regardless of decode
         count, so this is the correct "did this cycle actually occur and get captured"
         signal, not owsfz/ALL.TXT (which only lists cycles with >=1 decode and would
         silently drop legitimate zero-decode cycles from the population).
      2. `ts_offset_seconds(ts) == 0` -- the +0s (drift-free) stratum, evaluated on the
         RAW filename timestamp (offset==0 means raw==snapped, so no snap is needed on
         the 8080 side for population membership).
      3. `ts` also names a WAV file physically on disk in WSJT-X's own WAV archive
         (wsjt-x/wav/<ts>.wav) -- evidence the same nominal UTC cycle was independently
         captured by the WSJT-X-side chain too (WSJT-X's own G gate is 0.9984-1.0000, so
         raw==snapped is expected to hold there as well; this is checked, not assumed).

Leg A = 8080's own decode count (owsfz/ALL.TXT) on the population.
Leg C = WSJT-X's live decode count (wsjt-x/ALL.TXT) on the population.
Leg B (jt9 re-decode of 8080's own WAVs) is intentionally NOT computed here -- it needs a
jt9 pass, done in a later step only after N3 (instrument calibration) has passed.

"Both 8080 segments pooled" (prereg's own phrase, referencing the 1702 note's Section 2):
the +0s population as defined above is a single set over the whole 43.6h corpus and
naturally spans both of 8080's restart segments -- no separate pooling step is needed
because population membership is evaluated per-cycle, not per-segment.

Usage: python measurement_angle1_population.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
import anova_common as ac  # noqa: E402

CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts",
                       "20260731_live_run_2004-8080")
OWSFZ_ALL_TXT = os.path.join(CORPUS, "owsfz", "ALL.TXT")
OWSFZ_WAV_DIR = os.path.join(CORPUS, "owsfz", "wav")
WSJTX_ALL_TXT = os.path.join(CORPUS, "wsjt-x", "ALL.TXT")
WSJTX_WAV_DIR = os.path.join(CORPUS, "wsjt-x", "wav")

OUT_JSON = os.path.join(os.path.dirname(__file__), "_work", "angle1_population.json")


def main() -> int:
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

    owsfz_wav_ts = {os.path.splitext(f)[0] for f in os.listdir(OWSFZ_WAV_DIR)
                     if f.lower().endswith(".wav")}
    wsjtx_wav_ts = {os.path.splitext(f)[0] for f in os.listdir(WSJTX_WAV_DIR)
                     if f.lower().endswith(".wav")}
    print(f"8080 owsfz WAVs on disk: {len(owsfz_wav_ts)}")
    print(f"WSJT-X wav on disk: {len(wsjtx_wav_ts)}")

    plus0s = {ts for ts in owsfz_wav_ts if ac.ts_offset_seconds(ts) == 0}
    print(f"8080 WAVs with offset==0 (raw==snapped): {len(plus0s)}")

    population = sorted(plus0s & wsjtx_wav_ts)
    dropped_no_wsjtx_wav = sorted(plus0s - wsjtx_wav_ts)
    print(f"population (+0s AND WSJT-X wav present): {len(population)}")
    print(f"+0s cycles dropped for lacking a WSJT-X wav: {len(dropped_no_wsjtx_wav)}")
    if dropped_no_wsjtx_wav:
        print(f"  first few: {dropped_no_wsjtx_wav[:5]}")
        print(f"  last few: {dropped_no_wsjtx_wav[-5:]}")

    pop_set = set(population)

    owsfz_rows = ac.parse_all_txt(OWSFZ_ALL_TXT)
    wsjtx_rows = ac.parse_all_txt(WSJTX_ALL_TXT)
    print(f"owsfz ALL.TXT rows (whole corpus): {len(owsfz_rows)}")
    print(f"wsjt-x ALL.TXT rows (whole corpus): {len(wsjtx_rows)}")

    leg_a_rows = [r for r in owsfz_rows if r["ts"] in pop_set]
    leg_c_rows = [r for r in wsjtx_rows if r["ts"] in pop_set]
    print(f"leg A (8080 own decodes on population): {len(leg_a_rows)}")
    print(f"leg C (WSJT-X live decodes on population): {len(leg_c_rows)}")

    pop_cycles_with_a = len({r["ts"] for r in leg_a_rows})
    pop_cycles_with_c = len({r["ts"] for r in leg_c_rows})
    print(f"population cycles contributing >=1 decode to A: {pop_cycles_with_a} / {len(population)}")
    print(f"population cycles contributing >=1 decode to C: {pop_cycles_with_c} / {len(population)}")

    # N1 prep: match leg A against itself.
    self_pairs = ac.match_pairs(leg_a_rows, leg_a_rows)
    n1_recall = len(self_pairs) / len(leg_a_rows) if leg_a_rows else float("nan")
    print(f"N1 self-match recall: {n1_recall!r} ({len(self_pairs)}/{len(leg_a_rows)})")

    # N2 prep: grid gate on the analysed subset, computed on RAW ts (per compute_grid_gate's
    # own docstring: "evaluated on RAW (pre-snap) rows"). All three of these ARE already
    # on-grid by construction (population membership requires it), so this should read
    # G == 1.0000 for A and C's population-restricted rows -- a check that the population
    # definition itself is coherent, not just decoration.
    gate_a = ac.compute_grid_gate(leg_a_rows)
    gate_c = ac.compute_grid_gate(leg_c_rows)
    gate_pop = ac.compute_grid_gate([{"ts": ts} for ts in population])
    print(f"N2 grid gate, leg A rows: {gate_a}")
    print(f"N2 grid gate, leg C rows: {gate_c}")
    print(f"N2 grid gate, population itself: {gate_pop}")

    out = {
        "population": population,
        "n_population": len(population),
        "dropped_no_wsjtx_wav": dropped_no_wsjtx_wav,
        "leg_a_n": len(leg_a_rows),
        "leg_c_n": len(leg_c_rows),
        "n1_recall": n1_recall,
        "gate_a": gate_a,
        "gate_c": gate_c,
        "gate_population": gate_pop,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
