## Why

OpenWSFZ systematically over-reports SNR by **+2.42 dB** (threshold ±2.0 dB), confirmed across three independent R&R study runs with corrected synthesiser audio. The measurement system study verdict is FAIL. The fix is a one-line PCM conditioning step in managed code; the formal SNR accuracy requirement is also absent from the specification and must land alongside the fix.

## What Changes

- **`Ft8Decoder.cs`** — Add a one-pass RMS normalisation of the PCM `float[]` buffer to a fixed target level immediately before calling `Ft8LibInterop.DecodeAll`. No changes to native code, shim, or P/Invoke surface.
- **`ft8-decoder/spec.md`** — Add SNR accuracy requirement: reported SNR SHALL be within ±2.0 dB of true SNR as measured by the R&R S1 scenario, for both appraisers.
- **`ft8lib-interop/spec.md`** — Correct ABI self-test version constant from `20260004` → `20260005` (spec drift introduced by the D-003 diagnostics work; shim was bumped at that time but the spec was not updated).

## Capabilities

### New Capabilities

_(none — this is a defect fix, not a new feature)_

### Modified Capabilities

- `ft8-decoder`: Add SNR accuracy requirement (±2.0 dB bias threshold, R&R S1 pass criterion)
- `ft8lib-interop`: Correct ABI version constant in ABI self-test requirement from `20260004` to `20260005`

## Impact

- **`src/OpenWSFZ.Ft8/Ft8Decoder.cs`** — implementation change (PCM normalisation before native call)
- **`openspec/specs/ft8-decoder/spec.md`** — new requirement section
- **`openspec/specs/ft8lib-interop/spec.md`** — version constant correction
- **No native binaries change** — shim, DLL, SO, and dylib are untouched
- **No API surface change** — `DecodeAll` signature, `Ft8NativeResult` layout, and all public types are unchanged
- **No test count change expected** — existing Ft8.Tests pass unchanged; new unit tests for the normalisation helper and regression test for SNR accuracy added within the same assembly
