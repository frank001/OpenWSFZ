## ADDED Requirements

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
