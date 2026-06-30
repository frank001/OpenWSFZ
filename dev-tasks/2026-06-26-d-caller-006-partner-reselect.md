# Handoff: D-CALLER-006 — No ability to change partner after selection

**Date:** 2026-06-26  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action  
**Defect ID:** D-CALLER-006  
**Severity:** Medium — operator committed to wrong partner must abort the entire
session rather than switching in place.

---

## 1. Context

When `QsoCallerService` is in `None` mode (CallerPartnerSelect = None), teal
decode-responder rows appear in WaitAnswer.  Double-clicking one fires
`POST /api/v1/tx/select-responder`, state transitions to TxReport, and the
D-CALLER-005 sweep deactivates all teal rows.

New decode responses arriving during `TxReport` or `WaitRr73` receive only
`decode-partner` (red) highlighting — `isResponderRow = false` because
`currentTxState !== 'WaitAnswer'`.  Red rows have no click handler for partner
switching.  The operator cannot change partners; the only remedy is
Stop CQ or Abort TX followed by a new CQ cycle.

**Evidence (`openswfz-20260626T183541Z.log`):**

```
20:41:36  select-responder → PD3QA (operator's intended target was PD2FZ)
          renderTxPanel("TxReport") → sweep deactivates all teal rows
20:41:36+ PD2FZ/P PD2FZ +38 continues appearing — but state = TxReport
          → isResponderRow = false → rows are red only, no click handler
          → Operator double-clicks PD2FZ rows → nothing fires → "no effect"
```

---

## 2. Design decision required

Two implementation approaches are available.  **The Captain must choose one
before implementation begins.**

### Option A — Abort-and-reselect on click (aggressive, immediate)

While in `TxReport` or `WaitRr73` (caller role, None mode), decode rows that
match the responder pattern receive `decode-responder` class and a click handler.
Clicking one:
1. Fires `POST /api/v1/tx/abort` (immediate TX stop).
2. Fires `POST /api/v1/tx/call-cq` (re-arms caller role).
3. Fires `POST /api/v1/tx/select-responder` with the new callsign.

Steps 2 and 3 must be sequenced — fire call-cq after the WS `txState` event
confirms state = Idle (role = caller).

Visual distinction: these rows could use a different teal shade or a cursor with
a warning symbol to signal "clicking this aborts the current TX."

**Trade-off:** If the operator is mid-transmission, clicking a new responder row
cuts the TX audio immediately.  Good for fixing misclicks; bad if unintentional.

### Option B — Graceful-stop-and-reselect on click (conservative)

Same as Option A but uses `POST /api/v1/tx/stop-cq` instead of abort.  The
current TX plays to completion, then the service returns to Idle.

The click handler fires stop-cq and stores the desired new callsign locally.
When the WS `txState` event confirms Idle, the handler fires call-cq +
select-responder.

**Trade-off:** Up to 12.6 s delay before the switch takes effect.  Feedback
must be shown to the operator (e.g. a "Pending switch to [callsign]" label)
so they know the click was registered.  More complex to implement correctly.

---

## 3. Branch

`fix/caller-ux-fixes` — amend the existing branch.  Implement the chosen option.

---

## 4. Actions

### 4.1 — `web/js/main.js`: Extend `isResponderRow` to TxReport and WaitRr73

Current condition (inside `handleDecodes`):
```javascript
const isResponderRow =
  currentTxRole === 'caller'
  && currentTxState === 'WaitAnswer'
  && currentCallerPartnerSelect === 'None'
  && ...
```

Extend the state check:
```javascript
const isResponderRow =
  currentTxRole === 'caller'
  && (currentTxState === 'WaitAnswer'
      || currentTxState === 'TxReport'
      || currentTxState === 'WaitRr73')
  && currentCallerPartnerSelect === 'None'
  && ...
```

### 4.2 — `web/js/main.js`: Branch click handler on current state

Wrap the existing click handler body in `if (currentTxState === 'WaitAnswer')` and
add the TxReport/WaitRr73 branch:

```javascript
tr.addEventListener('click', async () => {
  if (selectInFlight) return;
  selectInFlight = true;
  tr.style.pointerEvents = 'none';

  const responderCallsign     = msgTokens[1];
  const responseCycleStartUtc = tr.dataset.cqCycleStartUtc;

  if (currentTxState === 'WaitAnswer') {
    // ── Normal WaitAnswer path — unchanged ────────────────────────────────
    try {
      const status = await postTxSelectResponder(
        responderCallsign, r.freqHz, responseCycleStartUtc);
      renderTxPanel(
        status.state             ?? currentTxState,
        status.partner           ?? currentTxPartner,
        status.autoAnswerEnabled ?? currentAutoAnswerEnabled,
        status.role              ?? currentTxRole);
      setTimeout(() => {
        selectInFlight = false;
        if (tr.classList.contains('decode-responder')) {
          tr.style.pointerEvents = '';
        }
      }, 400);
    } catch (err) {
      selectInFlight = false;
      tr.style.pointerEvents = '';
      const errStatus = /** @type {any} */ (err)?.status;
      if (errStatus === 409 || errStatus === 405) {
        console.warn('postTxSelectResponder ignored — role/state mismatch:', errStatus);
      } else {
        console.error('postTxSelectResponder error:', err);
      }
    }

  } else {
    // ── TxReport / WaitRr73: abort current session and re-arm CQ ──────────
    // postTxAbort() awaits SafeAbortToIdleAsync on the server before returning,
    // so the service is already at Idle+Answerer when the await resolves.
    // postTxCallCq() is safe to fire immediately after.
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
});
```

### 4.4 — `web/css/app.css`: Visual distinction for abort rows (optional)

Rows in TxReport/WaitRr73 trigger abort+call-cq on click rather than a direct
partner select.  If the Captain requests a visual distinction (e.g. amber instead
of teal, or a different cursor), add a CSS class `cq-responder-abort` and apply it
in the `isResponderRow` block when `currentTxState !== 'WaitAnswer'`.  Omit unless
requested.

---

## 5. Acceptance criteria

1. While in `TxReport` (caller role, None mode): new decode rows addressed to our
   callsign appear teal and are clickable.  Same applies in `WaitRr73`.
2. Double-clicking a teal row during `TxReport` fires `POST /api/v1/tx/abort`
   then `POST /api/v1/tx/call-cq` in that order.  Confirm both in the network tab.
3. TX to the previously selected partner ceases.  A new CQ fires on the next
   available FT8 slot.  The operator then selects their next partner by clicking
   a teal row in the new WaitAnswer.
4. If either request fails (non-2xx), `selectInFlight` is reset so the row
   accepts clicks again and the operator can retry.
5. Same behaviour in `WaitRr73`.
6. `WaitAnswer` behaviour is unchanged — normal select-responder path, no abort.
7. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
8. Full test suite — 0 failures.

---

## 6. References

- Session `openswfz-20260626T183541Z.log` lines 1443–1498
- D-CALLER-007 (separate, simpler handoff) — ghost row fix; apply alongside this change
- `web/js/main.js` — `handleDecodes`, `isResponderRow` block, click handler
- `web/js/api.js` — `postTxAbort`, `postTxCallCq`, `postTxSelectResponder` (all exist;
  no new endpoints or backend changes required — pure front-end change)
