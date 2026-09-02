# external-reporting Specification

## Purpose

Specifies `ExternalReportingService`: a WSJT-X-network-protocol-compatible UDP client that lets
third-party programs (GridTracker2, JTAlert, N1MM+, and similar WSJT-X-ecosystem tools) discover and
interoperate with OpenWSFZ over the same de-facto standard those tools already use with WSJT-X
itself. Covers the outbound broadcaster (Heartbeat, Status, Decode, Clear, QSOLogged, Close), the
inbound command listener (Reply, Halt Tx, Free Text, Close, and safe discarding of any other
message type), the absolute exclusion of synthetic/unresolved-region traffic from every outbound
channel, and the Settings-page "External Programs" tab. The feature is fully inert
(`enabled: false`, `targets: []`) until an operator opts in; see the `configuration` capability for
the `externalReporting` config schema and `qso-answerer` for the external-reply engagement entry
point this service calls into.

## Requirements

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
interval (matching WSJT-X's own convention) carrying the configured application `Id`
(`externalReporting.instanceId`, default `"OpenWSFZ"` — see `configuration` capability), the
maximum schema number supported, and a version/revision string. The first Heartbeat SHALL be sent
within one interval of `ExternalReportingService` becoming enabled (start-up or a config save that
newly enables the feature).

#### Scenario: Heartbeat sent after enabling

- **WHEN** `externalReporting.enabled` transitions from `false` to `true` via a config save
- **THEN** a Heartbeat datagram SHALL be sent to every enabled target within one heartbeat interval

---

### Requirement: Configurable per-instance Id for multi-instance disambiguation

The service SHALL carry the same `Id` field value on every outbound datagram it sends (Heartbeat,
Status, Decode, QSOLogged, Clear, Close): `AppConfig.ExternalReporting.InstanceId`, read live from
config at send time (not cached at startup), so a config save that changes it takes effect without
a daemon restart. Operators running more than one simultaneous `OpenWSFZ.Daemon` instance against
the same companion-program target (e.g. two bands captured via a split antenna, both reporting to
one local GridTracker) MUST give each instance a distinct `InstanceId`, or companion programs that
key off this field to distinguish multiple protocol-compatible instances will not be able to tell
them apart — observed in practice (2026-07-28 dual-receiver session) as the companion program's
live decode view resetting every FT8 cycle and silently dropped forwarding to downstream services
such as PSKReporter, not merely a cosmetic display glitch.

#### Scenario: Configured InstanceId is used across all outbound message types

- **WHEN** `externalReporting.instanceId` is set to a non-default value (e.g. `"OpenWSFZ-20m"`) and
  the service sends Heartbeat, Status, and Decode datagrams
- **THEN** every one of those datagrams' `Id` field SHALL carry `"OpenWSFZ-20m"`, not the literal
  `"OpenWSFZ"`

#### Scenario: Default InstanceId preserves single-instance behaviour

- **WHEN** `externalReporting.instanceId` is not configured (config omits the key, or a
  single-instance session never sets it)
- **THEN** every outbound datagram's `Id` field SHALL carry `"OpenWSFZ"`, byte-for-byte identical to
  every session before this field existed

---

### Requirement: Outbound Status message

The service SHALL send a WSJT-X-protocol Status datagram whenever the daemon's effective dial
frequency, decoding-enabled state, or TX/transmitting state changes, and at least once per heartbeat
interval regardless of change, containing: dial frequency (Hz), mode (`"FT8"`), DX call (active QSO
partner, empty when idle), report, TX mode, `TxEnabled`, `Transmitting` (true only while
`IPttController` has an active key-down), `Decoding` (mirrors the existing decode start/stop control,
FR-017), RX/TX audio offsets (Hz), `MyCall` (`tx.callsign`), `MyGrid` (`tx.grid`), and DX grid (active
partner's grid, when known from the decode). **Absolute exclusion, no exceptions:** when the active
partner resolves to an R&R-study synthetic entry or an unresolved (unknown) region, `DXCall` and DX
grid SHALL be sent empty instead of naming that partner — not gated by, and not overridable through,
`DecodeNoiseSuppressionConfig` or any other operator setting. The rest of the Status datagram (dial
frequency, TX/RX state, `Decoding`) SHALL continue to be sent normally; only the partner identity is
withheld.

#### Scenario: Status reflects an active QSO

- **WHEN** `QsoAnswererService` is in `WaitReport` with partner `Q1TST`
- **THEN** the next Status datagram SHALL carry `DXCall = "Q1TST"` and `Transmitting = false`

#### Scenario: Status reflects a live transmission

- **WHEN** `IPttController.KeyDownAsync` is active
- **THEN** the next Status datagram SHALL carry `Transmitting = true`

#### Scenario: Status blanks DxCall/DxGrid for a synthetic or unresolved active partner

- **WHEN** the active QSO partner resolves to an R&R-study synthetic entry (or does not resolve to
  any region at all), **and** `DecodeNoiseSuppressionConfig.SuppressSynthetic`/
  `SuppressUnknownRegion` are both `false` (the operator has not opted in to hiding it anywhere else)
- **THEN** the next Status datagram SHALL carry `DXCall = ""` and DX grid `""`, while dial frequency,
  `TxEnabled`, `Transmitting`, and `Decoding` SHALL continue to reflect the real, current state

---

### Requirement: Outbound Decode message

The service SHALL send one WSJT-X-protocol Decode datagram per `DecodeResult` delivered on the
existing per-cycle decode batch (the same feed `QsoAnswererService` subscribes to per its own spec),
carrying: UTC time, SNR, delta-time, delta-frequency (Hz), mode (`"~"` for FT8, matching WSJT-X's own
convention), the decoded message text, and the low-confidence flag. The `New` flag SHALL be `true`
(this service does not replay historical decodes).

**Absolute exclusion, no exceptions:** a `DecodeResult` whose `Region` is `null` (unresolved/unknown)
or whose `Region.Synthetic` is `true` (R&R-study synthetic entry, NFR-021 Q-prefix convention) SHALL
NEVER produce an outbound Decode datagram, to any target, under any circumstance. This exclusion is
enforced unconditionally inside `ExternalReportingService` itself, independent of
`DecodeNoiseSuppressionConfig.SuppressUnknownRegion`/`SuppressSynthetic` (which gate only the decode
panel and QSO automation and can be disabled by the operator) — it is not exposed as, and SHALL NOT
be exposed as, any Settings-page control or config field. This is a data-integrity/privacy floor:
nothing this application cannot vouch for as real, resolved amateur-radio traffic may leave the
machine via this channel, regardless of what the operator has configured elsewhere.

#### Scenario: One decode produces one Decode datagram per enabled target

- **WHEN** a decode cycle yields exactly one `DecodeResult` with a resolved, non-synthetic `Region`
- **THEN** exactly one Decode datagram carrying that result's fields SHALL be sent to each enabled
  target

#### Scenario: Unknown-region and synthetic decodes are never broadcast, even with suppression disabled

- **WHEN** `DecodeNoiseSuppressionConfig.SuppressUnknownRegion` and `SuppressSynthetic` are both
  `false` (the exact condition that lets such decodes reach this service's inbound channel), and a
  decode cycle contains a `DecodeResult` with `Region: null` and another with `Region.Synthetic: true`
- **THEN** neither `DecodeResult` SHALL produce an outbound Decode datagram to any target

---

### Requirement: Outbound Clear message

The service SHALL send a WSJT-X-protocol Clear datagram only when the daemon shuts down gracefully
(`ExternalReportingService.StopAsync`), sent alongside the existing Close datagram before the
outbound sockets close. The service SHALL NOT send a Clear datagram on any other cadence — in
particular, it SHALL NOT send one at the start of every decode cycle. This corrects a defect
present since this capability's original implementation: real WSJT-X (per its own
`NetworkMessage.hpp` protocol documentation) sends Clear only on an explicit operator
"erase Band Activity window" action or on its own graceful shutdown — never on its ordinary decode
cadence, which is identical to this service's. A third-party consumer (GridTracker2, JTAlert, ...)
treats Clear as "discard everything accumulated from this source"; sending it every ~15-second
decode cycle caused such a consumer's own accumulated state (e.g. a spot map) to be wiped every
cycle instead of persisting across a session, in stark contrast to a real WSJT-X source.

#### Scenario: No Clear datagram is sent during ordinary decode-cycle operation

- **WHEN** the service is running with at least one enabled target and successive decode cycles
  produce Decode datagrams, regardless of how many (or how few) decodes each cycle contains
- **THEN** no Clear datagram SHALL be sent at any point during this ordinary operation

#### Scenario: Clear sent on graceful shutdown

- **WHEN** the daemon receives a shutdown signal and `ExternalReportingService.StopAsync` runs
- **THEN** a Clear datagram SHALL be sent to every enabled target, alongside the existing Close
  datagram, before the outbound sockets close

---

### Requirement: Outbound QSOLogged message

The service SHALL send a WSJT-X-protocol QSOLogged datagram immediately after the daemon writes an
`ADIF.log` record (FR-051's `QsoComplete` write), carrying the same field values written to that
record: partner call, partner grid, TX/RX RST, QSO date/time on and off (UTC), operator call, my
grid, mode, and — when non-zero per FR-051 — frequency and band. No QSOLogged datagram SHALL be sent
for a QSO aborted by watchdog or operator (mirroring FR-051's own "no record on abort" rule).

**Absolute exclusion, no exceptions:** when the partner callsign resolves to an R&R-study synthetic
entry or an unresolved (unknown) region, no QSOLogged datagram SHALL be sent for that QSO, under any
circumstance — not gated by, and not overridable through, `DecodeNoiseSuppressionConfig` or any other
operator setting. A completed QSO with such a partner SHALL NOT be reported to any external program
as a real logged contact.

#### Scenario: QSOLogged sent alongside ADIF record

- **WHEN** a QSO reaches `QsoComplete`, its partner resolves to a real (non-synthetic, resolved-
  region) callsign, and an `ADIF.log` record is written
- **THEN** a QSOLogged datagram carrying the same partner call, grid, and QSO date/time SHALL be sent
  to every enabled target

#### Scenario: No QSOLogged datagram on watchdog abort

- **WHEN** a QSO is aborted by the watchdog (per `qso-answerer`'s existing watchdog-abort behaviour)
- **THEN** no QSOLogged datagram SHALL be sent

#### Scenario: No QSOLogged datagram for a synthetic or unknown-region partner

- **WHEN** a QSO reaches `QsoComplete` and its partner callsign resolves to an R&R-study synthetic
  entry, or resolves to no region at all
- **THEN** no QSOLogged datagram SHALL be sent to any target, even though the local `ADIF.log` record
  is still written normally (this exclusion applies only to the external channel)

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
`port = 2237`, `enabled = true`); a **"Honour inbound commands (Reply / Free Text)"** checkbox bound
to `externalReporting.honourInboundCommands`, with adjacent explanatory text stating that Halt Tx is
always honoured regardless of this setting; and a **"Restrict external Reply to the current
decode-panel filter"** checkbox bound to `externalReporting.restrictExternalRepliesToDecodeFilter`,
nested under/beside the "Honour inbound commands" control since it has no effect unless that one is
also checked, with adjacent explanatory text stating that unchecked (the default) allows a
third-party program to Reply to any currently decoded station regardless of the operator's own
decode-panel filter. All changes SHALL participate in the existing unsaved-changes flow (FR-040) and
SHALL be posted via `POST /api/v1/config` on Save. Per FR-016, this tab SHALL ship only once the
backend round-trip (config persistence and the running `ExternalReportingService`) is fully
implemented and testable end-to-end.

#### Scenario: Adding a target row

- **WHEN** the operator clicks "Add target" on the External Programs tab
- **THEN** a new blank row SHALL appear pre-filled with `host = "127.0.0.1"`, `port = 2237`,
  `enabled = true`, and the unsaved-changes indicator SHALL appear

#### Scenario: Honour-inbound-commands checkbox persists independently of Enabled

- **WHEN** the operator checks "Honour inbound commands" and saves, with `Enabled` already `true`
- **THEN** `POST /api/v1/config` SHALL include `externalReporting.honourInboundCommands: true`

#### Scenario: Restrict-external-replies checkbox defaults unchecked and persists when set

- **WHEN** the operator opens the External Programs tab on a config with no prior
  `restrictExternalRepliesToDecodeFilter` value
- **THEN** the checkbox SHALL render unchecked (matching the `false` default), and if the operator
  checks it and saves, `POST /api/v1/config` SHALL include
  `externalReporting.restrictExternalRepliesToDecodeFilter: true`

---

### Requirement: Leader role preserves existing direct-send behaviour

`ExternalReportingService` SHALL, when `externalReporting.role` is `"leader"` (the default), behave identically to this service's pre-existing (`gridtracker-udp-reporting`, `fix-external-reporting-clear-and-reply-filter`, `fix-external-reporting-appid-collision`) behaviour in every respect: it SHALL open its own outbound sockets to every enabled `targets` entry and its own inbound listener, and no requirement in this capability that predates this change SHALL be altered by a `"leader"` instance's presence or absence of followers.

#### Scenario: Leader with no followers is unchanged from today's behaviour

- **WHEN** `externalReporting.role` is `"leader"` (or the key is absent) and no follower ever relays
  to this instance
- **THEN** every outbound datagram this service sends SHALL be byte-for-byte identical to what this
  service would have sent before this change existed, for the same config and the same decode/QSO
  activity

---

### Requirement: Follower role relays instead of sending directly

An `ExternalReportingService` instance with `externalReporting.role` set to `"follower"` SHALL NOT
open any outbound or inbound socket to its own `targets` entries. Every datagram it would otherwise
have sent directly (Heartbeat, Status, Decode, QSOLogged, Clear, Close) SHALL instead be encoded
exactly as `"leader"` role encodes it today — same `instanceId` (this instance's own, read live from
config), same absolute exclusion of synthetic/unresolved-region traffic applied before encoding — and
relayed to `externalReporting.leaderUrl` via `POST /api/v1/external-reporting/relay` in place of a
direct UDP send.

#### Scenario: Follower's Decode datagram is relayed, not sent directly

- **WHEN** `externalReporting.role` is `"follower"` with a valid `leaderUrl`, and a decode cycle
  yields one `DecodeResult` with a resolved, non-synthetic `Region`
- **THEN** no UDP datagram SHALL be sent from this instance to any `targets` entry, and one
  `POST /api/v1/external-reporting/relay` request carrying that Decode datagram's encoded bytes SHALL
  be sent to `leaderUrl`

#### Scenario: Follower's absolute exclusion still applies before relaying

- **WHEN** `externalReporting.role` is `"follower"` and a decode cycle contains a `DecodeResult` with
  `Region: null`
- **THEN** no relay POST containing that result SHALL be sent — the same absolute exclusion this
  capability already guarantees for direct sends applies identically before a datagram is ever handed
  to the relay path

---

### Requirement: Leader relay endpoint dispatches a follower's batch atomically and in order

`POST /api/v1/external-reporting/relay` on a `"leader"`-role instance SHALL accept a batch of one or
more already-encoded datagrams from a follower and send every datagram in that batch, in the order
received, to every one of the leader's own enabled `targets`, before beginning to send any other
queued batch — whether that other batch originated from a different follower or from the leader's own
outbound traffic. No batch SHALL be interleaved with another mid-dispatch.

#### Scenario: A follower's Status-then-Decode batch is never split by another source

- **WHEN** a follower relays one batch containing a Status datagram immediately followed by three
  Decode datagrams from the same decode cycle, and the leader's own Status/Decode traffic (or a
  second follower's relayed batch) becomes ready to send at the same moment
- **THEN** all four datagrams from the first batch SHALL be sent to every enabled target, in order,
  before any datagram from the other source is sent

#### Scenario: Relay endpoint rejects a request from an unconfigured follower

- **WHEN** `POST /api/v1/external-reporting/relay` is received but the leader has no record of
  expecting relayed traffic (`externalReporting.enabled` is `false`, or the instance's own `role` is
  not `"leader"`)
- **THEN** the daemon SHALL return HTTP 503 and SHALL NOT send any datagram to any target

---

### Requirement: Follower degrades to direct send when its leader is unreachable

A `"follower"`-role instance SHALL, when its relay attempt to `leaderUrl` fails (connection refused, timeout, or a non-2xx response), send the affected datagram(s) directly to its own `targets`, under its own `instanceId`, exactly as `"leader"` role does — the same fallback path this capability already implements for a target whose host fails to resolve. A Warning SHALL be logged, at most once per leader-unreachable state (not once per datagram), and reconciliation back to relaying through `leaderUrl` SHALL happen automatically on the next successful relay attempt, with no restart or manual reconfiguration required.

#### Scenario: Follower keeps reporting when its leader is stopped

- **WHEN** `externalReporting.role` is `"follower"` with a valid `leaderUrl`, and the leader instance
  is stopped or otherwise unreachable
- **THEN** this instance SHALL continue sending its own Heartbeat/Status/Decode/QSOLogged/Clear/Close
  datagrams, now sent directly to its own `targets` under its own `instanceId`, and a Warning SHALL be
  logged once for the leader-unreachable state

#### Scenario: Follower resumes relaying once its leader becomes reachable again

- **WHEN** a follower is currently degraded to direct-send per the scenario above, and its leader
  becomes reachable again
- **THEN** the very next datagram SHALL be relayed to `leaderUrl` rather than sent directly, with no
  operator action required

---

### Requirement: Inbound Halt Tx broadcasts to configured followers

On receipt of a well-formed inbound Halt Tx datagram, a `"leader"`-role instance SHALL, in addition to
calling its own `IQsoController.AbortAsync` (per this capability's existing unconditional Halt Tx
requirement), send an abort request to every URL listed in `externalReporting.followerUrls`. A
follower that is not currently transmitting SHALL treat this as a no-op, matching
`IQsoController.AbortAsync`'s own existing idle-no-op behaviour. A follower that fails to respond
SHALL NOT prevent the abort request from reaching the leader's own QSO controller or any other
follower in the list.

#### Scenario: Halt Tx aborts the leader and every configured follower

- **WHEN** a leader with `followerUrls: ["http://127.0.0.1:8081"]` receives an inbound Halt Tx while
  its own QSO is active and the follower at that URL also has an active QSO
- **THEN** the leader's own QSO SHALL abort to `Idle` and an abort request SHALL be sent to
  `http://127.0.0.1:8081`

#### Scenario: An unreachable follower does not block Halt Tx on the leader or other followers

- **WHEN** `followerUrls` lists two entries and one is unreachable
- **THEN** the leader's own `AbortAsync` SHALL still be called and the reachable follower SHALL still
  receive its abort request

---

### Requirement: Inbound Reply is scoped to the leader's own decode batch (v1 limitation)

On receipt of a well-formed inbound Reply datagram, a `"leader"`-role instance SHALL resolve the named
callsign against its own current decode batch only, exactly as this capability's existing inbound
Reply requirement already specifies — this change does not extend Reply resolution to any follower's
decode batch. When the named callsign is not found in the leader's own current decode batch (and
`honourInboundCommands` is `true`), the daemon SHALL log an Information entry distinguishing this
"not in my own decode batch" case from the pre-existing "no callsign could be extracted" case, so an
operator running a follower can diagnose why Reply appeared to do nothing for a station only the
follower decoded.

#### Scenario: Reply for a follower-only decoded callsign is logged distinctly

- **WHEN** `honourInboundCommands` is `true`, a leader has at least one relaying follower, and an
  inbound Reply names a callsign that appears in the follower's current decode batch but not the
  leader's own
- **THEN** no engagement SHALL occur on the leader, and an Information log entry SHALL record that the
  named callsign was not found in this instance's own current decode batch
