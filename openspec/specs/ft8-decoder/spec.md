# ft8-decoder Specification

## Purpose
TBD - created by archiving change p8-ft8-decode-performance. Update Purpose after archive.
## Requirements
### Requirement: FT8 decode cycle completes within the 15-second budget

The FT8 decoder SHALL complete a full decode cycle — including all time-domain sweep positions, Costas candidate detection, Goertzel extraction, LDPC decode, and CRC verification — within **13 seconds** of wall-clock time on a single modern CPU core, leaving at least 2 seconds headroom before the next cycle window is delivered by the framer.

#### Scenario: Decode completes within budget on a multi-signal fixture

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a PCM buffer containing 8 simultaneous synthetic FT8 signals at distinct frequencies with additive noise
- **THEN** the method SHALL return within 10,000 ms (CI budget, allowing for runner variance) and SHALL decode at least 6 of the 8 known messages

#### Scenario: Decode does not stall the cycle pump on a live band

- **WHEN** a continuous stream of 15-second PCM windows is delivered by `CycleFramer` on a band with up to 30 simultaneous FT8 transmissions
- **THEN** the decode pump SHALL complete each window before the second subsequent window arrives (i.e., at most one window queued at any time during steady-state operation)

---

### Requirement: Costas candidate count is bounded relative to signal density

The FFT-based Costas scan SHALL produce no more than **2 candidates per (time-position, base-frequency) sweep pair**. Excess candidates above this cap SHALL be discarded before Goertzel extraction is performed.

#### Scenario: Candidate count does not exceed cap on a busy band

- **WHEN** `Ft8Decoder.DecodeAsync` processes a PCM window containing 20 simultaneous FT8 signals
- **THEN** the total number of Goertzel `Extract` calls SHALL be no greater than 2 × (time positions) × (frequency sweep steps) and SHALL NOT grow proportionally with the number of signals beyond this bound

#### Scenario: Highest-scoring candidates are retained when cap is applied

- **WHEN** a given (time-position, base-frequency) sweep pair produces more than 2 Costas candidates above the threshold
- **THEN** the 2 candidates with the highest normalised Costas scores SHALL be retained and the remainder discarded

---

### Requirement: Decode diagnostic log reports elapsed time per cycle

The decode cycle log line SHALL include the wall-clock elapsed time in milliseconds so that performance regressions are visible to the operator without external instrumentation.

#### Scenario: Elapsed time appears in the cycle log line

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle
- **THEN** the logged Information message SHALL include an `elapsed` field in milliseconds, e.g. `elapsed=2341 ms`, alongside the existing Costas/LDPC/CRC diagnostic counters

---

### Requirement: Goertzel extraction coefficients are computed once per call

For a given call to `SymbolExtractor.Extract`, the 15 Goertzel frequency coefficients (one per tone column) SHALL be computed exactly once and reused across all 79 symbol windows. Recomputing `MathF.Cos` per (symbol, tone) pair is prohibited.

#### Scenario: Coefficient computation does not scale with symbol count

- **WHEN** `SymbolExtractor.Extract` is called for a signal at any base frequency
- **THEN** the number of `MathF.Cos` evaluations SHALL equal the number of tone columns (15), not the number of (symbol × column) pairs (1,185)

---

### Requirement: IModeDecoder interface

The `IModeDecoder` interface in `OpenWSFZ.Abstractions` SHALL declare a single method
`DecodeAsync(float[] pcm, CancellationToken ct)` returning
`Task<IReadOnlyList<DecodeResult>>`. The `pcm` parameter SHALL contain exactly 15 seconds of
12 kHz mono float32 samples (180 000 samples). Implementations SHALL return an empty list
when no valid FT8 messages are found; they SHALL NOT throw for zero-decode cycles.

#### Scenario: DecodeAsync returns empty list for silent audio

- **WHEN** `DecodeAsync` is called with 180 000 samples of silence (all zeros)
- **THEN** the implementation SHALL return an empty `IReadOnlyList<DecodeResult>` without throwing

#### Scenario: DecodeAsync returns at least one result for a fixture with known decodes

- **WHEN** `DecodeAsync` is called with the canonical WAV fixture loaded from
  `tests/OpenWSFZ.Ft8.Tests/Fixtures/`
- **THEN** the implementation SHALL return at least one `DecodeResult` whose `Message`
  matches a known reference string from the fixture's accompanying reference file

#### Scenario: DecodeAsync respects cancellation

- **WHEN** the `CancellationToken` is cancelled during a decode pass
- **THEN** `DecodeAsync` SHALL throw `OperationCanceledException` and SHALL NOT return a
  partial result list

---

### Requirement: DecodeResult record

The `DecodeResult` record in `OpenWSFZ.Abstractions` SHALL expose the following properties:
`string Time` (UTC cycle start, format `HH:mm:ss`), `int Snr` (dB, relative to 2500 Hz
noise floor), `double Dt` (seconds, timing offset of the transmission within the cycle),
`int FreqHz` (audio offset in Hz of the strongest tone), `string Message` (decoded text).

