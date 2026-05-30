## ADDED Requirements

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
