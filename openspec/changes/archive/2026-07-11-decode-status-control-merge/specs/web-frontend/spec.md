## REMOVED Requirements

### Requirement: Decode start/stop toggle button in status bar
**Reason**: Superseded by "Combined decode status/toggle control in status bar" below — the
separate toggle button is merged with the decode-state badge into a single element.
**Migration**: `#decode-toggle` continues to exist as an element id (the `<button>` is kept, not
renamed), but its label text and styling now also carry the state-display role formerly owned by
`#decode-badge`. Any code or test referencing the old "Stop Decoding"/"Start Decoding"/"No device"
label text must be updated to the new labels defined in the replacement requirement.

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

### Requirement: Decoding-state badge in status bar
**Reason**: Superseded by "Combined decode status/toggle control in status bar" below — the
separate read-only badge is merged into the toggle button, eliminating the redundant adjacent
element.
**Migration**: `#decode-badge` is removed from the DOM entirely. Any code or test referencing
`#decode-badge`, its text content, or its `decoding-active`/`decoding-stopped` classes must be
updated to reference `#decode-toggle` and the new classes defined in the replacement requirement.

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

## ADDED Requirements

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
