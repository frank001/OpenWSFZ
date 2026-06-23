# Developer Handoff — TX Panel: Abort and QSO Completion Disarm

**Date:** 2026-06-22  
**Prepared by:** QA Engineer  
**Defect IDs:** D-TX-UI-001, D-TX-UI-002, D-TX-UI-003  

---

## 1. Context

Three defects were found during live QSO testing on `feat/gui-tx-panel`
(log `openswfz-20260622T163949Z.log`, session 18:39–18:47 local).

**D-TX-UI-001 — Abort TX does not disarm.**  
After clicking "Abort TX", `tx.autoAnswer` remains `true`. The QSO answerer
immediately answers the next decoded CQ without operator action. Confirmed in
the log: abort at 18:43:35 → new QSO started at 18:44:00 (25 seconds later).

**D-TX-UI-002 — "TX Armed" label is confusing.**  
The operator finds the label change from "Enable TX" → "TX Armed" unintuitive.
Preference: keep the label "Enable TX" throughout; red background alone signals
the armed state. This is a 1-line JS change.

**D-TX-UI-003 — QSO completion does not disarm.**  
After `QsoComplete` at 18:42:43, `tx.autoAnswer` remained `true`. The system
answered PD2FZ's next CQ at 18:43:30 without operator re-arming. The Captain
has confirmed the intended behaviour: **supervised single-QSO model** — any
return to Idle (whether from abort, normal completion, or retry exhaustion)
must disarm TX and require explicit operator re-arming before the next QSO.

---

## 2. Branch

Work on the existing branch: **`feat/gui-tx-panel`**  
These are defects found during QA review of that change; fix them before merge.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Web/AppJsonContext.cs` — extend `WsTxStateMessage`

Add `bool AutoAnswerEnabled` to the `WsTxStateMessage` record so that the
`txState` WebSocket event can carry the updated arm/disarm state on every
transition:

```csharp
// Before:
internal sealed record WsTxStateMessage(string Type, string State, string? Partner);

// After:
internal sealed record WsTxStateMessage(string Type, string State, string? Partner, bool AutoAnswerEnabled);
```

No `AppJsonContext` attribute change needed — the existing
`[JsonSerializable(typeof(WsTxStateMessage))]` covers the updated record.

---

### 3.2 — `src/OpenWSFZ.Web/WebSocketHub.cs` — extend `BroadcastTxState`

Add `bool autoAnswerEnabled` parameter and include it in the serialised message:

```csharp
// Before:
internal static void BroadcastTxState(QsoState state, string? partner)
{
    if (ActiveSockets.IsEmpty) return;
    var msg = new WsTxStateMessage(Type: "txState", State: state.ToString(), Partner: partner);
    ...
}

// After:
internal static void BroadcastTxState(QsoState state, string? partner, bool autoAnswerEnabled)
{
    if (ActiveSockets.IsEmpty) return;
    var msg = new WsTxStateMessage(
        Type:              "txState",
        State:             state.ToString(),
        Partner:           partner,
        AutoAnswerEnabled: autoAnswerEnabled);
    ...
}
```

---

### 3.3 — `src/OpenWSFZ.Web/TxEventBus.cs` — extend `Publish`

```csharp
// Before:
public void Publish(QsoState state, string? partner)
    => WebSocketHub.BroadcastTxState(state, partner);

// After:
public void Publish(QsoState state, string? partner, bool autoAnswerEnabled)
    => WebSocketHub.BroadcastTxState(state, partner, autoAnswerEnabled);
```

---

### 3.4 — `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — update callers

There are two call sites for `_txEventBus.Publish`:

**a) `SetStateAndNotify` — active QSO states (TxAnswer, TxReport, Tx73, WaitReport, WaitRr73, QsoComplete)**

For all of these states `autoAnswer` must be `true` (it was true to enter the
QSO). Pass `true` unconditionally:

```csharp
private void SetStateAndNotify(QsoState newState)
{
    var partner = _partner;
    _state = newState;
    _logger.LogDebug("QsoAnswererService: state → {State} (partner: {Partner}).",
        newState, partner ?? "(none)");
    _txEventBus.Publish(newState, partner, autoAnswerEnabled: true);
}
```

