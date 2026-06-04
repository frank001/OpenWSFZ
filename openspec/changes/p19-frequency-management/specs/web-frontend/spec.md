## ADDED Requirements

### Requirement: Settings page — Frequencies tab

The Settings page SHALL contain a fourth tab labelled **"Frequencies"** inserted after the existing *Advanced* tab. The tab SHALL allow the operator to view, add, edit, and delete working frequency entries. It SHALL participate in the same Save / unsaved-changes flow as the other tabs: changes are not applied until the operator clicks **Save**.

The tab content SHALL be a table with the following columns:
- **Protocol** — editable text input, e.g. `FT8`
- **Frequency (MHz)** — editable numeric input (step `0.001`, min `0`)
- **Description** — editable text input, e.g. `40m` (may be empty)
- **Delete** — a button per row that removes the row from the table

An **"Add frequency"** button below the table SHALL append a new blank row with `protocol` pre-filled to `"FT8"` and `frequencyMHz` set to `0.000`.

#### Scenario: Frequencies tab is present on the Settings page

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain a tab button labelled "Frequencies" with `aria-controls="tab-frequencies"` and a corresponding tab panel with `id="tab-frequencies"`

#### Scenario: Frequencies tab loads the current list from the API

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the page JavaScript SHALL call `GET /api/v1/frequencies` and populate the table with one row per returned entry

#### Scenario: Empty frequency list shows a placeholder row

- **WHEN** `GET /api/v1/frequencies` returns an empty array
- **THEN** the table SHALL display a single disabled row with the text "No frequencies configured — click Add to begin"

#### Scenario: Add frequency appends a new editable row

- **WHEN** the operator clicks the "Add frequency" button
- **THEN** a new row SHALL be appended to the table with `protocol = "FT8"`, `frequencyMHz = 0.000`, and `description = ""`
- **AND** the unsaved-changes indicator SHALL become visible

#### Scenario: Delete button removes the row

- **WHEN** the operator clicks the Delete button in a row
- **THEN** that row SHALL be removed from the table immediately
- **AND** the unsaved-changes indicator SHALL become visible

#### Scenario: Editing a field marks the form dirty

- **WHEN** the operator changes any cell value in the Frequencies table
- **THEN** the unsaved-changes indicator (FR-040) SHALL become visible

#### Scenario: Save posts the complete updated list

- **WHEN** the operator clicks the Save button while the Frequencies tab has unsaved changes
- **THEN** the page SHALL `POST /api/v1/frequencies` with the full serialised frequency list as a JSON array
- **AND** on HTTP 200 the unsaved-changes indicator for the frequencies list SHALL clear

#### Scenario: Frequencies tab is included in the FR-040 dirty-state comparison

- **WHEN** a browser loads `GET /settings.html` and the operator modifies a frequency entry
- **THEN** the JSON snapshot used by the FR-040 dirty-state check SHALL include the serialised frequency list so that the unsaved-changes indicator correctly reflects a change in this tab

#### Scenario: Row order is preserved on save

- **WHEN** the operator reorders rows by adding/deleting and then saves
- **THEN** the list persisted to `frequencies.json` SHALL reflect the order of rows in the table at the time of Save

---

## MODIFIED Requirements

### Requirement: Main page layout

The main page (`index.html`) SHALL contain a waterfall panel, a decoded-messages panel, a status bar, and a navigation affordance to the Settings page. All panels SHALL be present in Phase 3; the waterfall and decoded-messages panels display placeholder content until Phase 5 populates them with real data.

The status bar SHALL contain a `#dial-freq` element whose rendering adapts to the current CAT connection state:

- **CAT active** (CAT `status` is `Connected` or `Connecting`): `#dial-freq` SHALL render as a `<select>` element populated with working frequencies for the active protocol (FT8), with one `<option>` per entry showing the frequency formatted to three decimal places and the description (e.g., `14.074 MHz — 20m`). The option whose `value` is closest to the current `dialFrequencyMHz` SHALL be pre-selected. Changing the selected option SHALL immediately call `POST /api/v1/tune` with the chosen frequency.
- **CAT inactive** (CAT `status` is `Disabled` or `Error`, or no `cat_status` event has been received): `#dial-freq` SHALL render as a `<span>` element displaying the effective dial frequency as plain text (existing behaviour: three decimal places followed by `MHz`).

The transition between `<select>` and `<span>` SHALL occur in response to `cat_status` or `status` WebSocket events without a page reload. The element `id="dial-freq"` SHALL be present on whichever element is currently active.

The frequency list used to populate the `<select>` SHALL be fetched once from `GET /api/v1/frequencies` on page load, filtered to the active protocol (`"FT8"` in this change), and cached in `main.js`. The cached list SHALL be reused whenever the `<select>` is (re-)rendered.

#### Scenario: Main page contains waterfall canvas

- **WHEN** a browser loads `GET /`
- **THEN** the DOM SHALL contain a `<canvas>` element with `id="waterfall"` that is visible and occupies a significant portion of the viewport

#### Scenario: Waterfall canvas renders placeholder

- **WHEN** the main page JavaScript initialises
- **THEN** the canvas SHALL be painted with a dark background and placeholder text indicating that audio input is awaited

#### Scenario: Main page contains decoded-messages table

- **WHEN** a browser loads `GET /`
- **THEN** the DOM SHALL contain a `<table>` element with column headers for at minimum Time, Freq, and Message; the table body SHALL contain at least one row (a no-data placeholder row)

#### Scenario: Main page contains status bar

- **WHEN** a browser loads `GET /`
- **THEN** the DOM SHALL contain a status bar element that displays the WebSocket connection state and the active audio device name (or a "none" indicator)

#### Scenario: Settings navigation affordance is present

- **WHEN** a browser loads `GET /`
- **THEN** the page SHALL contain a visible link or button that navigates to `/settings.html`

#### Scenario: #dial-freq is a span when CAT is disabled

- **WHEN** the main page receives a `status` or `cat_status` event with `status = "Disabled"` or `status = "Error"`
- **THEN** `#dial-freq` SHALL be a `<span>` element displaying the effective frequency as text (e.g., `14.074 MHz`)

#### Scenario: #dial-freq becomes a select when CAT is active

- **WHEN** the main page receives a `cat_status` or `status` event with CAT `status = "Connected"` or `status = "Connecting"`
- **THEN** `#dial-freq` SHALL be rendered as a `<select>` element populated with FT8 frequency options
- **AND** the option closest to the current `dialFrequencyMHz` SHALL be selected

#### Scenario: Selecting a frequency from #dial-freq calls tune

- **WHEN** the operator changes the selected option in `#dial-freq`
- **THEN** `main.js` SHALL call `POST /api/v1/tune` with `{ "frequencyMHz": <selected value> }`
- **AND** on HTTP 200 the status bar frequency display SHALL update to reflect the response's `effectiveFrequencyMHz`

#### Scenario: Frequency list fetched once on page load

- **WHEN** the main page JavaScript initialises
- **THEN** a single `GET /api/v1/frequencies` request SHALL be issued
- **AND** the result SHALL be cached and reused for all subsequent renders of the `<select>` without additional requests
