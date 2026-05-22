## 1. Project Scaffolding

- [x] 1.1 Add `src/OpenWSFZ.Ft8/OpenWSFZ.Ft8.csproj` referencing `OpenWSFZ.Abstractions`; target `net10.0`
- [x] 1.2 Add `tests/OpenWSFZ.Ft8.Tests/OpenWSFZ.Ft8.Tests.csproj` referencing `OpenWSFZ.Ft8`, `OpenWSFZ.Abstractions`, and the xUnit packages already in `Directory.Packages.props`
- [x] 1.3 Add both new projects to `OpenWSFZ.slnx` under the existing `/src/` and `/tests/` folders
- [x] 1.4 Verify `dotnet build -c Release` exits 0 with no warnings (empty projects)

## 2. Abstractions

- [x] 2.1 Add `DateTime UtcNow { get; }` to `IClock` in `OpenWSFZ.Abstractions`
- [x] 2.2 Add `DecodeResult` record to `OpenWSFZ.Abstractions`: `string Time`, `int Snr`, `double Dt`, `int FreqHz`, `string Message`
- [x] 2.3 Flesh out `IModeDecoder` in `OpenWSFZ.Abstractions`: `Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct)`
- [x] 2.4 Add `SystemClock` implementation in `OpenWSFZ.Ft8` (wraps `DateTime.UtcNow`)
- [x] 2.5 Add `FakeClock` in `OpenWSFZ.Ft8.Tests` with a settable `UtcNow` property for deterministic tests
- [x] 2.6 Register `DecodeResult` in `AppJsonContext` (AOT-safe `System.Text.Json` serialisation)
- [x] 2.7 Verify `dotnet build -c Release` still exits 0

## 3. Goertzel Symbol Demodulation

- [x] 3.1 Implement `GoertzelDetector` in `OpenWSFZ.Ft8`: computes energy at a single target frequency over a `Span<float>` sample window using the Goertzel algorithm
- [x] 3.2 Implement `SymbolExtractor` in `OpenWSFZ.Ft8`: iterates the 79 symbol intervals (1920 samples each at 12 kHz / 6.25 Hz spacing), calls `GoertzelDetector` for each of the 8 tone frequencies, and builds a `float[79, 8]` log-energy grid
- [x] 3.3 Unit test (`Ft8Decoder: GoertzelDetectorTests`): synthetic single-tone buffer at a known frequency → correct energy peak bin in the expected symbol slot

## 4. Costas-Array Synchronisation

- [x] 4.1 Embed the FT8 Costas array pattern constant (`int[7]` of tone indices) per the specification
- [x] 4.2 Implement `CostasSynchroniser` in `OpenWSFZ.Ft8`: slides the 7×7 Costas template across the energy grid in both time (symbol offset) and frequency (tone-bin offset) dimensions; returns a list of `(symbolOffset, freqBinOffset, score)` candidates above a correlation threshold
      — **v1 note**: frequency sweep only; symbol offset is fixed at 0 (see task 4.2-bis)
- [x] 4.2-bis Add time-domain sweep to `CostasSynchroniser`: outer loop over candidate symbol offsets (0 to ~15, covering ±1 s at 1920 samples/symbol); pass `symbolOffset` as `startSample` to `SymbolExtractor.Extract`; update `CostasSynchroniserTests` to exercise a non-zero symbol offset. Required before the WAV fixture test is enabled; documented as v1 known limitation in `design.md` until resolved.
- [x] 4.3 Unit test (`Ft8Decoder: CostasSynchroniserTests`): energy grid derived from a synthetic FT8-framed buffer → synchroniser returns a candidate with correct symbol offset and frequency bin

## 5. LDPC(174,87) Decoder and CRC-14

