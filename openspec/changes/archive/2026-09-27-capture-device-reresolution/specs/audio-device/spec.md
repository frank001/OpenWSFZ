## ADDED Requirements

### Requirement: Enumerated devices report their availability

Each `AudioDeviceInfo` returned by `IAudioDeviceProvider` SHALL carry an `Available` flag that is
`true` when capture can be opened on the device now. On Windows, `Available` SHALL be `true` exactly
when the WASAPI endpoint state is Active. Disabled endpoints SHALL still be listed, with
`Available = false`. Providers that list only devices they can currently see (Linux, macOS) SHALL
report `Available = true`. `GET /api/v1/audio/devices` SHALL include the flag as a boolean
`available` field on each element.

#### Scenario: Disabled Windows endpoint is listed but not available

- **WHEN** a WASAPI capture endpoint is disabled in Windows Sound Settings
- **THEN** it SHALL appear in the device list with `Available = false`, and in
  `GET /api/v1/audio/devices` with `"available": false`

#### Scenario: Active Windows endpoint is available

- **WHEN** a WASAPI capture endpoint is active
- **THEN** it SHALL appear with `Available = true`
