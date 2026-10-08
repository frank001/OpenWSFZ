# OSD-FIX Amendment: TRAIN runs interleaved (7 rounds × 7 arms), with full statistics reported after every round

> **Revised 2026-10-08 17:57Z (by `date -u`), before any TRAIN decode.** The Captain asked: *"why are you so anal about not looking at the data before all the arms are done? just report the statistics between each round. what is wrong with that?"* The Architect agrees. TRAIN only **calibrates** `n*`. The verdict comes from TEST, on cycles that played no part in choosing anything, and TEST stays blind. So looking at TRAIN between rounds cannot manufacture a false F-GO; at worst it gives a noisier `n*`, which TEST then reads as F-NEUTRAL. §5 is rewritten accordingly. The original data-blind version is in commit `e5569303`.

- **From:** Architect. **To:** QA. cc Captain. **Date:** 2026-10-08 17:45Z (by `date -u`, HK-017).
- **Asked for by:** the Captain, in the Architect's window. He asked *"can the arms be interleaved?"*, then answered *"yes"* to "Shall I write the amendment?".
- **Status:** a **pre-decode** amendment to spec `2026-10-07-1545` §5.2 (the header allows these). **No TRAIN decode has run.** PEEK-100 (`2b346822`, QA `71f38534`) ran on 100 TRAIN cycles at REF and FIX(40). It is descriptive and changes nothing here (§6).
- **What changes:** only **how TRAIN is scheduled**, **what is reported between rounds** and **when it may stop**. The arms, the grid, the `n*` rule, the B1/B2 rulings, the estimands, the match rule, the validity rows, TEST and its verdict rows are all **unchanged**.

## 1. Why

Run arm after arm, TRAIN gives no answer until all six deciding arms are done (about 7–8 h), and the load on a shared PC falls on different arms at different times. Interleaved, every completed round is a balanced, paired comparison on the same cycles, load drift spreads across arms, and a failed process costs about 10 min instead of about 1.3 h.

## 2. Chunks (mechanical, committed before any TRAIN decode)

- Source: the frozen `selection.json` (`qa/osd-fix` `1f30263b`, SHA-256 LF `27bb840f…db11e`), list `TRAIN` (621 cycles), **in its stored order**.
- **7 chunks of contiguous slices:** chunks 1–6 have 89 cycles each and chunk 7 has 87 (6 × 89 + 87 = 621).
- **Warm-up (one cycle, decoded and discarded, as Replay81 does now):** chunk 1 uses the file's own `warmup` (`261004_163400`). Chunk k > 1 uses the **last cycle of chunk k − 1**. That cycle is scored once in chunk k − 1 and is never scored as a warm-up.
- QA writes the chunk files with a **committed script** and commits them, with each file's SHA, **before any TRAIN decode**. A test asserts that the 7 chunks, concatenated, equal `TRAIN` exactly (order and membership) and that no cycle appears twice.

## 3. Rounds and arm order

- **Arms (unchanged):** `REF` (switch 0, `nhard` 40), `FIX(40)`, `FIX(30)`, `FIX(24)`, `FIX(50)`, `FIX(60)`, `FIX(0)` (switch 1). Index them 0–6 in that order.
- **Round r (r = 1…7) = chunk r through all 7 arms.** Each arm × chunk is **its own fresh process**: DLL pinned at start and end, `osd_sign_fix` and `nhard` read back, V2′ probe after the warm-up (a miss stops that process, exit 5, as now).
- **Arm order within round r:** arm index `(j + r − 1) mod 7` for j = 0…6 (a cyclic rotation: REF runs first in round 1, last in round 2, sixth in round 3, …). Over 7 rounds every arm takes every position exactly once.
- **One process at a time.** No two arms ever overlap on the CPU. Ordinary PC use is acceptable (Captain, 2026-10-03). No live or overnight run and no build should overlap, because the decode-time row compares arms.

## 4. Validity per process, and re-runs

