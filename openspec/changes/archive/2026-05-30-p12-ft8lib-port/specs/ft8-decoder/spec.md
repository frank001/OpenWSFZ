## REMOVED Requirements

### Requirement: Costas candidate count is bounded relative to signal density
**Reason**: Implementation-specific constraint on the homegrown Costas synchroniser, which is retired in p12. `ft8_lib` manages its own candidate detection internally; the cap of 2 candidates per sweep pair no longer applies.
**Migration**: No caller-visible behaviour changes. Decode correctness is verified end-to-end by `RealSignalFixtureTests` (G6 gate).

### Requirement: Goertzel extraction coefficients are computed once per call
**Reason**: Implementation-specific constraint on the homegrown `SymbolExtractor`, which is retired in p12. `ft8_lib` uses its own spectrogram implementation; the Goertzel coefficient reuse constraint no longer applies.
**Migration**: No caller-visible behaviour changes.

---

## MODIFIED Requirements

### Requirement: FT8 decode cycle completes within the 15-second budget

The FT8 decoder SHALL complete a full decode cycle — including all time-domain analysis, sync candidate detection, LDPC decode, iterative signal subtraction, and message unpacking — within **13 seconds** of wall-clock time on a single modern CPU core, leaving at least 2 seconds headroom before the next cycle window is delivered by the framer.

#### Scenario: Decode completes within budget on a multi-signal fixture

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a real off-air PCM buffer containing multiple simultaneous FT8 signals
- **THEN** the method SHALL return within 13 000 ms on a development machine and within 30 000 ms on a CI runner (allowing for runner variance)

#### Scenario: Decode does not stall the cycle pump on a live band

- **WHEN** a continuous stream of 15-second PCM windows is delivered by `CycleFramer` on a band with up to 30 simultaneous FT8 transmissions
- **THEN** the decode pump SHALL complete each window before the second subsequent window arrives (i.e., at most one window queued at any time during steady-state operation)

---

## ADDED Requirements

### Requirement: Real off-air signal recovery (G6 gate)

The FT8 decoder SHALL correctly decode real off-air FT8 transmissions captured from the 40 m band. Given a 15-second PCM window from the committed WAV fixture corpus, the decoder SHALL recover the signals identified by WSJT-X for the same recording.

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a PCM buffer from the committed fixture corpus (`260528_235745`, `260529_000030`, or `260529_000200`)
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file

#### Scenario: Decoder produces no decode for a silent buffer

- **WHEN** `Ft8Decoder.DecodeAsync` is called with 180 000 samples of silence (all zeros)
- **THEN** the method SHALL return an empty list without throwing
