## Why

The previous D-001 fix (`fix-d001-pcm-sic`, reverted at `efc0920`) failed on two independent counts: a P1 crash from a 703 KB stack allocation in a P/Invoke target, and zero measurable improvement on real signals (−0.1 pp) because the CP-FSK synthesis model does not match the HF channel (Doppler spread, multipath, amplitude flutter). The gap — OpenWSFZ 46.2% vs WSJT-X 77.4% on synthetic S7 co-channel, 69.1% vs WSJT-X on the 42-cycle ground-truth corpus — remains open and warrants a structured second attempt.

## What Changes

- **Option A (investigation):** Audit kgoba/ft8_lib upstream for any SIC or iterative-decode improvements since our pinned v2.0; update the binary dependency if a meaningful improvement is available.
- **Option B (implementation):** Replace the current hard-zero spectrogram tile suppression with soft SNR-scaled attenuation — stronger signals suppressed more aggressively, borderline signals suppressed less to avoid artefacts on adjacent weaker signals. No waveform synthesis; no PCM buffer; no phase model.
- **Option C (gated implementation):** Retry PCM-domain SIC using a realistic channel model: per-symbol amplitude from waterfall magnitudes + linear frequency trajectory fitted across all 79 symbols. **Requires Captain approval gate based on Python PoC results before any production code is written.**
- **Option D (gated product decision):** Downgrade D-001 to Informational if Options A+B yield sufficient improvement or the Captain determines the gap is not a current priority. **Requires explicit Captain approval.**

## Capabilities

### New Capabilities

*(none)*

### Modified Capabilities

- `iterative-subtraction`: Soft SNR-scaled attenuation requirement replaces the hard-zero suppression requirement (Option B). If Option C proceeds, amplitude-tracked synthesis and residual rebuild requirements are added. Pass count, logging, and dedup requirements are unchanged.
- `ft8lib-interop`: Version constant and committed binaries may be updated if Option A yields an upstream improvement. No structural changes to the interop contract.

## Impact

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — Option B: attenuation factor computation. Option C (if approved): carrier estimation and synthesis functions.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, `linux-x64/libft8.so`, `osx-arm64/libft8.dylib` — rebuilt for any shim change (Options A, B, or C).
- `openspec/specs/iterative-subtraction/spec.md` — requirements updated for soft attenuation (Option B) and optionally for amplitude-tracked SIC (Option C).
- `openspec/specs/ft8lib-interop/spec.md` — version constant updated if Option A or B changes the shim version.
- `tests/OpenWSFZ.Ft8.Tests/` — existing `IterativeSubtractionTests` updated; new tests for soft attenuation behaviour.
- `qa/rr-study/` — S7 R&R scenario re-run after each implemented option to validate no regression and measure any improvement.
- No changes to managed API surface, UI, configuration, or any layer above `OpenWSFZ.Ft8`.
