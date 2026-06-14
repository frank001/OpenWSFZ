## MODIFIED Requirements

### Requirement: Settings page — Radio hardware tab

The Settings page (`settings.html`) SHALL allow the operator to view and change the
audio capture device selection, the audio output device selection, and port number,
then save those changes to the backend. The Radio hardware tab SHALL contain both
an **Audio capture device** selector and an **Audio output device** selector, with the
output device selector rendered immediately below the capture device selector and above
the CAT rig connection fieldset.

#### Scenario: Settings page loads audio capture device list

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

#### Scenario: Settings page pre-selects configured capture device

- **WHEN** the device list has loaded and the current config has a non-null
  `audioDeviceId`
- **THEN** the `<select id="device-select">` SHALL have the option whose `value`
  matches `config.audioDeviceId` selected

#### Scenario: Settings page pre-selects configured output device

- **WHEN** the output device list has loaded and the current config has a non-null
  `audioOutputDeviceId`
- **THEN** the `<select id="output-device-select">` SHALL have the option whose
  `value` matches `config.audioOutputDeviceId` selected; if no match is found (device
  no longer present) the "— No device —" placeholder SHALL be selected

#### Scenario: Settings page shows no output device selected when config value is null

- **WHEN** the output device list has loaded and `config.audioOutputDeviceId` is null
- **THEN** the `<select id="output-device-select">` SHALL have the "— No device —"
  placeholder option selected

#### Scenario: Save action posts audioOutputDeviceId and audioOutputFriendlyName

- **WHEN** the operator selects an output device and clicks Save
- **THEN** the page SHALL `POST /api/v1/config` with a JSON body containing
  `audioOutputDeviceId` (the `value` attribute of the selected output `<option>`
  or `null` if the placeholder is selected) and `audioOutputFriendlyName` (the
  visible text content of the selected output `<option>`, or `null` if the placeholder
  is selected), alongside all other config fields

#### Scenario: Save with no output device selected posts null for output device fields

- **WHEN** the operator clicks Save with the output "— No device —" placeholder
  selected
- **THEN** the POST body SHALL contain `audioOutputDeviceId: null` and
  `audioOutputFriendlyName: null`

#### Scenario: Output device selector participates in dirty-state tracking

- **WHEN** the operator changes the output device selection
- **THEN** the unsaved-changes indicator SHALL become visible, consistent with the
  behaviour for all other settings controls

---

### Requirement: `getOutputDevices` function in api.js

The `api.js` module SHALL export a `getOutputDevices()` function that calls
`GET /api/v1/audio/output-devices` and returns a `Promise<Array<{id: string, name: string}>>`.

#### Scenario: getOutputDevices returns output device list

- **WHEN** `getOutputDevices()` is called and the server responds with a non-empty
  JSON array
- **THEN** the function SHALL resolve with the parsed array

#### Scenario: getOutputDevices returns empty array when no devices present

- **WHEN** `getOutputDevices()` is called and the server responds with `[]`
- **THEN** the function SHALL resolve with an empty array
