# Handoff: "Call CQ" button — main TX panel

**Date:** 2026-06-25  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action

---

## 1. Context

`feat/qso-caller` has fully implemented the `QsoCallerService` backend and wired the Settings → General TX Mode selector (tasks 8.1–8.7). However, engaging the caller role requires navigating to the settings page, selecting "Caller", saving, and restarting the daemon — an unacceptable workflow for an operator who wants to call CQ spontaneously during a session.

The Captain has specified:

- A **"Call CQ" button** must be added to the main TX panel, next to "Abort TX".
- The button must work **regardless of the role the daemon was started with** (Answerer or Caller).  
  Clicking "Call CQ" while in Answerer mode must switch the runtime role to Caller, arm TX,  
  and transmit CQ — **no settings visit or daemon restart required**.
- **"Enable TX" remains** as the arm/disarm toggle for Answerer mode. Both buttons co-exist;  
  which is relevant depends on the active role.
- After the caller QSO completes naturally (RR73 sent) **or** is aborted, the runtime role  
  **reverts to whatever role the daemon was started with** (usually Answerer).

This work is to be completed on the **`feat/qso-caller`** branch before that branch is merged to `main`.

---

## 2. Branch

`feat/qso-caller` (existing) — add commits directly to this branch.  
Do **not** create a new branch; these changes are part of the same feature.

---

## 3. Actions

### 3.1 — Backend: runtime role switching

The current DI wiring in `Program.cs` registers either `QsoAnswererService` **or** `QsoCallerService` as `IQsoController` at startup. Dynamic switching requires both to be available at runtime.

**Recommended approach (developer may choose an alternative; document the reasoning in a commit message):**

Introduce a thin `QsoControllerRouter : IQsoController, IHostedService` that:

1. Is registered as a singleton (`IQsoController`, `IHostedService`). Replaces the current conditional registration of the concrete service as `IHostedService`.
2. Holds references to both a `QsoAnswererService` and a `QsoCallerService` singleton (injected; neither registered as `IHostedService` themselves).
3. Has a `QsoRole _configuredRole` (set from `TxConfig.Role` at construction) and a `QsoRole _activeRole` (runtime state, starts equal to `_configuredRole`).
4. Its `ExecuteAsync` runs a loop reading `DecodeBatch` items from the channel and calls an internal `ProcessBatchAsync(batch, ct)` on whichever concrete service matches `_activeRole`. The inactive service never sees batches.
5. Exposes `SwitchToCallerAsync()` / `SwitchToAnswererAsync()` methods:
   - Abort the currently active service if it is not Idle.
   - Update `_activeRole`.
   - Arm / disarm the target service accordingly.
6. Delegates all `IQsoController` members (`State`, `Partner`, `Role`, `AbortAsync`, `AnswerCqAsync`, `SelectResponderAsync`) to the service identified by `_activeRole`.
7. `Role` property: returns the `_configuredRole` (persisted setting), **not** the transient `_activeRole`, so that the settings page continues to reflect the stored configuration. The `txState` WebSocket event's `role` field should reflect the `_activeRole` (the active runtime behaviour).

> **Alternative approaches** (if the router pattern is too invasive):  
> - Fan-out the decode channel to two separate per-service channels; both services run as hosted services but each has an `bool IsActive` guard.  
> - A lightweight "mode override" flag on the answerer service that, when set, delegates `HandleIdleAsync` to caller logic.  
> Any of these is acceptable provided the acceptance criteria below are met.

**Revert-on-completion behaviour:**  
After `QsoCallerService.SafeAbortToIdleAsync` (for any reason — natural QSO completion or operator abort), if `_configuredRole == Answerer`, the router must switch `_activeRole` back to Answerer. This may be achieved by:
- Having `QsoCallerService` raise an event / call a delegate injected by the router, or
- Having the router observe the `txState` broadcast for `state == "Idle"` and `role == "caller"`.

### 3.2 — Backend: new API endpoint

Add to `WebApp.cs`:

```
POST /api/v1/tx/call-cq
```

Behaviour:
- **If active role is already Caller and state is Idle:** arm autoAnswer → the caller will transmit CQ on the next cycle. Return `TxStatusResponse` with `role: "caller"`.
- **If active role is Caller and state is not Idle:** return HTTP 409 (QSO in progress). Body: `{"error": "TX busy"}`.
- **If active role is Answerer and state is Idle:** call `router.SwitchToCallerAsync()`; arm autoAnswer. Return `TxStatusResponse` with `role: "caller"`.
- **If active role is Answerer and state is not Idle:** return HTTP 409.

The endpoint uses `IQsoController` (the router proxy) as its handle; it must not reference concrete service types directly.

Add `postTxCallCq` to `api.js`:
```js
export async function postTxCallCq() {
  return await _fetchJson('/api/v1/tx/call-cq', { method: 'POST' });
}
```

