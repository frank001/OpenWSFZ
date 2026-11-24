# Developer task: XC-BUILD remedy, R14 (co-location veto) and R15 (parity-block gate) for the batch-6 template stage, on top of `f82b6432`, default OFF as before

**Date:** 2026-11-14
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off before merge, HK-010; the Captain can stop this work at any point, the Architect's spec says so)
**Authorised by:** the Captain's build go of 2026-11-13 13:58Z ("go, don't wait for me"), which the Architect applies to this remedy (spec §13, Amendment 6, `arch/cross-cycle-prior` `c0b61532`), and QA's (k) review `qa/rr-study/2026-11-14-0231-qa-k-review-xc-build-amendment-6.md`.
**Status:** Proposed. HK-011: a `src/` change for a separate Developer session. 🛑 **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative.** QA pushes (HK-033), after QA's HK-039 review, the acceptance arms and `pre_merge_check.py` (HK-006).
**Spec (read §13 and QA's review; the earlier task `dev-tasks/2026-11-13-xc-template-build.md` still applies for everything not changed here):** `git show arch/cross-cycle-prior:qa/rr-study/2026-11-13-1258-architect-to-qa-spec-xc-template-build.md`, §13 A6.1 to A6.3. The reason in one line: on the night `20260808_0016`, 641 of the build's 2,579 batch-6 publishes were a stale template scored on the same station's next, different message (QA's XC-SUP, `2026-11-14-0221`), so `f82b6432` cannot be turned on as it is.
**Branch:** continue on **`feat/xc-template-prior`** from `f82b6432` (new commits on top; the earlier review stands for the commits it covered, the new commits get their own HK-039 record). Never commit to `main`.
**Version:** the branch already carries VERSION 0.72 for this feature; a further bump only if `python tools/check_version_bump.py origin/main` demands it. **No `native/` change** (the DLL SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` stays); if you find you need one, stop and report.
🔒 NFR-021: Q-prefix calls only in tests; **counts and numbers, never text or calls, in the log line and in the sink**.

---

## 0. Why (the mechanism, so you can build the right thing)

The FT8 frame is S7 · D29 · S7 · D29 · S7 (79 symbols). Data symbols 30 to 58 (frame symbols **43 to 71**, codeword bits 87 to 173) hold the CRC's tail and the LDPC parity, so **any change to the message re-draws that block almost at random**; a stale template matches about 1/8 of its symbols there, however strong the station is. The sync and callsign symbols that make S_E high lie outside it. QA's P0 measured it on 432 real pairs: sync 21/21, data block 1 20.0/29, **data block 2 3.94/29 (chance 3.63)**. A true repeat matches block 2 as well as the rest.

## 1. What to build

| Id | What |
|---|---|
| **R14 Co-location veto** | A template detection is **not published** if batches 1 to 5 of **cycle t** hold a decode with a **different text** at \|Δf\| <= 3.125 Hz and \|Δdt\| <= 0.2 s of the detection's argmax. **Convention:** your B1 fix works in WSJT-X's dt (minus `DELTA_P` 0.6 s) inside the detector; the batch 1 to 5 `DecodeResult.Dt` is in our own convention. **Convert the argmax back (plus `DELTA_P`) before the comparison**, so both sides are in our own dt, and say in the report which constant you used. Counted as `vetoed-colocated`; it applies to **shadow detections too**, counted separately. **A replay setting `SetCrossCyclePriorColocationVeto(bool)` (`internal`, like the T_E setter), default `true` in the product.** |
| **R15 Parity-block gate** | **S_P** = the R5 statistic restricted to **frame symbols 43 to 71** (29 symbols; same per-symbol ratio `P[tone] / ((1/8) Σ_b P[b])`, a symbol with no power counts 1, mean over those 29), computed **from the same correlations at the S_E\* argmax, with no separate search**. **Detected ⇔ S_E\* ≥ T_E and S_P ≥ T_P.** A template that clears T_E and fails T_P is counted `parity-rejected`, live and shadow separately. **T_P is a named constant, placeholder `0.0` in this build (no gating; QA's TR2 measures the real value, which goes in before any merge), settable for replay through an `internal` setter with read-back**, exactly as T_E is. |
| **R13 Sink (amended)** | Per tested template, live and shadow, **numbers only**: the existing fields plus **S_P**, **the prior's own position (frequency Hz, dt in our own convention) and its batch (1 to 5)**, and a **`vetoed` flag** (R14 would have vetoed it; in a run with the veto off it is counted, not applied). This is what lets QA tell which test carried which text (QA's K1). |
| **R10 Log line (amended)** | Adds counts: `vetoed-colocated` (live / shadow), `parity-rejected` (live / shadow). Still counts only. |
| **R11 OFF is unchanged** | Both existing flags OFF: published rows of every cycle identical to the build without the stage (QA's V-OFF compares OFF against `f82b6432`'s TEST OFF output, the per-cycle multiset of (batch, text, freq, dt, snr) plus the per-batch counts). **No new work, state write or allocation on the OFF path.** |
| **Read-back** | The existing decoder read-back line (the one the harness parses) gains **`xcveto=<True/False>`** and **`xctp=<value>`**, so every arm can assert them (K6). |

## 2. Fixtures and tests (TESTING_STRATEGY §11: no fixed sleeps; CI runs macOS and Linux; each test must be able to fail, QA mutates)

**Fixtures:** `dev-tasks/2026-11-14-xc-remedy-fixtures.json` (generator `qa/xc-build/xc_remedy_fixtures.py`, on `qa/same-chain`; same buffer recipe as `2026-11-13-xc-template-fixtures.json`). Cases carry `expected_S_E_star`, **`expected_S_P_at_argmax`** and the argmax, tolerance 1e-3 relative. Two to look at first: **`STALE_next_message_same_position`** (S_E\* 5.08, **S_P 0.84**: it clears any T_E and must fail a T_P near 1.9) and `found_at_centre` (S_E\* 7.55, S_P 7.59).

**Tests to add (the Architect's list plus QA's):**
1. A synthetic station whose **next message differs** (report or RR73) at the prior's exact position: the old template is **not published** with T_P set at 1.9 (parity gate) and **is published** with T_P = 0.0 (so the test can fail in both directions).
2. The **same message repeated**: it is published at T_P = 1.9.
3. A batch 1 to 5 decode with a **different text** in the window: the detection is **vetoed**; the same decode with the **same text**: not vetoed (the existing "already decoded" exclusion applies first).
4. **R14 boundary, in our own dt:** a decode at +0.19 s from the argmax vetoes, at +0.21 s does not; at 3.0 Hz vetoes, at 3.2 Hz does not. This is where a convention slip would be silent.
5. **The frame indices 43 to 71 asserted against the encoder:** encode two messages that differ, and assert the sync symbols and data block 1 positions used by the code are the ones the encoder places there, and that the 29 indices of block 2 are exactly 43..71 (QA's P0 as a unit test).
6. **Defaults:** `SetCrossCyclePriorColocationVeto` default is `true`; T_P default `0.0`; the read-back line shows both.
7. **Sink:** one record per tested template carries S_P, the prior's position and batch, and `vetoed`; no text. **Log line:** the two new counts appear, counts only.
8. **OFF path:** both flags OFF writes nothing new (extend your existing OFF test to the new fields).

## 3. Not in this build

No change to batches 1 to 5, the fallback, the late round, F1b, R-F4, multi-set, L1′, CQ-AP, v2, the 13 s budget, `native/`, T_E's value, or the Settings page. **No default ON.** **No T_P value other than the placeholder** (QA's TR2 on the TRAIN night measures it; a value chosen on the TEST night is not allowed).

## 4. What QA will check (so you build for it)

- **B-NAT:** `git diff --stat f82b6432 <your commit> -- native src/OpenWSFZ.Ft8/Native` empty; DLL SHA-256 = `bbde6eb6…6528`.
- **V-OFF:** OFF-T (the remedy build, TEST night, both flags off) against `f82b6432`'s TEST OFF output: equal, or STOP.
- **V-TE:** TR2 reproduces TR1's shadow scores: 23,219 shadow tests and T_E 3.076041980658299 to 1e-6, else STOP (R5 must not move).
- **Numerics:** the fixtures; and QA compares your S_P with `xt_lib` on 200 real (cycle, template) pairs of the TRAIN night before any arm.
- **K6:** the read-back tokens per arm.
- Then QA's HK-039 review record (`Reviewed-commit:` + `Verdict:`) comes **before any acceptance run**; a hook refuses the launch otherwise.

## 5. Questions to answer in your report

1. Which constant converts the argmax back to our dt for R14, and where.
2. Where S_P is computed (the same correlation matrix, no second pass) and the added cost per template.
3. What the shadow does under R14 and R15 (it is vetoed and parity-gated like live; confirm the counts are separate).
4. Where `xcveto` / `xctp` are formed in the read-back line.
5. Anything in R14/R15 that cannot be done without a change outside the template stage (stop and say).

## 6. Gates you run before handing back

As in the 2026-11-13 task: the full unfiltered `dotnet test OpenWSFZ.slnx -c Release` (exact command line and per-project counts, HK-022), `openspec validate --all --strict` (extend the change's `design.md` and delta spec with R14, R15 and the sink fields; QA adds `tasks.md`), `python tools/check_version_bump.py origin/main` after committing, the traceability gate (G3) clean (a new test or two with the FR number in the DisplayName). 🛑 **Do not run `pre_merge_check.py`.**

## 7. Stop-and-tell conditions

Stop and report to QA, without building around it, if: S_P cannot be formed from the existing correlations; the argmax cannot be converted to our dt without ambiguity; OFF would have to change; the fixtures cannot be matched within tolerance; R14 needs a decode list the stage does not have at that point (cycle t's batches 1 to 5).

## 8. Report back (HK-001 sections), then STOP

The commit hash(es); the §1 table answered row by row with FILE:LINE; the §5 answers; the fixture results per case (including the stale case's S_E\* and S_P); the test list with what each asserts; the command lines and counts of the full suite; deviations and why. **Then stop**: QA reviews, runs the arms and decides what happens next.
