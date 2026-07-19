## Context

`IQsoController` already exposes `State { get; }`, `Partner { get; }`, and `Keying { get; }` as
read-only properties, each implemented once per service and delegated through
`QsoControllerRouter.ActiveController` (`src/OpenWSFZ.Daemon/QsoControllerRouter.cs:78-97`) to
whichever role is currently active — this is the established pattern for "expose a piece of live
state from whichever service is running." `TxStatusResponse` and the `txState` WebSocket push
(`WsTxStateMessage`) are both built from these same three properties at every call site
(`src/OpenWSFZ.Web/WebApp.cs`, `src/OpenWSFZ.Web/AppJsonContext.cs:132-157`).

Neither carries the actual transmitted message text today. `QsoAnswererService` already tracks it
internally as `_lastTxMessage` (`src/OpenWSFZ.Daemon/QsoAnswererService.cs:87`, set at every TX
composition site: 898, 994, 1017, 1089, 1167, and reused verbatim for retries at 1273) but never
exposes it. `QsoCallerService` has no equivalent field at all — `reportMessage`/`rr73Message`/
`cqMessage` are local variables inside their respective methods.

On the frontend, `web/js/main.js`'s `renderMessageRows()` (lines 178-233) computes all three TX
message rows from a static per-role template array (`texts[0..2]`) keyed only by `partner`,
`txCallsign`, `txGrid` — never anything transmission-specific. The QSO Transcript's sent-entry
logging (`appendTranscriptEntry('sent', texts[activeIndex], currentTxPartner)`, line 231) reuses
that same template array. Both were correct by construction before `fix-tx-report-real-snr`
(TX-D04) shipped, because the real value really was always `+00`/`R+00`. They are now stale.

Critically, the daemon only ever needs to track the *single most recent* transmitted message, not
a full per-row history — the frontend already re-renders all three rows on every `txState` push and
is well-placed to remember "the real text I was told for row N" locally for the lifetime of the
current tracked QSO, exactly the way it already remembers `currentTxPartner`/`currentTxRole`/etc.

## Goals / Non-Goals

**Goals:**
- Every already-transmitted TX message row (`#tx-msg-1/2/3`) and every QSO Transcript `sent` entry
  shows the real message actually transmitted, not a template guess.
- A row not yet reached this session continues to show the existing template — there is no real
  content to show for something that hasn't been sent yet, and the template is still correct there.
- No change to how received-message capture, matching, rolling-log cap, or partner-change
  separators work (`web/js/qsoTranscript.js`) — untouched, out of scope.
- Minimal backend surface: one new field, following the exact existing `State`/`Partner`/`Keying`
  pattern, not a new subsystem.

**Non-Goals:**
- Backend-side per-row history tracking. The daemon exposes only "the last message I transmitted";
  reconstructing per-row history from that stream is a frontend concern (see Decisions).
- `D-CALLER-022` — separate, investigation-only, not part of this change.
- Any change to `IsRogerReport`/`FormatSnrReport`/report-composition logic itself — TX-D04 already
  fixed the *content*; this change only fixes *visibility* of that already-correct content.

## Decisions

