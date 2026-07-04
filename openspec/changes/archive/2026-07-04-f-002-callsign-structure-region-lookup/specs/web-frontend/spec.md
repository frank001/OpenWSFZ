## ADDED Requirements

### Requirement: Decode table — region column

Each decode table row SHALL display the region resolved for that decode's `region` field
(delivered on the decode-result WebSocket payload per the `region-lookup` capability), rendered
as a new column/badge on the row. Rendering SHALL follow these rules:

- A recognised, non-synthetic region SHALL render as `"{continent} — {entity}"` (e.g.
  `"EU — Monaco"`).
- The synthetic region SHALL render as its label verbatim (`"Synthetic (R&R Study)"`), with no
  continent prefix.
- An unresolved region SHALL render as `"Unknown"`.
- The column SHALL be populated at row-creation time, consistent with the existing `decode-cq`/
  `decode-responder` class-assignment timing, and SHALL NOT require a separate network round-trip
  (the region value arrives pre-computed on the decode payload).

#### Scenario: Recognised prefix renders continent and entity

- **WHEN** a decode row's payload has `region: { continent: "EU", entity: "Monaco", synthetic:
  false }`
- **THEN** the rendered decode table row SHALL display `"EU — Monaco"` in the region column

#### Scenario: Synthetic prefix renders without a continent

- **WHEN** a decode row's payload has `region: { entity: "Synthetic (R&R Study)", synthetic:
  true }`
- **THEN** the rendered decode table row SHALL display `"Synthetic (R&R Study)"` in the region
  column, with no continent segment

#### Scenario: Unresolved prefix renders Unknown

- **WHEN** a decode row's payload has no matching region (`region: "Unknown"` or equivalent
  absent/null value)
- **THEN** the rendered decode table row SHALL display `"Unknown"` in the region column

#### Scenario: Region column present on every decode row regardless of message type

- **WHEN** any decode is rendered in the decode table (CQ, standard QSO, Type 4 nonstandard
  literal, or hash-reference message)
- **THEN** the row SHALL include a region column value, falling back to `"Unknown"` if the
  message's callsign-position token cannot be resolved
