## ADDED Requirements

### Requirement: CycleFramer and Ft8Decoder wired into daemon lifecycle

The daemon SHALL instantiate `CycleFramer` and `Ft8Decoder` in `Program.cs` and start
`CycleFramer.RunAsync` on `ApplicationStarted` (after `CaptureManager.StartAsync` is
called). On `ApplicationStopping` the daemon SHALL cancel the `CycleFramer`'s
`CancellationToken` and await `CycleFramer.RunAsync` before disposing, mirroring the
existing pattern used for `CaptureManager`.

#### Scenario: CycleFramer starts when capture is active

- **WHEN** the daemon starts and a device is configured
- **THEN** `CycleFramer.RunAsync` SHALL be started on `ApplicationStarted` in the same
  callback that calls `CaptureManager.StartAsync`

#### Scenario: CycleFramer does not start when no device is configured

- **WHEN** the daemon starts and `AppConfig.AudioDeviceName` is null
- **THEN** `CycleFramer.RunAsync` SHALL NOT be called and `CycleFramer` SHALL remain idle

#### Scenario: CycleFramer restarts when capture device changes

- **WHEN** `POST /api/v1/config` is called with a new non-null `audioDeviceName`
- **THEN** any running `CycleFramer` session SHALL be cancelled and a new one SHALL be
  started after `CaptureManager.StartAsync` returns

#### Scenario: CycleFramer is stopped on daemon shutdown

- **WHEN** the daemon receives a shutdown signal (Ctrl-C or SIGTERM)
- **THEN** `CycleFramer`'s `CancellationToken` SHALL be cancelled and `RunAsync` SHALL
  be awaited (with a 3-second timeout) before the process exits
