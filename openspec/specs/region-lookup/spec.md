# region-lookup Specification

## Purpose

Specifies the advisory continent/country region lookup resolved for each decoded message's
primary callsign-position token, used for GUI display only. Region data is loaded from
`callsign-regions.json` via `ICallsignRegionStore`; a lookup miss, malformed configuration file,
or any error in region resolution degrades gracefully to an `"Unknown"` region label and never
feeds back into the `callsign-structure-validation` accept/reject decision. A dedicated entry
maps the project's synthetic Q-prefix callsign convention (NFR-021) to a distinct synthetic
region so R&R-study traffic is never misattributed to a real entity nor conflated with genuinely
unrecognised prefixes.

## Requirements
### Requirement: Region lookup is advisory and never affects decode acceptance

The system SHALL resolve a callsign-position token's continent and country/administration name
(its "region") from `callsign-regions.json` for display purposes only. A lookup miss, a malformed
configuration file, or any error in region resolution SHALL NOT cause a decode to be withheld
from `ALL.TXT` or the UI, and SHALL NOT feed back into the `callsign-structure-validation`
accept/reject decision.

#### Scenario: Decode with no matching region entry is still surfaced

- **WHEN** a decoded message's callsign token's prefix has no matching entry in
  `callsign-regions.json`
- **THEN** the message SHALL still reach `ALL.TXT` and the UI, with its region resolved as
  `"Unknown"`

#### Scenario: Region resolution failure does not affect the decode pipeline

- **WHEN** `callsign-regions.json` is missing, malformed, or the region lookup throws
- **THEN** the daemon SHALL log the condition, treat the region as `"Unknown"` for affected
  decodes, and continue decoding and displaying messages normally

---

### Requirement: Region resolved from `callsign-regions.json` and attached to the decode payload

For each decoded message, the daemon SHALL resolve the region of the message's primary
callsign-position token (the token in the caller-identification position) using
`ICallsignRegionStore`, and SHALL attach the result to the decode-result payload delivered over
the existing WebSocket decode channel, so the frontend does not need a separate lookup
round-trip.

#### Scenario: Recognised prefix resolves continent and entity name

- **WHEN** a decoded message's callsign token's prefix matches an entry in
  `callsign-regions.json` (e.g. an entry mapping the `3A` prefix block to continent `EU`, entity
  `Monaco`)
- **THEN** the decode-result payload SHALL include a `region` field populated with that
  continent and entity information

#### Scenario: Unrecognised prefix resolves to Unknown

- **WHEN** a decoded message's callsign token's prefix does not match any entry in
  `callsign-regions.json`
- **THEN** the decode-result payload's `region` field SHALL be `"Unknown"`

---

### Requirement: Synthetic Q-prefix callsigns resolve to a distinct synthetic region

`callsign-regions.json` SHALL carry a dedicated entry mapping the project's synthetic-callsign
convention (NFR-021, the `Q`-prefix series) to a region distinct from both any real
ITU-allocated entity and the generic `"Unknown"` fallback, so R&R-study synthetic traffic is
never misattributed to a real country nor conflated with genuinely unrecognised prefixes.

#### Scenario: Synthetic Q-prefix callsign resolves to the synthetic region label

- **WHEN** a decoded message's callsign token's prefix falls within the `Q`-series synthetic
  carve-out (e.g. a fictional `Q1ABC`)
- **THEN** the decode-result payload's `region` field SHALL be `"Synthetic (R&R Study)"`, and
  SHALL NOT be `"Unknown"` or any real entity/continent value

#### Scenario: Synthetic region is distinguishable from a real region in the payload

- **WHEN** the decode-result payload's `region` field is resolved for a synthetic-prefix callsign
- **THEN** the payload SHALL indicate the synthetic status (e.g. a boolean flag or a value the
  frontend can distinguish from a real continent/entity pair) so the frontend can render it
  without a continent prefix per its own rendering rule

---

### Requirement: Callsign region configuration is loaded from `callsign-regions.json`

The prefix→region table SHALL be loaded from `callsign-regions.json` at startup via
`ICallsignRegionStore`, following the same load/first-run/override conventions as
`ICallsignGrammarStore` and the existing `IFrequencyStore`.

#### Scenario: Missing configuration file creates a default file with seed data

- **WHEN** the daemon starts and `callsign-regions.json` does not exist at the resolved path
- **THEN** the daemon SHALL create the file with its seed region data (including the mandatory
  synthetic `Q`-series entry) and proceed without error

#### Scenario: Malformed configuration file falls back to Unknown-only behaviour with a warning

- **WHEN** the daemon starts and `callsign-regions.json` exists but fails to deserialise
- **THEN** the daemon SHALL log a Warning naming the parse failure, treat all region lookups as
  `"Unknown"` until corrected, and start normally

---

### Requirement: Region table can be replaced at runtime without a restart

`ICallsignRegionStore` SHALL support replacing its entire in-memory region table and persisting the
replacement to `callsign-regions.json` atomically, without requiring the daemon to restart, and
without affecting any in-flight or subsequent region lookup's correctness (a lookup during the
replacement SHALL observe either the complete old table or the complete new table, never a partial
one).

#### Scenario: Runtime replacement updates both memory and disk

- **WHEN** a caller replaces the region table via the store's runtime-replacement operation with a
  new, valid list of entries
- **THEN** `callsign-regions.json` SHALL be overwritten atomically (write-to-temp-then-rename) with
  the new list, and subsequent calls to resolve a region SHALL use the new list

#### Scenario: A failed write during replacement leaves the previous table active

- **WHEN** a caller replaces the region table via the store's runtime-replacement operation and the
  underlying file write fails
- **THEN** the in-memory region table SHALL remain the previous list, and `callsign-regions.json`
  on disk SHALL remain unchanged
