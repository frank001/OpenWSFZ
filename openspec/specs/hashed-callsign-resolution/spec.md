# hashed-callsign-resolution Specification

## Purpose

Specifies the session-scoped callsign hash table in the native FT8 decode pipeline
(`ft8_shim.c`) that lets a nonstandard/compound callsign (e.g. `PJ4/K1ABC`, special-event calls)
announced via a Type 4 message in one decode cycle be resolved by a later Type 1/2/3 message that
references it via a 22-bit hash, across multiple `ft8_decode_all` invocations within the same
process lifetime. Previously, `ft8_decode_all` allocated a fresh, empty hash table on every call
and destroyed it before returning, so a Type 4 message's callsign was immediately forgotten and
could never be resolved by a hash reference decoded in a later cycle — operators saw only the
WSJT-X-style `<...>` placeholder for stations using a compound or special-event callsign. The
table's growth is bounded to a fixed capacity, and a caught access violation (SEH) during
`ft8_decode_all` does not corrupt the table or leave a dangling pointer available to a later
decode cycle.

## Requirements

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

---

### Requirement: Bounded hash table growth

The session-scoped callsign hash table SHALL have a fixed maximum capacity. Once at capacity, the
table SHALL reject additional distinct callsigns rather than growing unbounded or corrupting
existing entries.

#### Scenario: Table at capacity rejects a new callsign without side effects

- **WHEN** the hash table already holds its maximum number of distinct callsign entries
- **AND** a Type 4 message announces a callsign not already present in the table
- **THEN** the new callsign SHALL be discarded (not stored)
- **AND** all previously stored entries SHALL remain unchanged and independently resolvable

---

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

---

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

---

### Requirement: Observable 12-bit hash-path unique-match sizing (Phase 1 — shipped 2026-08-30, shim `20260047`)

The native decode pipeline SHALL expose, read-only and without altering resolution behaviour, three
process-lifetime counts: how many EMITTED decodes displayed a callsign resolved via the 12-bit hash
path; of those, how many resolved against a probe chain holding two or more matching entries
(ambiguous); and of those, how many had their most-recently-*announced* matching entry differ from
the first (displayed) match (divergent). "Emitted" means the message is unconditionally headed for
the decode results returned to the caller — a lookup performed during an attempt that is later
discarded or deduplicated SHALL NOT be counted. Ambiguity and divergence SHALL be determined by
replaying the same probe sequence the existing lookup uses, in a function that never calls, and is
never called by, the existing lookup function — this measurement SHALL NOT alter what any lookup
returns or the callsign text it writes, on any input. Divergence SHALL be judged against
*announcement* recency, not lookup recency: recency SHALL be refreshed only when a callsign is
announced (a genuinely new table insert, or a repeat announcement of an already-known callsign),
never when a callsign is merely looked up.

#### Scenario: A single unambiguous match is not counted as ambiguous or divergent

- **WHEN** an emitted decode's 12-bit lookup resolves against a probe chain holding exactly one
  matching entry
- **THEN** the displaying count SHALL increment
- **AND** the ambiguous and divergent counts SHALL NOT increment for that decode

#### Scenario: An ambiguous match whose most recent announcement is also the first agrees, not diverges

- **WHEN** an emitted decode's 12-bit lookup resolves against a probe chain holding two or more
  matching entries, and the most-recently-announced of them is the same entry as the first
  (displayed) match
- **THEN** the displaying and ambiguous counts SHALL both increment
- **AND** the divergent count SHALL NOT increment for that decode

#### Scenario: An ambiguous match whose most recent announcement differs from the displayed one diverges

- **WHEN** an emitted decode's 12-bit lookup resolves against a probe chain holding two or more
  matching entries, and the most-recently-announced of them differs from the first (displayed)
  match
- **THEN** the displaying, ambiguous, and divergent counts SHALL all increment

#### Scenario: A lookup performed during a discarded or deduplicated attempt is not counted

- **WHEN** a candidate's 12-bit lookup is performed during `ftx_message_decode`, but the resulting
  message is subsequently discarded (fails text decode) or deduplicated before reaching the caller's
  results
- **THEN** none of the three counts SHALL increment for that attempt

#### Scenario: The three counts are observable from the managed layer without a debugger

- **WHEN** the managed layer reads any of the three counts, at any point during or after a session
- **THEN** the read SHALL return the current process-lifetime cumulative value
- **AND** the read SHALL NOT reset any count, alter the hash table's contents, or affect subsequent
  resolution behaviour in any way

#### Scenario: Per-cycle visibility

- **WHEN** a decode cycle completes
- **THEN** the daemon log SHALL record the three counts' current cumulative values for that cycle,
  so the measurement is reconstructible from an ordinary log without a live diagnostic query

---

### Requirement: Observable 12-bit hash-path per-code cluster identity (Phase 2 — Amendment 2, shipped 2026-08-30, shim `20260048`)

The native decode pipeline SHALL expose, read-only, a complete per-code breakdown of the three
counts from the preceding Requirement — one displaying/ambiguous/divergent triple per distinct
12-bit code, across the full 4,096-value code space — so that a statistical interval over the
unique-match sizing measurement can resample distinct codes (clusters) rather than individual
lookups, since one ambiguous code may generate many lookups and a lookup-level interval would
understate the true uncertainty. A code value that cannot be represented in 12 bits SHALL be
masked into range before being counted, AND the number of times this masking was required SHALL
itself be counted and exposed, separately from the per-code table, so that a code-width violation
is visible rather than silently absorbed into the wrong bucket. This Requirement adds no per-lookup
record of any kind — the per-code table is the complete measurement; a design that additionally
produced per-lookup rows would be out of scope for the statistic this Requirement exists to support.

#### Scenario: The per-code table sums to the same totals as the three cumulative counts

- **WHEN** the per-code displaying, ambiguous, and divergent tables are each summed across every
  code in the 4,096-value space, at any point in a session
- **THEN** each sum SHALL equal the corresponding cumulative count from the preceding Requirement,
  provided no code-width violation has occurred (see the next scenario for the case where one has)

#### Scenario: A code-width violation is counted, not silently masked away

- **WHEN** a 12-bit hash-path lookup's code value falls outside the representable 12-bit range
- **THEN** the violation count SHALL increment
- **AND** the lookup SHALL still be recorded, masked into range, in the per-code table — the
  violation count exists precisely so this masking is never mistaken for a violation-free run by a
  reconciliation check on the per-code table's own totals alone

#### Scenario: A code that never displays is absent from the participating population, not a zero entry

- **WHEN** the per-code table is read for the purpose of building a resample population of
  participating codes
- **THEN** a code whose displaying count is zero SHALL be excluded from that population — it SHALL
  NOT be treated as a code that participated zero times, since including it would change the
  population's size for a code that was never actually observed

#### Scenario: The per-code table is observable from outside the managed C# surface

- **WHEN** the per-code table is read
- **THEN** it SHALL be obtainable via the native library's exported interface (e.g. by a
  measurement harness driving the library directly), without requiring a managed
  `IFt8NativeInterop`/`Ft8LibInterop` binding to exist for it — this Requirement does not mandate a
  managed binding, since no managed consumer of a 4,096-row table exists
