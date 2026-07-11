## ADDED Requirements

### Requirement: ExternalReportingService is inert by default

A new `ExternalReportingService : IHostedService` SHALL be registered unconditionally in the DI
container. When `AppConfig.ExternalReporting.Enabled` is `false` (the default) or
`AppConfig.ExternalReporting.Targets` is empty, the service SHALL open no sockets, send no
datagrams, and listen for none. Config files without an `externalReporting` key SHALL deserialise to
these defaults and SHALL behave identically to a config file that explicitly disables the feature.

#### Scenario: Missing config key is fully inert

- **WHEN** the daemon starts with a config file containing no `externalReporting` key
- **THEN** `ExternalReportingService` SHALL start successfully and open no UDP sockets

#### Scenario: Enabling with no targets is inert

- **WHEN** `externalReporting.enabled` is `true` and `targets` is an empty array
- **THEN** no outbound socket SHALL be opened and no datagrams SHALL be sent

---

### Requirement: Multiple simultaneous outbound targets

`AppConfig.ExternalReporting.Targets` SHALL be a list of `{ name: string, host: string, port: int,
enabled: bool }` entries. Every entry with `enabled = true` SHALL receive an identical copy of every
outbound datagram (Heartbeat, Status, Decode, Clear, QSOLogged, Close) sent by this service. Entries
with `enabled = false` SHALL be skipped without error. A target whose `host` fails to resolve SHALL
log a Warning once per resolution failure and SHALL NOT prevent delivery to other configured targets.

#### Scenario: Two enabled targets both receive a Decode datagram

- **WHEN** two targets are configured and enabled (`GridTracker2` at `127.0.0.1:2237` and a second
  entry at `127.0.0.1:2238`) and a decode cycle produces one decoded message
- **THEN** an identical Decode datagram SHALL be sent to both `127.0.0.1:2237` and `127.0.0.1:2238`

#### Scenario: Disabled target is skipped

- **WHEN** a configured target has `enabled = false`
- **THEN** no datagram of any type SHALL be sent to that target's host/port

#### Scenario: Unresolvable host does not block other targets

- **WHEN** one of two enabled targets has a `host` that fails DNS/address resolution
- **THEN** a Warning SHALL be logged for that target and the other, resolvable target SHALL still
  receive the datagram

---

### Requirement: Outbound Heartbeat message

The service SHALL send a WSJT-X-protocol Heartbeat datagram to every enabled target at a fixed
interval (matching WSJT-X's own convention) carrying the configured application `Id` (default
`"OpenWSFZ"`), the maximum schema number supported, and a version/revision string. The first
Heartbeat SHALL be sent within one interval of `ExternalReportingService` becoming enabled (start-up
or a config save that newly enables the feature).

#### Scenario: Heartbeat sent after enabling

- **WHEN** `externalReporting.enabled` transitions from `false` to `true` via a config save
- **THEN** a Heartbeat datagram SHALL be sent to every enabled target within one heartbeat interval

---

### Requirement: Outbound Status message

