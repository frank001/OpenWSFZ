## Purpose

This capability defines the OpenWSFZ browser user interface: the static frontend directory layout and default theme, the main page and Settings page, the WebSocket status client, and the in-page controls for decode start/stop and status display.
## Requirements
### Requirement: Frontend directory layout

The frontend SHALL live in a top-level `web/` directory at the repository root with the following conventional structure. All files SHALL be plain files on disk that an operator can edit without rebuilding the application.

```
web/
  index.html
  settings.html
  css/
    app.css
  js/
    api.js
    ws.js
    main.js
    settings.js
```

#### Scenario: Build output contains the web directory

- **WHEN** `dotnet build` or `dotnet publish` is run for `OpenWSFZ.Daemon`
- **THEN** the output directory SHALL contain a `web/` subdirectory with all frontend files copied from the repository root `web/` tree

#### Scenario: Static file endpoints return correct content types

- **WHEN** a client requests `GET /index.html`, `GET /settings.html`, `GET /css/app.css`, or any `GET /js/*.js`
- **THEN** the server SHALL respond with HTTP 200 and the appropriate `Content-Type` header (`text/html`, `text/css`, `text/javascript` respectively)

---

### Requirement: Dark default theme

The web UI SHALL ship with a dark theme as its default visual style, implemented via CSS custom properties in `css/app.css`. The theme SHALL be changeable by an operator editing the CSS file on disk without rebuilding the application.

#### Scenario: Main page renders with dark background

- **WHEN** a browser loads `GET /`
- **THEN** the page background SHALL use the dark theme colour defined by the `--color-bg` CSS custom property

#### Scenario: CSS custom properties are defined

- **WHEN** `GET /css/app.css` is fetched
- **THEN** the response SHALL define at minimum the custom properties `--color-bg`, `--color-surface`, `--color-border`, `--color-text`, and `--color-accent` on the `:root` selector

---

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

### Requirement: Settings page

The Settings page (`settings.html`) SHALL allow the operator to view and change the
audio capture device selection, audio output device selection, and port number, then
save those changes to the backend. The Radio hardware tab SHALL contain both an
**Audio capture device** selector and an **Audio output device** selector, with the
output device selector rendered immediately below the capture device selector and
above the CAT rig connection fieldset. The page SHALL be navigable from the main page
and SHALL provide navigation back.

#### Scenario: Settings page loads audio device list

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the page JavaScript SHALL call `GET /api/v1/audio/devices` and populate a
  `<select id="device-select">` element with one `<option>` per returned device; if
  the list is empty a single disabled option reading "No devices found" SHALL be shown

#### Scenario: Settings page loads audio output device list

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the page JavaScript SHALL call `GET /api/v1/audio/output-devices` and
  populate a `<select id="output-device-select">` element with one `<option>` per
  returned device; the first option SHALL always be a "— No device —" option whose
  value is the empty string; if the device list is empty only this placeholder option
  SHALL be shown

#### Scenario: Settings page pre-selects configured device

- **WHEN** the device list has loaded and the current config has a non-null `audioDeviceId`
- **THEN** the `<select id="device-select">` SHALL have the option whose `value` matches `config.audioDeviceId` selected

#### Scenario: Settings page pre-selects configured output device

- **WHEN** the output device list has loaded and the current config has a non-null `audioOutputDeviceId`
- **THEN** the `<select id="output-device-select">` SHALL have the option whose `value`
  matches `config.audioOutputDeviceId` selected; if no match is found (device no longer
  present) the "— No device —" placeholder SHALL be selected

#### Scenario: Settings page shows no output device selected when config value is null

- **WHEN** the output device list has loaded and `config.audioOutputDeviceId` is null
- **THEN** the `<select id="output-device-select">` SHALL have the "— No device —"
  placeholder option selected

#### Scenario: Save action posts audioOutputDeviceId and audioOutputFriendlyName

- **WHEN** the operator selects an output device and clicks Save
- **THEN** the page SHALL `POST /api/v1/config` with a JSON body containing
  `audioOutputDeviceId` (the `value` attribute of the selected output `<option>` or
  `null` if the placeholder is selected) and `audioOutputFriendlyName` (the visible
  text of the selected output `<option>`, or `null` if the placeholder is selected),
  alongside all other config fields

#### Scenario: Save with no output device selected posts null for output device fields

- **WHEN** the operator clicks Save with the output "— No device —" placeholder selected
- **THEN** the POST body SHALL contain `audioOutputDeviceId: null` and `audioOutputFriendlyName: null`

#### Scenario: Output device selector participates in dirty-state tracking

- **WHEN** the operator changes the output device selection
- **THEN** the unsaved-changes indicator SHALL become visible, consistent with the
  behaviour for all other settings controls

#### Scenario: Settings page pre-fills port field

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the page JavaScript SHALL call `GET /api/v1/config` and populate a port `<input>` field with the current `port` value

#### Scenario: Save action posts audioDeviceId and audioDeviceFriendlyName

- **WHEN** the operator clicks the Save button on the Settings page
- **THEN** the page SHALL `POST /api/v1/config` with a JSON body containing `audioDeviceId` (the `value` attribute of the selected `<option>`), `audioDeviceFriendlyName` (the visible text content of the selected `<option>`), and the current port value

#### Scenario: Save with no device selected posts null for both device fields

- **WHEN** the operator clicks Save with no device selected (or the device list was empty)
- **THEN** the POST body SHALL contain `audioDeviceId: null` and `audioDeviceFriendlyName: null`

#### Scenario: Save success shows feedback

- **WHEN** `POST /api/v1/config` returns HTTP 200
- **THEN** the page SHALL display a visible success message to the operator

#### Scenario: Save error shows feedback

- **WHEN** `POST /api/v1/config` returns HTTP 400 or a network error occurs
- **THEN** the page SHALL display a visible error message and SHALL NOT navigate away from the Settings page

#### Scenario: Settings page has navigation back to main page

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the page SHALL contain a visible link that navigates back to `/`

---

### Requirement: WebSocket status client

The main page SHALL maintain a WebSocket connection to `/api/v1/ws` and update the status bar in real time from incoming `status` events. The client SHALL automatically reconnect after disconnection using exponential back-off.

#### Scenario: WebSocket connects on page load

- **WHEN** the main page JavaScript initialises
- **THEN** a WebSocket connection to `/api/v1/ws` SHALL be established within 1 second

#### Scenario: Status bar updates on status event

- **WHEN** the WebSocket receives a `status` event
- **THEN** the status bar SHALL update to reflect the `state` and `audioDevice` fields from the event payload; the `audioDevice` value SHALL be the human-readable device name when available, or the device ID as a fallback, or `"(no device)"` when null

#### Scenario: Status bar shows disconnected state

- **WHEN** the WebSocket connection is lost
- **THEN** the status bar SHALL display a visual indication that the connection is disconnected

#### Scenario: Client reconnects after disconnection

- **WHEN** the WebSocket connection is closed unexpectedly
- **THEN** the client SHALL attempt to reconnect after an initial delay, doubling the delay on each subsequent failure up to a maximum of 30 seconds

---

### Requirement: Settings page — Logging section

The Settings page SHALL contain a "Logging" section that allows the operator to configure all file logging options. The section SHALL be rendered below the existing audio-device and port controls and SHALL participate in the same Save/Cancel flow.

#### Scenario: Logging section is present on the Settings page

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain a section headed "Logging" with controls for: an enable/disable toggle (`fileEnabled`), a directory text input (`directory`), a log-level selector (`fileLogLevel`), a rotation-schedule selector (`rotationSchedule`), a rotation-time input (`rotationTime`), a rotation-day-of-week selector (`rotationDayOfWeek`), and a max-files number input (`maxFiles`)

#### Scenario: Logging controls pre-filled from current config

- **WHEN** the Settings page JavaScript calls `GET /api/v1/config`
- **THEN** each logging control SHALL be populated with the value from `config.logging` (or the default if absent)

#### Scenario: rotationDayOfWeek control is conditionally visible

- **WHEN** `rotationSchedule` is set to any value other than `"weekly"`
- **THEN** the `rotationDayOfWeek` control and its label SHALL be hidden (display:none or equivalent)

