# Result: OWS-REPLAY-CONSISTENCY, replication on sweeps 2-5 (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-16 19:30Z (`date -u`). **Follows:** `2026-10-16-1750-qa-to-architect-ows-replay-consistency-result.md` (sweep 1, ruled).
- **Scope line:** B2BASE sweeps 2-5, `sol` (FX-8350), build `338ef61c` shim 20260062, non-default ALSA chain, S6 SEQUENTIAL, standard tier (60 WAVs x 3 trials, 180 plays per sweep). Replayed audio through `DecodeTwoStageAsync`, not the station's live operation. No decode-rate claim; nothing about "better" or "worse"; nothing about the Windows station. **Per sweep, never pooled.**
- **Runs:** R-A and R-W per sweep (1 repeat, 8 threads, default budget); no R-D (X1 did not fire in sweep 1). Driver `run_ows_consistency.sh <sweep> <audio> <work> build 873287b1…ab03ac6a A W`; no `--filter`. Pin actual = pinned = `873287b114a8674f800d4816fd5362c51175fc050e535d190516e01dab03ac6a`.
- **Evidence:** `qa/rr-study/ows-replay-consistency/sweep{2,3,4,5}_result.json` (aggregates only). Working files with message text stay in `~/qa-scratch/ows-consistency/` on `sol`, outside git, deleted at job close.

## Validity

**V2 (added 2026-10-16, on the Architect's ruling):** per sweep, every play maps to exactly one archive file and one save WAV: sweep 2 180 of 180, sweep 3 180 of 180, sweep 4 180 of 180, sweep 5 180 of 180 (both lists; 0 files missing; 180 distinct paths in each list). Source: the `make_lists` output line in the driver log (`plays 180, missing_archive 0, missing_savewav 0, v2 PASS`, one per sweep), re-checked on `sol` against the written lists (`archive_o.tsv`, `savewav_w.tsv`: 180 lines, 180 distinct existing paths each). No re-run. The V2 line is not in the sweep JSON validity block, which holds V1, V3, V4, V5; it is recorded here and in `sweep_v2_record.json`. All four sweeps are at 180, so X3 and X4 for sweeps 2-5 stand.

V1 pins equal at start and end in all 8 runs; V3 180 of 180 per run; V5 0 untagged; V4 L and C_w recomputed equal the sweep's report figures in all four sweeps. **Residual passes abandoned: 0 in all 8 runs** (174-177 passes per run). Archive health: 0 of 180 cycles with clipped samples or a drop before, in every sweep. Wall time per run 634-657 s (R-A), 718-721 s (R-W).

## Rows, per sweep (WAV-clustered bootstrap, 2,000 resamples of the 60 WAVs, paired)

| sweep | X0: A = L | X0: live rows reproduced / extra | X3: W (OWS on WSJT-X's captures) vs A (own) | W - A [95 % CI] | X4: C_w (WSJT-X) | W - C_w [95 % CI] | X4 fires |
|---|---|---|---|---|---|---|---|
| 1 (ruled) | 71.55 % = 71.55 % | 100 % / 0 | 90.33 % vs 71.55 % | +18.78 pp [12.38, 25.44] | 93.89 % | -3.57 pp [-6.28, -0.79] | yes |
| 2 | 63.26 % = 63.26 % | 100 % / 0 | 91.16 % vs 63.26 % | +27.90 pp [19.30, 36.86] | 93.72 % | -2.57 pp [-5.54, +0.19] | no |
| 3 | 74.13 % = 74.13 % | 100 % / 0 | 89.88 % vs 74.13 % | +15.74 pp [9.25, 23.38] | 93.87 % | -3.99 pp [-7.43, -0.95] | yes |
| 4 | 74.79 % = 74.79 % | 100 % / 0 | 91.64 % vs 74.79 % | +16.85 pp [9.35, 24.86] | 93.54 % | -1.90 pp [-4.53, +0.77] | no |
| 5 | 71.48 % = 71.48 % | 100 % / 0 | 93.10 % vs 71.48 % | +21.62 pp [14.45, 29.25] | 94.36 % | -1.25 pp [-3.60, +0.90] | no |

Every X0 difference A - L is exactly 0.0000 [0.0000, 0.0000]: the replay reproduces the live decode on all five sweeps.

## Reading (mechanical, per sweep)

- **X0:** replay = live in 5 of 5 sweeps.
- **X3 fires positive in 5 of 5 sweeps**, every CI excluding 0 (range +15.7 to +27.9 pp). OpenWSFZ is more consistent on WSJT-X's three captures than on its own in every sweep. OpenWSFZ's own consistency moves most between sweeps (63.3 to 74.8 %); on WSJT-X's captures it is steadier (89.9 to 93.1 %).
- **X4 (label "sensitivity or threshold density, not separated") fires in 2 of 5 sweeps** (sweeps 1 and 3); in 3 of 5 the CI includes 0 (sweeps 2, 4, 5). The point estimate is negative in all five (-1.3 to -4.0 pp). No pooling, so no combined verdict; the count is 2 of 5.
- **Common set (W - C_w, point estimates; WSJT-X SNR bins <= -18 / -17 to -10 / >= -9 dB):** sweep 2: -17.8 / -16.2 / -3.9 pp (n 45 / 247 / 587); sweep 3: -28.6 / -20.1 / -3.4 pp (49 / 254 / 584); sweep 4: -20.5 / -16.5 / -3.1 pp (44 / 248 / 579); sweep 5: -22.2 / -12.4 / -2.2 pp (45 / 241 / 582). Sweep 1 was -37.5 / -16.6 / -3.4 pp. The gap on signals both programs decoded is negative in every bin of every sweep and grows toward weak signals.
- **By batch** (own-capture A, pass 0 / residual pass): sweep 2 67.3 / 24.8 %; sweep 3 77.2 / 43.0 %; sweep 4 78.8 / 35.2 %; sweep 5 75.1 / 35.7 % (sweep 1 76.7 / 27.4 %). On WSJT-X's captures (W): sweep 2 92.5 / 73.9 %; sweep 3 91.7 / 68.3 %; sweep 4 93.1 / 68.4 %; sweep 5 94.0 / 76.3 %. The residual pass is the least consistent batch in every sweep, on either input.

## What this adds, and what it does not

- Sweep 1's picture repeats: the decoder is deterministic (sweep 1, X1), the replay equals live, the inconsistency follows the input (X3 in 5 of 5), and a smaller part remains on identical captures (X4 in 2 of 5; the common-set gap in all).
- X1 was measured on sweep 1 only. It was not repeated on sweeps 2-5.
- The step that would say what in OpenWSFZ's capture and framing differs is the input-difference line (`archive_xcorr` offset spread, for both appraisers, A below/above the median spread). Not computed here; it is the Architect's second next step, awaiting the Captain's go.
- One host, one build, one chain; five sweeps of the same 60 WAVs, so the sweeps are not independent samples of the audio.

## NFR-021

Aggregates only; the four result files and this report scanned for callsign patterns: none.
