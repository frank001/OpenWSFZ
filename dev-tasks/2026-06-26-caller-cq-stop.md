# Handoff: FR-CQ-STOP-001 — Call CQ graceful stop + abort-500 fix + FR-CQ-COLOUR-001

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action
**Session log:** `openswfz-20260626T173118Z.log`

---

## 1. Context

UAT session following the D-CALLER-005 correction (`e577c0d`) surfaced three issues:

### Issue A — D-CALLER-ABT-001: HTTP 500 on first `POST /api/v1/tx/abort`

**Root cause confirmed from log:**

```
System.UnauthorizedAccessException: Access to the path is denied.
   at System.IO.FileSystem.MoveFile(String sourceFullPath, String destFullPath, Boolean overwrite)
   at OpenWSFZ.Config.JsonConfigStore.SaveAsync(AppConfig config, CancellationToken ct)
   at OpenWSFZ.Web.WebApp... line 666
```

`AbortAsync` fires `_txCts.Cancel()` + `_abortTcs.TrySetResult()`, which schedules
`SafeAbortToIdleAsync` on the background thread. `SafeAbortToIdleAsync` saves
`autoAnswer=false` via `JsonConfigStore.SaveAsync` (atomic temp-file + rename). The
HTTP abort handler *also* calls `store.SaveAsync(... autoAnswer=false)` at line 666.
Two concurrent `File.Move` calls on the same target → `UnauthorizedAccessException`.

The comment at line 663–664 ("no conflict") is incorrect and must be removed.
The abort succeeded; only the HTTP response was 500. On retry (12.402 UTC) the
service was already Idle, so no concurrent write → 200 OK.

**Fix:** Remove lines 663–666 from the abort handler. `SafeAbortToIdleAsync` already
saves `autoAnswer=false`; the HTTP handler hardcodes `AutoAnswerEnabled: false` in
the response, which is correct.

---

### Issue B — FR-CQ-STOP-001: Call CQ button disabled during CQ session

The operator cannot stop CQ calling via the Call CQ button. The button is disabled
whenever `state !== 'Idle'` (`main.js` line 223). The only escape is `Abort TX`,
which immediately kills the audio mid-sample — not the behaviour the operator wants.

**Required UX:**

| Condition | Button state | Click action |
|---|---|---|
| `state === 'Idle'` | Enabled, label **"Call CQ"** | Start CQ (existing) |
| `role === 'caller'` AND `state ≠ 'Idle'` | Enabled, label **"Stop CQ"** | Graceful stop (new) |
| `role === 'answerer'` AND `state ≠ 'Idle'` | Disabled | — (already in a QSO) |

**Graceful stop behaviour:**
- The current TX sample plays to completion (≤ 12.6 s).
- After TX, the service returns to Idle without retransmitting.
- `Abort TX` remains the immediate-kill path.

---

### Issue C — FR-CQ-COLOUR-001 + FR-WF-001 still not implemented