- **WHEN** `rotationSchedule` is changed to `"weekly"`
- **THEN** the `rotationDayOfWeek` control SHALL become visible without a page reload

#### Scenario: rotationTime control hidden for session and hourly schedules

- **WHEN** `rotationSchedule` is `"session"` or `"hourly"`
- **THEN** the `rotationTime` control and its label SHALL be hidden

- **WHEN** `rotationSchedule` is changed to `"daily"` or `"weekly"`
- **THEN** the `rotationTime` control SHALL become visible

#### Scenario: Save includes logging config

- **WHEN** the operator changes any logging field and clicks Save
- **THEN** the `POST /api/v1/config` body SHALL include the updated `logging` object alongside the existing audio device and port fields

#### Scenario: Logging section disabled when fileEnabled is false

- **WHEN** the `fileEnabled` toggle is off
- **THEN** the directory, log level, rotation schedule, rotation time, day-of-week, and max-files controls SHALL be visually disabled (greyed out) and SHALL NOT be editable

- **WHEN** the `fileEnabled` toggle is turned on
- **THEN** the dependent controls SHALL become enabled and editable immediately without a page reload

---

### Requirement: Combined decode status/toggle control in status bar

The main page (`index.html`) status bar SHALL include a single `<button id="decode-toggle">`
element that serves as both the decode-pipeline state indicator and the start/stop click target —
replacing the former separate `#decode-badge` display element and `#decode-toggle` button. The
element SHALL render in exactly one of three states, driven by the same `decodingEnabled` and
`audioDevice` status fields as before:

- **Decoding active** (`decodingEnabled: true`): bright-green background style and label text
  **"DECODING"** (all capitals).
- **Decoding stopped** (`decodingEnabled: false`, a device is configured): bright-red background
  style and label text **"Start decoding"** (sentence case — only the initial "S" capitalised).
- **No device configured** (`audioDevice` is `null` or `""`): disabled, neutral/muted style,
  label text **"No device"** — this state takes precedence over the active/stopped styling above,
  matching the former button's disabled-state precedence.

The control SHALL be updated whenever a `status` event, heartbeat event, or a successful response
from `/decode/start` or `/decode/stop` is received — the same update triggers the two predecessor
elements shared.

Clicking the control while in the "DECODING" (active) state SHALL call `POST /api/v1/decode/stop`;
clicking it while in the "Start decoding" (stopped) state SHALL call `POST /api/v1/decode/start`.
The control SHALL NOT be clickable (browser-native `disabled` behaviour) while in the "No device"
state.

#### Scenario: Control shows DECODING and bright green when active

- **WHEN** the `status` event is received with `decodingEnabled: true` and a configured
  `audioDevice`
- **THEN** `#decode-toggle` SHALL have label text "DECODING"
- **AND** SHALL render with the bright-green active style
- **AND** the button SHALL not be disabled

#### Scenario: Control shows Start decoding and bright red when stopped

- **WHEN** the `status` event is received with `decodingEnabled: false` and a configured
  `audioDevice`
- **THEN** `#decode-toggle` SHALL have label text "Start decoding"
- **AND** SHALL render with the bright-red stopped style
- **AND** the button SHALL not be disabled

#### Scenario: Control is disabled when no device is configured

- **WHEN** the `status` event is received with `audioDevice: null` or `audioDevice: ""`
- **THEN** `#decode-toggle` SHALL be disabled
- **AND** the button label SHALL read "No device"
- **AND** neither the active (bright-green) nor stopped (bright-red) style SHALL apply

#### Scenario: Clicking while active calls the stop endpoint

- **WHEN** `#decode-toggle` is clicked while showing "DECODING"
- **THEN** a `POST /api/v1/decode/stop` request SHALL be issued
- **AND** on a 200 response the control SHALL update to "Start decoding" / bright-red

#### Scenario: Clicking while stopped calls the start endpoint

- **WHEN** `#decode-toggle` is clicked while showing "Start decoding"
- **THEN** a `POST /api/v1/decode/start` request SHALL be issued
- **AND** on a 200 response the control SHALL update to "DECODING" / bright-green

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

### Requirement: Settings page — General tab

The Settings page SHALL contain a "General" tab inserted as the **first** tab, before the existing Radio tab. The tab SHALL contain the operator's station-identity and TX behaviour fields: callsign, Maidenhead grid locator, watchdog timer, and retry count. These fields are moved here from the Radio tab's TX fieldset.

The General tab SHALL participate in the same Save / unsaved-changes flow as all other tabs.

#### Scenario: General tab is present and is the first tab

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain a tab button labelled "General" with `aria-controls="tab-general"` and a corresponding tab panel with `id="tab-general"`
- **AND** the General tab button SHALL be the first tab button in the tab list (leftmost in the rendered order)

#### Scenario: General tab is active by default on page load

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the General tab panel SHALL be the initially visible panel and its tab button SHALL have `aria-selected="true"`

#### Scenario: General tab pre-fills callsign from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "callsign": "Q9XYZ", ... } }`
- **THEN** the `<input id="general-callsign">` element SHALL display `Q9XYZ` before the operator edits anything

#### Scenario: General tab pre-fills grid from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "grid": "IO91", ... } }`
- **THEN** the `<input id="general-grid">` element SHALL display `IO91` before the operator edits anything

#### Scenario: General tab pre-fills watchdogMinutes from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "watchdogMinutes": 4, ... } }`
- **THEN** the `<input id="general-watchdog-minutes">` element SHALL display `4` before the operator edits anything

#### Scenario: General tab pre-fills retryCount from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "retryCount": 3, ... } }`
- **THEN** the `<input id="general-retry-count">` element SHALL display `3` before the operator edits anything

#### Scenario: Save includes General tab fields in tx object

- **WHEN** the operator changes any General tab field and clicks Save
- **THEN** `POST /api/v1/config` SHALL include a `tx` object containing the values of `general-callsign`, `general-grid`, `general-watchdog-minutes`, and `general-retry-count`, alongside the `tx.autoAnswer` value read from the Radio tab

#### Scenario: Saving without changes does not trigger clamp warnings

- **WHEN** the operator opens the Settings page, makes no changes, and clicks Save
- **THEN** `POST /api/v1/config` SHALL submit `tx.watchdogMinutes` ≥ 1 and `tx.retryCount` ≥ 1, and the daemon SHALL NOT log a WRN clamp message

#### Scenario: General tab fields participate in dirty-state tracking

- **WHEN** the operator changes any field in the General tab
- **THEN** the unsaved-changes indicator SHALL become visible, consistent with the behaviour for all other settings controls

---

### Requirement: Hold TX Freq checkbox on main page

The main page SHALL include a `<label>` containing an `<input type="checkbox" id="hold-tx-freq">` element positioned near the waterfall display. The checkbox SHALL reflect the current `holdTxFreq` state received from the `status` or `audioOffset` WebSocket events. When the operator toggles the checkbox, the page SHALL immediately call `POST /api/v1/audio-offset` with the updated `holdTxFreq` value alongside the current `rxHz` and `txHz`.

#### Scenario: Checkbox reflects initial state from status event

- **WHEN** the main page receives a `status` WebSocket event with `holdTxFreq: true`
- **THEN** `#hold-tx-freq` SHALL be checked

#### Scenario: Checkbox reflects initial state false

- **WHEN** the main page receives a `status` WebSocket event with `holdTxFreq: false`
- **THEN** `#hold-tx-freq` SHALL be unchecked

#### Scenario: Toggling checkbox calls audio-offset endpoint

- **WHEN** the operator checks `#hold-tx-freq` while `rxHz = 1500` and `txHz = 1500`
- **THEN** `POST /api/v1/audio-offset` SHALL be called with `{"rxHz": 1500, "txHz": 1500, "holdTxFreq": true}`

---

### Requirement: Main page handles audioOffset WebSocket event

The main page WebSocket handler SHALL process `audioOffset` events and update the cursor lines, numeric readouts, and Hold TX Freq checkbox to reflect the new values. This ensures that when the QSO answerer auto-updates the TX cursor (Hold TX = OFF, CQ answered), all browser tabs update without requiring a page reload.

#### Scenario: audioOffset event updates TX cursor and readout

