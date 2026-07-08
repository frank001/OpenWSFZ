## ADDED Requirements

### Requirement: Decode table — worked-before confirmation columns

`#decodes-table` SHALL display three additional readonly checkbox columns, positioned
immediately after the existing Region column (the rightmost columns in the table): **P**
(Partner), **C** (Country), **R** (Region). Each column header SHALL display only the single
letter, with a `title` attribute of `"Partner"`, `"Country"`, and `"Region"` respectively for
tooltip disclosure. Each column SHALL be styled as narrow as practical (checkbox content only, no
excess padding).

Each cell SHALL contain a checkbox reflecting the corresponding boolean on that row's decode
payload `workedBefore` field (`call`/`country`/`region` — `qso-confirmation` capability),
populated at row-creation time with no separate network round-trip, consistent with the existing
Region column's population timing. Each checkbox SHALL be non-interactive (readonly) — since the
HTML `readonly` attribute has no effect on `<input type="checkbox">`, this SHALL be implemented
via the `disabled` attribute, reflecting state only and never accepting operator input.

#### Scenario: All three columns checked when previously worked

- **WHEN** a decode row's payload has `workedBefore: { call: true, country: true, region: true }`
- **THEN** the rendered row SHALL show all three checkboxes (P, C, R) checked

#### Scenario: Independent per-column state

- **WHEN** a decode row's payload has `workedBefore: { call: false, country: true, region: true }`
  (station never worked, but its country and continent have been)
- **THEN** the rendered row SHALL show P unchecked, C and R checked

#### Scenario: All three columns unchecked when never worked before

- **WHEN** a decode row's payload has `workedBefore: { call: false, country: false, region:
  false }`, or the `workedBefore` field is absent from the payload
- **THEN** the rendered row SHALL show all three checkboxes unchecked

#### Scenario: Checkboxes are not operator-editable

- **WHEN** an operator attempts to click any of the P/C/R checkboxes on any decode row
- **THEN** the checkbox state SHALL NOT change as a result of the click (the control is
  `disabled`)

#### Scenario: Columns present on every decode row regardless of message type

- **WHEN** any decode is rendered in the decode table (CQ, standard QSO, Type 4 nonstandard
  literal, or hash-reference message)
- **THEN** the row SHALL include all three P/C/R checkbox cells, defaulting to unchecked if
  `workedBefore` is absent or a given sub-field cannot be resolved

#### Scenario: No-data placeholder row spans the full column count

- **WHEN** the decode table has no decodes yet and displays its placeholder row
- **THEN** the placeholder row's `colspan` SHALL equal the table's total column count, including
  the three new P/C/R columns
