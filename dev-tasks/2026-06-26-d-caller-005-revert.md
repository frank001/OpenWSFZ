# Handoff: D-CALLER-005 design correction

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action
**Supersedes:** Section 3.2 of `2026-06-26-caller-ux-fixes.md`

---

## 1. Context

The D-CALLER-005 fix in `722115b` sweeps all `decode-responder` rows every time
a new decode cycle arrives (`handleDecodes`).  The intent was to prevent the
operator accidentally clicking a stale row — but in practice it removed
operator agency entirely: the click window for any given responder is limited
to roughly one 15-second FT8 cycle.

**Captain's ruling:** the operator is in command.  If they choose to work a
station decoded in an earlier cycle, the application must honour that click
at any time while the service is in `WaitAnswer`.  The per-cycle sweep is the
wrong design.

**Evidence from session `openswfz-20260626T170019Z.log`:**
```
19:03:30  PD2FZ/P PD3QA +38 decoded  → PD3QA row teal, clickable
19:04:00  PD2FZ/P PD2FZ +38 decoded  → D-CALLER-005 sweeps PD3QA row (pointer-events:none)
          Captain double-clicks PD3QA — silently rejected.
```

The operator intended to work PD3QA.  The application refused.

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch.  These changes belong in
the same PR as `722115b`.

---

## 3. Actions

### 3.1 — `web/js/main.js`: Remove the per-cycle sweep from `handleDecodes`

Remove the D-CALLER-005 block that was added in `722115b` (currently
lines 321–329):

```javascript
  // D-CALLER-005: Deactivate decode-responder rows from previous cycles.
  // Only rows produced by this call (below) should be clickable.
  // pointer-events:none is the visual+behavioural fix; the selectInFlight guard
  // inside each click handler is belt-and-suspenders.
  decodesBody.querySelectorAll('tr.decode-responder').forEach(oldRow => {
    oldRow.classList.remove('decode-responder');
    oldRow.style.cursor       = '';
    oldRow.style.pointerEvents = 'none';
  });
```

Delete those 9 lines entirely.  The placeholder-removal block immediately above
and the `// Prepend newest rows` comment below should remain untouched.

---

### 3.2 — `web/js/main.js`: Add sweep in `renderTxPanel` when leaving `WaitAnswer`

`renderTxPanel` is the single point where state transitions are applied to the
UI.  When the state transitions OUT of `WaitAnswer` (partner selected, QSO
complete, operator abort), all `decode-responder` rows must be deactivated
because they are no longer relevant.

**Change — inside `renderTxPanel` (currently line 189), capture the previous
state before it is overwritten, then add a sweep block near the end of the
function:**

```javascript
function renderTxPanel(state, partner, autoAnswerEnabled, role) {
  // Capture previous state before overwriting — used below to detect
  // WaitAnswer exit and sweep stale responder rows.
  const prevState = currentTxState;

  // Persist for subsequent partial updates (e.g. WS txState without config change).
  currentTxState           = state;
  // ... rest of function unchanged ...
```

Then, at the **end** of `renderTxPanel` (after `renderMessageRows`), add:

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

`decodesBody` is already a module-level constant (line 291) — no import needed.

---

## 4. Acceptance criteria

### D-CALLER-005 (corrected)

1. While the service is in `WaitAnswer` (None mode), ALL `decode-responder`
   rows from all previous decode cycles remain teal and clickable.
2. Clicking a row from any cycle — including one decoded 2+ minutes ago —
   sends the correct responder callsign to
   `POST /api/v1/tx/select-responder` and the service engages.
3. When the state transitions out of `WaitAnswer` (partner selected, abort,
   QSO complete), all `decode-responder` rows are deactivated
   (`pointer-events: none`, teal class removed) within the same render cycle.
4. D-CALLER-004 is unaffected: the service continues to hold in
   `WaitAnswer` through silent inter-cycles without retransmitting CQ.

### General

5. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
6. Full test suite — 0 failures (pure front-end change; no C# tests expected).

---

## 5. References

- Session `openswfz-20260626T170019Z.log` — PD3QA click blocked at 19:04:xx
- `722115b` — original (incorrect) D-CALLER-005 sweep implementation
- `2026-06-26-caller-ux-fixes.md` §3.2 — superseded
- `web/js/main.js:191` — `currentTxState = state` (capture prev before this line)
- `web/js/main.js:243` — `renderMessageRows(...)` (add sweep after this call)
- `web/js/main.js:314` — `handleDecodes` (remove the sweep block from here)
- `web/js/main.js:291` — `decodesBody` constant (already in scope)
