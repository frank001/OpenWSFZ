## MODIFIED Requirements

### Requirement: Real off-air signal recovery (G6 gate) — all three reference platforms

The FT8 decoder SHALL correctly decode real off-air FT8 transmissions captured from the 40 m band on **all three reference platforms** (Windows x64, Linux x64, and macOS ARM64), per **NFR-001**. Given a 15-second PCM window from the committed WAV fixture corpus, the decoder SHALL recover the signals identified by WSJT-X for the same recording.

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
