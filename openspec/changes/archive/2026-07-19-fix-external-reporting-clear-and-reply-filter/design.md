## Context

`external-reporting` (archived `gridtracker-udp-reporting`, 2026-07-12) implements the WSJT-X UDP
network protocol so third-party programs (GridTracker2, JTAlert, N1MM+, ...) can consume OpenWSFZ's
decodes and logged QSOs. Two issues surfaced this session while diagnosing "weird" GridTracker
behaviour, both already root-caused by QA (see `dev-tasks/2026-07-19-external-reply-decode-filter-
bypass-option.md` and `dev-tasks/2026-07-19-external-reporting-clear-every-cycle-defect.md` for the
full investigation trail):

1. `ExternalReportingService.DecodeLoopAsync` sends a Clear datagram before every ~15s decode
   cycle. Real WSJT-X (`NetworkMessage.hpp`'s own documentation) only sends Clear on an explicit
   operator "erase Band Activity window" action or on graceful shutdown. GridTracker2 treats Clear
   as "purge everything accumulated from this source," so every cycle we tell it to forget its own
   map history — confirmed empirically by the Captain (a real WSJT-X-fed map accumulates spots
   over a session; an OpenWSFZ-fed one shrinks between consecutive cycles).
2. `QsoAnswererService.TryEngageExternal` and `QsoCallerService.TryEngageExternalResponder` (via
   `SelectResponderAsync`) both reject an inbound Reply naming a callsign currently hidden under the
   operator's decode-panel filter (`DecodeFilterState`). This is today's shipped, spec'd behaviour
   (FR-054) — the Captain wants it made opt-in, defaulting to "honour it regardless."

## Goals / Non-Goals

**Goals:**
- Stop `ExternalReportingService` from sending a per-cycle Clear datagram; send one instead on
  graceful daemon shutdown, matching WSJT-X's actual second trigger condition.
- Add `externalReporting.restrictExternalRepliesToDecodeFilter` (default `false`): external Reply
  bypasses the decode-panel filter by default; opting in restores today's stricter behaviour.
  Applies identically to both the Answerer and Caller external-reply engagement paths.
- Keep every other consumer of the decode-panel filter — manual browser engagement, internal
  auto-answer/auto-call automation — completely unaffected by the new flag, in both states.

**Non-Goals:**
- Not re-litigating the absolute, non-configurable exclusion of synthetic/unknown-region traffic
  from external output (`ExternalReportingService.IsSuppressedCallsign`) — unaffected, not
  overridable by this or any other setting.
- Not adding an operator-facing "erase decode history" UI action. OpenWSFZ has none today; if one
  is added later, it would be the natural place to emit the real-WSJT-X-equivalent Clear (Window =
  0), but that is out of scope here.
- Not touching `DecodeNoiseSuppressionFilter` (a separate, already-correct two-axis suppression
  setting) or its interaction with `ExternalReportingService`.
- Not changing `WsjtxDatagram.EncodeClear`'s wire format — only the cadence at which it is called
  was wrong, not its byte layout.

## Decisions

### Decision 1 — Remove per-cycle Clear; add shutdown-time Clear

`DecodeLoopAsync` (`ExternalReportingService.cs:395`) drops its unconditional
`SendToAllEnabledAsync(WsjtxDatagram.EncodeClear(AppId))` call entirely; Decode datagrams continue
per-cycle, unchanged. `StopAsync` gains a Clear send alongside its existing `SendCloseToAllAsync`
call (`ExternalReportingService.cs:222-246`), so a GridTracker2 session tracking a stopped
OpenWSFZ instance gets the same "history is gone" signal real WSJT-X would give it on exit.

**Alternative considered:** gate the per-cycle Clear behind a new operator setting instead of
removing it outright. Rejected — there is no scenario in which the per-cycle behaviour is correct
against the real protocol; making it configurable would just let an operator re-introduce a defect,
not a legitimate preference (unlike Decision 2, which genuinely is a preference).

### Decision 2 — `restrictExternalRepliesToDecodeFilter`, default `false`, symmetric across roles

New `ExternalReportingConfig` field, following the existing `honourInboundCommands` pattern
(`[JsonConstructor]` default, absent-key-deserialises-to-default). Consulted at exactly two call
sites: `QsoAnswererService.TryEngageExternal` (self-contained inline filter check — trivial to make
conditional) and a new pre-check inside `QsoCallerService.TryEngageExternalResponder`.

**Alternative considered — Answerer-only scope:** the Captain's original report only exercised the
Answerer role. Rejected in favour of symmetric scope (confirmed with the Captain) so the setting
has one consistent meaning regardless of which controller is currently active, rather than
silently doing nothing for a Caller-role operator.

### Decision 3 — Extract `SelectResponderAsync`'s state-transition core so the manual path keeps filtering unconditionally

`TryEngageExternalResponder` currently reuses `SelectResponderAsync` "unmodified" (original
`gridtracker-udp-reporting` design.md Decision 4) — but `SelectResponderAsync` is also the seam the
manual `POST /api/v1/tx/select-responder` endpoint calls, and that path **must** keep respecting
the decode-panel filter unconditionally regardless of the new flag. Since the filter check is
currently baked into the same method that performs the state transition
(`_pendingResponder*` assignment + wakeup, `QsoCallerService.cs:335-363`), that body is extracted
into a private `SelectResponderCore(string callsign, double frequencyHz, DateTimeOffset
responseCycleStart, DecodeResult? recentDecode)`. `SelectResponderAsync` keeps its existing,
unconditional filter check and then calls the core. `TryEngageExternalResponder` performs its own
conditional filter check (reading the new flag) against `_recentResponderDecodes` directly, then
calls the same core — bypassing `SelectResponderAsync`'s own gate only when it decides to.

**Alternative considered:** thread a `bypassDecodeFilter` parameter through the public
`SelectResponderAsync`/`IQsoController` surface instead. Rejected — that would put an
external-reporting-specific concern onto a general-purpose, interface-level method (also called by
the manual HTTP endpoint and `IQsoController`), and risks a caller accidentally passing the wrong
value. Keeping the bypass entirely inside `QsoCallerService`'s private implementation, expressed as
"call the shared core directly instead of through the filtered entry point," keeps the manual path
structurally incapable of accidentally bypassing the filter.

## Risks / Trade-offs

- **[Risk]** No automated test in this repo drives a real GridTracker2 process, so the Clear-cadence
  fix's actual effect on GridTracker2's map cannot be proven by the test suite alone → **Mitigation**:
  acceptance criteria require a live re-run of the Captain's own before/after comparison (point a
  real GridTracker2 at a patched build for several minutes) before this is called done, mirroring
  how the defect itself was found.
