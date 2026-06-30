# Handoff: D-CALLER-009 — D-CALLER-006 abort-and-recq has a race; postTxCallCq fires before service reaches Idle

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action
**Defect ID:** D-CALLER-009
**Severity:** Medium — the intended UX (click a responder row during TxReport →
abort → new CQ fires automatically) does not work. The operator must restart
the CQ session manually. No crash, no stuck state.

---

## 1. Context

`D-CALLER-006` (`aea1081`) added an abort-and-recq path in the `decode-responder`
click handler. When the operator double-clicks a responder row while in `TxReport`
or `WaitRr73`, the handler fires:

```javascript
await postTxAbort();
await postTxCallCq();
```

The accompanying comment states:

> "`postTxAbort()` awaits `SafeAbortToIdleAsync` on the server before returning,
> so the service is already at Idle when the await resolves. `postTxCallCq` is
> safe to fire immediately after."

This is factually incorrect. `QsoCallerService.AbortAsync` sets flags and cancels
a `CancellationTokenSource`, then returns `Task.CompletedTask` immediately. The
HTTP abort handler does `await qsoController.AbortAsync(ct)` — which resolves in
microseconds — then returns 200 while the background service loop is still in the
middle of processing the cancellation. `SafeAbortToIdleAsync` (the state transition
to Idle) runs asynchronously on the background thread and completes several
milliseconds later.

### Evidence from `openswfz-20260626T201136Z.log`

```
22:15:49.484  POST /api/v1/tx/abort received
22:15:49.486  "abort requested (HTTP) — partner: PD3QA, state: TxReport"
22:15:49.487  TX KeyUp — stopping playback (abort signal)
22:15:49.495  HTTP 200  ← abort handler returns (SafeAbortToIdleAsync NOT complete)
22:15:49.499  POST /api/v1/tx/call-cq  ← JS fires immediately; 4 ms after abort 200
22:15:49.501  HTTP 409  ← service still in TxReport; CQ rejected
22:15:49.505  TX KeyDown — playback completed (audio buffer exhausted naturally)
22:15:49.506  "TX session cancelled during TX (state: TxReport)"
22:15:49.509  "aborted to Idle (was: TxReport, partner: PD3QA)"
22:15:49.509  "QsoControllerRouter: caller QSO ended — reverting role to Answerer"
```

The 4 ms gap between abort-200 and call-cq is not a human reaction time — it is the
D-CALLER-006 JS handler's `await postTxAbort()` resolving and immediately firing
`await postTxCallCq()`. The 409 is handled by the error handler; `selectInFlight`
and `pointerEvents` are kept deactivated, and `console.error` is emitted. No hang
or UI freeze — but the auto-rearm never fires and the operator must click Call CQ
manually.

---

## 2. Design

The authoritative signal that the service has reached Idle is the WS `txState`
event with `state: 'Idle'` and `role: 'answerer'`. The existing handler at
line 1141 already calls `renderTxPanel(...)` on this event.

**Fix pattern:** Replace the immediate `postTxCallCq()` call with a deferred
rearm. A module-level boolean `pendingRearmAfterAbort` is set by the D-CALLER-006
handler. The WS `txState` handler checks the flag when a confirming Idle event
arrives and fires `postTxCallCq()` at that point.

The flag must also be cleared by any other path that explicitly requests a stop:
- The **Abort TX** button handler (operator wants to stop, not restart)
- The **Stop CQ** button handler (same)

If neither of those clears the flag, the next WS Idle event from a manual abort
or graceful stop would inadvertently re-arm a new CQ session the operator did
not request.

---

## 3. Branch

`fix/caller-ux-fixes` — amend the existing branch. Pure front-end change.

---

## 4. Actions

All edits are in `web/js/main.js` only.

---

### 4.1 — Add module-level `pendingRearmAfterAbort` flag

Insert immediately after the `let currentCallerPartnerSelect` declaration
(currently around line 61):

```javascript
/**
 * D-CALLER-009: true when the D-CALLER-006 abort-and-recq path has fired
 * postTxAbort() and is waiting for the WS txState(Idle) event before calling
 * postTxCallCq().  Cleared on WS Idle delivery, Abort TX click, or Stop CQ click.
 */
let pendingRearmAfterAbort = false;
```

---

### 4.2 — D-CALLER-006 click handler: replace immediate call with flag set

