# XC-ROUND: subtract the cross-cycle detections and run one more round

**Date:** 2026-11-27 · **Author:** QA · **Spec:** `docs/decoder-rebuild/spec-xc-round.md` (Architect, `arch/decoder-rebuild` `6e4e8bec`), authorised by the Captain on 2026-11-27 · **Status:** a measurement, no bars; he decides whether it stays. Aggregates only (NFR-021): message text is read inside three functions (`xr_analyze.free_check_slice`, `pf_oo_check.analyse_slice`, `xr_freecheck_diag.diag_slice`, `xr_split.split_slice`) that return counts only.

**Update 2026-11-27 15:05 UTC: the build as shipped (no prior-store feed) was replayed to confirm (section 11). The free check passes, and the measured gain matches the estimate of section 10 to within 0.04 pp.** Sections 0 to 9 describe the first replay (with the feed).

## Summary

1. **Free check failed BY DESIGN: the spec's own section 2.2 stores batch 4 in the prior store, which feeds batch-4 decodes back into the cross-cycle stage 30, 60 and 90 s later. This was an Architect spec defect (`6e4e8bec`: section 2.2 contradicts section 3); the Architect has said so.** The native cycle path is untouched (every probe row of rounds 0 to 3 is identical to the PAYLOAD-FIT run in all 650 cycles). But the **published decodes of batches 1 to 3 are not identical**: the new run has **4 / 21 / 44 extra decodes** in them (in 4 / 20 / 40 cycles; 0 / 0 / 1 decodes lost; no decode changed a field). All extra ones but one are batch-3 (cross-cycle) detections, and every one sits 30, 60 or 90 s after a cycle that had batch-4 decodes: the spec stores batch 4 in the prior store, so a batch-4 decode becomes a template for later cycles' cross-cycle stage. **The replay is valid, and its gain includes this chained effect** (sections 0 and 8).
2. **The rate rises on all three slices: +0.47 pp (S40, 87.79 to 88.26 %), +0.76 pp (H40, 87.24 to 88.00 %), +1.26 pp (H20, 85.24 to 86.50 %).** Lean is now +3.87 / +2.71 / +5.25 pp over classic. (Table 1.)
3. **The false side rises more than the rate:** `ours_only` +0.34 / **+1.04 / +1.34** pp; only 58 %, 42 % and 48 % of the extra decodes are matched by WSJT-X (PAYLOAD-FIT's were 88 / 84 / 81 %). On H40 and H20 the added unconfirmed decodes (93, 124) now outnumber the added confirmed ones (68, 115). They repeat about as often as the confirmed ones (section 5).
4. **The direct effect on the XC cases (27 / 52 / 89):** N now has a round-4 `SUB` row in **27, 50 and 89**, and **T is matched in 13, 29 and 63** (48 %, 56 %, 71 %): 0.19, 0.32 and 0.69 pp, against the Architect's bounds of 0.40, 0.58 and 0.97. (Table 4.)
5. **Cost:** the round runs in 80, 91 and 93 % of cycles; its own logged cost is a median **328 / 355 / 391 ms wall and 0.73 / 0.98 / 1.45 CPU-s per run** (about **+0.62 / +1.03 / +1.40 CPU-s per cycle**); `last_p95` 2,350 / 2,453 / 2,537 ms (+82 / +138 / +277). The whole-process CPU per cycle reads -4.3 / 0.0 / +4.4 %, which is run-to-run noise against a logged cost of +3.6 / +5.9 / +8.5 %. No abandoned cycle, no native error.
6. **XC is no longer the main cause:** the K2 neighbours never subtracted fall from 53 / 87 / 132 to **28 / 45 / 57**, now R3 (no valid fit), R2 and R4. (Table 4.)
7. **No decode was lost** between the runs outside batches 1 to 3's one swap (0 / 0 / 1 ours_only lost; 0 matched lost).

## 0. The free check, in numbers (failed by design: an Architect spec defect, `6e4e8bec` section 2.2 against section 3)

| Slice | decodes of batches 1-3 before | after | only in before | only in after | fields changed | cycles differing | probe rows of rounds 0-3: cycles differing |
|---|---:|---:|---:|---:|---:|---:|---:|
| S40 | 6,246 | 6,250 | 0 | **4** | 0 | 4 | **0** |
| H40 | 8,465 | 8,486 | 0 | **21** | 0 | 20 | **0** |
| H20 | 8,454 | 8,497 | 1 | **44** | 0 | 40 | **0** |

The extra rows are in batch 3 (4 / 21 / 43) and batch 2 (0 / 0 / 1; the batch-2 one, with the one lost, is probably a hashed-call text that resolved after the hash table learned from a batch-4 decode); each lies 30, 60 or 90 s after a cycle with batch-4 decodes (4 of 4, 21 of 21, 44 of 44). That test is weak by itself (such cycles are common: 45, 99 and 133 of 170 / 240 / 240), so the mechanism is read from the spec (§2 item 2, stored "like batch 2") and the batch (3), not proved by it. The matched flags of the common decodes did not change. **The Architect was told before this note was written** (the stop rule of the spec) and answered that the fault is in the spec, not the build; the ledger marks XR-6 as his defect.

## 2. What was run

- **Build:** `feat/xc-round` `65bca805` (PAYLOAD-FIT `f20ae680` + the change), HK-039 record `qa/rr-study/2026-11-27-qa-code-review-xc-round-65bca805-APPROVED.md`. Harness `Ft8.FitProbe` from a clean checkout of the merged tree with `HasLean`, `HasProbe`, `HasXcRound` and the usual flags. **`libft8.dll` SHA-256 `fa0b96c1c8a220b363db80977c0f741b6b7898a89bce3b98fe56e51691442504` = the Developer's reported hash = the runner's pin** (asserted; the harness's copy hashes to it), shim 20260082. No `--filter` (a replay).
- **The harness had to forward the new interface method:** `DecodeLeanXcRound` is a default interface member returning an empty outcome, so the harness's wrapper would have run no round at all (no batch 4, no error). The forward is in the harness (`HasXcRound`); the replay shows it worked: **batch-4 decodes 51 / 140 / 195** and round-4 probe rows (SUB 272 / 580 / 796).
- **Arm and slices:** exactly the PAYLOAD-FIT arm: lean, 16 threads, effort normal, `--lean-probe 1`, LC-BASE's L flags with the cross-cycle stage on (`lc_base_run.py ... --tag xr --probe`): S40 (170 cycles), H40 and H20 (240 each), one after another on the otherwise idle PC (13:06 to 13:29 UTC). **Baseline: the PAYLOAD-FIT runs already on disk** (`pf_*`, `b26a156c`, shim 20260081); the two `sel.json` files are equal.

## 3. Table 1 and cost

| Slice | Arm | matched | ours | rate % | ours_only % |
|---|---|---:|---:|---:|---:|
| S40 | classic | 5716 | 5971 | 84.39 | 3.77 |
|  | lean with PAYLOAD-FIT | 5946 | 6246 | 87.79 | 4.43 |
|  | **lean with XC-ROUND** | 5978 | 6301 | **88.26** | 4.77 |
|  | **XC-ROUND effect** | +32 | +55 | **+0.47 pp** | +0.34 pp |
|  | lean now minus classic |  |  | **+3.87 pp** |  |
| H40 | classic | 7662 | 8233 | 85.29 | 6.36 |
|  | lean with PAYLOAD-FIT | 7837 | 8465 | 87.24 | 6.99 |
|  | **lean with XC-ROUND** | 7905 | 8626 | **88.00** | 8.03 |
|  | **XC-ROUND effect** | +68 | +161 | **+0.76 pp** | **+1.04 pp** |
|  | lean now minus classic |  |  | **+2.71 pp** |  |
| H20 | classic | 7438 | 7999 | 81.25 | 6.13 |
|  | lean with PAYLOAD-FIT | 7803 | 8454 | 85.24 | 7.11 |
|  | **lean with XC-ROUND** | 7918 | 8692 | **86.50** | 8.46 |
|  | **XC-ROUND effect** | +115 | +238 | **+1.26 pp** | **+1.34 pp** |
|  | lean now minus classic |  |  | **+5.25 pp** |  |

| Slice | CPU-s per cycle (before, after, change) | the round's own logged CPU per cycle | `last_p95` ms (before, after) | rounds run (share of cycles) | wall ms / CPU ms per round (median) | fits / fitNone per cycle | batch-4 decodes (per cycle) | abandoned | errors |
|---|---|---|---|---|---|---|---|---:|---:|
| S40 | 17.22, 16.49, **-4.3 %** | +0.62 (+3.6 %) | 2,268, 2,350 | 136 (80 %) | 328 / 734 | 1.61 / 0.01 | 51 (0.30) | 0 | 0 |
| H40 | 17.41, 17.40, **0.0 %** | +1.03 (+5.9 %) | 2,315, 2,453 | 218 (91 %) | 355 / 984 | 2.51 / 0.09 | 140 (0.58) | 0 | 0 |
| H20 | 16.50, 17.23, **+4.4 %** | +1.40 (+8.5 %) | 2,260, 2,537 | 223 (93 %) | 391 / 1,453 | 3.35 / 0.03 | 195 (0.81) | 0 | 0 |

The whole-process CPU is a noisy measure (two identical-decoder runs differ by a few percent); the round's own logged CPU, summed per cycle, is the better figure for its cost.

## 4. The XC cases and the new split

**Table 4a: the K2 cases of the PAYLOAD-FIT run whose never-subtracted neighbour N was a cross-cycle result** (the same universe as the 27 / 52 / 89):

| Slice | cases | N has a round-4 `SUB` row | T matched now | direct gain, pp (bound) | T matched and N has no round-4 row |
|---|---:|---:|---:|---|---:|
| S40 | 27 | 27 | 13 (48 %) | 0.19 (0.40) | 0 |
| H40 | 52 | 50 | 29 (56 %) | 0.32 (0.58) | 0 |
| H20 | 89 | 89 | 63 (71 %) | 0.69 (0.97) | 0 |

**Table 4b: the new never-subtracted K2 neighbours** (the universe is new: the K2 cases fall from 350 / 478 / 577 to 339 / 443 / 523):

| Slice | K2 cases | never subtracted (was) | XC | R2 fit skipped | R3 no valid fit | R4 last round | other |
|---|---:|---:|---:|---:|---:|---:|---|
| S40 | 339 | 28 (53) | 0 | 15 | 8 | 5 | |
| H40 | 443 | 45 (87) | 2 | 9 | 26 | 7 | 1 position-match miss |
| H20 | 523 | 57 (132) | 0 | 14 | 31 | 11 | 1 position-match miss |

(R1 is absent: PAYLOAD-FIT removed the gate. The two XC neighbours left on H40 are the two without a round-4 `SUB` row in Table 4a.)

**Knock-on:** matched gained **32 / 68 / 115**, lost **0 / 0 / 0**; **in the XC cases 13 / 29 / 63, outside them 19 / 39 / 52** (of which 17 / 34 / 41 crowded). The gain outside the cases includes the second-order effect of section 0 (later cycles' extra batch-3 detections feed it), which cannot be separated from the round's direct knock-on without a build that does not store batch 4 as priors.

## 5. The decodes this round added that WSJT-X did not confirm (`pf_oo_check.py pf xr`, the same definitions as the PAYLOAD-FIT note)

| Slice | Group | decodes | repeated in the next 4 cycles | repeat share | WSJT-X also saw it later | median SNR dB (q1 to q3) |
|---|---|---:|---:|---:|---:|---|
| S40 | **added, not matched** | **23** | 8 of 22 | **36.4 %** | 8 | **-13 (-18 to -6)** |
|  | added, matched | 32 | 13 of 31 | 41.9 % | 13 | -14 (-17 to -8) |
|  | baseline ours_only (PAYLOAD-FIT run) | 300 | 130 of 293 | 44.4 % | 102 | -17 (-19 to -13) |
| H40 | **added, not matched** | **93** | 35 of 91 | **38.5 %** | 25 | **-17 (-19 to -15)** |
|  | added, matched | 68 | 28 of 68 | 41.2 % | 27 | -16 (-18 to -14) |
|  | baseline ours_only | 628 | 316 of 618 | 51.1 % | 252 | -18 (-20 to -17) |
| H20 | **added, not matched** | **124** | 53 of 122 | **43.4 %** | 43 | **-16 (-18 to -14)** |
|  | added, matched | 115 | 54 of 115 | 47.0 % | 42 | -15 (-17 to -11) |
|  | baseline ours_only | 651 | 356 of 646 | 55.1 % | 254 | -17 (-19 to -16) |

As for PAYLOAD-FIT, the added unconfirmed decodes repeat about as often as the added confirmed ones (36 to 43 % against 41 to 47 %) and are about as weak, and WSJT-X itself decodes the same message in a later cycle for 36, 27 and 35 % of them (matched extras 42, 40 and 37 %). Their repeat share is somewhat lower than the baseline ours_only's (44 to 55 %). The count of unconfirmed decodes rises (23, 93, 124), which is the `ours_only` rise of the summary. Whether the unconfirmed ones are real is not measured (same caveat as before: a decode that does not repeat is not thereby false, and a repeat does not prove the text right).

## 6. The Architect's predictions, read mechanically (the ledger is his)

| # | Prediction | Result |
|---|---|---|
| XR-1 | S40 rate +0.30 pp or more | +0.47: **hit** |
| XR-2 | H40 rate +0.50 pp or more | +0.76: **hit** |
| XR-3 | H20 rate +0.80 pp or more | +1.26: **hit** |
| XR-4 | `ours_only` rises by no more than 0.30 pp on every slice | +0.34, +1.04, +1.34: **miss** (all three) |
| XR-5 | CPU per cycle rises by no more than 15 % on every slice | -4.3, 0.0, +4.4 % (the round's own logged cost +3.6, +5.9, +8.5 %): **hit** |
| XR-6 | the free check passes (batches 1-3 byte-identical) | extra batch-3 decodes in 4 / 20 / 40 cycles, probe rows identical: **miss**, marked by the Architect as his spec defect (section 0). The ledger scores 4 of 6. |

## 7. What this does and does not say

- It says the round works: N is subtracted in nearly every XC case, and the missed neighbour T is decoded in about half to seven tenths of them; the rate rises by 0.5 to 1.3 pp; the cost of the round itself is small (about 0.6 to 1.4 CPU-s per cycle, 2.4 to 2.5 s `last_p95`).
- It does **not** separate the round's own effect from its prior-store feed (section 0).
- The price is on the false side: `ours_only` rises by 1.0 to 1.3 pp on H40 and H20, where more than half of the added decodes are unconfirmed; the evidence of section 5 is the same kind as PAYLOAD-FIT's (they behave like the baseline unconfirmed decodes), not a proof.
- **Not measured:** the Architect's observation that a different payload with the same rendered text may be dropped by the text de-duplication; and (the Developer's design note) whether the round's native duplicate rule, which sees only its own results, lets a same-transmission decode of an earlier result through (an RR73-sentinel variant): not counted.
- The next lever the Architect named is the K2 decode step itself (bit metrics / BP): after this round the 28 / 45 / 57 never-subtracted neighbours are R3 (no valid fit) 8 / 26 / 31 and R2 plus R4 20 / 16 / 25, so the remaining misses are mostly decode failures of T itself, not missing subtractions.

## 8. Where the rise in `ours` comes from (`xr_split.py`, data on disk, no new run)

The Captain's decision turns on where the unconfirmed decodes come from. The rise in `ours` (+55 / +161 / +238) splits exactly into (a) the round's own batch-4 decodes, (b) the chained rows (decodes of batches 1-3 that the PAYLOAD-FIT run did not have, the prior-store feed of section 0) and (c) the rest:

| Slice | rise in ours | (a) batch 4: matched / unmatched | (b) chained rows in batches 1-3: matched / unmatched | (c) the rest | unconfirmed in total | of them from (b) |
|---|---:|---|---|---|---:|---|
| S40 | +55 | 51: 28 / 23 | 4: 4 / 0 | 0 | 23 | **0** (0 %) |
| H40 | +161 | 140: 60 / 80 | 21: 8 / 13 | 0 | 93 | **13** (14 %) |
| H20 | +238 | 195: 98 / 97 | 44: 17 / 27 | -1 (one ours_only decode of the baseline run dropped) | 124 added (123 net) | **27** (22 %) |

- **Most of the unconfirmed decodes are the round's own (a): 23 / 80 / 97 of 23 / 93 / 124, which is 100 %, 86 % and 78 %.** The chained rows (b) are 7 %, 13 % and 18 % of the rise, and 0, 14 and 22 % of the unconfirmed decodes. If batch 4 were not fed to the prior store, the chained rows (4 / 21 / 44, of which 4 / 8 / 17 matched) would go, and the rate would lose their matched part (4 / 8 / 17 matched decodes, 0.06 / 0.09 / 0.19 pp) and the false side its unmatched part (0 / 13 / 27 decodes, 0 / 0.15 / 0.29 pp of ours_only): the cost of dropping the feed on the rate is small, and so is its effect on the false side; it is the round itself that carries both. (This is arithmetic on the split; it is not a run without the feed.)
- **Whether the chained rows sit in cycles where WSJT-X decoded the same text:** the matched ones do by definition (4 / 8 / 17). For the unmatched ones (0 / 13 / 27) and for the unmatched batch-4 decodes (23 / 80 / 97): **none of the 240 (23 + 80 + 97 unmatched batch-4 decodes and 0 + 13 + 27 unmatched chained rows) has the same text in WSJT-X's own decodes of the same cycle**, at any frequency; they are decodes WSJT-X did not produce in that cycle. Whether they are real is the question of section 5.

## 9. Does the round run at the station? Every implementation of the new interface method

`IFt8NativeInterop.DecodeLeanXcRound` has a default body that returns an empty outcome (so a wrapper or fake that does not forward it never runs the round and never raises an error). On `feat/xc-round` `65bca805` there are 32 implementations of the interface:

| Implementation | Forwards / overrides | Falls back to the empty default |
|---|---|---|
| **`Ft8NativeInteropAdapter`** (`src/OpenWSFZ.Ft8/Interop`), the production adapter: `Ft8Decoder.DefaultInterop` (`Ft8Decoder.cs:115`), which the daemon uses (`src/OpenWSFZ.Daemon/Program.cs:306` constructs `new Ft8Decoder(...)` without an interop argument) | **yes: calls `Ft8LibInterop.DecodeLeanXcRound` (the native `ftz_xc_round`)** | no |
| `ScriptedLean` in `LeanEngineXcRoundManagedTests` (the new managed test seam) | overrides it (records the call) | no |
| `StageProbeInterop` (QA's replay harness, `qa/rr-study/sub-feas/replay81`) | **no on the Developer's commit; QA's harness commit forwards it** (`HasXcRound`, with the probe rows) | before QA's fix: yes |
| the other 29 test fakes in `tests/OpenWSFZ.Ft8.Tests` (the `FixedResultInterop` family, `CapturingInterop`, `RecordingInterop`, `LeanFake`, `NoLeanFake`, `RealLean`, the `ScriptedLean` of `LeanEngineBatchesTests`, and so on) | no | yes (by design: none of them models the round, so none publishes a batch 4) |

**So at the Captain's station the round does run** (production adapter forwards) whenever the lean engine is on (the default since DR-3), the cross-cycle stage is on (`crossCyclePrior`; the Architect's spec says the station has it on, from the build-provenance capture: not re-checked by QA here), effort is not Fast, the stage published at least one live detection and a residual exists. In the replay it ran in 80 %, 91 % and 93 % of cycles; the 136 / 218 / 223 rounds and the 51 / 140 / 195 batch-4 decodes show the harness forward worked. No other production implementation exists; only a future wrapper of the interface would need to forward it.

## 10. The decision: keep XC-ROUND WITHOUT the prior-store feed (Captain, 2026-11-27; the Architect's recommendation); no second replay

The Captain chose option 2 of three (keep as built, keep without the prior-store feed, drop). The Developer's follow-up `2f2d7fa9` (on `65bca805`; managed code and documents only, shim 20260082 and `libft8.dll` unchanged) maps batch 4 with `xcBatch: 0` (`Ft8Decoder.cs`, the same value batch 3 uses: never stored, no chaining) and flips the test: a batch-4 decode is not in the prior store and is not a template for the next cycle's stage.

**What the numbers above mean for the shipped build.** The replay measured the build WITH the feed. The shipped build has no feed, and **no replay of it was run** (the Captain accepted the arithmetic). The estimate is the measured run minus the chained rows of section 8 (4 / 21 / 44 decodes, of which 4 / 8 / 17 matched and 0 / 13 / 27 unmatched): **rate about -0.06 / -0.09 / -0.19 pp** (to about +0.41 / +0.67 / +1.07 pp over PAYLOAD-FIT) and **`ours_only` about 0 / -0.15 / -0.29 pp** (to about +0.34 / +0.89 / +1.05 pp). It assumes the chained rows simply disappear and nothing replaces them; the process-wide callsign hash table still learns from batch 4, so the one batch-2 swap of H20 may remain. The batch-4 decodes themselves (51 / 140 / 195; 28 / 60 / 98 matched) are the part this estimate keeps. These are estimates, not measurements.

## 11. Confirmation replay of the build as shipped (no prior-store feed), 2026-11-27 14:41 to 15:04 UTC

Asked for by the Captain after the sprint PR was opened ("run a replay to confirm"). **Build:** the sprint branch `f9662335` (`feat/xc-round` `2f2d7fa9`: batch 4 mapped with `xcBatch: 0`), harness from a clean checkout of that commit, **`libft8.dll` SHA-256 `fa0b96c1c8a220b363db80977c0f741b6b7898a89bce3b98fe56e51691442504`** (the runner's pin, asserted; unchanged by the follow-up). **Arm:** exactly the PAYLOAD-FIT arm again (`lc_base_run.py ... --tag xn --probe`), S40 / H40 / H20, same audio, same flags, baseline the PAYLOAD-FIT runs (`pf_*`). Scripts as before with the run tag `xn` (`xr_analyze.py xn`, `xr_split.py xn`, `pf_oo_check.py pf xn`); outputs `xn_analyze.json`, `xn_split.json`, `oo_check_pf_xn.json`.

**The free check passes.** Batches 1-3 are **identical** to the PAYLOAD-FIT run in every cycle: 6,246 / 8,465 / 8,454 decodes before and after, **0 extra, 0 lost, 0 fields changed, 0 cycles differing**; every probe row of rounds 0-3 is identical (0 cycles differing); the matched flags did not change. The hash-table swap seen on H20 in the first replay did not recur. The whole rise in `ours` is batch 4 (the split of section 8 now has no chained rows and no rest).

| Slice | rate % before, after | delta | `ours_only` % before, after | delta | matched / ours added | lean minus classic | the estimate of section 10 (rate / ours_only) | measured minus estimate |
|---|---|---|---|---|---|---|---|---|
| S40 | 87.79, **88.20** | **+0.41 pp** | 4.43, 4.77 | +0.34 pp | +28 / +51 | **+3.81 pp** | +0.41 / +0.34 | 0.00 / 0.00 |
| H40 | 87.24, **87.90** | **+0.66 pp** | 6.99, 7.89 | +0.90 pp | +59 / +140 | **+2.61 pp** | +0.67 / +0.89 | -0.01 / +0.01 |
| H20 | 85.24, **86.28** | **+1.04 pp** | 7.11, 8.12 | +1.00 pp | +95 / +187 | **+5.03 pp** | +1.07 / +1.05 | -0.03 / -0.04 |

**The estimate held:** the measured effect of the shipped build is within 0.04 pp of the arithmetic on the first replay, on all three slices and both measures.

**Cost** (the round's own logged cost is the better figure; whole-process CPU is noisy): the round runs in 134 / 217 / 220 cycles (79 / 90 / 92 %); median **315 / 353 / 393 ms wall and 0.72 / 0.92 / 1.34 CPU-s per run**; about **+0.62 / +0.99 / +1.33 CPU-s per cycle**; fits per cycle 1.59 / 2.42 / 3.17, `fitNone` 0.01 / 0.09 / 0.03; whole-process CPU per cycle -4.4 / -0.6 / +3.4 %; `last_p95` **2,397 / 2,472 / 2,536 ms** (was 2,268 / 2,315 / 2,260); **0 abandoned cycles, 0 native errors**, 0 round errors.

**Batch 4:** 51 / 140 / 187 decodes (28 / 59 / 95 matched, 23 / 81 / 92 unmatched). **The XC cases (27 / 52 / 89):** N has a round-4 `SUB` row in **27 / 50 / 89**; **T is matched in 13 / 29 / 62** (48 %, 56 %, 70 %): 0.19 / 0.32 / 0.68 pp of the gain, against the Architect's bounds of 0.40 / 0.58 / 0.97. **New never-subtracted K2 neighbours: 28 / 45 / 56** (R3 8 / 26 / 31, R2 15 / 9 / 14, R4 5 / 7 / 10, XC 0 / 2 / 0). **Knock-on:** matched gained 28 / 59 / 95 (in the XC cases 13 / 29 / 62, outside 15 / 30 / 33, of which 13 / 26 / 26 crowded), **lost 0 / 0 / 0**.

**The decodes this run added that WSJT-X did not confirm** (the same check as sections 5 and the PAYLOAD-FIT note): **23 / 81 / 92**, all batch 4. They repeat in the next 4 cycles in **36 % / 31 % / 37 %** (8 of 22, 25 of 80, 33 of 90), against **39 % / 39 % / 39 %** for the added confirmed decodes and **44 % / 51 % / 55 %** for the baseline ours_only decodes; WSJT-X itself decodes the same message later for 8, 20 and 31 of them; median SNR **-13 (-18 to -6), -17 (-19 to -14), -15 (-17 to -13) dB** (added confirmed: -13.5, -16, -14). Fewer unconfirmed decodes than with the feed on H40 and H20 (81 against 93, 92 against 124), as the arithmetic said; the share of the extras that WSJT-X confirms is 55 / 42 / 51 %.

**The Architect's predictions for the shipped build** (read mechanically, for the record; the ledger entry was scored on the first replay): XR-1 to XR-3 hit (+0.41, +0.66, +1.04 pp against +0.30 / +0.50 / +0.80), XR-4 miss (`ours_only` +0.34 / +0.90 / +1.00 against 0.30), XR-5 hit, XR-6 now holds (the free check passes).

**Reproduce:** `python -I qa/decoder-rebuild/xr_analyze.py` (reads `_qa-scratch\lc-base\runs\{pf,xr}_*`; writes `xr_analyze.json`), `python -I qa/decoder-rebuild/pf_oo_check.py pf xr` (`oo_check_pf_xr.json`), `python -I qa/decoder-rebuild/xr_freecheck_diag.py` (`xr_freecheck_diag.json`), `python -I qa/decoder-rebuild/xr_split.py` (`xr_split.json`). The outputs are beside this note.
