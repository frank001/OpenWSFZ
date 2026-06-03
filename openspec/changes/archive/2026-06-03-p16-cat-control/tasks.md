## 1. Requirements & Project Setup

- [x] 1.1 Add FR-031 through FR-034 to `REQUIREMENTS.md` (CAT connection config, frequency readout, UI status, graceful degradation); bump document version to 1.15
- [x] 1.2 Add `System.IO.Ports` to `Directory.Packages.props` (pinned version)
- [x] 1.3 Create `src/OpenWSFZ.Rig/OpenWSFZ.Rig.csproj` referencing `OpenWSFZ.Abstractions` and `System.IO.Ports`
- [x] 1.4 Create `tests/OpenWSFZ.Rig.Tests/OpenWSFZ.Rig.Tests.csproj` referencing `OpenWSFZ.Rig`, xUnit, and a mocking library
- [x] 1.5 Add both new projects to `OpenWSFZ.slnx`

## 2. Abstractions

- [x] 2.1 Add `IRadioConnection` interface to `OpenWSFZ.Abstractions` (`ConnectAsync`, `DisconnectAsync`, `GetDialFrequencyMhzAsync`, `IsConnected`)
- [x] 2.2 Add `CatConnectionStatus` enum to `OpenWSFZ.Abstractions` (`Disabled`, `Connecting`, `Connected`, `Error`)
- [x] 2.3 Add `ICatState` interface to `OpenWSFZ.Abstractions` (`DialFrequencyMHz`, `Status`)

## 3. Configuration Model

- [x] 3.1 Add `CatConfig` class: `Enabled`, `RigModel`, `SerialPort`, `BaudRate`, `RigctldHost` (default `"127.0.0.1"`), `RigctldPort` (default `4532`), `PollIntervalSeconds` with appropriate defaults and JSON property names
- [x] 3.2 Add `Cat` property of type `CatConfig` (nullable, defaulting to disabled) to `AppConfig`
- [x] 3.3 Update default config generation to include `"cat": { "enabled": false }` in the written file
- [x] 3.4 Verify round-trip: existing config files without a `cat` key deserialise without error and `Cat.Enabled` is `false`

## 4. SerialCatConnection

- [x] 4.1 Implement `SerialCatConnection : IRadioConnection, IDisposable` in `OpenWSFZ.Rig` using `System.IO.Ports.SerialPort`, 8N1, 500 ms `ReadTimeout`
- [x] 4.2 Implement `ConnectAsync` — opens the port; propagates `UnauthorizedAccessException` / `IOException` on failure
- [x] 4.3 Implement `GetDialFrequencyMhzAsync` — writes `FA;\r` (serial CAT protocol uses CR terminator), reads until `;`, validates prefix `FA` and length 14, parses 11-digit Hz value, returns MHz
- [x] 4.4 Implement `DisconnectAsync` and `Dispose` — close and dispose `SerialPort` if open

## 5. RigctldConnection

- [x] 5.1 Implement `RigctldConnection : IRadioConnection, IDisposable` in `OpenWSFZ.Rig` using `TcpClient`, 500 ms receive timeout
- [x] 5.2 Implement `ConnectAsync` — opens TCP connection to `rigctldHost:rigctldPort`; propagates `SocketException` on failure
- [x] 5.3 Implement `GetDialFrequencyMhzAsync` — sends `\get_freq\n`, reads response line, validates it is a non-negative integer (not `RPRT`), divides by 1 000 000 to return MHz
- [x] 5.4 Implement `DisconnectAsync` and `Dispose` — close and dispose `TcpClient` if connected
- [x] 5.5 Add `RigModelFactory` static helper that maps `"SerialCat"` → `SerialCatConnection` and `"RigCtld"` → `RigctldConnection`; unknown values throw `ArgumentException`

## 6. CatState

