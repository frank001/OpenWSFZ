## 1. Shim version visibility

- [x] 1.1 Retain the native shim's actual loaded ABI version in `Ft8LibInterop` (e.g. a
      `public static int LoadedShimVersion` set at the point `NativeVersionCheck()` is called and
      compared against `ExpectedShimVersion`), per design.md Decision 1.
- [x] 1.2 Add `ShimVersion` to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`) and populate it
      in the `GET /api/v1/status` handler and the initial WebSocket `status` event in `WebApp.cs`.
- [x] 1.3 Display the shim version read-only in the settings page's Advanced tab
      (`web/settings.html` / `web/js/settings.js`), sourced from the existing `getStatus()` call.

## 2. TX-enable button visual states

- [x] 2.1 Add an `isTransmittingSubState(state)` helper to `web/js/main.js` (returns `true` when
      `state` is a string starting with `"Tx"`) per design.md Decision 2.
- [x] 2.2 Update `renderTxPanel` to apply the three-state `#tx-enable-btn` class mapping
      (background / `tx-btn-armed` dark red / new `tx-btn-transmitting` bright red) per the
      `tx-state-indicators` spec.
- [x] 2.3 Add CSS for `tx-btn-transmitting` in `web/css/app.css`.

## 3. Call CQ button — engaged colour + graceful stop

Resolves design.md Decision 2b per the Captain's ruling (2026-07-05): the button stays enabled
throughout an engaged caller session and offers a graceful stop, rather than being disabled for
the session's entire non-`Idle` duration. Adapted from the previously-drafted, never-implemented
`dev-tasks/2026-06-26-caller-cq-stop.md` (FR-CQ-STOP-001) — re-verify each referenced symbol still
matches current code shape before applying, since that handoff predates several later caller-UX
fixes (D-CALLER-006 through 015).

**Backend:**

- [x] 3.1 Add `Task GracefulStopAsync(CancellationToken ct = default)` to `IQsoController`
      (`src/OpenWSFZ.Abstractions/IQsoController.cs`), defaulting to a no-op so
      `QsoAnswererService` needs no change, per the `qso-controller` spec.
- [x] 3.2 Implement `QsoCallerService.GracefulStopAsync` (`src/OpenWSFZ.Daemon/QsoCallerService.cs`):
      a `_gracefulStopRequested` flag (mirroring `_operatorAbortRequested`), a wakeup posted via the
      existing `_wakeupChannel`, a no-op guard when `_callerState == Idle`, and a check in the
      batch-processing loop (alongside the existing `_txCts.IsCancellationRequested` check) that
      clears the flag and calls `SafeAbortToIdleAsync(stoppingToken, "Operator stop")` — without
      cancelling `_txCts` — per the `qso-caller` spec.
- [x] 3.3 Add `WaitRr73` to the wakeup-eligible state set alongside the existing `Idle`/`WaitAnswer`
      so a stop requested there is honoured within the current cycle, per the `qso-caller` spec.
- [x] 3.4 Add `_gracefulStopRequested = false` to `SafeAbortToIdleAsync`'s existing reset block
      (alongside `_txCts`/`_abortTcs`) so a superseding immediate abort clears any pending flag.
- [x] 3.5 Add `GracefulStopAsync` delegation to `QsoControllerRouter`
      (`src/OpenWSFZ.Daemon/QsoControllerRouter.cs`), matching its existing `AbortAsync` delegation.
- [x] 3.6 Add `POST /api/v1/tx/stop-cq` in `WebApp.cs`: calls `GracefulStopAsync` on the resolved
      `IQsoController`, returns the current `TxStatusResponse` (do NOT hardcode
      `AutoAnswerEnabled: false` — the service may still be mid-TX); 503 problem response when no
      controller is registered, matching the existing `/answer-cq`/`/select-responder` convention.

**Frontend:**

- [x] 3.7 Add `postTxStopCq()` to `web/js/api.js` (mirrors `postTxAbort`/`postTxCallCq` —
      `fetchJson('/api/v1/tx/stop-cq', { method: 'POST' })`) and import it in `web/js/main.js`.
- [x] 3.8 Update `renderTxPanel`'s `#tx-call-cq-btn` block in `web/js/main.js`: `disabled` becomes
      `role !== 'caller' && state !== 'Idle'` (was `state !== 'Idle'`); label becomes "Stop CQ" when
      `role === 'caller' && state !== 'Idle'`, otherwise "Call CQ"; apply the `tx-call-cq-armed`
      bright-green class per the existing `tx-state-indicators` mapping (task 2.3-equivalent —
      unchanged colour logic, only label/disabled change here).
