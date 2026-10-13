# (k) review of the S6-in-battery spec, and the build estimate (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 16:40Z (`date -u`).
- **Reviewed:** `2026-10-13-1625-architect-to-qa-spec-s6-in-battery.md` (`arch/s6-in-battery` `b76e8990`), against `harness/corpus_replay.py`, `analyse_corpus.py`, `analyse_corpus_anova.py`, `run_study.py`, `run_study_linux.py`, and STUDY-SPEC §6.1 and R&R-008. Desk work only; nothing was run on sol for this.
- **Verdict: ACCEPTED WITH 7 AMENDMENTS.** The shape is right (WAVs in, both appraisers, K = 3, one ANOVA, three tiers, informational first row). Items A1 and A2 change a row or a prediction; the rest add output or labels.

## Amendments

**A1. S6-V2 as written cannot fail (HK-021(k)).** "Every play attributed to exactly one cycle by its timestamp, 0 mis-attributions" is vacuous when attribution *is* the line's slot timestamp. And §2.3's restructure ("collect N's decodes while N+1 plays") is unnecessary: the matcher for S1–S8 already plays everything, then reads both `ALL.TXT` once at the end. S6 should do the same: a **play log** (slot boundary, WAV id, trial, `aplay` start offset) and one parse of both logs after the last play. That removes the 5 s settle and the snapshot code, and 15 s per play follows from the slot grid. Replace V2 by three mechanical checks, all counts:
1. every play starts within a stated offset of its slot boundary (bar from the existing runner's offsets, to be read from a S1–S8 play log before it is frozen, HK-038);
2. 0 decode lines stamped in an S6-window slot that has no play (stray lines);
3. 0 slots with two plays.

**A2. S6P2 is decorative, and κ needs its construction stated (HK-021(k), HK-025).** `analyse_corpus._kappa` takes its universe as the union of every signal either appraiser decoded in any trial of that WAV. The "neither decoded" cell is then non-empty **only through trial-to-trial variability**, so κ mostly measures that. Both earlier rows were 0.08–0.10 on this construction. "κ < 0.40" fires on the same construction whatever the decoders do ⇒ refuse S6P2 as a prediction or restate it. Add the **positive-agreement share** to §3 item 2: per trial, rows decoded by both over rows decoded by either (non-hashed), with a WAV-clustered bootstrap CI. That is the readable agreement figure and the one a change test can use. Keep κ and describe it as it is.

**A3. The ANOVA candidate set is conditional on detection.** Parts are the signals both appraisers decoded in all 3 trials, so repeatability is understated and ndc overstated (the signals that flicker are exactly the ones removed). Say so in the block, beside "x of y candidates". And add a **WAV-clustered bootstrap CI for %StudyVar and the variance components**: signals in one WAV share a cycle, and treating them as independent narrows every interval. Without it the first row has no precision and a later change test has nothing to compare against. Validation: the R&R-008 toy dataset is not in the tree, so QA regenerates one with known injected variances and asserts recovery within a stated tolerance, as a unit test.

**A4. Add a trial-index effect (§3 item 5).** Decodes per play by trial 1 / 2 / 3 for each appraiser. It catches cross-cycle state (the product's text-dedup and hash tables, WSJT-X's own history) that a random order alone would hide. The order effect (Spearman) stays.

**A5. Label the chain and the CPU.** S6 runs on the product path with the subtraction deadline ON, on an FX-8350, with WSJT-X decoding in real time on the same 8 cores. The first reference-set run found the residual pass alone at a median of 18.8 s against a 15 s cycle with the deadline removed. OWS's decode count on sol is therefore partly a property of this CPU and of WSJT-X's load. Label every row "sol, FX-8350, deadline ON, non-default ALSA chain" and record, as descriptive fields: the load average before and after S6, and the daemon's per-cycle abandonment or lateness if it logs one (QA checks). Never compare with the station.

**A6. Level and stratification, stated.** (a) The old `_load_wav` normalises every WAV to a peak level; both appraisers hear the same samples, so it is fair, but the level then differs from the live recording. Keep it if the Captain wants it, and record the applied gain per WAV in the wavlist. (b) The wavlist is band-stratified only. 15 WAVs per band at standard are enough for a descriptive per-band row with wide intervals, not for a comparison; the report says so. The corpus manifest carries the sun state per block, so the report adds counts by day / twilight / night with no quota.

**A7. Hashed rows.** The exclusion test is the text (`<...>` in the row), as the reference-set scorer does. A hashed call that later prints as a plain call after the history has resolved it cannot be recognised by text; that residue is covered by the order and trial-index effects, not removed. Say so in §2.5.

## Predictions

S6P1 (OWS consistency ≥ WSJT-X): fine, add the CI. S6P3 (interaction > repeatability): fine, measurable, and now testable with the clustered CI.

## Validity rows

V1, V3, V4, V5 are mechanical as written. V3's "≥ 1 decode each" needs the warm-up WAV to be the same Q-prefix synthetic cycle the battery already uses (not a corpus cycle), so the check cannot be passed by a stale line. V4 "= tier × 3" counts plays in the play log, not decodes.

## Build estimate (QA focused work; sol not needed except for the dry run)

| step | hours |
|---|---|
| tier list builder, hash verification, committed `s6-wavlist.json` | 1.0 |
| S6 player: play log, mechanical warm-up, pins start and end, 15 s grid, Windows and Linux playback | 2.5 |
| observation builder from the two logs, hashed exclusion, trial and slot indices | 1.5 |
| outputs 1–5 + positive agreement, clustered CIs, trial effect, per-band, figure | 2.0 |
| Section 5 block and Section 6 row, V1–V5, "withhold S6 only", `--scenarios S6` alone, both launchers | 2.5 |
| unit tests (ANOVA recovery, stray-line detection, hashed exclusion, tier prefix) | 1.5 |
| review, NFR scan, commit | 0.5 |
| **Total** | **≈ 11.5 h, two working sessions** |

Then the quick-tier S6-only dry run on sol: ≈ 18 min of play plus ≈ 25 min of start-up and shut-down, so about 45 min door to door. The first standard battery with S6 is about 45 min for S6 plus the existing S1–S8 time (roughly 2 h on sol), so about 3 h.

## Sequencing on sol (one resource)

Sol is busy with the WSJT-X keep-up run (started 16:24:45Z, ETA about 17:45–17:55Z). The old-CPU profile (separate spec) and the S6 dry run each need the Captain's go in this window, and none of the three overlaps another. I propose: keep-up run, then the profile (once `perf` is installed; it is not), then the S6 dry run when the build exists.

## Not changed

Tiers 24 / 60 / 180, K = 3, seed 20261013, the frozen corpus as source, informational verdict on the first row, bars proposed from the first standard row (HK-038), and the stop rule scoped to the S6 block (HK-025 (ab)).
