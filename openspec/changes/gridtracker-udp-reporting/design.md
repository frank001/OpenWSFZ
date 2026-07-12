## Context

WSJT-X's UDP network protocol (`NetworkMessage.hpp` in the WSJT-X source, port 2237 by convention,
plain UDP datagrams, big-endian, a `quint32` magic number + schema version framing every message) is
not an OpenWSFZ invention — it is a third-party wire format this change must implement byte-compatibly
because GridTracker2 (and every other consumer: JTAlert, N1MM+, Log4OM, DXKeeper...) hard-codes it.
There is no negotiation and no OpenWSFZ-side flexibility in the framing or field layout of the
message types this change implements; the only real design freedom is (a) which subset of the ~16
message types to implement, (b) how the broadcaster/listener plugs into OpenWSFZ's existing decode
pipeline, config store, and TX state machines, and (c) the trust boundary around inbound commands
that can affect a live transmission — decided in the proposal (Halt Tx always honoured, Reply/Free
Text behind an explicit opt-in) and detailed further below.

Relevant existing seams this change builds on rather than duplicates:
- `DecodeEventBus` / the existing per-cycle `Channel<IReadOnlyList<DecodeResult>>` that
  `QsoAnswererService` already subscribes to (FR-050) — the outbound Decode broadcaster taps the same
  feed rather than re-deriving decode data.
- `IQsoController.AbortAsync` — already the single call `POST /api/v1/tx/abort` uses (`WebApp.cs`
  line ~1012) regardless of which role (`QsoAnswererService`/`QsoCallerService`) is active. Halt Tx
  calls this directly, in-process.
- `QsoCallerService.SelectResponderAsync` — an existing seam for manually picking which responder to
  a transmitted CQ to continue with (per `qso-caller` spec, "SelectResponderAsync stores pending
  responder and fires on correct phase"). Caller-role `Reply` routes here, unmodified.
- `ADIF.log` / `ALL.TXT` writers (FR-051, FR-028) — the source of truth for QSOLogged/Decode field
  content; the broadcaster reads the same in-memory data those writers already consume, it does not
  parse the log files back.
- The Settings-page tab pattern (FR-035, FR-043) and F-006's precedent of a capability owning its own
  settings-tab requirements directly in its own spec file (`region-lookup-data-refresh`,
  `decoder-settings`) rather than in `web-frontend`.

## Goals / Non-Goals

**Goals:**
- Byte-compatible WSJT-X UDP protocol implementation for the message subset in the proposal, verified
  against real GridTracker2 wire captures (task-level detail in tasks.md), not just against our own
  round-trip tests.
- Multiple simultaneous outbound targets, each independently enable/disable-able, from day one.
- A trust boundary that defaults to fully inert and, even once enabled, can never let a stray or
  malicious UDP datagram start a transmission or terminate the daemon.
- Halt Tx reachable the instant the listener is running, with no additional opt-in — it is a strictly
  safety-improving control.
- No change to any existing, already-shipped requirement's behaviour — this is additive from every
  existing capability's point of view.

**Non-Goals:**
- Not implementing the *entire* WSJT-X protocol. `Replay`, `Location`, `Highlight Callsign`, `Switch
  Configuration`, `Configure`, `WSPR Decode` (inbound), and any other type outside the proposal's
  explicit list are parsed only far enough to stay framed correctly on the socket, then discarded.
  Extending coverage is a follow-up change once this lands and its actual usage is known.
- Not building a general "free-message TX" capability. `Free Text` is accepted and stored so the
  protocol round-trips cleanly (and so a *future* free-message feature has somewhere to read it from
  on day one), but until such a feature exists, receiving it has **no transmission effect** — this is
  called out explicitly rather than silently dropped, so it is not mistaken for a bug.
- Not adding authentication/encryption to the UDP channel. This matches WSJT-X's own model (plaintext
  UDP, security through network topology — loopback or a trusted LAN) and is an accepted, unchanged
  trade-off; see Risks below.
- Not touching `remote-access`'s HTTP/WebSocket bind-policy machinery — this is a separate socket with
  its own, much narrower, config-driven target list, not a generalisation of remote access.

## Decisions

### 1. New standalone hosted service, not folded into an existing one

