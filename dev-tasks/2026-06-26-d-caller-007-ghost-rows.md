# Handoff: D-CALLER-007 — Ghost responder rows remain clickable after sweep

**Date:** 2026-06-26  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action  
**Defect ID:** D-CALLER-007  
**Severity:** Medium — causes operator to inadvertently re-engage a previous-session
station without visual feedback that the row is active.

---

## 1. Context

The `decode-responder` click handler (added as part of the D-CALLER-005 fix, task 7.5)
contains a 400 ms setTimeout that resets `tr.style.pointerEvents = ''` after a
successful `postTxSelectResponder` call.

The D-CALLER-005 sweep (`renderTxPanel`, triggered on WaitAnswer exit) sets
`pointer-events: none` on all `tr.decode-responder` rows AND removes the
`decode-responder` class.  This fires before the 400 ms timeout expires.

**Race:** sweep fires at T+0, removes `decode-responder`, sets `pointer-events: none`.
At T+400 ms the timeout fires and sets `tr.style.pointerEvents = ''`.  The row now
has no `decode-responder` class (visually grey / no teal) but accepts pointer events.
Its closure retains the original callsign and frequency.  A click on this ghost row
fires `postTxSelectResponder` for a station from a prior session.

**Evidence (`openswfz-20260626T183541Z.log`):**

Session 1 WaitAnswer: PD3QA (cycle 18:37:15, 500 Hz) row clicked → sweep fires
at 20:37:38 → 400 ms timeout fires at ~20:37:39 → `pointer-events: ''` restored.
This row persists as a ghost through sessions 2 and 3.

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch.

---

## 3. Actions

### 3.1 — `web/js/main.js`: Guard the pointer-events reset in the selectInFlight timeout

Locate the 400 ms setTimeout inside the `decode-responder` click handler
(inside `handleDecodes`, inside the `if (isResponderRow)` block):

**Current:**
```javascript
        setTimeout(() => {
          selectInFlight = false;
          tr.style.pointerEvents = '';
        }, 400);
```

**Replace with:**
```javascript
        setTimeout(() => {
          selectInFlight = false;
          // Only restore pointer-events if this row is still an active responder row.
          // If the D-CALLER-005 sweep has already deactivated it (removed the
          // decode-responder class and set pointer-events: none), restoring
          // pointer-events here would create a ghost row — clickable with no visual
          // indication, firing select-responder for a station from a prior session.
          if (tr.classList.contains('decode-responder')) {
            tr.style.pointerEvents = '';
          }
        }, 400);
```

One file, one location, three additional lines (the guard condition + comment).

---

## 4. Acceptance criteria

1. Select a responder in WaitAnswer (None mode). Confirm via DevTools that after
   ~400 ms, the selected row has `pointer-events: none` (NOT `pointer-events: ''`).
   The sweep set it to `none`; the timeout must not clear it.
2. Start a new CQ session. In the next WaitAnswer, double-clicking in the area
   occupied by old (grey) rows must not fire any `POST /api/v1/tx/select-responder`
   request. Teal rows above the grey area fire normally.
3. Abandon a session via Stop CQ and start a new one. Confirm that clickable
   decode-responder rows are ONLY the ones created during the current WaitAnswer —
   not rows from previous sessions.
4. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
5. Full test suite — 0 failures (pure front-end change).

---

## 5. References

- Session `openswfz-20260626T183541Z.log` lines 239–253 (session 1 select PD3QA),
  lines 410–428 (session 2 ghost PD3QA re-engaged), lines 1481–1498 (session 3 same)
- `web/js/main.js` — `handleDecodes` function, `isResponderRow` block, `setTimeout`
- D-CALLER-005 sweep — `renderTxPanel`, prevState === 'WaitAnswer' sweep block
- D-CALLER-006 (separate handoff) — partner re-selection; different defect, different fix
