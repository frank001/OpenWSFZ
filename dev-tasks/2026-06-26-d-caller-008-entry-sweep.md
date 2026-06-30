# Handoff: D-CALLER-008 — Stale TxReport/WaitRr73 decode-responder rows in new WaitAnswer

**Date:** 2026-06-26  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action  
**Defect ID:** D-CALLER-008  
**Severity:** Medium — stale teal rows carry old callsign and cycle data from a
prior QSO session into the new WaitAnswer; clicking one fires `postTxSelectResponder`
with a stale `responseCycleStartUtc`, producing wrong-phase TX slot selection.

---

## 1. Context

D-CALLER-006 extended `isResponderRow` to include `TxReport` and `WaitRr73` states
so the operator can abort-and-reselect mid-session.  Rows created during those states
receive the `decode-responder` class (teal), `cursor: pointer`, and a click handler.

The D-CALLER-005 sweep in `renderTxPanel` only fires on **WaitAnswer exit**:
```javascript
if (prevState === 'WaitAnswer' && state !== 'WaitAnswer') { /* sweep */ }
```

When a QSO completes without an abort (TxRr73 → QsoComplete → Idle → new CQ →
new WaitAnswer), the TxReport/WaitRr73 rows are never swept.  They remain in the
DOM at the start of the new WaitAnswer — teal, clickable, carrying stale
`responseCycleStartUtc` from the prior session.  They sit below the fresh rows
(table is newest-first) but are visually identical.

Clicking one fires `postTxSelectResponder(staleCallsign, staleFreq, staleCycleStart)`,
which the backend accepts (state = WaitAnswer), but uses the stale cycle start for
phase alignment → TX fires at the wrong slot.

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch.

---

## 3. Actions

### 3.1 — `web/js/main.js`: Add WaitAnswer entry sweep to `renderTxPanel`

Locate the bottom of `renderTxPanel`, immediately after the existing D-CALLER-005
exit sweep block:

```javascript
  // D-CALLER-005 (corrected): deactivate decode-responder rows when the
  // service leaves WaitAnswer.  Rows remain clickable throughout WaitAnswer
  // so the operator can select any responder they choose, from any cycle.
  if (prevState === 'WaitAnswer' && state !== 'WaitAnswer') {
    decodesBody.querySelectorAll('tr.decode-responder').forEach(row => {
      row.classList.remove('decode-responder');
      row.style.cursor       = '';
      row.style.pointerEvents = 'none';
    });
  }
```

Add the following block immediately after it:

```javascript
  // D-CALLER-008: sweep stale decode-responder rows on WaitAnswer entry.
  // Rows created during TxReport/WaitRr73 (D-CALLER-006) carry the
  // decode-responder class but become stale when the QSO completes normally
  // and a new WaitAnswer begins.  Clearing them here ensures only rows
  // created in the current WaitAnswer window are teal and clickable.
  if (prevState !== 'WaitAnswer' && state === 'WaitAnswer') {
    decodesBody.querySelectorAll('tr.decode-responder').forEach(row => {
      row.classList.remove('decode-responder');
      row.style.cursor        = '';
      row.style.pointerEvents = 'none';
    });
  }
```

One file, one location, eight lines (guard + sweep body + comment).

The entry sweep runs before any new decode rows arrive for the new WaitAnswer
(decodes are pushed by `handleDecodes`, not by `renderTxPanel`) so no freshly
created rows are cleared by this sweep.

---

## 4. Acceptance criteria

1. Complete a full QSO with a station (TxReport → WaitRr73 → TxRr73 → QsoComplete).
   Observe that decode-responder rows appear during TxReport/WaitRr73.
2. When the next WaitAnswer begins, confirm via DevTools Elements panel that ALL
   previously teal rows have had `decode-responder` removed and `pointer-events`
   set to `none`.  Only rows created within the new WaitAnswer window should be
   teal.
3. In the new WaitAnswer, clicking in the area of old (now grey) rows must not fire
   any `POST /api/v1/tx/select-responder` request.
4. The abort-and-recq path (D-CALLER-006) is unaffected: clicking a teal row in
   TxReport still fires `postTxAbort` + `postTxCallCq`, and the resulting new
   WaitAnswer has no stale rows.
5. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
6. Full test suite — 0 failures (pure front-end change).

---

## 5. References

- `web/js/main.js` — `renderTxPanel`, bottom of function, after D-CALLER-005 exit sweep
- D-CALLER-005 exit sweep (existing, do not modify)
- D-CALLER-006 (`aea1081`) — introduced the TxReport/WaitRr73 decode-responder rows
  that this sweep must clear on WaitAnswer entry
- QA review of `aea1081` — finding that prompted this handoff
