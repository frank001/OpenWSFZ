## 1. Native Shim — ft8_set_decode_params (shim 20260030)

- [x] 1.1 In `src/OpenWSFZ.Ft8/Native/ft8_shim.c`: declare three module-level `static` variables (`s_k_min_score_pass2 = 10`, `s_osd_corr_threshold = 0.10f`, `s_osd_nhard_max = 60`) and implement `ft8_set_decode_params(int k, float corr, int nhard)` that writes them; export the symbol via `ft8_shim.h`.
- [x] 1.2 In `ft8_shim.c` `ft8_decode_all`: replace the two compile-time `#define` references to `K_MIN_SCORE_PASS2`, `OSD_CORR_THRESHOLD`, and `OSD_NHARD_MAX` (in the pass-config table and decode.c call sites) with reads of the three module-level statics. Update the version comment block and advance `FT8_SHIM_VERSION` to `20260030`.
- [x] 1.3 In `native/ft8_lib_build/patched/ft8/decode.c`: update `OSD_CORR_THRESHOLD` and `OSD_NHARD_MAX` references to use the values passed through from the shim (the patched decode.c call sites receive these via function parameters — update `ftx_decode_candidate` and `ftx_decode_candidate_ap` signatures accordingly, or use extern globals exposed from `ft8_shim.c`).
- [x] 1.4 Rebuild the Windows x64 binary, verify `FT8_SHIM_VERSION = 20260030` via `check_native_version.py`, update `libft8.version.txt` and `BUILD.md`, and commit `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`.
- [x] 1.5 Push to CI and verify the `commit-native-binaries` job commits updated Linux x64 and macOS ARM64 binaries at shim 20260030.

## 2. C# Interop Layer

- [x] 2.1 In `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs`: add `void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)` to the interface.
- [x] 2.2 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`: add `[DllImport("libft8.dll", EntryPoint = "ft8_set_decode_params", ...)]` P/Invoke declaration; implement `public static void SetDecodeParams(int, float, int)` that calls `EnsureInitialized()` then the P/Invoke; advance `ExpectedShimVersion` to `20260030`; update the version history XML-doc comment.
- [x] 2.3 In `src/OpenWSFZ.Ft8/Interop/Ft8NativeInteropAdapter.cs`: implement `IFt8NativeInterop.SetDecodeParams` by delegating to `Ft8LibInterop.SetDecodeParams`.

## 3. Configuration Model

- [x] 3.1 Create `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: a `sealed record DecoderConfig` with `KMinScorePass2`, `OsdCorrThreshold`, and `OsdNhardMax` fields, a `[JsonConstructor]`-annotated constructor with parameter defaults matching the calibrated values (10, 0.10f, 60), per the Lesson 6 pattern.
- [x] 3.2 In `src/OpenWSFZ.Abstractions/AppConfig.cs`: add `public DecoderConfig? Decoder { get; init; } = null;` with appropriate XML-doc comment.
- [x] 3.3 In `src/OpenWSFZ.Config/ConfigJsonContext.cs`: add `DecoderConfig` to the `[JsonSerializable(...)]` attribute list.
- [x] 3.4 In `src/OpenWSFZ.Web/AppJsonContext.cs`: add `DecoderConfig` to the `[JsonSerializable(...)]` attribute list.

## 4. API Validation

- [x] 4.1 In `src/OpenWSFZ.Web/WebApp.cs`, inside the `POST /api/v1/config` handler: add a `decoder` validation block (after the `tx` validation block) that clamps `KMinScorePass2` to [5, 30], `OsdCorrThreshold` to [0.05f, 0.40f], and `OsdNhardMax` to [30, 100], logging a Warning for each clamped value (same pattern as the `tx` and `cat` blocks).

## 5. Daemon Startup Wiring

- [x] 5.1 In the daemon startup code (locate the `IConfigStore` initialisation and pipeline start sequence): subscribe to `IConfigStore.OnSaved` with a lambda that calls `Ft8LibInterop.SetDecodeParams(config.Decoder?.KMinScorePass2 ?? 10, config.Decoder?.OsdCorrThreshold ?? 0.10f, config.Decoder?.OsdNhardMax ?? 60)`.
- [x] 5.2 In the daemon startup code, after the `IConfigStore` is loaded and before audio capture starts: call `Ft8LibInterop.SetDecodeParams(...)` once with the initial config values (handles the "loaded calibrated defaults at startup" scenario).

## 6. Settings UI

- [x] 6.1 In `web/settings.html`: add a `<details id="advanced-decoder-settings">` section after the existing TX settings block. Include a `<summary>Advanced Decoder Settings</summary>`, the disclaimer text, three `<input type="number">` elements (`id="decoder-k"`, `id="decoder-corr"`, `id="decoder-nhard"`) with appropriate `min`/`max`/`step` attributes, a `<button id="decoder-reset">Reset to defaults</button>`, and a note that changes take effect on the next decode cycle.
- [x] 6.2 In `web/js/settings.js`: on load, after `GET /api/v1/config`, populate the three decoder inputs from `config.decoder` (using `10`, `0.10`, `60` as fallbacks when `decoder` is null). Wire `#decoder-reset` to reset inputs to the calibrated defaults. Include the `decoder` object in the save payload built for `POST /api/v1/config`, reading from the three input elements.

## 7. Tests

- [x] 7.1 In `tests/OpenWSFZ.Config.Tests/` (or `OpenWSFZ.Abstractions.Tests` if it exists): add `DecoderConfigTests.cs` — JSON round-trip test for all fields; missing-field defaults test via the `[JsonConstructor]` path (deserialise `{}` → expect calibrated defaults).
- [x] 7.2 In `tests/OpenWSFZ.Web.Tests/`: add decoder-section tests to the `WebApp` config validation test class — at-boundary values (5, 0.05, 30 and 30, 0.40, 100) are accepted unchanged; below-minimum values are clamped; above-maximum values are clamped; null decoder object is accepted unchanged.
- [x] 7.3 In `tests/OpenWSFZ.Ft8.Tests/`: add a `SetDecodeParamsTests.cs` — using the `FakeInterop` / mock path from existing tests, verify that `IFt8NativeInterop.SetDecodeParams` is called with the correct values. Mark any test that requires the real native binary with `[Trait("Category", "RequiresNativeBinary")]`.
- [x] 7.4 Run the full test suite (`dotnet test OpenWSFZ.slnx -c Release`) — verify 0 failures and that the new tests are counted in the pass totals. Update MEMORY.md test count.

## 8. Traceability and Housekeeping

- [x] 8.1 Update the G3 requirement-traceability debt file to map the new spec requirements to their implementing tests.
- [x] 8.2 Update MEMORY.md: advance shim version to 20260030 in the "Native binary state" section; update the main build/test counts; note the decoder-settings-page change as the active OpenSpec change.
