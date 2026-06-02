## Context

OpenWSFZ currently hard-codes `decodeLog.dialFrequencyMHz` as an operator-typed value (default `0.0`). Every ALL.TXT log line and the UI status bar uses this static figure. When the operator redraws to a new band and forgets to update the setting, the log is silently wrong — a subtle but chronic nuisance for serious operators.

A CAT-capable rig is available locally for acceptance testing (COM6, 9600 baud, Windows), already confirmed working with WSJT-X via Hamlib. We do **not** take a Hamlib dependency as a native library — but `rigctld`, Hamlib's companion TCP daemon, is a first-class connection option in this design (see D3).

A practical concern during the transition period: if the operator runs WSJT-X alongside OpenWSFZ to compare the two, both applications would fight over the serial port if direct serial is the only transport. `rigctld` eliminates this: it holds the port exclusively and serves both applications over TCP simultaneously.

CAT is also a required architectural prerequisite for TX (v1.0). The design must not foreclose PTT, frequency-set, or mode-set commands; it must simply not implement them yet.

---

## Goals / Non-Goals

**Goals:**
- Poll VFO-A frequency from the rig via either transport (direct serial or rigctld TCP) at a configurable interval (default 1 s)
- Expose live rig frequency to ALL.TXT logging and the UI status bar without mutating the operator's saved config
- Provide a clean `IRadioConnection` abstraction so future protocols (Hamlib, Icom CI-V, Kenwood) slot in without touching the polling layer
- Gracefully degrade on serial failure — never impact the FT8 decode pipeline
- Keep the radio safe — only `FA;` (read-only frequency query) is ever sent in this change

**Non-Goals:**
- PTT / TX keying (reserved for the TX change)
- Frequency-set or mode-set commands
- Hamlib / rigctld integration (future option)
- Support for protocols beyond `SerialCatConnection` and `RigctldConnection` (both ship in this change; further implementations are future work)
- CAT-driven audio device switching

---

## Decisions

### D1 — New `OpenWSFZ.Rig` project, not a folder in `OpenWSFZ.Daemon`

Rig-specific serial code does not belong in the daemon host. A dedicated `OpenWSFZ.Rig` project gives it a clear home, its own test project, and makes the dependency graph explicit: `Daemon → Rig → Abstractions`. The project is small; the overhead of an extra csproj is outweighed by the separation of concerns. The `OpenWSFZ.Abstractions` project hosts `IRadioConnection` so `Daemon` can depend on the abstraction without a direct reference to `Rig`.

**Rejected:** putting `IRadioConnection` and `SerialCatConnection` inside `OpenWSFZ.Daemon` — conflates deployment unit with protocol implementation and makes the interface untestable without spinning up a full daemon.

### D2 — `ICatState` singleton, not mutation of `IConfigStore`

The polling service must not overwrite `IConfigStore.Current.DecodeLog.DialFrequencyMHz` on every poll. That field is the operator's intentional configuration; overwriting it live would make the Settings page show a flickering read-only value and would persist the rig's current frequency if the operator saves mid-session.

Instead, a new `ICatState` singleton (registered as a scoped/singleton in DI) holds the latest polled frequency and connection status. Consumers that need the effective dial frequency call a helper:

```
effectiveFreq = catState.DialFrequencyMHz ?? configStore.Current.DecodeLog.DialFrequencyMHz
```

`AllTxtWriter`, `DaemonStatus`, and WebSocket heartbeats all use this helper. When CAT is disabled or in error, they fall back to the operator's configured value transparently.

**Rejected:** mutating `IConfigStore` — blurs the line between persisted config and live telemetry, causes Settings page confusion, and risks persisting a rig frequency the operator did not explicitly choose.

### D3 — Two transport implementations: `SerialCatConnection` and `RigctldConnection`

Both ship in this change. The operator picks via `cat.rigModel` (`"SerialCat"` or `"RigCtld"`). Default is `"SerialCat"` since it requires no external process.

**`SerialCatConnection`** uses `System.IO.Ports.SerialPort` — cross-platform, no external dependency, self-contained. The serial CAT `FA;` command is two bytes sent and a 15-byte response; no complex framing or state machine is needed. Owns the serial port exclusively while connected; fails with `UnauthorizedAccessException` if another application (e.g. WSJT-X) already holds it.

**`RigctldConnection`** opens a `TcpClient` to `rigctld` (default `127.0.0.1:4532`) and exchanges plain ASCII: send `\get_freq\n`, receive the frequency in Hz as a decimal string. `rigctld` is Hamlib's companion daemon; it holds the serial port and serves any number of TCP clients simultaneously, making side-by-side WSJT-X and OpenWSFZ operation conflict-free. `RigctldConnection` carries zero native dependency in OpenWSFZ — it is a 40-line TCP client. The operator is responsible for running `rigctld` before enabling this mode.

**Why not Hamlib as a native library?** Linking against `libhamlib` directly would require shipping a native binary for each of the three target platforms, version-pinning it, and adding LGPL-2.1 licence obligations. The rigctld TCP interface gives the same rig-coverage benefit (850+ rigs) without any of those costs. A native `HamlibRadioConnection` remains a future option if an operator's workflow demands it, but it is not needed now.

