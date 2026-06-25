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

### Requirement: Decode start/stop toggle button in status bar

The main page (`index.html`) status bar SHALL include a `<button id="decode-toggle">` element. The button label SHALL read **"Stop Decoding"** when the pipeline is active and **"Start Decoding"** when it is stopped. Clicking the button SHALL call `POST /api/v1/decode/stop` or `POST /api/v1/decode/start` accordingly and update the UI state on success.

The button SHALL be disabled (and labelled **"No device"**) when no audio device is configured (`audioDevice` is null or empty in the status payload), since starting is not possible without a device.

#### Scenario: Button shows Stop when decoding is active

- **WHEN** the `status` event is received with `decodingEnabled: true`
- **THEN** `#decode-toggle` SHALL have label text "Stop Decoding"
- **AND** the button SHALL not be disabled

#### Scenario: Button shows Start when decoding is stopped

- **WHEN** the `status` event is received with `decodingEnabled: false`
- **THEN** `#decode-toggle` SHALL have label text "Start Decoding"
- **AND** the button SHALL not be disabled (assuming a device is configured)

#### Scenario: Button is disabled when no device is configured

- **WHEN** the `status` event is received with `audioDevice: null` or `audioDevice: ""`
- **THEN** `#decode-toggle` SHALL be disabled
- **AND** the button label SHALL read "No device"

#### Scenario: Clicking Stop calls the stop endpoint

- **WHEN** `#decode-toggle` is clicked while in the "Stop Decoding" state
- **THEN** a `POST /api/v1/decode/stop` request SHALL be issued
- **AND** on a 200 response the button SHALL update to "Start Decoding"

#### Scenario: Clicking Start calls the start endpoint

- **WHEN** `#decode-toggle` is clicked while in the "Start Decoding" state
- **THEN** a `POST /api/v1/decode/start` request SHALL be issued
- **AND** on a 200 response the button SHALL update to "Stop Decoding"

---

### Requirement: Decoding-state badge in status bar

The main page status bar SHALL include a `<span id="decode-badge">` element that displays the current decode state: **"Decoding"** (with a visually distinct active style) when the pipeline is running, and **"Stopped"** (with a neutral/muted style) when it is not.

The badge SHALL be updated whenever a `status` event, heartbeat event, or a successful response from `/decode/start` or `/decode/stop` is received.

#### Scenario: Badge shows Decoding when active

- **WHEN** `decodingEnabled` is `true` in the current status
- **THEN** `#decode-badge` SHALL display the text "Decoding"
- **AND** SHALL have the CSS class `decoding-active`

#### Scenario: Badge shows Stopped when inactive

- **WHEN** `decodingEnabled` is `false` in the current status
- **THEN** `#decode-badge` SHALL display the text "Stopped"
- **AND** SHALL have the CSS class `decoding-stopped`

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

### Requirement: Settings page pre-fills TX numeric fields from loaded config

> **Superseded by tx-general-settings-page.** The element IDs `tx-watchdog-minutes` and `tx-retry-count` no longer exist; the fields are now `general-watchdog-minutes` and `general-retry-count` on the General tab. The behavioural contract (pre-populate from config, save without changes does not trigger clamp warnings) is preserved in the **Settings page — General tab** requirement above.

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
  the button SHALL have a visually alarming style (red/danger background, bold weight —
  CSS class `tx-btn-armed`) so the operator cannot overlook that autonomous transmission
  is active. The label is intentionally kept as "Enable TX" in both states; the red
  background alone signals the armed condition (D-TX-UI-002 — UAT decision 2026-06-22).

Clicking the button in the disarmed state SHALL call `POST /api/v1/tx/enable` and
apply the armed CSS class on HTTP 200. Clicking in the armed state SHALL call
`POST /api/v1/tx/disable` and remove the armed CSS class on HTTP 200. The button
SHALL be disabled for the duration of the pending request.

#### Scenario: Button shows Enable TX and is disarmed when autoAnswer is false

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: false`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL NOT have the `tx-btn-armed` CSS class

#### Scenario: Button shows Enable TX with armed style when autoAnswer is true

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: true`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL have the `tx-btn-armed` CSS class applied

#### Scenario: Clicking Enable TX (disarmed) calls /tx/enable and applies armed style