Locate the `else` branch of the `decode-responder` click handler (currently
lines 494–510):

**Current:**
```javascript
        } else {
          // ── TxReport / WaitRr73: abort current session and re-arm CQ ──────────
          // D-CALLER-006: postTxAbort awaits SafeAbortToIdleAsync on the server
          // before returning, so the service is already at Idle when the await
          // resolves. postTxCallCq is safe to fire immediately after.
          // The operator selects their next partner in the new WaitAnswer.
          try {
            await postTxAbort();
            await postTxCallCq();
          } catch (err) {
            selectInFlight = false;
            tr.style.pointerEvents = 'none'; // keep deactivated on error
            console.error('D-CALLER-006 abort-and-recq failed:', err);
          }
          // selectInFlight and pointerEvents are NOT restored on success —
          // this row's lifecycle ends here; the operator clicks a fresh row.
        }
```

**Replace with:**
```javascript
        } else {
          // ── TxReport / WaitRr73: abort current session and re-arm CQ ──────────
          // D-CALLER-009: postTxAbort returns before SafeAbortToIdleAsync completes
          // on the background thread — do NOT call postTxCallCq immediately.
          // Set pendingRearmAfterAbort; the WS txState handler fires postTxCallCq
          // when the daemon confirms state: Idle, role: answerer.
          try {
            await postTxAbort();
            pendingRearmAfterAbort = true;
          } catch (err) {
            selectInFlight = false;
            tr.style.pointerEvents = 'none'; // keep deactivated on error
            console.error('D-CALLER-006 abort-and-recq failed:', err);
          }
          // selectInFlight and pointerEvents are NOT restored on success —
          // this row's lifecycle ends here; the operator clicks a fresh row.
        }
```

---

### 4.3 — Abort TX button handler: clear the pending flag

Locate the Abort TX handler (currently lines 831–846):

**Current:**
```javascript
  if (txAbortBtnEl) {
    txAbortBtnEl.addEventListener('click', async () => {
      txAbortBtnEl.disabled = true;
      try {
        const status = await postTxAbort();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? null,
          status.autoAnswerEnabled ?? false);
      } catch (err) {
        console.error('POST /api/v1/tx/abort failed:', err);
      } finally {
        txAbortBtnEl.disabled = false;
      }
    });
  }
```

**Replace with:**
```javascript
  if (txAbortBtnEl) {
    txAbortBtnEl.addEventListener('click', async () => {
      // D-CALLER-009: a manual abort cancels any pending D-CALLER-006 rearm.
      // Without this, the WS Idle event would fire postTxCallCq immediately
      // after a deliberate operator stop.
      pendingRearmAfterAbort = false;
      txAbortBtnEl.disabled = true;
      try {
        const status = await postTxAbort();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? null,
          status.autoAnswerEnabled ?? false);
      } catch (err) {
        console.error('POST /api/v1/tx/abort failed:', err);
      } finally {
        txAbortBtnEl.disabled = false;
      }
    });
  }
```

---

### 4.4 — Stop CQ handler: clear the pending flag

Locate the graceful-stop branch inside the Call CQ / Stop CQ click handler
(currently lines 858–867):

**Current:**
```javascript
      // ── Graceful stop path ────────────────────────────────────────────
      if (currentTxRole === 'caller' && currentTxState !== 'Idle') {
        try {
          await postTxStopCq();
          // Do NOT call renderTxPanel — the WS txState event (state: 'Idle')
          // will update the panel when SafeAbortToIdleAsync fires on the daemon.
        } catch (err) {
          console.error('POST /api/v1/tx/stop-cq failed:', err);
        }
        return;
      }
```

**Replace with:**
```javascript
      // ── Graceful stop path ────────────────────────────────────────────
      if (currentTxRole === 'caller' && currentTxState !== 'Idle') {
        // D-CALLER-009: a deliberate Stop CQ cancels any pending D-CALLER-006
        // rearm. Without this, the WS Idle event from the graceful stop would
        // fire postTxCallCq immediately after the operator requested a stop.
        pendingRearmAfterAbort = false;
        try {
          await postTxStopCq();
          // Do NOT call renderTxPanel — the WS txState event (state: 'Idle')
          // will update the panel when SafeAbortToIdleAsync fires on the daemon.
        } catch (err) {
          console.error('POST /api/v1/tx/stop-cq failed:', err);
        }
        return;
      }
```