**b) `SafeAbortToIdleAsync` — the Idle transition (D-TX-UI-001 / D-TX-UI-003)**

`SafeAbortToIdleAsync` is called on every return to Idle (abort, QSO completion,
retry exhaustion, partner working another station). Per the supervised single-QSO
model, ALL of these must disarm. Add the config save and pass `false`:

```csharp
private async Task SafeAbortToIdleAsync(CancellationToken stoppingToken)
{
    var wasPartner = _partner;
    _partner        = null;
    _partnerGrid    = null;
    _skipNextRetry  = false;

    // H6: clear AP constraints.
    _decoder?.SetApConstraints(null);

    // Replace TX CTS with a fresh one.
    _txCts = new CancellationTokenSource();

    // Stop any active TX output.
    try { await _pttController.KeyUpAsync(stoppingToken).ConfigureAwait(false); }
    catch (Exception ex) { _logger.LogWarning(ex, "KeyUpAsync threw during abort — ignoring."); }

    // D-TX-UI-001 / D-TX-UI-003: disarm on every return to Idle (supervised model).
    // Save autoAnswer = false; this write is idempotent if the HTTP endpoint already saved it.
    try
    {
        var currentTx = _configStore.Current.Tx ?? new TxConfig();
        await _configStore.SaveAsync(
            _configStore.Current with { Tx = currentTx with { AutoAnswer = false } },
            stoppingToken).ConfigureAwait(false);
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "QsoAnswererService: failed to save autoAnswer=false on disarm — ignoring.");
    }

    if (_state != QsoState.Idle)
    {
        _logger.LogInformation(
            "QsoAnswererService: aborted to Idle (was: {State}, partner: {Partner}).",
            _state, wasPartner ?? "(none)");
    }

    _state      = QsoState.Idle;
    _retryCount = 0;
    _txEventBus.Publish(QsoState.Idle, null, autoAnswerEnabled: false);
}
```

---

### 3.5 — `src/OpenWSFZ.Web/WebApp.cs` — update `/api/v1/tx/abort` route (D-TX-UI-001)

The abort endpoint currently returns `Results.Ok()` with no body. Change it to
save `autoAnswer = false` and return a `TxStatusResponse`:

```csharp
// Before:
app.MapPost("/api/v1/tx/abort", async (CancellationToken ct) =>
{
    if (qsoController is not null)
        await qsoController.AbortAsync(ct);
    return Results.Ok();
});

// After:
app.MapPost("/api/v1/tx/abort", async (CancellationToken ct) =>
{
    if (qsoController is not null)
        await qsoController.AbortAsync(ct);

    // D-TX-UI-001: disarm after abort. This is idempotent with the save in
    // SafeAbortToIdleAsync — both write the same value; no conflict.
    var currentTx = store.Current.Tx ?? new TxConfig();
    await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = false } }, ct);

    var state   = qsoController?.State  ?? QsoState.Idle;
    var partner = qsoController?.Partner;
    return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: false));
});
```

The `store` variable is captured from the outer scope (already used by the other
route handlers). No new DI wiring required.

---

### 3.6 — `web/js/api.js` — update `postTxAbort` to return parsed JSON

```javascript
// Before:
export async function postTxAbort() {
  const res = await fetch('/api/v1/tx/abort', { method: 'POST' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/tx/abort`);
  }
}

// After:
/**
 * POST /api/v1/tx/abort
 * Aborts any in-progress QSO and disarms TX (sets autoAnswer = false).
 * Returns the updated TX status.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean}>}
 */
export function postTxAbort() {
  return fetchJson('/api/v1/tx/abort', { method: 'POST' });
}
```

---

### 3.7 — `web/js/main.js` — three changes

**a) Abort button handler (D-TX-UI-001):**

```javascript
// Before:
if (txAbortBtnEl) {
  txAbortBtnEl.addEventListener('click', () => {
    postTxAbort().catch(err => console.error('POST /api/v1/tx/abort failed:', err));
  });
}

// After:
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