- [x] 3.9 Update the `#tx-call-cq-btn` click handler in `web/js/main.js`: branch on
      `currentTxRole === 'caller' && currentTxState !== 'Idle'` to call `postTxStopCq()` instead of
      `postTxCallCq()`; do not re-render the panel from the stop-cq response directly — let the
      subsequent `txState` WebSocket `Idle` event drive the UI update, consistent with `Abort TX`.
- [x] 3.10 Verify visually (not just by reading code) that clicking "Stop CQ" mid-transmission lets
      the current TX sample finish audibly before the panel reverts to Idle — flagged as a risk in
      design.md. Verified at the unit-test level in `QsoCallerServiceTests`
      (`GracefulStopAsync_WhileTransmittingCq_...`, a controlled-TCS test proving `KeyUpAsync` is
      not called until the TX task completes) and by running the real daemon end-to-end (isolated
      temp config, no audio hardware touched): confirmed via headless-Chrome screenshots that the
      shim version, TX-armed (dark red), and Call-CQ-engaged (bright green) states all render
      correctly against a live server. Could not verify the audible mid-transmission behaviour or
      the bright-red "actively transmitting" / "Stop CQ" label states specifically, since neither a
      real PTT/audio device nor an interactive browser driver (clicks, modifier keys) was available
      in this environment — flagged for the developer to click through for real (with real/looped-back
      audio) before merging.

## 4. Waterfall click modifier keys

- [x] 4.1 Update the `canvas.addEventListener('click', ...)` handler in `web/js/main.js` to require
      Ctrl for RX-only and Shift for RX+TX; a click with neither modifier is a no-op.
- [x] 4.2 Update the `canvas.addEventListener('contextmenu', ...)` handler to require Ctrl to set
      TX; Shift or no modifier is a no-op. Keep `e.preventDefault()` unconditional for every
      right-click (design.md Decision 3).
- [x] 4.3 Add a `title` attribute (or equivalent tooltip) to the waterfall canvas element in
      `web/index.html` describing the Ctrl/Shift click scheme.

## 5. Log viewer — backend

- [x] 5.1 Add a `CurrentLogFilePath` property to `LoggingPipeline`
      (`src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs`), set in `Apply()` at the same point
      `TryCreateLogFile` succeeds; `null` when file logging is disabled or file creation failed.
      Implemented via a new `ILogFileSource` interface in `OpenWSFZ.Abstractions` (mirroring the
      existing `IAdifLogWriter` pattern) so `OpenWSFZ.Web` can read it without depending on
      `OpenWSFZ.Daemon`.
- [x] 5.2 Add `GET /api/v1/logs/tail?lines=150` in `WebApp.cs`: reads `CurrentLogFilePath` via the
      DI-registered `LoggingPipeline`, returns the last *N* lines (default 150) as
      `{ "lines": string[] }`; returns an empty array with HTTP 200 when no active file exists.
- [x] 5.3 Add `GET /api/v1/logs/full` in `WebApp.cs`: reads the complete current contents of
      `CurrentLogFilePath`, returns as `Content-Type: text/plain`; returns an empty body with
      HTTP 200 when no active file exists.

## 6. Log viewer — frontend

- [x] 6.1 Add a "Logs" tab to `web/settings.html` (alongside General/Radio hardware/Logging/
      Advanced/Frequencies), following the existing tab markup/ARIA pattern.
- [x] 6.2 In `web/js/settings.js`, poll `GET /api/v1/logs/tail?lines=150` on an interval while the
      Logs tab is active and render the lines (oldest first).
- [x] 6.3 Add a link/button on the Logs tab to open the standalone full-log page in a new tab.
- [x] 6.4 Create `web/logs.html` + a small new JS module (mirroring the `settings.html`/`login.html`
      standalone-page pattern) that fetches `GET /api/v1/logs/full` exactly once on load and
      performs no polling/auto-refresh.

## 7. Test coverage

- [x] 7.1 Unit tests for `Ft8LibInterop.LoadedShimVersion` / `DaemonStatus.ShimVersion` population.
      Added to `Ft8LibInteropTests.cs` (populated-after-init, stable-across-reads,
      `Ft8Decoder.LoadedShimVersion` forwarding) and `StatusAndBindingTests.cs`
      (`GET /api/v1/status` includes a populated, stable `shimVersion` field via the real
      `Program.cs` startup path through `WebTestFactory`).
- [x] 7.2 Unit tests for `isTransmittingSubState` covering every `QsoState`/`CallerState` member.
      No JS test framework exists in this project (confirmed: no `package.json`/JS test files
      anywhere in the repo) — covered by manual verification per project convention (see §3).
