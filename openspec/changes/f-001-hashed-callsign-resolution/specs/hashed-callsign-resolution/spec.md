## ADDED Requirements

### Requirement: Cross-cycle callsign hash resolution
The native decode pipeline SHALL retain callsign-hash mappings learned from decoded FT8 Type 4
(nonstandard call) messages across multiple `ft8_decode_all` invocations within the same process
lifetime, so that a 22-bit callsign hash embedded in a Type 1/2/3 message decoded in a later cycle
SHALL resolve to the full callsign text if that callsign was announced via a Type 4 message in any
earlier cycle of the same session.

#### Scenario: Hash resolves after being announced in an earlier cycle
- **WHEN** a Type 4 message announcing a nonstandard callsign (e.g. `PJ4/K1ABC`) is successfully
  decoded in cycle *N*
- **AND** a Type 1/2/3 message referencing that same callsign's 22-bit hash is decoded in any
  later cycle *N+k* (*k* ≥ 1) within the same running process
- **THEN** the decoded text for the cycle *N+k* message SHALL contain the full callsign text
  (e.g. `PJ4/K1ABC`), not an unresolved hash placeholder

#### Scenario: Never-announced hash remains unresolved
- **WHEN** a Type 1/2/3 message references a 22-bit callsign hash that has not been produced by
  any previously decoded Type 4 message in the current process session
- **THEN** the decoded text SHALL use the existing unresolved-hash placeholder convention (e.g.
  `<...>`), matching current WSJT-X-compatible behaviour — no change from today's output for this
  case

#### Scenario: Same-cycle resolution continues to work
- **WHEN** a Type 4 message and a Type 1/2/3 message referencing its hash are both decoded within
  the same `ft8_decode_all` call (the previously-supported case)
- **THEN** resolution SHALL continue to succeed exactly as it does today

### Requirement: Bounded hash table growth
The session-scoped callsign hash table SHALL have a fixed maximum capacity. Once at capacity, the
table SHALL reject additional distinct callsigns rather than growing unbounded or corrupting
existing entries.

#### Scenario: Table at capacity rejects a new callsign without side effects
- **WHEN** the hash table already holds its maximum number of distinct callsign entries
- **AND** a Type 4 message announces a callsign not already present in the table
- **THEN** the new callsign SHALL be discarded (not stored)
- **AND** all previously stored entries SHALL remain unchanged and independently resolvable

### Requirement: Exception-path safety
A caught access violation (or other SEH-contained fault) during `ft8_decode_all` SHALL NOT corrupt
the callsign hash table's internal state in a way that causes a subsequent lookup to return
incorrect callsign text or to crash, and SHALL NOT leave a dangling table pointer available to a
later decode cycle.

#### Scenario: Access violation during a decode cycle does not destabilise later cycles
- **WHEN** `ft8_decode_all` catches an access violation via its existing SEH wrapper and returns
  its error code
- **THEN** the thread-local pointer used by the hash-lookup/save callbacks SHALL be cleared before
  the call returns
- **AND** a subsequent, unrelated `ft8_decode_all` call SHALL execute normally, with previously
  learned hash mappings (from cycles before the fault) still resolvable exactly as if the fault
  had not occurred