The service SHALL send a WSJT-X-protocol Status datagram whenever the daemon's effective dial
frequency, decoding-enabled state, or TX/transmitting state changes, and at least once per heartbeat
interval regardless of change, containing: dial frequency (Hz), mode (`"FT8"`), DX call (active QSO
partner, empty when idle), report, TX mode, `TxEnabled`, `Transmitting` (true only while
`IPttController` has an active key-down), `Decoding` (mirrors the existing decode start/stop control,
FR-017), RX/TX audio offsets (Hz), `MyCall` (`tx.callsign`), `MyGrid` (`tx.grid`), and DX grid (active
partner's grid, when known from the decode).

#### Scenario: Status reflects an active QSO

- **WHEN** `QsoAnswererService` is in `WaitReport` with partner `Q1TST`
- **THEN** the next Status datagram SHALL carry `DXCall = "Q1TST"` and `Transmitting = false`

#### Scenario: Status reflects a live transmission

- **WHEN** `IPttController.KeyDownAsync` is active
- **THEN** the next Status datagram SHALL carry `Transmitting = true`

---

### Requirement: Outbound Decode message

The service SHALL send one WSJT-X-protocol Decode datagram per `DecodeResult` delivered on the
existing per-cycle decode batch (the same feed `QsoAnswererService` subscribes to per its own spec),
carrying: UTC time, SNR, delta-time, delta-frequency (Hz), mode (`"~"` for FT8, matching WSJT-X's own
convention), the decoded message text, and the low-confidence flag. The `New` flag SHALL be `true`
(this service does not replay historical decodes).

#### Scenario: One decode produces one Decode datagram per enabled target

- **WHEN** a decode cycle yields exactly one `DecodeResult`
- **THEN** exactly one Decode datagram carrying that result's fields SHALL be sent to each enabled
  target

---

### Requirement: Outbound Clear message

The service SHALL send a WSJT-X-protocol Clear datagram whenever the decode pipeline's own decode
window is cleared (mirroring whatever internal event already signals a fresh decode window began,
per the existing decode pipeline).

#### Scenario: Clear sent on new decode cycle boundary

- **WHEN** a new 15-second decode cycle begins
- **THEN** a Clear datagram SHALL be sent to every enabled target before that cycle's Decode
  datagrams

---

### Requirement: Outbound QSOLogged message

The service SHALL send a WSJT-X-protocol QSOLogged datagram immediately after the daemon writes an
`ADIF.log` record (FR-051's `QsoComplete` write), carrying the same field values written to that
record: partner call, partner grid, TX/RX RST, QSO date/time on and off (UTC), operator call, my
grid, mode, and — when non-zero per FR-051 — frequency and band. No QSOLogged datagram SHALL be sent
for a QSO aborted by watchdog or operator (mirroring FR-051's own "no record on abort" rule).

#### Scenario: QSOLogged sent alongside ADIF record

- **WHEN** a QSO reaches `QsoComplete` and an `ADIF.log` record is written
- **THEN** a QSOLogged datagram carrying the same partner call, grid, and QSO date/time SHALL be sent
  to every enabled target

#### Scenario: No QSOLogged datagram on watchdog abort

- **WHEN** a QSO is aborted by the watchdog (per `qso-answerer`'s existing watchdog-abort behaviour)
- **THEN** no QSOLogged datagram SHALL be sent

---

### Requirement: Outbound Close message on shutdown

When the daemon shuts down gracefully (`ExternalReportingService.StopAsync`), the service SHALL send
a WSJT-X-protocol Close datagram to every enabled target before closing its sockets.

#### Scenario: Close sent on graceful shutdown

- **WHEN** the daemon receives a shutdown signal and `ExternalReportingService.StopAsync` runs
- **THEN** a Close datagram SHALL be sent to every enabled target before the outbound sockets close

---

### Requirement: Inbound listener never crashes on malformed input

The inbound listener SHALL treat any datagram that fails to parse (too short, bad magic number,
unsupported schema version, truncated field) as a discarded datagram: log at Debug and continue
listening. No parse failure SHALL propagate an unhandled exception out of the receive loop or stop
the listener.

#### Scenario: Truncated datagram does not stop the listener

- **WHEN** a 3-byte garbage datagram is received
- **THEN** it SHALL be discarded, a Debug log entry SHALL be written, and the listener SHALL continue
  to accept subsequent, well-formed datagrams

---

### Requirement: Unrecognised inbound message types are discarded, not acted upon

The daemon SHALL parse any inbound WSJT-X-protocol message type other than Heartbeat, Reply, Halt Tx, Free Text, and Close only far enough to determine it is well-formed, then discard it with a Debug log line (e.g. Replay, Location, Highlight Callsign, Switch Configuration, Configure). No such message type SHALL have any observable effect on OpenWSFZ state.

#### Scenario: Replay message is accepted and discarded

- **WHEN** a well-formed inbound Replay datagram is received
- **THEN** it SHALL be logged at Debug and SHALL have no effect on decode state or TX state

---

### Requirement: Inbound Halt Tx always honoured

On receipt of a well-formed inbound Halt Tx datagram, the daemon SHALL call
`IQsoController.AbortAsync` — the same call `POST /api/v1/tx/abort` already makes — regardless of the
value of `externalReporting.honourInboundCommands`. This SHALL apply whenever
`ExternalReportingService`'s inbound listener is running (i.e. `externalReporting.enabled` is `true`
with at least one configured target), independent of the inbound-commands opt-in.

#### Scenario: Halt Tx aborts an in-progress transmission regardless of the opt-in

- **WHEN** `externalReporting.honourInboundCommands` is `false` and a Halt Tx datagram is received
  while a QSO is active
- **THEN** `IQsoController.AbortAsync` SHALL be called and the active QSO SHALL abort to `Idle`

#### Scenario: Halt Tx while idle is a no-op

- **WHEN** a Halt Tx datagram is received while no QSO is active
- **THEN** `IQsoController.AbortAsync` SHALL be called and SHALL be a no-op (matching its existing
  documented behaviour when already `Idle`)

---

### Requirement: Inbound Reply gated by honourInboundCommands

On receipt of a well-formed inbound Reply datagram naming a callsign, the daemon SHALL call
`IExternalReplyTarget.TryEngageAsync(callsign)` only when `externalReporting.honourInboundCommands`
is `true`. When `false`, the datagram SHALL be discarded and an Information-level log entry SHALL
record that Reply was received but ignored because the opt-in is disabled.

#### Scenario: Reply engages a decoded CQ when opted in

- **WHEN** `externalReporting.honourInboundCommands` is `true`, the active role is Answerer and
  `Idle`, and a Reply datagram names a callsign present in the current decode batch as a CQ
- **THEN** `IExternalReplyTarget.TryEngageAsync` SHALL be called and the answerer SHALL engage that
  callsign exactly as it would for its own auto-answer path

#### Scenario: Reply ignored when not opted in

- **WHEN** `externalReporting.honourInboundCommands` is `false` and a Reply datagram is received
- **THEN** no engagement SHALL occur and an Information log entry SHALL record the ignored command

---

### Requirement: Inbound Free Text gated and currently a no-op

On receipt of a well-formed inbound Free Text datagram, the daemon SHALL store the text only when
`externalReporting.honourInboundCommands` is `true`; when `false` it SHALL be discarded with the same
Information-level logging as Reply. Even when stored, Free Text SHALL have **no effect on any
transmission** — no OpenWSFZ TX state machine currently has a free-message slot to apply it to. This
is intentional (see design.md) and SHALL NOT be treated as a defect.

#### Scenario: Free Text is stored but does not affect TX

- **WHEN** `externalReporting.honourInboundCommands` is `true` and a Free Text datagram carrying
  `"TEST MSG"` is received
- **THEN** the text SHALL be retained in memory and no transmission of any kind SHALL result

---

### Requirement: Inbound Close is logged and never terminates the daemon

On receipt of a well-formed inbound Close datagram, the daemon SHALL log an Information entry noting
a client requested close, and SHALL take no other action. Under no circumstances SHALL an inbound
network datagram of any type cause the daemon process to exit.

#### Scenario: Inbound Close does not shut down the daemon

- **WHEN** an inbound Close datagram is received
- **THEN** an Information log entry SHALL be written and the daemon SHALL continue running unaffected

---

### Requirement: Settings page — External Programs tab

The Settings page SHALL gain a new tab labelled **"External Programs"**, following the existing tab
pattern (FR-035, FR-043). The tab SHALL display: an **Enabled** checkbox bound to
`externalReporting.enabled`; an editable table of targets (columns: Name, Host, Port, Enabled,
Delete) with an **"Add target"** button that appends a blank row (`name = ""`, `host = "127.0.0.1"`,
`port = 2237`, `enabled = true`); and a separate **"Honour inbound commands (Reply / Free Text)"**
checkbox bound to `externalReporting.honourInboundCommands`, with adjacent explanatory text stating
that Halt Tx is always honoured regardless of this setting. All changes SHALL participate in the
existing unsaved-changes flow (FR-040) and SHALL be posted via `POST /api/v1/config` on Save. Per
FR-016, this tab SHALL ship only once the backend round-trip (config persistence and the running
`ExternalReportingService`) is fully implemented and testable end-to-end.

#### Scenario: Adding a target row

- **WHEN** the operator clicks "Add target" on the External Programs tab
- **THEN** a new blank row SHALL appear pre-filled with `host = "127.0.0.1"`, `port = 2237`,
  `enabled = true`, and the unsaved-changes indicator SHALL appear

#### Scenario: Honour-inbound-commands checkbox persists independently of Enabled

- **WHEN** the operator checks "Honour inbound commands" and saves, with `Enabled` already `true`
- **THEN** `POST /api/v1/config` SHALL include `externalReporting.honourInboundCommands: true`
