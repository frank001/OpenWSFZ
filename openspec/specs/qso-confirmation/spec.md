# qso-confirmation Specification

## Purpose

Specifies the "worked before" advisory index: an in-memory record of every distinct callsign
(and its resolved DXCC entity/continent/CQ-zone/ITU-zone, plus the band(s) it was worked on)
ever logged to `ADIF.log` (`adif-log` capability), built once at daemon startup and kept live as
new QSOs are logged during the session. For each decoded message, resolves five independent
tri-state dimensions — has this exact callsign (Contact), this DXCC entity (Country), this
continent (Continent), this CQ Zone, or this ITU Zone been worked before, anywhere in
`ADIF.log`'s history, on any band or mode, and if so whether on the session's current active
band (`ThisBand`) or only some other band (`DifferentBand`), or never (`Never`) — and attaches
them to the decode-result WebSocket payload alongside `region-lookup`'s existing `region` field.
Fully advisory: a missing or unreadable `ADIF.log`, a malformed line, or any resolution failure
degrades to `Never` on the affected axis and never withholds a decode from `ALL.TXT` or the UI,
matching the `region-lookup` capability's existing advisory-only guarantee.

## Requirements

### Requirement: Worked-before index built from `ADIF.log` at startup

The daemon SHALL build an in-memory index of every distinct callsign that appears in a `CALL`
field anywhere in `ADIF.log`, read from the same path `AdifLogWriter` resolves and writes to
(`adif-log` capability). The index SHALL be built once at daemon startup, before decoding begins
serving worked-before results.

For each distinct logged callsign, the daemon SHALL additionally resolve its DXCC entity,
continent, CQ zone, and ITU zone via `ICallsignRegionStore.TryGetRegion` (`region-lookup`
capability) and record the resolved values for matching, subject to the Unknown/synthetic
exclusion below (unchanged from the original capability).

For each historical ADIF record, the daemon SHALL additionally read the record's `BAND` field
(when present and parseable) and associate it with that record's callsign and resolved
entity/continent/CQ-zone/ITU-zone values, so worked-before resolution can distinguish "worked on
this band" from "worked on some other band." A record whose `BAND` field is missing or
unparseable SHALL still contribute its callsign/entity/continent/zone values to the "worked at
all" fact for each axis, but SHALL NOT contribute to any specific band — such a record can never
by itself cause a later decode to resolve `ThisBand` for any axis.

#### Scenario: Index populated from an existing ADIF.log at startup

- **WHEN** the daemon starts and `ADIF.log` exists with one or more valid
  `<call:N>VALUE...<band:N>VALUE...<eor>` records
- **THEN** the worked-before index SHALL contain every distinct callsign found in those records,
  each associated with the band(s) it was worked on, available before the first decode cycle
  completes

#### Scenario: Missing ADIF.log degrades to an empty index, not an error

- **WHEN** the daemon starts and `ADIF.log` does not exist at the resolved path
- **THEN** the daemon SHALL start normally with an empty worked-before index (all decodes resolve
  to `Never` on every dimension) and SHALL NOT log this as an error condition

#### Scenario: Malformed or unparseable lines are skipped, not fatal

- **WHEN** `ADIF.log` contains one or more lines that do not yield a parseable `CALL` token (e.g.
  truncated, non-ADIF content)
- **THEN** the daemon SHALL skip each such line, log a Warning identifying the condition, and
  continue loading the remainder of the file into the index

#### Scenario: A record with CALL but no parseable BAND is indexed as "worked, band unknown"

- **WHEN** `ADIF.log` contains a record with a valid `<call:N>` tag but no `<band:N>` tag (or an
  unparseable one) — for example a record written before D-013's fix, when dial frequency
  resolved to `0.0`
- **THEN** the callsign (and its resolved entity/continent/CQ-zone/ITU-zone) SHALL be indexed as
  worked at all (sufficient to avoid `WorkedBeforeState.Never`), but SHALL NOT be associated with
  any band, and a later decode of that same station on any band SHALL resolve at most
  `DifferentBand` on the Contact axis from this record alone, never `ThisBand`

---

### Requirement: Index updated live when a new QSO is logged

