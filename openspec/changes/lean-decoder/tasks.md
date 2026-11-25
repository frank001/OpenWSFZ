## 1. Native

- [x] 1.1 `ftx_decode_candidate_tier_a` in `native/ft8_lib_build/patched/ft8/decode.c` (no OSD, reentrant, degenerate vectors rejected)
- [x] 1.2 `native/ftz_decoder/ftz_decoder.h` and `.c`: `ftz_decode_cycle`, `ftz_shutdown`, the fixed worker pool, the sort, the bounds checks, the SEH wrapper; provenance headers
- [x] 1.3 `ft8_shim.c` include at the end; `FT8_SHIM_VERSION` 20260073 in `ft8_shim.h`; `rebuild_shim.bat` exports; `libft8.dll` rebuilt (`libft8.version.txt`)
- [x] 1.4 `native/ftz_decoder/tests/ftz_fuzz.c` and `run_asan.sh`; CI job `native-asan`

## 2. Managed

- [x] 2.1 `Interop/LeanCycle.cs`, the P/Invoke, the interface members (default implementations) and the adapter; `ExpectedShimVersion` 20260073
- [x] 2.2 `DecoderEngine.cs`; `DecoderConfig.Engine` and `Threads`
- [x] 2.3 `Ft8Decoder.SetEngine` / `SetLeanThreads`, the branch, `DecodeLeanAsync`, the log line; `Dispose` frees the pool
- [x] 2.4 `Program.cs` setter calls (initial and per config change)

## 3. Tests (unit tests only, the Captain's rule of 2026-11-24)

- [x] 3.1 Primary-pass equality on `synth-qso-01` to `03` (`LeanEngineNativeTests`)
- [x] 3.2 Determinism at 1, 2 and 4 threads (and thread-count changes between cycles)
- [x] 3.3 Fuzz, 10,000 runs, managed (`LeanEngineNativeTests`) and under ASan + UBSan (`ftz_fuzz.c`)
- [x] 3.4 Engine switch: the golden recorded on the base build (`ClassicEngineGoldenTests`), lean routing, error code, exception, config round trip (`LeanEngineConfigTests`)
- [x] 3.5 Message-text rule on the log line
- [x] 3.6 Existing suites green, run per project

## 4. Documents

- [x] 4.1 `REQUIREMENTS.md` FR-108 and a changelog row
- [x] 4.2 This change, validated `--strict`
- [x] 4.3 VERSION: not bumped (`User-facing: no`); `check_version_bump.py` run after the commit

## 5. Step 2b (tier B and CQ-AP)

- [x] 5.1 `ftz_decoder.c`: tier B on the worker pool (`cf_process_one`, one coherent context per worker, multi-set on, the T1 gate, one row per payload), CQ-AP after it, the budget, the `out_tiers` array, the per-tier counters; `ftz_decoder.h` params and stats
- [x] 5.2 `FT8_SHIM_VERSION` 20260074; `libft8.dll` rebuilt; `libft8.version.txt`
- [x] 5.3 Managed: `LeanCycleParams`, the wire structs, the tiers, `DecodeLeanAsync` hands in CQ-AP and the budget, the provenance tags, the extended `lean:` line
- [x] 5.4 Tests: tier-B equality with the classic fallback, the gate and one-row-per-payload, CQ-AP on a drifting carrier, determinism over the tiers at 1, 2, 4 and 8 threads, the budget, the order comparison of the task's section 3
- [x] 5.5 Native harness (ASan + UBSan, 10,000 runs) extended to tier B, CQ-AP and random budgets
- [x] 5.6 `REQUIREMENTS.md` FR-108 extended and a changelog row; this change validated `--strict`

## 6. Step 2c (the subtract-and-retry loop)

- [x] 6.1 `ftz_decoder.c`: rounds 1 to 3 (`FTZ_FLAG_ROUNDS`): subtraction with `ft8_subfeas_fit_signal` on the original analytic signal, chunks of 16 fits on the worker pool summed in sorted order, the residual spectrogram, the residual search, the patch rule, the residual accept rules, the all-or-nothing budget with the 1,500 ms reserve, `out_rounds`, per-round statistics; test exports `ftz_patch_keep`, `ftz_payload_same_qso`, `ftz_residual_b_accept`
- [x] 6.2 `FT8_SHIM_VERSION` 20260075; `libft8.dll` rebuilt; `libft8.version.txt`
- [x] 6.3 Managed: `LeanCycleParams` (rounds, residual settings, test hook), wire structs, `LeanRoundStats`, the extended `lean:` line with the fit / search / decode CPU split
- [x] 6.4 Tests (`LeanEngineRoundsTests`, `LeanEngineWiringTests`): masked signal, payload equality with classic's residual pass, patch window, accept rules, stop rules, determinism at 1, 2 and 4 threads, budget
- [x] 6.5 Native harness (ASan + UBSan) runs the loop in the determinism run and on mutated real audio
- [x] 6.6 `REQUIREMENTS.md` FR-108 extended and a changelog row; this change validated `--strict`

