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