- [x] 5.1 Embed the LDPC(174,87) parity-check matrix `H` (87×174 bits) as a constant from the FT8 specification (compact packed-byte representation)
- [x] 5.2 Implement `LdpcDecoder` in `OpenWSFZ.Ft8`: min-sum flooding schedule, up to 50 iterations; accepts `float[174]` LLRs; returns `byte[87]` payload bits or `null` if not converged
- [x] 5.3 Implement `Crc14` in `OpenWSFZ.Ft8`: compute and verify CRC-14 over the 77-bit message using the FT8 specification polynomial (`0x2757`)
- [x] 5.4 Unit test (`Ft8Decoder: LdpcDecoderTests`): reference LLR vector from spec → decoder converges and `Crc14.Check` passes
- [x] 5.5 Unit test (`Ft8Decoder: LdpcDecoderTests`): 1 000 random LLR vectors → fewer than 1 false-positive CRC pass

## 6. 77-Bit Message Unpacking

- [x] 6.1 Implement `MessageUnpacker` in `OpenWSFZ.Ft8`: maps the 77-bit payload to a human-readable string for standard FT8 message types (Type 1: callsign/grid/report; Type 2: DX pedition; Type 0.5: free text)
- [x] 6.2 Implement hex fallback in `MessageUnpacker`: unrecognised type indicator → 20-character hex string of the 77 bits
- [x] 6.3 Unit test (`Ft8Decoder: MessageUnpackerTests`): reference 77-bit vectors for at least 3 standard exchange examples → expected human-readable strings
- [x] 6.4 Unit test (`Ft8Decoder: MessageUnpackerTests`): 77-bit vector with unrecognised type bits → 20-character hex string

## 7. Ft8Decoder Assembly

- [x] 7.1 Implement `Ft8Decoder : IModeDecoder` in `OpenWSFZ.Ft8`: orchestrates `SymbolExtractor` → `CostasSynchroniser` → LLR computation → `LdpcDecoder` → `Crc14` → `MessageUnpacker` for each sync candidate; collects `DecodeResult` records; de-duplicates identical messages within a cycle
- [x] 7.2 Inject `IClock` into `Ft8Decoder` constructor; use `IClock.UtcNow` to set `DecodeResult.Time` (UTC cycle-start rounded to the nearest 15-second boundary)
- [x] 7.3 Integration test (`Ft8Decoder: Ft8DecoderFixtureTests`): load WAV fixture from `tests/OpenWSFZ.Ft8.Tests/Fixtures/`; call `DecodeAsync`; assert at least one `DecodeResult` whose `Message` matches the reference string from the fixture metadata file

## 8. WAV Fixture

- [ ] 8.1 Obtain or synthesise a 15-second 12 kHz mono WAV clip containing at least one valid FT8 transmission with known decode output; name it `ft8-sample.wav`  ← NEEDS REAL AUDIO CAPTURE
- [ ] 8.2 Commit `ft8-sample.wav` and `ft8-sample.ref` (reference decode lines, one per result) to `tests/OpenWSFZ.Ft8.Tests/Fixtures/`; embed both as `EmbeddedResource` in the test project  ← NEEDS REAL AUDIO CAPTURE

## 9. CycleFramer

- [x] 9.1 Implement `CycleFramer` in `OpenWSFZ.Ft8`: constructor takes `ChannelReader<float[]>` and `IClock`; `RunAsync(ChannelWriter<float[]> output, CancellationToken ct)` accumulates chunks, aligns window boundaries to UTC even-second multiples of 15, pads the first window with leading zeros when starting mid-cycle, writes 180 000-sample arrays to `output`
- [x] 9.2 Unit test (`Ft8Decoder: CycleFramerTests`): `FakeClock` starting at second 0 of a cycle, synthetic chunks totalling > 30 s → exactly 2 windows emitted, each 180 000 samples
- [x] 9.3 Unit test (`Ft8Decoder: CycleFramerTests`): `FakeClock` starting 7 s into a cycle → first window has 84 000 leading zeros, remaining samples match injected audio
- [x] 9.4 Unit test (`Ft8Decoder: CycleFramerTests`): cancellation mid-accumulation → `RunAsync` returns, output channel is completed, no exception thrown

