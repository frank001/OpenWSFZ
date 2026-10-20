# COH-FALLBACK step 3: A0 per-cycle slack `s_i` (QA dated note, committed BEFORE any Stage 1 timing is seen)

- **Stamped:** 2026-10-20, measured 17:14:08Z to 17:19:37Z by `date -u`. The Stage 1 build does not exist yet; the Developer has been told not to publish timing before this note (handoff `dev-tasks/2026-10-20-coh-fallback-step3-stage1.md`).
- **Spec:** `qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md` section 8 (`f0b36e54`) A1.3, with Amendment 2 section 9 (`3f41a6b7`) on `arch/coherent-limb2`.
- **Definition:** `s_i` = 13.0 s minus the OFF build's elapsed decode time for cycle i (decode start to the end of the last ordinary pass: pass 0, residual and third pass; the harness's `elapsed_ms`, mode `three1`). The 13.0 s is `SubtractionCycleBudget` (`Ft8Decoder.cs:108`, as cited by the spec). A0 PASSES iff the number of cycles with `f_i > s_i` is at most 5 of these 100 (a cycle with `s_i <= 0` counts as a fail whatever `f_i` is; there are none).

## Measurement

| item | value |
|---|---|
| Corpus | `20261009_1752_endurance_run-gathered` (3,634 WAVs, gap-free, 15.14 h), 1-in-3 selection `i mod 3 == 1` of the gap-inclusive slot list, k odd, V-P PASS (605 even, 606 odd, 0.08 %); selection file SHA-256 (LF) `9c20b921240e51f5b4cb28f751d782f78705f155e121ce74ae314e6875d1f4d6`, frozen before any decode |
| Cycles measured | the first 100 selected (`261009_175215` onward), after one discarded warm-up cycle |
| Build | `main` `5229beec` (Replay81 built against it), shim 20260062; OFF (no fallback exists) |
| Settings, read back at start and at end | subtraction ON, threads 8 of 8 resolved (16 cores), `nhard` 24, `kMinScorePass2` 10, `osdCorrThreshold` 0.10, OSD sign fix set 1 / read 1, `decodingDepth` Deep |
| Command | `Replay81.exe --selection selection_first100.json --run 20261009_1752 --stratum Y40 --wav-root artefacts --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8` (no filter; script `_qa-scratch\coh-fallback\run_off100.sh`) |
| Conditions | station PC, background load 12 to 14 % (browser, Voicemeeter), no other heavy job; 0 exceptions; 0 abandoned or contained passes in the 100 cycles |

## Result

| figure | value |
|---|---|
| elapsed per cycle, ms: median / p95 / max | 3,277 / 3,997 / 4,287 |
| **slack `s_i`, ms: minimum / 5th percentile / median** | **8,713 / 9,003 / 9,723** |
| cycles with `s_i <= 0` | 0 |
| cycles with `s_i < 1,000 ms` | 0 |

Per-cycle values: `slack_OFF_first100.csv` (stamp, elapsed, `s_i`, abandoned; numbers only).

## What this means for A0 (descriptive; the predicate is the Architect's)

A0 fails only if the fallback's per-cycle wall time exceeds the cycle's slack in more than 5 of these 100 cycles. On this night the slack is 8.7 to 11.2 s on every cycle, so the fallback would need to take more than about 8.7 s on more than five cycles. The Stage 1 timing must be taken in the same kind of session (8 threads, no other heavy job) on the same 100 cycles.

## Limits

- The slack is measured serially in the Replay81 harness, with the same 8 threads the ordinary passes use; a parallel fallback design competes with them for cores, and A0's serial worst case assumes it runs after them (spec A1.3).
- One night, one chain (direct USB CODEC, not the Voicemeeter chain of 10-04 / 10-19), one session.
- The OFF arm of the full replay (and `U0`) is NOT this run: it waits for the Captain's confirmation of the A1.6 rule.
