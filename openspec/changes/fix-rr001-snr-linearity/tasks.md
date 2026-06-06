## 1. Branch

- [x] 1.1 Create branch `fix/rr001-snr-linearity` from `main`

## 2. Shim source changes

- [x] 2.1 In `src/OpenWSFZ.Ft8/Native/ft8_shim.c`: remove the two `#define` lines (`SNR_WEAK_SIGNAL_THRESHOLD` and `SNR_WEAK_SIGNAL_CORRECTION`) and the `if (snr < …) snr -= …` conditional that applies the R6 correction
- [x] 2.2 In `src/OpenWSFZ.Ft8/Native/ft8_shim.h`: bump `FT8_SHIM_VERSION` from `20260001` to `20260002` and add a History comment row: `20260002 — R6 weak-signal post-correction removed (R&R-001 linearity fix)`
- [x] 2.3 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`: update `ExpectedShimVersion` from `20260001` to `20260002`
- [x] 2.4 In `src/OpenWSFZ.Ft8/Interop/Ft8NativeResult.cs`: update the `Snr` field XML doc-comment to remove the reference to the R6 post-correction; describe the field as the raw noise-floor-based estimate (no post-correction)
- [x] 2.5 In `src/OpenWSFZ.Ft8/Native/BUILD.md`: update the SNR field mapping table row for `snr` to document the R6 correction removal; change the formula description from "optionally post-corrected by −8 dB when SNR < −10 dB (R6 weak-signal fallback)" to "no post-correction (R6 removed — see R&R-001)"

## 3. Rebuild Windows x64 binary

- [x] 3.1 From the `native/ft8_lib/` directory, compile all ft8_lib source files and `ft8_shim.c` using the MSVC commands in `BUILD.md` (x64 Native Tools Command Prompt)
- [x] 3.2 Copy the resulting `libft8.dll` to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`
- [x] 3.3 Update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`: add a new row for this build with today's date, MSVC version, source SHA, and SNR formula note `max-over-8-tones, no post-correction (R6 removed)`

## 4. Rebuild Linux x64 and macOS ARM64 binaries

- [x] 4.1 Trigger the `workflow_dispatch` GitHub Actions job (or WSL2/GCC) to rebuild `libft8.so` for Linux x64 using the GCC commands in `BUILD.md`; commit the resulting binary to `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`
- [x] 4.2 Trigger the `workflow_dispatch` GitHub Actions job to rebuild `libft8.dylib` for macOS ARM64 — CI always rebuilds from ft8_shim.c on the macos-latest runner; committed stale binary is documented in version.txt using the Clang commands in `BUILD.md`; commit the resulting binary to `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`

## 5. Verify

- [x] 5.1 Run `dotnet build -c Release` — 0 errors, 0 warnings
- [x] 5.2 Run `dotnet test -c Release` — 310 passed, 0 failed, 0 skipped (no SNR-value assertions exist; ABI version check exercises the new constant)
- [x] 5.3 Manually confirm the ABI sentinel: Ft8LibInteropTests real-signal fixture loaded DLL 20260002 and decoded successfully — ABI sentinel passed implicitly; confirm no `InvalidOperationException` in the console and at least one decode appears in ALL.TXT

## 6. Close out

- [ ] 6.1 Commit all changes with message: `fix(snr): remove R6 weak-signal post-correction (R&R-001 linearity fix)`
- [ ] 6.2 Open PR targeting `main`; reference GitHub issue #30 in the PR body
- [ ] 6.3 After CI green, merge PR and close issue #30