Tasks from `2026-06-26-call-cq-btn-states.md` have NOT been applied.
They are included in the actions below (§3.7, §3.8) so everything ships in one PR.

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch. Do **not** open a new branch.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Abstractions/IQsoController.cs`

Add a default no-op `GracefulStopAsync` method to the interface.
Insert after the `AbortAsync` declaration:

```csharp
/// <summary>
/// Requests a graceful stop of the current CQ caller session.  The service completes
/// any in-progress TX before returning to Idle.  No-op for the answerer role.
/// </summary>
Task GracefulStopAsync(CancellationToken ct = default) => Task.CompletedTask;
```

`QsoAnswererService` inherits the default no-op; no change needed there.

---

### 3.2 — `src/OpenWSFZ.Daemon/QsoCallerService.cs` — four targeted edits

#### 3.2.1 — Add `_gracefulStopRequested` field

Near `_operatorAbortRequested` (line 87), add:

```csharp
private volatile bool _gracefulStopRequested;
```

#### 3.2.2 — Implement `GracefulStopAsync`

Insert after `AbortAsync` (after line 194):

```csharp
/// <inheritdoc/>
public Task GracefulStopAsync(CancellationToken ct = default)
{
    if (_callerState == CallerState.Idle) return Task.CompletedTask;

    _gracefulStopRequested = true;

    // Post a wakeup so the service exits ReadNextBatchAsync promptly in
    // Wait states, rather than waiting up to 15 s for the next decode batch.
    // In TX states the wakeup is queued and consumed after TransmitAsync returns
    // and the state machine re-enters a Wait state.
    var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
    _wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));

    return Task.CompletedTask;
}
```

#### 3.2.3 — Expand `needsWakeup` in `ReadNextBatchAsync`

Current (line 304):
```csharp
bool needsWakeup = _callerState is CallerState.Idle or CallerState.WaitAnswer;
```

Replace with:
```csharp
bool needsWakeup = _callerState is CallerState.Idle or CallerState.WaitAnswer or CallerState.WaitRr73;
```

Rationale: the wakeup channel is not monitored in `WaitRr73` by default; expanding
`needsWakeup` allows `GracefulStopAsync`'s wakeup to reach the service when it is
holding in `WaitRr73`.

#### 3.2.4 — Add graceful-stop check in `ProcessBatchAsync`

After the existing `_txCts.IsCancellationRequested` block (after line 356), insert:

```csharp
// FR-CQ-STOP-001: Graceful stop was requested via POST /api/v1/tx/stop-cq.
// The wakeup channel delivered this batch after the current TX completed and
// the state machine re-entered a Wait state.  Transition to Idle without
// interrupting any transmission (unlike AbortAsync which cancels _txCts).
if (_gracefulStopRequested)
{
    _gracefulStopRequested = false;
    await SafeAbortToIdleAsync(stoppingToken, "Operator stop").ConfigureAwait(false);
    return;
}
```

#### 3.2.5 — Clear flag in `SafeAbortToIdleAsync`

In `SafeAbortToIdleAsync`, alongside the `_txCts` and `_abortTcs` resets (around line 792),
add:

```csharp
_gracefulStopRequested = false;
```

This ensures the flag is cleared if an immediate abort (`AbortAsync`) supersedes a
pending graceful stop.

---

### 3.3 — `src/OpenWSFZ.Daemon/QsoControllerRouter.cs`

Add delegation after `AbortAsync` (line 98):

```csharp
/// <inheritdoc/>
public Task GracefulStopAsync(CancellationToken ct = default)
    => ActiveController.GracefulStopAsync(ct);
```

---

### 3.4 — `src/OpenWSFZ.Web/WebApp.cs` — two edits

#### 3.4.1 — Fix abort handler (D-CALLER-ABT-001)

Remove lines 663–666 from `POST /api/v1/tx/abort`:

```csharp
// DELETE these four lines:
// D-TX-UI-001: disarm after abort. Idempotent with the save in
// SafeAbortToIdleAsync — both write the same value; no conflict.
var currentTx = store.Current.Tx ?? new TxConfig();
await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = false } }, ct);
```

The handler after the edit should read:

```csharp
app.MapPost("/api/v1/tx/abort", async (IConfigStore store, CancellationToken ct) =>
{
    if (qsoController is not null)
        await qsoController.AbortAsync(ct);

    var state               = qsoController?.State  ?? QsoState.Idle;
    var partner             = qsoController?.Partner;
    var role                = qsoController?.Role.ToString().ToLowerInvariant() ?? "answerer";
    var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
    return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: false, Role: role, CallerPartnerSelect: callerPartnerSelect));
});
```

`SafeAbortToIdleAsync` already saves `autoAnswer=false`; `AutoAnswerEnabled: false`
in the response is hardcoded and always correct.

#### 3.4.2 — Add `POST /api/v1/tx/stop-cq` route

Insert immediately after the abort route:

```csharp
// ── POST /api/v1/tx/stop-cq (FR-CQ-STOP-001 — graceful caller stop) ─────
// Requests a graceful stop: current TX plays to completion, then the service
// returns to Idle.  Unlike /abort, _txCts is NOT cancelled — no audio interruption.
// The UI waits for the WS txState event (state: 'Idle') for final confirmation.
app.MapPost("/api/v1/tx/stop-cq", async (IConfigStore store, CancellationToken ct) =>
{
    if (qsoController is null)
        return Results.Problem("TX controller not available.", statusCode: 503);

    await qsoController.GracefulStopAsync(ct);

    // Return current state — TX may still be playing.
    var state               = qsoController.State;
    var partner             = qsoController.Partner;
    var role                = qsoController.Role.ToString().ToLowerInvariant();
    var autoAnswerEnabled   = state != QsoState.Idle;
    var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
    return TypedResults.Ok(new TxStatusResponse(
        state.ToString(), partner, autoAnswerEnabled, role, callerPartnerSelect));
});
```

`TxStatusResponse` is already registered in `AppJsonContext` — no serialisation
changes required.

---

### 3.5 — `web/js/api.js`

Add after `postTxCallCq` (after line 316):

```javascript
/**
 * POST /api/v1/tx/stop-cq
 * Requests a graceful stop of the current CQ caller session.
 * The service completes any in-progress TX before returning to Idle.
 * Final state is delivered via the WS txState event (state: 'Idle').
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, role: string}>}
 */
