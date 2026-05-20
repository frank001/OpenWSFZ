## Why

Two bugs block Phase 5 (FT8 decoder) and make the existing Settings page useless in practice:

1. **Enumeration silently returns empty on Windows.** `WasapiAudioDeviceProvider` calls `MMDeviceEnumerator` on whatever thread ASP.NET Core dispatches the request on. Those threads are COM MTA. `MMDeviceEnumerator` requires COM STA. The exception is swallowed by the broad `catch {}` block, so `GET /api/v1/audio/devices` always returns `[]` on Windows — the operator cannot choose a device.

2. **No audio capture exists.** `IAudioSource` in the Abstractions project is an empty stub. Nothing opens a device and reads PCM samples. The FT8 decoder (Phase 5) must receive a continuous stream of 32-bit float mono samples at 12 000 Hz; without this pipeline that stream does not exist.

Both problems are structural prerequisites. They cannot be deferred: you cannot test decoding without audio.

## What Changes

- **Fix `WasapiAudioDeviceProvider`** — run `MMDeviceEnumerator` on a dedicated COM STA thread so enumeration returns real devices on Windows.
- **Define `IAudioSource`** — replace the stub with a real interface: `IAsyncEnumerable<float[]> CaptureAsync(string deviceId, CancellationToken ct)` delivering 32-bit float mono PCM at a declared `SampleRate`.
- **Implement `WasapiAudioSource`** (Windows) — uses `NAudio.WasapiCapture` on a dedicated STA thread; resamples to 12 000 Hz mono float via NAudio's resampling pipeline; buffers to a `Channel<float[]>`.
- **Implement `ArecordAudioSource`** (Linux) — runs `arecord -D <id> -f FLOAT_LE -r 12000 -c 1 -t raw` and pipes raw PCM bytes into the channel.
- **Implement `SoxAudioSource`** (macOS) — runs `sox -d -t raw -e float -b 32 -r 12000 -c 1 -` (with device selection via `AUDIODEV` env var or `-d <name>`).
- **`PlatformAudioSource`** — dispatches to the correct implementation based on OS, mirrors `PlatformAudioDeviceProvider`.
- **Daemon wiring** — start capture when a device is configured at startup; restart capture on config save if the device name changes; stop cleanly on shutdown.
- **Status endpoint enrichment** — `GET /api/v1/status` gains a `captureActive` boolean field so the UI (and tests) can verify audio is flowing.

## Capabilities

### New Capabilities

- `audio-capture`: PCM audio capture engine — `IAudioSource` interface, cross-platform implementations (WASAPI, arecord, sox), daemon lifecycle integration, capture status in the status endpoint.

### Modified Capabilities

- `audio-device`: Fix the STA threading defect in `WasapiAudioDeviceProvider`; add a scenario that validates enumeration returns real devices when called from a non-STA context.

## Impact

- `src/OpenWSFZ.Abstractions/IAudioSource.cs` — replace stub with real interface.
- `src/OpenWSFZ.Audio/` — new `WasapiAudioSource.cs`, `ArecordAudioSource.cs`, `SoxAudioSource.cs`, `PlatformAudioSource.cs`, `StaThread.cs` helper; fix `WasapiAudioDeviceProvider.cs`.
- `src/OpenWSFZ.Daemon/Program.cs` — register and start `PlatformAudioSource`; add device-change handling.
- `src/OpenWSFZ.Web/WebApp.cs` + `DaemonStatus.cs` — add `captureActive` field.
- New NAudio packages: `NAudio` already referenced on Windows; may need `NAudio.WinMM` or confirm existing package covers `WasapiCapture`.
- New test file: `tests/OpenWSFZ.Audio.Tests/` — unit tests for the STA fix and the subprocess capture sources.
- New test file: `tests/OpenWSFZ.Web.Tests/` — integration test verifying `captureActive` field in status response.
