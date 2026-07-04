## MODIFIED Requirements

### Requirement: TxReport — transmitting the signal report

When the service has selected a partner (via `First` auto-selection or `None` operator click), it SHALL:

1. Set `_partner = selectedCallsign`.
2. Compose: `{partner} {callsign} +00` (fixed report; TX-D04 deferred).
3. Encode; synthesise at `_lastTxFreqHz`; transmit.
4. Advance to `WaitRr73`.
5. Set `_skipNextRetry = true` (A-01).
6. Arm H6 AP decode constraints for `(callsign, partner)`.
7. Reset watchdog.

#### Scenario: Signal report message is correctly formatted

- **WHEN** `callsign = "PD2FZ"`, `partner = "Q1ABC"`, and the service transmits from
  `TxReport`
- **THEN** the transmitted message SHALL be `"Q1ABC PD2FZ +00"`

#### Scenario: AP decode constraints arm successfully for a nonstandard partner callsign

- **WHEN** the service transmits from `TxReport` with `partner` a nonstandard/compound
  callsign (e.g. `"PJ4/K1ABC"`) and `callsign` a standard basecall
- **THEN** step 6 SHALL arm H6 AP decode constraints using the extended callsign packer's
  nonstandard-callsign encoding for `partner`, rather than disabling AP decode-assist for the
  QSO (previously: either callsign failing to pack under the standard-basecall-only packer
  disabled AP entirely)
