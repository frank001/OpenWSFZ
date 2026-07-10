## ADDED Requirements

### Requirement: Filter state defaults to unfiltered, nine independent axes

The daemon SHALL maintain a single, in-memory `DecodeFilterState` covering nine independent
axes: four attribute allow-lists (DXCC entity, Continent, CQ Zone, ITU Zone) and five
worked-before tri-state selections (Contact, Country, Continent, CQ Zone, ITU Zone — one per
`qso-confirmation-band-awareness` dimension). Each axis SHALL default to "no restriction" (every
value passes) — a freshly-started daemon, or any axis the operator has never touched, SHALL
impose no filtering on that axis.

#### Scenario: Freshly started daemon filters nothing

- **WHEN** the daemon starts and no filter has been set via the API
- **THEN** every decode SHALL be considered visible/engageable on all nine axes

#### Scenario: An axis with an explicit empty selection filters everything on that axis

- **WHEN** the operator has explicitly deselected every value on the DXCC-entity allow-list axis
- **THEN** no decode SHALL pass that axis, distinct from the axis never having been touched

---

### Requirement: Filter state is daemon-owned, ephemeral, and shared across all connected clients

The current `DecodeFilterState` SHALL NOT be persisted to `TxConfig`, any configuration file, or
any other durable store — it SHALL reset to the unfiltered default on every daemon restart.
`GET /api/v1/decode-filter` SHALL return the current state. `POST /api/v1/decode-filter` SHALL
replace the entire current state (whole-object replace) and SHALL broadcast a
`decodeFilterChanged` WebSocket event carrying the new state to every connected client. The
filter SHALL NOT be scoped per browser tab or per connection — the most recent `POST` SHALL be
authoritative for all connected clients and for both QSO controller services.

#### Scenario: Filter change is broadcast to all connected clients

- **WHEN** one connected client issues `POST /api/v1/decode-filter` with a new state
- **THEN** every currently-connected WebSocket client SHALL receive a `decodeFilterChanged` event
  carrying the new state, including the client that issued the POST

#### Scenario: Filter resets on daemon restart

- **WHEN** the daemon is restarted after a non-default filter was previously set
- **THEN** `GET /api/v1/decode-filter` SHALL return the unfiltered default state

#### Scenario: Last write wins across multiple clients

- **WHEN** client A sets a filter, then client B sets a different filter
- **THEN** the daemon's authoritative state SHALL be client B's filter, and both
  `QsoAnswererService` and `QsoCallerService` SHALL evaluate engagement decisions against client
  B's filter, not client A's

---

### Requirement: Filter-evaluation predicate is advisory and fails open on unresolved data

A decode SHALL be considered visible/engageable if and only if it passes every axis of the
current `DecodeFilterState` whose value is non-null (an active restriction). A decode whose
relevant attribute is unresolved (e.g. `Region: null`, or a `WorkedBefore` sub-field absent)
SHALL NOT be excluded by an active attribute-allow-list filter on that axis — an unresolved value
always passes an attribute-allow-list axis, regardless of the axis's contents. A `WorkedBefore`
field absent from the decode payload SHALL be treated as `Never` on every worked-before axis for
filtering purposes, participating normally in an active worked-before-axis filter.

#### Scenario: Unresolved region attribute is never filtered out by an active allow-list

- **WHEN** a decode's `Region` is `null` (unresolved) and the DXCC-entity allow-list axis is
  actively restricted to a specific set of entities
- **THEN** the decode SHALL still be considered visible/engageable on that axis, regardless of
  which entities are in the allow-list

#### Scenario: Absent WorkedBefore is treated as Never for filtering

- **WHEN** a decode's `WorkedBefore` field is absent and the Contact worked-before axis is
  actively restricted to exclude `Never`
- **THEN** the decode SHALL be filtered out on that axis, identical to an explicit `Never`
  resolution

#### Scenario: A decode passing all active axes is visible

- **WHEN** a decode's resolved attributes and worked-before states satisfy every currently active
  (non-null) axis of the filter
- **THEN** the decode SHALL be considered visible/engageable
