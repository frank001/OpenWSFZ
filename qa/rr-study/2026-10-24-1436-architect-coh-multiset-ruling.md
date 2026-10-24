# COH-MULTISET ruling: L1-GO, final on V1(b)

**Architect, 2026-10-24 14:36:22Z by `date -u`.**
- Spec: `2026-10-24-1240-architect-to-qa-spec-coh-multiset.md` with Amendments A1 to A1.10, branch `arch/coh-multiset`.
- QA commits:
  - `6e85c4e4`: V4′ launcher, committed before the replay;
  - `167ddd07`: batch-labelled matched output and manifest, committed before evaluation;
  - `1d172b18`: V4′ evaluator and `v4p.json`;
  - `fe3dfed2`: main extraction, `result.json`. Untouched since, so it was frozen before V4′ ran.
- Docs only; the `src/` and `native/` diff is empty.

## 1. Ruling

| row | reading | verdict |
|---|---|---|
| **L1** | NET_X = **+2.115 pp, 95 % CI [1.937, 2.302]** (N = 26,190 WSJT-X rows, 974 cycles, 122 blocks of 8, B 10,000, seed 20261024) | **L1-GO**: CI_lo 1.94 ≥ BAR_L 0.5 (ratified 12:50:57Z, before any real-audio decode) |
| **W** | f_X = 15 / 569 = 2.64 %, Wilson [1.60, 4.30] %, against the same night's f_C3 = 46 / 1,524 = 3.02 % | **not W-FAIL**: CI_lo 1.60 % does not exceed 3.02 % |

**Status: L1-GO, final once V1(b) passes (§2.3).**
- If V1(b) finds an OSD accept with `nhard` > 24 in the G arm, the verdict is **VOID** and I rule again.
- §6's outcome then applies: I write a build spec for `coherent_fallback.c` (Developer, HK-011), and its replay, with the U′ instrument and a U′ bar set before ON data, is the false-decode gate.

## 2. Validity

### 2.1 V4′ (A1.10): PASS, checked against the commits

- **Order of commits:**
  - launcher `6e85c4e4` (15:09:22 local, 13:09:22Z);
  - replay 13:44:06–14:32:36Z;
  - output and manifest `167ddd07` (14:33:19Z);
  - evaluation `1d172b18` (14:34:08Z).
- **The run:**
  - checkout `main` `5a9667ee`, clean;
  - `libft8` SHA-256 `aaf6b03e…826aef` in the manifest;
  - exit 0, 0 abandoned cycles, 0 competing processes.
- **Readbacks at both ends:** Deep, subtraction ON, threads 8, `nhard` 24, sign fix 1 (read back as 1), fallback ON as shipped (cannot affect P1).
- **P1** = 15,240 rows. G success on P1 = **0.9547 ≥ 0.90** (bar unchanged). There were 0 cycles with a ws-count mismatch.
- **For comparison:** G succeeds on 0.5 % of batch 2+ rows (3,658) and 0.5 % of replay-unmatched rows (5,434). So V4's 0.770 was the population mixing that Q15 named, not a fault in G or in the mapping to anchors.

### 2.2 My own recount from `main_rows.csv` (HK-022)

I recounted from the committed rows, not from QA's summary:

| quantity | QA | mine |
|---|---:|---:|
| rows, cycles | 24,348 / 974 | 24,348 / 974 |
| rows consulted (G and C3 both no CRC-valid output) | 7,498 | 7,498 |
| X right / wrong (first CRC-valid of C1 → J2 → J3 → N1, BP) | 554 / 15 | 554 / 15 |
| NET_X = 554 / 26,190 | 2.115 pp | 2.115 pp |
| CI, block bootstrap | [1.937, 2.302] | ≈ [1.93, 2.31]* |
| G CRC-valid wrong (not consulted) | 732 | 732 |
| C3 right / wrong on G-no-output rows | 1,478 / 46 | 1,478 / 46 |

\*Mine is approximate: 4,000 resamples, with the unencodable rows spread pro rata because they are not in `main_rows.csv`. It agrees with QA's figure to the second decimal.

### 2.3 Still owed: V1(b)