- [x] 6.1 Implement `CatState : ICatState` in `OpenWSFZ.Daemon` with thread-safe `DialFrequencyMHz` (using `Interlocked.Exchange` on a `long`-backed bit representation) and `volatile CatConnectionStatus Status`
- [x] 6.2 Expose internal `Update(double? freqMHz, CatConnectionStatus status)` method for `CatPollingService` to call

## 7. CatPollingService

- [x] 7.1 Implement `CatPollingService : IHostedService, IAsyncDisposable` in `OpenWSFZ.Daemon`
- [x] 7.2 On `StartAsync`: if `Cat.Enabled` is false, set `ICatState.Status = Disabled` and return; otherwise use `RigModelFactory` to resolve `IRadioConnection` from `Cat.RigModel`, then call `ConnectAsync`; on failure log Error, set status `Error`, and schedule retry
- [x] 7.3 Polling loop: call `GetDialFrequencyMhzAsync` at `PollIntervalSeconds` interval; on success update `ICatState`; on failure log Warning, set `Error`, wait 2 s, attempt reconnect
- [x] 7.4 Config hot-reload: on each poll iteration compare current `CatConfig` snapshot against the live `IConfigStore.Current.Cat`; if changed, disconnect and reinitialise with new parameters (including switching transport if `RigModel` changed)
- [x] 7.5 On `StopAsync`: cancel the polling loop, call `DisconnectAsync`, complete within 3 s

## 8. WebSocket cat_status Event

- [x] 8.1 Define `cat_status` WebSocket message type in the WebSocket hub / event bus with payload `{ status: string, dialFrequencyMHz: number | null }`
- [x] 8.2 Wire `CatPollingService` to push `cat_status` event when `ICatState.Status` changes or `DialFrequencyMHz` changes by ≥ 1 Hz
- [x] 8.3 Update `DaemonStatus` and heartbeat payload to resolve `dialFrequencyMHz` using the effective precedence rule (`ICatState.DialFrequencyMHz ?? AppConfig.DecodeLog.DialFrequencyMHz`)

## 9. AllTxtWriter & DaemonStatus Integration

- [x] 9.1 Update `AllTxtWriter` to resolve dial frequency via the effective precedence rule (inject `ICatState`)
- [x] 9.2 Update `DaemonStatus` / status WebSocket event to include the effective `dialFrequencyMHz`
- [x] 9.3 Verify that when `ICatState.DialFrequencyMHz` is null, `AllTxtWriter` falls back to `AppConfig.DecodeLog.DialFrequencyMHz` (no regression)

## 10. REST API

- [x] 10.1 Update `GET /api/v1/config` response to include the `cat` object (all seven fields)
- [x] 10.2 Update `POST /api/v1/config` to accept and persist the `cat` object
- [x] 10.3 Validate `pollIntervalSeconds` on POST: clamp to [1, 60] with Warning if out of range; validate `rigModel` is a known value; return 400 on malformed JSON (existing behaviour)

## 11. DI Wiring

- [x] 11.1 Register `CatState` as `ICatState` singleton in `Program.cs` / DI setup
- [x] 11.2 Register `RigModelFactory`-resolved `IRadioConnection` as a transient or scoped service based on `AppConfig.Cat`
- [x] 11.3 Register `CatPollingService` as a hosted service

## 12. Settings Page UI

- [x] 12.1 Add CAT section to `settings.html`: enable toggle, `rigModel` selector (`SerialCat` / `RigCtld`), serial port field, baud rate field, rigctld host field, rigctld port field, poll interval field — show/hide serial vs. rigctld fields based on selected `rigModel`
- [x] 12.2 Populate and save all CAT fields via the existing `GET`/`POST /api/v1/config` flow in `settings.js`
- [x] 12.3 Display CAT connection status within the Settings CAT section (read-only indicator: Connected / Error / Disabled) and a note when `RigCtld` is selected that `rigctld` must be running before enabling

## 13. Main Page UI