**Decision:** Add `ExternalReportingService : IHostedService` in `OpenWSFZ.Daemon`, owning one
`UdpClient` per configured, enabled target for outbound sends, and a single inbound-listening
`UdpClient` bound to `0.0.0.0:<firstEnabledTargetPort>` (WSJT-X convention: the app listens on the
same port it's configured to send to, since GridTracker2 replies from the same port it received on).
It subscribes to `DecodeEventBus` (outbound Decode), a small new `IQsoStatusSnapshot` polled on a
short timer (outbound Status/Heartbeat — matching WSJT-X's own ~cadence, no event bus needed for a
periodic message), and the ADIF-write completion point (outbound QSOLogged). It is registered
unconditionally; when `externalReporting.enabled` is `false` it starts and immediately does nothing
(no socket opened) — same "inert by default" pattern as `CatPollingService` when `cat.enabled` is
`false`.

**Why:** Every other cross-cutting daemon capability (`CatPollingService`, `AudioWatchdog`,
`DataFlowMonitor`) is its own `IHostedService`; this keeps the same shape and keeps
`QsoAnswererService`/`QsoCallerService` completely unaware that external reporting exists, aside from
the one new narrow entry point for `Reply` (Decision 4).

**Alternatives considered:**
- *Fold broadcasting into `QsoAnswererService`* — rejected: conflates an orthogonal concern (talking
  to a third-party program) with QSO state-machine logic that already has enough responsibility, and
  would force `QsoCallerService` to duplicate the same code.

### 2. Outbound message construction reads existing state, never re-derives it

**Decision:** `Status` and `Decode` datagrams are built from the same `DecodeResult`/`ICatState`/
`IConfigStore.Current.Tx` data the WebSocket `status`/`txState` events and `ALL.TXT` writer already
use. `QSOLogged` is built at the exact point `ADIF.log`'s record is written (same call site, same
field values), not by re-parsing `ADIF.log`.

**Why:** Two independent encodings of "what just happened" from the same source data cannot drift
apart; deriving one from the other's *output file* would create a parsing dependency on `ADIF.log`'s
own format for no benefit.

### 3. Inbound trust boundary: `honourInboundCommands` gates Reply/Free Text; Halt Tx is ungated

**Decision:** As stated in the proposal. Implementation-wise, the inbound listener always parses and
dispatches every recognised datagram type, but the dispatcher for `Reply` and `Free Text` checks
`IConfigStore.Current.ExternalReporting.HonourInboundCommands` and no-ops (with an Information log:
*"external Reply command received but honourInboundCommands is disabled — ignoring"*) when `false`.
`Halt Tx`'s dispatcher has no such check.

**Why:** Mirrors `cat-tx-ptt`'s design philosophy directly: prefer the design that fails toward "rig
stays silent." An operator who has not opted in should never have a third-party program start a QSO
on their behalf; but an operator in that same state should still be able to reach for GridTracker2's
Halt Tx button as a second, independent stop mechanism if, say, the OpenWSFZ web UI is unreachable
for some reason. The two are not symmetric risks.

