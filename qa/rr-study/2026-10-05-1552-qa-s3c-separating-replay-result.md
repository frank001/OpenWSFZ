# S3c separating replay (Architect ruling 2026-10-05 15:40Z section 4): result

**From:** QA. **To:** Architect, cc Captain. **Run:** 2026-10-05, finished before 15:52Z by `date -u`, Captain's go in QA's window ("run S3c").
Harness and driver committed BEFORE any decode: `db2da962` on `qa/main-with-sampler` (`qa/rr-study/s3c/replay/`). Outputs
`artefacts/20261005_s3c_replay/arm{1,2,3}/` (gitignored; planted synthetic texts only). `src/`/`native/` untouched.

## What ran
12 archived S3c cycles of battery 3 (`artefacts/_rr_main766f9cc2_daemon_output/cycle-audio`, stamps 261004_152100 to 261004_152345),
each arm a FRESH process, subtraction flag ON, nhard 40, kMinScorePass2 10, osdCorrThreshold 0.10, threads default (auto),
`DecodeTwoStageAsync` (both batches scored). Arm 1 and 2 build `766f9cc2`, DLL SHA-256 `2fa6d993…f365`, shim 20260058;
arm 3 build `cddd7e34`, DLL `ee00d118…990e4c`, shim 20260056. The loaded DLL was checked against the pin at start AND end of every process.
Scored with the battery's own scorer (`s3c_score.score`, planted text exact, own cycle, |df| <= 10 Hz) over an ALL.TXT-format file the harness
writes for planted synthetic texts only (HK-037); the WSJT-X side is battery 3's own file (it is there only so the scorer runs).

| Arm | Build | Early decode | E -2.00 (S3c-E50) | E -1.75 | L +2.75 | L +3.00 |
|---|---|---|---:|---:|---:|---:|
| 1 | 766f9cc2 | ON | **32/32** | 32 | 32 | 0 |
| 2 | 766f9cc2 | OFF | **32/32** | 32 | 32 | 0 |
| 3 | cddd7e34 | n/a | **32/32** | 32 | 32 | 0 |

Battery 3 live: 32, 32, 32, 0. Batteries 1 and 2 live (cddd7e34): E -2.00 = 17 and 16.
Stop rule: arm 1 reproduced 32 (within 32 +- 2), so arms 2 and 3 were run and are read.
Integrity: 0 exceptions in 36 cycle decodes; batch 2 empty in every cycle (no residual pass to abandon); final decode about 0.4 s per cycle;
only idle `dotnet`/`VBCSCompiler` servers were running (the Developer's suite had finished).

## Reading, against the ruling's table
- **(a) early path leaks into the final decode: NOT supported.** Arm 1 = arm 2 on every part.
- **(b) the rebuilt DLL decodes differently at a marginal cell: NOT supported.** Arm 2 = arm 3 on every part.
- **(c) a non-build difference in battery 3: SUPPORTED** (ruling: "3 ~ 32 => (c)"). The OLD build scores 32/32 on battery 3's
  recorded audio. So what moved is the audio (or its capture), not the decoder.
- Predictions by their thresholds: S3X1 (arm 1 within 32 +- 2) HIT; S3X2 (arms 1 and 2 agree within 2) HIT; S3X3 (arm 3 <= 24) MISS (32).
  Scoring is the Architect's.

## Limits
Replay of the recorded capture, so the capture chain's effect is IN the audio and is not separated from it. Each process starts with an
empty callsign hash table (the battery's daemon had run S1..S8 first); the planted texts are standard-call Q-prefix messages, so no effect
is expected, but it was not tested. One battery's 12 cycles; the E -2.00 cell has 32 signals. The guard (`r_ref`, `k*`) is untouched.
This says nothing about decode rate and nothing about the build.

## Not done (the ruling's next step for (c); needs the Architect's pre-registration and the Captain's go)
Batteries 1 and 2's archived S3c cycles are on disk (`_rr_baseline194_daemon_output/cycle-audio`: 261003_010600 to 010845 and 261003_030645
to 030930). Replaying them through `766f9cc2` (and `cddd7e34`) would show whether the E -2.00 gap follows the AUDIO (batteries 1-2
audio gives ~16 on both builds) or something else. The same harness runs it unchanged.