- [x] 13.1 Update the status bar in `index.html` to display the effective dial frequency formatted as `14.074 MHz` (or `0.000 MHz` when zero)
- [x] 13.2 Add a CAT indicator badge to the status bar that shows `Connected` (green), `Error` (red/amber), or is absent when `Disabled`
- [x] 13.3 Handle `cat_status` WebSocket events in `ws.js` / `main.js` to update the frequency and indicator without a page reload

## 14. Tests

- [x] 14.1 `SerialCatConnection` unit tests (mock/stub serial port): `ConnectAsync` happy path, port-in-use failure, `GetDialFrequencyMhzAsync` parses `FA00014074000;` → `14.074`, malformed response throws, timeout throws — prefix `P16-Cat:`
- [x] 14.2 `RigctldConnection` unit tests (mock TCP): `ConnectAsync` happy path, connection refused, `GetDialFrequencyMhzAsync` parses `14074000` → `14.074`, `RPRT` error response throws, timeout throws — prefix `P16-Cat:`
- [x] 14.3 `CatPollingService` unit tests (mock `IRadioConnection`): polls at interval, updates `ICatState`, handles `ConnectAsync` failure gracefully, stops cleanly, config hot-reload triggers reconnect, `RigModel` change switches transport — prefix `P16-Cat:`
- [x] 14.4 `CatConfig` config schema tests: missing `cat` key defaults to disabled, `"SerialCat"` accepted, `"RigCtld"` accepted, unknown rigModel → Warning + disabled, `pollIntervalSeconds` clamped — prefix `P16-Cat:`
- [x] 14.5 `AllTxtWriter` effective-frequency tests: `ICatState` value takes precedence; null `ICatState` falls back to config — prefix `P16-Cat:`
- [x] 14.6 `GET`/`POST /api/v1/config` integration tests: full `cat` object (including `rigctldHost` and `rigctldPort`) round-trips correctly — prefix `P16-Cat:`

## 15. Acceptance Gate — Serial CAT mode (manual, hardware required)

- [x] 15.1 Set `cat.rigModel = "SerialCat"`, `cat.serialPort = "COM6"`, `cat.baudRate = 9600`, `cat.enabled = true`; start the daemon
- [x] 15.2 Verify the status bar shows the rig's current VFO-A frequency within 2 poll intervals
- [x] 15.3 Tune the rig to a different frequency; verify the status bar updates within 2 poll intervals
- [x] 15.4 Verify ALL.TXT log lines show the correct rig frequency when CAT is active
- [x] 15.5 Unplug the serial cable; verify the daemon logs a Warning, shows the Error indicator, and continues decoding without crashing
- [x] 15.6 Reconnect; verify CAT reconnects automatically and the indicator returns to Connected
- [x] 15.7 Confirm no rig-altering commands were sent throughout — observe the rig display

## 16. Acceptance Gate — rigctld mode (manual, hardware required)

- [x] 16.1 Start `rigctld` pointing at the test rig (e.g. `rigctld -m <model-id> -r COM6 -s 9600`)
- [x] 16.2 Set `cat.rigModel = "RigCtld"`, `cat.rigctldHost = "127.0.0.1"`, `cat.rigctldPort = 4532`, `cat.enabled = true`; start the daemon
- [x] 16.3 Verify the status bar shows the rig's current VFO-A frequency within 2 poll intervals
- [x] 16.4 Verify that a second application can connect to `rigctld` simultaneously (confirms no port conflict)
- [x] 16.5 Stop `rigctld`; verify the daemon logs a Warning, shows the Error indicator, and continues decoding without crashing
- [x] 16.6 Restart `rigctld`; verify CAT reconnects automatically
- [x] 16.7 Confirm no rig-altering commands were sent throughout

## 17. Housekeeping

- [x] 17.1 Commit all changes with `feat(p16): CAT control — serial CAT frequency readout`
- [x] 17.2 Push and confirm CI green (G1 build/test, G3 traceability, G5 licence, G7 secrets scan)
- [x] 17.3 Open PR to `main`; request QA gate review — https://github.com/frank001/OpenWSFZ/pull/20
