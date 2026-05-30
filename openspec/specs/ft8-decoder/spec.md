# ft8-decoder Specification

## Purpose
Specifies the behavioural requirements for the OpenWSFZ FT8 decoder component. The decoder accepts a 15-second 12 kHz mono PCM buffer and returns all decodable FT8 messages present in that window. From p12, decoding is delegated to the `kgoba/ft8_lib` native library via the `ft8lib-interop` layer; see that spec for P/Invoke and ABI requirements.

## Requirements

### Requirement: FT8 decode cycle completes within the 15-second budget

The FT8 decoder SHALL complete a full decode cycle — including all time-domain analysis, sync candidate detection, LDPC decode, iterative signal subtraction, and message unpacking — within **13 seconds** of wall-clock time on a single modern CPU core, leaving at least 2 seconds headroom before the next cycle window is delivered by the framer.

#### Scenario: Decode completes within budget on a multi-signal fixture

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a real off-air PCM buffer containing multiple simultaneous FT8 signals
- **THEN** the method SHALL return within 13 000 ms on a development machine and within 30 000 ms on a CI runner (allowing for runner variance)

#### Scenario: Decode does not stall the cycle pump on a live band

- **WHEN** a continuous stream of 15-second PCM windows is delivered by `CycleFramer` on a band with up to 30 simultaneous FT8 transmissions
- **THEN** the decode pump SHALL complete each window before the second subsequent window arrives (i.e., at most one window queued at any time during steady-state operation)

---

### Requirement: Decode diagnostic log reports elapsed time per cycle

The decode cycle log line SHALL include the wall-clock elapsed time in milliseconds so that performance regressions are visible to the operator without external instrumentation.

#### Scenario: Elapsed time appears in the cycle log line

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle
- **THEN** the logged Information message SHALL include an `elapsed` field in milliseconds, e.g. `elapsed=2341 ms`, alongside the cycle summary counters

---

### Requirement: Real off-air signal recovery (G6 gate) — all three reference platforms

The FT8 decoder SHALL correctly decode real off-air FT8 transmissions captured from the 40 m band on **all three reference platforms** (Windows x64, Linux x64, macOS ARM64), per **NFR-001**. Given a 15-second PCM window from the committed WAV fixture corpus, the decoder SHALL recover the signals identified by WSJT-X for the same recording.

The G6 gate CI check SHALL execute and pass on all three matrix legs (`windows-latest`, `ubuntu-latest`, `macos-latest`). A skip or absence on any leg is a gate failure. The use of `[WindowsOnlyFact]`, `[WindowsOnlyTheory]`, or any equivalent platform-conditional test skip attribute on G6 tests is a violation of this requirement.

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture (Windows)

- **WHEN** `Ft8Decoder.DecodeAsync` is called on Windows with a PCM buffer from the committed fixture corpus (`260528_235745`, `260529_000030`, or `260529_000200`)
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture (Linux)

- **WHEN** `Ft8Decoder.DecodeAsync` is called on Linux x64 with a PCM buffer from the committed fixture corpus
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture (macOS)

- **WHEN** `Ft8Decoder.DecodeAsync` is called on macOS ARM64 with a PCM buffer from the committed fixture corpus
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file

#### Scenario: Decoder produces no decode for a silent buffer

- **WHEN** `Ft8Decoder.DecodeAsync` is called with 180 000 samples of silence (all zeros)
- **THEN** the method SHALL return an empty list without throwing
