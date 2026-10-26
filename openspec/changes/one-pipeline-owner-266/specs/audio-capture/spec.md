## MODIFIED Requirements

### Requirement: Capture lifecycle managed by daemon

The daemon SHALL automatically start audio capture when a device is configured **and decoding is enabled** at startup and stop capture cleanly on shutdown. When the configured device changes (via `POST /api/v1/config`) **while decoding is enabled**, the daemon SHALL stop the current capture session and start a new one using the updated device identifier. **While decoding is disabled, a change of device SHALL be stored and SHALL NOT start capture, the framer or any other part of the pipeline; the next start of decoding SHALL use the stored device.**

#### Scenario: Capture starts automatically at daemon startup when device is configured

- **WHEN** the daemon starts, `AppConfig.AudioDeviceId` is non-null and `AppConfig.DecodingEnabled` is true
- **THEN** `CaptureManager.StartAsync` SHALL be called with `AppConfig.AudioDeviceId` before the application starts serving requests (or immediately after `ApplicationStarted`)

#### Scenario: Capture does not start when no device is configured

- **WHEN** the daemon starts and `AppConfig.AudioDeviceId` is null
- **THEN** `CaptureManager.IsCapturing` SHALL remain `false` and no `CaptureAsync` call SHALL be made

#### Scenario: Capture does not start at startup when decoding is disabled

- **WHEN** the daemon starts with a non-null `AppConfig.AudioDeviceId` and `AppConfig.DecodingEnabled` false
- **THEN** `CaptureManager.IsCapturing` SHALL remain `false` and no `CaptureAsync` call SHALL be made

#### Scenario: Capture restarts when device changes via config POST

- **WHEN** `POST /api/v1/config` is called with a new non-null `audioDeviceId` while `DecodingEnabled` is true
- **THEN** any in-progress capture session SHALL be stopped and a new session SHALL be started with the new `audioDeviceId`

#### Scenario: A device change while decoding is disabled is saved only

- **WHEN** `POST /api/v1/config` is called with a new non-null `audioDeviceId` while `DecodingEnabled` is false
- **THEN** the new `audioDeviceId` SHALL be persisted, no capture session and no framer SHALL be started, and no decode SHALL be produced
- **AND** a later start of decoding SHALL capture from the new `audioDeviceId`

#### Scenario: Capture stops on daemon shutdown

- **WHEN** the daemon receives a shutdown signal (Ctrl-C or SIGTERM)
- **THEN** the active `CaptureAsync` enumeration SHALL be cancelled and the `CaptureManager` SHALL be disposed without throwing
