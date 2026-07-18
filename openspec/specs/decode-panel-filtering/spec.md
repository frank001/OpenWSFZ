# decode-panel-filtering Specification

## Purpose

This capability defines the daemon-owned, ephemeral decode-visibility filter that gates which
decodes are considered "visible/engageable" across the decode table UI and both QSO controller
services (`QsoAnswererService`, `QsoCallerService`). It covers the `DecodeFilterState` shape (nine
independent axes: four attribute allow-lists and five worked-before tri-state selections), the
shared daemon-owned state model (no persistence, broadcast to all connected clients via
`decodeFilterChanged`), the advisory, fail-open evaluation semantics applied to decodes with
unresolved attributes, and the daemon-side auto-admission of previously-unseen attribute values
into a narrowed-but-non-empty allow-list axis, so a genuinely new DXCC entity/continent/CQ-zone/
ITU-zone is engageable by default rather than silently excluded.

## Requirements

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

---

### Requirement: Attribute allow-list axes auto-admit previously-unseen values

The daemon SHALL track which values have been observed this session for each of the four
attribute allow-list axes (DXCC entity, Continent, CQ Zone, ITU Zone). When a decode carries a
value on one of these axes that has never been observed this session, and that axis's current
allow-list is narrowed-but-non-empty (a non-null array containing at least one value), the daemon
SHALL admit the new value into that axis's allow-list, so it is considered visible/engageable by
default — matching the behavior of an axis that has never been touched. A value already observed
this session, whether currently included or explicitly excluded by the operator, SHALL NOT be
re-admitted or altered by this mechanism.

This auto-admission SHALL be performed by the daemon itself, independent of any connected browser
client, so it applies identically during headless operation (`daemon-background-mode`,
`--background`/`--background-worker`) as it does with a browser tab attached.

An axis whose current allow-list is explicitly empty (`[]` — the operator has deselected every
value on that axis) SHALL NOT auto-admit new values — this preserves the existing "an axis with an
explicit empty selection filters everything on that axis" behavior exactly, including for values
never before seen.

Whenever an auto-admission changes the current `DecodeFilterState`, the daemon SHALL broadcast the
updated state via the existing `decodeFilterChanged` WebSocket event, identical to an
operator-driven `POST /api/v1/decode-filter`, so every connected client's popup and rendered table
converge on the same authoritative state the daemon itself evaluated engagement against.

#### Scenario: A brand-new DXCC entity is admitted into a narrowed-but-non-empty axis

- **WHEN** the DXCC-entity allow-list axis is narrowed to `{"Germany", "Monaco"}` (the operator
  previously deselected at least one other, already-seen entity) and a decode arrives whose
  resolved entity is `"Wallis and Futuna"`, never before seen this session
- **THEN** the daemon SHALL admit `"Wallis and Futuna"` into the allow-list (now
  `{"Germany", "Monaco", "Wallis and Futuna"}`), and the decode SHALL be considered
  visible/engageable on this axis

#### Scenario: An already-seen, explicitly-excluded value is never re-admitted

- **WHEN** the DXCC-entity allow-list axis is narrowed to `{"Germany"}` after the operator
  explicitly deselected `"Monaco"` (previously seen), and a further decode arrives resolving to
  `"Monaco"`
- **THEN** the allow-list SHALL remain `{"Germany"}` — `"Monaco"` SHALL NOT be re-admitted, and the
  decode SHALL remain not visible/engageable on this axis

#### Scenario: An explicitly empty axis never auto-admits

- **WHEN** the DXCC-entity allow-list axis is explicitly empty (`[]`, e.g. via "Select None") and
  a decode arrives whose resolved entity has never been observed this session
- **THEN** the allow-list SHALL remain `[]`, and the decode SHALL NOT be considered
  visible/engageable on this axis

#### Scenario: An untouched (null) axis is unaffected by admission tracking

- **WHEN** the DXCC-entity allow-list axis has never been narrowed (still `null`) and a decode
  arrives whose resolved entity has never been observed this session
- **THEN** no state change or broadcast SHALL occur — the axis remains `null` (no restriction),
  matching its existing default behavior

#### Scenario: Auto-admission applies without any browser client connected

- **WHEN** the daemon is running headless (`--background`, no browser tab connected) with a
  narrowed-but-non-empty DXCC-entity axis, and a decode arrives resolving to a never-before-seen
  entity
- **THEN** the daemon SHALL still admit the new entity into the allow-list and make it
  engageable to `QsoAnswererService`/`QsoCallerService` on that same decode cycle, identical to
  the attended case

#### Scenario: Admission is visible to the same decode cycle's engagement decision

- **WHEN** a decode carrying a never-before-seen attribute value on a narrowed-but-non-empty axis
  is processed by the daemon
- **THEN** `QsoAnswererService`/`QsoCallerService`'s engagement-decision evaluation of that same
  decode, later in the same cycle, SHALL see the already-admitted (updated) filter state — not
  the pre-admission state
