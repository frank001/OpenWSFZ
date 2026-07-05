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
   Separately, `#tx-call-cq-btn` is disabled for the entire non-`Idle` duration of a caller session
   today (`disabled = (state !== 'Idle')`, informally documented only as a code comment — "task
   11.8" — never a formal spec requirement), with no way to stop a session short of the
   immediate-kill `Abort TX` button; see Decision 2b.
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
- Any change to the underlying `QsoState`/`CallerState` state machine *definitions* (no new states,
  no renamed states) — Decision 2b adds a new transition trigger (`GracefulStopAsync`) to the
  existing `CallerState` machine, but does not change the enum or its states.
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

(See Decision 2b for the button's *disabled*/label/click behaviour, which changes independently of
this colour mapping — under the resolved Decision 2b, this button is never both disabled and green
at the same time, since the engaged condition above is always enabled.)

**Alternative considered — a new server-side `isTransmittingNow` boolean:** rejected as redundant.
The existing enum naming convention already encodes exactly this distinction; a parallel boolean
would be duplicate, driftable state (two sources of truth for the same fact).

### Decision 2b — RESOLVED: clicking `#tx-call-cq-btn` while engaged requests a graceful stop

Captain's ruling (2026-07-05): "the operator is in control. When the Call CQ is active and the
operator clicks it, the Call CQ should become inactive." This is a functional change, not merely a
styling one, and it supersedes the Open Question originally logged here. It is materially the same
requirement as a previously-drafted-but-never-implemented handoff,
`dev-tasks/2026-06-26-caller-cq-stop.md` (FR-CQ-STOP-001), committed for record-keeping on
2026-06-30 but never actioned. This design adopts that handoff's *behavioural and technical* shape
as prior art — re-verified against the current `QsoCallerService`/`IQsoController`/`WebApp.cs`
(the field, method, and endpoint names it references are still present and unchanged in kind).

**Behaviour** (replaces the `disabled = (state !== 'Idle')` gating in place today):

| Condition | `#tx-call-cq-btn` state | Click action |
|---|---|---|
| `role !== 'caller'` and `state === 'Idle'` | Enabled, label "Call CQ" | `POST /api/v1/tx/call-cq` (existing — starts a caller session) |
| `role === 'caller'` and `state !== 'Idle'` | Enabled, label "Stop CQ" | `POST /api/v1/tx/stop-cq` (new — graceful stop) |
| `role !== 'caller'` and `state !== 'Idle'` (answerer mid-QSO) | Disabled | — (cannot start a CQ session while the answerer role is already busy) |

A graceful stop is deliberately **not** the same as `Abort TX`: any in-progress TX sample plays to
completion — `IPttController.KeyUpAsync` is NOT invoked — and the service returns to `Idle` only
once it reaches its next natural wait point. That is why it needs its own `IQsoController` method
and endpoint rather than reusing `AbortAsync`, which cancels `_txCts` and kills audio mid-sample.
`Abort TX` remains available, unchanged, as the immediate-kill path.

**Implementation shape** (adapted from the FR-CQ-STOP-001 handoff):
- `IQsoController` gains `Task GracefulStopAsync(CancellationToken ct = default)`, defaulting to a
  no-op so `QsoAnswererService` needs no change — graceful stop is a caller-only concept.
- `QsoCallerService.GracefulStopAsync` sets a `_gracefulStopRequested` flag (mirroring the existing
  `_operatorAbortRequested` pattern) and posts a wakeup through the existing `_wakeupChannel` so a
  waiting state machine doesn't have to sit out the rest of the current 15 s decode cycle. `WaitRr73`
  needs adding to the wakeup-eligible state set alongside the existing `Idle`/`WaitAnswer` — it is
  not currently wakeup-eligible, and a stop requested while holding there would otherwise stall for
  up to one cycle.
- The batch-processing loop checks `_gracefulStopRequested` at the same point it already checks
  `_txCts.IsCancellationRequested`; if set, it clears the flag and calls the existing
  `SafeAbortToIdleAsync` (reason: `"Operator stop"`) — *without* `_txCts` having been cancelled, so
  any TX already in flight is unaffected. Requesting a stop twice in quick succession is idempotent
  (the second call finds `_callerState == Idle` and no-ops, per the existing guard at the top of
  `GracefulStopAsync`).
- `QsoControllerRouter.GracefulStopAsync` delegates to `ActiveController`, matching its existing
  `AbortAsync` delegation.
- New `POST /api/v1/tx/stop-cq`: calls `GracefulStopAsync` and returns the current (possibly still
  mid-TX) `TxStatusResponse`. The frontend does not act on this response directly — it waits for the
  `txState` WebSocket event carrying `state: "Idle"` to reflect the completed stop, exactly as it
  already does for `Abort TX`.
- Frontend: the click handler branches on `currentTxRole === 'caller' && currentTxState !== 'Idle'`
  to call a new `postTxStopCq()` instead of `postTxCallCq()`. `renderTxPanel`'s disabled logic
  changes from `state !== 'Idle'` to `role !== 'caller' && state !== 'Idle'`. The label toggles
  "Call CQ" / "Stop CQ" on that same condition.

**Not adopted from the FR-CQ-STOP-001 handoff:** its proposed two-tone colour scheme (bright green
only while transmitting the CQ itself; dark green while a resulting QSO is in progress). That
predates, and would conflict with, this change's own Decision 2 (a single steady bright green for
the whole engaged period), decided independently and earlier in this proposal. Decision 2's colour
model stands unchanged; only the click/disabled/label behaviour above is adopted from the older
handoff. If the Captain would prefer the two-tone colour scheme after all, that is a one-line
change to Decision 2 — not made here because it was not asked for.

**Alternative considered — keep the button disabled throughout the engaged period (the original,
now-superseded reading of this decision):** rejected per the Captain's ruling above.

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
- **[Risk] Decision 2b's graceful stop touches live state-machine timing** (`WaitRr73` becoming
  wakeup-eligible; a stop requested mid-TX must not fire until the current sample finishes).
  → Mitigation: reuses the existing `_wakeupChannel`/`SafeAbortToIdleAsync` machinery rather than
  inventing a new mechanism; covered by the acceptance criteria in
  `dev-tasks/2026-06-26-caller-cq-stop.md` §4, which this design carries forward as the test basis
  (task 6.7).
- **[Risk] `role !== 'caller' && state !== 'Idle'` (answerer mid-QSO) must still disable the
  button** — a regression here would let an operator attempt to start a caller session while the
  answerer role is mid-exchange. → Mitigation: explicit scenario coverage in the `web-frontend`
  delta's new Call-CQ requirement (task 6.3).
- **[Risk] Breaking the waterfall's existing plain-click muscle memory could surprise an operator
  mid-session the first time this ships.** → Mitigation: this is the explicit purpose of the
  change (the whole point is that accidental clicks should no longer retune anything); the new
  tooltip documents the scheme for anyone who forgets.

## Migration Plan

No data migration — all four items are additive (new field, new CSS classes, new endpoints/pages)
or a pure interaction-model change (waterfall clicks) with no persisted state. Rollback is a plain
revert; no config schema changes are involved anywhere in this change.

## Open Questions

None outstanding. The sole open question (Decision 2b) was resolved by the Captain's ruling of
2026-07-05 — see Decision 2b above.
