# XC-PRIOR result: PURSUE by the registered rule. 520 of the 2,268 unreached rows (3.72 pp of n_ref, CI [3.40, 4.05]) repeat a message we matched 30 to 90 s earlier; the opposite-parity control finds 1.

**Written:** 2026-11-13, `date -u` read 12:03:35Z. **To:** Architect, then the Captain. **Spec:** `arch/cross-cycle-prior` `28627a82` + Amendment 1 (§4: 1 CLOSE, 2 VOID, 3 PURSUE, 4 BETWEEN). **Code:** `qa/same-chain` `9ea109dc` (blobs `xc_lib` `586218d9`, `xc_count` `9fbac174`, `xc_selftest` `7b0121bb`; **18 of 18 mutations killed**), committed before the run. **Run:** `xc_count.py` once. No filter applies (a count, no suite); no build or DLL is involved (the arm's matched file is the input). Working folder `_qa-scratch\xc-prior\` holds numbers only. Desk count: no replay, no PC.

## 1. The decision, mechanically

| row | predicate | value | result |
|---|---|---|---|
| V-CONT | 500 contiguous cycles | 0 gaps, `261110_184745` to `261110_205230` | pass |
| V-N | unreached = 13,997 − matched | 2,268 = 13,997 − 11,729 (N24: CQ-AP ON, v2 ON, nhard 24) | pass |
| 1 CLOSE | CI_hi(E1) < 1.0 pp | CI_hi = 4.05 | no |
| 2 VOID (V-PAR) | E-OPP ≤ 0.25 × E1 fails | E-OPP **1** ≤ 0.25 × 520 = 130 | not fired |
| **3 PURSUE** | **CI_lo(E1) ≥ 1.0 pp** | **CI_lo = 3.40** | **YES** |

**Outcome: PURSUE** (E1 3.72 pp, a factor of 3.4 above the bar at its lower end).

## 2. The counts (pp of n_ref = 13,997; cycle bootstrap B = 2000, seed 20261113)

| quantity | rows | pp of n_ref | 95 % CI | share of the 2,268 unreached |
|---|---:|---:|---|---:|
| **E1** exact repeat of a matched row 30 / 60 / 90 s earlier, ≤ 10 Hz | **520** | **3.715** | [3.400, 4.047] | **22.9 %** |
| E2 same first two fields, different message (descriptive) | 171 | 1.222 | [1.035, 1.425] | 7.5 % |
| **E-OPP** (the parity control: 15 / 45 / 75 s earlier) | **1** | 0.007 | [0, 0.022] | 0.04 % |

- **The control says E1 is repetition, not chance:** 520 same-parity repeats against 1 at the opposite parity.
- **Repetition is common on this night:** **5,167 of the 11,729 matched rows (44.1 %)** are themselves exact repeats of a matched row 30–90 s earlier. Among the unreached rows it is 22.9 %: about half the rate, as expected if weak stations are less often decoded earlier. **The E1 rows are not weaker than the unreached rows as a whole:** SNR quartiles 25 / 50 / 75: E1 −20 / −14 / −8 dB, all unreached −20 / −14 / −7 dB.

## 3. Descriptives (§5)

- **By nearest prior:** 30 s 391 rows (75 %), 60 s 78, 90 s 51.
- **By SNR band of the unreached row** (A ≥ 0, B −10…−1, C −15…−11, D < −15), E1 / all unreached: A 33 / 202, B 149 / 629, C 115 / 451, D 223 / 986 (shares 16 %, 24 %, 26 %, 23 %). E2 by band: A 8, B 45, C 33, D 85.
- **E1 by message kind** (`cf_fbid.shape_class`): `grid` (call + call + grid) **207**, `grid CQ` **139**, `report` 81, `RR73/73/RRR` 14, `other CQ` 3, and hashed variants: grid 39, report 32, RR73 2, other 3. **CQ messages are 142 of 520 (27 %)** (XP-3's "more than half CQ": no). The largest class is a station calling another with its grid, repeated.
- **Prior's batch:** the prior row was matched in batch 1 in **282** of the 520 (54 %), in a later batch in **238** (46 %).
- **Hashed rows:** 76 of the 520 E1 rows carry a `<…>` field (14.6 %), and 13 of the 171 E2 rows; a template test would need the hash resolved (#60).

## 4. What this does not say (§5, restated)

- **It is a ceiling, not a gain.** It counts rows whose message we already knew; whether a template test can **detect** them at their (weak) levels, and at what false-decode cost, is Stage 1.
- **The prior is real but not necessarily usable:** the median unreached E1 row is at −14 dB; the signal strength a template test needs is the Stage 1 question. WSJT-X decoded these rows, so they are reachable by a blind decoder that is better than ours; the count does not say a template test is better than a better blind test.
- **CQ-AP overlap handled** by using N24: the 142 CQ rows in E1 are CQs that CQ-AP did not take.
- **One night, 40 m, 500 contiguous cycles**; CQ density and QSO pace vary by band and hour.
- **Prediction scoring (Architect's, for the ruling):** XP-1 PURSUE **yes**; XP-2 CLOSE **no**; XP-3 more than half of E1 are CQ **no** (27 %).

## 5. Owed

**The Architect rules** (his §4: PURSUE ⇒ Stage 1, a desk template-test feasibility study with a wrong-parity / after-QSO null as its false control, on the Captain's go; no build). The working folder holds numbers only; nothing to delete at close.
