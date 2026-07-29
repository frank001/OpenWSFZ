## Context

`ExternalReportingService` (from `gridtracker-udp-reporting`, hardened by
`fix-external-reporting-clear-and-reply-filter` and `fix-external-reporting-appid-collision`) already
implements the WSJT-X UDP protocol correctly for exactly one OpenWSFZ instance talking to exactly one
set of external targets. `fix-external-reporting-appid-collision` made two simultaneous instances
individually well-behaved (distinct `Id`, no cross-instance Clear-wipe), and the 2026-07-28/29 live
session confirmed GridTracker2 itself now displays both correctly. What it cannot fix, because it is
outside OpenWSFZ's control, is that GridTracker2's own relay-to-PSK-Reporter step appears to follow
only one connected WSJT-X-protocol client at a time (its own `◀ WSJT-X ▶` instance selector implies
exactly this). Two distinctly-identified, simultaneously-connected instances are, from PSK Reporter's
point of view, indistinguishable from "one of them isn't there."

The Captain's directive is to make OpenWSFZ itself present as a single logical connection whenever
more than one local instance needs to reach the same external target — matching the one thing
GridTracker2 is already known to handle correctly (one real WSJT-X instance).

Relevant existing seams this design builds on rather than duplicates:
- `ExternalReportingService.SendToAllEnabledAsync` and its `_targetsLock`-guarded target list — the
  leader-side dispatch point a relayed batch needs to reach; no new UDP-sending code path, only a new
  *source* of datagrams feeding the existing one.
- `WsjtxDatagram.Encode*` — a follower keeps encoding its own datagrams exactly as today (same
  `InstanceId`-reading call sites, same absolute synthetic/unknown-region exclusion in
  `DecodeLoopAsync`/`BuildStatusFields`/`NotifyQsoLogged`). Relaying moves *where the encoded bytes get
  sent from*, not how they are built or filtered.
- `IConfigStore.OnSaved` / `Reconcile` — the existing live-reconfiguration path
  (`fix-external-reporting-appid-collision`'s design already established that `externalReporting`
  changes apply without a daemon restart); `role` changes reuse the same event.
- Each daemon's own already-running Kestrel host (`daemon-host`) — the transport for the new relay
  endpoint is "the other instance's existing local HTTP server," not a new listener/port to configure
  or firewall.

## Goals / Non-Goals

**Goals:**
- GridTracker2 (and, through it, PSK Reporter) sees exactly one WSJT-X-protocol connection per
  external target, regardless of how many local OpenWSFZ instances are running, when those instances
  are configured into a leader/follower group.
- A follower's Status-then-Decode ordering for a single decode cycle is never split by another
  source's Status landing in the middle of it — the actual mechanism that makes "single connection"
  true, not just true-looking.
- Zero behaviour change for every operator who does not opt in: default `role: "leader"` with no
  followers configured reproduces `ExternalReportingService`'s current behaviour exactly, byte for
  byte.
- A follower never goes silently dark: if its leader is unreachable, it falls back to exactly what a
  `"leader"` instance does today (direct send, own `instanceId`), not to dropping its own traffic.
- Halt Tx, already an unconditional safety control, becomes reachable across the whole local group,
  not just whichever instance GridTracker2 happens to be focused on.

**Non-Goals:**
- Not building automatic leader election, service discovery, or a membership protocol. Both `leaderUrl`
  (follower→leader) and `followerUrls` (leader→followers, Halt-Tx-broadcast only) are static, explicit
  config — consistent with how an operator already assigns distinct `port`/`instanceId` values by hand
  today. A dynamic registry is more moving parts for a scenario that is, in practice, one human
  configuring two `config.json` files on one desk.
- Not routing inbound **Reply** to the follower that actually decoded the named callsign. v1 scope is
  Reply acts on the leader's own current decode batch only, exactly as a single-instance leader does
  today; see Decision 5 for why this is an acceptable v1 limitation and Risks for the operator-visible
  consequence.
- Not changing any wire-format detail, the absolute synthetic/unknown-region exclusion, or the
  Clear-on-shutdown-only behaviour. This design only changes *which socket a fully-formed datagram
  goes out on*.
- Not adding authentication to the new relay endpoint beyond loopback/LAN trust — matches
  `remote-access`'s existing accepted trade-off for exactly the same reason (see that capability's own
  design.md), and the relay endpoint carries no more capability than the UDP channel it replaces
  (it can only cause OpenWSFZ to broadcast already-filtered datagrams or invoke `AbortAsync`).

## Decisions

### 1. `role` config field: `"leader"` (default) or `"follower"`, no third mode

