## Why

H3b (shim 20260009) replaced the proven spectrogram-domain soft-SNR tile suppression with
PCM-domain GFSK quadrature SIC and was rejected: S7 overall fell from 54.84% to 37.63%
(−17.21 pp), with collateral regressions across near-collision, time-offset, and capture parts.
Two iterations of PCM-domain SIC (H3, H3b) have now both been net-negative; the baseline
mechanism must be reinstated before any further improvement experiment can be validated.

## What Changes

- **Reinstate** the `suppress_candidate_tiles` call in the pass-1 inter-pass block of
  `ft8_decode_all()` in `src/OpenWSFZ.Ft8/Native/ft8_shim.c`.
- **Remove** the H3b PCM-domain SIC block: the `malloc`/synth/subtract/waterfall-rebuild
  sequence and the associated `monitor_t mon2`, `bool mon2_initialized`, `float* gfsk_kernel`,
  `float* gfsk_prefix`, and `float* synth_buf_q` declarations.
- **Remove** the `const monitor_t* mon_cur` pointer and revert all `mon_cur->` usages to
  `mon.` / `&mon.wf` (baseline pattern).
- **Remove** `if (mon2_initialized) monitor_free(&mon2)` from the cleanup section.
- **Retain** the GFSK helper functions (`build_gfsk_kernel`, `synth_ft8_gfsk_quad`,
  `compute_quadrature_amplitude`) — they are not called and have no runtime effect; they are
  preserved for a potential H3c hybrid experiment.
- **Retain** the D-003 diagnostic additions (`tls_last_noise_floor_db`,
  `ft8_get_last_noise_floor_db()`).
- **Bump** `FT8_SHIM_VERSION` from `20260009` to `20260010` and add a history comment
  entry recording H3b superseded, spectrogram suppression reinstated.
- **Rebuild** all three native binaries (win-x64, linux-x64, osx-arm64).

## Capabilities

### New Capabilities

*(none — this change introduces no new user-visible capabilities)*

### Modified Capabilities

- `iterative-subtraction`: The inter-pass mechanism reverts from PCM-domain SIC to
  spectrogram-domain soft-SNR tile attenuation. No requirement text changes; the
  implementation detail (which mechanism is active) is recorded in the shim history comment.
- `ft8lib-interop`: `FT8_SHIM_VERSION` advances to 20260010; the managed interop layer
  version-check assertion must be updated to match.

## Impact

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — primary change file
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — version constant update (if defined there)
- Native binaries: `Native/win-x64/libft8.dll`, `Native/linux-x64/libft8.so`,
  `Native/osx-arm64/libft8.dylib`
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — version-check constant if it asserts
  `FT8_SHIM_VERSION == 20260009`
- No managed API, no UI, no test changes expected