- **A1.10 set out two substitutes for the `nhard` read-back,** (a) and (b). QA has done (a): the log shows `nhard` = 24 at both ends, and the harness calls `ft8_set_decode_params(10, 0.10, 24)`. QA has **not** done (b): check that every OSD accept in the shipped diagnostics has `nhard` ≤ 24, and count the reason-0 rejects.
- **(b) is required as written.** A validity row is not relaxed after the result has been seen.
- **What it guards:** G's `nhard` decides which rows are consulted. A wrong setting would move X's population.
  - (a) and V4′ at 0.9547 make a wrong setting unlikely.
  - (b) is the mechanical proof, and it is cheap.

### 2.4 Two points for QA's report (neither changes the verdict)

- **Faults.** There are 16 rows with `fault = 1`, and 11 of them are among the consulted rows.
  - In `ms_run.py`, one kind of fault is a mismatch between the WSJT-X row and the true codeword, after which the whole row is skipped. The other is an extraction `rc ≠ 0` on one cell, after which only that cell is skipped.
  - At worst they move NET_X by 16 / 26,190 = 0.06 pp, against a margin of 1.44 pp above the bar.
  - The report should give the cause of each kind and the count of each.
- **Cycles.** 974 cycles have rows; the selection has 975, and the V4′ manifest gives `cycles_with_row` 975. The report should say which cycle has no encodable row and why.

## 3. What it means

- **The finding.** At WSJT-X's own positions, trying WSJT-X's four bit-metric sets one at a time recovers **554** of WSJT-X's decodes that neither our main extractor (G) nor the shipped fused coherent set (C3) gets. That is about **2.1 decodes in every 100 that WSJT-X makes**, on one 40 m night. The wrong-payload rate on those rows (2.6 %) is not clearly worse than what C3 already costs on the same night (3.0 %).
  - The CI on f_X reaches 4.3 %. So X is not shown to be cleaner than C3, only not clearly worse.
- **Where the gain comes from:**

| set | first success in X | right at all (any order) | only this set right |
|---|---:|---:|---:|
| C1 (single symbol) | 11 | 11 | 1 |
| J2 (joint pairs) | 262 | 269 | 64 |
| J3 (joint triples) | 210 | 401 | 196 |
| N1 (normalised single) | 71 | 177 | 71 |

  - J3 is the main contributor and N1 brings 71 rows no other set finds.
  - C1 adds 1 unique row. This is expected: the fused V3 set already contains the order-1 metric.
  - Which sets a build carries, and in what order, is for the build spec. Any change to the order is measured by the build's replay, never estimated from this table.
- **L2 (OSD in the fallback) is not worth building.**
  - C3 + OSD adds 19 right and 1 wrong over BP-only, about 0.07 pp.
  - X with OSD adds 7 right (561 against 554) and 0 extra wrong.
  - The gain is small and OSD costs CPU and adds a route for false decodes. L2 closes at this reading.
- **Cost.** The median CPU for the four sets is 0.031 s per consulted row, against 0.047 s for C3 and 0.078 s for G. That is cheap next to what already runs.
- **By stratum** (descriptive):
  - by SNR tercile: NET_X 2.71 / 2.39 / 1.29 pp, low SNR to high;
  - by load quintile: 2.53 / 2.30 / 2.02 / 1.87 / 1.95 pp;
  - f_X ranges from 1.8 % to 4.8 % across the strata.
  - The gain is spread across all strata, not confined to one.
- **Sanity line:** G ∪ C3 over G is +5.67 [5.29, 6.05], beside COH-GAIN's post-hoc +5.25. The instrument reads the shipped fallback as before.

**Limits (spec §10), to travel with every figure:**
- **Positions.** These are WSJT-X's positions, not our candidates. A production build will gain less: the fallback itself went from +5.25 at WSJT-X's positions to +3.82 in replay. No production figure is derived here; the build's replay measures it.
- **Scope.** One 40 m night, and no interaction with subtraction.
- **Wrong payloads.** These include genuine co-channel stations, so f_X is an upper bound on false decodes.
- **The 732 G-wrong rows** are outside X's population, as in production.
- **The method.** The joint metrics are QA's implementation of a prose method. They are validated by V2a/V2b, not shown to be identical to WSJT-X's. Under the licence policy, nothing was copied.

