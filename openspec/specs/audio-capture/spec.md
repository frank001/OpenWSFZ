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
