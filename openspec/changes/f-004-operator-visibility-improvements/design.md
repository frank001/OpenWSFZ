## Context

Four independent, small-surface-area GUI/status gaps, each already grounded in existing code
during the discovery conversation that produced this change:

1. **Shim version.** `Ft8LibInterop`'s static resolver calls `NativeVersionCheck()` once at process
   start and compares the result to `ExpectedShimVersion` (currently `20260031`), throwing
   `InvalidOperationException` on mismatch — but the actual value is never retained after the
   comparison. `DaemonStatus` (`GET /api/v1/status`, `src/OpenWSFZ.Web/DaemonStatus.cs`) has no
   field for it.
2. **TX/Call-CQ visual state.** `renderTxPanel` in `web/js/main.js` toggles a single
   `tx-btn-armed` CSS class on `#tx-enable-btn` from `autoAnswerEnabled` alone (D-TX-UI-002: "red
   background alone signals the armed state"). The `txState` WebSocket payload already carries
   `state` (the `QsoState` enum for the Answerer role — `Idle`, `TxAnswer`, `WaitReport`,
   `TxReport`, `WaitRr73`, `Tx73`, `QsoComplete` — and the `CallerState` enum for the Caller role —
   `Idle`, `TxCq`, `WaitAnswer`, `TxReport`, `WaitRr73`, `TxRr73`, `QsoComplete`), `autoAnswerEnabled`,
   and `role`. Both state enums already name every transmitting sub-state with a `Tx` prefix and no
   non-transmitting state with that prefix — this is the load-bearing fact this design relies on.
3. **Waterfall click safety.** `web/js/main.js`'s `canvas.addEventListener('click', ...)` and
   `'contextmenu'` handlers implement today's `{plain-left→RX, shift-left→RX+TX, plain-right→TX}`
   scheme with zero confirmation and no tooltip — governed by the `waterfall-cursors` spec.
4. **Log viewer.** `LoggingPipeline.TryCreateLogFile` (`src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs`)
   computes the active log file's path inside `Apply()` but discards it once the Serilog logger is
   built — there is no stored, queryable "current log file path" anywhere today.

## Goals / Non-Goals

**Goals:**
- Implement all four items using existing data paths and page/component patterns — no new
  architectural layer, no new persisted configuration.
- Keep each item's blast radius small and independently reviewable (they touch disjoint files
  except for shared conventions in `web/settings.html`/`settings.js`).

**Non-Goals:**
- A remote-restart capability (raised in the same discovery conversation, explicitly deferred by
  the Captain to a separate, later change).
- Any change to the underlying `QsoState`/`CallerState` state machines themselves — this change
  only alters how existing states are *displayed*.
- Any change to log rotation, retention, or the on-disk log format — the log viewer only reads
  what `LoggingPipeline` already produces.

## Decisions

### Decision 1 — Retain the already-computed shim version; do not re-query the native library

`Ft8LibInterop`'s ABI self-test already calls `NativeVersionCheck()` once at startup, and a
mismatch throws before the web host ever starts listening — so by the time `GET /api/v1/status`
can serve a single request, `actual == ExpectedShimVersion` is already guaranteed. Store the
`actual` value read during that startup check (e.g. a `public static int LoadedShimVersion`
property on `Ft8LibInterop`, or an internal static field the status endpoint reads through the
existing DI-registered interop instance) and surface it as `DaemonStatus.ShimVersion`.

**Alternative considered — re-invoke `NativeVersionCheck()` on every status request:** rejected.
The value is invariant for the process lifetime once the startup check has passed; a repeated
P/Invoke call on every poll of the status endpoint (the frontend polls/streams this) buys nothing.

### Decision 2 — TX/Call-CQ colour states are a pure client-side mapping over existing fields

No server-side change is needed. `web/js/main.js` gains a small helper:

```js
function isTransmittingSubState(state) {
  return typeof state === 'string' && state.startsWith('Tx');
}
```

This works uniformly across both `QsoState` (`TxAnswer`/`TxReport`/`Tx73`) and `CallerState`
(`TxCq`/`TxReport`/`TxRr73`) because every transmitting sub-state in both enums is named with a
`Tx` prefix and no waiting/idle state is. `renderTxPanel` applies:

