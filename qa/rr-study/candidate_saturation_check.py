#!/usr/bin/env python3
"""Task 3 (FP spec Sec.5) -- is the candidate budget actually saturated?

PRE-REGISTERED RULE (commit before running; strict order, first match wins):

| row | condition                                              | consequence |
|-----|---------------------------------------------------------|-------------|
| 1 VOID      | candidate counts unavailable, or < 500 cycles carry them | no verdict; report and stop |
| 2 SATURATED | sat_0 >= 0.50                                            | budget is rivalrous => FPs cost real decodes => cap sweep gets priced |
| 3 PARTIAL   | 0.10 <= sat_0 < 0.50                                     | rivalrous in the dense regime only => report sat_0 stratified by decodes/cycle |
| 4 REFUTED   | sat_0 < 0.10                                             | budget not the constraint => Sec.1's hypothesis is dead |

Corpus: artefacts/20260803_live_run_1713/, decisive epoch (the daemon log
openswfz-20260803T185914Z.log, 18.96 h, one process instance = one epoch by construction).

Step 1: search the gathered daemon log for raw LDPC candidate counts. Log lines look like:
    "Iterative subtraction: pass 1 of 2, 140 candidates found, 20 decoded."
    "Iterative subtraction: pass 2 of 2, 200 candidates found, 1 decoded."
pass 1 of 2 == pass-0 (cap 140, ft8_shim.c:467); pass 2 of 2 == pass-1 (cap 200, ft8_shim.c:504).
Each processed cycle emits exactly one pass-1 line immediately followed by one pass-2 line (both
present even at 0 candidates) -- consecutive pairing is used, not timestamp parsing, since the log
carries no cycle-start label, only a wall-clock write time.

NFR-021: reads only candidate/decoded COUNTS from DBG lines -- no message text, no callsigns.
ASCII-only output (HK-009).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

# ---------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS
# ---------------------------------------------------------------------------
MIN_CYCLES_WITH_COUNTS = 500
SATURATED_BAR = 0.50
PARTIAL_LOW_BAR = 0.10

K_MAX_CANDIDATES = 140       # pass 0 / "pass 1 of 2" -- ft8_shim.c:467
K_MAX_CANDIDATES_PASS2 = 200  # pass 1 / "pass 2 of 2" -- ft8_shim.c:504

LOG_PATH = Path("artefacts/20260803_live_run_1713/owsfz/openswfz-20260803T185914Z.log")

LINE_RE = re.compile(
    r"Iterative subtraction: pass (\d) of 2, (\d+) candidates found, (\d+) decoded\.")


def main() -> int:
    log_path = LOG_PATH.resolve()
    print("=" * 78)
    print("TASK 3 -- candidate-budget saturation check")
    print(f"log : {log_path}")
    print("=" * 78 + "\n")

    if not log_path.exists():
        print(f"ROW 1 -- VOID: log not found at {log_path}")
        return 1

    # Walk the log sequentially, pairing each "pass 1" line with the next "pass 2" line.
    cycles = []  # list of (pass0_candidates, pass0_decoded, pass1_candidates, pass1_decoded)
    pending_pass0 = None
    total_lines_matched = 0
    with open(log_path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            total_lines_matched += 1
            pass_no, cand, dec = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if pass_no == 1:
                if pending_pass0 is not None:
                    # Unpaired pass-1 with no following pass-2 before the next pass-1 --
                    # record it with pass1=None so it's still visible, not silently dropped.
                    cycles.append((pending_pass0[0], pending_pass0[1], None, None))
                pending_pass0 = (cand, dec)
            elif pass_no == 2:
                if pending_pass0 is None:
                    # pass-2 with no preceding pass-1 in this scan -- also recorded, not dropped.
                    cycles.append((None, None, cand, dec))
                else:
                    cycles.append((pending_pass0[0], pending_pass0[1], cand, dec))
                    pending_pass0 = None
    if pending_pass0 is not None:
        cycles.append((pending_pass0[0], pending_pass0[1], None, None))

    print(f"Raw matched DBG lines: {total_lines_matched}")
    print(f"Paired cycles reconstructed: {len(cycles)}")

    complete = [c for c in cycles if c[0] is not None and c[2] is not None]
    print(f"Cycles with BOTH pass-0 and pass-1 counts: {len(complete)}")

    print("\n" + "-" * 60)
    print("PRE-REGISTERED RULE EVALUATION (strict order)")
    print("-" * 60)

    if len(complete) < MIN_CYCLES_WITH_COUNTS:
        print(f"\nROW 1 -- VOID")
        print(f"{len(complete)} cycles carry both counts, under the {MIN_CYCLES_WITH_COUNTS} bar.")
        print("NO VERDICT. Report and stop.")
        return 1

    sat0_count = sum(1 for c in complete if c[0] == K_MAX_CANDIDATES)
    sat1_count = sum(1 for c in complete if c[2] == K_MAX_CANDIDATES_PASS2)
    sat_0 = sat0_count / len(complete)
    sat_1 = sat1_count / len(complete)

    print(f"\nsat_0 (pass-0 candidates == {K_MAX_CANDIDATES}): "
          f"{sat0_count}/{len(complete)} = {sat_0:.4f}")
    print(f"sat_1 (pass-1 candidates == {K_MAX_CANDIDATES_PASS2}): "
          f"{sat1_count}/{len(complete)} = {sat_1:.4f}")

    # Distribution context (not part of the pre-registered rule, reported regardless).
    import statistics
    pass0_vals = [c[0] for c in complete]
    print(f"\npass-0 candidate count distribution: min={min(pass0_vals)} "
          f"median={statistics.median(pass0_vals)} max={max(pass0_vals)} "
          f"mean={statistics.mean(pass0_vals):.1f}")

    if sat_0 >= SATURATED_BAR:
        print(f"\nROW 2 -- SATURATED (sat_0={sat_0:.4f} >= {SATURATED_BAR})")
        print("Budget is rivalrous => FPs cost real decodes => the cap sweep gets priced.")
        return 0

    if PARTIAL_LOW_BAR <= sat_0 < SATURATED_BAR:
        print(f"\nROW 3 -- PARTIAL ({PARTIAL_LOW_BAR} <= sat_0={sat_0:.4f} < {SATURATED_BAR})")
        print("Rivalrous in the dense regime only. sat_0 stratified by decodes/cycle "
              "(pass-0 decoded count):")
        buckets: dict[int, list[bool]] = {}
        for c in complete:
            pass0_dec = c[1]
            buckets.setdefault(pass0_dec, []).append(c[0] == K_MAX_CANDIDATES)
        for dec in sorted(buckets):
            vals = buckets[dec]
            print(f"  decoded={dec:>3}: n={len(vals):>5}  sat_0={sum(vals) / len(vals):.4f}")
        return 0

    print(f"\nROW 4 -- REFUTED (sat_0={sat_0:.4f} < {PARTIAL_LOW_BAR})")
    print("The budget is not the constraint on this corpus. Sec.1's hypothesis is dead; "
          "the FP question stands alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