## 4. Predictions, scored now (§11)

| id | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| X1 | NET_X point ≥ 0.5 pp | 0.40 | H | ✅ HIT (2.115) |
| X2 | L1-GO at 0.5 | 0.30 | H | ✅ HIT (CI_lo 1.94) |
| X3 | J2 + J3 > half of first successes | 0.60 | H | ✅ HIT (472 / 554 = 85 %) |
| X4 | W-FAIL fires | 0.20 | H | ❌ did not fire (P was 0.20, so the call was right) |
| X5 | C3 + OSD ≤ 0.3 pp over C3 BP-only | 0.75 | C | ✅ HIT (19 / 26,190 = 0.07 pp) |
| X6 | V2a passes first time for all four sets | 0.60 | C | ✅ HIT (200/200 each) |

- **Brier score:** 0.36, 0.49, 0.16, 0.04, 0.0625, 0.16, mean **0.212**.
- **Calibration:** I was *under*-confident on X1 and X2. The gain came out at about 4× the bar, where I gave 0.40 for even reaching it. This runs against the ledger's usual bias, where hypothesised calls favour a findable defect, and is recorded as such.

## 4a. Addendum, 14:43:02Z by `date -u`: V1(b) PASS, so L1-GO is FINAL

**QA's result** (output `d1f7d906`, committed before evaluation):
- **The run:** `ft8_decode_all` over the 975 sampled cycles. Same DLL `aaf6b03e`. The process was configured as `ms_run` configures it: `set_decode_params(10, 0.10, 24)`, sign fix 1.
- **Decodes:** 16,543, with 48 OSD accepts. All 48 were stored, so the store was not truncated.
- **`nhard` on accepts:** the maximum was 16; **0 accepts had `nhard` > 24**.
- **Rejects:** 7,153 under reason 0, the `nhard` cap, so the cap was demonstrably in force; 0 under reason 1.

**Why this counts for the G arm** (FILE:LINE on `5a9667ee`):
- The shipped diagnostic records only the `ft8_decode_all` path, so it cannot see G's `ft8_ldpc_decode_llrs` calls (QA, `ft8_shim.h:1139–1140`).
- Both paths read the same cap:
  - the gate in `ft8_ldpc_decode_llrs` is `if (nhard > OSD_NHARD_MAX)` (`decode.c:1034`);
  - `OSD_NHARD_MAX` is `s_osd_nhard_max` (`decode.c:77`), a process-global that `extern` declares at `decode.c:65`;
  - the candidate path reads the same macro at `decode.c:727`.
- So (a), the call and its return in the harness log, together with this run, shows the cap at 24 in a process set up like G's. It is not an instrument on G itself, and QA's report says so.
- **My error (ledger E55).** I wrote (b) without checking what the diagnostic covers. QA's substitute is the mechanical check that can actually be done, and I accept it.

**Report items, counted by QA:**
- **(i) Faults.** All 16 fault rows are one kind: `ft8_extract_llrs_at` returned −3 (frequency outside the export band).
  - 13 rows sit at 113–134 Hz and 3 at 3,106–3,107 Hz.
  - On 15 rows all 9 lattice cells failed; on 1 row, 6 of 9.
  - There were 0 mismatches between codeword and row. C3 ran on these rows.
  - 11 rows are in the consulted population and 5 are not. Immaterial (at most 0.06 pp).
- **(ii) The missing cycle.** It is cycle index 1, stamp `261022_194915`, at the very start of the run, where WSJT-X logged no Rx lines. So 975 cycles were selected and 974 have rows. Every sampled cycle that has WSJT-X lines has at least one encodable row.

**Verdict: L1-GO, FINAL; not W-FAIL.** The next step is a build spec, which waits on the Captain's go (HK-011).

## 5. Next

1. **QA:**
   - V1(b);
   - then the noise leg (descriptive, HK-026), because the report has to contain it;
   - then the written report in COH-GAIN's format, including §2.4's two points;
   - then copy the run folder to the root `qa\rr-study\results\` (standing rule).
2. **Captain:** a go or no-go on the Developer build of `coherent_fallback.c` (HK-011). I write the build spec on his go, after V1(b) passes. It is a separate step and needs a decision of its own.
