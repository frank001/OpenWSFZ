#!/usr/bin/env python3
"""D-001 R.1b -- the unfilled cell: empirical null across the TIGHT tolerance ladder
(2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md Sec.5).

R.1's Condition 1 (frequency-displaced null) was only ever measured at the published
+-10 Hz / +-0.5 s tolerance. R.1's Condition 2 (tolerance ladder) was only ever measured on the
TRUE population. Neither computed the null AT the tight tolerances -- the one cell that
distinguishes "detection is imprecise" (true separates from null at some tolerance) from
"detection carries no location information" (true == null everywhere) from "anti-correlation"
(true < null at tight tolerance), per the 19:00 note's reading table.

Purely offline against the same C.4 frozen artefacts R.1 used -- no decode run, no rebuild, no
new instrument. Reuses c4_min_score_sweep_analysis.py's matching machinery and
r1_coincidence_null_analysis.py's displacement/wrap logic verbatim.

ASCII-only console output (HK-009). NFR-021: aggregate stats only, no callsigns/messages printed.
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
import c4_min_score_sweep_analysis as c4  # noqa: E402
import r1_coincidence_null_analysis as r1  # noqa: E402  (wrap_freq, DELTAS_HZ, SETTINGS, etc.)

FREQ_TOLS = r1.FREQ_TOLS   # [10.0, 5.0, 3.125, 1.5625]
DT_TOLS = r1.DT_TOLS       # [0.5, 0.16, 0.08]
DELTAS_HZ = r1.DELTAS_HZ   # [-600,-450,-300,-150,150,300,450,600]


def true_and_null_rate(population: list[dict], cand_by_cycle: dict[str, list[dict]],
                        freq_tol: float, dt_tol: float) -> tuple[float, float, list[float]]:
    n = len(population)
    _, true_pct = r1.recov_rate(population, cand_by_cycle, "freq", freq_tol, dt_tol)

    null_pcts = []
    for delta in DELTAS_HZ:
        displaced = [{**row, "freq_disp": r1.wrap_freq(row["freq"], delta)} for row in population]
        _, pct = r1.recov_rate(displaced, cand_by_cycle, "freq_disp", freq_tol, dt_tol)
        null_pcts.append(pct)
    null_mean = sum(null_pcts) / len(null_pcts)
    return true_pct, null_mean, null_pcts


def classify(true_pct: float, null_mean: float, null_pcts: list[float]) -> str:
    """Rough per-cell signpost only -- the written verdict applies the 19:00 note's table by hand
    against the full picture, not this function alone."""
    null_max = max(null_pcts)
    null_min = min(null_pcts)
    spread = null_max - null_min
    # "a few points" tolerance, consistent with R.1's own row-1 read (4.5 pts on a 90.8% base)
    band = max(3.0, 0.5 * spread)
    if true_pct < null_mean - band:
        return "BELOW null (anti-correlation candidate)"
    if true_pct > null_mean + band:
        return "ABOVE null (separation candidate)"
    return "~= null"


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(c4.WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} matched cycles\n")

    population_648 = c4.compute_648_population(cycles)
    n648 = len(population_648)
    print(f"\nR.1b self-check: population_648 size = {n648} (expect 648)\n")
    if n648 != 648:
        print("[SELF-CHECK FAILED] stopping per stop rule -- do not trust anything below.",
              file=sys.stderr)
        return

    for label, out_dir in r1.SETTINGS:
        diag_csv_path = os.path.join(out_dir, "candidate_diag.csv")
        cand_by_cycle = c4.load_candidate_diag(diag_csv_path)

        print("=" * 90)
        print(f"SETTING: {label}")
        print("=" * 90)
        header = f"  {'freq_tol_Hz':>11} {'dt_tol_s':>9} {'TRUE%':>8} {'null_mean%':>11} {'true-null':>10}  {'null_min-max':>14}  verdict"
        print(header)
        for ft in FREQ_TOLS:
            for dt in DT_TOLS:
                true_pct, null_mean, null_pcts = true_and_null_rate(population_648, cand_by_cycle, ft, dt)
                verdict = classify(true_pct, null_mean, null_pcts)
                print(f"  {ft:>11} {dt:>9} {true_pct:>7.1f}% {null_mean:>10.1f}% "
                      f"{true_pct - null_mean:>+9.1f}  "
                      f"{min(null_pcts):>5.1f}-{max(null_pcts):>5.1f}%  {verdict}")
        print()

    print("=" * 90)
    print("Reading rule (2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md Sec.5):")
    print("  true ~= null at every tolerance, both settings -> no location information at all")
    print("        (detection failure total, not imprecise). Row-4 target = sync detector/metric.")
    print("  true materially BELOW null at tight tolerance -> anti-correlation. Detector")
    print("        systematically does not fire where these signals are.")
    print("  true separates ABOVE null at some tolerance tau -> imprecise detection; tau sizes R.2's grid.")


if __name__ == "__main__":
    main()
