## ADDED Requirements

### Requirement: Real-signal WAV test corpus with WSJT-X answer key

The project SHALL maintain a corpus of real off-air FT8 recordings captured as 12 kHz mono WAV files, each paired with the set of FT8 messages that WSJT-X decoded from the identical recording (the "answer key"). Recordings SHALL be obtained from WSJT-X's *Save All* output (`save/YYMMDD_HHMMSS.wav`) with the matching `ALL.TXT` decode lines, keyed by timestamp. Where a live capture is unavailable, MIT-licensed `kgoba/ft8_lib` `test/wav/` recordings MAY be used, with attribution recorded in the dependency/licence inventory.

#### Scenario: Captured recording is paired with its answer key

- **WHEN** a WSJT-X *Save All* recording `YYMMDD_HHMMSS.wav` is added to the corpus
- **THEN** the corresponding WSJT-X `ALL.TXT` decode lines for timestamp `YYMMDD_HHMMSS` SHALL be recorded as that recording's expected-message answer key

#### Scenario: Fallback recordings carry attribution

- **WHEN** a `kgoba/ft8_lib` recording is used as a fixture
- **THEN** its MIT licence and attribution SHALL be present in the dependency/licence inventory so the licence gate remains green

### Requirement: WAV-to-PCM reader

The test infrastructure SHALL provide a reader that converts a 12 kHz mono int16 WAV file into the normalised `float[]` PCM buffer accepted by `Ft8Decoder.DecodeAsync`. The reader SHALL reproduce the sample values of the recording without resampling.

#### Scenario: WAV decodes to the decoder's PCM format

- **WHEN** a 12 kHz mono int16 WAV file is read
- **THEN** the reader SHALL return a `float[]` whose length equals the WAV's sample count and whose values are the int16 samples normalised to `[-1, 1]`

#### Scenario: Unsupported format is rejected

- **WHEN** a WAV file is not 12 kHz mono PCM
- **THEN** the reader SHALL fail with a clear error rather than silently misinterpreting the samples

### Requirement: Offline replay harness reports recovery rate

The project SHALL provide a harness that decodes each corpus recording through `Ft8Decoder.DecodeAsync` and compares the results against that recording's answer key. For each recording and in aggregate the harness SHALL report: real signals matched (present in both), WSJT-X signals missed (in the answer key but not decoded), and false positives (decoded but not in the answer key).

#### Scenario: Harness measures recovery against WSJT-X

- **WHEN** the harness runs over the corpus
- **THEN** it SHALL output, per recording and in aggregate, the count of matched, missed, and false-positive messages

#### Scenario: Recovery rate is the decision-gate metric

- **WHEN** the aggregate recovery rate is computed
- **THEN** it SHALL be the metric used to choose the downstream decoder strategy (zero recovery → port a proven decoder; partial recovery → patch against this oracle; parity → no decoder rework)

### Requirement: Real-signal fixture integration test

The test suite SHALL include an integration test that decodes 2–3 committed real-signal WAV fixtures (embedded in the test assembly) and asserts that a defined subset of unambiguous, strong real FT8 messages from the answer key is decoded. This test SHALL be the authoritative integration oracle for decoder correctness.

#### Scenario: Known real signals decode

- **WHEN** the integration test decodes a committed real-signal fixture
- **THEN** the decoded messages SHALL contain every message in that fixture's asserted answer-key subset

#### Scenario: Circular encoder test is not the integration oracle

- **WHEN** decoder correctness is assessed
- **THEN** the `TestFt8Encoder`-based round-trip test SHALL be treated as an internal-consistency check only and SHALL NOT be accepted as evidence that the decoder decodes real signals
