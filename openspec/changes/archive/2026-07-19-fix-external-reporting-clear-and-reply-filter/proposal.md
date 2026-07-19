**User-facing:** yes

## Why

Two independent problems surfaced this session while the Captain diagnosed "weird" behaviour
between OpenWSFZ and GridTracker2, both already root-caused by QA (see
`dev-tasks/2026-07-19-external-reply-decode-filter-bypass-option.md` and
`dev-tasks/2026-07-19-external-reporting-clear-every-cycle-defect.md` for the full investigation
trail — this proposal formalises both rather than re-deriving them):

1. **Confirmed defect:** `ExternalReportingService` sends a WSJT-X-protocol Clear datagram before
   *every* ~15-second decode cycle. Real WSJT-X only sends Clear on an explicit operator
   "erase Band Activity window" action or on graceful shutdown (per WSJT-X's own
   `NetworkMessage.hpp` protocol documentation) — never on its ordinary decode cadence, which is
   identical to ours. GridTracker2 treats Clear as "discard everything you've accumulated from
   this source," so every cycle we are telling it to purge its own map history. The Captain
   confirmed this empirically: a WSJT-X-fed GridTracker2 map accumulates spots across a session;
   an OpenWSFZ-fed one shrinks between consecutive 15-second cycles. This shipped as part of
   `gridtracker-udp-reporting` (archived 2026-07-12) and was verified against its own — incorrect
   — spec expectation, so it passed review and tests without anyone catching the mismatch against
   the real protocol.
2. **Requested behaviour change:** separately, the Captain reported that an inbound GridTracker
   "Reply" command (asking OpenWSFZ to engage a specific decoded station) is silently ignored
   whenever that callsign is currently hidden under the operator's own decode-panel filter
   (`DecodeFilterState`). This is today's shipped, spec'd behaviour (FR-054) and is not a defect —
   but the Captain wants it configurable: by default, an explicit external command should be
   honoured regardless of what the operator's own panel view happens to be filtering, with an
   opt-in to restore the stricter behaviour for anyone who wants it.

Both items touch the same `external-reporting` capability and were investigated together, but are
otherwise unrelated — one is a protocol-conformance bug fix, the other is a new opt-in setting. They
are wrapped into one change at the Captain's request.

## What Changes

- Remove the per-decode-cycle Clear datagram send from `ExternalReportingService.DecodeLoopAsync`.
  Decode datagrams continue to be sent every cycle, unchanged. A single Clear datagram is sent
  instead on graceful daemon shutdown, alongside the existing Close datagram, matching WSJT-X's
  actual second trigger condition.
- **BREAKING (behavioural, not API):** GridTracker2 (and any other WSJT-X-protocol consumer) fed by
  OpenWSFZ will retain decode/spot history across a session instead of having it purged every
  cycle — a materially different, and correct, on-map experience for anyone already using this
  feature.
- Add a new opt-in `externalReporting.restrictExternalRepliesToDecodeFilter` config field
  (default `false`). When `false` (new default), an inbound Reply naming a callsign hidden under
  the active decode-panel filter is still honoured — the external command is treated as
  authoritative. When `true`, today's stricter behaviour (filtered-out callsigns rejected) is
  preserved. Applies symmetrically to both the Answerer (`TryEngageExternal`) and Caller
  (`TryEngageExternalResponder`/`SelectResponderAsync`) engagement paths.
- **BREAKING (behavioural, not API):** the default behaviour of external Reply changes for anyone
  already using `honourInboundCommands` with a narrowed decode-panel filter — Reply commands that
  were previously silently dropped will now engage.
- Explicitly **not** changed by either item: the manual/browser engagement paths (double-click,
  `POST /api/v1/tx/select-responder`, `POST /api/v1/tx/engage-decode`), the internal
  auto-answer/auto-call automation scans, and `ExternalReportingService`'s own absolute,
  non-configurable exclusion of synthetic/unknown-region traffic — all continue to respect the
  decode-panel filter (or their own independent rules) exactly as today, in every case.
- New "External Programs" settings-tab checkbox for the new config field, alongside the existing
  "Honour inbound commands" control.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `external-reporting`: "Outbound Clear message" requirement corrected to reflect real WSJT-X
  semantics (shutdown-triggered, not per-decode-cycle); its "Outbound Decode message" requirement
  loses the now-invalid "still sends Clear" scenario; its Settings-page tab requirement gains the
  new checkbox.
- `configuration`: `externalReporting` config schema gains
  `restrictExternalRepliesToDecodeFilter` (bool, default `false`), round-tripped the same way as
  the existing `honourInboundCommands` field.
- `qso-answerer`: "External reply engages a specific decoded CQ" requirement's "filtered-out
  callsign is a no-op" scenario becomes conditional on the new config flag, with a new default-case
  scenario for the bypass.
- `qso-caller`: the "None mode — SelectResponderAsync rejects a filtered-out callsign" requirement
  gains an explicit carve-out for calls arriving via the external-reply entry point, conditional on
  the same new flag; the manual/browser entry point's behaviour is unchanged.

## Impact

- `src/OpenWSFZ.Daemon/ExternalReportingService.cs` — `DecodeLoopAsync` (remove per-cycle Clear),
  `StopAsync`/`SendCloseToAllAsync` (add shutdown-time Clear).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `TryEngageExternal`.
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — `SelectResponderAsync`, `TryEngageExternalResponder`
  (requires extracting the state-transition core so the manual and external-reply entry points can
  apply the decode-filter check independently — see design.md).
- `src/OpenWSFZ.Abstractions/ExternalReportingConfig.cs` — new field.
- `web/settings.html`, `web/js/settings.js` — new checkbox in the External Programs tab.
- `openspec/specs/external-reporting/spec.md`, `openspec/specs/qso-answerer/spec.md`,
  `openspec/specs/qso-caller/spec.md` — delta specs.
- `REQUIREMENTS.md` — amend FR-053 (Clear cadence) and FR-054 (external reply filter conditionality).
- `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`,
  `QsoAnswererServiceExternalReplyTests.cs`, `QsoCallerServiceTests.cs`,
  `tests/OpenWSFZ.Config.Tests/ExternalReportingConfigTests.cs`.
- Per project policy, this change touches the answerer/caller decode-filtering hook directly:
  `qa/decode-filter-synth-verify/live_verify_9_axes.py` must be re-run before merge, and the
  Clear-cadence fix should additionally be confirmed live against a real GridTracker2 instance
  (no automated test here drives one).
