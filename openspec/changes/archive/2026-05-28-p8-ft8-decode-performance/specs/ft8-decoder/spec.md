## ADDED Requirements

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
