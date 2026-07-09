## ADDED Requirements

### Requirement: Worked-before index built from `ADIF.log` at startup

The daemon SHALL build an in-memory index of every distinct callsign that appears in a `CALL`
field anywhere in `ADIF.log`, read from the same path `AdifLogWriter` resolves and writes to
(`adif-log` capability). The index SHALL be built once at daemon startup, before decoding begins
serving worked-before results.

For each distinct logged callsign, the daemon SHALL additionally resolve its DXCC entity and
continent via `ICallsignRegionStore.TryGetRegion` (`region-lookup` capability) and record the
resolved entity/continent for country/region matching, subject to the Unknown/synthetic exclusion
below.

#### Scenario: Index populated from an existing ADIF.log at startup

- **WHEN** the daemon starts and `ADIF.log` exists with one or more valid `<call:N>VALUE...<eor>`
  records
- **THEN** the worked-before index SHALL contain every distinct callsign found in those records,
  available before the first decode cycle completes

#### Scenario: Missing ADIF.log degrades to an empty index, not an error

- **WHEN** the daemon starts and `ADIF.log` does not exist at the resolved path
- **THEN** the daemon SHALL start normally with an empty worked-before index (all decodes resolve
  to not-worked-before on every column) and SHALL NOT log this as an error condition

#### Scenario: Malformed or unparseable lines are skipped, not fatal

- **WHEN** `ADIF.log` contains one or more lines that do not yield a parseable `CALL` token (e.g.
  truncated, non-ADIF content)
- **THEN** the daemon SHALL skip each such line, log a Warning identifying the condition, and
  continue loading the remainder of the file into the index

---

### Requirement: Index updated live when a new QSO is logged

When `AdifLogWriter.AppendQsoAsync` successfully writes a new ADIF record, the daemon SHALL
register that record's partner callsign (and its resolved DXCC entity/continent, subject to the
Unknown/synthetic exclusion below) into the same in-memory worked-before index used to serve
decode results, without requiring a daemon restart or a re-read of `ADIF.log`.

#### Scenario: A station logged this session is confirmed on its next decode

- **WHEN** a QSO with callsign `Q1XYZ` is successfully logged to `ADIF.log` during the current
  session
- **THEN** the very next decode of a message whose primary callsign token is `Q1XYZ` SHALL
  resolve `workedBefore.call` as `true`

#### Scenario: A failed ADIF write does not register the callsign

- **WHEN** `AdifLogWriter.AppendQsoAsync` fails to write (e.g. `IOException`,
  `UnauthorizedAccessException`, per the `adif-log` capability's existing failure handling)
- **THEN** the worked-before index SHALL NOT register that callsign, consistent with no record
  actually having been persisted

---

### Requirement: Partner (callsign) matching includes portable-suffix variants

The Partner (callsign) worked-before check SHALL treat two callsign tokens as the same station
if they are exactly equal, or if one is a portable-suffixed variant of the other's base callsign
(a `"/"`-delimited suffix appended to the base, e.g. `PD2FZ/P` matching base `PD2FZ`) — the same
matching semantics as the existing frontend `tokenMatchesCallsign` helper used for CQ
click-to-answer.

#### Scenario: Exact callsign match

- **WHEN** a decode's primary callsign token is `Q1TST` and `Q1TST` has been logged before
- **THEN** `workedBefore.call` SHALL be `true`

#### Scenario: Portable-suffixed decode matches a plain historical log entry

- **WHEN** a decode's primary callsign token is `Q1TST/P` and `Q1TST` (no suffix) has been logged
  before
- **THEN** `workedBefore.call` SHALL be `true`

#### Scenario: Plain decode matches a portable-suffixed historical log entry

- **WHEN** a decode's primary callsign token is `Q1TST` and `Q1TST/P` has been logged before
- **THEN** `workedBefore.call` SHALL be `true`

#### Scenario: Unrelated callsign does not match

- **WHEN** a decode's primary callsign token is `Q2ABC` and no entry equal to or a portable
  variant of `Q2ABC` has ever been logged
- **THEN** `workedBefore.call` SHALL be `false`

---

### Requirement: Country and Region matching, with Unknown and synthetic entries excluded

The Country worked-before check SHALL compare the DXCC entity resolved for the decode's primary
callsign token against the set of DXCC entities resolved for historically-logged callsigns; the
Region worked-before check SHALL compare continents the same way. A resolution that fails (lookup
miss, "Unknown") or resolves to the synthetic Q-series entry (`Synthetic == true`, NFR-021) SHALL
be excluded from both sides of the comparison: it SHALL NOT be inserted into the worked-entity/
worked-continent sets, and a decode whose own resolution is Unknown or synthetic SHALL always
resolve `workedBefore.country` and `workedBefore.region` to `false`, regardless of index content.

#### Scenario: Same DXCC entity previously worked

- **WHEN** a decode's primary callsign token resolves to entity `"Germany"`, and some
  historically-logged callsign also resolves to entity `"Germany"`
- **THEN** `workedBefore.country` SHALL be `true`

#### Scenario: Same continent previously worked, different entity

- **WHEN** a decode's primary callsign token resolves to continent `"EU"`, entity `"Monaco"`, and
  no historically-logged callsign resolves to entity `"Monaco"`, but at least one resolves to
  continent `"EU"` (e.g. entity `"Germany"`)
- **THEN** `workedBefore.region` SHALL be `true` and `workedBefore.country` SHALL be `false`

#### Scenario: Two unresolved callsigns never co-match

- **WHEN** a decode's primary callsign token fails to resolve (`"Unknown"`), even if one or more
  historically-logged callsigns also failed to resolve
- **THEN** `workedBefore.country` and `workedBefore.region` SHALL both be `false`

#### Scenario: Synthetic Q-prefix decode never matches, and never contributes to a match

- **WHEN** a decode's primary callsign token resolves to the synthetic region (NFR-021), or a
  historically-logged callsign resolves to the synthetic region
- **THEN** that decode's `workedBefore.country`/`workedBefore.region` SHALL be `false`, and no
  synthetic-resolved historical callsign SHALL cause a real decode's Country/Region check to
  become `true`

---

### Requirement: `WorkedBefore` field attached to the decode-result payload

For each decoded message, the daemon SHALL resolve worked-before state (`call`, `country`,
`region` — three independent booleans) for the message's primary callsign-position token and
attach it to the decode-result payload delivered over the existing WebSocket decode channel,
alongside the existing `region` field, so the frontend does not need a separate lookup
round-trip. Resolution failure of any kind SHALL degrade to all three booleans `false` and SHALL
NOT withhold the decode from `ALL.TXT` or the UI, matching the `region-lookup` capability's
existing advisory-only guarantee.

#### Scenario: Decode-result payload includes independent worked-before booleans

- **WHEN** a message is decoded whose primary callsign token has been worked before (callsign)
  but not before in that country
- **THEN** the decode-result payload's `workedBefore` field SHALL report `call: true`,
  `country: false` (and `region` per its own resolution)

#### Scenario: Worked-before resolution failure does not affect the decode pipeline

- **WHEN** worked-before resolution throws or the index is unavailable for any reason
- **THEN** the daemon SHALL log the condition, resolve `workedBefore` as `{ call: false,
  country: false, region: false }` for the affected decode, and continue decoding and displaying
  messages normally
