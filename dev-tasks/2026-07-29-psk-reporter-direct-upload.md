# Developer/Architect handoff: give OpenWSFZ its own direct-to-PSK-Reporter upload path

**Authored by:** QA (per HK-000/HK-015), found live 2026-07-29 during the 40m (radio)/20m (SDR Uno)
dual-instance live-run session (corpus gathering + soak test + external-reporting validation
against real signals).
**Branch:** fresh off `main` (this file lives on `qa/dev-task-psk-reporter-direct-upload`, branched
directly off `main` at `a029574`; do not stack on `feat/external-reporting-single-connection` or any
other in-flight branch).
**Status:** root cause confirmed live, directive given by the Captain, **not designed, not
implemented**. This is new user-facing capability requiring a wire protocol OpenWSFZ does not
currently speak at all — recommend an Architect session (`openspec-propose`/`openspec-explore`)
scope this properly into its own OpenSpec change rather than a quick patch.
**Priority context:** every multi-instance OpenWSFZ session (split-band, split-antenna, SDR-plus-
radio — the exact operating mode the 2026-07-28/29 sessions established as a real, recurring setup)
loses PSK Reporter visibility for OpenWSFZ's own decodes entirely, tonight included. Not a crash, not
data loss — a silent reporting gap that looks fine locally (GridTracker displays everything
correctly) and only shows up if someone thinks to check PSK Reporter's own map directly, which is
exactly how it was caught both times (2026-07-28/29 and again tonight).

## 1. Finding — tonight's direct observation

Running two `OpenWSFZ.Daemon` instances tonight (40m leader on 7.074 MHz, real radio;
20m follower on 14.074 MHz, SDR Uno via Voicemeeter, relayed through the leader per
`feat/external-reporting-single-connection`, commit `e9600ed`), with both instances decoding real
off-air traffic and WSJT-X also running and decoding independently:

- **PSK Reporter's own map** (`pskreporter.info`, monitoring `PD2FZ`) showed exactly one monitor
  entry: `Frequency: 7.077 MHz (40m)`, `Using: WSJT-X v2.7.0`, `Rig: Yaesu FT-991` — i.e. WSJT-X's
  own native reporting, and nothing else. No 20m entry, no entry attributable to either OpenWSFZ
  instance.
- **GridTracker2**, meanwhile, showed **four** distinct instance-selector tabs across its lifetime
  this session: `WSJT-X` (real app, 40m), a stale generic `OpenWSFZ` tab (left over from the ~2
  minutes before this session's build included `feat/external-reporting-single-connection` — see
  `dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md` for that timeline), and two
  live, actively-decoding tabs `OpenWSFZ-40m` (7.074 MHz) and `OpenWSFZ-20m` (14.074 MHz) — both
  showing real Rx Calls/QSO/QSL counts, confirming GridTracker was receiving both OpenWSFZ instances'
  reports correctly at the local level.
- Leader-side log (`OpenWSFZ-40m-capture/logs/openswfz-20260729T182813Z.log`) confirms the relay
  mechanism itself worked exactly as designed: a steady stream of
  `POST /api/v1/external-reporting/relay` requests, each logged
  `external-reporting: enqueuing a N-datagram relay batch from follower 'OpenWSFZ-20m'` — the
  follower never opened its own UDP socket, exactly per `feat/external-reporting-single-connection`'s
  Decision record.

So: GridTracker sees everything, locally, correctly. PSK Reporter sees only WSJT-X. The relay did
not change this outcome.

## 2. Root cause

Two independent facts compound:

**(a) OpenWSFZ has never had its own PSK Reporter uploader.** The original `gridtracker-udp-reporting`
change (2026-07-12, archived) explicitly deferred a direct-to-PSK-Reporter path as future work, on
the stated assumption that "GridTracker2's own relay would cover it exactly as it does for a single
real WSJT-X instance" (`openspec/changes/external-reporting-single-connection/proposal.md:16-18`).
OpenWSFZ's only route to PSK Reporter has always been *through* GridTracker2 acting as a relay.

