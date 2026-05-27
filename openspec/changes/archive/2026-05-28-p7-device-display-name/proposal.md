## Why

The status bar, WebSocket status and heartbeat events, and server log messages all display the configured audio device as a raw OS identifier string (e.g. `{0.0.1.00000000}.{eaf691c7-8f15-4559-9591-8287520e768b}`), because `AppConfig.AudioDeviceName` stores the WASAPI device ID, not the human-readable label. `AudioDeviceInfo` already carries both `Id` and `Name` — the friendly name is available at selection time but is never persisted.

## What Changes

- **BREAKING — `AppConfig` field rename**: `audioDeviceName` → `audioDeviceId`. The field always held an OS identifier; the name is corrected to match its actual content.
- **New `AppConfig` field**: `audioDeviceFriendlyName` (nullable string) — the human-readable device label, persisted alongside the device ID.
- **Migration**: config files that contain the legacy `audioDeviceName` key (and no `audioDeviceId`) are read transparently — the value is treated as the device ID; `audioDeviceFriendlyName` defaults to `null`. The operator sees the ID in the status bar until they visit Settings and re-save, at which point both fields are written correctly.
- **Settings page**: the `POST /api/v1/config` body now sends both `audioDeviceId` (the `<select>` option value) and `audioDeviceFriendlyName` (the `<select>` option text). The pre-select logic uses `config.audioDeviceId` instead of `config.audioDeviceName`.
- **Status and heartbeat events**: `DaemonStatus.AudioDevice` is populated with `audioDeviceFriendlyName ?? audioDeviceId`, so a human-readable label always appears when available and the ID is the fallback.
- **Log messages**: all `Program.cs` log interpolations that currently use `AudioDeviceName` switch to `AudioDeviceFriendlyName ?? AudioDeviceId`.

## Capabilities

### New Capabilities

_(none — this change fixes existing behaviour; no new capability is introduced)_

### Modified Capabilities

- `configuration`: `AppConfig` schema changes (field rename + new field); migration behaviour on legacy config files.
- `web-frontend`: Settings page `POST` body and pre-select logic updated to use the renamed and new fields; status bar displays the friendly name.
- `daemon-host`: Log messages use the friendly name with ID fallback.

## Impact

- **`src/OpenWSFZ.Abstractions/AppConfig.cs`**: rename `AudioDeviceName` → `AudioDeviceId`; add `AudioDeviceFriendlyName`.
- **`src/OpenWSFZ.Daemon/Program.cs`**: all references to `AudioDeviceName` updated; log interpolations use friendly name.
- **`src/OpenWSFZ.Web/WebApp.cs`**: `DaemonStatus` construction uses `AudioDeviceFriendlyName ?? AudioDeviceId`.
- **`web/js/settings.js`**: read `audioDeviceId` for pre-select; write both `audioDeviceId` and `audioDeviceFriendlyName` in POST body.
- **`src/OpenWSFZ.Web/AppJsonContext.cs`**: no structural change; `AppConfig` serialisation handles the new field automatically.
- **Existing config files**: remain loadable; migration is silent and non-destructive.
- **No new NuGet dependencies.**
- **Tests**: any test that constructs `AppConfig` with `AudioDeviceName` must be updated to `AudioDeviceId`.
