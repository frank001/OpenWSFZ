# STRONG-MISS: run protocol (QA, frozen before the run)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-10 (`date -u` stamp in the commit). **Spec:** `2026-10-10-1015-architect-to-qa-spec-strong-miss-replay.md` with amendment 1 (`arch/strong-miss` `22e46d8f`).
- **Go:** the Captain, in the QA window ("go"), after the Architect's answers to QA's two questions.
- **Nature:** diagnostic and descriptive. One night (`20261009_1752`), one chain, first nhard 24 + corrected-OSD row, subtraction ON. No gain is claimable, nothing is pooled.

## What is frozen here (before any decode)

| item | value | where it comes from |
|---|---|---|
| Target set T | 504 rows in 433 cycles | the spec; **re-derived** by the harness from the two `ALL.TXT` files and asserted (run on 2026-10-10 before this note: `--derive-only` gave T 504, cycles 433, C 1,671, by form two-call 318 / CQ 72 / hashed 66 / compound `/` 48, matched 62,340, WSJT-X-only 31,271: all equal to the spec) |
| Control set C | 1,671 matched rows of the same shape in the same cycles | the spec, asserted |
| Build under test | checkout `421e3ce2` (DI sync 5), `libft8.dll` SHA-256 `a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610` | the live night's `arm_config.json`; the harness output DLL and the checkout DLL are both byte-checked against it |
| Live settings | `osdNhardMax` 24, sign fix on, subtraction ON, `subtractionMaxThreads` 8, `kMinScorePass2` 10, `osdCorrThreshold` 0.10 | `arm_readback.json` of the live run |
| Decode call | `Ft8Decoder.DecodeTwoStageAsync`, one call per cycle, batch 1 plus the residual batch, output already post-plausibility and per-cycle text-dedup (both live inside the decoder) | the Replay81 family call (not the live early/final path: stated limit) |
| **SM-V2 bar** | R-OWN reproduces **at least 99 %** of the live OpenWSFZ rows in the 433 cycles AND adds **at most 1 %** rows not in the live output, both as a share of the live row count | amendment 1 (QA's proposal, accepted): 5 % of the ~12,000 live rows would exceed the 504 targets. Basis: the 10-01 subtraction-ON replay against the 09-30 live night showed 409/430 cycles with equal row count and sum \|diff\| 41 of 9,827 (0.42 %); that is an older build and another night, counts only |
| SM-V2 also reported per cycle | cycles with equal row count, sum \|diff\|, and sum \|diff\| as a share of live rows, so the two read side by side | amendment 1 |
| SM-V3 | C recovered in R-OWN, with a Wilson 95 % CI, no bar | the spec |
| Classes | exclusive, first match wins: SM-LIVE (R-OWN decodes it), SM-CAPTURE (R-OWN misses, R-WSJ decodes), SM-DECODER (both miss); per class count with Wilson 95 % CI, overall and by form | the spec |
| "Decoded" | a target is decoded in an arm if that arm's cycle output holds its comparison key at least `rank + 1` times, where rank is the row's position among rows with the same key in that cycle (so duplicates are not double counted) | QA, to make "contains the match key" exact for repeated texts |
| Comparison key | cycle stamp + message text with every `<...>` collapsed to `<HASH>` (the standing matching rule). Text only, no frequency tolerance | the spec |
| Extra reporting | SM-DECODER by WSJT-X SNR bin and DT bin; cycles whose R-OWN and R-WSJ outputs differ (0 would be suspicious); R-OWN rows not in the live output; residual-pass abandonment and contained-exception counts per arm | the spec and QA |

If SM-V2 fails, the classes are DESCRIPTIVE ONLY and the Architect rules (spec). The predictions SM1 to SM6 are the Architect's and are scored at the ruling.

## Design limits (stated now, repeated in the report)

1. **Not the live path.** The replay uses the two-stage call, not the daemon's early-decode plus final split, and WSJT-X is not part of the decoder's process. SM-V2 measures how close this is on the 433 cycles.
2. **Hash-table history.** The callsign hash table is process-global. Neither arm has the live process's 15 h history. The harness interleaves the arms per cycle (R-OWN then R-WSJ), so both see the same history. The comparison key collapses `<...>`, so hashed text does not depend on it.
3. **Competing load.** WSJT-X (and `jt9`) are resident, as on the live night. No timing is compared, but a deadline abandonment would change a decode: the per-arm abandonment counts are reported, and the live run had none in its residual passes.
4. **One run, no repeat.** Replay-to-replay repeatability on this build is not measured here; the DENSITY-SUB same-build repeat (162 of 163 no-hashed cycles equal, the one difference an abandonment) is the nearest record, an older build.
5. **Target selection.** T is selected on a live miss, so any residual nondeterminism would move some targets into SM-LIVE. SM-V2 bounds how much.

## HK-037 / NFR-021

One process: `StrongMiss.dll` reads both `ALL.TXT` files, derives T and C, decodes both audio sets, scores, and writes aggregate counters to `result.json`. No per-message list, digest, or temp file is written; its log allows only aggregate templates and warning templates. The orchestrator never reads message text. The report is scanned for callsign-shaped tokens before it leaves the artefact directory.

## Run

`python qa/rr-study/sub-feas/strong_miss_run.py` (detached, supervised). Artefacts: `artefacts/rr_2026-10-10_strong_miss/` (`preflight.json`, `pins.jsonl`, `harness.log`, `status.json`, `result.json`, `run_end.json`). Estimate about 433 cycles x 2 arms x ~6.7 s = ~1.6 h. The arm does not resume: a crash restarts it (nothing partial is on disk by design).