export function postTxStopCq() {
  return fetchJson('/api/v1/tx/stop-cq', { method: 'POST' });
}
```

`fetchJson` injects the `X-Api-Key` header and handles 401 redirect — same as
`postTxAbort`. No manual `fetch` needed.

---

### 3.6 — `web/js/main.js` — four edits

#### 3.6.1 — Add `postTxStopCq` to the import statement (line 11)

Current:
```javascript
import { getConfig, getFrequencies, postTune, postAudioOffset,
         getTxStatus, postTxEnable, postTxDisable, postTxAbort,
         postTxAnswerCq, postTxSelectResponder, postTxCallCq,
         postTxCallerPartnerSelect, getApiKey }                              from './api.js';
```

Replace with:
```javascript
import { getConfig, getFrequencies, postTune, postAudioOffset,
         getTxStatus, postTxEnable, postTxDisable, postTxAbort,
         postTxAnswerCq, postTxSelectResponder, postTxCallCq, postTxStopCq,
         postTxCallerPartnerSelect, getApiKey }                              from './api.js';
```

#### 3.6.2 — Hide Enable TX during caller mode — add one line in `renderTxPanel` (line 205)

**Root cause of the "totally unusable" interaction (session `openswfz-20260626T180106Z.log`):**

`SetStateAndNotify` in `QsoCallerService` hardcodes `autoAnswerEnabled: true` in every
WS event it publishes. `renderTxPanel` drives the Enable TX button from
`autoAnswerEnabled`, so the button stays armed-red for the entire caller session. When
the operator clicks Enable TX to disarm (POST `/api/v1/tx/disable`), the response
briefly shows it disarmed — but the next WS `txState` event from the caller
immediately re-arms it. The operator sees a rapid flicker and cannot break the loop.
Additionally, `POST /api/v1/tx/disable` only saves `autoAnswer=false` in config; it has
no effect on the running caller state machine (which only checks `autoAnswer` in
`HandleIdleAsync`, not once a session is underway).

**The fix:** hide Enable TX entirely when in caller mode.  The Call CQ / Stop CQ button
(§3.6.3) is the caller's primary control; Enable TX is an answerer concept.

Inside the existing Enable TX block in `renderTxPanel` (after `if (txEnableBtnEl) {`,
currently line 204), add one line immediately after that opening brace:

**Current block:**
```javascript
  // ── Enable/Disable toggle button ─────────────────────────────────────
  // D-TX-UI-002: label is always "Enable TX"; red background alone signals the armed state.
  if (txEnableBtnEl) {
    txEnableBtnEl.textContent = 'Enable TX';
    if (autoAnswerEnabled) {
      txEnableBtnEl.classList.add('tx-btn-armed');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-armed');
    }

    // FR-TX-UI-004: bright red when actively transmitting, dark red when armed-idle.
    if (autoAnswerEnabled && state.startsWith('Tx')) {
      txEnableBtnEl.classList.add('tx-btn-transmitting');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-transmitting');
    }
  }
```

**Replace with:**
```javascript
  // ── Enable/Disable toggle button ─────────────────────────────────────
  // D-TX-UI-002: label is always "Enable TX"; red background alone signals the armed state.
  if (txEnableBtnEl) {
    // FR-CQ-STOP-001: Hide Enable TX in caller mode.
    // The caller service always publishes autoAnswerEnabled=true; showing this button
    // armed during a CQ session creates an unbreakable re-arm loop — the operator
    // clicks disarm, the response briefly shows disarmed, then the next WS txState
    // event re-arms it.  Enable TX is an answerer concept; hide it in caller mode.
    // It reappears correctly when the role reverts to Answerer after the session ends.
    txEnableBtnEl.hidden = (currentTxRole === 'caller');

    txEnableBtnEl.textContent = 'Enable TX';
    if (autoAnswerEnabled) {
      txEnableBtnEl.classList.add('tx-btn-armed');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-armed');
    }

    // FR-TX-UI-004: bright red when actively transmitting, dark red when armed-idle.
    if (autoAnswerEnabled && state.startsWith('Tx')) {
      txEnableBtnEl.classList.add('tx-btn-transmitting');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-transmitting');
    }
  }
```

Note: `currentTxRole` is updated at line 197 (`if (role) currentTxRole = role;`) before
this block, so it always reflects the current role at the time of the call.

---

#### 3.6.3 — Replace the Call CQ button block in `renderTxPanel` (lines 220–224)

Current block:
```javascript
  // ── Call CQ button — enabled only when Idle ───────────────────────────
  // Spec (task 11.8): enabled when currentTxState === 'Idle'; disabled otherwise.
  if (txCallCqBtnEl) {
    txCallCqBtnEl.disabled = (state !== 'Idle');
  }
```

Replace with:
```javascript
  // ── Call CQ button — enable/disable + label + role-state colour ───────
  // FR-CQ-STOP-001: button toggles between "Call CQ" (Idle) and "Stop CQ"
  //   (caller active) so the operator can end a CQ session gracefully.
  // Disabled only when the answerer is busy (role ≠ caller AND state ≠ Idle).
  // FR-CQ-COLOUR-001: bright green = actively transmitting CQ (TxAnswer,
  //   role=caller); dark green = QSO in progress (any other non-Idle caller
  //   state); default = answerer mode or Idle.
  if (txCallCqBtnEl) {
    const effectiveRole  = role ?? currentTxRole;
    const isCallerActive = effectiveRole === 'caller' && state !== 'Idle';

    txCallCqBtnEl.disabled    = !isCallerActive && state !== 'Idle';
    txCallCqBtnEl.textContent = isCallerActive ? 'Stop CQ' : 'Call CQ';

    const isCalling  = effectiveRole === 'caller' && state === 'TxAnswer';
    const inProgress = effectiveRole === 'caller' && state !== 'Idle' && state !== 'TxAnswer';
    txCallCqBtnEl.classList.toggle('cq-btn-calling',     isCalling);
    txCallCqBtnEl.classList.toggle('cq-btn-in-progress', inProgress);
  }
```

#### 3.6.4 — Replace the Call CQ click handler in `DOMContentLoaded` (lines 788–819)

Current handler:
```javascript
  // Task 11.8 — Call CQ button.
  // Sends POST /api/v1/tx/call-cq; ...
  if (txCallCqBtnEl) {
    let callCqInFlight = false;
    txCallCqBtnEl.addEventListener('click', async () => {
      if (callCqInFlight) return;
      callCqInFlight = true;
      txCallCqBtnEl.disabled = true;
      try {
        const status = await postTxCallCq();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? currentTxPartner,
          status.autoAnswerEnabled ?? true,
          status.role              ?? 'caller');
        setTimeout(() => {
          callCqInFlight = false;
          // Button re-enable is driven by renderTxPanel (disabled when not Idle).
        }, 400);
      } catch (err) {
        callCqInFlight = false;
        txCallCqBtnEl.disabled = (currentTxState !== 'Idle');
        if (/** @type {any} */ (err)?.status === 409) {
          console.warn('Call CQ rejected — TX busy.');
        } else {
          console.error('POST /api/v1/tx/call-cq failed:', err);
        }
      }
    });
  }
