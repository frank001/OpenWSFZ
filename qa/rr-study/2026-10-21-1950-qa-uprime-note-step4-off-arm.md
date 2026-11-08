# QA: the U′ note for COH-FALLBACK step 4 (OFF arm read; U′_max for the Captain; no ON decode has run)

**From:** QA. **To:** the Captain (decides U′_max), Architect. **Stamped:** 2026-10-21 ~19:45Z by `date -u` (the file name's 1950 was a guess made before the stamp; the freeze note below carries the checked time).
**Spec:** `arch/coherent-limb2` step3-build.md §14 A14.3, §15 A15.3, §16 A16.3, §17 A17.2 and the Captain's decision of 2026-10-21 18:45Z ("go with your recommendations": the §16 default thresholds, frozen before the OFF arm).

## What was run (pre-flight, HK-020)

| item | value |
|---|---|
| night | `20260922_2056` (Voicemeeter chain, 40 m, band confirmed from the run's correction note), selection frozen before any decode: 1-in-3, 961 of 2,882 slots, V-P PASS, SHA-256 (LF) `9ce4fbb4b94ae7328bc62697224cc8db918ca03f234d4401830f3501e25f7c28`, re-hashed at launch |
| build | `feat/coh-fallback-stage1` `b8fc732e`, shim 20260069, `libft8.dll` `aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef` (hashed at the start AND the end of the arm: both equal) |
| read back, start and end of the log | flag `cohfb=False`, `decodingDepth=Deep`, `nhard=24`, `osdSignFixRead=1`, `shim=20260069` |
| arm | OFF, 18:51:24Z to 19:41:13Z (49 min 49 s), 961 cycles, 0 exceptions, 0 deadline-abandoned cycles; third pass ran on 910, skipped (no new decodes) on 51 |
| cycles in U′ | 960 (the one cycle where WSJT-X decoded nothing is excluded, paired) |
| frozen procedure | `cf_uprime.py` (committed `93fa9d2b` before the arm ran): `cf_fbid.py` blob `66dd1e94` (= `ecc4c5e7`, asserted), T = 0.276, thresholds n ≥ 10 and present rate ≥ 80 %, up to 50 per class, seed 20261007 |

## The class table (the OFF arm's CONFIRMED decodes; this is the list frozen for both arms)

| class | confirmed decodes | sampled n | present | present rate | Wilson 95 % CI | testable |
|---|---:|---:|---:|---:|---|:---:|
| RR73 / 73 / RRR | 2,842 | 50 | 47 | 0.940 | [0.838, 0.979] | yes |
| grid | 6,855 | 50 | 48 | 0.960 | [0.865, 0.989] | yes |
| grid CQ | 5,254 | 50 | 48 | 0.960 | [0.865, 0.989] | yes |
| report | 5,462 | 50 | 47 | 0.940 | [0.838, 0.979] | yes |
| other CQ | 545 | 50 | 2 | 0.040 | [0.011, 0.135] | **no** (rate) |
| other | 8 | 8 | 5 | 0.625 | [0.306, 0.863] | **no** (n < 10) |

- No testable class sits near the 80 % line: the lowest is 94 %. The Architect's condition for reopening the threshold (a class right at the threshold) does not arise.
- The shape-class function is the committed one; the hashed texts are not in this table (they are untestable by rule (i)).
- **The night's own null:** n = 5,160 sequences, mean 0.148, **p99 = 0.2759 against the frozen T = 0.276** (difference 0.0001, tolerance 0.03). No flag to the Architect.
- Calibration (where a reported DT puts symbol 0): median start − DT = −0.18 s from 70 of 80 controls with a Costas hit ≥ 0.6.

## U′0 (the OFF arm; per cycle, 960 cycles)

| | decodes | per cycle |
|---|---:|---:|
| all decodes scored | 22,264 | |
| confirmed by WSJT-X (Test B) | 21,974 | |
| **not confirmed** | **290** | 0.302 |
| of which tested and shown present (not counted in U′) | 111 | |
| **tested-absent** (testable class, tones below T) | 36 | 0.0375 |
| **hashed or unencodable** | 135 | 0.1406 |
| **untestable class** (other CQ, other) | 8 | 0.0083 |
| **U′0** = the three counted rows | 179 | **0.1865** |

- Three quarters of U′0 (135 of 179) are hashed texts, not decodes the instrument found absent. Counting them as "not shown present" is the conservative rule of A14.3 and makes U′ an upper bound.
- Of the 147 not-confirmed decodes in testable classes, 111 (76 %) show their tones: most of what WSJT-X did not confirm is real signal, as on 10-09.

## The proposal (QA's, per the frozen rule; the choice is the Captain's)

| | value |
|---|---:|
| U′_max = 0.30 × U′0 | **0.0559** |
| projected paired half-width of ΔU′ (A11.2: 1.96 × √(2 × U′_max / 960)) | 0.0212 |
| 2 × half-width | 0.0423 |
| U′_max ≥ 2 × half-width (A2.4(a)) | **yes** (0.0559 ≥ 0.0423): the "goes back to the Captain" trigger does not fire |
| the A15.3 line: "U′_max is ≤ 2 × 0.021 = 0.042" | **NO** (0.0559 > 0.042) |

### What "no" means, and what it leads to (data, per your rule 2026-10-06)

- 0.021 is the largest ΔU′ that 10-09 showed (0.005 to 0.021). The line asks: would the bar catch a fallback **twice as noisy** as that?
- At U′_max = 0.0559 it would **not** be caught outright. A fallback twice as noisy (ΔU′ ≈ 0.042) gives an upper CI bound of about 0.060, above 0.0559, so the row would read **U′-OPEN**, not U′-FAIL.
- What each row needs, with this bar and this sample: **U′-OK** needs ΔU′ ≤ 0.038 (CI upper bound ≤ 0.0559); **U′-FAIL** needs ΔU′ ≥ 0.082 (CI lower bound > 0.0559), about 3.9 times 10-09's largest. (Solved with the A11.2 half-width at 960 cycles; the thresholds move a little with the ON arm's real dispersion.) Between them: U′-OPEN, which is not a breach and goes to you.
- By §15 A15.3 the choice is **yours, not QA's**:
  1. **Keep the 30 % rule: U′_max = 0.0559** (a decision value, 30 % of what the OFF arm does without the fallback, the rule you confirmed on 2026-10-20 for U). Consequence: the weak-bar case above; the row is reported as weak.
  2. **A fixed value you name**, for example **0.042** (the 2 × 0.021 line). Consequence: a fallback twice as noisy as 10-09's lies exactly at the bar; U′-OK would need ΔU′ ≤ 0.027, i.e. only slightly worse than 10-09's largest; U′-FAIL needs ΔU′ ≥ 0.065 (3.1 times 10-09's largest). A tighter bar is more likely to read U′-OPEN or U′-FAIL on this night.
- This is a decision value, not housekeeping: it sets what "the fallback adds too many unconfirmed decodes" means before any ON decode.

## What is NOT in this note, said once

- No ON decode has run. The class list above is frozen from the OFF arm alone and goes unchanged to ON and ON-repeat, together with T, the sampling and the calibration offset.
- The old Test-B ΔU (descriptive, beside U′) and NET by band are computed from the ON arm later.
- The working file with message text (`nc_dump.tsv`) stays under `D:\Projects\claude\_qa-scratch\coh-fallback\step4\off\`, outside git, and is deleted at job close (HK-037). Everything committed with this note is numbers and stamps only.
