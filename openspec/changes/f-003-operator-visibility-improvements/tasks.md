## 1. Shim version visibility

- [ ] 1.1 Retain the native shim's actual loaded ABI version in `Ft8LibInterop` (e.g. a
      `public static int LoadedShimVersion` set at the point `NativeVersionCheck()` is called and
      compared against `ExpectedShimVersion`), per design.md Decision 1.
- [ ] 1.2 Add `ShimVersion` to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`) and populate it
      in the `GET /api/v1/status` handler and the initial WebSocket `status` event in `WebApp.cs`.
- [ ] 1.3 Display the shim version read-only in the settings page's Advanced tab
      (`web/settings.html` / `web/js/settings.js`), sourced from the existing `getStatus()` call.

## 2. TX / Call-CQ visual states

- [ ] 2.1 Add an `isTransmittingSubState(state)` helper to `web/js/main.js` (returns `true` when
      `state` is a string starting with `"Tx"`) per design.md Decision 2.
- [ ] 2.2 Update `renderTxPanel` to apply the three-state `#tx-enable-btn` class mapping
      (background / `tx-btn-armed` dark red / new `tx-btn-transmitting` bright red) per the
      `tx-state-indicators` spec.
- [ ] 2.3 Update `renderTxPanel` to apply the `#tx-call-cq-btn` bright-green (`tx-call-cq-armed`)
      class whenever `role === 'caller' && autoAnswerEnabled`, independent of `state`.
- [ ] 2.4 Add CSS for `tx-btn-transmitting` and `tx-call-cq-armed` in `web/css/app.css`, including
      an explicit `.tx-btn.tx-call-cq-armed:disabled` rule so the disabled attribute does not dim
      the green colour (design.md Decision 2b) — confirm the Open Question (disabled semantics
      unchanged, only colour) before or during this task.
- [ ] 2.5 Verify visually (not just by reading CSS) that the disabled/armed-green interaction
      renders as intended in a real browser — flagged as a risk in design.md.

## 3. Waterfall click modifier keys

- [ ] 3.1 Update the `canvas.addEventListener('click', ...)` handler in `web/js/main.js` to require
      Ctrl for RX-only and Shift for RX+TX; a click with neither modifier is a no-op.
- [ ] 3.2 Update the `canvas.addEventListener('contextmenu', ...)` handler to require Ctrl to set
      TX; Shift or no modifier is a no-op. Keep `e.preventDefault()` unconditional for every
      right-click (design.md Decision 3).
- [ ] 3.3 Add a `title` attribute (or equivalent tooltip) to the waterfall canvas element in
      `web/index.html` describing the Ctrl/Shift click scheme.

## 4. Log viewer — backend

- [ ] 4.1 Add a `CurrentLogFilePath` property to `LoggingPipeline`
      (`src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs`), set in `Apply()` at the same point
      `TryCreateLogFile` succeeds; `null` when file logging is disabled or file creation failed.
- [ ] 4.2 Add `GET /api/v1/logs/tail?lines=150` in `WebApp.cs`: reads `CurrentLogFilePath` via the
      DI-registered `LoggingPipeline`, returns the last *N* lines (default 150) as
      `{ "lines": string[] }`; returns an empty array with HTTP 200 when no active file exists.
- [ ] 4.3 Add `GET /api/v1/logs/full` in `WebApp.cs`: reads the complete current contents of
      `CurrentLogFilePath`, returns as `Content-Type: text/plain`; returns an empty body with
      HTTP 200 when no active file exists.

## 5. Log viewer — frontend

- [ ] 5.1 Add a "Logs" tab to `web/settings.html` (alongside General/Radio hardware/Logging/
      Advanced/Frequencies), following the existing tab markup/ARIA pattern.
- [ ] 5.2 In `web/js/settings.js`, poll `GET /api/v1/logs/tail?lines=150` on an interval while the
      Logs tab is active and render the lines (oldest first).
- [ ] 5.3 Add a link/button on the Logs tab to open the standalone full-log page in a new tab.
- [ ] 5.4 Create `web/logs.html` + a small new JS module (mirroring the `settings.html`/`login.html`
      standalone-page pattern) that fetches `GET /api/v1/logs/full` exactly once on load and
      performs no polling/auto-refresh.

## 6. Test coverage

- [ ] 6.1 Unit tests for `Ft8LibInterop.LoadedShimVersion` / `DaemonStatus.ShimVersion` population.
- [ ] 6.2 Unit tests for `isTransmittingSubState` covering every `QsoState`/`CallerState` member.
- [ ] 6.3 Frontend/integration tests (or manual verification, per project convention) for the
      `#tx-enable-btn`/`#tx-call-cq-btn` class mapping across the full state × armed × role matrix
      in the `tx-state-indicators` spec.
- [ ] 6.4 Tests for the waterfall click/contextmenu handlers covering the full Ctrl/Shift × Left/
      Right matrix, including both no-op cases, per the modified `waterfall-cursors` spec.
- [ ] 6.5 Unit tests for `LoggingPipeline.CurrentLogFilePath` (set on successful file creation,
      `null` when disabled/failed) and for both `/api/v1/logs/*` endpoints (line-count limiting,
      empty-file-logging-disabled case, content-type of the full endpoint).
- [ ] 6.6 Full `dotnet test` run — 0 new failures.

## 7. Documentation and handoff

- [ ] 7.1 Confirm the Decision 2b Open Question with the Captain before or during task 2.4/2.5.
- [ ] 7.2 Run `/opsx:archive` once merged.