## 7. Step 2d (three batches, XC on the residual, effort)

- [x] 7.1 `ftz_decoder.c/.h`: `round0_cb` / `round0_ctx` (the hand-off after round 0, before round 1), `out_residual` and `has_residual`, `FTZ_FLAG_NO_TIER_B`; params version 4
- [x] 7.2 `FT8_SHIM_VERSION` 20260076; `libft8.dll` rebuilt; `libft8.version.txt`
- [x] 7.3 Managed: `DecodeLeanCycle` with the hand-off (copy, swallow, never throw across), `DecodeLeanAsync` with the three batches, the shared `RunCrossCycleStageSharedAsync` (classic and lean, one body), priors from batches 1 and 2, `decoder.effort` (`DecoderEffort`, config, daemon), the pump's `LeanEngine` hook, the extended `lean:` line
- [x] 7.4 Tests (`LeanEngineBatchesTests`, `LeanEngineBatchesNativeTests`, `LateBatch4Tests`, `LeanEngineConfigTests`, `LeanEngineWiringTests`): batch 1 before round 1 (native held inside the hand-off), empty batch 1, one text once, priors, XC on the residual (and the skip, the veto, the shadow), effort, routing, determinism including the residual bytes
- [x] 7.5 Native harness (ASan + UBSan) runs the callback, the residual buffer (NULL and exactly sized) and the no-tier-B flag in the determinism run and the fuzz
- [x] 7.6 `REQUIREMENTS.md` FR-108 extended and a changelog row; this change validated `--strict`

## 8. Step 2e (a cheaper fit, the fit-skip rule, the residual accept rule)

- [x] 8.1 `subfeas_fit.c`: the frequency-shift table once per fit, copy + mix + decimation fused, four step-3 candidates at a time; `ft8_subfeas_set_reference_mode` (the old paths kept verbatim behind it) proves them byte for byte; profile taken first (one fit about 265 ms CPU, 59 % in step 2)
- [x] 8.2 `ftz_decoder.c/.h`: `FTZ_FLAG_SKIP_FITS` and `ftz_fit_needed` (the fit-skip rule), per-round `n_fit_skipped`, the residual accept rule without the residual-candidates restriction, `resid_valid` cleared when a subtraction starts, the `inject_error_round` test hook; params version 5
- [x] 8.3 `FT8_SHIM_VERSION` 20260077; `libft8.dll` rebuilt; `libft8.version.txt`
- [x] 8.4 Managed: `LeanCycleParams` (`SkipFits`, `InjectErrorRound`), the lean cycle turns the rule on, the `lean:` line's skipped counts, `DecodeLeanAsync` awaits the native call before a publisher exception propagates
- [x] 8.5 Tests (`LeanEngineFitCostTests`, `LeanEngineRoundsTests`, `LeanEngineBatchesTests`): 38-signal byte equality, the rule at its edges, two fixtures (set unchanged; masked signal lost), the rule off equal to step 2d, the accept rule, the error after the first chunk, the throwing publisher
- [x] 8.6 Native harness (ASan + UBSan) runs the rule on and off, the injected error, and the determinism digest
- [x] 8.7 `REQUIREMENTS.md` FR-108 extended and a changelog row; this change validated `--strict`

## 9. Operator threads setting

- [x] 9.1 Screenshot, before: the Advanced Decoder Settings block as it was (`dev-tasks/screenshots/threads-setting-before.png`), taken first in this section, ahead of any change to it (HK-005)
- [x] 9.2 Settings page: number input for `decoder.threads` (1 to 16), selects for `decoder.engine` and `decoder.effort`, help text with the host processor count and the one measurement; wired into the snapshot, the pre-fill, the payload and the reset (`web/js/settings.js`, `web/js/decoderThreads.js`, `web/settings.html`)
- [x] 9.3 Server: `processorCount` on the status endpoint; the config POST clamps `threads` to 1 to 16 with a warning; `DecoderConfig.MaxThreads` 16
- [x] 9.4 Native: `FTZ_MAX_THREADS` 8 to 16; `FT8_SHIM_VERSION` 20260078; `libft8.dll` rebuilt
- [x] 9.5 Tests: front-end (`decoderThreads.test.js`), Web (the status field, the clamp, the overlay), Config, native determinism at 1, 2, 4, 8 and 16 threads, the ASan fuzz at 16
- [x] 9.6 Screenshot, after: the block with the new controls (`dev-tasks/screenshots/threads-setting-after.png`)
- [x] 9.7 `REQUIREMENTS.md` FR-108 extended and a changelog row; this change validated `--strict`
