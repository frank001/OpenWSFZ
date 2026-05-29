## 1. Study ft8_lib source and plan the shim

- [ ] 1.1 Clone `kgoba/ft8_lib` at the latest tagged release; read `ft8/decode.h`, `ft8/decode.c`, and `example/decode_ft8.c` to identify the highest-level decode entry point and its exact signature
- [ ] 1.2 Determine whether ft8_lib exposes a single "decode all signals from PCM" function or whether the caller must orchestrate the sync + LDPC + iterative-subtraction loop; document the chosen integration point in `src/OpenWSFZ.Ft8/Native/BUILD.md`
- [ ] 1.3 Confirm the `FT8Result`-equivalent struct fields available from ft8_lib (freq_hz, dt, snr, message text); document the mapping to `DecodeResult` fields (including any unit conversions)
- [ ] 1.4 Record the chosen git tag/commit SHA in `src/OpenWSFZ.Ft8/Native/BUILD.md`

## 2. Add ft8_lib as a git submodule

- [ ] 2.1 `git submodule add https://github.com/kgoba/ft8_lib.git native/ft8_lib` at the pinned commit from task 1.4
- [ ] 2.2 Confirm `LicenseInventoryCheck` enumerates `native/ft8_lib` with `MIT` and G5 gate stays green (`dotnet run --project tools/LicenseInventoryCheck`)
- [ ] 2.3 Update `traceability-debt.md` if the new `ft8lib-interop` capability requires a new FR/NFR entry in `REQUIREMENTS.md`; add it and cite the ID in the relevant test display names

## 3. Write the C shim and compile libft8.dll

- [ ] 3.1 Write `src/OpenWSFZ.Ft8/Native/ft8_shim.c` implementing: `ft8_lib_version_check()` returning a compile-time constant; `ft8_decode_all(const float* pcm, int pcm_len, FT8Result* results, int max_results)` wrapping the ft8_lib decode pipeline
- [ ] 3.2 Define the `FT8Result` C struct (`int freq_hz`, `float dt`, `int snr`, `char message[32]`) in `ft8_shim.h`; document `sizeof(FT8Result)` as the value that the managed `Marshal.SizeOf<Ft8NativeResult>()` must match
- [ ] 3.3 Compile `libft8.dll` (Windows x64) using MSVC or MinGW; link against the ft8_lib object files from the submodule; confirm the DLL exports `ft8_lib_version_check` and `ft8_decode_all`
- [ ] 3.4 Commit `libft8.dll` to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and `libft8.version.txt` (source commit SHA, compiler version, build date)
- [ ] 3.5 Commit `ft8_shim.c` and `ft8_shim.h` to `src/OpenWSFZ.Ft8/Native/` so the DLL is reproducible

## 4. P/Invoke binding layer

- [ ] 4.1 Add `src/OpenWSFZ.Ft8/Interop/Ft8NativeResult.cs` — `[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]` struct with fields matching `FT8Result`; assert `Marshal.SizeOf<Ft8NativeResult>()` equals the documented C struct size in an `#if DEBUG` guard or static constructor
- [ ] 4.2 Add `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — lazy `NativeLibrary.Load("libft8.dll", ...)` singleton; `[DllImport]` declarations for `ft8_lib_version_check` and `ft8_decode_all`; ABI self-test on first load; `DecodeAll(float[] pcm)` public method that validates length, pins the array, calls native, and returns `Ft8NativeResult[]`
- [ ] 4.3 Declare `<Content Include="Native\win-x64\libft8.dll" CopyToOutputDirectory="Always" />` in `OpenWSFZ.Ft8.csproj`
- [ ] 4.4 `dotnet build -c Release` — 0 errors, 0 warnings; confirm `libft8.dll` appears in `bin/Release/net10.0/`

## 5. Rewrite Ft8Decoder

- [ ] 5.1 Rewrite `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — replace the Bluestein spectrogram + Costas + LDPC pipeline with a single call to `Ft8LibInterop.DecodeAll(pcm)`; map each `Ft8NativeResult` to a `DecodeResult` (Time from `_clock`, Snr, Dt, FreqHz, Message)
- [ ] 5.2 Retain the RMS silence guard (skip cycle if RMS < 1e-6) — keeps the all-zero codeword protection and matches the existing observable behaviour
- [ ] 5.3 Retain the diagnostic log line (`Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms`) so the `Decode diagnostic log` spec requirement is met
- [ ] 5.4 `dotnet build -c Release` — 0 errors, 0 warnings

## 6. Retire homegrown DSP classes and tests

- [ ] 6.1 Delete `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs`, `CostasSynchroniser.cs`, `LdpcDecoder.cs`, `Crc14.cs`, `MessageUnpacker.cs`
- [ ] 6.2 Delete the corresponding test files: `SymbolExtractorTests.cs`, `GoertzelDetectorTests.cs`, `MessageUnpackerTests.cs` and any other test files that exclusively test the retired DSP classes
- [ ] 6.3 Retain `WavReader.cs` and `WavReaderTests.cs` — these are test-harness utilities, not DSP pipeline code
- [ ] 6.4 Retain `RealSignalFixtureTests.cs`, `ReplayHarnessTests.cs`, `WsjtxAllTxtParser.cs`, and `Ft8DecoderFixtureTests.cs` (round-trip internal-consistency check)
- [ ] 6.5 `dotnet build -c Release` — 0 errors, 0 warnings after deletions

## 7. G6 gate — verify correctness

- [ ] 7.1 `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "RealSignal"` — all three `RealSignalFixtureTests` must pass (G6 gate green)
- [ ] 7.2 If any fixture test still fails: check ft8_lib iterative-subtraction pass count (OQ2); reduce answer-key subset to SNR > 0 dB signals only if the target signal is genuinely unrecoverable at the current pass depth; document the decision
- [ ] 7.3 `dotnet test -c Release` — full suite green (0 failures); record final test counts

## 8. Traceability and licence gates

- [ ] 8.1 Update `traceability-debt.md` — remove the NFR-016 deferral entry now that G6 is green; any remaining deferred IDs must still be present
- [ ] 8.2 `dotnet run --project tools/TraceabilityCheck` — G3 gate green
- [ ] 8.3 `dotnet run --project tools/LicenseInventoryCheck` — G5 gate green (ft8_lib MIT entry present)
- [ ] 8.4 `dotnet build -c Release` — G1 gate green (0 errors, 0 warnings)

## 9. Verification and archive

- [ ] 9.1 `dotnet test -c Release` — final full-suite run; all gates green; record counts in a commit message
- [ ] 9.2 CAPTAIN: review G6 results — confirm the three real-signal fixture tests pass and the decoded messages match the committed answer keys
- [ ] 9.3 Open PR to `main`; confirm CI green on all three matrix legs
- [ ] 9.4 QA review; merge on approval; archive this change
