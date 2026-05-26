## 1. Requirements Registration

- [x] 1.1 Add `FR-025` to `REQUIREMENTS.md`: *Audio device friendly name display — the daemon SHALL persist the human-readable audio device label alongside the OS device identifier; the label SHALL be displayed in the status bar, WebSocket status and heartbeat events, and log messages; when no label is stored (legacy or unconfigured), the OS identifier SHALL be used as a fallback*

## 2. AppConfig Schema

- [x] 2.1 In `src/OpenWSFZ.Abstractions/AppConfig.cs`, rename the `AudioDeviceName` parameter to `AudioDeviceId` and add a new `AudioDeviceFriendlyName` parameter:
  ```csharp
  // Before:
  public record AppConfig(
      string? AudioDeviceName = null,
      int     Port            = 8080,
      ...);

  // After:
  public record AppConfig(
      string? AudioDeviceId           = null,
      string? AudioDeviceFriendlyName = null,
      int     Port                    = 8080,
      ...);
  ```
- [x] 2.2 Verify `dotnet build -c Release` fails with clear compile errors at every callsite that used `AudioDeviceName` — this confirms the full impact is visible before fixes begin

## 3. Migration in JsonConfigStore

- [x] 3.1 In `JsonConfigStore.Load()`, after `JsonSerializer.Deserialize`, add a post-load migration block: if the returned `AppConfig.AudioDeviceId` is null, parse the raw JSON string with `JsonDocument` and look for a `audioDeviceName` property; if found and non-null, return `config with { AudioDeviceId = legacyValue }`:
  ```csharp
  var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)
      ?? new AppConfig();

  // Migrate legacy audioDeviceName → audioDeviceId (p7 rename).
  if (config.AudioDeviceId is null)
  {
      using var doc = JsonDocument.Parse(json);
      if (doc.RootElement.TryGetProperty("audioDeviceName", out var legacy) &&
          legacy.ValueKind == JsonValueKind.String)
      {
          config = config with { AudioDeviceId = legacy.GetString() };
      }
  }

  return config;
  ```
- [x] 3.2 Confirm `ConfigJsonContext` (in `src/OpenWSFZ.Config/`) has `AppConfig` registered — no new registration should be needed, but verify after the rename

## 4. Server-Side Callsite Fixes

- [x] 4.1 In `src/OpenWSFZ.Web/WebApp.cs` line 131, replace `store.Current.AudioDeviceName` with `store.Current.AudioDeviceFriendlyName ?? store.Current.AudioDeviceId`
- [x] 4.2 In `src/OpenWSFZ.Web/WebSocketHub.cs` line 138, apply the same substitution: `configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId`
- [x] 4.3 In `src/OpenWSFZ.Daemon/Program.cs`, fix all eight references:
  - Lines 132, 165, 198, 228: `configStore.Current.AudioDeviceName` → `configStore.Current.AudioDeviceId` (used to pass the ID to `CaptureManager.StartAsync` — must remain the raw ID, not the friendly name)
  - Line 231: `newConfig.AudioDeviceName` → `newConfig.AudioDeviceId`
  - Lines 126, 175: log interpolations → use `configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId` so the log reads the human-readable name
- [x] 4.4 Verify `dotnet build -c Release` exits 0 with no warnings

## 5. Settings Page — JavaScript

- [x] 5.1 In `web/js/settings.js` line 49, change the pre-select logic from `config.audioDeviceName` to `config.audioDeviceId`:
  ```js
  // Before:
  deviceSelect.value = config.audioDeviceName ?? '';
  // After:
  deviceSelect.value = config.audioDeviceId ?? '';
  ```
- [x] 5.2 In `web/js/settings.js` in the Save handler, replace the single `audioDeviceName` field in the POST body with `audioDeviceId` and `audioDeviceFriendlyName`:
  ```js
  // Before:
  const audioDeviceName = deviceSelect.value.trim() || null;
  await postConfig({ audioDeviceName, port, ... });

  // After:
  const audioDeviceId           = deviceSelect.value.trim() || null;
  const selectedOption          = deviceSelect.options[deviceSelect.selectedIndex];
  const audioDeviceFriendlyName = audioDeviceId
      ? (selectedOption?.textContent?.trim() || null)
      : null;
  await postConfig({ audioDeviceId, audioDeviceFriendlyName, port, ... });
  ```

## 6. Test Updates

- [x] 6.1 In `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs`:
  - Update all `AppConfig(AudioDeviceName: ...)` constructions to `AppConfig(AudioDeviceId: ...)`
  - Update all `store.Current.AudioDeviceName` assertions to `store.Current.AudioDeviceId`
  - Convert the existing test at line 125 (which reads `{"audioDeviceName":"TestMic","port":9090}`) into a migration test: assert `store.Current.AudioDeviceId == "TestMic"` and `store.Current.AudioDeviceFriendlyName == null`
  - Add a new test: `FR-025: Legacy audioDeviceName config migrates to AudioDeviceId on load` — write a config file with `{"audioDeviceName":"LegacyDevice","port":8080}`, load it, assert `AudioDeviceId == "LegacyDevice"` and `AudioDeviceFriendlyName == null`
  - Add a new test: `FR-025: AudioDeviceFriendlyName is stored and round-trips` — save a config with both fields populated; reload; assert both values survive
- [x] 6.2 In `tests/OpenWSFZ.Config.Tests/ConfigPathResolverTests.cs` line 78: update `.AudioDeviceName.Should().BeNull()` → `.AudioDeviceId.Should().BeNull()`
- [x] 6.3 In `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs`:
  - Line 137–138: assert `audioDeviceId` field is present (not `audioDeviceName`)
  - Line 153: change POST payload from `{"audioDeviceName":"NewMic","port":9090}` to `{"audioDeviceId":"NewMic","audioDeviceFriendlyName":"New Mic Label","port":9090}`
  - Lines 162, 169: assert `audioDeviceId` (and optionally `audioDeviceFriendlyName`) from the response

## 7. Traceability and Build Verification

- [x] 7.1 Add `[Fact(DisplayName = "FR-025: Legacy audioDeviceName config migrates to AudioDeviceId on load")]` and `[Fact(DisplayName = "FR-025: AudioDeviceFriendlyName is stored and round-trips")]` to the new tests from task 6.1
- [x] 7.2 Verify `dotnet build -c Release` exits 0 with 0 warnings across all projects
- [x] 7.3 Verify `dotnet test -c Release` exits 0 — all existing tests green, new migration tests pass
- [ ] 7.4 Manual smoke test: start the daemon, open Settings, select a device, save — confirm the status bar shows the human-readable device label (e.g. "Jabra EVOLVE LINK") rather than the GUID; confirm `config.json` now contains `audioDeviceId` and `audioDeviceFriendlyName`; confirm legacy `config.json` with only `audioDeviceName` still starts capture correctly
