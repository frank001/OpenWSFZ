## Why

The spectrogram-domain soft suppression ramp in `ft8_shim.c` uses constants that have never been
tuned: at the S7 test SNR of 0 dB the current ramp suppresses only 25% of each decoded tile's
energy before pass 1, leaving substantial residual from the first signal. H5 tests whether
shifting the ramp window to produce ~75% suppression at 0 dB SNR closes the remaining gap
between OpenWSFZ and WSJT-X on the time-offset co-channel scenarios (P8/P9/P10).

## What Changes

- `K_SOFT_SUPP_SNR_MIN_DB` in `ft8_shim.c` changed from `−5.0f` to `−15.0f`
- `K_SOFT_SUPP_SNR_MAX_DB` in `ft8_shim.c` changed from `+15.0f` to `+5.0f`
- `FT8_SHIM_VERSION` bumped from `20260010` to `20260011`
- `ExpectedShimVersion` in `Ft8LibInterop.cs` updated from `20260010` to `20260011`
- All three platform binaries rebuilt and committed (`win-x64`, `linux-x64`, `osx-arm64`)

No other shim logic, pass configuration, managed-layer logic, or test scenarios change.
This is a single-variable diagnostic experiment.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ft8lib-interop`: shim version constant advances from 20260010 to 20260011; the hard-assert
  in `Ft8LibInterop.cs` must track this.
- `iterative-subtraction`: the soft SNR-scaled suppression ramp bounds change; spec must
  document the new constant values and the rationale for their selection.

## Impact

- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`** — two `#define` edits and a version bump
- **`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`** — one constant update
- **`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`**, **`linux-x64/libft8.so`**,
  **`osx-arm64/libft8.dylib`** — rebuilt binaries committed
- **S7 R&R validation run** required post-build; acceptance gates defined below

### Acceptance gates

| Gate | Criterion | Source |
|---|---|---|
| (a) overall recovery | ≥ 56.99% (≥ 53/93) | H4 R1 baseline (`cd9f06b`) |
| (b) no per-part regression | every part count ≥ its H4 R1 count | H4 R1 per-part table |

Both gates PASS → H5 ACCEPTED; shim 20260011 becomes the new S7 baseline.  
Either gate FAIL → H5 REJECTED; constants must be reverted to `−5.0f`/`+15.0f`, version
returns to 20260010.