**Add `string? LastTxMessage { get; }` to `IQsoController`, implemented identically to
`State`/`Partner`/`Keying`.** `QsoAnswererService` returns its existing `_lastTxMessage` field
directly (already correct, just never read externally). `QsoCallerService` gains a new
`_lastTxMessage` field (mirroring the answerer's naming), set at its three TX-composition sites
(`ExecuteTxReportAsync`, `RetryOrAbortAsync`'s two retransmit branches, and the CQ/RR73 composition
points) alongside the existing `_rstSent` persistence TX-D04 already added. `QsoControllerRouter`
delegates via `ActiveController.LastTxMessage`, same one-line pattern as the three existing
properties.

*Alternative considered*: expose three separate fields (`LastCqMessage`, `LastReportMessage`,
`LastFinalMessage`) so the backend tracks full per-row history itself. Rejected — this triples the
new surface area for no benefit, since the frontend already re-renders on every push and is a
cheaper, more natural place to remember "the last thing I was told for this row" (see next
decision). It would also need its own reset-on-new-QSO logic duplicated three times instead of
once.

**Thread `LastTxMessage` into `TxStatusResponse` and `WsTxStateMessage` as a new nullable
field**, populated at every existing call site that already reads `State`/`Partner`/`Keying` from
the active controller (`WebApp.cs`'s status-returning endpoints, `WebSocketHub.BroadcastTxState`'s
call site). `null` when nothing has been transmitted yet this process lifetime (fresh start, or
never armed) — the frontend's fallback-to-template behaviour (next decision) already handles
`null`/absent gracefully.

**Frontend caches the real text per row locally, keyed by which row was active at the moment a
given `LastTxMessage` arrived — not by asking the backend for history.** `renderMessageRows`
already runs `hasEnteredNewActiveTxState(prevState, state, activeStates)` to decide whether to log
a new transcript entry (design already established by `qso-transcript-panel`). On that same
transition, if `LastTxMessage` is present, store it in a small per-session object (e.g.
`realRowText[activeIndex] = lastTxMessage`) alongside the existing `currentTxPartner`/
`currentTxRole` module state. Row rendering becomes `realRowText[i] ?? texts[i]` — real value if
we've ever seen one for that row this QSO, template otherwise. The Transcript's `sent` entry uses
the same real value at the same capture point, replacing the current unconditional
`texts[activeIndex]`.

*Alternative considered*: have the backend send the message text as an explicit part of the
`decode`/`txState` push at exactly the transition moment only (event-sourced, not polled state).
Rejected as unnecessary complexity — `WsTxStateMessage` already fires exactly once per state
transition (that is what `hasEnteredNewActiveTxState` already detects), so a plain "current value"
field on the existing push is equivalent in practice to a dedicated transition event, without a new
message type.

**Reset `realRowText` to empty whenever the tracked partner changes or the role switches to
`Idle`**, mirroring how `currentTxPartner` itself is already reset at those points. Prevents a
previous QSO's real text leaking into a fresh QSO's row 1/2/3 display before that fresh QSO has
transmitted anything of its own.

**Do not touch `qso-transcript-panel`'s received-entry path.** `shouldCaptureDecode` and its
callers are unaffected — this change is entirely about what text a `sent`-kind entry carries, never
about `received`/`abort`/`partner-change` entries, which already show real decode/event content.

## Risks / Trade-offs

- **[Risk]** A row's real text, once cached client-side, persists in `realRowText` even if the
  operator navigates away and back within the same QSO (e.g. a page refresh) — the backend's single
  `LastTxMessage` field only reflects the *most recent* transmission, so a refreshed page would only
  recover the real text for whichever row was most recently sent, not earlier rows in the same QSO.
  → **Mitigation**: accepted. A full page refresh already loses other client-only session state
  today (e.g. `qso-transcript-panel`'s own rolling log is not persisted server-side either); this is
  consistent with existing behaviour, not a new gap, and a refreshed page still shows the *current*
  row correctly, which is what matters most while a QSO is actually in progress.
- **[Risk]** `QsoCallerService` gaining a new `_lastTxMessage` field duplicates information already
  derivable from `_rstSent` plus the known message templates. → **Mitigation**: deliberate — storing
  the literal composed string (not reconstructing it from parts) is the same pattern
  `QsoAnswererService` already uses, guarantees byte-for-byte fidelity with what was actually
  transmitted, and avoids a second formatting code path that could drift from the first.
- **[Risk]** Additive-only field on two public-ish contracts (`TxStatusResponse` JSON,
  `WsTxStateMessage` JSON) — a strict/unknown-fields-reject client could choke on the new field.
  → **Mitigation**: no such client exists in this codebase (the only consumer is this project's own
  frontend, using standard permissive `JSON.parse`); consistent with every prior additive field on
  these same records (`Role`, `CallerPartnerSelect`, `Keying`, `AbortReason` were all added the same
  way, none breaking).

## Migration Plan

Not applicable — no data migration, no schema change, no persisted state. Both new fields are
purely additive; an older cached frontend bundle that doesn't read `lastTxMessage` simply keeps
showing the template for every row, exactly today's behaviour — not a regression, a graceful
no-op. Rollback is a plain revert.

## Open Questions

None outstanding. Scope was fully bounded by TX-D05's source dev-task
(`dev-tasks/2026-07-19-tx-d05-transcript-and-message-rows-show-stale-template.md`) and
`openspec/qa-backlog.md` N12; `D-CALLER-022` remains explicitly separate and out of scope.