**Decision:** `ExternalReportingConfig` gains `Role` (string enum, default `"leader"`). A `"leader"`
instance is byte-for-byte today's `ExternalReportingService`. A `"follower"` instance never opens a
socket to its `targets` at all — everything it would have sent goes to its leader instead.

**Why:** A leader with zero followers must be indistinguishable from today's behaviour for existing
configs to keep working untouched; making `"leader"` the default and the only behaviour-preserving
value achieves that for free. Two modes (not three, no separate "standalone" value) keeps the config
surface as small as the actual behavioural difference — a leader already behaves exactly like a
standalone instance whenever no follower is relaying to it.

**Alternatives considered:** A boolean `isFollower`/`leaderUrl-presence-implies-follower` (skip the
enum). Rejected: an explicit `role` string is self-documenting in a saved config file and in the
Settings-page's eventual UI, and leaves room for the field to mean something else on the leader side
(it doesn't today, but `"leader"` reads correctly next to a populated `followerUrls`).

### 2. Relay transport: follower POSTs already-encoded datagram bytes, leader is a byte-blind forwarder

**Decision:** `POST /api/v1/external-reporting/relay` on the leader accepts a JSON body: `{
followerInstanceId: string, datagrams: [ { type: string, bytesBase64: string } ] }` — a follower packs
one or more already-`WsjtxDatagram.Encode*`-produced byte arrays (base64) into a single POST per
"moment" (one decode cycle's Status+Decode set, or a single Heartbeat/QSOLogged/Clear/Close). The
leader does not decode, reinterpret, or re-derive anything from the payload — it hands each byte array
to the exact same `SendToAllEnabledAsync` its own outbound path already uses, in array order, for the
one HTTP request, before accepting the next.

**Why:** The follower's own encoding logic (`InstanceId` read-live-at-send-time, the absolute
synthetic/unknown-region exclusion applied *before* encoding) needs zero changes and stays exercised
by its existing unit tests unmodified — relaying is purely a change of transport for bytes that are
already correct and already filtered. A leader that only forwards opaque bytes also can never
re-introduce a filtering bug on the relay path by accident, since it never touches decoded field
values at all.

**Alternatives considered:** Relaying structured/semantic fields (e.g. a JSON `DecodeFields` object)
and re-encoding on the leader. Rejected: doubles the surface that must track the WSJT-X wire format
(follower's encoder and leader's re-encoder could drift), and gains nothing — the leader has no reason
to inspect field values it will never act on differently per-source.

### 3. Ordering guarantee: one POST = one atomic, in-order dispatch; a single-consumer queue on the leader serialises across followers

**Decision:** The leader's relay endpoint handler enqueues each accepted POST's `datagrams` array,
in full and in order, onto a single-consumer channel already drained by the same dispatch loop the
leader's own Status/Decode traffic goes through (i.e. the leader's own outbound sends and every
follower's relayed batches all funnel through one serial sender). A batch is never partially sent
before the next queued batch (from any source, including the leader's own) begins.

**Why:** This is the actual mechanism that makes "single connection" correct rather than merely
labelled — see Context: the WSJT-X Status message models one operator on one band at a time. Without
this guarantee, a leader that itself sends Status(40m) while a follower's relayed Status(80m)+Decode
batch is only half-sent would let a subsequent Decode be attributed to the wrong dial frequency,
actively corrupting spots rather than just dropping them (the same failure mode a naive shared-Id
approach would have hit, identified live before design work started). Queuing at "one HTTP POST" (not
"one datagram") granularity is what keeps a follower's own internally-correct Status-then-Decode
sequence intact across the relay hop.

**Alternatives considered:** Per-datagram-type locking (e.g. a global "Status lock" held from send-
Status to send-of-its-associated-Decodes). Rejected: more complex, and the follower already knows the
correct grouping (one decode cycle) at the point it builds one POST body — no reason to reconstruct
that grouping on the leader side from finer-grained pieces.

### 4. Leader-unreachable degrade: fall back to direct send under the follower's own `instanceId`, not silence

**Decision:** A follower's relay attempt that fails (connection refused, timeout, non-2xx) logs a
Warning (same `_resolutionWarned`-style once-per-failure-state pattern `SendToAllEnabledAsync` already
uses, not a warning per datagram) and, for that send, falls back to opening its own direct UDP send to
`targets` under its own `instanceId` — i.e. degrades to exactly `"leader"`-role behaviour for the
duration the leader is unreachable. Reconciliation back to relay-through-leader is automatic: the very
next successful relay attempt resumes it, no restart or manual action required.

**Why:** Going dark is strictly worse than tonight's already-working baseline (two distinctly-
identified direct connections); a follower that can't reach its leader still has a fully correct,
already-shipped fallback available for free. This also means a leader instance being restarted for any
reason (config change, crash, deliberate) never blacks out its followers' external visibility, only
temporarily returns them to pre-this-change behaviour.

**Alternatives considered:** Queue-and-retry (buffer relay attempts, replay once the leader returns).
Rejected for v1: a buffered, out-of-order replay of stale decodes on reconnect is worse for a live
map/spot consumer than either (a) the direct-send fallback (real-time, just briefly dual-identified
again) or (b) accepting a genuine gap — and direct-send-fallback is strictly better than either.

### 5. Inbound Halt Tx broadcasts to `followerUrls`; inbound Reply stays leader-scoped in v1

**Decision:** On receiving inbound Halt Tx, the leader calls its own `IQsoController.AbortAsync` (as
today) **and** POSTs the equivalent internal abort to every URL in its own `followerUrls` list
(reusing each follower's own already-existing local abort surface — `POST /api/v1/tx/abort`, the same
one `HandleHaltTxAsync` calls into today). Inbound Reply continues to resolve only against the
leader's own current decode batch, exactly as today's single-instance behaviour — a Reply naming a
callsign a *follower* actually decoded will not engage on that follower via this path in this change.

**Why:** Halt Tx is the one inbound command already documented as unconditional/always-honoured
regardless of any opt-in — broadcasting it to every follower is a strict safety improvement (an
operator hitting Halt Tx almost never means "only this one band"), and it is a no-op, not a hazard, on
a follower that wasn't transmitting. Reply is opt-in, not safety-related, and correctly routing it
requires the leader to track *which follower most recently decoded which callsign* — a genuinely
separate piece of state and design surface this change does not need in order to close tonight's PSK
Reporter gap. Scoping it out keeps this change reviewable and shippable; it is called out here,
explicitly, rather than silently mishandled (see Risks).

**Alternatives considered:** Full per-callsign inbound routing in this same change. Rejected for v1
scope/size; tracked as a natural follow-up once this lands and its `followerUrls`/relay plumbing
already exists to build on.

## Risks / Trade-offs

- **[Risk]** An operator running a relayed follower may expect GridTracker2's Reply button to work for
  a station only the follower decoded, and be confused when it silently does nothing (today's existing
  "no callsign extracted" / "no `IExternalReplyTarget`" logging does not cover "wrong instance" as a
  reason). → **Mitigation:** design.md Decision 5 documents this explicitly as v1 scope; tasks.md
  includes a log line on the leader distinguishing "Reply named a callsign not in my own current decode
  batch" from other Reply-ignored reasons, so the gap is diagnosable rather than mysterious, pending the
  follow-up.
- **[Risk]** The relay HTTP hop adds a new failure mode (leader's Kestrel host down/slow) that didn't
  exist when every instance spoke UDP directly. → **Mitigation:** Decision 4's degrade-to-direct-send
  makes this fail open to today's already-correct behaviour, not fail closed to silence.
- **[Risk]** `followerUrls` is manually kept in sync with which followers actually exist; a stale entry
  just means an occasional failed POST to a follower that's no longer running. → **Mitigation:** treat
  exactly like `SendToAllEnabledAsync`'s existing per-target unresolvable-host handling — log once,
  keep retrying silently, never block delivery to the followers that do resolve.
- **[Trade-off]** No authentication on the relay endpoint. → Accepted, matching `remote-access`'s
  existing loopback/LAN trust-boundary precedent (see Non-Goals); the endpoint's blast radius is no
  larger than the UDP channel it replaces.

## Migration Plan

Purely additive and opt-in; no migration step is required for any existing config. An operator who
wants the new behaviour edits both instances' `config.json` (or uses the eventual Settings-page
control, out of scope for this change per FR-016 — same "backend first" gating
`gridtracker-udp-reporting` itself followed): set the intended leader's `followerUrls` to include the
follower's base URL, and the follower's `role: "follower"` + `leaderUrl` pointing at the leader.
Rollback is symmetric: setting `role` back to `"leader"` (or removing it) on the follower instantly
reverts to today's already-shipped, already-verified two-distinct-instances behaviour, live, via the
existing `OnConfigSaved`/`Reconcile` path — no restart required.

## Open Questions

- Should `followerUrls` eventually be inferred automatically (e.g. from `port`s already known to be
  running on `127.0.0.1` at daemon-list time) rather than hand-configured? Deferred — see Non-Goals;
  revisit only if hand-configuring two URLs proves to be a real operator pain point in practice, not
  pre-emptively.
- Full inbound-Reply routing to the originating follower (Decision 5's deferred half) — worth scoping
  as its own follow-up change once this one is live and the Captain has a live session's worth of
  feedback on how much the v1 limitation is actually felt.
