## MODIFIED Requirements

### Requirement: TxReport — transmitting the signal report

When the service has selected a partner (via `First` auto-selection or `None` operator click), it SHALL:

1. Set `_partner = selectedCallsign`.
2. Compose: `{partner} {callsign} {report}`, where `{report}` is the real measured `Snr` of the
   triggering decode (the matched `DecodeResult` for `First` mode; the re-derived responder decode
   for `None` mode), formatted as a two-digit signed FT8 report clamped to `±30` (e.g. `+07`,
   `-13`, `+00`) — never a fixed placeholder.
3. Persist `{report}` as `_rstSent` for reuse by the `WaitRr73` retry retransmission and the ADIF
   `RstSent` field, so a subsequent retry resends the exact value chosen here rather than a freshly
   (and potentially unavailable) recomputed one.
4. Encode; synthesise at `_lastTxFreqHz`; transmit.
5. Advance to `WaitRr73`.
6. Set `_skipNextRetry = true` (A-01).
7. Arm H6 AP decode constraints for `(callsign, partner)`.
8. Reset watchdog.

#### Scenario: Signal report message reflects the real measured SNR

- **WHEN** `callsign = "PD2FZ"`, `partner = "Q1ABC"`, the triggering decode's `Snr = -7`, and the
  service transmits from `TxReport`
- **THEN** the transmitted message SHALL be `"Q1ABC PD2FZ -07"`, not `"Q1ABC PD2FZ +00"`

#### Scenario: Signal report is clamped to the FT8 ±30 range

- **WHEN** the triggering decode's `Snr` is `+42` (outside the standard FT8 report range)
- **THEN** the transmitted report SHALL be clamped to `"+30"`

#### Scenario: WaitRr73 retry resends the same report value, not a recomputed one

- **WHEN** the service transmitted `TxReport` with a report of `"-07"` and then times out waiting
  for a roger report, triggering `RetryOrAbortAsync`'s `WaitRr73` retry branch
- **THEN** the retransmitted message SHALL again contain `"-07"` — the persisted `_rstSent` value —
  regardless of whether a fresh decode of the partner is available in the retry cycle

#### Scenario: ADIF RstSent reflects the real transmitted report

- **WHEN** a QSO completes after a `TxReport` transmission whose report was `"-07"`
- **THEN** the written `QsoRecord.RstSent` SHALL be `"-07"`, not the fixed `"+00"` placeholder

#### Scenario: AP decode constraints arm successfully for a nonstandard partner callsign

- **WHEN** the service transmits from `TxReport` with `partner` a nonstandard/compound
  callsign (e.g. `"PJ4/K1ABC"`) and `callsign` a standard basecall
- **THEN** step 7 SHALL arm H6 AP decode constraints using the extended callsign packer's
  nonstandard-callsign encoding for `partner`, rather than disabling AP decode-assist for the
  QSO (previously: either callsign failing to pack under the standard-basecall-only packer
  disabled AP entirely)