#### Scenario: DecodeResult round-trips through JSON serialisation

- **WHEN** a `DecodeResult` is serialised to JSON via `System.Text.Json` and deserialised
  back
- **THEN** all five fields SHALL be equal to the original values

---

### Requirement: IClock interface

The `IClock` interface in `OpenWSFZ.Abstractions` SHALL declare a single property
`DateTime UtcNow { get; }` returning the current UTC time. A production implementation
`SystemClock` wrapping `DateTime.UtcNow` SHALL be registered as a singleton. A
`FakeClock` with a settable `UtcNow` SHALL be available in the test assembly for
deterministic cycle-alignment tests.

#### Scenario: SystemClock.UtcNow is within 1 second of DateTime.UtcNow

- **WHEN** `SystemClock.UtcNow` is read
- **THEN** the returned value SHALL be within 1 second of `DateTime.UtcNow` (Kind = Utc)

---

### Requirement: CycleFramer produces UTC-aligned 15-second audio windows

`CycleFramer` SHALL consume `float[]` chunks from `CaptureManager.Samples` and emit one
exactly-180 000-sample buffer per FT8 cycle. Cycle boundaries SHALL align to even UTC second
boundaries (:00 and :15 of each minute). If the framer starts mid-cycle it SHALL pre-fill
the leading portion of the current window with zeros and complete the window normally.

#### Scenario: CycleFramer emits one window per 15-second cycle

- **WHEN** `CycleFramer` receives a continuous stream of audio chunks spanning two or more
  cycle boundaries (provided by a `FakeClock` and synthetic chunks)
- **THEN** it SHALL emit exactly one `float[]` of length 180 000 per cycle boundary crossed

#### Scenario: CycleFramer pads the first window when starting mid-cycle

- **WHEN** `CycleFramer` starts at an offset of `T` seconds into a cycle (e.g., `T = 7`)
  as indicated by `FakeClock.UtcNow`
- **THEN** the first emitted window SHALL contain `T × 12 000` leading zero samples followed
  by the audio received during the remaining `(15 − T) × 12 000` samples of that cycle

#### Scenario: CycleFramer stops cleanly on cancellation

- **WHEN** the `CancellationToken` passed to `CycleFramer.RunAsync` is cancelled
- **THEN** `RunAsync` SHALL return without throwing and the output channel SHALL be completed

---

### Requirement: FT8 LDPC(174,87) soft-decision decode

`Ft8Decoder` SHALL implement LDPC(174,87) soft-decision decoding using log-likelihood ratios
derived from symbol energies. The generator matrix `H` SHALL be embedded as a constant from
the FT8 specification. The decoder SHALL run up to 50 min-sum flooding iterations per
candidate and SHALL accept a codeword if and only if the CRC-14 check passes.

#### Scenario: Known-good LDPC codeword is accepted

- **WHEN** `Ft8Decoder` processes an LLR vector derived from a reference codeword from the
  specification appendix
- **THEN** the decoder SHALL converge within 50 iterations and the CRC-14 check SHALL pass

#### Scenario: Random noise LLR vector is rejected

- **WHEN** `Ft8Decoder` processes an LLR vector derived from pure random noise
- **THEN** the decoder SHALL return no decoded message (CRC-14 check failure) for the
  overwhelming majority of trials (false-positive rate SHALL be below 1 in 1 000 trials)

---

### Requirement: 77-bit message unpacking

The 77-bit payload extracted after LDPC and CRC-14 SHALL be unpacked into a human-readable
message string. Standard FT8 messages (callsign/grid/report format) SHALL be decoded to the
conventional text representation used by WSJT-X (e.g., `"W1AW K1TTT EN43"`). Non-standard
messages or bit patterns not conforming to a known standard format SHALL be represented as
`"<hex>"` where `<hex>` is the 20-character hexadecimal encoding of the 77 bits.

#### Scenario: Standard callsign/grid/report message is decoded to text

- **WHEN** a 77-bit payload corresponding to a standard FT8 exchange is unpacked
- **THEN** the resulting `Message` string SHALL match the human-readable form of that exchange

#### Scenario: Unknown message type is represented as hex

- **WHEN** a 77-bit payload with a message type indicator not recognised by the unpacker is
  processed
- **THEN** the `Message` string SHALL be the 20-character hex representation of the 77 bits

---

### Requirement: Costas-array synchronisation

`Ft8Decoder` SHALL locate FT8 transmissions within the 15-second window by cross-correlating
the received time–frequency grid against the known 7-symbol Costas array pattern at positions
0, 36, and 72 within the 79-symbol transmission. The synchroniser SHALL search across the
full audio passband (0–6000 Hz) and SHALL report the audio frequency of each candidate.

#### Scenario: Synchroniser finds a transmission at a known frequency

- **WHEN** a synthetic 8-FSK signal at a known audio offset is embedded in a quiet buffer
  and fed to `Ft8Decoder`
- **THEN** the reported `FreqHz` in the `DecodeResult` SHALL be within 12 Hz of the actual
  offset (two tone-spacing bins)

