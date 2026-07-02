## Why

The three D-009 OSD gate parameters (`K_MIN_SCORE_PASS2`, `OSD_CORR_THRESHOLD`, `OSD_NHARD_MAX`) are currently hardcoded compile-time constants in the native shim, meaning any tuning adjustment requires a native rebuild and deployment. Exposing them as live-configurable settings lets expert operators and the QA engineer adjust the false-positive / sensitivity trade-off in the field — without a recompile — and provides a direct path for diagnostic investigations when new band conditions or propagation modes are encountered.

## What Changes

- **New `DecoderConfig` record** in `OpenWSFZ.Abstractions` with three fields (`KMinScorePass2`, `OsdCorrThreshold`, `OsdNhardMax`) and calibrated defaults from the D-009 R&R study.
- **New `decoder` key in `AppConfig`** (nullable, same pattern as `cat` and `tx`) so existing config files deserialise without error.
- **New native entry point `ft8_set_decode_params`** in `ft8_shim.c` — stores three parameters in module-level statics read by `ft8_decode_all`; shim version bumped to `20260030`. All three platform binaries must be rebuilt.
- **New `SetDecodeParams` P/Invoke** in `Ft8LibInterop` and corresponding method on `IFt8NativeInterop`.
- **Config-change listener in daemon startup** — when `IConfigStore.OnSaved` fires, `SetDecodeParams` is called so the next decode cycle uses the updated values.
- **API validation** in `POST /api/v1/config`: out-of-range values are clamped with a `LogWarning` (same pattern as `cat` and `tx`).
- **New "Advanced Decoder Settings" section** in the existing settings page — three numeric inputs with range hints, a disclaimer, and a "Reset to defaults" button. Changes take effect on the next decode cycle without restart.
- **Updated `ConfigJsonContext`** to include `DecoderConfig` in the AOT-safe JSON serialisation chain.

## Capabilities

### New Capabilities

- `decoder-settings`: Operator-configurable OSD gate parameters (`KMinScorePass2`, `OsdCorrThreshold`, `OsdNhardMax`). Covers the `DecoderConfig` schema, API validation rules, native `ft8_set_decode_params` contract, and settings-page UI controls.

### Modified Capabilities

- `configuration`: `AppConfig` gains a nullable `decoder` sub-object; `POST /api/v1/config` gains three new clamped-validation rules; default config file includes the `decoder` key.
- `ft8lib-interop`: New `ft8_set_decode_params` native entry point; `ExpectedShimVersion` advances to `20260030`; `IFt8NativeInterop` gains `SetDecodeParams`; committed binaries advance to shim `20260030`.

## Impact

- **`OpenWSFZ.Abstractions`** — new `DecoderConfig.cs` record.
- **`OpenWSFZ.Config`** — `ConfigJsonContext` updated for `DecoderConfig`.
- **`OpenWSFZ.Ft8`** — `Ft8LibInterop.cs`, `IFt8NativeInterop.cs`: new method; `ExpectedShimVersion` updated.
- **`OpenWSFZ.Web`** — `WebApp.cs` validation block; `AppJsonContext.cs` updated.
- **`OpenWSFZ.Daemon`** — startup wiring to subscribe to `IConfigStore.OnSaved` and call `SetDecodeParams`.
- **Native shim** — `src/OpenWSFZ.Ft8/Native/ft8_shim.c` and `native/ft8_lib_build/patched/ft8/decode.c`: `ft8_set_decode_params` function; three platform binaries rebuilt; `libft8.version.txt` and `BUILD.md` updated.
- **Settings UI** — new collapsible section in the existing HTML/CSS/JS settings page.
- **Tests** — `OpenWSFZ.Config.Tests`, `OpenWSFZ.Ft8.Tests`, `OpenWSFZ.Web.Tests`: new test cases.
- **No breaking changes** — `AppConfig.Decoder` is nullable; missing `decoder` key in existing config files deserialises as `null`, treated as calibrated defaults.