- Each process must pass V1 (pin), V2 (read-back + chunk SHA), V3 (0 access violations / contained exceptions / non-zero exits) and the V2′ probe.
- **A process that fails is re-run once, unchanged.** If the re-run also fails, the round is **incomplete**: QA stops TRAIN and flags the Architect with the failure. Nothing is scored.
- V6 (abandoned residual work ≤ 5 %) is evaluated **per arm over all completed rounds**, as in the spec.

## 5. Stopping, and what a stopped TRAIN means

- **After every completed round, QA reports the interim statistics, cumulative over all completed rounds:**
  - validity and wall time per process;
  - for each FIX arm against REF: NET and ΔU, each with a 95 % CI (the spec's bootstrap, blocks of 40 consecutive cycles, or the whole round if it is shorter);
  - NET and ΔU by batch (1 vs 2);
  - the `n*` the rule **would** pick on the rounds so far, labelled **INTERIM**.
  Every interim figure is marked "interim, k of 7 rounds". 🛑 None is citable as a TRAIN result. The expected noise after one round is about ±0.35 pp (PEEK-100 on 100 cycles gave [−0.14, +0.21]), against expected effects of about 0.1 pp. Early rounds **will** wobble.
- **The Captain may stop TRAIN at any round boundary, for any reason, including what the interim numbers show.** This is safe because TEST is the verdict and is untouched (header note).
- **What stays fixed after looking:** the grid, the `n*` rule, the arms and the chunks. If anyone wants to change one of them after seeing interim data, that is a new amendment, marked **post-data**, and the report says so.
- **TRAIN ends** when 7 rounds are complete or the Captain stops it. The final §5.2 estimands use **completed rounds only**, by concatenating each arm's per-cycle rows across rounds.
- **Minimum for the `n*` rule: 4 completed rounds (about 356 cycles).**
  - Where the 4 comes from (HK-038): NHARD-REP scored 311 cycles of this same night with a NET CI half-width of about 0.19 pp (`[−0.79, −0.41]`), which resolved its effect. Four rounds is the smallest round count at or above that size.
  - With **fewer than 4** completed rounds, TRAIN is reported **descriptive only**: no `n*`, no TEST. The Captain then decides with that data whether to resume, which continues at the next round in the same order.
- **Resuming** after a stop is allowed on the Captain's go and continues at the next round. It is not a re-start. If QA has computed the estimands at a stop of 4 or more rounds and the Captain then resumes, the `n*` that counts is the one computed at the **final** stop. The earlier one is reported beside it, marked as superseded.

## 6. Unchanged, stated so nobody has to infer it

- §5.2 rule: `n*` = among grid values with ΔU_TRAIN(n) ≤ 0, the largest NET_TRAIN(n); ties → the lower `n`; none ⇒ `FIX-NO-GATE`. B1: `FIX(0)` is descriptive, outside the rule. B2: no extension below 24; an upper-edge `n*` = 60 goes to the Architect before TEST.
- TEST (§5.3), the verdict rows, V5 and every descriptive row (by batch, by SNR band, OSD-accept `nhard` histogram, wall time, FP-watch) are as specified. Timing rows are now pooled per arm across rounds, which is the reason the rotation exists.
- The 100 PEEK-100 cycles are inside TRAIN. Their REF and FIX(40) results are known to QA and the Architect. That is disclosed, not corrected: the `n*` rule is mechanical, and those 100 cycles are 16 % of TRAIN.
- HK-037: ALL.TXT stays inside the matching function. Outputs are numeric. Run folders are copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\` when TRAIN ends.

## 7. QA's to-do before round 1

1. Chunking script + test (§2), chunk files and SHAs committed.
2. Round runner: rotation order (§3), one process at a time, per-process validity and one re-run (§4), a per-round report with the interim statistics (§5).
3. V2′ probe vectors recalibrated on DLL `2029b080…82bb` and committed **before any FIX decode** (ruling A3, unchanged).
4. Report "ready" with the expected wall time per round (from PEEK-100: about 815 s per 100 cycles ⇒ about 12 min per process, about 1.4 h per round).

Then TRAIN runs **round by round on the Captain's go in QA's window** (one go may cover several rounds).
