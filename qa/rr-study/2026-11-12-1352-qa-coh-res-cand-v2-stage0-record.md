# COH-RES-CAND v2 Stage 0 record: verdict FEASIBLE (narrowly), gate `freq <= 1097 Hz`

**Run:** 2026-11-12T13:48:28Z (`date -u` at the output). **To:** Architect, then the Captain. **Spec:** `2026-11-12-1340` section 1 plus Amendment 1 section 8 (`arch/coh-res-cand-v2` `83a98408`). **QA (k) review:** `1fe6b588`.
**Nothing was built and no arm was run.** Desk computation on #272's arm folders, which were intact (`crc_result.json` prefix `2b53b412366ce250`).

## What was frozen before any output (committed first, `3fd08b02`)

| item | value |
|---|---|
| script | `qa/rr-study/coh-res-cand-v2/stage0.py`, git blob **`18f230e70d50b809c078dca35213dd23f1786a1c`** |
| permutation procedure | `qa/rr-study/coh-res-cand-v2/p0_null.py`, blob **`7935a226cf309493f1ca2e3514f7aa984fc9c00a`** (same blob at `1fe6b588`, as Amendment 1 asks); `stage0.py` reuses its family, RNG (`random.Random(20261112)`, one list shuffled in place per draw) and 5,000 draws |
| features, in order | `snr`, `dt` (2 dp), `freq` (Hz): frozen in `1fe6b588` before any feature was computed against a class |
| admissible | `kept_TA <= 4` |
| FEASIBLE | `kept_C >= 40` AND `p_perm <= 0.05` (Amendment 1 K1) |
| tie rule | larger `kept_C`, smaller `kept_TA`, earlier feature, threshold that keeps more rows (spec); then `>=` before `<=` (the spec is silent; stated in the script before any output). Not invoked as far as I can tell: I did not enumerate ties |
| instrument | `crc_analyse.py` at `87c5486a`, imported (not copied); classes file SHA-256 prefix `8046a4be4b806fcd08b9`; selection prefix `2575e115` (both asserted by the script) |

## Step 1: the 19 / 9 / 2 split re-derived into a new path (stop rule not triggered)

| | re-derived | #272 report |
|---|---:|---:|
| P0 (B's new-text kind-4 outputs) | **149** | 149 |
| C (corroborated) | **119** | 119 |
| TA (tested_absent) | **19** | 19 |
| tested_present | **9** | 9 |
| hashed or unencodable | **2** | 2 |
| untestable class | **0** | 0 |

Identical in every cell. Per-row numeric table (`snr, dt, freq, class`, no text): `_qa-scratch\coh-res-cand-v2\p0_rows.csv`, SHA-256 prefix `5a4ff6185dfcf61a`. `crc_result.json` was not touched.

## Steps 2 and 3: the selection (run once) and p_perm

| | |
|---|---|
| **chosen gate** | **`freq <= 1097` Hz** (keep a row iff its published frequency is at most 1,097 Hz) |
| `kept_C` | **57** of 119 (47.9 %) |
| `kept_TA` | **4** of 19 (21.1 %), exactly the admissibility cap |
| `kept_other` | 5 of 11 |
| `p_perm` | **0.0476** (238 of 5,000 permutations reached `kept_C >= 57`; the family has 326 gates) |
| `kept_C >= 40` | yes |
| `p_perm <= 0.05` | yes, **by 12 permutations** (250 would have failed it) |
| **Stage 0 verdict** | **FEASIBLE** |

Descriptive (not part of the verdict): the best admissible `kept_C` per feature was **`snr` 55**, **`dt` 37**, **`freq` 57**. Output: `_qa-scratch\coh-res-cand-v2\stage0_result.json`, SHA-256 prefix `b31e81eb42903628`.

## How to read this (QA)

1. **FEASIBLE is narrow, and it should be read as narrow.** `p_perm` is 0.0476 against a limit of 0.05. The Monte Carlo standard error of a share near 0.048 over 5,000 draws is about 0.003, so 0.05 sits about 0.8 standard errors away; a different seed could land on either side. The seed is frozen and I did not re-run with others (that would be shopping for a verdict). The permutation procedure is also not the only reading of "no information": it permutes labels over rows and keeps feature values fixed.
2. **The winner is a frequency gate, not an SNR gate.** CV-1's reasoning was that wrong payloads sit "at the weak end (lowest SNR)". `snr` alone reaches 55 kept C at the cap, 2 fewer than `freq`, and the data does not separate the two features meaningfully. I can name no mechanism by which wrong payloads concentrate below 1,097 Hz, and the instrument cannot say whether the 19 TA rows are wrong payloads at all (#272 report, "What QA does not conclude"). A threshold on audio frequency also depends on where stations sit in the passband on a given night.
3. **`kept_TA` is at the cap, 4 of 4.** Amendment 1 and the spec already say P0's `kept_TA` is optimistic by construction and that P0 is never cited as v2's U cost. 4 per 400 cycles is 0.010 per cycle, about half the bar; on a new night it will be worse.
4. **What the gate would remove from the gain.** 62 of the 119 C rows (52 %) are gated out on this population. I have not computed a NET projection for v2 and do not offer one: the added run's rows, the protected A-only rows and the new night all differ from #272's arm.
5. **Band and configuration shift.** Fitted on a 20 m night with R-F4 and L1′ OFF; Stage 2 runs a 40 m night with both ON and a tested_absent baseline 2 to 3.6× higher (review, request 3). A Stage 2 FAIL will not separate "overfit to 19 rows" from "does not transfer"; the review proposed one descriptive line for that.

## What this record does not conclude

- It does not say the gate works; it says no condition of the spec stops a build, and a build is a Developer session, an HK-039 review and about 1 h of PC.
- It does not revisit any choice after Stage 2 (spec section 7), and no bar was taken from this data.
- It makes no statement about CQ-AP, which is unmeasured with v2 ON.

## Next (spec section 5, items 3 and 4)

1. **The Architect's amendment writes the triple in:** `freq <= 1097` (comparison `<=` on the published integer Hz; the build implements exactly this).
2. **The Captain's go** for the Developer session (Stage 1: R1 to R8). Not given by the spec, not requested by QA before this record is read.
3. Then HK-039 review, the freeze, B-OFF (about 3.5 min), arm B (about 42 to 46 min), the report.

QA holds `_qa-scratch\cq-ap\arms\OFF` (with `nc.tsv`), `coh-res-cand\raw` and `scratch`, and `coh-res-cand-v2\` until v2 is ruled. Nothing of QA's is running.
