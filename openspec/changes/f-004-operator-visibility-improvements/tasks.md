## 1. Shim version visibility

- [x] 1.1 Retain the native shim's actual loaded ABI version in `Ft8LibInterop` (e.g. a
      `public static int LoadedShimVersion` set at the point `NativeVersionCheck()` is called and
      compared against `ExpectedShimVersion`), per design.md Decision 1.
- [ ] 1.2 Add `ShimVersion` to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`) and populate it
      in the `GET /api/v1/status` handler and the initial WebSocket `status` event in `WebApp.cs`.
- [ ] 1.3 Display the shim version read-only in the settings page's Advanced tab
      (`web/settings.html` / `web/js/settings.js`), sourced from the existing `getStatus()` call.

## 2. TX-enable button visual states

- [ ] 2.1 Add an `isTransmittingSubState(state)` helper to `web/js/main.js` (returns `true` when
      `state` is a string starting with `"Tx"`) per design.md Decision 2.
- [ ] 2.2 Update `renderTxPanel` to apply the three-state `#tx-enable-btn` class mapping
      (background / `tx-btn-armed` dark red / new `tx-btn-transmitting` bright red) per the
      `tx-state-indicators` spec.
- [ ] 2.3 Add CSS for `tx-btn-transmitting` in `web/css/app.css`.

## 3. Call CQ button — engaged colour + graceful stop

Resolves design.md Decision 2b per the Captain's ruling (2026-07-05): the button stays enabled
throughout an engaged caller session and offers a graceful stop, rather than being disabled for
the session's entire non-`Idle` duration. Adapted from the previously-drafted, never-implemented
`dev-tasks/2026-06-26-caller-cq-stop.md` (FR-CQ-STOP-001) — re-verify each referenced symbol still
matches current code shape before applying, since that handoff predates several later caller-UX
fixes (D-CALLER-006 through 015).

**Backend:**

- [ ] 3.1 Add `Task GracefulStopAsync(CancellationToken ct = default)` to `IQsoController`
      (`src/OpenWSFZ.Abstractions/IQsoController.cs`), defaulting to a no-op so
      `QsoAnswererService` needs no change, per the `qso-controller` spec.
- [ ] 3.2 Implement `QsoCallerService.GracefulStopAsync` (`src/OpenWSFZ.Daemon/QsoCallerService.cs`):
      a `_gracefulStopRequested` flag (mirroring `_operatorAbortRequested`), a wakeup posted via the
      existing `_wakeupChannel`, a no-op guard when `_callerState == Idle`, and a check in the
      batch-processing loop (alongside the existing `_txCts.IsCancellationRequested` check) that
      clears the flag and calls `SafeAbortToIdleAsync(stoppingToken, "Operator stop")` — without
      cancelling `_txCts` — per the `qso-caller` spec.
- [ ] 3.3 Add `WaitRr73` to the wakeup-eligible state set alongside the existing `Idle`/`WaitAnswer`
      so a stop requested there is honoured within the current cycle, per the `qso-caller` spec.
- [ ] 3.4 Add `_gracefulStopRequested = false` to `SafeAbortToIdleAsync`'s existing reset block
      (alongside `_txCts`/`_abortTcs`) so a superseding immediate abort clears any pending flag.
- [ ] 3.5 Add `GracefulStopAsync` delegation to `QsoControllerRouter`
      (`src/OpenWSFZ.Daemon/QsoControllerRouter.cs`), matching its existing `AbortAsync` delegation.
- [ ] 3.6 Add `POST /api/v1/tx/stop-cq` in `WebApp.cs`: calls `GracefulStopAsync` on the resolved
      `IQsoController`, returns the current `TxStatusResponse` (do NOT hardcode
      `AutoAnswerEnabled: false` — the service may still be mid-TX); 503 problem response when no
      controller is registered, matching the existing `/answer-cq`/`/select-responder` convention.

**Frontend:**

- [ ] 3.7 Add `postTxStopCq()` to `web/js/api.js` (mirrors `postTxAbort`/`postTxCallCq` —
      `fetchJson('/api/v1/tx/stop-cq', { method: 'POST' })`) and import it in `web/js/main.js`.
- [ ] 3.8 Update `renderTxPanel`'s `#tx-call-cq-btn` block in `web/js/main.js`: `disabled` becomes
      `role !== 'caller' && state !== 'Idle'` (was `state !== 'Idle'`); label becomes "Stop CQ" when
      `role === 'caller' && state !== 'Idle'`, otherwise "Call CQ"; apply the `tx-call-cq-armed`
      bright-green class per the existing `tx-state-indicators` mapping (task 2.3-equivalent —
      unchanged colour logic, only label/disabled change here).
- [ ] 3.9 Update the `#tx-call-cq-btn` click handler in `web/js/main.js`: branch on
      `currentTxRole === 'caller' && currentTxState !== 'Idle'` to call `postTxStopCq()` instead of
      `postTxCallCq()`; do not re-render the panel from the stop-cq response directly — let the
      subsequent `txState` WebSocket `Idle` event drive the UI update, consistent with `Abort TX`.
- [ ] 3.10 Verify visually (not just by reading code) that clicking "Stop CQ" mid-transmission lets
      the current TX sample finish audibly before the panel reverts to Idle — flagged as a risk in
      design.md.

## 4. Waterfall click modifier keys

- [ ] 4.1 Update the `canvas.addEventListener('click', ...)` handler in `web/js/main.js` to require
      Ctrl for RX-only and Shift for RX+TX; a click with neither modifier is a no-op.
