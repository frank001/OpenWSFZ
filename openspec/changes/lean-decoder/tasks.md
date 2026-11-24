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