- **WHEN** the main page receives an `audioOffset` event with `{"rxHz": 900, "txHz": 1234, "holdTxFreq": false}`
- **THEN** the waterfall TX cursor line SHALL move to 1234 Hz
- **AND** `#tx-freq-display` SHALL show `1234 Hz`
- **AND** `#hold-tx-freq` SHALL be unchecked

#### Scenario: audioOffset event updates RX cursor and readout

- **WHEN** the main page receives an `audioOffset` event with `{"rxHz": 750, "txHz": 1500, "holdTxFreq": false}`
- **THEN** the waterfall RX cursor line SHALL move to 750 Hz
- **AND** `#rx-freq-display` SHALL show `750 Hz`

---

### Requirement: Settings page — TX fieldset on Radio tab

The Radio tab SHALL contain an "FT8 TX" fieldset containing **only** the auto-answer enable/disable checkbox (`id="tx-auto-answer"`). The callsign, grid, watchdog minutes, and retry count fields have been moved to the General tab and SHALL NOT appear in the TX fieldset.

The TX fieldset legend SHALL read "FT8 TX".

#### Scenario: TX fieldset contains only the auto-answer checkbox

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the TX fieldset (`id="tx-settings"`) SHALL contain a `<input type="checkbox" id="tx-auto-answer">` element
- **AND** the TX fieldset SHALL NOT contain inputs with IDs `tx-callsign`, `tx-grid`, `tx-watchdog-minutes`, or `tx-retry-count`

#### Scenario: Auto-answer checkbox pre-fills from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "autoAnswer": true, ... } }`
- **THEN** the `<input id="tx-auto-answer">` checkbox SHALL be checked

#### Scenario: Save includes autoAnswer from Radio tab

- **WHEN** the operator changes the auto-answer checkbox and clicks Save
- **THEN** `POST /api/v1/config` SHALL include `tx.autoAnswer` reflecting the current checkbox state, alongside the General tab's callsign, grid, watchdog, and retry fields

---

### Requirement: TX panel — layout alongside decoded-messages panel

The main page SHALL be restructured so that the area below the waterfall controls
contains a horizontal flex row with two panels:

- `#decodes-panel` — existing decoded-messages table; `flex: 1 1 0` (grows to fill)
- `#tx-panel` — new TX control panel; `flex: 0 0 320px` (fixed width, right-hand side)

Both panels SHALL fill the full height of the content area below the waterfall controls.
The `#tx-panel` SHALL be always rendered and visible regardless of TX configuration state.
A wrapper `<div id="content-row">` SHALL enclose both panels and be the flex-row container.

#### Scenario: TX panel is present on the main page at all times

- **WHEN** a browser loads `GET /`
- **THEN** the DOM SHALL contain `<div id="tx-panel">` as a sibling of `#decodes-panel`
  inside `#content-row`

#### Scenario: Panels are side-by-side

- **WHEN** a browser loads `GET /` on a desktop-width viewport
- **THEN** `#decodes-panel` and `#tx-panel` SHALL be rendered in the same horizontal row
  (computed `display` value is consistent with a flex-row container)

---

### Requirement: TX panel — Enable TX toggle button

The TX panel SHALL contain a single `<button id="tx-enable-btn">` that reflects and
controls the `tx.autoAnswer` state:

- **Disarmed** (`autoAnswer = false`): label reads **"Enable TX"**; standard neutral
  button styling.
- **Armed** (`autoAnswer = true`): label reads **"Enable TX"** (label does not change);
  the button SHALL have a visually alarming style (red/danger background, bold weight)
  so the operator cannot overlook that autonomous transmission is active. The label is
  intentionally kept as "Enable TX" in both states; a visually alarming colour alone
  signals the armed condition (D-TX-UI-002 — UAT decision 2026-06-22). The specific
  armed-state colour — dark red when not currently transmitting, bright red when the
  `txState` payload's `state` is one of the transmitting `Tx*` sub-states — is governed
  by the `tx-state-indicators` capability; this requirement establishes only that an
  armed style distinct from the disarmed style SHALL always be present.

Clicking the button in the disarmed state SHALL call `POST /api/v1/tx/enable` and
apply an armed CSS class on HTTP 200. Clicking in the armed state SHALL call
`POST /api/v1/tx/disable` and remove all armed CSS classes on HTTP 200. The button
SHALL be disabled for the duration of the pending request.

#### Scenario: Button shows Enable TX and is disarmed when autoAnswer is false

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: false`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL NOT have the `tx-btn-armed` or `tx-btn-transmitting` CSS class

#### Scenario: Button shows Enable TX with armed style when autoAnswer is true

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: true`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL have an armed CSS class applied (`tx-btn-armed` or `tx-btn-transmitting`,
  per the `state` value — see `tx-state-indicators`)

#### Scenario: Clicking Enable TX (disarmed) calls /tx/enable and applies armed style

- **WHEN** `#tx-enable-btn` is clicked while in the disarmed state
- **THEN** `POST /api/v1/tx/enable` SHALL be called
- **AND** on HTTP 200, an armed CSS class SHALL be applied; label remains "Enable TX"

#### Scenario: Clicking Enable TX (armed) calls /tx/disable and removes armed style

- **WHEN** `#tx-enable-btn` is clicked while in the armed state
- **THEN** `POST /api/v1/tx/disable` SHALL be called
- **AND** on HTTP 200, all armed CSS classes SHALL be removed; label remains "Enable TX"

#### Scenario: Button is disabled during pending request

- **WHEN** a click on `#tx-enable-btn` triggers a request that has not yet resolved
- **THEN** `#tx-enable-btn` SHALL be `disabled` until the response (success or error) is
  received

---

### Requirement: TX panel — Call CQ button

The TX panel SHALL contain a single `<button id="tx-call-cq-btn">` whose label, enabled state, and
click action are all derived from the existing `role` and `state` fields (no additional
server-side signal beyond the new `POST /api/v1/tx/stop-cq` endpoint described below):

| Condition | Enabled? | Label | Click action |
|---|---|---|---|
| `role !== "caller"` and `state === "Idle"` | Enabled | "Call CQ" | `POST /api/v1/tx/call-cq` (existing) |
| `role === "caller"` and `state !== "Idle"` | Enabled | "Stop CQ" | `POST /api/v1/tx/stop-cq` (new) |
| `role !== "caller"` and `state !== "Idle"` (answerer mid-QSO) | Disabled | "Call CQ" | — |

This SHALL supersede the button's previous informal gating (`disabled` whenever `state !== "Idle"`,
undocumented as a formal requirement prior to this change) — the button is no longer unconditionally
disabled for the whole non-`Idle` duration of a caller session; while `role === "caller"` it remains
enabled throughout, so the operator can always stop a session in progress.

A "Stop CQ" click requests a **graceful stop**, distinct from the always-available `Abort TX`
button: any TX sample already in flight plays to completion (no audio interruption), and the
service returns to `Idle` only once it reaches its next natural wait point. The click handler
SHALL NOT re-render the panel from the `POST /api/v1/tx/stop-cq` response directly — the panel
SHALL update once the subsequent `txState` WebSocket event carrying `state: "Idle"` arrives,
consistent with how `Abort TX` is already handled.

This button's bright-green "engaged" colour while `role === "caller" && autoAnswerEnabled` is
governed by the `tx-state-indicators` capability, independently of the enabled/label/click
behaviour specified here.

#### Scenario: Idle button starts a CQ session

- **WHEN** `state` is `"Idle"` (any role)
- **THEN** `#tx-call-cq-btn` SHALL be enabled with label "Call CQ"
- **AND** clicking it SHALL call `POST /api/v1/tx/call-cq`

#### Scenario: Engaged caller button offers a graceful stop

- **WHEN** `role` is `"caller"` and `state` is any non-`"Idle"` value (e.g. `"TxCq"`,
  `"WaitAnswer"`, `"TxReport"`, `"WaitRr73"`, `"TxRr73"`, `"QsoComplete"`)
- **THEN** `#tx-call-cq-btn` SHALL be enabled with label "Stop CQ"
- **AND** clicking it SHALL call `POST /api/v1/tx/stop-cq`, not `POST /api/v1/tx/abort`

#### Scenario: Answerer mid-QSO disables the button

