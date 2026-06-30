# Handoff: D-CALLER-010 — Remove D-CALLER-005; promote abort-and-recq to double-click

**Date:** 2026-06-27
**Prepared by:** QA engineer
**Status:** Awaiting developer action
**Defect ID:** D-CALLER-010
**Severity:** High — the "switch to another answerer while QSO is in progress" feature
(D-CALLER-006 + D-CALLER-009) is inoperable in any scenario where no fresh FT8
decode arrives during TxReport/WaitRr73.

---

## 1. Context

D-CALLER-006 added abort-and-recq behaviour when the operator clicks a teal
responder row during TxReport or WaitRr73.  D-CALLER-009 fixed the race between
`postTxAbort()` returning and `SafeAbortToIdleAsync` completing on the background
thread.

Both fixes are correct.  The missing piece is **D-CALLER-005**, which sweeps
every `decode-responder` row the moment WaitAnswer exits to TxReport:

```javascript
// lines 270–279 in main.js (current)
if (prevState === 'WaitAnswer' && state !== 'WaitAnswer') {
  decodesBody.querySelectorAll('tr.decode-responder').forEach(row => {
    row.classList.remove('decode-responder');
    row.style.cursor       = '';
    row.style.pointerEvents = 'none';
  });
}
```

This sweep runs at the instant the operator commits to a partner.  The teal rows
for every *other* caller (e.g. PD3QA, who also responded to the CQ) immediately
lose the `decode-responder` class and gain `pointer-events: none`.

D-CALLER-006 then has nothing to offer:

- **In a test environment** (single simulated responder, silence guard fires on
  TX cycles): no fresh decodes arrive during TxReport/WaitRr73 → no new teal rows
  → the else-branch in the click handler is unreachable.
- **In a real low-traffic pileup**: the same situation applies unless another
  station happens to transmit *and be decoded* during the operator's TX window.

The fix has two parts:

1. **Remove D-CALLER-005** entirely.  D-CALLER-008 (WaitAnswer entry sweep)
   already handles cleanup when a new WaitAnswer begins.  The WaitAnswer-era rows
   can safely persist through TxReport and WaitRr73 — they are stale only in the
   `responseCycleStartUtc` sense, which is irrelevant in the abort-and-recq path.

2. **Promote the abort-and-recq action from single-click to double-click.**
   The Captain's requirement: a deliberate double-click on a teal row during
   TxReport/WaitRr73 aborts the current QSO and re-arms the CQ cycle.  Single-
   click in those states does nothing (silent guard), so an accidental touch cannot
   abort a QSO in progress.  The operator is in full control; no confirmation
   dialog is needed.

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch.  Pure front-end change.

---

## 3. Actions

All edits are in `web/js/main.js` only.

---

### 3.1 — Remove D-CALLER-005 from `renderTxPanel`

**Location:** lines 270–279 (the block immediately after `renderMessageRows`).

**Remove** the entire block:

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

After removal, the D-CALLER-008 block (currently lines 281–292) immediately
follows `renderMessageRows`.  No other change is needed in `renderTxPanel`.

---

### 3.2 — Split the row event handler: `click` (WaitAnswer) + `dblclick` (TxReport/WaitRr73)

**Location:** lines 459–518 — the `let selectInFlight … tr.addEventListener('click' …` block inside the `if (isResponderRow)` branch.

**Replace** the entire block (lines 459–518) with:

```javascript
      let selectInFlight = false;

      // ── Single-click: WaitAnswer only — select this responder ────────────
      // D-CALLER-010: return immediately when not in WaitAnswer so that an
      // accidental tap on a teal row during TxReport/WaitRr73 is a no-op.
      // The operator uses double-click (dblclick handler below) to abort.
      tr.addEventListener('click', async () => {
        if (currentTxState !== 'WaitAnswer') return;
        if (selectInFlight) return;
        selectInFlight = true;
        tr.style.pointerEvents = 'none';

        const responderCallsign     = msgTokens[1];
        const responseCycleStartUtc = tr.dataset.cqCycleStartUtc;

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
            // D-CALLER-007 / D-CALLER-010: only restore pointer-events if
            // this row is still an active decode-responder.  D-CALLER-008
            // may have swept it (class removed, pointer-events: none) while
            // the 400 ms timer was running.
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
      });

      // ── Double-click: TxReport / WaitRr73 — abort and re-arm CQ ─────────
      // D-CALLER-010: WaitAnswer rows remain teal into TxReport/WaitRr73
      // (D-CALLER-005 removed).  The operator double-clicks another caller
      // to abort the current QSO immediately and restart the CQ cycle.
      // D-CALLER-009 deferred rearm ensures postTxCallCq fires only after
      // the daemon confirms state: Idle, role: answerer via the WS event.
      tr.addEventListener('dblclick', async () => {
        if (currentTxState !== 'TxReport' && currentTxState !== 'WaitRr73') return;
        if (selectInFlight) return;
        selectInFlight = true;
        tr.style.pointerEvents = 'none';

        try {
          await postTxAbort();
          pendingRearmAfterAbort = true;
        } catch (err) {
          selectInFlight = false;
          tr.style.pointerEvents = 'none'; // keep deactivated on error
          console.error('D-CALLER-010 abort-and-recq failed:', err);
        }
        // selectInFlight and pointerEvents are NOT restored on success —
        // this row's lifecycle ends here; the operator double-clicks a
        // fresh row in the new WaitAnswer.
      });
```