When `AdifLogWriter.AppendQsoAsync` successfully writes a new ADIF record, the daemon SHALL
register that record's partner callsign, its resolved DXCC entity/continent/CQ-zone/ITU-zone
(subject to the Unknown/synthetic exclusion below), and the band the QSO was worked on (already
computed by `AdifLogWriter` for the record's own `BAND` tag) into the same in-memory
worked-before index used to serve decode results, without requiring a daemon restart or a
re-read of `ADIF.log`.

#### Scenario: A station logged this session is confirmed on its next decode, band-correct

- **WHEN** a QSO with callsign `Q1XYZ` on band `20m` is successfully logged to `ADIF.log` during
  the current session
- **THEN** the very next decode of a message whose primary callsign token is `Q1XYZ`, while the
  session's current active band is `20m`, SHALL resolve `workedBefore.contact` as `ThisBand`

#### Scenario: A station logged on a different band than the current session band

- **WHEN** a QSO with callsign `Q1XYZ` on band `40m` is successfully logged to `ADIF.log`, and the
  session's current active band is `20m`
- **THEN** the next decode of `Q1XYZ` SHALL resolve `workedBefore.contact` as `DifferentBand`, not
  `ThisBand`

#### Scenario: A failed ADIF write does not register the callsign

- **WHEN** `AdifLogWriter.AppendQsoAsync` fails to write (e.g. `IOException`,
  `UnauthorizedAccessException`, per the `adif-log` capability's existing failure handling)
- **THEN** the worked-before index SHALL NOT register that callsign or band, consistent with no
  record actually having been persisted

---

### Requirement: `WorkedBefore` field attached to the decode-result payload

For each decoded message, the daemon SHALL resolve worked-before state for the message's primary
callsign-position token across five independent dimensions — **Contact** (exact callsign),
**Country** (DXCC entity), **Continent**, **CQ Zone**, and **ITU Zone** — each resolving to one of
three states: `Never` (not worked on this axis, any band), `DifferentBand` (worked on this axis,
but not on the session's current active band), or `ThisBand` (worked on this axis, on the
session's current active band). The resolved `workedBefore` field SHALL be attached to the
decode-result payload delivered over the existing WebSocket decode channel, alongside the
existing `region` field, so the frontend does not need a separate lookup round-trip.

The "session's current active band" SHALL be resolved via the same live-CAT-aware three-tier
frequency rule used elsewhere in the daemon (`region-lookup`/dial-frequency resolution
precedent), converted to a band name using the same frequency→band-name mapping `AdifLogWriter`
uses for its own `BAND` field. When the current band cannot be resolved (no CAT, no manual
fallback configured, or the resolved frequency falls outside all known amateur bands), every
dimension that would otherwise resolve `ThisBand` SHALL instead resolve `DifferentBand` (if
worked on any band at all) — never `ThisBand` on an unresolvable current band, and never an error
surfaced to the operator.

Resolution failure of any kind (index unavailable, lookup exception) SHALL degrade every
dimension to `Never` and SHALL NOT withhold the decode from `ALL.TXT` or the UI, matching this
capability's existing advisory-only guarantee.

#### Scenario: Decode-result payload includes five independent tri-state dimensions

- **WHEN** a message is decoded whose primary callsign token has been worked before (on a
  different band) but its DXCC entity has never been worked at all
- **THEN** the decode-result payload's `workedBefore` field SHALL report `contact: DifferentBand`,
  `country: Never` (and `continent`/`cqZone`/`ituZone` per their own resolution)

#### Scenario: Current band unresolvable — ThisBand never claimed

- **WHEN** the daemon cannot resolve the session's current active band (no CAT connection and no
  manual dial-frequency fallback configured), and a decode's callsign has been worked before on
  some band
- **THEN** `workedBefore.contact` SHALL resolve `DifferentBand`, never `ThisBand`

#### Scenario: Worked-before resolution failure does not affect the decode pipeline

- **WHEN** worked-before resolution throws or the index is unavailable for any reason
- **THEN** the daemon SHALL log the condition, resolve every `workedBefore` dimension as `Never`
  for the affected decode, and continue decoding and displaying messages normally

---

### Requirement: Contact (callsign) matching includes portable-suffix variants, band-aware

The Contact (exact callsign) worked-before check SHALL treat two callsign tokens as the same
station if they are exactly equal, or if one is a portable-suffixed variant of the other's base
callsign (a `"/"`-delimited suffix appended to the base, e.g. `PD2FZ/P` matching base `PD2FZ`) —
the same matching semantics as the existing frontend `tokenMatchesCallsign` helper used for CQ
click-to-answer. The result SHALL be `Never` if no historically-logged callsign matches;
`DifferentBand` if at least one match exists but none was worked on the session's current active
band; `ThisBand` if at least one match was worked on the current active band.

#### Scenario: Exact callsign match, never worked

- **WHEN** a decode's primary callsign token is `Q2ABC` and no entry equal to or a portable
  variant of `Q2ABC` has ever been logged
- **THEN** `workedBefore.contact` SHALL be `Never`

#### Scenario: Exact callsign match, worked on a different band

- **WHEN** a decode's primary callsign token is `Q1TST`, `Q1TST` was logged on band `40m`, and the
  session's current active band is `20m`
- **THEN** `workedBefore.contact` SHALL be `DifferentBand`

#### Scenario: Exact callsign match, worked on the current band

- **WHEN** a decode's primary callsign token is `Q1TST`, `Q1TST` was logged on band `20m`, and the
  session's current active band is `20m`
- **THEN** `workedBefore.contact` SHALL be `ThisBand`

#### Scenario: Portable-suffixed decode matches a plain historical log entry, band-aware

- **WHEN** a decode's primary callsign token is `Q1TST/P`, `Q1TST` (no suffix) was logged on band
  `20m`, and the session's current active band is `20m`
- **THEN** `workedBefore.contact` SHALL be `ThisBand`

#### Scenario: Plain decode matches a portable-suffixed historical log entry, band-aware

- **WHEN** a decode's primary callsign token is `Q1TST`, `Q1TST/P` was logged on band `40m`, and
  the session's current active band is `20m`
- **THEN** `workedBefore.contact` SHALL be `DifferentBand`

#### Scenario: Worked on both the current band and a different band — ThisBand wins

- **WHEN** a decode's primary callsign token is `Q1TST`, logged once on `40m` and once on `20m`,
  and the session's current active band is `20m`
- **THEN** `workedBefore.contact` SHALL be `ThisBand` (any current-band match takes priority over
  a different-band-only match)

---

### Requirement: Country, Continent, CQ Zone, and ITU Zone matching, band-aware, with Unknown and synthetic entries excluded

The worked-before check SHALL compare, for each of the Country (DXCC entity), Continent, CQ
Zone, and ITU Zone axes, the value resolved for the decode's primary callsign token against the
set of that same value type resolved for historically-logged callsigns, and resolve `Never` /
`DifferentBand` / `ThisBand` using the same band-priority rule as the Contact axis (any
current-band match wins over a different-band-only match). A resolution that fails (lookup miss,
"Unknown") or resolves to the synthetic Q-series entry (`Synthetic == true`, NFR-021) SHALL be
excluded from all four sides of the comparison: it SHALL NOT be inserted into any of the four
worked-value indexes, and a decode whose own resolution is Unknown or synthetic SHALL always
resolve all four dimensions to `Never`, regardless of index content.

#### Scenario: Same DXCC entity previously worked, on the current band

- **WHEN** a decode's primary callsign token resolves to entity `"Germany"`, and some
  historically-logged callsign also resolves to entity `"Germany"` and was worked on the session's
  current active band
- **THEN** `workedBefore.country` SHALL be `ThisBand`

#### Scenario: Same continent previously worked, different entity, different band

- **WHEN** a decode's primary callsign token resolves to continent `"EU"`, entity `"Monaco"`; no
  historically-logged callsign resolves to entity `"Monaco"`, but at least one resolves to
  continent `"EU"` (e.g. entity `"Germany"`), worked only on a band other than the session's
  current active band
- **THEN** `workedBefore.continent` SHALL be `DifferentBand` and `workedBefore.country` SHALL be
  `Never`

#### Scenario: Same CQ Zone previously worked (new axis)

- **WHEN** a decode's primary callsign token resolves to CQ Zone `14`, and some historically-logged
  callsign also resolves to CQ Zone `14`, worked on the session's current active band
- **THEN** `workedBefore.cqZone` SHALL be `ThisBand`

#### Scenario: Same ITU Zone previously worked (new axis)

- **WHEN** a decode's primary callsign token resolves to ITU Zone `27`, and some historically-logged
  callsign also resolves to ITU Zone `27`, worked on a band other than the session's current
  active band
- **THEN** `workedBefore.ituZone` SHALL be `DifferentBand`

#### Scenario: Two unresolved callsigns never co-match

- **WHEN** a decode's primary callsign token fails to resolve (`"Unknown"`), even if one or more
  historically-logged callsigns also failed to resolve
- **THEN** `workedBefore.country`, `workedBefore.continent`, `workedBefore.cqZone`, and
  `workedBefore.ituZone` SHALL all be `Never`

#### Scenario: Synthetic Q-prefix decode never matches, and never contributes to a match

- **WHEN** a decode's primary callsign token resolves to the synthetic region (NFR-021), or a
  historically-logged callsign resolves to the synthetic region
- **THEN** that decode's `workedBefore.country`/`continent`/`cqZone`/`ituZone` SHALL all be
  `Never`, and no synthetic-resolved historical callsign SHALL cause a real decode's Country/
  Continent/CQ-Zone/ITU-Zone check to become anything other than `Never`