- **WHEN** `role` is `"answerer"` and `state` is not `"Idle"`
- **THEN** `#tx-call-cq-btn` SHALL be disabled with label "Call CQ"

#### Scenario: Stop CQ click does not immediately re-render the panel

- **WHEN** the operator clicks "Stop CQ" and `POST /api/v1/tx/stop-cq` returns HTTP 200 with a
  non-`"Idle"` `state` (TX still completing)
- **THEN** the TX panel SHALL NOT be forced to the `Idle`/disarmed appearance from that response
  alone
- **AND** the panel SHALL update to `Idle` only when a subsequent `txState` WebSocket event with
  `state: "Idle"` is received

#### Scenario: Clicking Stop CQ twice in quick succession is idempotent

- **WHEN** `POST /api/v1/tx/stop-cq` is sent twice in immediate succession for the same session
- **THEN** neither call SHALL error, and the service SHALL still reach `Idle` exactly once, at the
  same point it would have from a single request

---

### Requirement: TX panel — Abort TX button

The TX panel SHALL contain a `<button id="tx-abort-btn">` labelled **"Abort TX"**.
Clicking it SHALL call `POST /api/v1/tx/abort`. The button SHALL always be present and
enabled regardless of TX state (it is a safety control; disabling it would defeat its
purpose). The button SHALL be disabled for the duration of the pending request.

`POST /api/v1/tx/abort` returns a `TxStatusResponse` JSON body (HTTP 200). On receipt,
the frontend SHALL call `renderTxPanel` immediately with `autoAnswerEnabled: false` to
disarm the button without waiting for a subsequent `txState` WebSocket event
(D-TX-UI-001 — supervised single-QSO model, UAT decision 2026-06-22).

#### Scenario: Abort TX button is always present and enabled

- **WHEN** a browser loads `GET /` and the TX state is `Idle`
- **THEN** `#tx-abort-btn` SHALL be present in the DOM and SHALL NOT be `disabled`

#### Scenario: Clicking Abort TX calls the abort endpoint and disarms the panel

- **WHEN** `#tx-abort-btn` is clicked
- **THEN** `POST /api/v1/tx/abort` SHALL be called
- **AND** on HTTP 200 the TX panel SHALL update to the disarmed / Idle appearance
  immediately (the `tx-btn-armed` class SHALL be removed from `#tx-enable-btn`)
- **AND** `#tx-abort-btn` SHALL be re-enabled

---

### Requirement: TX panel — state and partner status display

The TX panel SHALL contain a `<span id="tx-state-display">` that shows the current QSO
controller state in a human-readable form:

- `Idle` state: shows **"Idle"** with muted styling
- Any non-Idle state: shows **"Working \<callsign\>"** (e.g. `Working Q2XYZ`) with
  prominent/accent styling

The display SHALL update on every `txState` WebSocket event.

#### Scenario: Display shows Idle at startup

- **WHEN** the page loads and the initial TX status is `Idle`
- **THEN** `#tx-state-display` SHALL contain the text "Idle"

#### Scenario: Display updates to Working on txState event

- **WHEN** a `txState` event is received with `{ "state": "TxAnswer", "partner": "Q2XYZ" }`
- **THEN** `#tx-state-display` SHALL contain the text "Working Q2XYZ"

#### Scenario: Display reverts to Idle on txState Idle event

- **WHEN** a `txState` event is received with `{ "state": "Idle", "partner": null }`
- **THEN** `#tx-state-display` SHALL contain the text "Idle"

---

### Requirement: TX panel — standard message rows

The TX panel SHALL display three message rows, identified by `id` attributes
`tx-msg-1`, `tx-msg-2`, and `tx-msg-3`, each containing a read-only text representation
of the standard FT8 message for that slot:

| Row  | Message template                         | Active QSO state(s)         |
|------|------------------------------------------|-----------------------------|
| Tx 1 | `{partner} {callsign} {grid}`            | `TxAnswer`                  |
| Tx 2 | `{partner} {callsign} R+00`              | `TxReport`                  |
| Tx 3 | `{partner} {callsign} 73`                | `Tx73`                      |

Values for `{callsign}` and `{grid}` SHALL be read from `config.tx.callsign` and
`config.tx.grid` obtained via `GET /api/v1/config` on page load. The `{partner}` token
SHALL be populated from the `partner` field of the most recent `txState` WebSocket event.

When `State == Idle` (partner is `null`), the partner slot SHALL be rendered as `———`
(three em-dashes) so the row still previews the operator's own callsign and grid.

**Active row highlighting:** When the current `txState.state` matches a row's active
states, that row SHALL receive the CSS class `tx-msg-active` and be rendered with an
accent colour. All other rows SHALL have muted styling.

**Greyed-out when disarmed:** When `autoAnswer` is `false`, all three rows SHALL receive
the CSS class `tx-msg-muted` (greyed/dimmed). When `autoAnswer` becomes `true`, the
`tx-msg-muted` class SHALL be removed.

#### Scenario: Message rows show operator callsign and grid in Idle state

- **WHEN** the page loads with `config.tx.callsign = "Q1OFZ"`, `config.tx.grid = "JO33"`,
  and the TX state is `Idle`
- **THEN** `#tx-msg-1` SHALL display text matching `——— Q1OFZ JO33`
- **AND** `#tx-msg-2` SHALL display text matching `——— Q1OFZ R+00`
- **AND** `#tx-msg-3` SHALL display text matching `——— Q1OFZ 73`

#### Scenario: Message rows populate partner on active QSO

- **WHEN** a `txState` event is received with `partner: "Q2XYZ"`
- **THEN** `#tx-msg-1` SHALL display `Q2XYZ Q1OFZ JO33`
- **AND** `#tx-msg-2` SHALL display `Q2XYZ Q1OFZ R+00`
- **AND** `#tx-msg-3` SHALL display `Q2XYZ Q1OFZ 73`

#### Scenario: Active row is highlighted during TxAnswer

- **WHEN** a `txState` event is received with `state: "TxAnswer"`
- **THEN** `#tx-msg-1` SHALL have CSS class `tx-msg-active`
- **AND** `#tx-msg-2` and `#tx-msg-3` SHALL NOT have `tx-msg-active`

#### Scenario: Active row is highlighted during TxReport

- **WHEN** a `txState` event is received with `state: "TxReport"`
- **THEN** `#tx-msg-2` SHALL have CSS class `tx-msg-active`

#### Scenario: Active row is highlighted during Tx73

- **WHEN** a `txState` event is received with `state: "TxReport"`
- **THEN** `#tx-msg-3` SHALL have CSS class `tx-msg-active`

#### Scenario: No row highlighted in wait states

- **WHEN** a `txState` event is received with `state: "WaitReport"` or `"WaitRr73"`
- **THEN** no row SHALL have CSS class `tx-msg-active`

#### Scenario: Message rows greyed out when TX is disarmed

- **WHEN** `autoAnswerEnabled` is `false`
- **THEN** `#tx-msg-1`, `#tx-msg-2`, and `#tx-msg-3` SHALL each have CSS class
  `tx-msg-muted`

#### Scenario: Message rows normal when TX is armed

- **WHEN** `autoAnswerEnabled` is `true`
- **THEN** none of `#tx-msg-1`, `#tx-msg-2`, `#tx-msg-3` SHALL have CSS class
  `tx-msg-muted`

---

### Requirement: TX panel — QSO Transcript section

The TX panel SHALL contain a **QSO Transcript** section, occupying the same DOM location
previously used by the "TX History" abort-reason list (`FR-062`, superseding the unspecified
`FR-UX-002` abort-only behaviour), rendered as `<ol id="tx-transcript-log">` inside
`<div id="tx-transcript-section">`. The section SHALL remain hidden until its first entry is
appended, exactly as the prior TX History section did.

The section SHALL record, as a single unified, newest-on-top, chronological list:

1. **Sent** entries — every standard FT8 message the operator's own station actually transmits.
2. **Received** entries — every decoded message belonging to the operator's own tracked
   conversation (matched by callsign token against the operator's own callsign or the active
   partner), sourced from the raw `decode` WebSocket feed **before** any `decode-panel-filtering`
   column-filter or `decode-noise-suppression` gating is applied to it.
3. **Abort** entries — an abort reason string, exactly as previously produced by `FR-UX-002`,
   now folded inline into this same list instead of a separate one.