## 10. Daemon Wiring

- [x] 10.1 Instantiate `SystemClock`, `CycleFramer`, and `Ft8Decoder` in `Program.cs`; route `CycleFramer` output channel to an internal `Channel<DecodeResult[]>`
- [x] 10.2 On `ApplicationStarted`: start `CycleFramer.RunAsync` on a background `Task` alongside the existing `CaptureManager.StartAsync` call (only when a device is configured)
- [x] 10.3 Start a decode-pump `Task` that reads `DecodeResult[]` from the output channel and calls `WebSocketHub.BroadcastDecodes`
- [x] 10.4 On `ApplicationStopping`: cancel the `CycleFramer` CTS, await the framer task (up to 3 s timeout), then stop `CaptureManager` as before
- [x] 10.5 On `configStore.OnSaved` device-change: restart `CycleFramer` alongside the existing `CaptureManager` restart

## 11. WebSocket Broadcast

- [x] 11.1 Add `BroadcastDecodes(IReadOnlyList<DecodeResult> results)` method to `WebSocketHub`
- [x] 11.2 Serialise the `decode` event as `{ "type": "decode", "payload": [...] }` using `AppJsonContext`; register a `JsonSerializerContext` entry for `DecodeResult[]` or `List<DecodeResult>`
- [x] 11.3 Send to each tracked active connection with a per-send `CancellationTokenSource` timeout of 1 second; catch `OperationCanceledException` and close + remove the stale socket
- [x] 11.4 Update `WebSocketHub` to maintain a thread-safe set of active connections (needed for broadcast; single-connection loop is insufficient)
- [x] 11.5 Update existing WebSocket integration test to assert that a `decode` event arrives after the test harness injects a result into the decode channel

## 12. UI Decode Handler

- [x] 12.1 In `web/js/main.js`, add a `decode` branch to the existing WS event dispatch: extract `event.payload` array
- [x] 12.2 For each result in the payload, prepend a `<tr>` to `#decodes-body` with cells for Time, dB (`snr`), DT (`dt` formatted to 1 decimal place), Freq (`freqHz`), and Message
- [x] 12.3 On first non-empty decode event, remove the placeholder `<tr class="td-no-data">` row
- [x] 12.4 After inserting new rows, trim `#decodes-body` to a maximum of 200 rows (remove from the bottom)

## 13. Traceability and Build Verification

- [x] 13.1 Update `traceability-debt.md`: remove `FR-001` and `FR-009` from the debt list (they are now implemented)
- [x] 13.2 Verify `dotnet build -c Release` exits 0 with 0 warnings across all projects
- [x] 13.3 Verify `dotnet test -c Release` exits 0 with all tests green (including all new `OpenWSFZ.Ft8.Tests`)
  — Re-certified after QA-review fixes (2026-05-21): 0 failed, 119 passed, 1 skipped (WAV fixture, needs real audio)
  — Fixed: B1 heartbeat test loop; B2 `LdpcDecoder.InfoBits = 91`; S1 dead code; S2 XSS innerHTML→textContent; S3 Array.IndexOf→pre-computed VarNeighboursIdx
- [ ] 13.4 Manual smoke test: start daemon with a configured audio device, open `http://127.0.0.1:8080`, confirm decoded FT8 rows appear in the table after one 15-second cycle
- [ ] 13.5 Commit all changes to `feat/p5-ft8-decoder`, push, and open a draft PR to `main`

## 14. Known Follow-Up Items

- [x] 14.1 (S4) Guard concurrent `SendAsync` calls on the same WebSocket in `WebSocketHub.BroadcastDecodes`. Current fire-and-forget pattern is safe at 15-second decode intervals but not resilient to rapid back-to-back decode cycles (e.g. WAV fixture testing). Implement per-socket `SemaphoreSlim` or `Channel`-based send queue before enabling the WAV fixture test and high-throughput scenarios.
