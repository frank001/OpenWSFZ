# `external-reporting-single-connection` — live verification

**Date:** 2026-07-29, 18:37:45–19:26:30 local (~49 minutes). **Not previously written up** — this
directory (leader/follower config, logs, console output) is the only record of this session; it
sat committed nowhere until 2026-07-31, found and screened by the Architect (see
`qa/cycleframer-alignment-replay/2026-07-31-1414-…-land-untracked-work-and-merge-sequence.md`
§3) and confirmed clean by QA before commit.

## What was set up

Two simultaneous OpenWSFZ instances on one machine, reporting to the same local GridTracker2
instance (`127.0.0.1:2237`) under one shared identity, per the `external-reporting-single-connection`
design (leader/follower HTTP relay):

- **`leader/`** — port 8090, `instanceId: "OpenWSFZ-40m"`, `role: "leader"`, `followerUrls:
  ["http://127.0.0.1:8091"]`. Real station identity throughout: `tx.callsign = "PD2FZ"`,
  `tx.grid = "JO33"` (NFR-021 exception).
- **`follower/`** — port 8091, `instanceId: "OpenWSFZ-20m"`, `role: "follower"`, `leaderUrl:
  "http://127.0.0.1:8090"`. Same `PD2FZ`/`JO33` identity.

Both sides had `externalReporting.enabled: true` targeting the same GridTracker2 target. The
follower relays its decodes to the leader over HTTP (`POST /api/v1/external-reporting/relay`);
the leader is the only instance actually talking to GridTracker2, so GridTracker2 sees one logical
connection instead of two competing instances under the same callsign — the problem this design
exists to solve (see `openspec/specs/external-reporting/spec.md`).

`leader-config-before.json` / `leader-config-disabled.json` at the top of this directory are
config snapshots taken at different points in the session (before enabling `externalReporting`,
and with it explicitly disabled) — kept for the same reason as the running configs.

## What was verified

- **776 relay POSTs**, leader-side, all `HTTP 200` bar the one transient failure below. Follower
  and leader each logged **195 decode cycles** over the session — matched 1:1, consistent with
  both instances running the entire window without drift or restart.
- **The fallback path was genuinely exercised, not just designed.** At `18:56:11` the follower's
  relay to the leader got back `HTTP 503` and logged `degrading to direct send under this
  instance's own instanceId until the leader becomes reachable again` — the documented degrade
  behaviour firing for real, not a simulated fault. It self-recovered 15 seconds later
  (`18:56:26`, `leader at 'http://127.0.0.1:8090' reachable again - resuming relay`) with no
  intervention. This is the one `WRN` in either console log; the leader log has zero
  warnings/errors for the full session.
- **No callsign leakage.** Both `config.json`s carry only the allowed `PD2FZ`/`JO33` exception.
  Console and daemon logs record decode counts and cycle metadata only (`N decode(s) found,
  elapsed=… ms`), never message text or per-decode callsigns. Re-screened by QA on 2026-07-31
  across every file in this directory (configs, logs, reference JSON) with a callsign-shaped
  regex — zero hits outside `PD2FZ`.

## What was not verified / left open

- **Whether GridTracker2 actually forwarded to PSKReporter correctly is not established by this
  directory.** These logs show the relay working locally (follower → leader → GridTracker2); they
  say nothing about GridTracker2 → PSKReporter, which was a separate, confounded observation from
  the same session (see the memory note below) — the real WSJT-X application's own independent
  native PSKReporter-spotting feature was running on the same machine at the same time, so
  PSKReporter activity in that session can't be attributed to this relay alone from this evidence.
- **The GridTracker2 native-multicast alternative was never evaluated here.** GridTracker2 has a
  `Multicast?` toggle (General tab, "Receive UDP Messages") that might have solved the
  single-logical-connection problem more simply than this leader/follower relay — raised directly
  by the Captain during the same session, not addressed in `design.md`'s "Alternatives
  considered", and not something this test setup was built to answer. Tracked as a standing TODO
  (QA memory: `gridtracker-multicast-alternative-todo.md`) — a candidate simplification for an
  Architect-level look next time this capability is touched, not a reason to revisit the shipped
  design now.

## Files

| path | what it is |
|---|---|
| `leader/config.json`, `follower/config.json` | the two instances' running config |
| `leader-config-before.json`, `leader-config-disabled.json` | config snapshots at other points in the session |
| `leader/console.log`, `follower/console.log` | full stdout for the session (2,586 / 614 lines) — the primary evidence trail; the source for every number in this README |
| `leader/callsign-grammar.json`, `follower/callsign-grammar.json`, and the matching `callsign-regions.json`/`frequencies.json`/`prop-modes.json` | reference data snapshots each instance loaded, not test output |

`leader/logs/*.log` and `follower/logs/*.log` (the structured Serilog daemon logs, startup-only,
short) exist on disk but are **not part of this commit** — repo-wide `.gitignore` excludes every
`logs/` directory, and there is no `console.log`-style carve-out for this one. `console.log`
above already carries the same content plus the full cycle-by-cycle record, so nothing evidentiary
is lost.