4. **Partner-change** entries — a separator noting the tracked partner has changed, whenever
   `currentTxPartner` transitions to a new non-null value from a different previous value.

The list SHALL be capped at 100 entries; when a new entry would exceed the cap, the oldest
entry SHALL be dropped.

Sent and received entries SHALL be visually distinguished by direction: sent entries SHALL carry
CSS class `transcript-sent`; received entries SHALL carry CSS class `transcript-received`. Abort
and partner-change entries SHALL carry CSS class `transcript-event` and SHALL NOT be colorized
by direction.

#### Scenario: Section is hidden until first entry

- **WHEN** the page loads and no transcript entry has yet been recorded
- **THEN** `#tx-transcript-section` SHALL be `hidden`

#### Scenario: Sent message is recorded once per transmission step, using the real transmitted text when available

- **WHEN** a `txState` event is received with `state: "TxAnswer"`, the previous state was
  `"Idle"` (answerer role), and the event's `lastTxMessage` field is `"Q2XYZ Q1OFZ JO33"`
- **THEN** exactly one new entry with CSS class `transcript-sent` SHALL be appended to
  `#tx-transcript-log`, containing that real `lastTxMessage` text (`fix-tx-transcript-real-message`
  — previously this entry always contained the per-state template text regardless of what was
  actually transmitted; see the new "TX panel message rows prefer the real transmitted message
  over the template" requirement for the fallback behaviour when `lastTxMessage` is absent)

#### Scenario: Repeated push of the same state does not duplicate the entry

- **WHEN** two consecutive `txState` events are received both carrying `state: "TxAnswer"` with
  no state change in between
- **THEN** only one `transcript-sent` entry for that transmission step SHALL exist in
  `#tx-transcript-log`

#### Scenario: A retried transmission is logged again

- **WHEN** the state machine re-enters `"TxReport"` after having left it for `"WaitRr73"` and
  timing out back to `"TxReport"` (a retry)
- **THEN** a second `transcript-sent` entry for the report message SHALL be appended, distinct
  from the first

#### Scenario: Received message from the tracked partner is recorded even when column-filtered

- **WHEN** a `decode` WebSocket event arrives whose message tokens include the active partner's
  callsign, and the current `decode-panel-filtering` column filter would hide that decode's row
  in `#decodes-table` (`tr.hidden === true`)
- **THEN** a `transcript-received` entry for that message SHALL still be appended to
  `#tx-transcript-log`

#### Scenario: Unrelated traffic is not recorded

- **WHEN** a `decode` WebSocket event arrives whose message tokens include neither the operator's
  own callsign nor the active partner's callsign
- **THEN** no entry SHALL be appended to `#tx-transcript-log` for that decode

#### Scenario: Partner change appends a separator entry

- **WHEN** `currentTxPartner` changes from `"Q2XYZ"` to `"Q3ABC"`
- **THEN** a `transcript-event` separator entry noting the new partner SHALL be appended before
  any further `transcript-sent`/`transcript-received` entries for `"Q3ABC"`

#### Scenario: Abort reason appears inline in the transcript

- **WHEN** the daemon reports a `txState` event transitioning to `"Idle"` with a non-null
  `abortReason`
- **THEN** a `transcript-event` entry containing that reason SHALL be appended to
  `#tx-transcript-log`, in chronological order alongside any sent/received entries for that QSO

#### Scenario: List is capped at 100 entries

- **WHEN** a 101st transcript entry (of any kind) is appended
- **THEN** the oldest entry SHALL be removed from `#tx-transcript-log`, leaving exactly 100

---

### Requirement: Main page handles txState WebSocket event

The main page WebSocket handler SHALL process `txState` events (previously unhandled)
and update the TX panel accordingly. A `txState` event carries:
- `state` — the new `QsoState` as a string
- `partner` — the active partner callsign, or `null`
- `autoAnswerEnabled` — the current armed/disarmed state (added for D-TX-UI-003,
  2026-06-22; allows QSO completion and abort to disarm the panel without a separate
  HTTP call)
- `lastTxMessage` — the real text of the most recently transmitted message, or `null` if
  nothing has been transmitted yet this process lifetime (`fix-tx-transcript-real-message`)

Wire format example (active state):
`{"type":"txState","state":"TxAnswer","partner":"Q2XYZ","autoAnswerEnabled":true,"lastTxMessage":"Q2XYZ Q1OFZ JO33"}`

Wire format example (idle / disarmed):
`{"type":"txState","state":"Idle","partner":null,"autoAnswerEnabled":false,"lastTxMessage":null}`

The frontend SHALL read `autoAnswerEnabled` from the event and pass it to `renderTxPanel`.
If the field is absent (forward-compatibility), the frontend SHALL fall back to the last
known local `currentAutoAnswerEnabled` value.

#### Scenario: txState event updates state display and message rows

- **WHEN** the WebSocket receives `{ "type": "txState", "state": "WaitReport", "partner": "Q2XYZ", "autoAnswerEnabled": true }`
- **THEN** `#tx-state-display` SHALL update to "Working Q2XYZ"
- **AND** no message row SHALL have the `tx-msg-active` class (wait state — no row active)
- **AND** all message rows SHALL show `Q2XYZ` as the partner token

#### Scenario: Idle txState event disarms the panel (D-TX-UI-003)

- **WHEN** the WebSocket receives `{ "type": "txState", "state": "Idle", "partner": null, "autoAnswerEnabled": false }`
- **THEN** `#tx-enable-btn` SHALL NOT have the `tx-btn-armed` class
- **AND** `#tx-state-display` SHALL show "Idle"
- **AND** all message rows SHALL have the `tx-msg-muted` class

#### Scenario: Missing lastTxMessage field is forward-compatible

- **WHEN** a `txState` event has no `lastTxMessage` field (older cached backend, or a state prior
  to this change)
- **THEN** the frontend SHALL treat this identically to `lastTxMessage: null` — message rows fall
  back to the per-state template exactly as they did before this change

---

### Requirement: TX panel message rows prefer the real transmitted message over the template

Once a `txState` event's `lastTxMessage` field is non-null, the frontend SHALL remember it against
the row corresponding to the state that was active at the moment it arrived (the same
transition-into-active-state moment `hasEnteredNewActiveTxState` already detects). For each of
`#tx-msg-1`/`#tx-msg-2`/`#tx-msg-3`, rendering SHALL use that remembered real text if one has been
recorded for that row this tracked QSO, and SHALL fall back to the existing per-state/per-role
template (`TX panel — standard message rows`, `TX panel message rows are role-aware`) only for a
row that has not yet had a real message recorded.

The remembered real text for all three rows SHALL be cleared whenever `currentTxPartner` changes to
a different non-null value, or the state returns to `Idle` — consistent with how `currentTxPartner`
itself is already reset at those points — so a previous QSO's real text SHALL NOT leak into a new
QSO's row display before that new QSO has transmitted anything of its own.

#### Scenario: A row shows its real transmitted text once available

- **WHEN** a `txState` event transitions into `"TxReport"` with `lastTxMessage: "Q2XYZ Q1OFZ -07"`
- **THEN** `#tx-msg-2` SHALL display `"Q2XYZ Q1OFZ -07"`, not the template `"Q2XYZ Q1OFZ R+00"`

#### Scenario: A row not yet transmitted still shows the template

- **WHEN** the current QSO has transmitted `#tx-msg-1` (with a real recorded message) but has not
  yet reached `TxReport`
- **THEN** `#tx-msg-2` SHALL still display its per-state/per-role template text, since no real
  message has been recorded for that row yet

#### Scenario: A row keeps showing its real text after the QSO advances past it

- **WHEN** `#tx-msg-2` has recorded real text `"Q2XYZ Q1OFZ -07"` and the state subsequently
  advances to `"WaitRr73"` and then `"TxRr73"`
- **THEN** `#tx-msg-2` SHALL continue to display `"Q2XYZ Q1OFZ -07"` (not revert to the template),
  even though the backend's `LastTxMessage` field itself has since moved on to the row 3 text

#### Scenario: Real text is cleared when the tracked partner changes

- **WHEN** `#tx-msg-2` has recorded real text from a QSO with `"Q2XYZ"`, and `currentTxPartner`
  then changes to `"Q3ABC"`
- **THEN** `#tx-msg-2` SHALL revert to showing its template text (with the new partner token) until
  a real message is recorded for that row in the new QSO

#### Scenario: Real text is cleared on return to Idle

- **WHEN** the state returns to `"Idle"` after a completed or aborted QSO
- **THEN** all three rows' remembered real text SHALL be cleared

---

### Requirement: Main page fetches initial TX status on load

On page load (inside `DOMContentLoaded`), the main page JavaScript SHALL call
`GET /api/v1/tx/status` to seed the TX panel with the current `state`, `partner`, and
`autoAnswerEnabled` before the first `txState` WebSocket event arrives.

#### Scenario: Panel is seeded from GET /api/v1/tx/status on load

- **WHEN** the main page is loaded and `GET /api/v1/tx/status` returns
  `{ "state": "Idle", "partner": null, "autoAnswerEnabled": false }`
- **THEN** `#tx-enable-btn` SHALL show "Enable TX" without the `tx-btn-armed` class (disarmed style)
- **AND** `#tx-state-display` SHALL show "Idle"
- **AND** message rows SHALL be greyed out (`tx-msg-muted`)

#### Scenario: TX status fetch failure is non-fatal

- **WHEN** `GET /api/v1/tx/status` fails (network error or non-200 response) on page load
- **THEN** the TX panel SHALL remain visible with default disarmed / Idle appearance
- **AND** no unhandled exception or console error stack SHALL prevent subsequent
  WebSocket operation

---

### Requirement: Decode table — CQ row highlighting

Decode table rows whose message text begins with `"CQ "` SHALL receive the CSS class
`decode-cq`. The styling SHALL use a visually distinct warm accent colour that draws the
operator's attention to stations calling CQ without overwhelming the table. The class
SHALL be applied at row-creation time when the decode row is rendered.

#### Scenario: CQ message row receives decode-cq class

- **WHEN** a decode with message `"CQ Q1ABC JO33"` is rendered in the decode table
- **THEN** the corresponding table row SHALL have CSS class `decode-cq`

#### Scenario: Non-CQ message row does not receive decode-cq class

- **WHEN** a decode with message `"Q1ABC Q2XYZ +05"` is rendered in the decode table
- **THEN** the corresponding table row SHALL NOT have CSS class `decode-cq`

---

### Requirement: Decode table — clickable CQ rows (TX-D01)

CQ decode table rows SHALL be clickable, and SHALL require a double-click (not a single
click) to arm TX. Double-clicking a CQ row while the TX controller is `Idle` SHALL:

1. Extract the partner callsign, audio frequency offset, and CQ cycle start time from
   the decode row.
2. Call `POST /api/v1/tx/answer-cq` with `{ callsign, frequencyHz, cqCycleStartUtc }`.
3. On HTTP 200: call `renderTxPanel` with the returned status (system is now armed and
   waiting for the correct FT8 answer phase; TX fires within 0–30 s at most).
4. On HTTP 409 (controller not Idle): log a console warning; no UI change.
5. On other error: log to console; no UI change.

A single click on a CQ row SHALL have no effect — it SHALL NOT call
`POST /api/v1/tx/answer-cq` and SHALL NOT change TX controller state. The row SHALL
still render its existing hover/cursor affordance (`.decode-cq:hover`, `cursor: pointer`)
so it continues to read as an interactive element; discoverability of the double-click
requirement is via that affordance and operator documentation, not an in-app prompt.

**Callsign extraction** from the CQ message:
- 3-token CQ (`CQ callsign grid`): token at index 1
- 4-token CQ (`CQ modifier callsign grid`): token at index 2

**Frequency:** the `offsetHz` value of the decode row (the audio frequency in Hz at
which the signal was detected).

**`cqCycleStartUtc`:** the UTC cycle-start timestamp of the decode row, formatted as an
ISO 8601 string (e.g. `"2026-06-22T17:29:15Z"`). The decode row's timestamp column
contains this value; the frontend SHALL parse it from the row data at render time and
store it as a data attribute or in a closure for retrieval when the row is double-clicked.

Decode row timestamp format: `YYMMDD_HHMMSS` (UTC). Parsing:
```javascript
function parseFt8CycleStartUtc(ft8Ts) {
  // ft8Ts example: "260622_172915"
  const [date, time] = ft8Ts.split('_');
  return `20${date.slice(0,2)}-${date.slice(2,4)}-${date.slice(4,6)}` +
         `T${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}Z`;
}
```

Double-clicking a CQ row while the controller is NOT Idle SHALL have no effect (the
double-click is silently ignored; a 409 response is swallowed with a console warning).

#### Scenario: Double-clicking a CQ row calls answer-cq with phase info and arms the TX panel

- **WHEN** the controller is `Idle` and the operator double-clicks a CQ row with
  message `"CQ Q1ABC JO33"`, `offsetHz = 1500`, and row timestamp `"260622_172915"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "cqCycleStartUtc": "2026-06-22T17:29:15Z" }`
- **AND** on HTTP 200 the TX panel SHALL update to the armed appearance

#### Scenario: A single click on a CQ row does not arm TX

- **WHEN** the controller is `Idle` and the operator clicks (once, not followed by a
  second click) a CQ row with message `"CQ Q1ABC JO33"`
- **THEN** no `POST /api/v1/tx/answer-cq` request SHALL be sent
- **AND** the TX controller state SHALL remain unchanged

#### Scenario: Double-clicking a 4-token CQ row extracts the callsign correctly

- **WHEN** the operator double-clicks a CQ row with message `"CQ DX Q9XYZ FN42"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with `callsign = "Q9XYZ"`

#### Scenario: Double-clicking a CQ row when not Idle has no effect

- **WHEN** the controller state is `TxAnswer` (active QSO) and the operator
  double-clicks a CQ row
- **THEN** no `POST /api/v1/tx/answer-cq` request SHALL be sent
  (or the resulting 409 SHALL be silently swallowed)

---

### Requirement: Decode table — partner interaction highlighting

Decode table rows that are part of the active QSO exchange SHALL receive the CSS class
`decode-partner`. The styling SHALL use a subdued red colour that is clearly readable
but not harsh (e.g. a muted rose or dark salmon; specific shade is a developer
decision within the constraint of legibility).

A row is "part of the active QSO exchange" if and only if:
- `currentTxPartner` is not `null`, **AND**
- The message contains the operator's callsign (from `config.tx.callsign`) as a
  space-delimited token, **AND**
- The message contains the partner's callsign (from `currentTxPartner`) as a
  space-delimited token.

A token matches a callsign if the token equals the callsign exactly, **OR** the token
equals the callsign followed by `/` and one or more suffix characters (e.g. token
`PD2FZ/P` matches callsign `PD2FZ`).

The class SHALL be applied or removed when each decode row is created. Rows rendered
while no QSO is active (partner is null) SHALL NOT have `decode-partner`.

Note: rows from a previous QSO that are already in the table are not retroactively
reclassified when the partner changes. Only newly rendered rows are evaluated.

#### Scenario: QSO exchange row receives decode-partner class

- **WHEN** `currentTxPartner = "Q1ABC"`, `txCallsign = "Q9XYZ"`, and a decode with
  message `"Q1ABC Q9XYZ +05"` is rendered
- **THEN** the row SHALL have CSS class `decode-partner`

#### Scenario: Third-party message does not receive decode-partner class

- **WHEN** `currentTxPartner = "Q1ABC"`, `txCallsign = "Q9XYZ"`, and a decode with
  message `"Q2OTHER Q1ABC +12"` is rendered (partner present, operator's callsign absent)
- **THEN** the row SHALL NOT have CSS class `decode-partner`

#### Scenario: CQ row does not receive decode-partner class

- **WHEN** `currentTxPartner = "Q1ABC"` and a decode with message `"CQ Q1ABC JO33"`
  is rendered
- **THEN** the row SHALL NOT have CSS class `decode-partner`
  (operator's callsign is not present in the message)

#### Scenario: Partner suffix variant is matched

- **WHEN** `currentTxPartner = "Q1ABC"`, `txCallsign = "Q9XYZ/P"`, and a decode with
  message `"Q1ABC Q9XYZ/P RR73"` is rendered
- **THEN** the row SHALL have CSS class `decode-partner`
  (token `Q9XYZ/P` matches callsign `Q9XYZ/P` exactly)

---

### Requirement: TX panel message rows are role-aware

The TX panel message rows (`#tx-msg-1`, `#tx-msg-2`, `#tx-msg-3`) SHALL render
different content templates depending on the `role` field of the most recent `txState`
WebSocket event (or the `role` field from the initial `GET /api/v1/tx/status` response).

| Row  | Answerer template               | Caller template                |
|------|---------------------------------|--------------------------------|
| Tx 1 | `{partner} {callsign} {grid}`   | `CQ {callsign} {grid}`         |
| Tx 2 | `{partner} {callsign} R+00`     | `{partner} {callsign} +00`     |
| Tx 3 | `{partner} {callsign} 73`       | `{partner} {callsign} RR73`    |

The `{partner}` placeholder uses three em-dashes (`———`) when `partner` is `null`
(Idle state), consistent with the existing answerer behaviour.

Active-row state mapping SHALL be role-specific:

| State (Answerer) | Active row | State (Caller) | Active row |
|------------------|-----------|----------------|-----------|
| `TxAnswer`       | Tx 1      | `TxCq`         | Tx 1      |
| `TxReport`       | Tx 2      | `TxReport`     | Tx 2      |
| `Tx73`           | Tx 3      | `TxRr73`       | Tx 3      |

All other states (wait states, `Idle`) → no row highlighted.

The frontend SHALL default to `"answerer"` role rendering when the `role` field is
absent from a `txState` event (forward-compatibility).

#### Scenario: Caller role — Tx 1 shows CQ template in Idle state

- **WHEN** the active role is `Caller`, `callsign = "PD2FZ"`, `grid = "JO33"`, and
  the state is `Idle`
- **THEN** `#tx-msg-1` SHALL display `"CQ PD2FZ JO33"`
- **AND** `#tx-msg-2` SHALL display `"——— PD2FZ +00"`
- **AND** `#tx-msg-3` SHALL display `"——— PD2FZ RR73"`

#### Scenario: Caller role — Tx 1 highlighted during TxCq

- **WHEN** the `txState` event contains `role: "caller"` and `state: "TxCq"`
- **THEN** `#tx-msg-1` SHALL have CSS class `tx-msg-active`
- **AND** `#tx-msg-2` and `#tx-msg-3` SHALL NOT have `tx-msg-active`

#### Scenario: Caller role — Tx 3 shows partner and RR73 during WaitRr73

- **WHEN** the `txState` event contains `role: "caller"`, `state: "WaitRr73"`,
  and `partner: "Q1ABC"`
- **THEN** `#tx-msg-3` SHALL display `"Q1ABC PD2FZ RR73"`
- **AND** no row SHALL have `tx-msg-active` (wait state)

#### Scenario: Missing role field defaults to answerer rendering

- **WHEN** a `txState` event has no `role` field
- **THEN** the frontend SHALL render message rows using the answerer templates

---

### Requirement: Settings page — TX Mode selector

The Settings page General tab SHALL include a **TX Mode** control allowing the
operator to select between `Answerer` and `Caller` roles. The control SHALL be a
`<select id="general-tx-role">` element with two `<option>` elements:
- `value="Answerer"`: "Answerer (respond to CQ)"
- `value="Caller"`: "Caller (call CQ)"

The control SHALL be pre-populated from `config.tx.role` on page load. Changing the
value SHALL mark the form dirty (unsaved-changes indicator). Saving SHALL include
`tx.role` in the `POST /api/v1/config` payload.

#### Scenario: TX Mode selector pre-fills from config

- **WHEN** `GET /api/v1/config` returns `{ "tx": { "role": "Answerer" } }`
- **THEN** `#general-tx-role` SHALL have `"Answerer"` selected

#### Scenario: TX Mode selector change marks form dirty

- **WHEN** the operator changes `#general-tx-role`
- **THEN** the unsaved-changes indicator SHALL become visible

#### Scenario: Save includes tx.role

- **WHEN** the operator selects `"Caller"` and clicks Save
- **THEN** `POST /api/v1/config` SHALL include `"tx": { "role": "Caller", ... }`

---

### Requirement: Settings page — CallerPartnerSelect control

The Settings page General tab SHALL include a **Partner selection** control
(`<select id="general-caller-partner-select">`) with two options:
- `value="First"`: "First responder (automatic)"
- `value="None"`: "None (operator selects)"

This control SHALL be visible only when `#general-tx-role` is set to `"Caller"`, and
SHALL be hidden (or `display: none`) when `"Answerer"` is selected. The control SHALL
be pre-populated from `config.tx.callerPartnerSelect` on page load.

#### Scenario: CallerPartnerSelect hidden when role is Answerer

- **WHEN** `#general-tx-role` is set to `"Answerer"`
- **THEN** `#general-caller-partner-select` (and its label) SHALL NOT be visible

#### Scenario: CallerPartnerSelect visible when role is Caller

- **WHEN** `#general-tx-role` is changed to `"Caller"`
- **THEN** `#general-caller-partner-select` SHALL become visible without a page reload

#### Scenario: Save includes tx.callerPartnerSelect

- **WHEN** the operator selects `"Caller"` + `"None"` and clicks Save
- **THEN** `POST /api/v1/config` SHALL include `"tx": { "callerPartnerSelect": "None", ... }`

---

### Requirement: Settings page — restart notice after role change

The page SHALL display a visible notice, **"TX mode change saved. Restart the application for the change to take effect."**, if the operator changes `#general-tx-role` (to a value different from the currently saved `config.tx.role`) and clicks Save.

The notice SHALL appear after the save succeeds (HTTP 200) and SHALL persist until
the page is navigated away from or reloaded.

#### Scenario: Restart notice appears after role change is saved

- **WHEN** the operator changes `#general-tx-role` from its current saved value and
  clicks Save and the response is HTTP 200
- **THEN** a visible restart notice SHALL appear on the Settings page

#### Scenario: Restart notice does not appear when role is unchanged

- **WHEN** the operator saves without changing `#general-tx-role`
- **THEN** no restart notice SHALL appear

---

### Requirement: Decode table — responder row highlighting (None mode)

Decode table rows that appear to be responses to our CQ SHALL receive the CSS class `decode-responder` when the active role is `Caller`, `CallerPartnerSelect = None`, and the controller is in `WaitAnswer`.

A row is a candidate response if its message contains `{our_callsign}` as the first
token AND a second token that is a valid callsign AND a third token that looks like a
Maidenhead grid (4-character alphanumeric starting with two letters). This matches
the FT8 format `{our_callsign} {their_callsign} {their_grid}`.

The `decode-responder` class SHALL use a visually distinct style (e.g. a warm green
or teal accent) that differentiates responders from `decode-cq` (warm amber) and
`decode-partner` (subdued red).

#### Scenario: Responder row highlighted during WaitAnswer (None mode)

- **WHEN** `role = "caller"`, `callerPartnerSelect = "None"`, the state is
  `"WaitAnswer"`, and a decode with message `"PD2FZ Q1ABC JO22"` is rendered
  (where `PD2FZ` is our callsign)
- **THEN** the row SHALL have CSS class `decode-responder`

#### Scenario: Non-response row not highlighted

- **WHEN** the state is `"WaitAnswer"` and a decode with message `"CQ Q1ABC JO22"`
  is rendered
- **THEN** the row SHALL NOT have CSS class `decode-responder`

#### Scenario: Responder rows not highlighted in Answerer role

- **WHEN** `role = "answerer"` and a decode with message `"PD2FZ Q1ABC JO22"` is
  rendered
- **THEN** the row SHALL NOT have CSS class `decode-responder`

---

### Requirement: Decode table — clickable responder rows (None mode)

Rows bearing the `decode-responder` class SHALL be clickable when `role = "caller"` and `CallerPartnerSelect = None`. A click SHALL:

1. Extract the responding callsign (second token), audio frequency offset, and
   response cycle start time from the row.
2. Call `POST /api/v1/tx/select-responder` with
   `{ callsign, frequencyHz, responseCycleStartUtc }`.
3. On HTTP 200: call `renderTxPanel` with the returned status.
4. On HTTP 409 (controller not in `WaitAnswer`): log a console warning; no UI change.
5. On HTTP 405 (role is Answerer): log a console warning; no UI change.

The `responseCycleStartUtc` is derived from the row's decode timestamp using the
existing `parseFt8CycleStartUtc` function.

Double-click guard: the same 400 ms `inFlight` guard used for CQ rows SHALL apply to
responder rows to prevent accidental double-clicks.

#### Scenario: Clicking a responder row calls select-responder

- **WHEN** `role = "caller"`, `CallerPartnerSelect = None`, the state is
  `"WaitAnswer"`, and the operator clicks a row with message `"PD2FZ Q1ABC JO22"`,
  `offsetHz = 1500`, timestamp `"260625_142915"`
- **THEN** `POST /api/v1/tx/select-responder` SHALL be called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "responseCycleStartUtc": "2026-06-25T14:29:15Z" }`

#### Scenario: Non-responder row click has no effect

- **WHEN** the operator clicks a row that does not have `decode-responder` class
- **THEN** no `POST /api/v1/tx/select-responder` request SHALL be sent

---

### Requirement: Settings page — Remote Access section
The Settings page SHALL contain an **"Advanced"** tab (or a section within an existing Advanced tab) that includes a "Remote Access" sub-section. The sub-section SHALL allow the operator to enable LAN access and configure the passphrase. It SHALL participate in the same Save / unsaved-changes flow as all other settings controls.

The Remote Access sub-section SHALL contain:
- A toggle labelled **"Allow access from local network"** (`id="remote-access-enabled"`, maps to `remoteAccess.enabled`)
- A password text input labelled **"Passphrase"** (`id="remote-access-passphrase"`, maps to `remoteAccess.passphrase`), with a show/hide toggle button; visible and editable only when the enable toggle is on
- A **restart-required warning banner** displayed when `enabled` is `true`: `"A restart is required for binding changes to take effect."`
- A **legal disclaimer block** displayed when `enabled` is `true` containing the full operator responsibility text (see below)

**Legal disclaimer text (verbatim):**

> The operator of this application is solely responsible for ensuring compliance with all applicable local, national, and international laws, regulations, and licensing requirements related to amateur radio operation.
>
> This software may provide remote control or automation features that could allow operation of the connected transceiver by unauthorized persons if the hosting webpage, network, or system is improperly secured or exposed to the public.
>
> It is the responsibility of the operator to implement appropriate security measures, restrict access to authorized users only, and ensure that the station is operated in accordance with applicable regulations at all times.
>
> The authors, developers, and contributors of this software accept no liability for misuse, unauthorized transmissions, regulatory violations, equipment damage, or any resulting claims, penalties, or losses arising from the use of this application.
>
> By using this software, you acknowledge and accept full responsibility for its operation, its security configuration, and all consequences — including regulatory, legal, and technical — arising from its use.

#### Scenario: Remote Access toggle is present on the Settings page
- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain an `<input type="checkbox" id="remote-access-enabled">` element within the Settings page

#### Scenario: Remote Access toggle pre-fills from config
- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "remoteAccess": { "enabled": true, ... } }`
- **THEN** `#remote-access-enabled` SHALL be checked

