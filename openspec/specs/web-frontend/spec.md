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