**Alternatives considered:**
- *Single `enabled` flag governs everything, including Halt Tx* — rejected: an operator who enables
  outbound reporting only (to get GridTracker2's map working) but has not thought about the inbound
  command surface at all would otherwise unknowingly also expose Reply. Splitting the flags makes the
  outbound-only, common case (map/logging visibility) the version that ships with zero additional risk
  surface, and makes the opt-in step for "let GridTracker2 drive my radio" a deliberate second decision.
- *No opt-in at all — honour Reply/Free Text whenever `enabled`* — rejected as the default because it
  collapses "I want GridTracker2 to see my station" and "I want GridTracker2 to be able to key my
  station" into one checkbox; FR-016's "no speculative behaviour" spirit argues for making a new
  remote-control surface opt-in explicitly, not implicitly via a reporting toggle.

### 4. `Reply` routes to role-specific existing seams via a narrow interface, not a new state machine

**Decision:** Add `IExternalReplyTarget` (defined in `OpenWSFZ.Web`, alongside `IQsoRoleSwitcher`,
same rationale — avoids a project reference from `OpenWSFZ.Web`/the new listener back into
`OpenWSFZ.Daemon`) with one method: `Task<bool> TryEngageAsync(string callsign, CancellationToken ct)`.
`QsoControllerRouter` (the existing implementer of `IQsoRoleSwitcher`) also implements this: when the
active role is Answerer, it calls a new `QsoAnswererService.TryEngageExternal(callsign)` that runs the
exact same selection/guard logic as the auto-answer path (`DecodeFilterState` check, empty
callsign/grid guard) but targets the specified callsign instead of "first CQ in the batch"; when the
active role is Caller, it calls the existing `SelectResponderAsync(callsign)` unmodified. Returns
`false` (no-op, logged at Information with a reason) if the callsign is not currently a decoded,
engageable station.

**Why:** Reuses two already-tested selection mechanisms instead of inventing a third. The new surface
on `QsoAnswererService` is additive (a new public method with new guards mirroring existing ones, not
a change to the auto-answer requirement itself), which is why `qso-answerer`'s delta spec uses ADDED,
not MODIFIED.

**Alternatives considered:**
- *Always require the operator to also enable `tx.autoAnswer` for `Reply` to do anything* — rejected:
  `Reply` is inherently a manual, one-shot instruction ("engage *this* station specifically"), which is
  a different intent from "auto-answer whatever CQ appears first"; gating it behind `autoAnswer` would
  make manual GridTracker2-driven operation impossible without also accepting fully automatic
  operation.

### 5. Framing/serialisation lives in a small, dependency-free internal library

**Decision:** A new internal static class (e.g. `WsjtxDatagram`) in `OpenWSFZ.Daemon` handles the
magic-number/schema-version header, big-endian primitive read/write, and per-message-type
encode/decode, with no dependency on any other OpenWSFZ type — it operates purely on primitive
fields passed in and out. All OpenWSFZ-specific mapping (which `DecodeResult` field goes in which
datagram field) lives in `ExternalReportingService`, one layer up.

**Why:** Keeps the one piece of this change that must be byte-perfect against an external spec
small, self-contained, and exhaustively unit-testable (encode a known message, assert exact bytes;
decode known captured bytes, assert exact fields) without dragging in decode-pipeline or config-store
mocking for what is fundamentally a serialisation problem.

### 6. Absolute exclusion of synthetic/unknown-region traffic — hard-coded, not configurable

**Decision:** `ExternalReportingService` unconditionally withholds any decode, Status partner
identity, or QSOLogged record whose associated callsign resolves to an R&R-study synthetic entry
(NFR-021's Q-prefix convention) or fails to resolve to any region at all (`Region: null`). This is
implemented as a *second*, hard-coded filter inside the class that actually emits UDP traffic —
`DecodeLoopAsync` checks `DecodeResult.Region` directly; `BuildStatusFields`/`NotifyQsoLogged` use a
new `IsSuppressedCallsign` helper backed by an optional `ICallsignRegionStore` — entirely
independent of, and layered *after*, the existing operator-toggleable
`DecodeNoiseSuppressionConfig.SuppressUnknownRegion`/`SuppressSynthetic` settings that gate the
decode panel and QSO automation upstream. It is not exposed as, and SHALL NOT be exposed as, any
Settings-page control or config field — there is no way for an operator to turn it off.

**Why:** Directed by the Captain in the plainest possible terms (dev-tasks/2026-07-12-gridtracker-
udp-reporting-review-fixes.md §4): R&R synthetic signals are not real amateur-radio traffic, and
GridTracker2 may itself relay spots onward to a real map, a real logbook, or another real-world
tool this project has no authority over — letting synthetic or unverified traffic leak into that
chain would contaminate systems outside this application's control. Unknown-region decodes are
unverified/likely-noisy and get the same treatment for the same reason: this is a data-integrity/
privacy floor, not a preference, so it cannot depend on upstream config staying a particular way
(an operator who has disabled both `DecodeNoiseSuppressionConfig` settings — a legitimate, supported
choice for the decode panel — must not thereby also leak synthetic/unknown traffic externally; the
two concerns are deliberately decoupled).

**Fail-closed, not fail-open:** unlike most optional-dependency (`Foo?`) patterns elsewhere in this
codebase, which fail *open* when the dependency is absent (e.g. a `null` `IDecodeFilterStore` means
"unfiltered"), `IsSuppressedCallsign` treats a `null` `ICallsignRegionStore` exactly like a lookup
miss — suppressed. "Cannot verify" must never be silently treated as "verified real."

**Alternatives considered:**
- *Rely on `DecodeNoiseSuppressionConfig` defaulting to suppress-on* — rejected: defaults are
  overridable by the operator for a legitimate, unrelated reason (wanting to see synthetic/unknown
  traffic on the decode panel during an R&R study run), and this exclusion must hold regardless.
- *A new, dedicated `externalReporting` config flag for this* — rejected: the Captain's directive is
  explicit that this is "not gated by, not overridable through, any operator setting." A flag,
  however defaulted, is still a flag an operator could theoretically flip.

### 7. Inbound bind uses `SO_REUSEADDR`; primary target's outbound sends share that same socket (D-014)

**Decision:** Amends Decision 1's inbound bind. The inbound `UdpClient` sets
`SocketOptionName.ReuseAddress` before binding — mirroring Qt's
`ShareAddress | ReuseAddressHint`, the bind option every WSJT-X-protocol peer (GridTracker2
included) uses — so the bind succeeds even when a peer already owns the port at daemon-startup
time. Separately, the *primary* target (index 0 of the enabled target list, whose port the inbound
listener binds to) has its outbound sends routed through that same shared socket rather than a
separate ephemeral `UdpClient`, falling back to an ephemeral client only if the shared bind is
unavailable. Secondary targets (index 1+) are unaffected — each still gets its own dedicated
outbound-only client.

**Why:** Found during pre-merge review (D-014): without `ReuseAddress`, the bind threw whenever the
operator's mapping tool was already running — the normal real-world case, not an edge case — and the
exception was swallowed and logged at Warning only, leaving Halt Tx/Reply/Free Text silently and
*permanently* unreachable (nothing retries the bind outside of a config save). The shared-socket
send additionally makes Decision 1's own stated rationale ("GridTracker2 replies from the same port
it received on") actually true: without it, the primary target's sends went out from a separate
ephemeral port, so a peer's reply-to-sender-port semantics would arrive at the wrong place.

**Verification status — read before trusting this in production:** empirically probed on Windows
while implementing D-014's regression tests: when two `UdpClient`s share one local port via
`SO_REUSEADDR`, Windows delivers an incoming unicast datagram to only the *first-bound* socket —
never both, and (unlike Linux `SO_REUSEPORT`) with no load-balancing fan-out. This means true
*simultaneous* two-listener coexistence on one port on one machine (OpenWSFZ and GridTracker2 both
genuinely receiving their own inbound traffic at the same time) is **not guaranteed by this fix
alone** on Windows — it would need UDP multicast, which the Open Questions section below already
identifies as unimplemented, deliberately out of scope for this change. What this fix does
guarantee, and what its regression tests actually prove: the bind no longer fails/stays permanently
`null` when a peer already owns the port at startup, and the primary target's outbound sends
genuinely originate from the shared bound port. This is the same category of caveat as tasks 2.6/
10.3 (no live GridTracker2 available to verify the richer message layouts byte-for-byte) — a real
GridTracker2 session is the place to confirm actual bidirectional coexistence before relying on this
operationally.

**Linux addendum (2026-07-12, found via PR #70's `ubuntu-latest` CI failure — see
dev-tasks/2026-07-12-gridtracker-udp-reporting-linux-ci-failure.md):** the Windows finding above is
about *inbound* delivery (which of two listeners receives a datagram sent *to* the shared port).
Linux's `SO_REUSEADDR` semantics for UDP are documented (and generally observed, kernel/version
dependent) to differ from Windows in a way that creates the mirror-image risk on the *outbound* side:
rather than first-bind-wins, unicast delivery to a `SO_REUSEADDR`-shared UDP port on Linux has
historically gone to the **last-bound** socket. In the realistic startup order this feature targets
(GridTracker2 already running and bound to the shared port first; OpenWSFZ's `_inboundClient` binds
second, inside `Reconcile`), a datagram OpenWSFZ sends from its primary-target outbound path to
`127.0.0.1:port` — i.e. addressed to GridTracker2's port on the same host — could, on a Linux kernel
exhibiting last-bind-wins behaviour, be delivered back to OpenWSFZ's own `_inboundClient`/
`InboundLoopAsync` instead of ever reaching GridTracker2's socket. If so, Heartbeat/Status/Clear/
Decode/QSOLogged would silently never arrive at GridTracker2 on Linux in the exact
peer-started-first scenario this whole feature is built for, while inbound Halt Tx/Reply/Free Text
(GridTracker2 → OpenWSFZ, a genuinely different socket pair since GridTracker2's *own* send
originates from GridTracker2's process, not from a second local bind) are unaffected.

This was not exercised by a real two-process Linux test — no live GridTracker2 (or second real
peer process) was available to confirm it end-to-end; the finding is reasoned from documented
kernel behaviour plus the CI symptom (`OutboundToPrimaryTarget_UsesSharedInboundPort` timing out
with `fakePeer` receiving nothing, which is consistent with, though not exclusive proof of, the
daemon's own send looping back to itself). Given the plaintext-loopback nature of this feature and
that Decision 7's existing verification-status caveat already flags true simultaneous two-listener
coexistence as unguaranteed on Windows too, this is logged as an **open risk carried forward, not
fixed in this change**: the shared-socket send optimisation (routing the primary target's outbound
through `_inboundClient` rather than a dedicated ephemeral client, so reply-to-sender-port semantics
work) is kept as-is, since reverting it would sacrifice the Windows-side benefit it exists for and
the risk is unconfirmed on real hardware either way. A real Linux deployment with GridTracker2 (or a
packet capture on a Linux box) is needed to confirm or rule this out before treating Linux delivery
as solid; tracked as a follow-up verification item alongside tasks 2.6/10.3's existing "no live
GridTracker2" caveat, not a new Open Question line item since it is a refinement of the same
unresolved multicast/multi-listener question already below.

## Risks / Trade-offs

- **[Risk] Plaintext, unauthenticated UDP to an operator-configured host** → Mitigation: this is
  WSJT-X's own, already-widely-deployed trust model — GridTracker2 users already accept it for
  WSJT-X. Documented as an accepted trade-off, not re-litigated. Default target list is empty and
  `enabled` defaults to `false`, so no packets leave the machine until the operator configures a
  target.
- **[Risk] A malformed or adversarial inbound datagram (short buffer, garbage schema version) crashes
  the listener** → Mitigation: `WsjtxDatagram` decode paths SHALL treat any parse failure as "discard
  this datagram, log at Debug, continue listening" — never throw uncaught out of the receive loop.
  Task-level requirement: a fuzzed/truncated-datagram test proves the listener survives.
  Never bring down `ExternalReportingService`, let alone the daemon, from a bad packet.
- **[Risk] `Reply`/`Halt Tx` racing with an in-progress QSO's own state transition (e.g. Halt Tx
  arrives the same instant the QSO completes naturally)** → Mitigation: `IQsoController.AbortAsync`
  already documents this as a no-op when already `Idle` (existing `qso-answerer` "Operator abort"
  requirement); no new race is introduced because no new stop mechanism is introduced.
  `TryEngageAsync` is naturally idempotent-safe the same way `SelectResponderAsync` already is
  (existing "two requests in quick succession are idempotent"-style scenario for the Caller case;
  the new Answerer-side `TryEngageExternal` gets an equivalent scenario).
- **[Risk] Sending a Status/Heartbeat datagram every second-or-so to multiple targets becomes a
  measurable CPU/allocation cost on a Raspberry-Pi-class deployment** → Mitigation: reuse a single
  pre-sized buffer for encoding (no per-send allocation), matching the existing performance-conscious
  pattern in the decode pipeline (FR-026's throughput budget). Not expected to be material, but
  called out so it is deliberately checked once, not assumed.

## Migration Plan

- Purely additive: new config block, new hosted service, new settings tab, new (additive) method on
  `QsoAnswererService`. No existing config field, wire message, or public interface changes meaning.
- Deploy as a normal minor-version bump per `release-versioning`; missing `externalReporting` key in
  an existing config file deserialises to fully-inert defaults.
- Rollback: safe at any point — reverting the change removes the feature entirely; even without
  reverting, setting `externalReporting.enabled = false` (the default) fully disables all new network
  activity with no other side effects.

## Open Questions

- Should `Free Text` gain real transmission effect once/if a manual free-message TX feature is
  proposed for OpenWSFZ generally, or should this change's "accepted but no-op" behaviour simply
  persist indefinitely? Deferred — no such feature exists today to wire it to.
- Should a future change expose per-target outbound message-type filtering (e.g. send Decode to
  GridTracker2 but withhold QSOLogged from a different target)? Not requested; the current design
  sends the same full outbound stream to every enabled target uniformly.
- Multicast support (WSJT-X optionally supports a multicast group instead of unicast per-target) is
  not included — every target in `externalReporting.targets` is a unicast UDP destination. Worth
  revisiting if a real multi-listener-on-one-machine use case surfaces. **Updated relevance (D-014,
  see Decision 7):** this is no longer purely hypothetical — Windows' single-winner delivery
  semantics for a `SO_REUSEADDR`-shared unicast port mean genuine simultaneous inbound coexistence
  with a same-machine peer (e.g. GridTracker2) may specifically require multicast to guarantee, not
  just "worth revisiting."
