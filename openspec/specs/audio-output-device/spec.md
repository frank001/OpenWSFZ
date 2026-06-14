## Requirements

### Requirement: Audio output device enumeration via IAudioOutputDeviceProvider

The application SHALL introduce an `IAudioOutputDeviceProvider` interface in
`OpenWSFZ.Abstractions` with a single method:

```csharp
Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default);
```

The contract SHALL be identical to `IAudioDeviceProvider` except that it enumerates
**render** (playback) endpoints rather than capture endpoints. The implementation
SHALL return an empty list — never throw — when no devices are found or the
underlying API is unavailable.

On Windows the implementation SHALL use `DataFlow.Render` with WASAPI via NAudio's
`MMDeviceEnumerator`, dispatched on a COM STA thread via `StaThread.Run`.
On Linux and macOS a stub implementation SHALL return an empty list and log a single
Debug-level message indicating that output device enumeration is not yet supported on
the current platform.

#### Scenario: Output devices enumerated on Windows via WASAPI

- **WHEN** `IAudioOutputDeviceProvider.GetDevicesAsync()` is called on Windows
- **THEN** the implementation SHALL return a list of `AudioDeviceInfo` records, one
  per active or disabled WASAPI render endpoint, each containing a non-empty `Id` and
  a human-readable `Name`

#### Scenario: Enumeration failure returns empty list

- **WHEN** `IAudioOutputDeviceProvider.GetDevicesAsync()` is called and the underlying
  WASAPI call throws (e.g. Windows Audio service stopped)
- **THEN** the implementation SHALL return an empty list and SHALL NOT throw; a Warning
  SHALL be logged naming the exception

#### Scenario: No render devices present returns empty list

- **WHEN** `IAudioOutputDeviceProvider.GetDevicesAsync()` is called on a host with no
  audio render devices
- **THEN** the implementation SHALL return an empty list (zero elements)

#### Scenario: Windows enumeration succeeds from a non-STA calling thread

- **WHEN** `IAudioOutputDeviceProvider.GetDevicesAsync()` is called from a thread-pool
  thread (MTA apartment)
- **THEN** the implementation SHALL internally switch to a COM STA thread for the
  `MMDeviceEnumerator` call and return the correct device list without throwing

#### Scenario: Linux stub returns empty list

- **WHEN** `IAudioOutputDeviceProvider.GetDevicesAsync()` is called on Linux or macOS
- **THEN** the implementation SHALL return an empty list and SHALL log a single message
  at Debug level indicating that output device enumeration is not yet implemented on
  the current platform; it SHALL NOT throw

---

### Requirement: Audio output device REST endpoint

The web server SHALL expose `GET /api/v1/audio/output-devices` that returns the
current list of enumerated audio render devices as a JSON array.

`IAudioOutputDeviceProvider` SHALL be registered as a singleton in the DI container
and injected into the endpoint handler.

#### Scenario: Endpoint returns output device list

- **WHEN** a client sends `GET /api/v1/audio/output-devices`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`,
  and a JSON array where each element contains at minimum `id` and `name` string fields

#### Scenario: Endpoint returns empty array when no render devices present

- **WHEN** a client sends `GET /api/v1/audio/output-devices` and no render devices are
  available (or the platform stub returns an empty list)
- **THEN** the server SHALL respond with HTTP 200 and an empty JSON array `[]`