- **[Risk]** Extracting `SelectResponderCore` touches a state-machine method with existing test
  coverage (`QsoCallerServiceTests.cs`) → **Mitigation**: the extraction must be a pure refactor
  (identical behaviour for the manual path); existing tests for `SelectResponderAsync` must pass
  unchanged, plus new tests added for the bypass path specifically.
- **[Risk]** Default-behaviour change for `restrictExternalRepliesToDecodeFilter` (Decision 2) means
  any operator already relying on today's implicit filtering of external Reply will see a different
  result after upgrading, with no explicit action on their part → **Mitigation**: called out as
  **BREAKING (behavioural, not API)** in the proposal and the FR-054 amendment, same convention used
  for prior behavioural-default changes in this project (e.g. `engage-window`).
- **[Trade-off]** The shutdown-time Clear (Decision 1) is best-effort parity with real WSJT-X, not
  something GridTracker2 is known to strictly require — if it complicates `StopAsync` disproportionately,
  it can be deferred without blocking the core fix (removing the per-cycle Clear), per the original
  dev-task's own framing.

## Migration Plan

No data migration. Config default (`restrictExternalRepliesToDecodeFilter: false`) makes the new
behaviour effective immediately for anyone upgrading with `externalReporting.enabled: true` and
`honourInboundCommands: true` — no action required to get the requested "honour external Reply
regardless of panel filter" behaviour; the checkbox exists only for operators who want to opt back
into the old, stricter behaviour. The Clear-cadence fix requires no config change at all — it takes
effect for every existing `externalReporting`-enabled installation on upgrade.

## Open Questions

- Should the shutdown-time Clear (Decision 1) be scoped to this change or split into a follow-up?
  Recommendation: include it here since it's a small addition alongside code already being touched,
  but it is not load-bearing for the reported symptom — flag back to QA if it's judged out of scope
  during implementation rather than silently dropping it.