### D4 — `CatPollingService` hot-reloads on config change

When the operator toggles CAT enabled/disabled, changes the port, or changes the baud rate in Settings and saves, `CatPollingService` detects the change (via `IConfigStore` change notification or a comparison on each poll iteration), disconnects the current connection, and re-initialises with the new parameters. This matches the hot-reload behaviour established by FR-030 for logging config and avoids requiring a daemon restart for CAT changes.

### D5 — WebSocket event only on frequency change or state change

Emitting a WebSocket frame on every 1-second poll when the frequency has not changed is wasteful and pollutes the browser's event log. `CatPollingService` compares the newly polled value against the last-emitted value and only pushes a `cat_status` WebSocket event when:
- The frequency changes by ≥ 1 Hz, OR
- The connection state changes (connected ↔ disconnected ↔ error)

The existing heartbeat already carries `dialFrequencyMHz` (via `DaemonStatus`), so the browser always has a fresh value every 5 seconds regardless.

### D6 — Serial port timeout: 500 ms read, 2 s reconnect backoff

All serial I/O is guarded by a 500 ms `ReadTimeout`. If a response does not arrive within that window, the command is treated as a failure, the connection is marked `Error`, a Warning is logged, and the polling loop sleeps for 2 s before attempting a reconnect. This ensures a locked or absent rig does not hold a thread. The 500 ms value is generous for a local USB serial device; a responsive rig on a direct USB connection typically replies within 10–20 ms.

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| COM port already in use (operator still has WSJT-X open) | `SerialPort.Open()` throws `UnauthorizedAccessException`; caught, logged at Error, CAT state set to `Error`. Operator sees the indicator; CAT retries on next poll cycle after the 2 s backoff. |
| Rig firmware differences silently changing `FA;` response format | Response validated by prefix `FA` and length 15 before parsing. Any parse failure logs Warning + raw response string for diagnosis and falls back gracefully. |
| `System.IO.Ports` not available on a given platform | Package is in NuGet; CI will catch a missing transitive dep. Confirmed present on win-x64, linux-x64, osx-arm64 in .NET 10. |
| CAT polling adds latency to decode pipeline | `CatPollingService` runs on its own `Timer`-driven loop, completely independent of the audio/decode pipeline. No shared locks; frequency reads are `volatile`/`Interlocked`-protected in `ICatState`. |
| Operator accidentally sends rig-altering commands in a future change | `IRadioConnection` exposes only `GetDialFrequencyMhzAsync` in this change. Transmit-side methods (`SetFrequencyAsync`, `KeyPttAsync`) are added only in the TX phase, not now. |
| Manual smoke test can't run in CI (no hardware) | CAT unit tests mock `IRadioConnection`. Manual acceptance gate is documented in tasks. The G1/G6 CI gates are unaffected. |
| `rigctld` not running when `RigCtld` mode is selected | `TcpClient.Connect` fails; caught, logged at Error, CAT enters `Error` state, retries after 2 s. Same graceful degradation as a missing serial port. Operator is reminded in the Settings page that `rigctld` must be running. |
| `rigctld` response is not a plain decimal Hz value (old version, error response) | Response trimmed and parsed with `long.TryParse`; failure logs Warning with raw response and falls back. `rigctld` error responses begin with `RPRT` and will fail the parse cleanly. |

---

## Migration Plan

1. `OpenWSFZ.Rig` project and `IRadioConnection` are additive — no existing code changes until wiring.
2. `AppConfig` gains a nullable `Cat` property; deserialisation defaults to `null` (CAT disabled). Existing config files are unaffected — round-trip fidelity is preserved.
3. DI registration adds `CatPollingService` and `ICatState`; the polling service starts in disabled state and does nothing until the operator enables CAT in Settings.
4. `AllTxtWriter` and `DaemonStatus` are updated to read from `ICatState` with fallback — this is a drop-in change, no behaviour difference when CAT is disabled.
5. Rollback: set `cat.enabled = false` in config (or remove the `cat` key). The daemon behaves exactly as it did before this change.

---

## Open Questions

| # | Question | Owner | Resolution |
|---|---|---|---|
| 1 | Should the Settings page allow the operator to enter a port name manually (text field) or select from an enumerated list of available serial ports? An enumerated list (`SerialPort.GetPortNames()`) is friendlier but adds UI complexity. | Captain | Propose: manual text field for v0.x; enumerated list is a Settings UX improvement for a later change. |
| 2 | Should `cat.rigModel` be a free-form string or an enum? Enum is safer for DI factory lookup; free-form is easier to extend. | ~~Architect~~ | **Resolved:** enum with two known values — `"SerialCat"` and `"RigCtld"` — both shipping in this change. Unknown values log Warning and disable CAT. |
| 3 | Should CAT config changes (port, baud) take effect on next poll or require an explicit reconnect button? | Captain | Propose: automatic reconnect on config save (consistent with FR-030 hot-reload principle). |
