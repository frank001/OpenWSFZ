## ADDED Requirements

### Requirement: Observable 12-bit hash-path unresolved-lookup sizing, by code

The native decode pipeline SHALL expose, read-only, a complete per-code breakdown of 12-bit
hash-path lookups that found **no** matching table entry — one count per distinct 12-bit code,
across the full 4,096-value code space — so that L3's own sizing question (whether this project's
code is a disproportionate source of unresolved 12-bit hash lookups) can be measured at all. This
is the complement of the existing "Observable 12-bit hash-path per-code cluster identity"
Requirement, which counts only lookups that **resolved and were displayed**; the two populations
are disjoint by construction (a lookup either finds a matching entry or it does not, never both),
and their per-code tables are never combined or double-counted. A code value that cannot be
represented in 12 bits SHALL be masked into range before being counted, sharing the existing
code-width-violation counter defined by that Requirement rather than duplicating it — a violation
in either population is the same underlying wiring defect and is exposed as one signal.

This Requirement adds no per-lookup record of any kind, and reads a message's own field content
for nothing beyond the 12-bit code already extracted by the existing lookup path — the per-code
table is the complete measurement.

🔴 **This export's population includes padding lookups, and that is a known, disclosed property,
not a defect to fix here.** `ftx_message_encode_nonstd` hard-wires the 12-bit field to zero for
every CQ-shaped (`icq != 0`) Type-4 message, and the decoder looks that padding field up
unconditionally before discarding it — those lookups reach the same code path as any real
unresolved hash reference and, when unresolved (the common case for padding), land at code 0 in
this table. Because the table is per-code, this is isolated for free: a consumer that wants the
padding-free sizing population reads `total(counts) − counts[0]`, never a raw total. This
Requirement does not mandate a second, padding-free counter — none is needed for that isolation to
be possible.

#### Scenario: The per-code table counts only lookups that found no matching entry

- **WHEN** a 12-bit hash-path lookup is performed
- **THEN** it SHALL increment an entry in this table if and only if the lookup found no matching
  table entry at all — a lookup that resolved (whether or not the match was later suppressed as
  ambiguous) SHALL NOT increment any entry here

#### Scenario: A code-width violation is counted, not silently masked away

- **WHEN** an unresolved 12-bit hash-path lookup's code value falls outside the representable
  12-bit range
- **THEN** the shared code-width-violation count SHALL increment
- **AND** the lookup SHALL still be recorded, masked into range, in this Requirement's per-code
  table

#### Scenario: Padding lookups land at code 0, and code 0 is not excluded from the table

- **WHEN** an unresolved 12-bit hash-path lookup originates from a hard-wired zero padding field
  (a CQ-shaped Type-4 message's own encoding, not a genuine hash reference)
- **THEN** it SHALL be counted at `counts[0]` exactly as any other unresolved code-0 lookup would
  be — this Requirement does not attempt to distinguish padding from a genuine unresolved hash
  whose real value happens to be 0, and does not need to: isolating the padding-contaminated cell
  is a consumer-side reading convention (`total − counts[0]`), not a measurement this Requirement
  must perform itself

#### Scenario: The per-code table is observable from outside the managed C# surface

- **WHEN** the per-code table is read
- **THEN** it SHALL be obtainable via the native library's exported interface (e.g. by a
  measurement harness driving the library directly), without requiring a managed
  `IFt8NativeInterop`/`Ft8LibInterop` binding to exist for it — this Requirement does not mandate a
  managed binding, since no managed consumer of a 4,096-row table exists
