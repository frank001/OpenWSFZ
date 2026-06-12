## Why

D-001 (High) — OpenWSFZ recovers only ~47% of co-channel FT8 signals in the synthetic S7 scenario versus WSJT-X's ~76%, and achieves only 69.7% decode rate against the 42-WAV S6 corpus. Data analysis shows the gap is concentrated at exact co-channel conditions (0 Hz frequency separation); at ≥3 Hz separation, OpenWSFZ and WSJT-X perform identically. Before committing to a costly architectural change, we need to quantify the contribution of pass count as an isolated variable.

## What Changes

- **`ft8_shim.c`**: `K_MAX_PASSES` increased from 2 to 3. Pass 2 uses the same candidate/LDPC parameters as the existing pass 1 (wider net). `K_MAX_DECODED` ceiling raised to cover the additional pass capacity. `FT8_SHIM_VERSION` incremented to `20260007`.
- **`Ft8LibInterop.cs`**: `ExpectedShimVersion` updated to `20260007`; `MaxDecodePasses` updated to `3`.
- **`Ft8Decoder.cs`**: Per-pass log loop generalised from two hard-coded lines to a `for` loop over `passCounts.Length`, so it remains correct regardless of pass count.
- **Native binary**: `libft8.dll` (Windows), `libft8.so` (Linux), `libft8.dylib` (macOS) rebuilt and committed.
- **R&R study**: S7 re-run and reported against the 2-pass baseline (54.8% recovery). Outcome determines next step.

## Capabilities

### New Capabilities

*(none — this is a diagnostic/tuning change to an existing capability)*

### Modified Capabilities

- `iterative-subtraction`: pass count increased from 2 to 3; shim version constant updated accordingly.
- `ft8lib-interop`: `ExpectedShimVersion` and `MaxDecodePasses` managed constants updated to match the new shim.

## Impact

- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`** — core change
- **`src/OpenWSFZ.Ft8/Native/` binaries** — must be rebuilt for all three platforms
- **`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`** — version constants
- **`src/OpenWSFZ.Ft8/Ft8Decoder.cs`** — log loop generalisation
- **`qa/rr-study/`** — S7 re-run required post-implementation to evaluate hypothesis H2
- No API or contract changes; no configuration changes; no UI changes.
- Decode latency may increase marginally (one additional spectrogram suppression + candidate search pass). Expected impact: < 50 ms on a typical 15 s cycle.
