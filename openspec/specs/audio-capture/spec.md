# audio-capture Specification

## Purpose

Specifies the cross-platform PCM audio capture abstraction the daemon uses to acquire 12 kHz
mono audio for decoding, its lifecycle management, and how capture status is surfaced via the
daemon status endpoint.
## Requirements
### Requirement: PCM audio capture interface

The application SHALL expose an `IAudioSource` interface that delivers a continuous stream of 32-bit float mono PCM samples from a named audio capture device. The stream SHALL be accessible as an `IAsyncEnumerable<float[]>` and SHALL be cancellable. The interface SHALL declare the sample rate and channel count. Implementations SHALL throw `AudioCaptureException` — not a generic exception — when a device cannot be opened or capture fails unrecoverably.

#### Scenario: CaptureAsync yields float chunks at declared sample rate

- **WHEN** `IAudioSource.CaptureAsync(deviceId, ct)` is called with a valid device ID
- **THEN** the implementation SHALL yield non-empty `float[]` arrays where each value is in the range `[-1.0, +1.0]` and the sample rate matches `IAudioSource.SampleRate`

#### Scenario: CaptureAsync terminates on cancellation

- **WHEN** the `CancellationToken` passed to `CaptureAsync` is cancelled
- **THEN** the async enumerable SHALL complete without throwing (i.e., the `await foreach` loop exits cleanly)

#### Scenario: CaptureAsync throws AudioCaptureException for unknown device

- **WHEN** `CaptureAsync` is called with a device ID that does not correspond to any capture device on the current OS
- **THEN** the implementation SHALL throw `AudioCaptureException` before yielding any chunks

---

### Requirement: Cross-platform capture implementations

The application SHALL provide platform-specific implementations of `IAudioSource` selected at runtime by `PlatformAudioSource`. On Windows the implementation SHALL use WASAPI via NAudio and SHALL resample to 12 000 Hz mono internally. On Linux the implementation SHALL use `arecord`. On macOS the implementation SHALL use `sox`. The target sample rate is 12 000 Hz and the channel count is 1 (mono) for all platforms.

#### Scenario: Windows capture delivers 12 000 Hz mono float samples

- **WHEN** `WasapiAudioSource.CaptureAsync` is called on Windows with a valid WASAPI device ID
- **THEN** `SampleRate` SHALL be 12 000 and `ChannelCount` SHALL be 1, and chunks SHALL contain float samples resampled from the device's native rate

#### Scenario: Linux capture invokes arecord with correct arguments

- **WHEN** `ArecordAudioSource.CaptureAsync` is called on Linux with a valid ALSA device ID (e.g., `hw:0,0`)
- **THEN** the implementation SHALL invoke `arecord` with arguments that specify FLOAT_LE format, 12 000 Hz sample rate, 1 channel, and raw output

#### Scenario: macOS capture invokes sox with correct arguments

- **WHEN** `SoxAudioSource.CaptureAsync` is called on macOS with a device name
- **THEN** the implementation SHALL invoke `sox` with arguments that specify the CoreAudio input, raw float 32-bit output, 12 000 Hz, and 1 channel

#### Scenario: Unsupported platform returns NullAudioSource that throws

- **WHEN** `PlatformAudioSource.CaptureAsync` is called on an OS other than Windows, Linux, or macOS
- **THEN** it SHALL throw `AudioCaptureException` with a message indicating the platform is unsupported

---

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

---

### Requirement: Capture status in the status endpoint

The `GET /api/v1/status` response SHALL include a `captureActive` boolean field indicating whether an audio capture session is currently running.

#### Scenario: captureActive is true when capture is running

- **WHEN** `CaptureManager.IsCapturing` is `true`
- **THEN** `GET /api/v1/status` SHALL return a JSON body with `captureActive: true`

#### Scenario: captureActive is false when no capture session is active

- **WHEN** no device is configured or capture has not yet started
- **THEN** `GET /api/v1/status` SHALL return a JSON body with `captureActive: false`

### Requirement: Capture health is evaluated independently of client connections

