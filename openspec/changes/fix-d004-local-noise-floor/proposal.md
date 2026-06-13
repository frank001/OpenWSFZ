## Why

The SNR formula in `ft8_shim.c` uses a single global waterfall median as the noise floor for all decoded signals, regardless of their frequency. Live endurance data (2026-06-13, 1h42m, 8 691 OpenWSFZ decodes vs 15 877 WSJT-X) demonstrates that the audio chain has significant high-frequency rolloff: back-computed `signal_db` falls from −39.7 dB at 800–1000 Hz to −67.5 dB at 2800–3000 Hz, while `noise_floor_db` stays essentially constant at −66.7 dB across the band. The result is a frequency-dependent SNR bias of up to −22 dB at the top of the FT8 audio passband — and of −18 dB at the low end — causing D-004 (systematic bias) and, in the high-frequency tail, D-003 (intermittent SNR values below −30 dB). D-003 is confirmed to be the extreme tail of D-004, not a separate defect.

## What Changes

- **`ft8_shim.c`** — the per-signal SNR computation replaces the call to `compute_noise_floor` (global histogram median) with a per-signal **local noise floor** sampled from waterfall bins in a frequency sideband window around the decoded signal's own tones. The global noise floor is retained for the existing per-cycle diagnostic log (it is useful for stability monitoring) but is no longer used in the SNR calculation.
- **`ft8_shim.h`** — `FT8_SHIM_VERSION` bumped to document the algorithm change. Struct layout (`FT8Result`) is unchanged; this is not an ABI break.
- **Native binaries rebuilt** — win-x64 `libft8.dll`, linux-x64 `libft8.so`, osx-arm64 `libft8.dylib` replaced with the new build.
- **`Ft8LibInterop.cs`** — `ExpectedShimVersion` constant updated to the new version value.
- **`ft8lib-interop/spec.md`** — ABI sentinel version updated.
- **R&R S1 re-run** — SNR bias calibration validated after fix; the −26.5 dB bandwidth constant may require adjustment.

No public API changes. No change to `DecodeResult`, `FT8Result` layout, or any managed interface.

## Capabilities

### New Capabilities

_(None — this is a bug fix to existing SNR computation, not a new capability.)_

### Modified Capabilities

- `ft8lib-interop`: ABI sentinel version advances; `ExpectedShimVersion` and `ft8lib-interop/spec.md` version references must be updated to match the new `FT8_SHIM_VERSION`.
- `ft8-decoder`: SNR accuracy behaviour changes. The existing SNR accuracy requirement (S1 R&R gate) must be re-validated after the fix and the spec updated if the calibration constant changes.

## Impact

| Area | Detail |
|---|---|
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` | SNR computation changed; local noise floor function added |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | `FT8_SHIM_VERSION` bumped |
| `src/OpenWSFZ.Ft8/Native/{win-x64,linux-x64,osx-arm64}/libft8.{dll,so,dylib}` | Rebuilt binaries |
| `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` | `ExpectedShimVersion` constant |
| `openspec/specs/ft8lib-interop/spec.md` | ABI sentinel version |
| `qa/rr-study/` | S1 R&R run required post-fix to validate bias and calibrate constant |
| D-003 (GitHub #11) | Close as duplicate of D-004; resolved by this fix |
| D-004 (GitHub #12) | Root-cause fix; re-characterise after S1 validation |