- [ ] 4.2 Update the `canvas.addEventListener('contextmenu', ...)` handler to require Ctrl to set
      TX; Shift or no modifier is a no-op. Keep `e.preventDefault()` unconditional for every
      right-click (design.md Decision 3).
- [ ] 4.3 Add a `title` attribute (or equivalent tooltip) to the waterfall canvas element in
      `web/index.html` describing the Ctrl/Shift click scheme.

## 5. Log viewer — backend

- [ ] 5.1 Add a `CurrentLogFilePath` property to `LoggingPipeline`
      (`src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs`), set in `Apply()` at the same point
      `TryCreateLogFile` succeeds; `null` when file logging is disabled or file creation failed.
- [ ] 5.2 Add `GET /api/v1/logs/tail?lines=150` in `WebApp.cs`: reads `CurrentLogFilePath` via the
      DI-registered `LoggingPipeline`, returns the last *N* lines (default 150) as
      `{ "lines": string[] }`; returns an empty array with HTTP 200 when no active file exists.
- [ ] 5.3 Add `GET /api/v1/logs/full` in `WebApp.cs`: reads the complete current contents of
      `CurrentLogFilePath`, returns as `Content-Type: text/plain`; returns an empty body with
      HTTP 200 when no active file exists.

## 6. Log viewer — frontend

- [ ] 6.1 Add a "Logs" tab to `web/settings.html` (alongside General/Radio hardware/Logging/
      Advanced/Frequencies), following the existing tab markup/ARIA pattern.
- [ ] 6.2 In `web/js/settings.js`, poll `GET /api/v1/logs/tail?lines=150` on an interval while the
      Logs tab is active and render the lines (oldest first).
- [ ] 6.3 Add a link/button on the Logs tab to open the standalone full-log page in a new tab.
- [ ] 6.4 Create `web/logs.html` + a small new JS module (mirroring the `settings.html`/`login.html`
      standalone-page pattern) that fetches `GET /api/v1/logs/full` exactly once on load and
      performs no polling/auto-refresh.

## 7. Test coverage

- [ ] 7.1 Unit tests for `Ft8LibInterop.LoadedShimVersion` / `DaemonStatus.ShimVersion` population.
- [ ] 7.2 Unit tests for `isTransmittingSubState` covering every `QsoState`/`CallerState` member.
- [ ] 7.3 Frontend/integration tests (or manual verification, per project convention) for the
      `#tx-enable-btn`/`#tx-call-cq-btn` class and disabled/label mapping across the full state ×
      armed × role matrix in the `tx-state-indicators` and `web-frontend` (Call CQ button) specs.
- [ ] 7.4 Tests for the waterfall click/contextmenu handlers covering the full Ctrl/Shift × Left/
      Right matrix, including both no-op cases, per the modified `waterfall-cursors` spec.
- [ ] 7.5 Unit tests for `LoggingPipeline.CurrentLogFilePath` (set on successful file creation,
      `null` when disabled/failed) and for both `/api/v1/logs/*` endpoints (line-count limiting,
      empty-file-logging-disabled case, content-type of the full endpoint).
- [ ] 7.6 Unit tests for `QsoCallerService.GracefulStopAsync` per the `qso-caller` spec: no-op when
      already `Idle`; no `KeyUpAsync` call when stopping mid-TX; reaches `Idle` within the current
      cycle from `WaitAnswer` and `WaitRr73`; idempotent on a second call before the first completes.
      Any test double implementing `IQsoController` directly will need `GracefulStopAsync` added
      (a no-op body is sufficient unless the test specifically exercises it).
- [ ] 7.7 Unit test for `POST /api/v1/tx/stop-cq` per the `qso-controller` spec: calls
      `GracefulStopAsync` on the resolved controller; 503 when no controller is registered.
- [ ] 7.8 Full `dotnet test` run — 0 new failures.

## 8. Documentation and handoff

- [x] 8.1 QA pre-merge review (2026-07-05): renumbered `f-003-operator-visibility-improvements` →
      `f-004-operator-visibility-improvements` (the `f-003` slug was already claimed by the
      merged `f-003-ap-assist-nonstandard-callsigns`); rebased onto `main`; added a
      `web-frontend` MODIFIED delta narrowing the pre-existing "TX panel — Enable TX toggle
      button" requirement so it no longer conflicts with `tx-state-indicators`'s dark-red/
      bright-red split; corrected `tx-state-indicators`' dangling cross-reference to a
      non-existent `qso-caller` frontend requirement; fixed a `log-viewer` requirement whose
      `SHALL` fell outside the validator's first-line check. `openspec validate --strict` now
      passes.
- [x] 8.2 QA follow-up (2026-07-05): Captain ruled on the Decision 2b open question — clicking
      Call CQ while engaged SHALL deactivate it. Resolved as a graceful stop (not an immediate
      abort), reviving `dev-tasks/2026-06-26-caller-cq-stop.md` (FR-CQ-STOP-001). Added ADDED
      requirements to `qso-controller` (`GracefulStopAsync`, `POST /api/v1/tx/stop-cq`) and
      `qso-caller` (state-machine behaviour), a new `web-frontend` "TX panel — Call CQ button"
      requirement, corrected `tx-state-indicators`' now-unreachable disabled+green scenario, and
      tasks 3.1–3.10 / 7.6–7.7 above. The FR-CQ-COLOUR-001 two-tone colour scheme from that same
      old handoff was deliberately NOT adopted — it conflicts with this proposal's own
      already-decided steady-green Decision 2; flagged to the Captain as available if wanted, not
      applied unasked.
- [ ] 8.3 Run `/opsx:archive` once merged.
