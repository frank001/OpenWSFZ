## ADDED Requirements

### Requirement: Decode table — worked-before confirmation columns

`#decodes-table` SHALL display three additional readonly indicator columns, positioned
immediately after the existing Region column (the rightmost columns in the table): **P**
(Partner), **C** (Country), **R** (Region). Each column header SHALL display only the single
letter, with a `title` attribute of `"Partner"`, `"Country"`, and `"Region"` respectively for
tooltip disclosure. Each column SHALL be styled as narrow as practical (indicator content only,
no excess padding).

Each cell SHALL contain a non-interactive `<span>` reflecting the corresponding boolean on that
row's decode payload `workedBefore` field (`call`/`country`/`region` — `qso-confirmation`
capability), populated at row-creation time with no separate network round-trip, consistent with
the existing Region column's population timing. When the boolean is `true`, the span SHALL
display a checkmark glyph styled in the success colour (`--color-success`); when `false` (or the
field/sub-field is absent), the span SHALL be empty. A `<span>` has no interactive semantics, so
there is nothing for the operator to click or edit (design.md Decision 7 — this supersedes an
earlier disabled-checkbox implementation found, on manual review, to render too washed-out to
read at a glance against the dark theme).

#### Scenario: All three columns show a checkmark when previously worked

- **WHEN** a decode row's payload has `workedBefore: { call: true, country: true, region: true }`
- **THEN** the rendered row SHALL show a green checkmark in all three indicator cells (P, C, R)

#### Scenario: Independent per-column state

- **WHEN** a decode row's payload has `workedBefore: { call: false, country: true, region: true }`
  (station never worked, but its country and continent have been)
- **THEN** the rendered row SHALL show P empty, C and R with a checkmark

#### Scenario: All three columns empty when never worked before

- **WHEN** a decode row's payload has `workedBefore: { call: false, country: false, region:
  false }`, or the `workedBefore` field is absent from the payload
- **THEN** the rendered row SHALL show all three indicator cells empty

#### Scenario: Indicators are not operator-editable

- **WHEN** an operator attempts to click any of the P/C/R indicator cells on any decode row
- **THEN** nothing SHALL happen — the cell contains a plain `<span>`, not an interactive control

#### Scenario: Columns present on every decode row regardless of message type

- **WHEN** any decode is rendered in the decode table (CQ, standard QSO, Type 4 nonstandard
  literal, or hash-reference message)
- **THEN** the row SHALL include all three P/C/R indicator cells, defaulting to empty if
  `workedBefore` is absent or a given sub-field cannot be resolved

#### Scenario: No-data placeholder row spans the full column count

- **WHEN** the decode table has no decodes yet and displays its placeholder row
- **THEN** the placeholder row's `colspan` SHALL equal the table's total column count, including
  the three new P/C/R columns
