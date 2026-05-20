## 1. Scaffolding

- [x] 1.1 Create `src/OpenWSFZ.Audio/OpenWSFZ.Audio.csproj` — class library targeting `net10.0`, `Nullable enable`, `TreatWarningsAsErrors true`; add to `OpenWSFZ.slnx`.
- [x] 1.2 Create `src/OpenWSFZ.Config/OpenWSFZ.Config.csproj` — class library targeting `net10.0`, `Nullable enable`, `TreatWarningsAsErrors true`; add to `OpenWSFZ.slnx`.
- [x] 1.3 Create `tests/OpenWSFZ.Audio.Tests/OpenWSFZ.Audio.Tests.csproj` — xUnit project referencing `OpenWSFZ.Audio` and `coverlet.collector`; add to `OpenWSFZ.slnx`.
- [x] 1.4 Create `tests/OpenWSFZ.Config.Tests/OpenWSFZ.Config.Tests.csproj` — xUnit project referencing `OpenWSFZ.Config` and `coverlet.collector`; add to `OpenWSFZ.slnx`.
- [x] 1.5 Add required NuGet versions to `Directory.Packages.props`: `NAudio` (Windows WASAPI enumeration).
- [x] 1.6 Add project references: `OpenWSFZ.Audio` → `OpenWSFZ.Abstractions`; `OpenWSFZ.Config` → `OpenWSFZ.Abstractions`; `OpenWSFZ.Daemon` → `OpenWSFZ.Audio` and `OpenWSFZ.Config`; `OpenWSFZ.Web` → `OpenWSFZ.Audio` and `OpenWSFZ.Config`.

## 2. Abstractions

- [x] 2.1 Add `AudioDeviceInfo` record to `OpenWSFZ.Abstractions` with `Id` (string) and `Name` (string) properties.
- [x] 2.2 Add `IAudioDeviceProvider` interface to `OpenWSFZ.Abstractions` with `Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct)`.
- [x] 2.3 Add `AppConfig` record to `OpenWSFZ.Config` with `AudioDeviceName` (string?, default null) and `Port` (int, default 8080).
- [x] 2.4 Add `IConfigStore` interface to `OpenWSFZ.Abstractions` with `AppConfig Current { get; }` and `Task SaveAsync(AppConfig config, CancellationToken ct)`.

## 3. Audio device implementation

- [x] 3.1 Implement `WasapiAudioDeviceProvider : IAudioDeviceProvider` in `OpenWSFZ.Audio` — uses `NAudio.Wasapi` `MMDeviceEnumerator` to list capture endpoints; returns `AudioDeviceInfo` list. Guard with `[SupportedOSPlatform("windows")]`.
- [x] 3.2 Implement `SubprocessAudioDeviceProvider : IAudioDeviceProvider` in `OpenWSFZ.Audio` — accepts the command and arguments as constructor parameters; parses stdout into `AudioDeviceInfo` records; returns empty list on non-zero exit or missing tool. Used for Linux (`arecord --list-devices`) and macOS (`system_profiler SPAudioDataType -json`).
- [x] 3.3 Implement `PlatformAudioDeviceProvider : IAudioDeviceProvider` in `OpenWSFZ.Audio` — dispatches to `WasapiAudioDeviceProvider` on Windows, appropriate `SubprocessAudioDeviceProvider` on Linux/macOS, using `RuntimeInformation.IsOSPlatform`. Registered as the concrete implementation in DI.

## 4. Configuration implementation

- [x] 4.1 Implement `JsonConfigStore : IConfigStore` in `OpenWSFZ.Config` — loads from a file path at construction time (or creates default if absent); writes atomically via temp-file-then-rename; uses a `[JsonSerializable]` source-generated context for AOT safety.
- [x] 4.2 Add `ConfigJsonContext : JsonSerializerContext` to `OpenWSFZ.Config` with `[JsonSerializable(typeof(AppConfig))]`.
- [x] 4.3 Implement `ConfigPathResolver` static helper in `OpenWSFZ.Config` — resolves the config path from (1) supplied override, (2) `OPENWSFZ_CONFIG` env var, (3) platform default (`Environment.GetFolderPath(ApplicationData)/OpenWSFZ/config.json`).

## 5. Daemon wiring

- [x] 5.1 Extend `LaunchOptions` in `OpenWSFZ.Daemon` with a `ConfigPath` property (string?, default null); wire `--config <path>` argument parsing before host construction.
- [x] 5.2 In `Program.cs`, resolve the config path via `ConfigPathResolver`, log it at startup (source + resolved path), initialise `JsonConfigStore`, and register `IConfigStore` as a singleton in DI.
- [x] 5.3 Register `PlatformAudioDeviceProvider` as `IAudioDeviceProvider` singleton in `Program.cs` via DI.
- [x] 5.4 Read `AppConfig.Port` from the loaded config and use it as the default port (still overridable by `--port`; CLI flag wins).

## 6. Web server — updated status and new endpoints

