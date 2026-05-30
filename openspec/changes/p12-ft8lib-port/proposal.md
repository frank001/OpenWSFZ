## Why

The homegrown FT8 DSP pipeline (Bluestein spectrogram, custom LDPC, custom Costas sync) achieved **0% recovery** across 42 real off-air WAVs containing 887 WSJT-X-decoded signals. Root-cause analysis confirmed the fundamental issue: single-pass decoding cannot separate overlapping co-frequency transmissions on a busy 40 m band. Iterative signal subtraction — decode the strongest signal, subtract it from the PCM buffer, repeat — is required, and it is already implemented and battle-tested in `kgoba/ft8_lib` (MIT licence). Continuing to patch the homegrown approach is not a viable path; the G6 gate will remain permanently red without it.

## What Changes

- Replace the DSP internals of `Ft8Decoder` with a P/Invoke wrapper around the compiled `ft8_lib` native library (`libft8.dll` on Windows).
- `IModeDecoder`, `CycleFramer`, `DecodeResult`, and the `ALL.TXT` logging pipeline remain **unchanged** — the native library sits entirely behind the existing interface.
- Add `libft8.dll` (built from `kgoba/ft8_lib` source, MIT licence) as a committed native asset in `src/OpenWSFZ.Ft8/`.
- Update `LicenseInventoryCheck` inventory to record the `kgoba/ft8_lib` MIT dependency.
- Retire the now-superseded homegrown DSP classes: `SymbolExtractor`, `CostasSynchroniser`, `LdpcDecoder`, `Crc14`, `MessageUnpacker` (all internal to `OpenWSFZ.Ft8`). Tests covering only those classes may be retired alongside them; the real-signal fixture tests (G6 gate) are the correctness oracle going forward.

## Capabilities

### New Capabilities

- `ft8lib-interop`: P/Invoke binding layer between managed C# and the native `libft8` decode API — sample buffer in, `DecodeResult[]` out.

### Modified Capabilities

- `ft8-decoder`: Replace implementation-specific requirements (Costas candidate cap, Goertzel coefficient reuse) with requirements on observable correctness behaviour (real-signal recovery rate, cycle timing budget). The performance and correctness requirements that matter operationally are retained; internal algorithm requirements that no longer apply to the new implementation are removed.
- `dependency-licence-policy`: Add `kgoba/ft8_lib` (MIT) to the approved dependency inventory.

## Impact

- **`src/OpenWSFZ.Ft8/`**: `Ft8Decoder.cs` rewired; DSP classes retired; new `Interop/Ft8LibInterop.cs` P/Invoke binding added; `libft8.dll` committed as an embedded native resource.
- **`tests/OpenWSFZ.Ft8.Tests/`**: Unit tests for retired DSP classes removed; `RealSignalFixtureTests` (G6 gate) must go green — this is the primary acceptance criterion.
- **`tools/LicenseInventoryCheck/`**: Inventory updated with `kgoba/ft8_lib` MIT entry.
- **CI**: No gate changes required; G6 already exists and will go green once the decoder works. The pre-existing `dotnet test` exit-code check will detect the improvement automatically.
- **Distribution**: `libft8.dll` (Windows x64) must be present alongside the daemon executable. This introduces a native binary dependency that must be documented for operators.
