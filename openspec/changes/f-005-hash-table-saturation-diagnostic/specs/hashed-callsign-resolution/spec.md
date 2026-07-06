## ADDED Requirements

### Requirement: Observable hash table saturation state

The session-scoped callsign hash table's reject-when-full count SHALL be readable from the
managed layer without requiring a debugger or native instrumentation. This count reflects the
number of times a new-callsign registration attempt was discarded because the table was already
at its 256-entry capacity, so that table saturation during a live or completed session can be
confirmed or ruled out directly instead of only being inferable indirectly. A registration
attempt arises both from a Type 4 nonstandard-callsign announcement and from a standard Type 1/2
message's `call_to`/`call_de` field — any decoded message field that causes the native decode
pipeline to attempt to record a callsign's hash counts, not only Type 4 messages.

#### Scenario: Reject count is zero when the table has never been full

- **WHEN** a session has run and no callsign registration attempt has ever been discarded due to
  the table being at capacity
- **THEN** the managed-layer reject-count read SHALL return `0`

#### Scenario: Reject count reflects discarded registration attempts once the table is full

- **WHEN** the table is already at its 256-entry capacity
- **AND** one or more subsequently decoded messages (a Type 4 announcement, or a standard
  message's `call_to`/`call_de` field) attempt to register a callsign not already present in the
  table
- **THEN** each such discarded registration attempt SHALL increment the count returned by the
  managed-layer reject-count read
- **AND** this SHALL match the existing "table at capacity rejects a new callsign without side
  effects" behaviour (no change to which callsigns are stored or resolvable)

#### Scenario: Reading the count has no side effects

- **WHEN** the managed layer reads the reject count at any point during or after a session
- **THEN** the read SHALL NOT reset the count, alter the hash table's contents, or affect
  subsequent hash resolution behaviour in any way

#### Scenario: Session-end visibility

- **WHEN** the daemon completes a graceful shutdown
- **THEN** the session's final reject-count value SHALL be written to the daemon log, so it is
  available for review without requiring a live diagnostic query during the session