```

Replace with:
```javascript
  // Task 11.8 / FR-CQ-STOP-001 — Call CQ / Stop CQ toggle button.
  // When Idle: POST /api/v1/tx/call-cq starts the CQ session (existing path).
  // When role=caller AND state≠Idle: POST /api/v1/tx/stop-cq requests a graceful
  //   stop — current TX plays to completion, then the service returns to Idle.
  //   Final state arrives via the WS txState event; no re-render on response.
  // When role=answerer AND state≠Idle: button is disabled (cannot start CQ).
  if (txCallCqBtnEl) {
    let callCqInFlight = false;
    txCallCqBtnEl.addEventListener('click', async () => {

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

      // ── Normal Call CQ path ───────────────────────────────────────────
      if (callCqInFlight) return;
      callCqInFlight = true;
      txCallCqBtnEl.disabled = true;
      try {
        const status = await postTxCallCq();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? currentTxPartner,
          status.autoAnswerEnabled ?? true,
          status.role              ?? 'caller');
        setTimeout(() => {
          callCqInFlight = false;
          // Button re-enable / label driven by renderTxPanel (via WS events).
        }, 400);
      } catch (err) {
        callCqInFlight = false;
        txCallCqBtnEl.disabled = (currentTxState !== 'Idle');
        if (/** @type {any} */ (err)?.status === 409) {
          console.warn('Call CQ rejected — TX busy.');
        } else {
          console.error('POST /api/v1/tx/call-cq failed:', err);
        }
      }
    });
  }
