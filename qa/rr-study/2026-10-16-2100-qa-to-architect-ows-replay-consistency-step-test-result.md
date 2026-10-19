# Result: OWS-REPLAY-CONSISTENCY step 4, the step test (sweep 1) (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-16 21:00Z (`date -u`). **Spec:** `2026-10-16-2100-architect-...-step-test-spec.md` + amendment 1 (`arch/ows-replay-consistency` `e6db72f2`: unmatched chunks carry the nearest matched e(k); steps counted between consecutive matched chunks only; d_k = e_O(k) - median e_W of the play; 1 s resolution limit; leftover reads "not explained by timing at 1 s resolution"; split floor 10 WAVs). The Captain gave the go in QA's window.
- **Scope line:** `sol` (FX-8350), build `338ef61c` shim 20260062, non-default ALSA chain (`samplerate_best`), replayed B2BASE sweep 1 audio, S6 SEQUENTIAL, standard tier (60 WAVs x 3 trials, 180 plays). Replayed audio through `DecodeTwoStageAsync`, not the station's live operation. No decode-rate claim; nothing about "better" or "worse"; nothing about the Windows station.
- **Tooling:** `qa/rr-study/s6/ows_step_test.py` (commit `7007bea1`, 7 unit tests; 25 with the earlier suites). Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/sweep1_step_result.json`, `sweep1_step_build.json`. Pin actual = pinned = `873287b114a8674f800d4816fd5362c51175fc050e535d190516e01dab03ac6a`. Cost: build 4 min, arm P 670 s, analysis 1 min; `sol` otherwise idle.

## Validity (all PASS)

SV1: pins equal at start and end in all 5 runs (R-W, R-A, Z, S, P); 0 abandoned residual passes in each (arm P 0 of 176). SV2: W_Z = R-W, 0 of 180 plays differ. SV3: 0 zero-filled plays in arm P. **PV4:** 10 seeded P windows through `archive_xcorr`, 150 matched chunks compared, max error 0.0020 s (bar 0.02 s).

## Part 1: steps inside a window (descriptive)

**J = 0.0170 s** (the 99.9th percentile of WSJT-X's chunk-to-chunk |delta e| over its 180 windows, consecutive matched chunks only).

| appraiser | windows with >= 1 step | steps | size: median / max (s) | direction | within 0.05 s of a multiple of 0.25 s | within 0.05 s of exactly 0.25 s |
|---|---|---|---|---|---|---|
| OpenWSFZ (archive) | **21 of 180 (11.7 %)** | 21 | 0.338 / **1.595** | 21 positive, 0 negative | 14 of 21 (66.7 %) | 10 of 21 (47.6 %) |
| WSJT-X (save WAVs) | 3 of 180 (1.7 %) | 3 | 0.040 / 0.050 | 3 positive | 2 of 3 | 0 of 3 |

- Ratio of the shares 11.7 / 1.7 = **7.0**. (The 3 WSJT-X steps sit just above J, which is the p99.9 of its own deltas, and all lie at chunk 14.)
- All 21 OpenWSFZ steps are positive: source audio skipped, none repeated. **Position (the chunk at which the new e begins): 18 of 21 begin at chunk 3, 2 at chunk 2, 1 at chunk 4.** The steps cluster about 3 s into the window. This is a measurement, not an explanation.
- **A split (OpenWSFZ on its own captures), by WAVs with a step in any trial:** 19 of 60 WAVs have a step in at least one trial (both groups above the 10-WAV floor). Without a step (41 WAVs) A = **83.8 %**; with a step (19 WAVs) A = **41.6 %**; difference **-42.2 pp [-55.4, -27.4]** (unpaired WAV-clustered bootstrap), separates. A data-derived split: descriptive.

## Part 2: arm P (piecewise), sweep 1

| arm | own consistency over the 3 trials |
|---|---|
| Z (identity) | 90.33 % |
| S (median placement) | 85.46 % |
| **P (piecewise, per-chunk e(k))** | **72.66 %** |
| reference: R-A (OpenWSFZ on its own captures) | 71.55 % |

| row | figure (paired WAV-clustered bootstrap, 2,000 resamples) | fires |
|---|---|---|
| **P1** W_Z - W_P | **+17.67 pp [+11.01, +24.49]**; share of (W - A = 18.78 pp): **0.941 [0.809, 1.066]** | **yes** |
| **P2** W_S - W_P (the steps beyond the median placement) | **+12.80 pp [+6.45, +19.83]** | **yes** |

By batch (W_P): pass 0 77.6 % (Z 92.5 %), residual pass 31.3 % (Z 71.4 %).

**Remaining after P (reads only "not explained by timing at 1 s resolution"):** (W - A) - (W_Z - W_P) = 0.0111, i.e. 1.1 pp of the 18.8 pp. The CI of the share includes 1.0.

## Reading, and the limits

- Giving WSJT-X's stable captures OpenWSFZ's measured PER-CHUNK timing (repeats and discards included, at 1 s resolution) takes OpenWSFZ's consistency from 90.3 % down to 72.7 %, which is 94 % of the way to its consistency on its own captures (71.6 %). With the median placement alone (arm S) the loss was a quarter (0.26). Timing, measured at 1 s resolution, accounts for essentially all of the capture-side difference in this sweep, with the audio chain held fixed.
- The step part is concrete: 21 of 180 OpenWSFZ windows (11.7 %) contain a forward jump of source time, up to 1.6 s, mostly near 3 s into the window; WSJT-X's contain none beyond 0.05 s. The WAVs with a step are far less consistent (41.6 % against 83.8 %).
- **What arm P does not isolate.** P reproduces the whole per-chunk e(k) curve, including sub-J wander, not only the 21 windows' steps. P2 (+12.8 pp) says the structure beyond the median shift matters; it does not say how much of it is the >J steps and how much is smaller wander inside windows. Separating them would be another arm (e.g. steps only).
- **Resolution limit (frozen):** steps inside a chunk are placed at the chunk boundary; P reproduces e(k) at 1 s resolution only.
- Sweep 1 only; one host, one build, one chain. The arm used OpenWSFZ's measured placement from the archive WAVs; it does not say what disturbs the timing on these replays (the question #238 holds as a hypothesis), nor anything about the Windows station.
- **Predictions (Architect's ledger, for the Architect to score):** RC-8 (OpenWSFZ share >= 10 x WSJT-X's): 7.0, below 10 on the figures above. RC-9 (P2 fires): fired. RC-10 (P share >= 0.5): 0.94.

## NFR-021

Aggregates only; this report and the two JSON files scanned for callsign patterns: none. The shifted audio and decode working files stay in `~/qa-scratch/ows-consistency/` on `sol`, outside git, to be deleted at job close.
