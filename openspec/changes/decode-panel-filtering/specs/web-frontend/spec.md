## ADDED Requirements

### Requirement: Decode table — clickable column-header filter popups

`#decodes-table` SHALL make the DXCC, Continent (Cnt), CQ Zone (CQz), and ITU Zone (ITz) column
headers clickable, opening a popup with two sections: an attribute allow-list (multi-select
checkboxes for values currently relevant to the session, defaulting to all selected) and a
worked-before tri-state selection (`Never`/`DifferentBand`/`ThisBand`, defaulting to all
selected). The Ctc (Contact) column header SHALL also be clickable, opening a popup with only the
worked-before tri-state section (no attribute allow-list — there is no small enumerable
value-set for individual callsigns). Closing the popup without changes SHALL leave the filter
unchanged. Changing a selection SHALL issue `POST /api/v1/decode-filter` with the updated state
(`decode-panel-filtering` capability).

#### Scenario: Clicking a DXCC/Cnt/CQz/ITz header opens a two-section popup

- **WHEN** the operator clicks the DXCC column header
- **THEN** a popup SHALL open showing both an entity allow-list section and a worked-before
  tri-state section, both currently reflecting the daemon's active filter state

#### Scenario: Clicking the Ctc header opens a one-section popup

- **WHEN** the operator clicks the Ctc column header
- **THEN** a popup SHALL open showing only the worked-before tri-state section

#### Scenario: Changing a selection updates the daemon's filter state

- **WHEN** the operator unchecks a value in any popup section
- **THEN** the frontend SHALL issue `POST /api/v1/decode-filter` with the updated
  `DecodeFilterState`

---

### Requirement: Decode table — filtered-out rows are hidden and re-evaluated on filter change

`#decodes-table` SHALL hide any decode row that `DecodeFilterEvaluator`'s ported JS twin
(`decode-panel-filtering` capability) evaluates as not visible against the current filter state
(not rendered, or rendered then immediately hidden — implementation detail left to the
developer). On receipt of a `decodeFilterChanged` WebSocket event, the frontend SHALL
re-evaluate visibility for every currently-rendered row against the new filter state, showing or
hiding rows accordingly, without requiring a page reload.

#### Scenario: A decode failing the active filter is not shown

- **WHEN** a new decode arrives whose attributes fail at least one active filter axis
- **THEN** the row SHALL NOT be rendered as visible in `#decodes-table`

#### Scenario: Changing the filter re-evaluates already-rendered rows

- **WHEN** the filter changes (via a `decodeFilterChanged` event, from any client) while rows are
  already rendered in the table
- **THEN** each already-rendered row SHALL be re-evaluated against the new filter and shown or
  hidden accordingly, without waiting for a new decode to arrive