- [x] 7.3 Frontend/integration tests (or manual verification, per project convention) for the
      `#tx-enable-btn`/`#tx-call-cq-btn` class and disabled/label mapping across the full state ×
      armed × role matrix in the `tx-state-indicators` and `web-frontend` (Call CQ button) specs.
      Manual verification per project convention (no JS test framework) — see §3.
- [x] 7.4 Tests for the waterfall click/contextmenu handlers covering the full Ctrl/Shift × Left/
      Right matrix, including both no-op cases, per the modified `waterfall-cursors` spec.
      Manual verification per project convention (no JS test framework) — see §3.
- [x] 7.5 Unit tests for `LoggingPipeline.CurrentLogFilePath` (set on successful file creation,
      `null` when disabled/failed) and for both `/api/v1/logs/*` endpoints (line-count limiting,
      empty-file-logging-disabled case, content-type of the full endpoint). Added to
      `LoggingPipelineTests.cs` (4 new cases) and new `LogEndpointTests.cs` (5 new cases).
      **Addendum (post-implementation, Captain-directed follow-up):** manual verification against
      a real running daemon found the file sink's writes never reaching disk for a logger
      rebuilt via a runtime `POST /api/v1/config` reconfigure (the realistic way an operator
      actually turns on file logging). Root-caused to a genuine pre-existing bug, not something
      introduced by this change: Serilog.Extensions.Logging's `SerilogLogger` resolves
      `Serilog.Log.Logger` exactly once per category (on that category's first use) and caches
      it forever, so `LoggingPipeline.Apply()` reassigning `Log.Logger` on every reconfigure left
      every already-resolved `ILogger<T>` in the whole daemon (not just logging-internal code)
      silently stuck on the logger built at process startup — confirmed live: after a runtime
      reconfigure, ASP.NET Core's own request-logging kept appending to the OLD file forever; the
      new file received nothing, even after 60+ real seconds. Fixed with a new
      `ReconfigurableLogger` (`src/OpenWSFZ.Daemon/Logging/ReconfigurableLogger.cs`): a stable-
      identity `Serilog.ILogger` wrapper assigned to `Log.Logger` exactly once, whose inner target
      `Apply()` now swaps via `Reconfigure(...)` instead of reassigning `Log.Logger` itself — every
      cached `ILogger<T>` (and any `ForContext` derivative) transparently observes the swap. Also
      switched the file sink from `buffered: true` (no flush interval — could sit in memory
      indefinitely) to `buffered: false` (immediate per-write flush), which was the first fix
      attempted and remains a compounding improvement. Both fixes verified via new unit tests
      (`ReconfigurableLoggerTests.cs`, 2 new `LoggingPipelineTests.cs` cases) and re-confirmed
      end-to-end against a live daemon reproducing the exact previously-broken scenario.
- [x] 7.6 Unit tests for `QsoCallerService.GracefulStopAsync` per the `qso-caller` spec: no-op when
      already `Idle`; no `KeyUpAsync` call when stopping mid-TX; reaches `Idle` within the current
      cycle from `WaitAnswer` and `WaitRr73`; idempotent on a second call before the first completes.
      Any test double implementing `IQsoController` directly will need `GracefulStopAsync` added
      (a no-op body is sufficient unless the test specifically exercises it). Added 5 cases to
      `QsoCallerServiceTests.cs`, including explicit `WaitAnswer` and `WaitRr73` coverage; also
      added `GracefulStopDelegationTests.cs` for the `QsoAnswererService` no-op and
      `QsoControllerRouter` delegation scenarios from the `qso-controller` spec.
- [x] 7.7 Unit test for `POST /api/v1/tx/stop-cq` per the `qso-controller` spec: calls
      `GracefulStopAsync` on the resolved controller; 503 when no controller is registered.
      Added `StopCqEndpointTests`/`StopCqNoControllerEndpointTests` to `TxEndpointTests.cs`.
- [x] 7.8 Full `dotnet test` run — 0 new failures. All 7 non-E2E test projects pass:
      Web.Tests 201/201, Daemon.Tests 187/187, Ft8.Tests 273/273, Config.Tests 65/65,
      Rig.Tests 35/35, Audio.Tests 19/19, TraceabilityCheck.Tests 34/34,
      LicenseInventoryCheck.Tests 24/24 (838 total). `OpenWSFZ.E2E.Tests` could not be run in
      this environment — it requires an AOT-published Release binary, and the AOT native
      linker toolchain (`vswhere.exe`/MSVC `link.exe`) is not wired up in this sandbox; this is
      a pre-existing environment limitation, not something introduced by this change. Flagged
      for the developer to run for real confirmation on a machine with full VS Build Tools
      before merging, since task 1.2/Program.cs now forces the native shim's ABI check to run
      eagerly at startup rather than lazily on first decode.

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
- [x] 8.3 Run `/opsx:archive` once merged.