```

---

### 3.7 — `web/index.html` — FR-WF-001 hint text (from `call-cq-btn-states.md`)

Line 60, current:
```html
<span class="freq-readout-hint">Left-click: RX &middot; Right-click: TX &middot; Shift+click: both</span>
```

Replace with:
```html
<span class="freq-readout-hint">Ctrl+click: RX &middot; Ctrl+right-click: TX &middot; Ctrl+Shift+click: both</span>
```

---

### 3.8 — `web/css/app.css` — FR-CQ-COLOUR-001 CSS (from `call-cq-btn-states.md`)

Insert immediately after the existing `#tx-enable-btn.tx-btn-transmitting` block
(after line 231 of the current file):

```css
/* ── Call CQ button: role-state colours (FR-CQ-COLOUR-001) ─────────────── */

/* Calling CQ — bright green: role=caller, actively transmitting CQ */
#tx-call-cq-btn.cq-btn-calling {
  background:   var(--color-success);
  border-color: var(--color-success);
  color:        #0d1117;
  font-weight:  700;
}
#tx-call-cq-btn.cq-btn-calling:disabled {
  opacity: 1;   /* override default disabled dimming so colour reads clearly */
}
#tx-call-cq-btn.cq-btn-calling:hover:not(:disabled) {
  background:   #35a247;
  border-color: #35a247;
}

/* In progress — dark green: role=caller, QSO underway (not transmitting CQ) */
#tx-call-cq-btn.cq-btn-in-progress {
  background:   #1b4d26;
  border-color: #266636;
  color:        #fff;
  font-weight:  700;
}
#tx-call-cq-btn.cq-btn-in-progress:disabled {
  opacity: 1;   /* same: keep colour visible while button is disabled */
}
#tx-call-cq-btn.cq-btn-in-progress:hover:not(:disabled) {
  background:   #215930;
  border-color: #2d7a3a;
}
```

---

## 4. Acceptance criteria

### D-CALLER-ABT-001 (abort 500)

1. `POST /api/v1/tx/abort` returns HTTP 200 on the **first** call when the service is
   in `WaitAnswer` state — the `UnauthorizedAccessException` from concurrent
   `JsonConfigStore.MoveFile` no longer occurs.
2. After `AbortAsync` returns, the daemon log confirms "aborted to Idle" and the HTTP
   response body carries `state: "Idle"` or `state: "WaitReport"` (the latter is
   acceptable — the WS txState event corrects the panel within one cycle).

### FR-CQ-STOP-001 (Enable TX interaction fix — §3.6.2)

3. When the active role is `caller` (at any state), the Enable TX button is **not
   visible** in the DOM (`hidden` attribute set). It does not appear armed, does not
   flash, and cannot be clicked.
4. After a caller session ends (abort, graceful stop, QSO complete) and the role
   reverts to Answerer, Enable TX **reappears** in its correct disarmed state
   (WS txState event carries `autoAnswerEnabled: false`).