- [x] 6.1 Extend `DaemonStatus` record in `OpenWSFZ.Web` to add `AudioDevice` (string?) property; update `AppJsonContext` serialisation context accordingly.
- [x] 6.2 Update `GET /api/v1/status` endpoint to populate `AudioDevice` from `IConfigStore.Current.AudioDeviceName`.
- [x] 6.3 Add `GET /api/v1/audio/devices` endpoint — calls `IAudioDeviceProvider.GetDevicesAsync()` and returns the list as JSON; add `AudioDeviceInfo` and `IReadOnlyList<AudioDeviceInfo>` to `AppJsonContext`.
- [x] 6.4 Add `GET /api/v1/config` endpoint — returns `IConfigStore.Current` serialised as JSON; add `AppConfig` to `AppJsonContext`.
- [x] 6.5 Add `POST /api/v1/config` endpoint — deserialises the request body as `AppConfig`; calls `IConfigStore.SaveAsync()`; returns the updated config with HTTP 200; returns HTTP 400 on malformed JSON.

## 7. Unit tests — audio

- [x] 7.1 Write `"FR-003: GetDevicesAsync returns empty list when subprocess exits non-zero"` — in `OpenWSFZ.Audio.Tests`; uses a fake subprocess that exits 1; asserts empty list, no exception.
- [x] 7.2 Write `"FR-003: GetDevicesAsync returns empty list when tool is absent"` — subprocess command is a non-existent binary; asserts empty list.
- [x] 7.3 Write `"FR-003: SubprocessAudioDeviceProvider parses arecord output correctly"` — feeds sample `arecord` stdout to the parser; asserts correct `Id` and `Name` values.

## 8. Unit tests — config

- [x] 8.1 Write `"FR-004: JsonConfigStore loads existing config file"` — writes a known JSON file to a temp path; loads it; asserts correct field values.
- [x] 8.2 Write `"FR-004: JsonConfigStore creates default config when file absent"` — points store at a non-existent path; asserts file is created with default values and no exception thrown.
- [x] 8.3 Write `"FR-004: JsonConfigStore.SaveAsync writes atomically"` — saves config; asserts the target file exists and contains the expected JSON; verifies no temp file remains.
- [x] 8.4 Write `"FR-005: ConfigPathResolver returns CLI flag path when provided"` — asserts CLI flag path takes precedence.
- [x] 8.5 Write `"FR-005: ConfigPathResolver falls back to OPENWSFZ_CONFIG env var"` — sets env var; no flag; asserts env-var path returned.
- [x] 8.6 Write `"FR-005: ConfigPathResolver returns platform default when no override"` — no flag, no env var; asserts path ends with `OpenWSFZ/config.json`.
- [x] 8.7 Write `"FR-006: Default config contains expected fields"` — asserts `AudioDeviceName` is null and `Port` is 8080.

## 9. Integration tests — web server

- [x] 9.1 Write `"FR-003: GET /api/v1/audio/devices returns 200 with JSON array"` — in `OpenWSFZ.Web.Tests`; asserts HTTP 200, `Content-Type: application/json`, and a JSON array body.
- [x] 9.2 Write `"FR-004: GET /api/v1/config returns 200 with current config"` — asserts HTTP 200 and JSON body containing `audioDeviceName` and `port` fields.
- [x] 9.3 Write `"FR-004: POST /api/v1/config persists and returns updated config"` — posts a valid config body; asserts HTTP 200 and updated values in response; subsequent GET returns same values.
- [x] 9.4 Write `"FR-004: POST /api/v1/config returns 400 for malformed JSON"` — posts `{ broken` as body; asserts HTTP 400.
- [x] 9.5 Write `"FR-002: GET /api/v1/status includes audioDevice field"` — asserts the `audioDevice` field is present in the status JSON (may be null).
- [x] 9.6 Write `"FR-002: WebSocket status event payload includes audioDevice field"` — connects via WebSocket; asserts `payload.audioDevice` field present in the initial status frame.

## 10. Debt file and CI update

- [x] 10.1 Remove FR-003, FR-004, FR-005, FR-006 from `traceability-debt.md` — these requirements now have test coverage.
- [x] 10.2 Add `OpenWSFZ.Audio.Tests.dll` and `OpenWSFZ.Config.Tests.dll` to the `--assemblies` list in the Gate G3 (TraceabilityCheck) step in `.github/workflows/ci.yml`. (CI already uses `find . -path "*/bin/Release/net10.0/*.Tests.dll"` glob — no change needed.)

## 11. Exit gate verification (M3)

- [x] 11.1 Run `dotnet build -c Release` — confirm zero errors, zero warnings.
- [x] 11.2 Run `dotnet test -c Release --no-build` — confirm all tests pass including the new audio and config unit tests.
- [x] 11.3 Run TraceabilityCheck locally — confirm FR-003, FR-004, FR-005, FR-006 are mapped and no stale debt entries remain for those IDs.
- [x] 11.4 Run LicenseInventoryCheck locally — confirm NAudio licence passes the allow-list (MIT / Ms-PL). (Fixed: added `KnownFileLicences` table for `<license type="file">` packages.)
- [x] 11.5 Publish `OpenWSFZ.Daemon` AOT for the current RID, launch the binary, confirm `GET /api/v1/audio/devices` returns a JSON array, `GET /api/v1/config` returns the default config, and the WebSocket status event includes the `audioDevice` field.