**(b) GridTracker2's relay-to-PSK-Reporter step only follows one connected WSJT-X-protocol client at
a time**, keyed off the `Id` field carried inside each datagram's payload (not the OS-level UDP
socket/source it arrived from) — this was already established as the reason
`feat/external-reporting-single-connection` was proposed in the first place
(`openspec/changes/external-reporting-single-connection/design.md:8-12`, and
`proposal.md:9-14`: *"PSK Reporter received nothing from either instance all night... GridTracker2's
relay-to-PSK-Reporter behaviour follows whichever WSJT-X-protocol connection is currently focused in
its own UI."*).

**The gap:** `feat/external-reporting-single-connection`'s shipped Decision
(`design.md` line ~89-97) has a follower pre-encode its own WSJT-X-protocol datagrams — with its own
distinct `Id` (e.g. `"OpenWSFZ-20m"`) already baked into the bytes — and simply hands the raw bytes
to the leader, which forwards them verbatim over its one UDP socket. This achieves "one OS-level
socket" but, per tonight's direct observation, does **not** achieve "one GridTracker-visible client":
GridTracker still lists `OpenWSFZ-40m` and `OpenWSFZ-20m` as two separate, persistent tabs, because
its bookkeeping is keyed off the `Id` field content, not the transport source. The design's stated
Goal #1 (*"GridTracker2 ... sees exactly one WSJT-X-protocol connection ... regardless of how many
local OpenWSFZ instances are running"* — `design.md:36-38`) does not hold up against tonight's
evidence. Whatever GridTracker's "one client at a time" PSK-relay rule actually is (first-connected?
a hardcoded preference for a literal `"WSJT-X"` identity? something else internal to a closed-source
app we don't control), it still sees multiple OpenWSFZ identities tonight, same as it did before this
feature existed — and it has picked WSJT-X, not either of them.

**Conclusion:** relying on GridTracker2's relay was always going to be fragile for exactly the
multi-instance operating mode this project has now established as routine. `feat/external-reporting-
single-connection` is not wrong to keep (it correctly fixes the earlier `AppId` collision problem,
gives correct per-band frequency/decode attribution, and centralises Halt-Tx reachability across the
group — see its own design.md Goals), but it does not and structurally cannot fix PSK Reporter
reachability, because that was never actually under OpenWSFZ's control in the first place.

## 3. Directive (Captain, 2026-07-29)

> "I want that PSK reporting stuff available in the application."

Build OpenWSFZ its own native, direct-to-PSK-Reporter upload path — the same category of capability
WSJT-X's own "Enable PSK Reporter Spotting" checkbox already provides — so that PSK Reporter
reachability no longer depends on GridTracker2's relay behaviour at all. This supersedes the "make
GridTracker see us as one connection" angle entirely for the PSK-Reporter-specific goal; per
tonight's conversation, the Captain is not concerned about GridTracker's own tab/UI cosmetics
(multiple instance tabs are fine) — only that OpenWSFZ's own real decodes reach PSK Reporter reliably,
independent of what any third-party companion app does or doesn't relay.

## 4. Open questions for the Architect session that scopes this

This needs a proper `openspec-propose`/`openspec-explore` pass, not a quick patch — flagging what I
already know is unresolved rather than guessing:

- **Wire protocol is unknown/unresearched.** PSK Reporter's ingestion protocol is **not** the same as
  the local WSJT-X-GridTracker UDP protocol `ExternalReportingService`/`WsjtxDatagram` already speak.
  WSJT-X's own native PSK Reporter uploader (the "Enable PSK Reporter Spotting" checkbox) sends spot
  reports directly to PSK Reporter's own ingestion service (historically `report.pskreporter.info`
  UDP, an IPFIX-derived binary framing distinct from the local Heartbeat/Status/Decode datagram
  schema). Do not assume familiarity with this format — it needs real research (WSJT-X's own
  open-source implementation is the authoritative reference; there may also be existing minimal
  reference clients in the ham-radio open-source ecosystem worth reviewing) before any design is
  written, let alone code.
- **Per-instance vs. centralised upload.** Should every OpenWSFZ instance (leader and each follower)
  upload directly to PSK Reporter independently under its own identity, or should the leader be the
  sole uploader on behalf of the whole group (extending `feat/external-reporting-single-connection`'s
  existing relay rather than introducing a second, parallel reporting path)? The latter avoids two
  simultaneous direct connections to PSK Reporter from the same machine/callsign; the former is
  simpler and matches "each instance is independently responsible for its own reporting," consistent
  with how `cycleAudioArchive`/`decodeLog` already work per-instance.
- **Dedup/rate-limit tolerance is unverified.** PSK Reporter presumably already deduplicates spots
  reasonably (a station running multiple simultaneous receivers under one callsign is a normal,
  documented real-world setup, not just this project's test rig) but this project has not confirmed
  PSK Reporter's actual tolerance for multiple near-simultaneous reports of the same received
  callsign/band/mode from one operator. Worth a direct, deliberate small-scale live test once a design
  exists, rather than assuming.
- **Config shape.** Likely a new config section (e.g. `pskReporter`: `enabled`, reusing
  `tx.callsign`/`tx.grid` rather than duplicating them) sitting alongside — not inside —
  `externalReporting`, since this is a genuinely different target/protocol/failure-mode, not another
  GridTracker-style target entry.
- **Does this retire any part of `feat/external-reporting-single-connection`?** No — that change's
  own stated goals (per-band decode/frequency attribution, Halt-Tx reachability across the group,
  zero-behaviour-change default) remain valid and worth keeping regardless of this new capability.
  This dev-task is additive, not a replacement.

## 5. Non-goals

- Not attempting to influence or "fix" GridTracker2's own connection-selection/PSK-relay behaviour —
  it's a third-party closed application outside this project's control, and per tonight's
  conversation, the Captain is explicitly not concerned about its cosmetic multi-tab display.
- Not reopening `feat/external-reporting-single-connection` for rework before this is scoped — it
  solves a real, distinct problem (the `AppId` collision) correctly on its own terms.

## 6. Evidence trail

- `openspec/changes/external-reporting-single-connection/proposal.md` (esp. lines 9-25) — prior
  session's own root-cause writeup for the GridTracker one-client-at-a-time behaviour, and the
  explicit statement that a direct-to-PSK-Reporter path was deferred as future work back in
  `gridtracker-udp-reporting` (2026-07-12).
- `openspec/changes/external-reporting-single-connection/design.md` (esp. lines 1-16, 33-48, 89-97) —
  the shipped Decision that preserves each follower's own `Id` rather than collapsing to one, and the
  Goal statement tonight's evidence contradicts.
- `OpenWSFZ-40m-capture/logs/openswfz-20260729T182813Z.log` — leader-side confirmation the relay is
  mechanically functioning (batches arriving from `OpenWSFZ-20m`, forwarded on schedule).
- Five screenshots from tonight's live session (PSK Reporter map showing only the WSJT-X/40m monitor
  entry; four GridTracker2 instance-tab views: `WSJT-X`, `OpenWSFZ` [stale], `OpenWSFZ-40m`,
  `OpenWSFZ-20m`) — held by the Captain, not committed to the repo (real off-air station data/
  screenshots, NFR-021 privacy posture).
