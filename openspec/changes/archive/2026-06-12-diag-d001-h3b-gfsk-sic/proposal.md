## Why

H3 (diag-d001-pcm-sic, shim 20260008) was rejected: −13.98 pp regression, P0/P1 co-channel
still 0/6. Post-mortem confirmed two compounding model mismatches in the CP-FSK/cosine
cancellation synthesiser: (a) CP-FSK vs GFSK modulation — the actual FT8 waveform uses
Gaussian frequency shaping (BT=2.0); (b) cos(phase) vs sin(phase) initialisation, and more
fundamentally, a fixed phase-zero assumption that is invalid for any signal whose carrier
phase is not known a priori. Together these drove the least-squares projection amplitude
`a ≈ 0`, meaning the subtraction removed essentially nothing while discarding the
spectrogram-domain suppression that had been working.

## What Changes

- **`ft8_shim.c` — `synth_ft8_cpsfc` replaced with GFSK quadrature synthesiser:**
  The CP-FSK scalar synthesiser is replaced by a function that produces two quadrature
  GFSK waveforms (I = sin component, Q = cos component) using a 3-symbol Gaussian
  smoothing pulse (BT=2.0), matching the modulation used by real FT8 transmitters and the
  QA Python synthesiser. Both components are written into caller-provided buffers; no heap
  allocation inside the function.
- **`ft8_shim.c` — `compute_projection_amplitude` replaced with quadrature estimator:**
  The scalar dot-product estimator is replaced by an analytic quadrature estimator that
  computes `dot_I = dot(pcm, synth_sin)` and `dot_Q = dot(pcm, synth_cos)`, derives
  optimal amplitude `a = sqrt(dot_I² + dot_Q²) / energy(synth)` and optimal phase
  `φ = atan2(dot_Q, dot_I)`, and returns the correctly-phased scalar subtraction
  coefficient. This is O(N) — no sweep, no iteration — and is valid for any carrier phase.
- **`ft8_shim.c` — PCM-domain SIC integration updated:** The signal subtraction loop
  updated to pass two quadrature output buffers to the synthesiser and use the quadrature
  amplitude estimator. The `synth_buf` heap allocation strategy is unchanged; a second
  heap buffer (`synth_buf_q`) of equal size is added for the Q component.
- **`ft8_shim.c` — `FT8_SHIM_VERSION` bumped from `20260008` to `20260009`.**
- **`Ft8LibInterop.cs` — `ExpectedShimVersion` updated from `20260008` to `20260009`.**
- **Native binaries rebuilt** for all three reference platforms.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `iterative-subtraction`: The inter-pass cancellation synthesiser changes from CP-FSK/cosine
  to GFSK/quadrature with analytic phase estimation. The heap-allocation requirement
  (two 720 KB buffers) gains a third buffer (`synth_buf_q`, 720 KB) for the Q component.
  The subtraction formula changes from `residual -= a * synth_buf` to
  `residual -= (a_I * synth_buf_sin + a_Q * synth_buf_q)` where
  `a_I = a * cos(φ)` and `a_Q = a * sin(φ)`.
- `ft8lib-interop`: Expected shim version updated from `20260008` to `20260009`.

## Impact

- **Modified files:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`,
  `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`
- **Rebuilt binaries:** all three platform native libraries + `libft8.version.txt`
- **No managed API surface changes** — `DecodeAll`, `GetLastPassCounts`,
  `GetLastNoiseFloorDb` signatures unchanged; `MaxDecodePasses = 2` and `MaxResults = 340`
  unchanged
- **Additional heap allocation:** one extra 720 KB buffer (`synth_buf_q`) per decode cycle
  during the pass-1 SIC stage; total PCM-domain SIC heap rises from 1.44 MB to 2.16 MB
- **Test impact:** all 320 existing tests must remain green; new S7 R&R study (T3) is the
  acceptance gate for the diagnostic
- **R&R study:** S7 must be re-run after T2 merge; same gate criteria as H3 — any
  improvement on P0 or P1, AND overall ≥ +5 pp vs 54.84% baseline
