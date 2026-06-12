## Why

D-001 (co-channel / weak-signal decode gap, High severity) remains open after two diagnostic
experiments: H1 (PCM-domain SIC, reverted — stack-overflow crash) and H2 (three-pass
spectrogram-domain SIC, reverted — −4.30 pp regression). H2 confirmed the root cause: waterfall
tiles from exact co-channel signals are fully superimposed before the waterfall is built, so no
number of spectrogram-domain passes can recover the lost information. PCM-domain SIC is the only
remaining candidate mechanism — it operates on the signal *before* the waterfall is constructed.
H3 tests whether a correct implementation (heap-allocated buffers, CP-FSK synthesis, phase-zero
assumption) achieves measurable improvement on P0/P1 co-channel parts.

## What Changes

- **`ft8_shim.c`** — The inter-pass stage between pass 0 and pass 1 changes from spectrogram-domain
  soft-SNR-scaled tile suppression to **PCM-domain SIC**: for each signal decoded in pass 0, a
  CP-FSK waveform is synthesised (using `ft8_encode` tone sequence, no Gaussian shaping, phase
  zero), subtracted from a heap-allocated copy of the input PCM, and the waterfall is rebuilt from
  the residual before pass 1 runs. All intermediate buffers (720 KB PCM residual, 720 KB
  synthesised signal) are heap-allocated via `malloc`/`free` with NULL guards and freed on all
  exit paths. No VLAs, no automatic arrays larger than a few hundred bytes.
- **`ft8_shim.c` version** — `FT8_SHIM_VERSION` incremented from `20260006` to `20260008`
  (20260007 was the reverted three-pass SIC; that slot is skipped to avoid confusion).
- **`Ft8LibInterop.cs`** — `ExpectedShimVersion` updated from `20260006` to `20260008`.
  `MaxDecodePasses` and `MaxResults` are **unchanged** (K_MAX_PASSES stays 2; the external
  pass count and result capacity are unaffected by the change in what happens between passes).
- **Native binaries** — All three platform binaries rebuilt from the updated shim
  (`win-x64/libft8.dll`, `linux-x64/libft8.so`, `osx-arm64/libft8.dylib`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `iterative-subtraction`: The inter-pass stage changes from spectrogram-domain tile suppression
  to PCM-domain SIC (synthesis + subtraction + waterfall rebuild). Heap-allocation requirement
  (previously gated on Captain approval) is now active. PoC gate requirement is superseded by the
  H3 diagnostic decision.
- `ft8lib-interop`: Expected shim version updated from `20260006` to `20260008` in ABI self-test
  requirement and all associated version-mismatch scenarios.

## Impact

- **Modified files:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`
- **Rebuilt binaries:** `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`,
  `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`,
  `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`, `libft8.version.txt`
- **No managed API surface changes** — `DecodeAll`, `GetLastPassCounts`, `GetLastNoiseFloorDb`
  signatures are unchanged; `MaxDecodePasses = 2` and `MaxResults = 340` are unchanged
- **Test impact:** All 319 existing tests must remain green; new integration test added in T2
- **R&R study:** S7 must be re-run after T2 merge (NS-001 trigger condition: H3 fix merged)
