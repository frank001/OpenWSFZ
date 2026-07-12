## Why

GridTracker2 (and JTAlert, N1MM+, and other logging/mapping tools) discover a running FT8
application entirely via the UDP protocol WSJT-X invented and that has since become the de-facto
amateur-radio interop standard. OpenWSFZ currently speaks to nothing outside itself: an operator
running GridTracker2 alongside OpenWSFZ today sees no traffic and gets no map, no spot list, and no
automatic QSO logging into GridTracker2's own log. Section 4.3 of `REQUIREMENTS.md` already flags
"PSK Reporter / DX cluster" style integrations as a known future need; this change is the first of
that family, chosen because it is the highest-value, lowest-risk one available — GridTracker2's own
"Reply"/"Halt Tx" affordances are the same ones every WSJT-X operator already trusts, so wiring
OpenWSFZ into the same protocol lets it slot into an existing operator's workflow unmodified.

This is a post-v1.0 addition (v1.0's gate is a confirmed two-way QSO via CAT+TX, tracked separately
by `cat-tx-ptt`) — it does not block that gate and depends on it only for the Halt Tx safety path
(§ below), which this change reuses rather than duplicates.

## What Changes

- Add a new outbound UDP broadcaster implementing the WSJT-X network protocol's core message types:
  **Heartbeat**, **Status** (dial frequency, mode, TX/RX state, DX call, active partner), **Decode**
  (one datagram per decoded FT8 message, mirroring what already goes to `ALL.TXT` per FR-028),
  **Clear**, **QSOLogged** (mirroring what already goes to `ADIF.log` per FR-051), and **Close**
  (sent on graceful daemon shutdown). This lets GridTracker2 plot the waterfall/spots on its map and
  log completed QSOs exactly as it does for WSJT-X today.
- Add a matching **inbound** listener on the same socket, honouring exactly four WSJT-X client→app
  message types: **Reply** (operator, in GridTracker2, selects a decoded station — OpenWSFZ engages
  it the same way its own auto-answer would), **Halt Tx** (immediately abort any in-progress
  transmission), **Free Text** (accepted and stored; currently a **no-op** — OpenWSFZ's TX state
  machines have no free-message slot to apply it to yet, see design.md), and **Close** (logged and
  otherwise ignored — a network datagram SHALL NEVER be able to terminate the daemon). Any other
  inbound WSJT-X message type is parsed enough not to desynchronise the socket and then discarded
  with a Debug log line — no other command is acted upon.
- Add a `externalReporting` block to `AppConfig`: `enabled` (bool, default `false`), a `targets`
  list (each `{ name, host, port, enabled }`) supporting **multiple simultaneous** outbound
  destinations from day one, and `honourInboundCommands` (bool, default `false`) — a dedicated
  opt-in for whether `Reply`/`Free Text` are acted on at all. **Halt Tx is exempt from this gate and
  is always honoured when the listener is running**, on the same "fail toward rig stays silent"
  principle `cat-tx-ptt` establishes: a third-party program being able to force TX *off* is safe by
  construction; a third-party program being able to force TX *on* (`Reply`) is the thing that needs
  explicit operator consent. Missing/absent `externalReporting` key deserialises to all-defaults —
  identical to today's behaviour (nothing is sent, nothing is listened for).
- Add a new **"External Programs"** tab to the Settings page (distinct from Radio hardware, Logging,
  Advanced, Frequencies, Logs, and Region data) listing configured targets with add/remove/enable
  controls and the inbound-commands opt-in checkbox, following the existing tab pattern (FR-035,
  FR-043) and gated by FR-016 (ships only once the backend round-trip is fully working).
- Extend `QsoAnswererService` with a narrow, testable "external reply" entry point that engages a
  specific currently-decoded CQ on command, subject to the same guards (empty callsign/grid,
  `DecodeFilterState`) as its existing auto-answer path. `QsoCallerService`'s existing
  `SelectResponderAsync` seam is reused, unmodified, for the Caller-role case.
- `Halt Tx` reuses the existing `IQsoController.AbortAsync` — the same method `POST /api/v1/tx/abort`
  already calls — rather than introducing a second stop mechanism.

## Capabilities

### New Capabilities

- `external-reporting`: WSJT-X-compatible UDP protocol client (outbound broadcast + inbound command
  listener), multi-target configuration, and its own Settings-page tab.

### Modified Capabilities

- `configuration`: `AppConfig` gains the `externalReporting` block described above; `GET`/`POST
  /api/v1/config` round-trip it.
- `qso-answerer`: gains a new, additive "external reply engages a specific CQ" entry point. No
  existing requirement's behaviour changes.

## Impact

- **Code**: new `OpenWSFZ.Daemon` component(s) for the UDP broadcaster/listener and WSJT-X datagram
  (de)serialisation; `OpenWSFZ.Config` for the new `ExternalReportingConfig` schema; `OpenWSFZ.Web`
  for the config round-trip and the new settings-tab markup/JS; `QsoAnswererService` for the new
  reply entry point.
- **Config**: additive only; existing `openswfz.json` files continue to work unchanged, and the
  feature is fully inert (`enabled: false`, `targets: []`, `honourInboundCommands: false`) until an
  operator opts in.
- **Network**: this is the first OpenWSFZ feature that opens an outbound/inbound UDP socket to
  arbitrary configured hosts (default target `127.0.0.1`, but an operator can point it at a LAN
  host). `remote-access`'s existing loopback/LAN bind-policy precedent applies conceptually but does
  not itself gate this — see design.md for why an unauthenticated UDP protocol is an accepted
  trade-off here (it is WSJT-X's own trust model, unchanged).
- **Requirements**: new FRs appended to `REQUIREMENTS.md` §4.1 (FR-052 onward) and a new row in the
  §4.3 Integrations table (superseding the "Future PSK Reporter / DX cluster" placeholder's GridTracker2
  case specifically — PSK Reporter itself remains future work).
- **Dependency**: Halt Tx's abort path assumes `IQsoController.AbortAsync` exists and behaves as
  documented today; it does not depend on any part of the in-flight `cat-tx-ptt` change landing
  first, since `AbortAsync` already existed before that change.