#### Scenario: Passphrase input visible only when toggle is on
- **WHEN** `#remote-access-enabled` is unchecked
- **THEN** the passphrase input (`#remote-access-passphrase`) and its label SHALL be hidden (display:none or equivalent)

- **WHEN** `#remote-access-enabled` is checked
- **THEN** the passphrase input SHALL become visible without a page reload

#### Scenario: Passphrase input pre-fills from config
- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "remoteAccess": { "passphrase": "mypassword" } }`
- **THEN** `#remote-access-passphrase` SHALL display `"mypassword"` (value pre-filled)

#### Scenario: Passphrase show/hide toggle works
- **WHEN** the operator clicks the show/hide button adjacent to `#remote-access-passphrase`
- **THEN** the input type SHALL toggle between `password` (masked) and `text` (visible)

#### Scenario: Restart warning banner shown when enabled is true
- **WHEN** `#remote-access-enabled` is checked (either from config or by the operator toggling it on)
- **THEN** the DOM SHALL display a visible warning element containing the text "restart"

#### Scenario: Restart warning banner hidden when enabled is false
- **WHEN** `#remote-access-enabled` is unchecked
- **THEN** the restart warning element SHALL be hidden (display:none or equivalent)

#### Scenario: Legal disclaimer shown when enabled is true
- **WHEN** `#remote-access-enabled` is checked
- **THEN** the DOM SHALL display the legal disclaimer block containing text that includes "solely responsible" and "accept no liability"

