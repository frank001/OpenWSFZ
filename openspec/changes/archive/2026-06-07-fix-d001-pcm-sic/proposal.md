## Why

OpenWSFZ recovers only 46% of co-channel / time-frequency overlapping signals compared to WSJT-X's 77% (D-001, GitHub #3). The root cause is that the current p15 second pass operates in the spectrogram domain at ±3.125 Hz bin resolution, which cannot coherently cancel co-channel interference. WSJT-X uses PCM-domain successive interference cancellation (SIC): it reconstructs decoded signals as raw audio, subtracts them from the buffer, and re-decodes the residual. Closing this gap meaningfully requires the same technique.

## What Changes

- **Add a PCM-domain subtraction step between decode passes in `ft8_shim.c`**: after pass 1 decodes signals, estimate each decoded signal's carrier frequency to sub-Hz precision via DFT parabolic interpolation, synthesise its CP-FSK waveform in PCM, subtract it from the raw PCM buffer, rebuild the waterfall from the residual, and run a further decode pass on the cleaned waterfall.
- **Increase `K_MAX_PASSES` from 2 to 3**: pass 0 = full waterfall decode, pass 1 = PCM-subtraction residual decode (new), pass 2 = spectrogram-domain residual decode on whatever remains. The existing spectrogram-domain suppression (`suppress_candidate_tiles`) is retained as pass 2 and now operates on a PCM-cleaned waterfall, compounding the two approaches.
- **Bump `FT8_SHIM_VERSION` to `20260003`** to reflect the ABI change (new pass count).
- **Update managed constants** in `Ft8LibInterop.cs`: `MaxDecodePasses → 3`, `MaxResults → 480` (140 + 200 + 140), `ExpectedShimVersion → 20260003`.
- **Rebuild and commit native binaries** for all three platforms (win-x64, linux-x64, osx-arm64).

No breaking changes to the `IModeDecoder` interface or `Ft8Decoder` public API.

## Capabilities

### New Capabilities

_None — the PCM-domain SIC is an extension of the existing iterative-subtraction capability, not a new standalone capability._

### Modified Capabilities

- `iterative-subtraction`: adds PCM-domain sub-Hz carrier estimation, CP-FSK waveform synthesis, PCM subtraction, and waterfall rebuild requirements; updates AC-IS-1 recovery-rate target; adds new acceptance criteria for the PCM subtraction step.
- `ft8lib-interop`: bumps expected `FT8_SHIM_VERSION` to `20260003`; updates `MaxDecodePasses` to 3; updates `MaxResults` buffer sizing; updates committed binary manifests for all three platforms.

## Impact

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — main change: new `pcm_subtract_decoded_signals()` function, rebuilt waterfall, third pass.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — no new exported functions (same ABI surface); version constant bump only.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — three constant updates.
- `src/OpenWSFZ.Ft8/Native/{win-x64,linux-x64,osx-arm64}/libft8.*` — rebuilt binaries.
- `src/OpenWSFZ.Ft8/Native/libft8.version.txt` — updated build records.
- `tests/OpenWSFZ.Ft8.Tests/` — new/updated tests for PCM SIC pass count and recovery rate.
- `openspec/specs/iterative-subtraction/spec.md` — delta requirements.
- `openspec/specs/ft8lib-interop/spec.md` — version constant and buffer-size updates.
