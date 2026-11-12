# `COH-RES-CAND v2` (programme candidate #3) spec: a fourth fallback run on the residual audio with the residual buffer's own candidates, behind a gate frozen from #272's data, tested on the 10 November capture

**From:** Architect · **To:** QA (for the Developer, HK-015) · **Date:** 2026-11-12 13:38:15Z (`date -u`) · **Branch:** `arch/coh-res-cand-v2` (off `origin/main` `70bc72b1`)
**Authority:** the Captain, 2026-11-12 (relayed by QA): "start the spec for candidate #3, COH-RES-CAND v2". His standing word on #272 also applies: "keep the verification tests small". **The Developer session (Stage 1) needs his go after Stage 0**; this spec does not give it.
**Base:** `main` `70bc72b1` (v0.70, shim 20260072). Its tree is identical to `7ca00264` (`git diff --quiet 7ca00264 70bc72b1` exits 0), the build of the CQ-AP arms. Stage 1 is a `src/` change and needs a separate Developer session (HK-011), QA's HK-039 review before any arm, and `pre_merge_check.py` before any push (HK-006). **This document is docs only** (`git diff --stat origin/main -- src/ native/` is empty).

🟢 **Size rule (the Captain's, carried from #272).** Stage 0 is a desk check on data already on disk. Stage 2 is **one** new 500-cycle replay arm on the PC plus a 40-cycle identity check; arm A is **reused**, not re-run. No sol, no second night, no station time. Any amendment that adds an arm or cycles needs his word.

---

## §0. What #272 taught, and what v2 changes

#272 (`b0d01f4f`, ruling `2026-11-08-1859`, FAIL by U-FAIL) **replaced** the list the residual run reads (original snapshot → residual buffer's snapshot). On `20260930_1930`, first 400 cycles:
- **B-only:** 150 texts, 120 corroborated. **A-only:** 79 texts, 58 corroborated. NET +0.504 pp [0.286, 0.717].
- B's new-text batch-4 outputs not corroborated: 19 tested_absent, 9 tested_present, 2 hashed. **ΔU′_ta 0.0475 [0.0274, 0.0700] against the bar 0.021.**
- So the design lost 58 good rows (my error E136), and the rows it gained carried a wrong-payload cost of about 2.3× the bar.

**v2 fixes both, in two separate pieces:**
1. **Add, don't replace.** The two runs that exist today stay exactly as they are, with the same lists, the same order and the same budget. A **new, last** run reads the residual audio with the residual buffer's snapshot, on whatever budget is left. Every row today's runs produce is still produced, so the 58 A-only rows cannot be lost by design.
2. **Gate the new run's rows** with a one-feature threshold **frozen from #272's arm-B data (Stage 0)**, before the build exists. It is then tested on a night it was not fitted on (Stage 2). If no feature separates the 19 tested_absent rows from the corroborated ones in #272's data, **v2 stops at Stage 0 with no build.**

**Why now (the programme's condition for #3):** the station runs R-F4 and L1′ ON (default since v0.69). Since 2026-11-10 there is a capture from that build with **WSJT-X running alongside**: `artefacts\20261110_1817_cq-ap-live\`, 40 m, 739 cycles, the corpus of the CQ-AP arms. That is the U side #272 could not see in this configuration.

## §1. Stage 0: is there a gate at all? (QA, desk, no build, no new runs)

**Data:** `_qa-scratch\coh-res-cand\raw\B` and `\A`, #272's arm folders, still on disk. QA's (k) review confirms they are complete and unaltered (SHA-256 of `crc_result.json` prefix `2b53b412366ce250…` as reported).

**Population P0:** #272 arm B's **new-text batch-4 outputs** (texts absent from A's rows of that cycle), 149 rows, classified by the frozen U′ instrument exactly as in #272's report:
- class **C**, corroborated (report: 119);
- class **TA**, tested_absent (report: 19);
- **other** (9 tested_present, 2 hashed). These are carried and counted, but they do not drive the choice.

If QA's re-count differs from 119 / 19 / 11, QA stops and reports before any feature is looked at.

**Features (frozen in QA's (k) review, BEFORE any feature is computed against a class):** only per-row numeric fields the harness already writes for a published fallback row. Known today: `snr`, `dt`, `freq` and `path` in `outcomes.csv` (`stamp,kind,seq,freq,dt,snr,path`). QA adds any other per-row fallback field it finds in the arm's files (for example a multi-set `crc_*` set id per row, if one exists per row and not only per cycle). **QA lists the fields in a fixed order, and states which of them the build can compute at publish time**: a gate the build cannot compute is not a gate. No new instrument, and no field derived from the WSJT-X lines.

**Gate family:** one feature `f`, one direction `d` (keep `f ≥ t` or keep `f ≤ t`), one threshold `t` taken from the observed values of `f` in P0.

**Selection rule (mechanical, run once):**
1. For every (f, d, t): `kept_TA` = TA rows kept, and `kept_C` = C rows kept.
2. Admissible iff `kept_TA ≤ 4`.
3. Choose the admissible triple with the largest `kept_C`. Ties go to the smaller `kept_TA`, then the earlier feature in QA's frozen order, then the threshold that keeps more rows.

**Verdict:**
- **FEASIBLE** iff the chosen triple has `kept_C ≥ 40`. Report (f, d, t), `kept_C`, `kept_TA` and the kept count of "other".
- **NOT-FEASIBLE** otherwise. **v2 stops.** The Architect recommends closing #272 to the Captain, and no build is asked for.

**Where the two numbers come from (HK-038).** Both are #272's data, which is the only data on file for this population.
- **`kept_TA ≤ 4`:** 4 rows in 400 cycles is 0.010 per cycle, about half the U bar of 0.021. The other half is margin for the CI on a new night. #272's ΔU′_ta interval was about ±0.02 wide at 19 rows, so a point near 0.01 is needed for `CI_hi` to stay ≤ 0.021.
- **`kept_C ≥ 40`:** at #272's n_ref of 12,292, 40 rows is ≈ +0.33 pp. #272's 400-cycle NET interval was ±0.22 pp wide, so a true gain below ~0.3 pp would not reach N-GO reliably on one arm. Below 40, the arm cannot answer its own question.

🔴 **Fitting risk, stated.** A threshold chosen on 19 TA rows is fitted to them, and P0's `kept_TA` is optimistic by construction. **Stage 2 on a different night is the test; Stage 0 only decides whether a test is worth building.** P0 is never cited as v2's U cost.

**Cost:** about 1 h of QA desk time. Aggregates only leave the script (HK-037); message text lives in memory, read from `_qa-scratch`.

**Output:** a short Stage 0 record (the frozen feature list, the chosen triple, the counts, the verdict), committed by QA **before any Stage 1 work starts**. With FEASIBLE, the triple is written into this spec by an amendment, and the build implements exactly that triple.

## §2. Stage 1: the build (only with FEASIBLE and the Captain's go; Developer session, HK-011)

**R1. The setting.** New key **`decoder.coherentFallbackResidualCandidates`** (bool), the same key #272 used (never merged).
- Absent means `false`. It follows the config overlay (HK-035) like `decoder.lateSubtractionRound` (`Ft8Decoder.cs:259–271`).
- **OFF ⇒ today's code path exactly, and no extra snapshot is taken** (row B-OFF).
- It has an effect only in `Both` mode with a residual buffer present (R2 or R3).

**R2. The residual snapshot.** As #272 R2 (spec `2026-11-08-1614` §1 R2 and Amendment 3; QA's HK-039 review of `b0d01f4f` found it needed no `native/` change, CR-1 HIT).
- The Developer may port `feat/coh-res-cand` (`b0d01f4f`)'s snapshot plumbing onto `70bc72b1`, citing what was taken.
- The snapshot is taken on the thread that ran `DecodeAll` on the buffer, right after that call, for R2 and for R3. The one matching `CohFallbackAudioSelector.Select` (`:1262`) is used.

**R3. The new run.** In the `Both` branch (`Ft8Decoder.cs:1276–1300`):
- **The two runs of today are unchanged:** residual audio with `cohSnapshot` first, then original audio with `cohSnapshot`, on the same budget arithmetic.
- **Then, with the setting ON and a residual buffer present, a THIRD `RunCoherentFallback` call:** `choice.Pcm` with the residual snapshot, on `leftMs` recomputed after the second run.
- If nothing is left (`leftMs ≤ 0`), the new run is not started, and the cycle is logged `resRun=skipped-budget`.
- If the residual snapshot is missing, the new run is not started (`resRun=no-snapshot`). Nothing throws.
- 🔴 **R-F4's ungating never applies to the new run.** Its rows pass F1b exactly as the residual run's rows did with R-F4 OFF. Reason: the Stage 0 gate was fitted on #272's rows, which were F1b-gated (R-F4 OFF in both arms).
  - `CohFallbackAudioSelector.Merge` takes two row sets and one `ungatedOn` flag (`Ft8Decoder.cs:1292`). I have not read how a third set should enter it.
  - **The Developer states, with file:line, how the new run's rows get F1b with R-F4 ON,** and a unit test proves it (R8).

**R4. The gate.** Each row of the new run whose text is not already published in this cycle (batches 1–3 or today's two fallback runs) is kept iff it passes the Stage 0 triple (f, d, t).
- Rows that fail are dropped and counted (`resNewGated`). The gate is applied **only** to the new run's rows.
- The comparison is exact as frozen (`≥` or `≤`, on the same quantity, rounded as the harness writes it). The Developer cites the field's source and its rounding.

**R5. Publication.** Kept rows join batch 4 through today's `Merge`/`Select` and the per-cycle text de-duplication. No text twice in a cycle (row B-DUP). The rows feed L1′'s fit list like any batch-4 row.

**R6. The log line.** Added to the coherent-fallback line, only when the setting is ON:
- `resRun={ran|skipped-budget|no-snapshot|no-residual}`;
- `resCand={residual-R2|residual-R3}`;
- `resEligible={n}`;
- `resNew={n}`: new-text rows before the gate;
- `resNewGated={n}`;
- `resNewKept={n}`;
- `resWallMs={ms}`.

**R7. Version and docs.**
- `VERSION` 0.70 → 0.71, in every place the gates check.
- `REQUIREMENTS.md`: a new FR at the next free number.
- An OpenSpec change `coh-res-cand-v2` and a changelog row.
- The docs state: default OFF, `Both` only, the gate's frozen triple and where it came from, and that ON starts a new live era.

**R8. Unit tests.**
- OFF is a no-op: no snapshot call, no third run.
- ON: the third run gets the residual snapshot of the buffer `Select` returned (R2 and R3).
- The first two runs still get `cohSnapshot` with unchanged budgets.
- `skipped-budget` and `no-snapshot` are reachable, and nothing throws.
- The gate keeps and drops at exactly `t` (both sides).
- R-F4 ON does not ungate new-run rows.
- No duplicate text.

**Not in this build:** no change to the first two runs, to F1b, R-F4, multi-set, L1′, CQ-AP, batches 1–3, the 13 s budget, or `native/`. No default ON.

## §3. Stage 2: the test (PC, station daemon stopped, WSJT-X closed or idle and recorded as such)

**Night:** `20261110_1817_cq-ap-live` (40 m), **the 500 cycles of `qa/cq-ap/live-session-cycle-list.txt`** (CQ-AP freeze Part 1, `342d320b`), in that order, one process.

**Arm A is reused:** `_qa-scratch\cq-ap\arms\OFF`, the CQ-AP OFF arm.
- Build `7ca00264` (tree identical to `70bc72b1`), `--cq-ap 0`, Deep, `nhard` 24, OSD fix, `--mode three1`, 8 threads, fallback + multi-set ON, `Both`, kmin 5, OSD corr 0.05, R-F4 ON, L1′ ON (`cqap_arms.sh` lines 6–9 and 39–44).
- Its repeat OFF2 differed in 0 of 500 cycles, so A is reproducible on this PC.
- 🔴 **QA keeps `_qa-scratch\cq-ap\arms\OFF` (and `nc.tsv` in it) until v2 is ruled.** It is a per-message working file under HK-037's 2026-10-10 amendment, deleted at v2's job close, not at CQ-AP's.

**Arm B:** the v2 build with the setting ON. Every other argument is identical to A's command line, `--cq-ap 0` included.
- CQ-AP is OFF in both arms on purpose: A already exists that way, and it keeps the comparison to one change.
- The station runs CQ-AP ON, so the interaction is **unmeasured** and is stated as a limit. Any v2 ON on the station starts a new era anyway.

**Freeze (one commit, before arm B's output exists):**
- the build commit and DLL SHA-256 (the pin `bbde6eb6…6528` unless `native/` changed, which R2 forbids);
- the cycle list's SHA-256;
- arm A's folder hashes;
- the Stage 0 triple;
- the analysis code (adapted from `crc_analyse.py` at `87c5486a`), with a synthetic self-test that passes;
- the seed **20261112**, B = 2000.

| row | predicate (mechanical) |
|---|---|
| **B-NAT** | `git diff --stat 70bc72b1 <build> -- native/ src/OpenWSFZ.Ft8/Native` is empty, and the DLL SHA-256 = `bbde6eb6…6528` at the start and end of every leg |
| **B-OFF** | the build with the setting OFF, on the first 40 cycles of the list, publishes rows identical to arm A's for those cycles, every field (kind, freq, dt, snr, path, text, matched flag), **40 of 40**. This also licenses arm A's reuse: if it fails, stop. Bar source: OFF vs OFF2, 0 of 500 differing on this night and PC |
| **B-WIRE** | denominator: arm-B cycles whose fallback line shows a residual level. (i) `resRun` ≠ `no-snapshot` in **100 %** of them (the snapshot plumbing passed 400/400 in #272); (ii) `resNewGated` > 0 **or** `resNewKept` > 0 in ≥ 1 cycle (plumbing floor only) |
| **B-KEEP** | every arm-A row of **batches 1–4** (by cycle and text) is in arm B. **Allowed, listed and counted:** a row whose text holds a hashed call (`<…>`) and whose B row in the same cycle has the same freq and dt with a different rendering (the hash table is process-global, so the new run's unpacks can change later renderings). Any other missing row fails the row: it tests "add, don't replace". **Batch 5 is outside B-KEEP:** new batch-4 rows change what L1′ subtracts, so batch-5 rows may legitimately differ. A-only batch-5 rows are a descriptive line, and NET pays for them |
| **B-DUP** | no text published twice in one cycle of arm B |
| **N-GO** | `CI_lo(NET_B−A)` > **0** pp |
| **N-STOP** | `CI_hi(NET_B−A)` ≤ 0 pp |
| **U-OK** | `CI_hi(ΔU′_ta)` ≤ **0.021** per cycle |
| **U-FAIL** | `CI_lo(ΔU′_ta)` > 0.021 |
| **B-AB** | cycles with fallback `abandoned > 0`: count(B) ≤ count(A) |
| **B-LATE** | cycles whose L1′ round was abandoned: count(B) ≤ count(A) + 5 (1 % of 500) |

**Instruments (NET, ΔU′_ta, bootstrap).**
- Exactly as #272 (`crc_analyse.py` at `87c5486a`, B = 2000), against this night's WSJT-X lines (FT991A profile `frans`, gathered in the artefact folder).
- **ΔU′_ta** covers B's new-text, not-corroborated outputs in **batches 4 and 5** (batch 5 because new batch-4 rows change what L1′ subtracts), classified tested_absent, per cycle with WSJT-X lines.
- **The U′ classes are frozen from arm A** (`cf_uprime.py off` on A's `nc.tsv`/`testb.csv`), committed in the freeze before B runs.
- `T` = 0.276 as frozen. If this night's null p99 differs by more than 0.03 (exit 4), **stop and the Architect rules before B's U′ is read.**

**Verdict:**
- **ACCEPT** iff B-NAT, B-OFF, B-WIRE, B-KEEP, B-DUP, N-GO, U-OK, B-AB and B-LATE all pass.
- **FAIL** iff N-STOP or U-FAIL fires.
- **OPEN** otherwise, which goes to the Captain with the numbers. No second night automatically.

**Descriptive (no verdict):**
- `resNew`, `resNewGated` and `resNewKept` totals;
- the gated-out rows' C / TA split (what the gate threw away), from the same instrument;
- `resWallMs` median and max;
- the latest-batch p95 of B − A against 13 s;
- B-only rows split by batch (4 vs 5);
- the 9-tested_present-style split of the not-corroborated new rows.

**Bars (HK-038), and where each comes from.**
- **NET 0 pp:** the Captain's bar for #272 (2026-11-08, "fine with me"), carried unchanged. He may change it in QA's (k) round, never after data.
- **U 0.021 per cycle on tested_absent:** U_bar_G, ratified at COH-GATE-G (2026-10-28) on **20 m** nights, and used for LATE-SUB, L1′ and #272. 🔴 **This night is 40 m. The bar has never been checked against a 40 m night's own U′ level.** QA's (k) review states arm A's U′0 (total not-shown-present per cycle, all batches) on this night beside the 20 m nights' values on file. If it is more than 2× the highest 20 m value, the Architect rules on the bar **before** arm B runs, and says so in an amendment.
- **B-LATE + 5:** data on file: L1′ abandoned 0/940 in the first live session (era "RF4+L1′ ON") and 0 in both CQ-AP arms on this night. The +5 is my choice: 1 % of cycles, below which a timing cost cannot matter at the station's 13 s budget. Stated as a choice, not derived.

## §4. Timing

Today's fallback ends at about 5.6 s on the PC (#272 report: latest fallback end 5,606 ms in A). The third run adds about one run's wall time: #272's median `fbWallMs` was 529–605 ms for **both** runs together, so perhaps 0.3–0.5 s. The L1′ round then starts that much later on the same 13 s budget.
- **B-AB and B-LATE are the guards.** NET pays for any lost rows.
- No sol leg. Sol-class timing is seen only if the Captain later wants default ON, in that run.

## §5. Order and cost

1. **QA's (k) review of this spec.** Freeze the Stage 0 feature list here, confirm the #272 folders and arm A, and give the 40 m U′0 figure (§3).
2. **Stage 0** (QA, about 1 h desk). Record committed. **NOT-FEASIBLE ⇒ stop**; my recommendation goes to the Captain.
3. **FEASIBLE ⇒ an amendment writes the triple in**, and **the Captain's go for the Developer session.**
4. Developer: R1–R8, commit. QA: HK-039 review.
5. QA: freeze, then B-OFF (40 cycles, about 5 min), then arm B (500 cycles, **about 1 h**: an estimate from the CQ-AP arms' plan of about 3.5 h for 500 + 500 + 500 + 50 cycles. QA's stamps for those arms are the real figure, and QA corrects it in (k) if they differ).
6. QA: a short report (rows table, the descriptive lines). Then my ruling.
7. ACCEPT ⇒ `pre_merge_check.py` and the Captain's sign-off to merge with the setting **OFF**. ON on the station is his separate decision, and a new era.

**Total if FEASIBLE and ACCEPT:** about 1 h desk, one Developer session, about 1 h 15 min PC. **If NOT-FEASIBLE: about 1 h, nothing built.**

## §6. Predictions (Architect; scored at the rulings)

| # | prediction | P | class |
|---|---|---:|:---:|
| CV-1 | Stage 0 is FEASIBLE | 0.40 | H |
| CV-2 | no `native/` change is needed (R2 ports from `b0d01f4f`) | 0.85 | C |
| CV-3 | B-OFF and B-WIRE pass on the first Developer commit (given FEASIBLE) | 0.75 | C |
| CV-4 | U-OK fires on Stage 2 (given FEASIBLE) | 0.50 | H |
| CV-5 | ACCEPT (given FEASIBLE) | 0.35 | H |

**Reasoning.**
- **CV-1:** 19 TA rows against 119 C. If the wrong payloads sit at the weak end (lowest SNR) or in one multi-set path, one threshold can keep ≥ 40 C at ≤ 4 TA. If they are spread like the good rows, nothing can. I have not looked at the data, so the price sits just below even.
- **CV-4 and CV-5:** the gate is fitted on 19 rows of another band and another configuration (R-F4 and L1′ OFF), so its kept-TA rate on a new night will be worse than in Stage 0. CR-5's confident miss (0.80, "no gate loosened ⇒ no U cost") is why CV-4 sits at even.

🔴 **Bias check:** HYPOTHESISED calls lean toward "a localised, findable gain". CV-1 and CV-5 are held below 0.5 for that reason.

## §7. What this spec does NOT do

- It does not reopen #272's verdict. FAIL stands for `b0d01f4f`. v2 is a different design (add + gate) with its own bars, frozen before its data. It is not a re-read of a closed gate with a better metric (standing prohibition).
- No bar is taken from Stage 2's data, and no Stage 0 choice is revisited after Stage 2.
- No change to CQ-AP, R-F4, L1′, or the station's config.

## §8. Amendment 1 (2026-11-12 13:46:14Z, `date -u`): QA (k) review adopted, and a ruling on the U bar for 40 m

QA's review: `qa/rr-study/2026-11-12-1350-qa-k-review-coh-res-cand-v2.md` (`qa/same-chain` `1fe6b588`, local), **ACCEPT WITH THREE AMENDMENTS.** All three are adopted. They replace the named parts of §1 and §3.

**A1.0 Facts from the review, now part of the spec.**
- **Stage 0 features, frozen in this order:** F1 `snr`, F2 `dt` (2 dp), F3 `freq` (Hz). All three are computable at publish time.
- **Not admitted:**
  - `kind` and `path`, which are constant in P0 (`path` = 2 for all 1,441 of B's kind-4 rows);
  - every field derived from the WSJT-X lines;
  - per-cycle `coh.csv` fields.
- **No per-row multi-set id exists,** so §6's "one multi-set path" branch of CV-1 cannot be tested.
- **#272 folders intact:** `crc_result.json` prefix `2b53b412366ce250` matches. P0 = 149 rows, 119 C, 30 not corroborated.
  - The 19 / 9 / 2 split of the 30 is **step 1 of Stage 0**: the frozen U′ instrument, into a new output path.
  - **If it differs from 19 / 9 / 2, stop and report before any feature is read.**
- **Timing, from QA's stamps:** a 500-cycle arm takes 40.0–41.9 min, and the whole CQ-AP chain took 2 h 08 min. **Arm B is about 42–46 min, and B-OFF about 3.5 min.** §5's "about 1 h" and "3.5 h" were wrong (E161).

**A1.1 (K1) The FEASIBLE row, restated: it must beat chance.**
- With the class labels permuted (no information at all), the §1 rule reaches `kept_C ≥ 40` in **54.4 %** of 5,000 draws (326 gates; null median 41, 95th percentile 56).
- So §1's FEASIBLE row fired about as often on noise as on a real separation. **That is my error E160:** I did not check whether the row could discriminate.
- **Restated:** FEASIBLE iff `kept_C ≥ 40` **and** `p_perm ≤ 0.05`.
  - `p_perm` is the share of 5,000 label permutations (seed 20261112, the null procedure in `qa/rr-study/coh-res-cand-v2/p0_null.py` at `1fe6b588`, blob hash recorded in the Stage 0 record) whose best admissible `kept_C` is ≥ the observed one.
  - The same three features, the same `kept_TA ≤ 4`, the same tie rule. The search over three features is inside the null, so no single-feature restriction is needed.
  - **In practice, about `kept_C ≥ 56`.** That is ≈ +0.46 pp at #272's n_ref.
- Stage 0 runs this once. NOT-FEASIBLE stops v2 as in §1.

**A1.2 (K2) VOID for validity rows.**
- **VOID** iff B-NAT, B-OFF, B-WIRE, B-KEEP or B-DUP fails. Nothing else is read. It goes back to the Developer (B-OFF, B-KEEP, B-DUP, B-WIRE) or to QA's harness (B-NAT), and the arm is re-run once on the fixed build. No bar moves.
- **If no validity row failed:**
  - **ACCEPT** iff N-GO, U-OK, B-AB and B-LATE all pass;
  - **FAIL** iff N-STOP or U-FAIL;
  - **OPEN** otherwise.
- This replaces §3's verdict block.

**A1.3 (K3) The 40 m trigger moves to tested_absent. It fires, and the bar is ruled now, before Stage 0.**
- **On file (QA, arm A, 500 cycles, `cf_uprime off`, null p99 0.293 vs T 0.276, no flag):**

  | quantity | 40 m (this night) | 20 m nights on file |
  |---|---:|---|
  | tested_absent per cycle | 0.136 | 0.0375 and 0.0663 |
  | U′0 total per cycle | 0.558 | 0.186 (960 cycles) and 0.288 (799 cycles) |

- On the total, my §3 trigger does not fire (1.94× the highest 20 m value). **On tested_absent, the bar's own quantity, it does: 2.05× the highest, 3.6× the lowest.** QA is right that the trigger belongs on the bar's quantity.
- **Ruling: the U bar stays 0.021 per cycle, as an ABSOLUTE added rate.**
  - The bar was ratified (COH-GATE-G, 2026-10-28) as the Captain's tolerance for **added** wrong decodes in his log: one more unconfirmed, signal-absent decode about every 48 cycles (≈ 12 min).
  - That tolerance is about his log, not about the band. A busier band with more background `tested_absent` is no reason to admit more of them from a new lever.
  - Scaling the bar by 2.05× (to ≈ 0.043) would loosen it after seeing arm A's data. I don't do that.
  - ΔU′_ta counts **only B's new-text rows**, so the higher 40 m baseline does not enter the difference directly. It enters only if the gate admits more signal-absent rows on a denser band, and **that is exactly the risk the test should see.**
- **Consequence, stated:** on 40 m the test is harder than on the 20 m nights the bar came from. A FAIL here may be partly the band.
  - If the result is U-FAIL with N-GO, the ruling will say so, but **the verdict stands as registered.**
  - The Captain may still change the bar, but only **before** Stage 2's arm B runs, never after.
- `kept_TA ≤ 4` (Stage 0, 20 m data) stays derived from 0.021 and is unchanged.

**A1.4 Predictions, restated BEFORE any Stage 0 output exists.**
- **CV-1 (FEASIBLE under A1.1): 0.30, H.** The stricter row needs a real separation, not just a large `kept_C`, and the multi-set branch of my reasoning is gone (A1.0).
- **CV-4: 0.45, H.** The 40 m night is harder (A1.3).
- CV-2, CV-3 and CV-5 are unchanged.

**Next:** QA runs Stage 0 (step 1: the 19 / 9 / 2 re-derivation; step 2: the selection; step 3: `p_perm`) and commits the record. Then I write the triple in, or recommend closing #272.

## §9. Amendment 2 (2026-11-12 13:49:31Z, `date -u`): Stage 0 is FEASIBLE; the gate is frozen

**Record:** `qa/rr-study/2026-11-12-1352-qa-coh-res-cand-v2-stage0-record.md` (`qa/same-chain` `271b5562`, local).
- Script frozen first at `3fd08b02`. `stage0.py` blob `18f230e7…`, `p0_null.py` blob `7935a226…` (= `1fe6b588`'s).
- `p0_rows.csv` prefix `5a4ff618…`, `stage0_result.json` prefix `b31e81eb…`.

| step | result |
|---|---|
| 1 (stop rule) | P0 149 = C 119 / TA 19 / tested_present 9 / hashed 2 / untestable 0. Identical to #272's report in every cell, so it does not stop |
| 2 (selection) | **`freq ≤ 1097` Hz.** kept_C **57** of 119, kept_TA **4** of 19 (at the cap), kept_other 5 of 11 |
| 3 (`p_perm`) | **0.0476** (238 of 5,000; limit 0.05, met by 12 permutations; MC standard error ≈ 0.003) |
| verdict | **FEASIBLE** by the registered rows |

**A2.1 The gate, frozen. It replaces "the Stage 0 triple (f, d, t)" everywhere in §2–§3.**
- A row of the new run that is new text (R4) is **kept iff its frequency, as the published integer Hz of that row, is ≤ 1097.** Otherwise it is dropped and counted in `resNewGated`.
- **The Developer cites the file:line where the published integer Hz is formed**, and applies the gate to that same value (not to an unrounded internal frequency). R8's boundary test uses 1097 (kept) and 1098 (dropped).
- `freq` is the audio offset in the passband. It means the same on 20 m and 40 m.

**A2.2 What the verdict is worth, said plainly (no rule changes).**
- FEASIBLE is **narrow**: `p_perm` sits about 0.8 MC standard errors under the limit. A different seed could have landed on either side. The seed was frozen, and no other seed is run.
- **No mechanism is known** for wrong payloads sitting above 1,097 Hz. `snr` came within 2 rows (55), so the data does not really prefer frequency over SNR.
- A frequency threshold also depends on where stations sit in the passband on a given night. **On 40 m that is different activity, so the gate may not transfer.**
- kept_TA is at its cap, and the gate drops 62 of 119 good rows on P0.
- **Stage 2 exists to answer exactly this.** It is one arm on a night the gate never saw. I do not overrule a registered FEASIBLE with doubts formed after its data, and I do not add a row now.

**A2.3 Predictions.** CV-1 is scored: **HIT (P 0.30)**, but my reasoning (an SNR gate) was not borne out. These are restated **before any build or Stage 2 data**, on Stage 0's evidence of a fitted, mechanism-less, at-chance-margin gate:
- **CV-4 (U-OK): 0.45 → 0.35, H.**
- **CV-5 (ACCEPT): 0.35 → 0.25, H.**
- CV-2 and CV-3 are unchanged.

**A2.4 The ceiling, for the Captain's go.** On P0, the 57 kept good rows are ≈ **+0.46 pp** at #272's n_ref (57 / 12,292). With "add, don't replace", no A-row is lost by design. Stage 2's NET on 40 m will differ, and only it counts.

**Next: the Captain's go (or not) for the Developer session (Stage 1).**
- The cost if he says go: one Developer session, QA's HK-039 review, and about 50 min of PC (B-OFF about 3.5 min + arm B about 45 min, per QA's stamps).
- If he declines, v2 closes at this record, and I recommend closing #272 on the issue.
