## Requirements

### Requirement: DecodingEnabled persisted to configuration

`AppConfig` SHALL include a `bool DecodingEnabled` field (default: `true`). This field SHALL be written to and read from the JSON config file alongside all other `AppConfig` fields. A config file that does not contain the field SHALL deserialise with `DecodingEnabled = true`, preserving the current unconditional-start behaviour for existing installations.

#### Scenario: Missing field deserialises as true

- **WHEN** the config file exists but does not contain a `decodingEnabled` key
- **THEN** `store.Current.DecodingEnabled` SHALL be `true`

#### Scenario: Persisted false survives restart

- **WHEN** `DecodingEnabled` is set to `false` and saved
- **AND** the application is restarted
- **THEN** `store.Current.DecodingEnabled` SHALL be `false` on the next launch

---

### Requirement: Pipeline respects DecodingEnabled at startup

On application startup, the FT8 pipeline SHALL only start if both `AudioDeviceId` is non-null AND `DecodingEnabled` is `true`. If `DecodingEnabled` is `false`, the application SHALL start normally (Kestrel, WebSocket hub, config store) but SHALL NOT call `StartPipeline()`.

#### Scenario: Decoding disabled — pipeline does not start

- **WHEN** the application starts with `DecodingEnabled = false` and a valid `AudioDeviceId`
- **THEN** `captureManager.IsCapturing` SHALL be `false` after startup
- **AND** no FT8 decode cycles SHALL be processed

#### Scenario: Decoding enabled — pipeline starts as before

- **WHEN** the application starts with `DecodingEnabled = true` and a valid `AudioDeviceId`
- **THEN** the pipeline SHALL start as it did before this change (no regression)

---

### Requirement: POST /api/v1/decode/start starts the pipeline

`POST /api/v1/decode/start` SHALL set `DecodingEnabled = true`, persist the updated config, start the FT8 pipeline (if an audio device is configured and the pipeline is not already running), and return HTTP 200 with the current `DaemonStatus` body.

If no audio device is configured (`AudioDeviceId` is null), the endpoint SHALL return HTTP 400 with a plain-text body: `"No audio device configured. Select a device in Settings before starting decoding."`. The config SHALL NOT be modified in this case.

#### Scenario: Start with device configured

- **WHEN** `POST /api/v1/decode/start` is called with a valid `AudioDeviceId` in config
- **THEN** the response SHALL be HTTP 200
- **AND** `store.Current.DecodingEnabled` SHALL be `true`
- **AND** the pipeline SHALL be running

#### Scenario: Start without device configured

- **WHEN** `POST /api/v1/decode/start` is called with `AudioDeviceId = null`
- **THEN** the response SHALL be HTTP 400
- **AND** `store.Current.DecodingEnabled` SHALL remain unchanged

#### Scenario: Start when already running is idempotent

- **WHEN** `POST /api/v1/decode/start` is called while the pipeline is already running
- **THEN** the response SHALL be HTTP 200
- **AND** the pipeline SHALL continue running without a restart

---

### Requirement: POST /api/v1/decode/stop stops the pipeline

`POST /api/v1/decode/stop` SHALL set `DecodingEnabled = false`, persist the updated config, stop the FT8 pipeline (drain the framer, stop audio capture), and return HTTP 200 with the current `DaemonStatus` body.

#### Scenario: Stop while running

- **WHEN** `POST /api/v1/decode/stop` is called while the pipeline is running
- **THEN** the response SHALL be HTTP 200
- **AND** `store.Current.DecodingEnabled` SHALL be `false`
- **AND** `captureManager.IsCapturing` SHALL be `false` within 5 seconds

#### Scenario: Stop when already stopped is idempotent

- **WHEN** `POST /api/v1/decode/stop` is called while the pipeline is already stopped
- **THEN** the response SHALL be HTTP 200
- **AND** `store.Current.DecodingEnabled` SHALL be `false`

---

### Requirement: DaemonStatus carries DecodingEnabled

`DaemonStatus` SHALL include a `bool DecodingEnabled` field. `GET /api/v1/status` SHALL reflect the current `store.Current.DecodingEnabled` value. The WebSocket `status` event payload SHALL include `decodingEnabled` in its JSON object.

#### Scenario: Status reflects disabled state

- **WHEN** `store.Current.DecodingEnabled` is `false`
- **AND** a client calls `GET /api/v1/status`
- **THEN** the response body SHALL contain `"DecodingEnabled": false`

#### Scenario: WebSocket status event carries DecodingEnabled

- **WHEN** a WebSocket client connects
- **THEN** the initial `status` event payload SHALL include `"decodingEnabled": false` or `"decodingEnabled": true` matching the current config
