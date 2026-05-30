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

---

### Requirement: Settings page

The Settings page (`settings.html`) SHALL allow the operator to view and change the audio device selection and port number, then save those changes to the backend. The page SHALL be navigable from the main page and SHALL provide navigation back.

#### Scenario: Settings page loads audio device list

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the page JavaScript SHALL call `GET /api/v1/audio/devices` and populate a `<select>` element with one `<option>` per returned device; if the list is empty a single disabled option reading "No devices found" SHALL be shown

#### Scenario: Settings page pre-selects configured device

- **WHEN** the device list has loaded and the current config has a non-null `audioDeviceId`
- **THEN** the `<select>` SHALL have the option whose `value` matches `config.audioDeviceId` selected

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
