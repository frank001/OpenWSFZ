## Why

Transmitting FT8 requires routing audio to a specific playback device — typically a
soundcard connected to the transceiver's audio input. Currently OpenWSFZ has no way
to configure which output device the TX pipeline should use; adding this setting now
establishes the plumbing before the TX pipeline is built, so that feature arrives
with device selection already in place.

## What Changes

- Add `audioOutputDeviceId` and `audioOutputFriendlyName` fields to `AppConfig`.
- Add a new `IAudioOutputDeviceProvider` abstraction and WASAPI render-endpoint
  implementation (`DataFlow.Render`) mirroring the existing capture-device provider.
- Expose a new REST endpoint `GET /api/v1/audio/output-devices` that returns the
  enumerated output devices.
- Add an **Audio output device** `<select>` to the Radio hardware tab of
  `settings.html`, populated on page load and persisted via `POST /api/v1/config`.
- Add `getOutputDevices()` to `api.js`.
- Include the output device fields in the `POST /api/v1/config` save payload and
  `GET /api/v1/config` response.

## Capabilities

### New Capabilities

- `audio-output-device`: Enumerating audio render (playback) endpoints and exposing
  them through a REST endpoint and settings UI. Covers the provider abstraction,
  WASAPI implementation, REST endpoint, and config persistence.

### Modified Capabilities

- `configuration`: `AppConfig` gains two nullable string fields —
  `audioOutputDeviceId` and `audioOutputFriendlyName` — and their corresponding
  default-config values (`null`). The `GET`/`POST /api/v1/config` contract is
  extended to include these fields.
- `web-frontend`: The Settings page Radio hardware tab gains an output device
  selector rendered below the existing capture-device selector. The save/cancel
  flow includes the new fields. `api.js` gains `getOutputDevices()`.

## Impact

- **`OpenWSFZ.Abstractions`** — new `IAudioOutputDeviceProvider` interface; `AppConfig`
  record gains two fields.
- **`OpenWSFZ.Audio`** — new `WasapiAudioOutputDeviceProvider` (Windows); new
  `PlatformAudioOutputDeviceProvider` factory; `SubprocessAudioOutputDeviceProvider`
  stub (Linux — no `aplay --list-devices` analogue; returns empty list for now).
- **`OpenWSFZ.Config`** — `ConfigJsonContext` updated for new AppConfig fields.
- **`OpenWSFZ.Web`** — new `AudioOutputDevicesEndpoint` (or inline endpoint in
  `WebApp.cs`); DI registration of `IAudioOutputDeviceProvider`.
- **`web/settings.html`** and **`web/js/settings.js`** / **`web/js/api.js`** —
  UI and API client changes.
- **No breaking changes** — new config fields default to `null`; existing config
  files round-trip without error.
