## ADDED Requirements

### Requirement: H6 AP decode constraint arming

The service SHALL arm H6 directed AP decode constraints for the active `(callsign, partner)` pair after transmitting the answer (`"{partner} {callsign} {grid}"`) and advancing from `TxAnswer` to `WaitReport`, using the callsign packer's full encoding support (standard basecalls, special tokens, and nonstandard/compound callsigns via `ihashcall`). AP decode-assist SHALL be disabled for the QSO only when the packer genuinely cannot encode one of the two callsigns (an unsupported form — see `ap-assist-callsign-packing`'s "Unsupported forms" requirement), not merely because either callsign is nonstandard.

#### Scenario: AP constraints arm after transmitting the answer

- **WHEN** the service transmits the answer message and advances to `WaitReport`
- **THEN** it SHALL arm H6 AP decode constraints for `(tx.Callsign, partner)` before notifying
  the state change

#### Scenario: AP decode constraints arm successfully for a nonstandard partner callsign

- **WHEN** `partner` is a nonstandard/compound callsign (e.g. `"PJ4/K1ABC"`) and `tx.Callsign`
  is a standard basecall
- **THEN** AP decode constraints SHALL arm using the extended packer's nonstandard-callsign
  encoding for `partner`, rather than disabling AP decode-assist for the QSO

#### Scenario: AP decode constraints disabled when a callsign is genuinely unpackable

- **WHEN** either `tx.Callsign` or `partner` is a form the callsign packer does not support
  (e.g. a directed CQ with a non-numeric suffix, or malformed input)
- **THEN** AP decode-assist SHALL be disabled for the QSO, and a warning SHALL be logged naming
  which callsign failed to pack