The daemon SHALL evaluate audio-capture health on a single daemon-lifetime periodic timer with a
5-second window, regardless of how many WebSocket clients are connected, including zero. Each
window SHALL be evaluated exactly once. The evaluation SHALL consume the per-window data-flow state
exactly once, SHALL advance the capture watchdog exactly once, and SHALL publish a snapshot that all
other consumers read. WebSocket connections SHALL NOT consume per-window monitor state and SHALL NOT
advance the watchdog. The watchdog SHALL trigger a pipeline restart after 3 consecutive windows in
which capture is active and no audio chunk was received.

#### Scenario: Watchdog restarts a silent stall with no client connected

- **WHEN** capture is active, zero WebSocket clients are connected, and the audio source stops
  delivering chunks without throwing
- **THEN** the pipeline restart action SHALL be invoked exactly once after 3 consecutive empty
  windows (15 s), and `watchdogRestartCount` SHALL increase by 1

#### Scenario: Watchdog tick rate does not depend on client count

- **WHEN** capture is active and 3 WebSocket clients are connected for 10 consecutive windows
- **THEN** the watchdog SHALL have been advanced exactly 10 times, and the data-flow state SHALL
  have been consumed exactly 10 times

#### Scenario: Quiet but flowing audio is not a stall

- **WHEN** capture is active and the source delivers chunks whose samples are all zero
- **THEN** `dataFlowing` SHALL be `true` for each window and the watchdog SHALL NOT trigger

#### Scenario: Stopped capture is not a stall

- **WHEN** no capture session is running (`captureActive` is `false`)
- **THEN** the watchdog SHALL NOT trigger, however many windows pass

#### Scenario: Heartbeat log line is written with no client connected

- **WHEN** the daemon runs with capture configured and zero WebSocket clients for 60 s
- **THEN** the log SHALL contain one line per window matching
  `Heartbeat: captureActive=(true|false), audioActive=(true|false), dataFlowing=(true|false)`
  (lowercase, byte-identical to the format the daemon writes today), and at most one such line
  per window, regardless of client count

### Requirement: Live data-flow status on the status endpoint

`GET /api/v1/status` and the initial WebSocket `status` event SHALL include three capture-health
fields:

- `dataFlowing` (boolean): whether at least one audio chunk was received in the most recent
  completed window. It is `false` before the first window completes.
- `lastChunkAgeMs` (integer or null): milliseconds elapsed since the most recent audio chunk was
  received, computed at the time the response is built from a monotonic clock. It is `null` only if
  no chunk has been received since process start. A pipeline restart SHALL NOT reset it.
- `watchdogRestartCount` (integer): the number of times the capture watchdog has triggered a
  pipeline restart since process start.

None of these fields SHALL latch. Each SHALL reflect current state at request time or at the most
recent window.

#### Scenario: Stall becomes visible to an HTTP-only poller

- **WHEN** capture is active with zero WebSocket clients and the source stops delivering chunks at time T
- **THEN** a `GET /api/v1/status` issued at T + 11 s SHALL return `dataFlowing: false` and
  `lastChunkAgeMs >= 10000`

#### Scenario: Healthy capture reads healthy

- **WHEN** the source delivers chunks continuously
- **THEN** every `GET /api/v1/status` after the first completed window SHALL return
  `dataFlowing: true` and `lastChunkAgeMs < 2000`

#### Scenario: A restart that delivers nothing keeps ageing

- **WHEN** the last chunk arrived at time T, the pipeline is restarted at T + 15 s, and the
  restarted session delivers no chunks
- **THEN** a `GET /api/v1/status` at T + 30 s SHALL return `lastChunkAgeMs >= 29000`

### Requirement: Audio activity has one meaning on every surface

The `audioActive` field SHALL carry the same value on `GET /api/v1/status`, on the initial WebSocket
`status` event, and on each WebSocket `heartbeat` frame: the `dataFlowing` value of the most recent
completed window. `audioActive` SHALL NOT latch across windows.

#### Scenario: REST audioActive falls when audio stops

- **WHEN** audio chunks were flowing and then stop, with zero WebSocket clients connected
- **THEN** `GET /api/v1/status` SHALL return `audioActive: false` within 10 s

#### Scenario: Surfaces agree

- **WHEN** a WebSocket client connects and, within the same window, `GET /api/v1/status` is requested
- **THEN** the `audioActive` value in the initial `status` event and in the REST response SHALL be equal

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