#### Scenario: Legal disclaimer hidden when enabled is false
- **WHEN** `#remote-access-enabled` is unchecked
- **THEN** the legal disclaimer block SHALL be hidden (display:none or equivalent)

#### Scenario: Save includes remoteAccess object
- **WHEN** the operator changes the Remote Access toggle or passphrase and clicks Save
- **THEN** `POST /api/v1/config` SHALL include a `remoteAccess` object with `enabled` and `passphrase` fields reflecting the current UI values

#### Scenario: Passphrase posted as null when input is empty
- **WHEN** the operator saves with `#remote-access-passphrase` empty
- **THEN** the POST body SHALL contain `remoteAccess.passphrase = null`

#### Scenario: Remote Access controls participate in dirty-state tracking
- **WHEN** the operator changes the Remote Access toggle or passphrase input
- **THEN** the unsaved-changes indicator SHALL become visible, consistent with all other settings controls

---

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

---

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

---

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

---

### Requirement: Restart Daemon action in Settings

The Settings page (Advanced tab) SHALL provide a single "Restart Daemon" action that calls `POST /api/v1/system/restart`. This SHALL be the one place in the UI that actually triggers a restart; any restart-required notice elsewhere in the UI SHALL link/point to this action rather than duplicating its own restart control.

#### Scenario: Restart Daemon action is present in the Advanced tab