- **WHEN** `#tx-enable-btn` is clicked while in the disarmed state
- **THEN** `POST /api/v1/tx/enable` SHALL be called
- **AND** on HTTP 200, the `tx-btn-armed` CSS class SHALL be applied; label remains "Enable TX"

#### Scenario: Clicking Enable TX (armed) calls /tx/disable and removes armed style

- **WHEN** `#tx-enable-btn` is clicked while in the armed state
- **THEN** `POST /api/v1/tx/disable` SHALL be called
- **AND** on HTTP 200, the `tx-btn-armed` CSS class SHALL be removed; label remains "Enable TX"

#### Scenario: Button is disabled during pending request

- **WHEN** a click on `#tx-enable-btn` triggers a request that has not yet resolved
- **THEN** `#tx-enable-btn` SHALL be `disabled` until the response (success or error) is
  received

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

### Requirement: Main page handles txState WebSocket event

The main page WebSocket handler SHALL process `txState` events (previously unhandled)
and update the TX panel accordingly. A `txState` event carries:
- `state` — the new `QsoState` as a string
- `partner` — the active partner callsign, or `null`
- `autoAnswerEnabled` — the current armed/disarmed state (added for D-TX-UI-003,
  2026-06-22; allows QSO completion and abort to disarm the panel without a separate
  HTTP call)

Wire format example (active state):
`{"type":"txState","state":"TxAnswer","partner":"Q2XYZ","autoAnswerEnabled":true}`

Wire format example (idle / disarmed):
`{"type":"txState","state":"Idle","partner":null,"autoAnswerEnabled":false}`

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

CQ decode table rows SHALL be clickable. Clicking a CQ row while the TX controller is
`Idle` SHALL:

1. Extract the partner callsign, audio frequency offset, and CQ cycle start time from
   the decode row.
2. Call `POST /api/v1/tx/answer-cq` with `{ callsign, frequencyHz, cqCycleStartUtc }`.
3. On HTTP 200: call `renderTxPanel` with the returned status (system is now armed and
   waiting for the correct FT8 answer phase; TX fires within 0–30 s at most).
4. On HTTP 409 (controller not Idle): log a console warning; no UI change.
5. On other error: log to console; no UI change.

**Callsign extraction** from the CQ message:
- 3-token CQ (`CQ callsign grid`): token at index 1
- 4-token CQ (`CQ modifier callsign grid`): token at index 2

**Frequency:** the `offsetHz` value of the decode row (the audio frequency in Hz at
which the signal was detected).

**`cqCycleStartUtc`:** the UTC cycle-start timestamp of the decode row, formatted as an
ISO 8601 string (e.g. `"2026-06-22T17:29:15Z"`). The decode row's timestamp column
contains this value; the frontend SHALL parse it from the row data at render time and
store it as a data attribute or in a closure for retrieval when the row is clicked.

Decode row timestamp format: `YYMMDD_HHMMSS` (UTC). Parsing:
```javascript
function parseFt8CycleStartUtc(ft8Ts) {
  // ft8Ts example: "260622_172915"
  const [date, time] = ft8Ts.split('_');
  return `20${date.slice(0,2)}-${date.slice(2,4)}-${date.slice(4,6)}` +
         `T${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}Z`;
}
```

Clicking a CQ row while the controller is NOT Idle SHALL have no effect (the click is
silently ignored; a 409 response is swallowed with a console warning).

#### Scenario: Clicking a CQ row calls answer-cq with phase info and arms the TX panel

- **WHEN** the controller is `Idle` and the operator clicks a CQ row with
  message `"CQ Q1ABC JO33"`, `offsetHz = 1500`, and row timestamp `"260622_172915"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "cqCycleStartUtc": "2026-06-22T17:29:15Z" }`
- **AND** on HTTP 200 the TX panel SHALL update to the armed appearance

#### Scenario: Clicking a 4-token CQ row extracts the callsign correctly

- **WHEN** the operator clicks a CQ row with message `"CQ DX Q9XYZ FN42"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with `callsign = "Q9XYZ"`

#### Scenario: Clicking a CQ row when not Idle has no effect

- **WHEN** the controller state is `TxAnswer` (active QSO) and the operator clicks
  a CQ row
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
