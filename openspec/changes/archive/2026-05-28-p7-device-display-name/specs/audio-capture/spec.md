## MODIFIED Requirements

### Requirement: Capture lifecycle managed by daemon

The daemon SHALL automatically start audio capture when a device is configured at startup and stop capture cleanly on shutdown. When the configured device changes (via `POST /api/v1/config`), the daemon SHALL stop the current capture session and start a new one using the updated device identifier.

#### Scenario: Capture starts automatically at daemon startup when device is configured

- **WHEN** the daemon starts and `AppConfig.AudioDeviceId` is non-null
- **THEN** `CaptureManager.StartAsync` SHALL be called with `AppConfig.AudioDeviceId` before the application starts serving requests (or immediately after `ApplicationStarted`)

#### Scenario: Capture does not start when no device is configured

- **WHEN** the daemon starts and `AppConfig.AudioDeviceId` is null
- **THEN** `CaptureManager.IsCapturing` SHALL remain `false` and no `CaptureAsync` call SHALL be made

#### Scenario: Capture restarts when device changes via config POST

- **WHEN** `POST /api/v1/config` is called with a new non-null `audioDeviceId`
- **THEN** any in-progress capture session SHALL be stopped and a new session SHALL be started with the new `audioDeviceId`

#### Scenario: Capture stops on daemon shutdown

- **WHEN** the daemon receives a shutdown signal (Ctrl-C or SIGTERM)
- **THEN** the active `CaptureAsync` enumeration SHALL be cancelled and the `CaptureManager` SHALL be disposed without throwing