### 3.3 — Frontend: HTML

In `web/index.html`, inside `#tx-panel`, locate the controls row containing `#tx-enable-btn` and `#tx-abort-btn`. Add **between** the two existing buttons:

```html
<button id="tx-call-cq-btn" class="tx-btn">Call CQ</button>
```

Final button order in the row: **Enable TX · Call CQ · Abort TX**

### 3.4 — Frontend: CSS

No new rules required — `tx-btn` already styles generic TX buttons. If the designer wishes, a distinct `.tx-btn-caller` armed state (e.g. a teal/green background) may be added to visually differentiate the Caller armed state from the Answerer armed state (`tx-btn-armed` red). This is optional; the QA engineer will not block on it.

### 3.5 — Frontend: main.js

1. Import `postTxCallCq` from `api.js`.
2. Cache `document.getElementById('tx-call-cq-btn')` as `txCallCqBtnEl`.
3. Wire click handler:
   - Disable button during request.
   - Call `postTxCallCq()`.
   - On HTTP 200: call `renderTxPanel(status.state, status.partner, status.autoAnswerEnabled, status.role)`.
   - On HTTP 409: log `console.warn('Call CQ rejected — TX busy')`. Re-enable button.
   - On other error: log `console.error(...)`. Re-enable button.
   - Use an `inFlight` guard (400 ms, same pattern as CQ-row clicks) to prevent double-fire.
4. Button enabled/disabled state: **enabled** when `currentTxState === 'Idle'`; **disabled** at all other times. Update in `renderTxPanel`.

### 3.6 — Backend: tests

Add to `OpenWSFZ.Web.Tests` (or a new `QsoControllerRouterTests` in `Daemon.Tests`):

1. `CallCq_WhenAnswererIdle_SwitchesToCallerAndArms` — POST `/api/v1/tx/call-cq` when configured as Answerer and Idle; assert response `role: "caller"`, `autoAnswerEnabled: true`.
2. `CallCq_WhenAnswererBusy_Returns409` — POST while Answerer has an active QSO; assert HTTP 409.
3. `CallCq_WhenCallerIdle_ArmsWithoutSwitch` — POST when already in Caller mode and Idle; assert HTTP 200, `role: "caller"`.
4. `CallCq_WhenCallerBusy_Returns409` — POST while Caller QSO active; assert HTTP 409.
5. `Router_AfterCallerQsoComplete_RevertsToAnswerer` — drive a full caller QSO to completion (RR73 sent); assert `IQsoController.Role` reverts to `QsoRole.Answerer` if that was the configured role.
6. `Router_AfterCallerAbort_RevertsToAnswerer` — abort a caller QSO; assert role reverts.

### 3.7 — Existing verification tasks

Update `openspec/changes/qso-caller/tasks.md` — mark tasks 10.1–10.4 (manual verification) as applicable to post-implementation testing. Do not mark them `[x]` — the QA engineer will verify them.

---

## 4. Acceptance criteria

The QA engineer will verify:

1. **Button present:** "Call CQ" button is visible in the TX panel between "Enable TX" and "Abort TX" when viewing the main page.
2. **Answerer → Caller at runtime:** With daemon started in Answerer mode, clicking "Call CQ" arms the system and the TX panel shows caller message row templates (`CQ / +00 / RR73`). No settings visit or restart was performed.
3. **CQ transmitted:** On the next appropriate FT8 cycle, the daemon transmits `CQ {callsign} {grid}`.
4. **Revert after QSO:** After a full CQ → Exchange → RR73 QSO completes, the panel reverts to Answerer mode. Clicking "Enable TX" subsequently arms the answerer (not the caller).
5. **Revert after abort:** Clicking "Abort TX" during a caller QSO reverts the panel to Answerer mode.
6. **409 handling:** Clicking "Call CQ" during an active QSO (any role) does nothing visible to the user (logged to console); the button re-enables after the request completes.
7. **Answerer unaffected:** With daemon started in Answerer mode and no "Call CQ" interaction, the answerer behaves identically to the current `main` branch. (Regression.)
8. **All tests green:** `dotnet test OpenWSFZ.slnx -c Release` — zero failures.
9. **Zero build warnings:** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

---

## 5. References

- OpenSpec change: `openspec/changes/qso-caller/` (tasks.md sections 3–9)
- Design note: tasks.md section 3.14 (D8 — `IQsoController.State` maps `CallerState` to proxy `QsoState`)
- Lesson learned #18 (MEMORY.md): sealed classes prevent substitution — do not seal the router
- Lesson learned #6 (MEMORY.md): STJ source-gen and `[JsonConstructor]` default parameters
- Prior DI pattern: `Program.cs` lines 339–353 (conditional registration)
