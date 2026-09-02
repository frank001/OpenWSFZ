**User-facing:** yes

## Why

The 2026-07-28/29 dual-receiver live session (40m via radio, 80m via SDR, two simultaneous
`OpenWSFZ.Daemon.exe` instances) exercised `fix-external-reporting-appid-collision` (b400425) and
confirmed it works: GridTracker2 now shows both instances distinctly instead of one clobbering the
other. But it surfaced a second, deeper problem that fix did not — and could not — address: PSK
Reporter (`pskreporter.info`) received nothing from either instance all night. Root cause is not a
bug in either instance's own datagrams; it is that GridTracker2's relay-to-PSK-Reporter behaviour
follows whichever WSJT-X-protocol connection is currently focused in its own UI (a `◀ WSJT-X ▶`
instance selector is visible in GridTracker2 itself), so at most one of two simultaneously-connected,
distinctly-identified OpenWSFZ instances ever gets relayed onward — silently, with neither instance
receiving any error to log.

`gridtracker-udp-reporting` (2026-07-12, archived) explicitly deferred a direct-to-PSK-Reporter
upload path as future work, on the assumption that GridTracker2's own relay would cover it exactly as
it does for a single real WSJT-X instance. That assumption holds for one OpenWSFZ instance; it breaks
for two or more running simultaneously on the same machine, which is now a demonstrated real
operating mode (split-band, split-antenna, or SDR-plus-radio setups), not a hypothetical one.

The Captain's direction: OpenWSFZ should own this, not push it onto GridTracker2's own
per-instance-selection behaviour. When multiple local instances need to reach the same external
target, they SHALL present as a single logical connection — exactly what GridTracker2 (and, through
it, PSK Reporter) already knows how to handle correctly for one real WSJT-X instance.

## What Changes

- Add an `externalReporting.role` config field: `"leader"` (default) or `"follower"`. A `"leader"`
  instance behaves exactly as `ExternalReportingService` does today — opens its own outbound/inbound
  UDP sockets and speaks the WSJT-X protocol directly to its configured `targets`. This is fully
  backward compatible: an existing config with no `role` key, or every instance's `role` left at
  `"leader"`, reproduces today's behaviour byte-for-byte, including the side-by-side distinct-
  `instanceId` mode `fix-external-reporting-appid-collision` shipped — that mode remains supported for
  operators who don't need PSK Reporter relay and are content with two separate GridTracker2 entries.
- A `"follower"` instance opens **no** outbound/inbound UDP sockets to `targets` at all. Instead it
  builds its WSJT-X-protocol datagrams exactly as it always has (same encoding, same absolute
  synthetic/unknown-region exclusion, same everything) and relays the already-encoded bytes to a
  configured leader over local HTTP, in place of a direct UDP send. Add `externalReporting.leaderUrl`
  (required when `role = "follower"`): the leader daemon's own base URL (e.g. `http://127.0.0.1:8080`
  — every daemon already runs a local Kestrel host on its configured `port`).
- Add a new leader-side HTTP endpoint, `POST /api/v1/external-reporting/relay`, that accepts an
  ordered batch of pre-encoded datagrams from a follower and sends that batch, atomically and in
  order, to every one of the leader's own enabled targets — so a follower's Status-then-Decode
  ordering for one decode cycle is never split across an interleaving Status from a different
  follower or from the leader's own band. This is the mechanism that makes "single connection to the
  outside" actually true at the wire level, not just at the config level (see design.md for why a
  shared `instanceId` alone is insufficient).
- Add `externalReporting.followerUrls` (leader-side, string list, default empty): the local base URLs
  of any followers this leader should forward an inbound **Halt Tx** to, in addition to acting on it
  itself — an operator hitting Halt Tx in GridTracker2 almost always means "stop transmitting,
  whichever of my stations is doing it," and broadcasting an abort to an idle follower is a safe
  no-op. Inbound **Reply** remains scoped to the leader's own band only in this change (see design.md
  "Inbound Reply routing — v1 scope limitation"); a follower's own local UI is unaffected and remains
  fully usable for its own QSO automation regardless of role.
- A follower that cannot reach its configured leader (leader not yet started, restarting, or
  misconfigured `leaderUrl`) SHALL degrade to sending directly to `targets` under its own
  `instanceId`, exactly as `"leader"` role does today, logging a Warning — never silently going dark
  — and SHALL reconcile back to relay-through-leader automatically once the leader becomes reachable
  again.
- No change to any existing outbound message type's field content, the absolute synthetic/unknown-
  region exclusion, the Clear-on-shutdown-only behaviour, or the inbound Halt-Tx/Reply/Free-
  Text/Close handling that already exists on whichever instance ends up as the effective UDP owner.

## Capabilities

### New Capabilities

(none — this extends the existing `external-reporting` capability rather than introducing a new
domain)

### Modified Capabilities

- `external-reporting`: adds the leader/follower relay model described above — `role` config,
  the follower's relay-instead-of-direct-send behaviour, the new leader-side relay HTTP endpoint and
  its ordering guarantee, the leader-unreachable degrade-and-reconcile behaviour, and Halt-Tx
  broadcast to configured followers.
- `configuration`: `ExternalReportingConfig` gains `role` (default `"leader"`), `leaderUrl`
  (nullable, follower-only), and `followerUrls` (list, leader-only, default empty). `GET`/`POST
  /api/v1/config` round-trip all three.

## Impact

- **Code**: `OpenWSFZ.Daemon/ExternalReportingService.cs` (role-aware send path: direct-UDP vs.
  relay-POST, plus the new relay-ingestion/dispatch logic when acting as a leader);
  `OpenWSFZ.Abstractions/ExternalReportingConfig.cs` (three new fields); `OpenWSFZ.Web/WebApp.cs` (new
  `POST /api/v1/external-reporting/relay` endpoint, config round-trip for the new fields).
- **Config**: additive only. Every existing `externalReporting` block continues to work unchanged;
  the relay model is opt-in per instance via `role: "follower"` plus `leaderUrl`.
- **Network**: adds a second local (loopback-by-default, same trust model as `remote-access`)
  HTTP surface between co-located daemon instances, alongside the existing UDP surface to external
  targets. No new traffic leaves the machine beyond what a single `"leader"` instance already sends
  today.
- **Requirements**: new FRs appended to `REQUIREMENTS.md` §4.1, starting at FR-063.
- **Depends on**: `fix-external-reporting-appid-collision` (b400425) having landed — `instanceId`
  remains the wire identity a `"leader"` instance (or a relaying follower's leader) uses; this change
  does not replace or revert that mechanism, only adds a second mode on top of it.
