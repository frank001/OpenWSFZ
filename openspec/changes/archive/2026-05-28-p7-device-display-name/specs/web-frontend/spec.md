## MODIFIED Requirements

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
