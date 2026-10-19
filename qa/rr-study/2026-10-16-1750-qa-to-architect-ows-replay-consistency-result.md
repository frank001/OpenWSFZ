# Result: OWS-REPLAY-CONSISTENCY, sweep 1 (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-16 17:50Z (`date -u`). **Spec:** `2026-10-16-1635-architect-to-qa-spec-ows-replay-consistency.md` + amendment 1 (`arch/ows-replay-consistency` `f44b8140`).
- **Scope line:** B2BASE sweep 1 only, `sol` (FX-8350), build `338ef61c` shim 20260062, non-default ALSA chain, S6 SEQUENTIAL, standard tier (60 WAVs x 3 trials, 180 plays). Replayed audio through the product's real decode call (`DecodeTwoStageAsync`), not the station's live operation. No decode-rate claim; nothing about "better" or "worse"; nothing about the Windows station.
- **Status:** sweep 1 (R-A, R-W, R-D8) done. Sweeps 2-5 (R-A, R-W replication) **not run**, waiting for the Captain's go. R-D1 **not run**: its condition (D8 (i) < 100 %) did not hold.
- **Evidence:** `qa/rr-study/ows-replay-consistency/sweep1_result.json` (aggregates only), `sweep1_run.log`. Tooling: `qa/rr-study/s6/ows_replay_consistency.py`, `run_ows_consistency.sh`, `refset/harness/Program.cs --wavlist` (commit `eb1e8120`). Working files (message text) are in `~/qa-scratch/ows-consistency/` on `sol`, outside git, to be deleted at job close.
- **Command:** `run_ows_consistency.sh <sweep1> <sweep1-captured-audio> sweep1 build 873287b1…ab03ac6a A W D8`; no `--filter` applies (not a test run). Pin actual = pinned = `873287b114a8674f800d4816fd5362c51175fc050e535d190516e01dab03ac6a`.

## Validity (all PASS)

| row | result |
|---|---|
| V1 | `libft8.so` SHA equal at start and end of all 5 runs; readback nhard 24, kMinScorePass2 10, osdCorrThreshold 0.1, threads 8, subtraction ON, OSD sign fix 1, shim 20260062 |
| V2 | 180 of 180 plays map to one archive file and one save WAV |
| V3 | every run decoded 180 of 180 items |
| V4 | L recomputed 71.55 % = report 71.55 %; C_w recomputed 93.89 % = report 93.89 % |
| V5 | 0 untagged decodes |

Residual passes abandoned: **0 of 177 in every run** (R-A, R-W, R-D8 x 3). Live S6 had 0 of 900. Archive health: 0 of 180 cycles with clipped samples, 0 with a drop before. Wall time per run: R-A 652 s, R-W 723 s, R-D8 653 / 652 / 652 s (about 3.6-4.0 s per cycle).

## Rows (WAV-clustered bootstrap, 2,000 resamples of the 60 WAVs, paired by WAV)

| row | figure | reading (mechanical) |
|---|---|---|
| **X0** replay vs live | A 71.55 %, L 71.55 %; A - L 0.0000 [0.0000, 0.0000]; 100 % of live non-hashed rows reproduced, 0 extra rows | descriptive. CI contains 0: the replay reproduces the live decode on this sweep exactly; no "replay != live" label |
| **X1** candidate 1, determinism | D8 (i): **180 of 180 plays identical** in all 3 repeats (including the reported SNR); D8 (ii) 100 % | **does not fire.** The decoder is deterministic on identical audio at 8 threads with the default budget. R-D1 not needed |
| **X2** candidate 2, input | D8 (ii) - A = +28.45 pp [21.21, 36.01] | label: **"100 % - A: derived, not a finding"** (D8 (i) = 100 %). The sign is arithmetic. What it does say is that the whole 28.5 pp lost to inconsistency on OpenWSFZ's own captures is lost to the INPUT differing, none to the decoder |
| **X3** OpenWSFZ's capture vs WSJT-X's | W 90.33 %, A 71.55 %; W - A = **+18.78 pp [12.38, 25.44]** | fires, positive: **OpenWSFZ is more consistent on WSJT-X's three captures than on its own three** (capture or framing side) |
| **X4** candidate 3 | W 90.33 %, C_w 93.89 %; W - C_w = **-3.57 pp [-6.28, -0.79]** | fires, negative. Label: **sensitivity or threshold density, not separated** |

