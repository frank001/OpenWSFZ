## Context

The homegrown `Ft8Decoder` pipeline consists of five internal DSP classes: `SymbolExtractor` (Bluestein chirp-Z spectrogram), `CostasSynchroniser` (sync detection), `LdpcDecoder` (soft-decision LDPC), `Crc14` (CRC-14 verification), and `MessageUnpacker` (77-bit payload decode). After eleven rounds of DSP iteration it achieved 0% recovery on 42 real off-air WAVs. The definitive root cause is architectural — single-pass decoding cannot unmix overlapping co-frequency signals, and iterative subtraction is needed. `kgoba/ft8_lib` (MIT, [github.com/kgoba/ft8_lib](https://github.com/kgoba/ft8_lib)) implements the complete WSJT-X decode pipeline in ~3 000 lines of C, including iterative subtraction. It is the same algorithm used by WSJT-X and is known to decode real off-air signals correctly.

The change boundary is clean: `IModeDecoder.DecodeAsync(float[] pcm, CancellationToken)` is the only caller-visible interface. Everything inside `Ft8Decoder` can be replaced without touching `CycleFramer`, `DecodeResult`, `ALL.TXT` logging, or any higher layer.

## Goals / Non-Goals

**Goals:**
- Make the three `RealSignalFixtureTests` (G6 gate) go green.
- Replace the homegrown DSP internals with a P/Invoke binding to `libft8` while preserving the `IModeDecoder` contract exactly.
- Keep the build reproducible: no C toolchain required on developer machines or CI runners — the compiled `libft8.dll` is committed to the repository.
- Retire all five homegrown DSP classes and their associated unit tests; the real-signal fixture tests become the sole correctness oracle.

**Non-Goals:**
- A full C# source translation of `ft8_lib` (considered and rejected — see Decisions).
- Support for Linux or macOS native binaries in this change (Windows x64 only; cross-platform is a future concern).
- Exposing any `ft8_lib` internals above the `IModeDecoder` boundary.
- Changing `CycleFramer`, `DecodeResult`, `ALL.TXT`, or any other layer.

## Decisions

### D1 — P/Invoke wrapper over a full C# translation

**Chosen:** P/Invoke to a pre-compiled native `libft8.dll`.

**Alternatives considered:**
- *Full C# translation*: Translating ~3 000 lines of C to C# eliminates the native dependency but introduces a high risk of silent translation errors in the LDPC belief-propagation and iterative-subtraction logic. These bugs would be nearly impossible to distinguish from correct algorithm behaviour without an exhaustive test corpus. The translation cost is high and the correctness risk is unacceptable given the prior history of homegrown algorithm errors.
- *Managed wrapper around the `ft8_lib` executable*: Spawning a subprocess per cycle is too slow (process start overhead exceeds the cycle budget) and adds IPC complexity.

P/Invoke gives us the exact, tested algorithm with zero translation risk. The only cost is a native binary dependency, which is manageable on Windows.

### D2 — Pre-compiled DLL committed to the repository

**Chosen:** Build `libft8.dll` once from the tagged `kgoba/ft8_lib` source, commit it to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`. CI uses the committed binary; no C compiler is required in the build environment.

**Alternatives considered:**
- *Build from source in CI*: Adds a MSVC or MinGW step to every CI run. Complicates the CI matrix, adds minutes to the pipeline, and creates a dependency on a C toolchain that the rest of the project does not use.
- *NuGet package*: No existing NuGet package for `ft8_lib`. Creating one is out of scope.

The committed DLL must include the `kgoba/ft8_lib` git tag/commit hash in a companion `libft8.version.txt` file so the provenance is auditable.

### D3 — Thin C shim exposing a single decode function

**Chosen:** Write a small `ft8_shim.c` that wraps the `ft8_lib` internal API into one extern-C function:

```c
int ft8_decode_all(
    const float* pcm,       // 180 000 float32 samples, 12 kHz mono
    int          pcm_len,   // must be 180 000
    FT8Result*   results,   // caller-allocated output array
    int          max_results
);
// Returns number of results written (0..max_results).
// FT8Result: { int freq_hz; float dt; int snr; char message[32]; }
```

The shim calls `ft8_lib`'s internal sync + decode + iterative-subtraction loop and fills the result array. The P/Invoke side marshals `FT8Result` as a `[StructLayout(LayoutKind.Sequential)]` C# struct.

**Why a shim rather than calling ft8_lib internals directly:** The ft8_lib internal API evolves; a shim isolates the P/Invoke declarations from those changes. The shim also handles the result buffer convention (fixed-size array, count return) which is simpler to marshal than ft8_lib's internal linked-list structures.

### D4 — Embed libft8.dll as an MSBuild content file; load via NativeLibrary.Load

**Chosen:** Mark `libft8.dll` as `<Content CopyToOutputDirectory="Always"/>` in the `.csproj`. At runtime `Ft8LibInterop` calls `NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, "libft8.dll"))` once (lazy, thread-safe singleton). No extraction from embedded resources — the DLL sits alongside the exe in the output directory, which is the standard pattern for .NET native dependencies.

### D5 — Retire all five homegrown DSP classes

**Chosen:** Delete `SymbolExtractor`, `CostasSynchroniser`, `LdpcDecoder`, `Crc14`, `MessageUnpacker` and all tests that cover only those classes. The G6 real-signal fixture tests are the correctness oracle; internal DSP unit tests are superseded.

**Rationale:** Keeping dead code alongside the new implementation creates maintenance confusion and false coverage signals. The `RealSignalFixtureTests` (end-to-end, against committed off-air WAVs) is a stronger oracle than any unit test of internal DSP logic.

Exception: `WavReader` and `WavReaderTests` are retained — they are independent utilities used by the test harness, not part of the decode pipeline.

## Risks / Trade-offs

**[Risk] libft8.dll is a pre-compiled binary committed to the repo** → Mitigation: document the build procedure in `src/OpenWSFZ.Ft8/Native/BUILD.md` (compiler version, flags, source commit hash) so the DLL can be reproduced. The MIT licence and source commit hash are recorded in `libft8.version.txt` beside the DLL.

**[Risk] ft8_lib iterative subtraction may not recover all G6 fixture signals** → Mitigation: the G6 fixture answer keys use only the top-3 SNR signals per recording — these are the strongest signals on the band and the most likely to be recovered by iterative subtraction. If any still fail after a correct integration, reduce the answer-key subset to signals with SNR > 0 dB.

**[Risk] P/Invoke struct layout mismatch between C shim and C# declaration** → Mitigation: add a self-test in `Ft8LibInterop` that calls a sentinel function (`ft8_version()`) and asserts the returned integer matches the expected value; this catches ABI mismatches at startup rather than silently producing garbage results.

**[Risk] Thread safety of ft8_lib under `Parallel.For`** → The existing `Ft8Decoder.DecodeAsync` uses `Parallel.For` across time-domain sweep positions. The `ft8_lib` decode functions use only stack-local state; calling them concurrently from multiple threads is safe. However, the new design calls `ft8_decode_all` once per cycle (not per sweep), so `Parallel.For` is removed — ft8_lib's own iterative-subtraction loop is already inherently sequential.

**[Risk] DLL not found at runtime in test runner** → MSBuild `CopyToOutputDirectory` ensures the DLL is in the test output directory; add an xUnit assembly fixture that calls `NativeLibrary.Load` and fails fast with a clear message if the DLL is absent.

## Migration Plan

1. Clone `kgoba/ft8_lib` at a pinned tag; write `ft8_shim.c`; compile `libft8.dll` locally (MSVC or MinGW).
2. Add the DLL to `src/OpenWSFZ.Ft8/Native/win-x64/` with provenance files; update `.csproj`.
3. Write `Ft8LibInterop.cs` (P/Invoke declarations, `NativeLibrary.Load`, struct marshal).
4. Rewrite `Ft8Decoder.cs` to call `Ft8LibInterop.DecodeAll()` and map `FT8Result[]` → `DecodeResult[]`.
5. Run `dotnet test` — G6 gate expected to go green; retire DSP classes and their tests.
6. Update `LicenseInventoryCheck` inventory; confirm G5 gate green.
7. Update `traceability-debt.md` to remove NFR-016 (G6 now green, no longer deferred).

**Rollback:** The homegrown DSP classes are deleted, not deprecated. Rollback requires reverting the commit. Given the homegrown approach is definitively non-functional, rollback is not a viable option — the correct path if P/Invoke integration fails is to debug the shim, not restore the old DSP.

## Open Questions

**OQ1 — ft8_lib API surface**: The exact function signatures in `ft8_lib` must be confirmed by reading the source before writing the shim. The decode entry point may be `ft8_decode()`, `ft8_multi_decode()`, or a higher-level helper depending on the version. *Resolution: first task in implementation is to read `ft8_lib` source and document the chosen entry point.*

**OQ2 — Iterative subtraction depth**: ft8_lib's iterative subtraction runs a configurable number of passes. The default (3 passes) is likely sufficient for the G6 fixtures, but may need tuning for a busy 40 m band with 20+ simultaneous signals. *Resolution: use the default in the first integration; tune only if G6 tests still fail.*

**OQ3 — SNR and Dt field mapping**: ft8_lib reports SNR and time offset (dt) in its result struct. The mapping to `DecodeResult.Snr` (int, dB) and `DecodeResult.Dt` (double, seconds) must be confirmed against WSJT-X conventions. *Resolution: document the mapping in `Ft8LibInterop.cs` XML doc.*
