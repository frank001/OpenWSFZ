## ADDED Requirements

### Requirement: Stale capture device identifier is re-resolved by friendly name

The daemon SHALL enumerate the available capture devices and resolve the device to use before
every automatic capture start (startup auto-start, restart after a capture failure, and watchdog
restart), as follows:

- If the configured `audioDeviceId` is present and available, the daemon SHALL use it, even if that
  device's current name differs from `audioDeviceFriendlyName`.
- Otherwise, if exactly one available device has a name byte-for-byte equal to
  `audioDeviceFriendlyName`, the daemon SHALL adopt that device's identifier, persist it as
  `audioDeviceId` with `audioDeviceFriendlyName` unchanged, and log one Warning naming the old
  identifier, the new identifier and the friendly name. Exactly one capture start SHALL result from
  one adoption.
- Otherwise, if zero or more than one available device matches, the daemon SHALL NOT start capture
  on any device and SHALL enter the `DeviceUnavailable` state.
- If enumeration returns no devices, or `audioDeviceFriendlyName` is null, the daemon SHALL attempt
  the configured `audioDeviceId` unchanged.

The daemon SHALL NOT adopt a device that is not available, SHALL NOT match names by substring,
case-folding or whitespace normalisation, and SHALL NOT re-resolve a device identifier that the
operator has just set through `POST /api/v1/config`.

#### Scenario: Rotated endpoint ID is adopted

- **WHEN** the configured ID `{0.0.1.00000000}.{AAAA…}` is absent, and exactly one available device
  `{0.0.1.00000000}.{BBBB…}` is named `"Microphone (2- USB Audio CODEC )"`, equal to the configured
  friendly name
- **THEN** capture SHALL start on `{…BBBB…}`, `config.json`'s `audioDeviceId` SHALL equal
  `{…BBBB…}`, `audioDeviceFriendlyName` SHALL be unchanged, and exactly one Warning naming both IDs
  SHALL be logged

#### Scenario: Stale ID at daemon startup is adopted

- **WHEN** the daemon starts with decoding enabled, a configured ID that no longer exists, and a
  friendly name matching exactly one available device
- **THEN** capture SHALL be running on the matching device, with at least one chunk received,
  within 30 s of startup, with no operator action

#### Scenario: Configured device present is never replaced

- **WHEN** the configured ID is present and available, and a different available device also bears
  the configured friendly name
- **THEN** the daemon SHALL use the configured ID and SHALL NOT modify `config.json`

#### Scenario: Ambiguous name is never guessed

- **WHEN** the configured ID is absent and two available devices bear the configured friendly name
- **THEN** no capture session SHALL be started, `captureState` SHALL be `DeviceUnavailable`, and a
  Warning stating the match count SHALL be logged

#### Scenario: Disabled-only match is not adopted

- **WHEN** the configured ID is absent and the only device bearing the configured friendly name is
  not available
- **THEN** no capture session SHALL be started and `captureState` SHALL be `DeviceUnavailable`

#### Scenario: Near-miss names do not match

- **WHEN** the configured friendly name is `"Microphone (2- USB Audio CODEC )"` and the only
  available device is named `"Microphone (3- USB Audio CODEC )"` or `"Microphone (2- USB Audio CODEC)"`
- **THEN** no device SHALL be adopted

### Requirement: Automatic capture restarts use bounded backoff and never stop

Automatic capture restarts (after a capture failure, or triggered by the watchdog) SHALL share one
count of consecutive failures. The delay before consecutive automatic attempt *k* (k ≥ 1) SHALL be
`min(5 × 2^(k−1), 60)` seconds. The count SHALL reset to zero when a restarted capture session
delivers its first audio chunk. An automatic attempt at which resolution finds no uniquely matching
available device SHALL count as a failed attempt, even though no capture session is opened.
Automatic restarts SHALL continue indefinitely at the 60-second
cap while the failure persists. Operator-initiated device changes and the first startup attempt
SHALL NOT be delayed.

#### Scenario: Backoff schedule

- **WHEN** every automatic attempt fails immediately
- **THEN** the first seven attempts SHALL be scheduled after 5, 10, 20, 40, 60, 60 and 60 s (±1 s)

#### Scenario: Recovery resets the schedule

- **WHEN** the fourth attempt succeeds and delivers a chunk, and capture later fails again
- **THEN** the next automatic attempt SHALL be scheduled after 5 s

#### Scenario: A device that returns hours later is picked up

- **WHEN** the capture device is absent for 2 hours and then becomes available under the configured
  ID or a uniquely matching name
- **THEN** capture SHALL resume, with chunks flowing, within 70 s of the device becoming
  available, with no operator action

### Requirement: Capture recovery state on the status endpoint

`GET /api/v1/status` and the initial WebSocket `status` event SHALL include:

- `captureState`: one of `Idle` (no device configured or decoding disabled), `Capturing` (a session is
  running with zero consecutive failures), `Recovering` (one or more consecutive failures, and the
  last resolution identified a usable device or could not resolve), `DeviceUnavailable` (the last
  resolution found no uniquely matching available device);
- `captureRestartCount`: automatic restart attempts since process start;
- `consecutiveCaptureFailures`: the current consecutive-failure count;
- `lastCaptureError`: the message of the most recent capture failure or failed resolution,
  truncated to 500 characters, or null if neither has occurred since process start. A failed
  resolution SHALL produce a message stating the configured friendly name and the number of
  available matches (0 or ≥2). It SHALL NOT be cleared on recovery.

The daemon SHALL log one Warning on each transition into `DeviceUnavailable` and one Warning on each
recovery, stating the number of attempts and the seconds without audio. Per-termination logging
required by FR-021 SHALL be unchanged.

#### Scenario: Dead device is visible to an HTTP-only poller

- **WHEN** the configured device and friendly name both match no available device, and zero
  WebSocket clients are connected
- **THEN** within 30 s of the first failure, `GET /api/v1/status` SHALL return
  `captureState: "DeviceUnavailable"`, `consecutiveCaptureFailures >= 1`, and a non-null
  `lastCaptureError`

#### Scenario: Recovery is visible

- **WHEN** a device in `DeviceUnavailable` becomes available and capture resumes
- **THEN** `GET /api/v1/status` SHALL return `captureState: "Capturing"`,
  `consecutiveCaptureFailures: 0`, and `lastCaptureError` SHALL still hold the last failure's message
