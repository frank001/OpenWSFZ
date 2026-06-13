## 1. Shim constant update

- [x] 1.1 In `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, change `K_SOFT_SUPP_SNR_MIN_DB` from `(-5.0f)` to `(-15.0f)`
- [x] 1.2 In `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, change `K_SOFT_SUPP_SNR_MAX_DB` from `(15.0f)` to `(5.0f)`
- [x] 1.3 In `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, update `FT8_SHIM_VERSION` from `20260010` to `20260011`
- [x] 1.4 Update the shim version history comment block in `ft8_shim.c` to record H5: suppression ramp shifted to [−15, +5]

## 2. Managed interop update

- [x] 2.1 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, update `ExpectedShimVersion` from `20260010` to `20260011`

## 3. Binary rebuild

- [x] 3.1 Rebuild the Windows x64 binary: `libft8.dll` → commit to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`
- [x] 3.2 Rebuild the Linux x64 binary: `libft8.so` → commit to `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`
- [x] 3.3 Rebuild the macOS ARM64 binary: `libft8.dylib` → commit to `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`
- [x] 3.4 Update `src/OpenWSFZ.Ft8/Native/libft8.version.txt` with build date, SHA, toolchain, and new version 20260011 for each platform

## 4. Build verification

- [x] 4.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings (including no `-Wunused-function` warnings for retained GFSK helpers)
- [x] 4.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all 327 tests pass, 0 failures

## 5. S7 R&R validation run

- [x] 5.1 Run the S7 synthetic co-channel R&R harness against the rebuilt binary (K=3, fresh seeds)
- [x] 5.2 Evaluate gate (a): S7 overall ≥ 56.99% (≥ 53/93)
- [x] 5.3 Evaluate gate (b): no per-part regression vs H4 R1 baseline (each part count ≥ H4 R1 count)
- [x] 5.4 Write NFR-023-compliant `report-v2.md` in the run results directory and commit

## 6. Verdict and documentation

- [ ] 6.1 **If both gates PASS:** record H5 ACCEPTED in MEMORY.md; update S7 baseline to the new overall %; post acceptance comment to GitHub issue #3
- [x] 6.2 **If either gate FAILS:** record H5 REJECTED in MEMORY.md; revert constants to `(-5.0f)` / `(15.0f)`, bump to 20260012 (do not return binary to 20260010 without a rebuild); post rejection findings to GitHub issue #3 with next-step hypothesis
  - Result: 43/93 = 46.24% — gate (a) FAIL (−10 decodes); gate (b) FAIL (P4 −1, P5 −2, P9 −5, P10 −1, P11 −1, P12 −2). H5 REJECTED.
  - Shim revert (20260012) deferred to H5b — follows H3b→H4 precedent; bad constants sit in main until next hypothesis implements the fix.
