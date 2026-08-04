#!/usr/bin/env python3
"""Task 5 -- PRE-REGISTERED RULE (commit before running either arm, HK-021).

Executes
`qa/cycleframer-alignment-replay/2026-08-04-1441-architect-to-qa-spec-isolated-replay-rerun-post-drift-fix.md`
Sec.3.

recovery_X = (Isolated-class live misses that decode on replay) / (Isolated-class live misses
tried), per arm, aggregated over both SNR strata. Tried/decoded counts come from
run_isolated_replay_generic.py's output; the drawn sample is a seeded random permutation of the
full isolated-class population, consumed sequentially, so the ratio over the tried subsample is
an unbiased estimator of the ratio over the full population regardless of early stopping (order
is independent of content).

Population size (for ROW 1) comes from materialise_isolated_sample_generic.py's
`population_totals.total` -- the FULL isolated-class population, not the drawn/tried subsample.

r = recovery_B / recovery_A.

PRE-REGISTERED RULE, strict order, first match wins, mutually exclusive:

| row | condition                                              | consequence |
|-----|---------------------------------------------------------|-------------|
| 1 VOID | either arm has < 200 Isolated-class live misses (population) | no verdict; report counts and stop |
| 2 VOID | arm A's corpus does NOT fire ROW 2 FAIL on drift_screen.py    | wrong corpus for positive control; no verdict |
| 3 VOID | recovery_A < 0.10                                              | instrument cannot reproduce the effect; no contrast interpretable |
| 4 STRONG  | r <= 0.333                                                  | drift accounted for MOST of the live-path loss; fix validated |
| 5 PARTIAL | 0.333 < r <= 0.667                                          | drift accounted for PART of it; second mechanism comparable in size |
| 6 NULL    | r > 0.667                                                   | live-path loss largely NOT drift; escalate |

Usage:
    python evaluate_rule.py --arm-a-population <json> --arm-a-results <json>
        --arm-b-population <json> --arm-b-results <json> --arm-a-drift-row "ROW 2 -- FAIL"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS
# ---------------------------------------------------------------------------
MIN_POPULATION = 200
VOID_RECOVERY_A_FLOOR = 0.10
STRONG_R_BAR = 0.333
PARTIAL_R_BAR = 0.667


def recovery_rate(results_path: Path) -> tuple[float, int, int]:
    data = json.loads(results_path.read_text(encoding="utf-8"))
    tried_total = 0
    decoded_total = 0
    for band, b in data["results"].items():
        tried_total += b["tried"]
        decoded_total += b["decoded_on_replay"]
    if tried_total == 0:
        return float("nan"), 0, 0
    return decoded_total / tried_total, decoded_total, tried_total


def population_size(population_json_path: Path) -> int:
    data = json.loads(population_json_path.read_text(encoding="utf-8"))
    return data["population_totals"]["total"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm-a-population", required=True, type=Path)
    ap.add_argument("--arm-a-results", type=Path, help="omit if arm A has not been run yet")
    ap.add_argument("--arm-b-population", type=Path)
    ap.add_argument("--arm-b-results", type=Path)
    ap.add_argument("--arm-a-drift-row", required=True,
                    help="the row string drift_screen.py reported for arm A's corpus, "
                         "e.g. 'ROW 2 -- FAIL'")
    args = ap.parse_args()

    print("=" * 78)
    print("TASK 5 -- pre-registered rule evaluation")
    print("=" * 78 + "\n")

    n_a = population_size(args.arm_a_population)
    print(f"Arm A population (Isolated-class live misses): {n_a}")

    n_b = None
    if args.arm_b_population:
        n_b = population_size(args.arm_b_population)
        print(f"Arm B population (Isolated-class live misses): {n_b}")

    if n_a < MIN_POPULATION or (n_b is not None and n_b < MIN_POPULATION):
        print(f"\nROW 1 -- VOID: population under {MIN_POPULATION} "
              f"(arm A={n_a}, arm B={n_b}). NO VERDICT. Report and stop.")
        return 1

    print(f"\nArm A drift_screen.py row: '{args.arm_a_drift_row}'")
    if not args.arm_a_drift_row.strip().upper().startswith("ROW 2"):
        print("\nROW 2 -- VOID: arm A's corpus did not fire ROW 2 FAIL. Wrong corpus for the "
              "positive control. NO VERDICT.")
        return 1

    if args.arm_a_results is None:
        print("\n[stop here] Arm A has not been replayed yet. Run arm A first; only proceed to "
              "arm B if this does not VOID.")
        return 0

    recovery_a, dec_a, tried_a = recovery_rate(args.arm_a_results)
    print(f"\nrecovery_A = {dec_a}/{tried_a} = {recovery_a:.4f}")

    if recovery_a < VOID_RECOVERY_A_FLOOR:
        print(f"\nROW 3 -- VOID: recovery_A ({recovery_a:.4f}) < {VOID_RECOVERY_A_FLOOR}. "
              "The instrument cannot reproduce the effect it exists to measure. "
              "NO CONTRAST IS INTERPRETABLE. Do not run arm B (or disregard if already run).")
        return 1

    if args.arm_b_results is None:
        print("\n[stop here] Arm A cleared rows 1-3. Proceed to arm B.")
        return 0

    recovery_b, dec_b, tried_b = recovery_rate(args.arm_b_results)
    print(f"recovery_B = {dec_b}/{tried_b} = {recovery_b:.4f}")

    r = recovery_b / recovery_a
    print(f"\nr = recovery_B / recovery_A = {recovery_b:.4f} / {recovery_a:.4f} = {r:.4f}")

    if r <= STRONG_R_BAR:
        print(f"\nROW 4 -- STRONG (r={r:.4f} <= {STRONG_R_BAR})")
        print("Drift accounted for MOST of the live-path loss. The fix is validated on the "
              "live path.")
        return 0
    if r <= PARTIAL_R_BAR:
        print(f"\nROW 5 -- PARTIAL ({STRONG_R_BAR} < r={r:.4f} <= {PARTIAL_R_BAR})")
        print("Drift accounted for PART of it. A second pre-decoder mechanism stands, and is "
              "comparable in size.")
        return 0
    print(f"\nROW 6 -- NULL (r={r:.4f} > {PARTIAL_R_BAR})")
    print("The live-path loss is largely NOT drift. Escalate -- a named second mechanism "
          "becomes the priority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