---

## 4. Acceptance criteria

### AC-1 — WaitAnswer rows survive into TxReport/WaitRr73

After selecting a partner (e.g. PD2FZ) in None mode, confirm in the browser
DevTools Elements panel that the **other** teal rows (e.g. PD3QA) still carry the
`decode-responder` class and do **not** have `pointer-events: none`.  The
D-CALLER-005 sweep no longer fires.

### AC-2 — Single-click during TxReport/WaitRr73 is a no-op

While in TxReport or WaitRr73, single-click a teal row.  Confirm:
- No network request fires in the DevTools Network tab.
- No console error.
- No state change on the daemon side.

### AC-3 — Double-click during TxReport triggers abort-and-recq (happy path)

While in TxReport (None mode, caller role), **double-click** a teal responder row.
Confirm in the Network tab:
- `POST /api/v1/tx/abort` → 200.
- `POST /api/v1/tx/call-cq` fires within ~50 ms of the WS `txState` event
  delivering `state: 'Idle'` → returns 200 (not 409).
- Daemon log shows `QsoCallerService: state → "TxCq"` and TX fires the new CQ
  without operator intervention.

### AC-4 — Double-click during WaitRr73 triggers abort-and-recq

Repeat AC-3 with the service in `WaitRr73` instead of `TxReport`.

### AC-5 — Double-click in WaitAnswer fires select-responder (once)

In WaitAnswer, double-click a teal row.
- The first click fires `postTxSelectResponder` → `selectInFlight = true`.
- The second click and the `dblclick` event are both blocked by `selectInFlight`.
- Confirm in the Network tab: exactly **one** `POST /api/v1/tx/select-responder`.

### AC-6 — Abort TX still clears the pending rearm flag (D-CALLER-009 regression)

While `pendingRearmAfterAbort` would be set (i.e., after a double-click abort-and-
recq but before the WS Idle event), click the **Abort TX** button.  Confirm no
`POST /api/v1/tx/call-cq` fires after the WS Idle event arrives.

### AC-7 — Stop CQ still clears the pending rearm flag (D-CALLER-009 regression)

Same scenario — click **Stop CQ** instead of **Abort TX**.  Confirm no automatic
call-cq fires when the daemon delivers Idle.

### AC-8 — D-CALLER-008 sweep still fires on new WaitAnswer

After the abort-and-recq, when the new WaitAnswer begins, confirm in DevTools
Elements that all old teal rows have had `decode-responder` removed and
`pointer-events: none` applied.

### AC-9 — Build and tests

```
dotnet build OpenWSFZ.slnx -c Release   # 0 errors, 0 warnings
dotnet test                              # 0 failures
```

(Pure front-end change; no C# tests affected.)

---

## 5. References

- `web/js/main.js` lines 270–279 — D-CALLER-005 block to remove
- `web/js/main.js` lines 459–518 — click handler block to replace
- `web/js/main.js` lines 281–292 — D-CALLER-008 sweep (unchanged)
- `web/js/main.js` lines 1168–1178 — D-CALLER-009 WS txState rearm (unchanged)
- `web/js/main.js` lines 840–843 — Abort TX clears flag (unchanged)
- `web/js/main.js` lines 871–874 — Stop CQ clears flag (unchanged)
- `aea1081` — D-CALLER-006 (original abort-and-recq, now superseded by dblclick)
- `c4bc017` — D-CALLER-008 (WaitAnswer entry sweep; remains in force)
- `c9e014c` — D-CALLER-009 (deferred rearm; remains in force)
- Log `logs/openswfz-20260627T101518Z.log` — evidence run showing D-CALLER-005
  deactivating PD3QA row before operator can use it during WaitRr73
