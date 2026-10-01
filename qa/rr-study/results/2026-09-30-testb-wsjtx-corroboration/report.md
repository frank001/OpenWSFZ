# Test B: WSJT-X corroboration of the flag-ON extra decodes (plausibility check on the endurance corpora)

| Field | Value |
|---|---|
| Run | 2026-09-30, 17:19:13Z to 17:35:26Z (orchestrator DONE, orphan check empty, 3 of 3 harness invocations rc 0) |
| Build | `feat/sub-feas-two-stage-publish` @`247ac391`; `libft8.dll` `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` = pinned |
| Harness / scripts | commit `14740bc0` (Replay81 with in-process scoring, `testb_run.py`, `testb_rows.py`), committed **before** the run; harness mode `two1` (flag ON, `DecodeTwoStageAsync`, one call per cycle, so the native call sequence equals S1's) |
| Cycles | the 161 E1 cycles (`e1_selection.json` SHA `f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2`), three runs: `20260922_2056` (49), `20260923_1730` (77), `20260925_2010` (35) |
| Consistency check | batch 1 = **3 842** decodes and batch 2 = **692** decodes, **exactly S1's totals** on the same cycles |
| Privacy | 🔒 HK-037: the match is done **inside the harness process**, where the decoded text lives in memory, against WSJT-X's `ALL.TXT` read in the same process; only **counts and stamps** were written. No message text, callsign or text-derived hash exists in any output. Committed: this report and the aggregate `rows.json` |

> **Bottom line.** **672 of the 692 flag-ON extra (residual) decodes, 97.1 %, were also decoded by WSJT-X in the same cycle**; the pass-0 control rate is 97.6 %.
> The 20 not-corroborated residual decodes are **2.9 %**, an **upper bound** on false positives among them, and 12 of the 20 sit in the weakest band (≤ −16 dB).
> **Descriptive plausibility check only: not the base change's §8.2 result, and no decode-rate claim.**

## Method (pre-registered in `testb_run.py`/`testb_rows.py` before the run)

A decode is **corroborated** iff WSJT-X decoded the **same message text in the same cycle within 10 Hz** (Amendment 1 / Stage 2 convention), paired **one-to-one nearest-first** across both batches, so a WSJT-X decode corroborates at most one OpenWSFZ decode.
Bands are by the OpenWSFZ decode's SNR: **A ≥ 0, B −10..−1, C −15..−11, D ≤ −16 dB**. **b1** (pass-0) is the **control**: how often WSJT-X also decodes what pass-0 decodes. **b2** (the residual decodes) is the question.
Intervals are 95 % **cluster-bootstrap over contiguous blocks** of cycles (busy cycles cluster, so the effective N is the block count: 159 blocks of 161 cycles), 4 000 resamples, seed 20260930.

## Results, all three runs pooled

| Band | b1 control: n / corroborated / rate [95 % CI] | **b2 residual: n / corroborated / rate [95 % CI]** |
|---|---|---|
| A (≥ 0 dB) | 920 / 903 / 98.2 % [97.3, 98.9] | 32 / 32 / 100 % [100, 100] |
| B (−10..−1) | 1 540 / 1 513 / 98.2 % [97.5, 99.0] | 275 / 270 / 98.2 % [96.1, 99.7] |
| C (−15..−11) | 773 / 753 / 97.4 % [96.0, 98.6] | 216 / 213 / 98.6 % [96.9, 100] |
| D (≤ −16) | 609 / 580 / 95.2 % [93.4, 96.9] | **169 / 157 / 92.9 % [88.1, 96.9]** |
| **All** | **3 842 / 3 749 / 97.6 %** | **692 / 672 / 97.1 %** |

Not corroborated, residual decodes: **20** in total: band B 5, band C 3, band D 12 (and 0 in band A).

## Per run (b2, residual decodes)

| Run | n | corroborated | rate | band D: n / corroborated / rate [95 % CI] |
|---|---:|---:|---:|---|
| 20260922_2056 (Voicemeeter B1) | 191 | 185 | 96.9 % | 48 / 43 / 89.6 % [79.6, 98.0] |
| 20260923_1730 (direct CODEC) | 373 | 361 | 96.8 % | 89 / 82 / 92.1 % [84.9, 97.8] |
| 20260925_2010 (direct CODEC) | 128 | 126 | 98.4 % | 32 / 32 / 100 % [100, 100] |

Control (b1) per run: 98.1 %, 97.1 %, 98.1 %. WSJT-X decoded 6 182 messages in these 161 cycles (1 811 / 3 186 / 1 185 per run); the pooled b1 and b2 corroborated counts together are 4 421 of them.

## What it says

1. **The extra decodes look real.** WSJT-X independently decoded the same message at the same frequency for **97.1 %** of them, about the same as for pass-0's own decodes (97.6 %). No band of the residual decodes is materially worse than its pass-0 counterpart **except possibly the weakest (≤ −16 dB)**, where the residual rate is 92.9 % against 95.2 % for pass-0; the intervals overlap ([88.1, 96.9] vs [93.4, 96.9]) and the difference is **not established** at this sample size. That is the one place a clustering of false positives could hide, and the band is small (169 decodes).
2. **"Not corroborated" is an upper bound on false positives, nothing more.** WSJT-X can miss a real weak signal, and **text equality is stricter than Stage 2's payload match**: a hashed-callsign placeholder rendered differently by the two decoders counts as a miss. The pass-0 control shows the size of that floor: **2.4 % of pass-0 decodes are also "not corroborated"** by the same rule, so a residual not-corroborated share of 2.9 % is close to the floor.
3. **Gross, descriptive arithmetic, with the caveats attached.** The corroborated residual decodes (672) are 10.9 % of WSJT-X's 6 182 decodes in these cycles. **This is not a decode-rate figure:** it is gross (no replay-versus-live control; the Stage 2 research found the original-PCM replay alone adds 0.76 points, and cited the **net** +8.89 pp [8.01, 9.75] after that control), it covers **busy cycles only** (≥ 20 first-pass decodes), and the corpora are **not independent** of the research corpus's neighbourhood. **Do not cite the 10.9 % without those three caveats.**

## Limits, stated up front (HK-026)

- **Not the base change's §8.2.** The corpora (same station, same bands, same period as the SUB-FEAS research) are not independent; §8.2 needs an independent corpus, which the overnight run may provide.
- **Busy cycles only**, 161 cycles, one machine, three runs; the weak-band sample is small (169 residual decodes in band D).
- **No false-positive rate is measured**: only an upper bound, and only against WSJT-X, which is not ground truth.
- **No decode-rate claim.** This is a plausibility check that the flag-ON extras are the kind of thing WSJT-X also decodes.
- Not done: the extension to all 905 §8.1 cycles (needs a ~90 min replay; a Captain's call).
