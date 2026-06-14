## 1. Abstractions — interface and AppConfig fields

- [x] 1.1 Add `IAudioOutputDeviceProvider` interface to `OpenWSFZ.Abstractions` with `Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)`
- [x] 1.2 Add `audioOutputDeviceId` (nullable string, default `null`) and `audioOutputFriendlyName` (nullable string, default `null`) positional parameters to the `AppConfig` record

## 2. Audio layer — provider implementations

- [x] 2.1 Add `WasapiAudioOutputDeviceProvider` in `OpenWSFZ.Audio` (guarded by `#if WASAPI_SUPPORTED`): enumerates `DataFlow.Render` via `MMDeviceEnumerator` on a `StaThread`; mirrors `WasapiAudioDeviceProvider` exactly except for `DataFlow`
- [x] 2.2 Add `SubprocessAudioOutputDeviceProvider` stub in `OpenWSFZ.Audio`: returns `[]` and logs a single Debug message; used on Linux/macOS
- [x] 2.3 Add `PlatformAudioOutputDeviceProvider` factory class in `OpenWSFZ.Audio` that selects the correct implementation based on runtime OS (mirrors `PlatformAudioDeviceProvider`)

## 3. Config serialisation

- [x] 3.1 Update `ConfigJsonContext` in `OpenWSFZ.Config` to include the new `AppConfig` fields (`audioOutputDeviceId`, `audioOutputFriendlyName`) so AOT-safe JSON serialisation works correctly

## 4. REST endpoint

- [x] 4.1 Register `IAudioOutputDeviceProvider` as a singleton (using `PlatformAudioOutputDeviceProvider`) in `WebApp.cs` DI setup
- [x] 4.2 Add `GET /api/v1/audio/output-devices` endpoint in `WebApp.cs` (or alongside the existing `/audio/devices` endpoint): injects `IAudioOutputDeviceProvider`, calls `GetDevicesAsync`, returns JSON array of `{id, name}`

## 5. Frontend — api.js

- [x] 5.1 Add `getOutputDevices()` export to `web/js/api.js`: calls `GET /api/v1/audio/output-devices`, returns `Promise<Array<{id, name}>>`

## 6. Frontend — settings.html

- [x] 6.1 Add `<div class="field-group">` block with `<label for="output-device-select">Audio output device</label>` and `<select id="output-device-select">` immediately below the existing `#device-select` group and above the `#cat-settings` fieldset in the Radio hardware tab

## 7. Frontend — settings.js

- [x] 7.1 Import `getOutputDevices` from `./api.js` alongside the existing imports
- [x] 7.2 Declare `outputDeviceSelect` constant referencing `#output-device-select`
- [x] 7.3 In the page-load `Promise.all`, add `getOutputDevices()` to the parallel fetch calls
- [x] 7.4 Populate `#output-device-select` from the fetched output devices: prepend a "— No device —" option with empty `value`; add one `<option>` per device; pre-select `config.audioOutputDeviceId` (or the placeholder if null or not found)
- [x] 7.5 Wire `#output-device-select` into the dirty-state tracking (same pattern as the other controls)
- [x] 7.6 In the save handler, read `outputDeviceSelect.value` and the selected option's text; include `audioOutputDeviceId` (or `null`) and `audioOutputFriendlyName` (or `null`) in the `POST /api/v1/config` body

## 8. Tests

- [x] 8.1 Add unit tests for `WasapiAudioOutputDeviceProvider` (inject `_enumerateOverride` seam): success path returns `[AudioDeviceInfo]`; failure path returns `[]` and logs Warning
- [x] 8.2 Add unit test for `SubprocessAudioOutputDeviceProvider`: returns empty list without throwing
- [x] 8.3 Add `AppConfig` round-trip tests: config without `audioOutputDeviceId` deserialises to `null`; config with values round-trips correctly
- [x] 8.4 Add integration test for `GET /api/v1/audio/output-devices`: mock `IAudioOutputDeviceProvider` returning one device; assert HTTP 200 and JSON body; second test with empty list asserts `[]`
- [x] 8.5 Verify all 341 existing tests still pass (`dotnet test -c Release`)
