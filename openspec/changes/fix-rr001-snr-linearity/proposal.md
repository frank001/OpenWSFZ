## Why

The first live R&R study run (2026-06-06, SHA `46d7f6a`) found that OpenWSFZ's SNR
estimator has a bias slope of **0.512** (acceptance gate: ≤ 0.1). Root cause is the
R6 weak-signal post-correction in `ft8_shim.c`: subtracting 8 dB when the estimated
SNR < −10 dB creates a step-function discontinuity that linear regression interprets as
a large positive slope. Without the correction the raw estimator delivers a flat ~+1 dB
bias across the entire decoded SNR range — well within the ±2 dB mean-bias gate and
essentially slope-free.

## What Changes

- **Remove** the R6 fallback weak-signal post-correction from `ft8_shim.c`:
  - Delete `#define SNR_WEAK_SIGNAL_THRESHOLD` (−10.0 dB)
  - Delete `#define SNR_WEAK_SIGNAL_CORRECTION` (8.0 dB)
  - Delete the conditional `if (snr < threshold) snr -= correction`
- **Bump** `FT8_SHIM_VERSION` in `ft8_shim.h` to `20260002` (ABI sentinel requires a rebuild)
- **Update** `ExpectedShimVersion` in `Ft8LibInterop.cs` to `20260002`
- **Rebuild** all three platform native binaries (`libft8.dll`, `libft8.so`, `libft8.dylib`)
- **Update** `win-x64/libft8.version.txt`, `BUILD.md`, and `Ft8NativeResult.cs` doc-comments
- **Close** GitHub issue #30 (R&R-001)

## Capabilities

### New Capabilities

*(none — this is a pure defect fix with no new externally visible capability)*

### Modified Capabilities

- `ft8lib-interop`: The SNR field mapping changes: the R6 post-correction is removed,
  so the `snr` field now reflects the raw noise-floor-based estimate without the −8 dB
  weak-signal step. Reported integer SNR values change for signals whose pre-correction
  estimate was < −10 dB.

## Impact

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — remove R6 correction block
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — bump `FT8_SHIM_VERSION` to `20260002`
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` — rebuilt binary
- `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` — rebuilt binary
- `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` — rebuilt binary
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — updated provenance
- `src/OpenWSFZ.Ft8/Native/BUILD.md` — SNR mapping table updated
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `ExpectedShimVersion` updated
- `src/OpenWSFZ.Ft8/Interop/Ft8NativeResult.cs` — `Snr` field doc-comment updated
- No API, schema, or protocol changes; decode results are unaffected except for SNR integer values