---

### 4.5 — WS txState handler: consume the flag on Idle

Locate the `if (event.type === 'txState')` block (currently lines 1141–1153).
After the `event.abortReason` block and before `return`, add:

**Current:**
```javascript
    if (event.type === 'txState') {
      renderTxPanel(
        event.state             ?? 'Idle',
        event.partner           ?? null,
        event.autoAnswerEnabled ?? currentAutoAnswerEnabled,
        event.role              ?? undefined);

      // FR-UX-002: append to abort log when the daemon reports an abort reason.
      if (event.abortReason) {
        appendTxAbortLog(event.abortReason, event.partner ?? null);
      }
      return;
    }
```

**Replace with:**
```javascript
    if (event.type === 'txState') {
      renderTxPanel(
        event.state             ?? 'Idle',
        event.partner           ?? null,
        event.autoAnswerEnabled ?? currentAutoAnswerEnabled,
        event.role              ?? undefined);

      // FR-UX-002: append to abort log when the daemon reports an abort reason.
      if (event.abortReason) {
        appendTxAbortLog(event.abortReason, event.partner ?? null);
      }

      // D-CALLER-009: deferred rearm from D-CALLER-006 abort-and-recq path.
      // postTxAbort returns before SafeAbortToIdleAsync completes; we wait for
      // the authoritative WS Idle event before firing postTxCallCq.
      // Guard on role='answerer' because the service reverts to Answerer on
      // abort; a stale Idle event from the answerer path must not trigger rearm.
      if (pendingRearmAfterAbort
          && (event.state ?? 'Idle') === 'Idle'
          && (event.role  ?? 'answerer') === 'answerer') {
        pendingRearmAfterAbort = false;
        postTxCallCq().catch(err => console.error('D-CALLER-009 rearm failed:', err));
      }
      return;
    }
```

---

## 5. Acceptance criteria

1. **Happy path — abort-and-recq works end-to-end:**
   While in `TxReport` (None mode, caller role), double-click a responder row.
   Confirm in the browser network tab:
   - `POST /api/v1/tx/abort` fires and returns 200.
   - `POST /api/v1/tx/call-cq` fires within ~50 ms of the WS `txState`
     event delivering `state: 'Idle'`. Confirm it returns 200 (not 409).
   - The daemon log shows `QsoCallerService: state → TxCq` and TX fires
     the new CQ without operator intervention.

2. **Abort TX does not rearm:**
   While `pendingRearmAfterAbort` would be set (e.g. after a D-CALLER-006
   row click), click Abort TX. Confirm that no `POST /api/v1/tx/call-cq`
   fires after the WS Idle event arrives.

3. **Stop CQ does not rearm:**
   Same scenario — click Stop CQ instead of Abort TX. Confirm no automatic
   call-cq fires when the daemon delivers Idle.

4. **Idempotency — double row click:**
   Double-click the same responder row twice in quick succession. The second
   click is rejected by `selectInFlight`. Only one abort is sent; only one
   `pendingRearmAfterAbort = true` is set.

5. **Normal Stop CQ path unaffected:**
   With no pending rearm (normal session, operator clicks Stop CQ): the WS Idle
   event arrives, `pendingRearmAfterAbort` is false, no call-cq fires. Service
   returns to Idle cleanly.

6. **Same behaviour in `WaitRr73`:** repeat criterion 1 with the service in
   `WaitRr73` instead of `TxReport`.

7. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

8. Full test suite — 0 failures. (Pure front-end change; no C# tests affected.)

---

## 6. References

- Evidence log: `logs/openswfz-20260626T201136Z.log` — lines 406–436
- `web/js/main.js` lines 494–510 — D-CALLER-006 click handler else-branch
- `web/js/main.js` lines 831–846 — Abort TX button handler
- `web/js/main.js` lines 858–867 — Stop CQ handler
- `web/js/main.js` lines 1141–1153 — WS txState handler
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — `AbortAsync` (returns
  `Task.CompletedTask` immediately; see the field-set + CTS-cancel pattern)
- `src/OpenWSFZ.Web/WebApp.cs` lines 658–668 — abort endpoint (returns before
  `SafeAbortToIdleAsync` completes on the background thread)
- `aea1081` — D-CALLER-006 implementation (incorrect assumption in comment)
