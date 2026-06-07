## 1. Branch & baseline

- [x] 1.1 Create branch `revert/fix-d001-pcm-sic` from `main`
- [x] 1.2 Confirm build is green: `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings
- [x] 1.3 Confirm test baseline: `dotnet test OpenWSFZ.slnx -c Release` — all tests pass, 0 failures
- [x] 1.4 Close PR #5 (`fix/native-stack-overflow-pcm-residual`) on GitHub with a comment referencing this revert branch

## 2. Native shim — `ft8_shim.h`

- [x] 2.1 In `src/OpenWSFZ.Ft8/Native/ft8_shim.h`, change `FT8_SHIM_VERSION` from `20260003` to `20260002`

## 3. Native shim — `ft8_shim.c`

- [x] 3.1 Remove the `estimate_carrier_hz_offset` function (carrier estimation via Goertzel/parabolic interpolation) and its `goertzel_magnitude` helper
- [x] 3.2 Remove the `synthesise_cp_fsk` function (CP-FSK waveform synthesis and in-place subtraction)
- [x] 3.3 Remove the `pcm_residual` heap allocation block (`malloc`, `free`, the `if (!pcm_residual)` OOM guard) and all references to `pcm_residual`
- [x] 3.4 Remove the PCM subtraction loop and waterfall rebuild block (`if (pass == 1) { if (num_decoded > 0) { memcpy ... monitor_free ... monitor_init ... } }`)
- [x] 3.5 Remove the `all_supp_snrs[]` accumulator array and all SNR tracking for the suppression accumulator (SNR is not needed for spectrogram suppression)
- [x] 3.6 Remove the buffer-full-guard spectrogram-suppression block inside the `if (num_decoded >= max_results)` early-exit (spectrogram suppression was originally inside the buffer-full path for pass 2; simplify)
- [x] 3.7 Change `K_MAX_PASSES` from `3` to `2`
- [x] 3.8 Remove `K_PCM_SIC_SNR_GATE_DB` constant and `K_MIN_SCORE_PASS2` / `K_MAX_CANDIDATES_PASS2` / `K_LDPC_ITERATIONS_PASS2` — **wait**: keep `K_MIN_SCORE_PASS2`, `K_MAX_CANDIDATES_PASS2`, `K_LDPC_ITERATIONS_PASS2` as they are used by pass 1 (spectrogram suppression); remove only `K_PCM_SIC_SNR_GATE_DB`
- [x] 3.9 Update the `k_pass_cfg` table to two rows: pass 0 (full waterfall, K_MIN_SCORE / K_MAX_CANDIDATES / K_LDPC_ITERATIONS) and pass 1 (spectrogram suppression, K_MIN_SCORE_PASS2 / K_MAX_CANDIDATES_PASS2 / K_LDPC_ITERATIONS_PASS2)
- [x] 3.10 Update `MaxResults` comment and usage: `all_supp_cands` and `all_supp_msgs` arrays are sized `K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2` (340); confirm this is still correct after the two-pass reduction
- [x] 3.11 Update the file-header comment block: remove the `fix-D001 — PCM-domain Successive Interference Cancellation` section; update `p15` description to reflect two-pass structure
- [x] 3.12 Remove the Decision 6 comment block (heap-allocated pcm_residual) that is no longer applicable

## 4. Native binaries rebuild — Windows & Linux

- [x] 4.1 Rebuild `libft8.dll` for Windows x64 using `native\ft8_lib_build\rebuild_monitor_and_shim.bat`; confirm `BUILD SUCCESS` and binary is copied to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`
- [x] 4.2 Rebuild `libft8.so` for Linux x64 via WSL2 (follow `BUILD.md` Linux procedure with the patched `monitor.c`); copy binary to `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`
- [x] 4.3 Update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`: update build dates for Windows and Linux entries to record "revert-pcm-sic: two-pass spectrogram suppression, FT8_SHIM_VERSION=20260002"; macOS entry: add "CI run: pending — push branch and wait for macos-latest leg"

## 5. Managed layer updates

- [x] 5.1 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`: change `ExpectedShimVersion` from `20260003` to `20260002`
- [x] 5.2 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`: change `MaxDecodePasses` from `3` to `2`
- [x] 5.3 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`: change `MaxResults` from `540` to `340`; update the doc-comment to read "K_MAX_CANDIDATES (pass 0, 140) + K_MAX_CANDIDATES_PASS2 (pass 1, 200) = 340"
- [x] 5.4 In `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: replace the `for (int i = 0; i < passCounts.Length; i++)` per-pass debug-log loop with two explicit `LogDebug` calls, one per pass (pass index 0 and 1); update the pass-count comment in the file header to reflect two passes

## 6. Tests

- [x] 6.1 Delete `tests/OpenWSFZ.Ft8.Tests/PcmSicTests.cs`
- [x] 6.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all remaining tests pass, 0 failures; verify the PcmSic tests are gone and no other tests reference SIC-only behaviour

## 7. macOS ARM64 binary

- [x] 7.1 Push the `revert/fix-d001-pcm-sic` branch to `origin`; wait for CI `macos-latest` leg to complete
- [x] 7.2 Download artifact `libft8-dylib-osx-arm64` from the successful CI run; copy to `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`
- [x] 7.3 Update `libft8.version.txt` macOS entry: replace "CI run: pending" with the actual CI run reference and build date
- [x] 7.4 Commit and push the macOS dylib and updated version.txt

## 8. Documentation & spec updates

- [x] 8.1 Update `DEFECT-native-stack-overflow-pcm-residual.md` status: change to "Superseded — PCM-SIC reverted on `revert/fix-d001-pcm-sic`; pcm_residual no longer exists"
- [x] 8.2 Update `openspec/specs/iterative-subtraction/spec.md`: merge the delta from this change's `specs/iterative-subtraction/spec.md` — apply REMOVED and MODIFIED requirements, update AC-IS-1 with outcome note
- [x] 8.3 Update `openspec/specs/ft8lib-interop/spec.md`: merge the delta from this change's `specs/ft8lib-interop/spec.md` — update version constant to `20260002`, `MaxDecodePasses` to 2, `MaxResults` to 340 with correct comment

## 9. Final integration

- [x] 9.1 Run `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings
- [x] 9.2 Run `dotnet test OpenWSFZ.slnx -c Release` — all tests pass, 0 failures
- [x] 9.3 Open PR against `main`; confirm CI green on all three matrix legs (Windows, Linux, macOS)
- [ ] 9.4 QA review and merge
