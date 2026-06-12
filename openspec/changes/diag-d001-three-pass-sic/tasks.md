## 1. Native shim — ft8_shim.c

- [x] 1.1 Increment `FT8_SHIM_VERSION` from `20260006` to `20260007`
- [x] 1.2 Change `K_MAX_PASSES` from `2` to `3`
- [x] 1.3 Raise `K_MAX_DECODED` ceiling: update formula to `K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2 + K_MAX_CANDIDATES_PASS2` (140 + 200 + 200 = 540)
- [x] 1.4 Update the per-pass config table (`k_pass_cfg`) to declare a third entry for pass 2, reusing `K_MIN_SCORE_PASS2`, `K_MAX_CANDIDATES_PASS2`, `K_LDPC_ITERATIONS_PASS2`
- [x] 1.5 Extend the suppression accumulator guard to cover pass 1 as well as pass 0: change `if (pass == 0 && n_all_supp < K_MAX_CANDIDATES)` to `if ((pass == 0 || pass == 1) && n_all_supp < K_MAX_CANDIDATES)`
- [x] 1.6 Update the shim version history comment block to document `20260007`

## 2. Native binary rebuild

- [x] 2.1 Rebuild `libft8.dll` (Windows x64) from the updated `ft8_shim.c` and commit to `src/OpenWSFZ.Ft8/Native/win-x64/`
- [x] 2.2 Rebuild `libft8.so` (Linux x64) and commit to `src/OpenWSFZ.Ft8/Native/linux-x64/`
- [x] 2.3 Rebuild `libft8.dylib` (macOS ARM64) and commit to `src/OpenWSFZ.Ft8/Native/osx-arm64/`
- [x] 2.4 Update `libft8.version.txt` for all three platforms: increment version to `20260007`, update pass count to `3`, record build date and compiler version

## 3. Managed interop layer — Ft8LibInterop.cs

- [x] 3.1 Update `ExpectedShimVersion` from `20260006` to `20260007`
- [x] 3.2 Update `MaxDecodePasses` from `2` to `3`
- [x] 3.3 Update `MaxResults` from `340` to `540` (= 140 + 200 + 200) to match the expanded `K_MAX_DECODED`
- [x] 3.4 Update the XML doc comment on `ExpectedShimVersion` to include the `20260007` entry in the version history

## 4. Managed decoder — Ft8Decoder.cs

- [x] 4.1 Replace the two hard-coded per-pass `_logger?.LogDebug(...)` calls with a `for` loop over `passCounts.Length`, emitting `"Iterative subtraction: pass {n} of {max}, {k} new decodes"` for each pass (1-indexed `n`, `passCounts.Length` as `max`)

## 5. Verification

- [x] 5.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings
- [x] 5.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all tests pass (G6 gate: `RealSignalFixtureTests` must remain green; `IterativeSubtractionTests` must remain green; `Ft8LibInteropTests` version-check test must pass with the new binary)
- [x] 5.3 Confirm the ABI version check passes: the new binary returns `20260007` and no `InvalidOperationException` is thrown on startup
- [x] 5.4 Confirm `Ft8DecoderFixtureTests` (if present) and `LoggingPipelineTests` remain green — the log loop change must not break expected log output assertions
