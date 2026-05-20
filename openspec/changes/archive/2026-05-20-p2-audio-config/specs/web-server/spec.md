## ADDED Requirements

### Requirement: Status endpoint includes active audio device

The `GET /api/v1/status` response SHALL include an `audioDevice` field containing the name of the currently configured audio capture device, or `null` if no device has been configured.

#### Scenario: Status includes configured device name

- **WHEN** a client sends `GET /api/v1/status` and an audio device is configured
- **THEN** the JSON response SHALL include an `audioDevice` field with the configured device's name as a non-empty string

#### Scenario: Status includes null when no device configured

- **WHEN** a client sends `GET /api/v1/status` and no audio device has been configured
- **THEN** the JSON response SHALL include an `audioDevice` field with a `null` value

#### Scenario: WebSocket status event includes audioDevice field

- **WHEN** a WebSocket connection is established
- **THEN** the initial `status` event's `payload` SHALL include an `audioDevice` field (either a string or `null`)