## Descriptive (no verdict)

- **By batch** (consistency with each trial restricted to that batch's decodes): A batch 1 (pass 0) 76.7 %, batch 2 (residual pass) **27.4 %**; W batch 1 92.5 %, batch 2 71.4 %; D8 (ii) 100 % in both. The flicker sits mainly in the residual pass.
- **By own reported SNR** (n signals, consistency): A: <= -18 dB 67, 35.8 %; -17 to -10 dB 308, 65.3 %; >= -9 dB 465, 80.9 %. W: 61, 65.6 %; 324, 85.2 %; 504, 96.6 %. C_w (WSJT-X): 144, 75.7 %; 387, 92.8 %; 664, 98.5 %. Every program is less consistent at lower SNR; OpenWSFZ on its own captures is the lowest in every bin.
- **Common set** (signals both programs decoded at least once on the same three save WAVs, matched on the key, binned by WSJT-X's SNR), W vs C_w:

| WSJT-X SNR bin | n common | OpenWSFZ on those captures (W) | WSJT-X (C_w) | W - C_w [WAV-clustered 95 % CI] |
|---|---|---|---|---|
| <= -18 dB | 48 | 60.4 % | 97.9 % | -37.5 pp [-53.2, -20.5] |
| -17 to -10 dB | 253 | 83.0 % | 99.6 % | -16.6 pp [-21.6, -12.0] |
| >= -9 dB | 586 | 96.2 % | 99.7 % | -3.4 pp [-5.3, -1.6] |

  On the same signals at the same strength on the same captures, WSJT-X decodes almost all of them in every trial; OpenWSFZ does not, and the gap grows as the signal weakens. That is the line that bears on X4's confound (threshold density): it does not remove the difference, but it is the sample of signals where both programs succeeded at least once.
- **Not computed:** the input-difference line (the spread of `archive_xcorr`'s offset per WAV). It needs the played corpus audio and a cross-correlation pass. A separate step if the Architect wants it.

## What this says, and what it does not

- **Candidate 1 (non-determinism): not supported.** 180 of 180 identical. This is sweep 1, 3 repeats, 8 threads, default budget, 0 abandoned passes.
- **Candidate 2 (the input differs): supported as the whole of the replay inconsistency.** X2 is derived, but combined with X1 it means the 28.5 pp is entirely input-driven. X3 adds that the same decoder on WSJT-X's captures is 18.8 pp more consistent. The test cannot say which part of OpenWSFZ's capture and framing (positive clamps, realignment, resampling, level) makes its three captures differ more; it does not look inside the audio.
- **Candidate 3 (sensitivity): supported in the sense of X4 firing, not separated from threshold density.** The common-set table shows the gap on the signals both programs found, growing toward weak signals. Amplification is possible in the residual pass (a flicker in a pass-0 decode changes what is subtracted), which would fit the by-batch figure; that is a hypothesis, not tested here.
- All three can hold together; the sizes are not additive.
- **Predictions (Architect's ledger, for the Architect to score):** RC-1 (X1 fires, 0.50): did not fire. RC-2 (X2 fires, 0.65): numerically positive, but derived under amendment 1. RC-3 (X4 fires, 0.70): fired.
- **Limits.** One sweep (the primary); replication on sweeps 2-5 is pending. One host, one build, one chain. A capture's "more consistent" is a property of this test's inputs, not of either program's live operation.

## Cost

Build and unit tests: 9 toy-set tests, 48 passing with the analyser's. Pilot 80 s. Sweep 1 runs: 652 + 723 + 3 x 652 s = 55 min wall, `sol` idle otherwise.

## NFR-021

Aggregates only; `sweep1_result.json` and this report scanned for callsign patterns: none.
