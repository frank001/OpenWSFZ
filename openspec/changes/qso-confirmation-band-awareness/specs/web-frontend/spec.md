## REMOVED Requirements

### Requirement: Decode table — worked-before confirmation columns

**Reason**: Superseded by "Decode table — band-aware worked-before confirmation columns" below —
the three columns (P/C/R) are renamed (Ctc/DXCC/Cnt), two new columns are added (CQz/ITz), and
every cell's glyph becomes tri-state (never/different-band/this-band) instead of a binary
checkmark, per the Captain's explicit direction to mirror WSJT-X/JTAlert-style worked-before-by-
band indication and to resolve the "Region" naming collision with the pre-existing Region display
column.

**Migration**: No data migration — purely a rendering and column-set change over the same decode
payload's `workedBefore` field (whose shape changes from three booleans to five tri-state values
in the `qso-confirmation-band-awareness` backend change this delta is paired with). Existing
readonly, non-interactive `<span>`-based rendering approach (no `disabled` checkbox — see the
original capability's Decision 7) is carried forward unmodified; only the glyph content and
column set change.

## ADDED Requirements

### Requirement: Decode table — band-aware worked-before confirmation columns

`#decodes-table` SHALL display five readonly indicator columns, positioned immediately after the
existing Region column (the rightmost columns in the table, replacing the previous three-column
P/C/R set): **Ctc** (Contact), **DXCC** (Country), **Cnt** (Continent), **CQz** (CQ Zone), **ITz**
(ITU Zone). Each column header SHALL display the abbreviated label shown above, with a `title`
attribute giving the full dimension name (`"Contact"`, `"DXCC (Country)"`, `"Continent"`,
`"CQ Zone"`, `"ITU Zone"` respectively) for tooltip disclosure. Each column SHALL be styled as
narrow as practical (indicator content only, no excess padding).

Each cell SHALL contain a non-interactive `<span>` reflecting the corresponding tri-state value on
that row's decode payload `workedBefore` field (`contact`/`country`/`continent`/`cqZone`/`ituZone`
— `qso-confirmation` capability), populated at row-creation time with no separate network
round-trip, consistent with the existing Region column's population timing. Rendering SHALL
follow these rules:

- `Never` (or the field/sub-field absent) → the span SHALL be empty.
- `DifferentBand` → the span SHALL display a distinct "worked, different band" glyph, visually
  differentiated from both the empty state and the `ThisBand` state (exact glyph/colour choice
  left to the implementing developer, consistent with this codebase's existing `--color-success`
  token convention for the `ThisBand` state — e.g. an amber/muted variant for `DifferentBand`).
- `ThisBand` → the span SHALL display the existing checkmark glyph in `--color-success`, unchanged
  from the prior binary implementation's "worked" rendering.

A `<span>` has no interactive semantics, so there is nothing for the operator to click or edit —
carried forward unmodified from the prior implementation.

#### Scenario: All five columns show the this-band glyph when worked on the current band

- **WHEN** a decode row's payload has `workedBefore: { contact: "thisBand", country: "thisBand",
  continent: "thisBand", cqZone: "thisBand", ituZone: "thisBand" }`
- **THEN** the rendered row SHALL show the this-band checkmark glyph in all five indicator cells

#### Scenario: Different-band state renders distinctly from both empty and this-band

- **WHEN** a decode row's payload has `workedBefore: { contact: "differentBand", country: "never",
  continent: "thisBand", cqZone: "never", ituZone: "never" }`
- **THEN** the rendered row SHALL show Ctc with the different-band glyph, DXCC empty, Cnt with the
  this-band checkmark glyph, and CQz/ITz empty — three visually distinct states demonstrated across
  one row

#### Scenario: All five columns empty when never worked before

- **WHEN** a decode row's payload has `workedBefore: { contact: "never", country: "never",
  continent: "never", cqZone: "never", ituZone: "never" }`, or the `workedBefore` field is absent
  from the payload
- **THEN** the rendered row SHALL show all five indicator cells empty

#### Scenario: Indicators are not operator-editable

- **WHEN** an operator attempts to click any of the five indicator cells on any decode row
- **THEN** nothing SHALL happen — the cell contains a plain `<span>`, not an interactive control

#### Scenario: Columns present on every decode row regardless of message type

- **WHEN** any decode is rendered in the decode table (CQ, standard QSO, Type 4 nonstandard
  literal, or hash-reference message)
- **THEN** the row SHALL include all five indicator cells, defaulting to empty if `workedBefore`
  is absent or a given sub-field cannot be resolved

#### Scenario: No-data placeholder row spans the full column count

- **WHEN** the decode table has no decodes yet and displays its placeholder row
- **THEN** the placeholder row's `colspan` SHALL equal the table's total column count, including
  the five worked-before columns (two more than the prior three-column set) and the Band column
  below

---

### Requirement: Decode table — Band column

`#decodes-table` SHALL display a **Band** column positioned immediately after the Time column
(before dB), showing the session's current active band that decode was made on (e.g. `"40m"`),
using the same band-name convention as the Settings → Frequencies tab's Description column. The
cell SHALL be populated from that row's decode payload `band` field (`qso-confirmation-band-awareness`
capability — the same value threaded into worked-before resolution as `currentBand` for that
decode), at row-creation time with no separate network round-trip. When the `band` field is
absent or `null` (current band unresolvable — no CAT, no manual fallback configured, or the
resolved frequency falls outside all known amateur bands), the cell SHALL be empty.

#### Scenario: Band column shows the resolved band

- **WHEN** a decode row's payload has `band: "40m"`
- **THEN** the rendered row SHALL display `"40m"` in the Band column

#### Scenario: Band column is empty when the current band is unresolvable

- **WHEN** a decode row's payload has `band: null`, or the `band` field is absent from the payload
- **THEN** the rendered row SHALL display an empty Band column cell

#### Scenario: Band column present on every decode row regardless of message type

- **WHEN** any decode is rendered in the decode table (CQ, standard QSO, Type 4 nonstandard
  literal, or hash-reference message)
- **THEN** the row SHALL include a Band column cell, defaulting to empty if `band` is absent

#### Scenario: Band column agrees with the worked-before indicators on the same row

- **WHEN** a decode row's payload has `band: "20m"` and `workedBefore.contact: "thisBand"`
- **THEN** both values originate from the same `currentBand` resolution for that decode cycle —
  there is no scenario where the Band column shows one band while a `"thisBand"` worked-before
  indicator on the same row implies a different one