5. Rapidly toggling Enable TX before clicking Call CQ (answerer mode): no
   observable interference with the subsequent caller session.

### FR-CQ-STOP-001 (graceful stop)

6. While the service is in ANY non-Idle caller state (TxCq = "TxAnswer", WaitAnswer =
   "WaitReport", TxReport, WaitRr73, TxRr73): the Call CQ button is **enabled** and
   labelled **"Stop CQ"**.
4. Clicking "Stop CQ" while `CallerState.TxCq` (radio on air):
   - The current TX audio sample plays to completion (approx. 12.6 s remaining).
   - No immediate audio interruption (`KeyUpAsync` is NOT called from `GracefulStopAsync`).
   - After TX completes, the daemon log shows `state → WaitAnswer → Idle`.
   - The WS `txState` event delivers `state: "Idle"`, `role: "answerer"`,
     `autoAnswerEnabled: false`.
   - The TX panel reverts to Idle / disarmed; button shows "Call CQ".
5. Clicking "Stop CQ" while `CallerState.WaitAnswer` (no TX active):
   - Service transitions to Idle promptly (within one decode cycle, ≤ 15 s).
   - Same WS event and UI revert as criterion 4.
6. Clicking "Stop CQ" while `CallerState.WaitRr73` (no TX active):
   - Service transitions to Idle within one decode cycle (≤ 15 s).
   - Same WS event and UI revert as criterion 4.
7. Clicking "Stop CQ" twice in quick succession: idempotent. No error, no hang.
8. `Abort TX` button: behaviour **unchanged** — immediate audio kill, transitions to
   Idle at once.

### FR-CQ-COLOUR-001 (button colours)

9. Role = answerer or state = Idle: Call CQ button shows **default appearance**.
10. Role = caller, state = TxAnswer (CQ transmitting): Call CQ button shows
    **bright green** (`var(--color-success)` background). `opacity: 1` override
    keeps colour visible while disabled.
11. Role = caller, state ≠ Idle AND state ≠ TxAnswer (QSO in progress): Call CQ
    button shows **dark green** (`#1b4d26` background). Same opacity override.
12. On QSO complete / abort / graceful stop → Idle: button reverts to **default**.

### FR-WF-001 hint text

13. Waterfall hint reads exactly:
    `Ctrl+click: RX · Ctrl+right-click: TX · Ctrl+Shift+click: both`
14. The old hint text (`Left-click: RX`) does not appear anywhere in `web/`.

### General

15. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
16. Full test suite — 0 failures.  `GracefulStopAsync` on `QsoAnswererService`
    uses the default interface no-op — no test stub changes expected.
    Any mock in tests that implements `IQsoController` directly will need
    `GracefulStopAsync` added (it can be a no-op body: `=> Task.CompletedTask`).

---

## 5. References

- `openswfz-20260626T173118Z.log` — lines 3219–3270: full abort-500 stack trace
- `src/OpenWSFZ.Web/WebApp.cs:658–673` — abort handler (remove lines 663–666)
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:87` — `_operatorAbortRequested` field (add
  `_gracefulStopRequested` nearby)
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:172` — `AbortAsync` (insert
  `GracefulStopAsync` after this block)
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:304` — `needsWakeup` line (expand to
  include `WaitRr73`)
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:345` — `ProcessBatchAsync` top (insert
  graceful-stop check after the `_txCts.IsCancellationRequested` block at line 356)
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:770` — `SafeAbortToIdleAsync` reset block
  (add `_gracefulStopRequested = false`)
- `src/OpenWSFZ.Daemon/QsoControllerRouter.cs:97` — `AbortAsync` delegation (add
  `GracefulStopAsync` delegation immediately after)
- `web/js/main.js:11` — import line (add `postTxStopCq`)
- `web/js/main.js:220` — Call CQ button block in `renderTxPanel` (replace 4-line block)
- `web/js/main.js:788` — Call CQ click handler in `DOMContentLoaded` (replace block)
- `2026-06-26-call-cq-btn-states.md` — FR-WF-001 + FR-CQ-COLOUR-001 (superseded by
  §3.7 and §3.8 above; no separate implementation needed)
