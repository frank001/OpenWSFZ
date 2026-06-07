## Why

The R&R study (run `2026-06-06-5b868ce`) revealed that OpenWSFZ's SNR reporting carries a
systematic +1 to +2 dB positive bias and has poor within-appraiser repeatability (R² = 0.267
vs WSJT-X's 0.752), both traceable to a single flaw in the signal power estimator inside
`ft8_shim.c`: it takes the **max over all 8 FT8 tone bins** per symbol rather than reading
only the bin that carries the transmitted tone.

## What Changes

- **Replace** the per-symbol `max(row[0..7])` signal power loop in `ft8_shim.c` with a
  tone-specific read: `row[tones[b - b0]]`, where `tones[]` is the 79-symbol sequence
  produced by `ft8_encode(msg.payload, tones)` — a call already made on the same decoded
  message in `suppress_candidate_tiles`.
- **No change** to the noise-floor estimator, the 26 dB bandwidth correction, the decode
  pipeline, the `Ft8Decoder.cs` managed wrapper, or any public API.

## Capabilities

### New Capabilities

_(none — this is a pure implementation correction with no new user-visible capability)_

### Modified Capabilities

- `ft8-decoder`: The SNR value reported per decode result changes in magnitude. The
  requirement is that SNR be accurate relative to the 2500 Hz WSJT-X convention; this fix
  brings the implementation into closer conformance with that requirement.

## Impact

- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`** — only file modified.
- **`src/OpenWSFZ.Ft8/Native/libft8.dll` (and sibling `.so`/`.dylib`)** — must be rebuilt
  from the updated shim source.
- **Existing tests** — `Ft8DecoderPlausibilityTests` and `ReplayHarnessTests` exercise decode
  correctness, not SNR value; they are unaffected. SNR-specific tests in
  `Ft8DecoderPlausibilityTests` that assert SNR ranges may need tolerance updates.
- **R&R trend** — `qa/rr-study/trend.csv` gains a new row after a post-fix study run;
  expected outcome is %GR&R (S1) < 30% and bias closer to 0 dB.
