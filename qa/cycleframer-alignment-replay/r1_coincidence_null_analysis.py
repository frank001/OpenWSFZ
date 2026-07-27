#!/usr/bin/env python3
"""D-001 R.1 -- the coincidence null (2026-07-27-r1-coincidence-null-task-spec.md).

Does "a candidate exists within +-10 Hz / +-0.5 s of a WSJT-X-reported message" measure
detection, or the density of our own candidate set? Purely offline against C.4's already-
committed frozen artefacts -- no decode run, no rebuild. Reuses c4_min_score_sweep_analysis.py's
own matching machinery (compute_648_population, load_candidate_diag, has_any_candidate_nearby)
rather than reinventing it.

Two comparison conditions, each against the K=10@600 ("k10") and K=4@2000 ("k4_cap2000") settings:

  1. Frequency-displaced null: displace each of the 648 targets' WSJT-X frequency by
     delta in {+-150,+-300,+-450,+-600} Hz (wrapped inside 200-3000 Hz), keep dt/cycle, re-match
     at the published tolerance (+-10 Hz / +-0.5 s).
  2. Tolerance ladder: re-match the TRUE (undisplaced) 648 at freq tolerances
     {10, 5, 3.125, 1.5625} Hz crossed with dt tolerances {0.5, 0.16, 0.08} s.

ASCII-only console output (HK-009). NFR-021: aggregate stats only, no callsigns/messages printed.
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
import c4_min_score_sweep_analysis as c4  # noqa: E402  (reuse, not reinvent)

BAND_LO = 200.0
BAND_HI = 3000.0
BAND_WIDTH = BAND_HI - BAND_LO  # 2800.0

DELTAS_HZ = [-600, -450, -300, -150, 150, 300, 450, 600]
FREQ_TOLS = [10.0, 5.0, 3.125, 1.5625]
DT_TOLS = [0.5, 0.16, 0.08]

SETTINGS = [
    ("k10 (K=10@600)", os.path.join(c4.BASE, "c4_min_score", "k10", "k10_c0.10_n60")),
    ("k4_cap2000 (K=4@2000)", os.path.join(c4.BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60")),
]


def wrap_freq(freq: float, delta: float) -> float:
    return BAND_LO + ((freq - BAND_LO + delta) % BAND_WIDTH)


def has_any_candidate_nearby_tol(freq: float, dt: float, cands: list[dict],
                                  freq_tol: float, dt_tol: float) -> bool:
    for c in cands:
        if abs(c["freq_hz"] - freq) <= freq_tol and abs(c["dt"] - dt) <= dt_tol:
            return True
    return False


def recov_rate(population: list[dict], cand_by_cycle: dict[str, list[dict]],
                freq_key: str, freq_tol: float, dt_tol: float) -> tuple[int, float]:
    n = len(population)
    if n == 0:
        return 0, 0.0
    hits = 0
    for row in population:
        cands = cand_by_cycle.get(row["ts"], [])
        if has_any_candidate_nearby_tol(row[freq_key], row["dt"], cands, freq_tol, dt_tol):
            hits += 1
    return hits, 100.0 * hits / n


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(c4.WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} matched cycles\n")

    population_648 = c4.compute_648_population(cycles)
    n648 = len(population_648)
    print(f"\nR.1 self-check: population_648 size = {n648} (expect 648, matching C.3's published count)\n")
    if n648 != 648:
        print("[SELF-CHECK FAILED] population size does not match C.3's published 648 -- "
              "stopping per design doc Sec.6 stop rule. Do not trust anything below.", file=sys.stderr)

    for label, out_dir in SETTINGS:
        diag_csv_path = os.path.join(out_dir, "candidate_diag.csv")
        cand_by_cycle = c4.load_candidate_diag(diag_csv_path)

        print("=" * 78)
        print(f"SETTING: {label}")
        print("=" * 78)

        # ---- Condition 1: frequency-displaced null vs. true, at published tolerance ----
        true_hits, true_pct = recov_rate(population_648, cand_by_cycle, "freq", 10.0, 0.5)
        print(f"\n[Condition 1] Frequency-displaced null (tolerance fixed at +-10 Hz / +-0.5 s)")
        print(f"  TRUE (undisplaced): recov648 = {true_hits}/{n648} = {true_pct:.1f}%")

        null_pcts = []
        for delta in DELTAS_HZ:
            displaced = [{**row, "freq_disp": wrap_freq(row["freq"], delta)} for row in population_648]
            hits, pct = recov_rate(displaced, cand_by_cycle, "freq_disp", 10.0, 0.5)
            null_pcts.append(pct)
            print(f"  delta={delta:+5d} Hz: recov648 = {hits}/{n648} = {pct:.1f}%")

        null_mean = sum(null_pcts) / len(null_pcts)
        print(f"  null mean across 8 displacements: {null_mean:.1f}%  "
              f"(true - null_mean = {true_pct - null_mean:+.1f} pts)")

        # ---- Condition 2: tolerance ladder, true population only ----
        print(f"\n[Condition 2] Tolerance ladder (true/undisplaced population)")
        header = f"  {'freq_tol_Hz':>11}" + "".join(f"{'dt<=' + str(dt):>12}" for dt in DT_TOLS)
        print(header)
        for ft in FREQ_TOLS:
            row_cells = []
            for dt in DT_TOLS:
                hits, pct = recov_rate(population_648, cand_by_cycle, "freq", ft, dt)
                row_cells.append(f"{pct:>10.1f}%")
            print(f"  {ft:>11}" + "".join(f"{c:>12}" for c in row_cells))
        print()

    print("=" * 78)
    print("Reading rule (design doc Sec.4, R.1 table) -- apply to Condition 1's true-vs-null gap "
          "at K=4@2000 primarily, cross-checked against K=10@600 and Condition 2's convergence "
          "behaviour. See task spec Sec.3 for the full three-row table.")


if __name__ == "__main__":
    main()