| `#tx-enable-btn` condition | CSS class |
|---|---|
| `!autoAnswerEnabled` | none (background colour) |
| `autoAnswerEnabled && !isTransmittingSubState(state)` | `tx-btn-armed` (dark red — kept as today's class name/colour) |
| `autoAnswerEnabled && isTransmittingSubState(state)` | `tx-btn-transmitting` (new, bright red) |

| `#tx-call-cq-btn` condition | CSS class |
|---|---|
| `role === 'caller' && autoAnswerEnabled` | `tx-call-cq-armed` (new, bright green) — independent of `state` |
| otherwise | none (background colour) |

**Alternative considered — a new server-side `isTransmittingNow` boolean:** rejected as redundant.
The existing enum naming convention already encodes exactly this distinction; a parallel boolean
would be duplicate, driftable state (two sources of truth for the same fact).

### Decision 2b — decouple `#tx-call-cq-btn`'s colour from its `disabled` attribute

Today, `renderTxPanel` sets `txCallCqBtnEl.disabled = (state !== 'Idle')` (task 11.8) — this is
*functional* gating, preventing a duplicate/conflicting POST while a CQ cycle is already in
flight, and this design does not change that gating. The requirement ("bright green … independent
of actual audio being sent") is about **colour**, not clickability. The two currently interact only
by accident, if the page's base button styles dim `:disabled` elements — this design adds an
explicit `.tx-btn.tx-call-cq-armed:disabled` CSS rule so the green class's colour is not overridden
by disabled-state dimming, while the `disabled` attribute itself keeps gating clicks exactly as it
does today. See Open Questions — confirm this reading (colour changes, clickability doesn't) before
implementation, since the discovery conversation didn't explicitly separate the two.

### Decision 3 — Waterfall context-menu suppression stays unconditional

The four required interactions are Ctrl+left (RX), Ctrl+right (TX), Shift+left (RX+TX), and
Shift+right (no-op); an unmodified click of either button is also a no-op. The browser's native
right-click context menu is suppressed on the canvas regardless of which case applies — showing it
only for the "no-op" right-click cases (plain right-click, Shift+right-click) while suppressing it
for Ctrl+right-click would be an inconsistent user experience (menu sometimes appears, sometimes
doesn't, depending on a modifier key the operator may not even be thinking about) for no
countervailing benefit, since the waterfall canvas has no useful native context-menu items anyway.

**Alternative considered — restore the native context menu whenever the click is a no-op:**
rejected per the above; flagged during the original discovery conversation and not corrected when
the exact click matrix was specified, so treated as confirmed.

### Decision 4 — Two endpoints, two consumption patterns, one shared "current log path" source

`LoggingPipeline` gains a `CurrentLogFilePath` property (nullable — `null` when file logging is
disabled or the file could not be created), set at the same point `Apply()` already computes the
path via `TryCreateLogFile`. Two new `WebApp.cs` endpoints read it:

- `GET /api/v1/logs/tail?lines=150` — reads the current log file, returns the last *N* lines
  (default 150, capped at some reasonable maximum e.g. 1000) as JSON (`{ "lines": string[] }`).
  Polled by the new settings-page "Logs" tab on an interval. Returns an empty array (not an error)
  when file logging is disabled or no file exists yet.
- `GET /api/v1/logs/full` — reads the entire current log file, returns it as `Content-Type:
  text/plain`. Fetched exactly once by the new standalone `web/logs.html` page on load; that page
  performs no polling — the operator reloads the browser tab to see new content, per the Captain's
  explicit choice.

Both endpoints read whatever file `CurrentLogFilePath` names *at request time* — if rotation
happens between the tail panel's polls, the panel naturally starts tailing the new file (a
one-cycle "log just rotated" blip is acceptable and self-correcting); the full-log page is a single
snapshot by design and does not need to handle a rotation mid-fetch specially.

**Alternative considered — a single endpoint with an optional `lines` param, `logs.html` calling it
with a very large limit:** rejected. Serving potentially MB+ of Trace-level log as a JSON string
array is wasteful compared to a plain-text response, and the two pages have genuinely different
consumption shapes (structured array for incremental polling/rendering vs. a flat blob for a
"view the whole thing" page) — using the same endpoint for both would force one of them to do
unnecessary work.

## Risks / Trade-offs

- **[Risk] `GET /api/v1/logs/full` on a large Trace-level log file could be slow or memory-heavy.**
  → Mitigation: this is an explicit, operator-initiated action (clicking through to a dedicated
  page), not a background poll; acceptable to be a plain synchronous file read for a first cut.
  Revisit with streaming if it proves to be an actual problem in practice.
- **[Risk] Decision 2b's disabled/colour decoupling is a CSS-specificity detail that's easy to get
  subtly wrong (e.g. a browser default `button:disabled` rule winning over a class selector).**
  → Mitigation: called out explicitly as its own decision and open question; verify visually
  during implementation, not just by reading the CSS.
- **[Risk] Breaking the waterfall's existing plain-click muscle memory could surprise an operator
  mid-session the first time this ships.** → Mitigation: this is the explicit purpose of the
  change (the whole point is that accidental clicks should no longer retune anything); the new
  tooltip documents the scheme for anyone who forgets.

## Migration Plan

No data migration — all four items are additive (new field, new CSS classes, new endpoints/pages)
or a pure interaction-model change (waterfall clicks) with no persisted state. Rollback is a plain
revert; no config schema changes are involved anywhere in this change.

## Open Questions

- **Decision 2b**: confirm the reading that `#tx-call-cq-btn`'s `disabled` attribute (clickability)
  is unchanged and only its *colour while disabled* changes. If the Captain instead wants the
  button to become genuinely clickable (re-armable) at any point while Call-CQ mode is engaged,
  that is a materially different, larger change to the Caller click-handling logic, not just styling.