**b) `txState` WebSocket event handler — read `autoAnswerEnabled` from event (D-TX-UI-003):**

```javascript
// Before:
if (event.type === 'txState') {
  renderTxPanel(
    event.state   ?? 'Idle',
    event.partner ?? null,
    currentAutoAnswerEnabled);
  return;
}

// After:
if (event.type === 'txState') {
  renderTxPanel(
    event.state             ?? 'Idle',
    event.partner           ?? null,
    event.autoAnswerEnabled ?? currentAutoAnswerEnabled);
  return;
}
```

**c) `renderTxPanel` label fix (D-TX-UI-002) — keep "Enable TX" always:**

```javascript
// Before (main.js ~line 119):
txEnableBtnEl.textContent = 'TX Armed';

// After:
txEnableBtnEl.textContent = 'Enable TX';
```

The `.tx-btn-armed` CSS class (red background) remains unchanged. The button
label is always "Enable TX"; colour alone signals the armed state.

---

### 3.8 — Tests

**`tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`:**

Add the following test cases (follow the existing patterns in that file):

1. **`AbortAsync_WhenActiveQso_SetsAutoAnswerFalseInConfig`** — start a QSO
   (use the existing feeder pattern), call `AbortAsync`, assert
   `configStore.Current.Tx.AutoAnswer == false`.

2. **`QsoComplete_SetsAutoAnswerFalseInConfig`** — drive a complete
   TxAnswer→TxReport→Tx73 exchange, assert `configStore.Current.Tx.AutoAnswer == false`
   after the `QsoComplete` transition.

3. **`RetryExhausted_SetsAutoAnswerFalseInConfig`** — let the watchdog or retry
   counter expire and confirm `autoAnswer` is cleared on the resulting Idle
   transition.

**`tests/OpenWSFZ.Web.Tests/`** (integration tests for the abort endpoint):

4. **`TxAbort_ReturnsJsonBodyWithAutoAnswerEnabledFalse`** — `POST /api/v1/tx/abort`,
   assert HTTP 200 and `response.autoAnswerEnabled == false`.

**`tests/OpenWSFZ.Web.Tests/`** (WS event schema):

5. **`TxStateBroadcast_IncludesAutoAnswerEnabled`** — verify that the `txState`
   event JSON contains an `autoAnswerEnabled` field (true for active states,
   false for Idle).

---

## 4. Acceptance Criteria

QA will verify all of the following before approving merge:

- [ ] **AC-1 (D-TX-UI-001):** After clicking "Abort TX" during an active QSO, the
  "Enable TX" button returns to its unarmed appearance (no red background).
  The system does NOT automatically answer the next decoded CQ.
  `POST /api/v1/tx/abort` returns a JSON body with `autoAnswerEnabled: false`.

- [ ] **AC-2 (D-TX-UI-002):** The "Enable TX" button label never changes to
  "TX Armed" in any state. Red background is the only visual distinction between
  armed and disarmed. Verified in browser.

- [ ] **AC-3 (D-TX-UI-003):** After a QSO completes (73 sent and logged), the
  "Enable TX" button returns to its unarmed appearance. The system does NOT
  automatically answer the next decoded CQ without operator re-arming.

- [ ] **AC-4:** The `txState` WebSocket event carries `autoAnswerEnabled` in its
  JSON payload. Verified in browser DevTools Network → WS frame inspector.

- [ ] **AC-5:** `dotnet test OpenWSFZ.slnx -c Release` — all existing tests pass
  plus the five new tests from §3.8.

- [ ] **AC-6:** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings.

---

## 5. References

- OpenSpec change: `openspec/changes/gui-tx-panel/`  
- Live session log: `logs/openswfz-20260622T163949Z.log` (git-ignored)  
- Key log lines: abort at 18:43:35; immediate re-answer at 18:44:00; QsoComplete at 18:42:43; immediate re-answer at 18:43:30  
- Design doc: `openspec/changes/gui-tx-panel/design.md` (Goals section: "Single source of truth for the armed/disarmed state")  
- QA review findings: conversation 2026-06-22 (TX panel field session review)
