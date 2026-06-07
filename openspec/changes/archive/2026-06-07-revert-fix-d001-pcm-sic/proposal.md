## Why

The PCM-domain SIC (successive interference cancellation) decode path introduced in `fix-d001-pcm-sic` produced two fatal `0xC0000005` crashes in production — the second occurring with the heap-allocation patch applied — while delivering zero measurable improvement (−0.1 pp delta) in the R&R study. The code is unstable and without demonstrated benefit; it must be removed to restore a reliable baseline.

## What Changes

- **BREAKING** `FT8_SHIM_VERSION` reverted `20260003 → 20260002`; any `libft8` binary at 20260003 will be rejected by the managed ABI self-test after this change lands.
- `ft8_shim.c`: remove `estimate_carrier_hz_offset`, `synthesise_cp_fsk`, heap `pcm_residual` buffer, PCM subtraction loop, and waterfall-rebuild-from-residual block. `K_MAX_PASSES` reduced `3 → 2`. `K_PCM_SIC_SNR_GATE_DB` removed.
- `ft8_shim.h`: `FT8_SHIM_VERSION` constant reverted to `20260002`.
- `Ft8LibInterop.cs`: `ExpectedShimVersion` → `20260002`; `MaxDecodePasses` → `2`; `MaxResults` → `340` (140 + 200); doc-comments updated.
- `Ft8Decoder.cs`: per-pass debug-log loop (`"Iterative subtraction: pass N of 3"`) replaced with a single summary log line; pass count logging retained for the two remaining passes.
- `PcmSicTests.cs`: deleted — tests for functionality being removed.
- All three native binaries (`libft8.dll`, `libft8.so`, `libft8.dylib`) rebuilt from the reverted shim source.
- `libft8.version.txt`: all three platform entries updated to record the revert build date.
- `iterative-subtraction/spec.md` AC-IS-1: updated to note the criterion was tested and not met; D-001 remains Open.
- PR #5 (`fix/native-stack-overflow-pcm-residual`) closed — superseded by this revert.
- `DEFECT-native-stack-overflow-pcm-residual.md` status updated to "superseded by revert".

## Capabilities

### New Capabilities

*(none — this is a revert, no new capabilities are introduced)*

### Modified Capabilities

- `iterative-subtraction`: AC-IS-1 outcome must be recorded; the three-pass SIC requirement changes back to two-pass spectrogram-suppression only.
- `ft8lib-interop`: ABI version reverts to `20260002`; `MaxDecodePasses` and `MaxResults` constants change.

## Impact

- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`** — substantial reduction (~300 lines removed)
- **`src/OpenWSFZ.Ft8/Native/ft8_shim.h`** — version constant only
- **`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`** — three constants + comments
- **`src/OpenWSFZ.Ft8/Ft8Decoder.cs`** — log loop simplification
- **`tests/OpenWSFZ.Ft8.Tests/PcmSicTests.cs`** — deleted
- **`Native/win-x64/libft8.dll`**, **`Native/linux-x64/libft8.so`**, **`Native/osx-arm64/libft8.dylib`** — all three binaries rebuilt
- **`openspec/specs/iterative-subtraction/spec.md`** — AC-IS-1 outcome note
- **`openspec/specs/ft8lib-interop/spec.md`** — version and constant values
- Decode correctness test suite (G6 gate): remains green; G6 exercises the two-pass path which is unaffected
- No user-facing behaviour change: decode output is identical to the stable 69.1% baseline
