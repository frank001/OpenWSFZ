# NHARD-CEIL step 2 result (QA): SETTLED where U′ can see, with U-COV 0 of 0 and a degenerate interval

**Written:** 2026-11-12, `date -u` read 19:04:59Z. **To:** Architect, then the Captain. **Inputs:** `qa/rr-study/results/2026-11-12-nhard-ceil/nhard_result.json` (commit `70b41cd5`), the one run of `nhard_analyse.py main` (blob `c02f04f9`); the freeze record `ebc840ba`; the Architect's V-NAT ruling (`arch/fp-alarm-nhard` `c519ba43`).

## 1. V-NAT, how it was read

The analysis printed V-NAT FAIL because my predicate (freeze record line 22) required the native diff `59eb5a8f..260190e8` to be empty, and it lists the Linux `.so` and the macOS `.dylib`. **V-NAT is read on spec §2's registered row, "DLL = pin at the start and end of each arm", per the Architect's ruling `c519ba43`:** that row held (`dll_pin_ok` true, `arms_pin_ok_at_start_and_end` true). The extra clause was mine, not the spec's (ledger Q61). The analysis was not re-run and its numbers are unchanged. This is a reading of the printed result, not a recomputation.

## 2. The frozen rows against the printed numbers

| row | printed | bar | result |
|---|---|---|---|
| V-NAT (spec row) | pin held at start and end of both arms | pin | PASS |
| V-SET | PASS | | PASS |
| V-WIRE | 8 of 500 cycles differ in published rows | ≥ 1 | PASS |
| C-NET | 0.0 pp, CI [0.0, 0.0]; N24 and N0 each corroborate 11,729 of 13,997 reference rows (83.80 %) | SETTLED needs CI_hi < 0.15 | met |
| C-U | ΔU′_ta 0.0, CI [0.0, 0.0] | SETTLED needs CI_hi ≤ 0.021 | met |
| flag CI_hi(NET) < 0 | 0.0 | | not raised |
| **verdict** | | | **SETTLED**, worded **"settled where U′ can see"** |

**U-COV:** N24's new-text rows absent from N0 = **0**, so the share U′ can judge is **0 of 0, undefined** (not "4 of 19"; there was nothing to judge). N0-only text rows: 0. Latest-batch p95 6,219 ms (N24) and 6,248 ms (N0) against 13 s; no fallback, third-run or late-round abandons in either arm.

## 3. What the SETTLED does not say (read before citing)

- **The intervals are degenerate, not narrow.** Zero text rows differ between the arms, so the bootstrap has no variance to resample. "CI [0, 0]" means *no cycle differed in text*, not that a precision of 0.0 pp was achieved. Against TRAIN's FIX24 minus FIX0 (+0.082 pp [+0.044, +0.123], 621 cycles) this night shows no OSD contribution at all on the station stack with CQ-AP and v2 ON.
- **V-WIRE's 8 differing cycles are not text rows.** I did not open them (HK-037). Whether they are SNR, DT or frequency fields, or something else, is not known from this file.
- **One night, 500 cycles, 40 m.** SETTLED is for this night and this stack.
- Descriptive only: N24 minus the v2 Stage 2 arm B (only `--cq-ap` differs) = +0.536 pp [+0.406, +0.669], 11,729 versus 11,654 corroborated. No verdict.
- Not yet done (descriptive): the N24-derived U′ classes against arm A's `84ec02ba`.

Message text for this job (`_qa-scratch\nhard-ceil\arms\*\nc.tsv`, `arms_dry`) stays until job close.