- **WHEN** the operator opens Settings → Advanced
- **THEN** a "Restart Daemon" action SHALL be visible

#### Scenario: Restart-required notices link to the single restart action

- **WHEN** the operator changes `ptt.method` or a Remote Access bind-affecting setting and saves
- **THEN** the restart-required notice shown SHALL direct the operator to the Advanced tab's "Restart Daemon" action rather than presenting its own separate restart control

---

### Requirement: Restart requires explicit confirmation

The Restart Daemon action SHALL require the operator to explicitly confirm before the restart request is sent, unlike this page's other actions (Save, Retry, Refresh, Test), which act immediately with no confirmation prompt.

#### Scenario: Clicking Restart Daemon shows a confirmation prompt

- **WHEN** the operator clicks "Restart Daemon"
- **THEN** the UI SHALL present a confirmation prompt describing the disruption (the connection will drop briefly and any other connected operators will also be disconnected) before sending `POST /api/v1/system/restart`

#### Scenario: Declining the confirmation sends no request

- **WHEN** the operator is shown the confirmation prompt and declines/cancels it
- **THEN** the UI SHALL NOT send `POST /api/v1/system/restart`

#### Scenario: A 409 (QSO transmitting) response is shown as an actionable message, not a silent failure

- **WHEN** the operator confirms Restart Daemon and the server responds `409 Conflict` because a QSO is transmitting
- **THEN** the UI SHALL display a message explaining that restart was refused because a QSO is currently transmitting, and SHALL NOT show a "reconnecting" state (no restart is in progress)

---

### Requirement: Reconnect UX after a confirmed restart

After a restart request is accepted (`202`), the UI SHALL show a "reconnecting…" state and poll `GET /api/v1/status` until it succeeds, then automatically return to normal operation, rather than presenting the connection drop as an error.

#### Scenario: UI shows reconnecting state immediately after 202

- **WHEN** `POST /api/v1/system/restart` responds `202 Accepted`
- **THEN** the UI SHALL immediately show a "reconnecting…" state

#### Scenario: UI recovers automatically once the new instance is reachable

- **WHEN** the daemon has restarted and `GET /api/v1/status` begins responding successfully again
- **THEN** the UI SHALL clear the "reconnecting…" state and resume normal operation without requiring a manual page reload
