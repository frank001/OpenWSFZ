# Result: OWS-REPLAY-CONSISTENCY step 3, the shift test (sweep 1), and the spread line on sweeps 2-5 (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-16 20:40Z (`date -u`). **Spec:** `2026-10-16-2150-architect-...-shift-test-spec.md` + amendment 1 (`arch/ows-replay-consistency` `1806ee63`: S3 adopted, SV4 guards S1-S3, a non-firing S1 does not clear placement). The Captain gave the go in QA's window.
- **Scope line:** `sol` (FX-8350), build `338ef61c` shim 20260062, non-default ALSA chain (`samplerate_best`), replayed B2BASE audio, S6 SEQUENTIAL, standard tier (60 WAVs x 3 trials, 180 plays). Replayed audio through `DecodeTwoStageAsync`, not the station's live operation. No decode-rate claim; nothing about "better" or "worse"; nothing about the Windows station.
- **Tooling:** `qa/rr-study/s6/ows_shift_test.py`, `run_shift_arms.sh` (commit `cc6808ae`, 6 unit tests). Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/sweep1_shift_result.json`, `sweep1_shift_build.json`, `sweep{1..5}_input_spread.json`. Pin actual = pinned = `873287b114a8674f800d4816fd5362c51175fc050e535d190516e01dab03ac6a`. Cost: build 4 min, arms 724 + 685 + 710 s, analysis 1 min.

## Shift test, sweep 1

**Validity (all PASS).** SV1: pins equal at start and end in all 5 runs (Z, S, K, and the R-W and R-A references); readback nhard 24, kMinScorePass2 10, osdCorrThreshold 0.1, threads 8, subtraction ON. SV2: W_Z = 90.33 % = R-W's W exactly, 0 of 180 plays differ. SV3: 0 zero-filled plays in each of Z, S, K (0 %, not fill-affected). SV4: 10 seeded plays through `archive_xcorr`, S windows max error 0.0001 s, K windows 0.0009 s (bar 0.02 s, from `sweep1_input_spread.json`'s WSJT-X p90 0.050 s halved). Abandoned residual passes: 0 of 177 in every run.

| arm | per-play shift of WSJT-X's window | own consistency over the 3 trials |
|---|---|---|
| Z (identity) | 0 | **90.33 %** (= R-W) |
| S (measured) | d = e_O - e_W | **85.46 %** |
| K (per-WAV constant) | mean d of the WAV | **89.31 %** |
| reference: R-A (OpenWSFZ on its own captures) | n/a | 71.55 % |

| row | figure (paired WAV-clustered bootstrap, 2,000 resamples) | fires |
|---|---|---|
| **S1** W_Z - W_S | **+4.87 pp [+2.05, +7.85]**; share of (W - A = 18.78 pp): **0.259 [0.113, 0.451]** | **yes** |
| **S2** W_Z - W_K | +1.02 pp [-1.26, +3.54] | no |
| **S3** W_K - W_S (QA addition, adopted) | **+3.85 pp [+1.72, +6.12]** | **yes** |

**Reading.**
- S1 fires: giving WSJT-X's stable captures OpenWSFZ's measured per-play placement error lowers OpenWSFZ's consistency by 4.9 pp. Placement alone, at the level of one median shift per play, accounts for about a quarter (0.26, CI 0.11 to 0.45) of the 18.8 pp between OpenWSFZ on WSJT-X's captures and on its own. The upper CI limit is below 0.5.
- S2 does not fire and S3 does: the mean lag alone does not lower it measurably; the trial-to-trial spread does (the direct contrast S3 is the reading; S2 is not read against S1).
- **Limit, as stated in amendment 1:** one constant shift per play does not model steps inside a window (the framer's -0.25 s realignment and any lost or repeated audio). S1's share is therefore what the median placement error alone does; the remaining three quarters are not explained by it. Level, the resampling chain and within-window steps remain untested. The decoder is deterministic (X1), so the loss in S is entirely due to the shifted input.
- By batch (descriptive): W_Z batch 1 / residual pass 92.5 % / 71.4 %; W_S 90.5 % / **39.1 %**. The placement effect lands almost entirely in the residual pass.
- Clamp lines against placement wander (descriptive, no verdict): 180 plays, 131 with at least one "Cycle-grid realignment clamped" line in the 10 cycles before their pass-O slot; Spearman rho between that count and |e_O - median e_O of the WAV| = **+0.023 (p 0.764)**. The log does not show an association, which does NOT test section 2's pointer well: 73 % of plays have a clamp line in that window, so the count barely varies. It neither supports nor refutes it.

## Spread line, sweeps 2-5 (replication of the sweep-1 step; per sweep, never pooled)

| sweep | OpenWSFZ capture spread: median / p90 / max (s) | WSJT-X: median / max (s) | A, upper - lower-spread half [95 % CI] | rho (A) [n 59-60] | W (OpenWSFZ on WSJT-X's captures) | C_w (WSJT-X's own) |
|---|---|---|---|---|---|---|
| 1 | 0.520 / 1.42 / 1.59 | 0.025 / 0.059 | -18.4 pp [-30.4, -5.2] **separates** | -0.23 (p 0.083) | -4.6 [-8.8, +0.0] no | -1.7 [-5.0, +1.5] no |
| 2 | 1.062 / 1.68 / 2.71 | 0.021 / 0.041 | -23.3 [-39.8, -5.5] **separates** | -0.34 (p 0.008) | -4.4 [-9.4, +0.4] no | +1.4 [-1.2, +4.1] no |
| 3 | 0.462 / 1.45 / 1.79 | 0.033 / 0.055 | -22.4 [-36.0, -9.9] **separates** | -0.39 (p 0.003) | -6.2 [-11.4, -1.2] separates | -0.5 [-4.0, +2.4] no |
| 4 | 0.485 / 1.62 / 2.49 | 0.030 / 0.055 | -24.3 [-37.4, -11.6] **separates** | -0.41 (p 0.001) | -4.7 [-9.8, -0.3] separates | +0.1 [-2.8, +2.8] no |
| 5 | 0.545 / 1.39 / 1.59 | 0.012 / 0.034 | -23.3 [-36.5, -11.1] **separates** | -0.42 (p 0.001) | -1.2 [-5.3, +2.9] no | -3.0 [-5.3, -0.7] separates |

- In every sweep OpenWSFZ's capture start wanders between trials by a median of 0.46 to 1.06 s (max 1.59 to 2.71 s), against 0.012 to 0.033 s (max 0.034 to 0.059 s) for WSJT-X. 60 of 60 WAVs had a spread in every sweep for both appraisers.
- The spread separates OpenWSFZ's own consistency in **5 of 5 sweeps** (-18.4 to -24.3 pp, every CI excludes 0); the rank correlation is significant (p <= 0.008) in sweeps 2-5 and not in sweep 1 (p 0.083).
- On WSJT-X's captures it separates OpenWSFZ's consistency in 2 of 5 sweeps (3 and 4) and WSJT-X's own in 1 of 5 (sweep 5, -3.0 pp); those effects are small (-1.2 to -6.2 pp). The medians are data-derived cuts: descriptive.

## What this does and does not say

- The spread line is replicated: an association between capture-start wander and OpenWSFZ's inconsistency in 5 of 5 sweeps.
- The shift test turns that association into a measured effect on one sweep: placement alone, as a median shift per play, accounts for about a quarter of the capture-side difference. RC-4 (S1 fires) and RC-6 (S2 does not fire) and RC-7 (S3 fires) are as predicted; RC-5 (share >= 0.5) is not: 0.26 [0.11, 0.45].
- The larger part of the capture-side difference is not explained by median placement. It may lie in the within-window steps (not modelled here), in level, or in the resampling chain; none of these is tested.
- One host, one build, one chain, sweep 1 for the shift test.

## NFR-021

Aggregates only; this report and the seven JSON files were scanned for callsign patterns: none. The shifted audio and the decode working files stay in `~/qa-scratch/ows-consistency/` on `sol`, outside git, to be deleted at job close.
