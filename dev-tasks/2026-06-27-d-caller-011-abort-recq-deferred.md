# Defect Record: D-CALLER-011 — Abort-and-Recq via Double-Click — Deferred

**Date:** 2026-06-27
**Recorded by:** QA engineer
**Status:** DEFERRED
**Severity:** Medium — convenience feature; core caller role (CQ → QSO) is unaffected
**Branch:** `fix/caller-ux-fixes`

---

## 1. Summary

The ability to abort a QSO in progress and immediately re-arm the CQ cycle by
double-clicking a teal responder row (`decode-responder`) during `TxReport` or
`WaitRr73` does **not work in practice**, despite the D-CALLER-010 implementation
being applied at commit `273c195`.

---

## 2. History of attempted fixes

| Commit | Defect | Description |
|---|---|---|
| `aea1081` | D-CALLER-006 | Initial abort-and-recq on single-click during TxReport/WaitRr73 |
| `c9e014c` | D-CALLER-009 | Race fix: deferred rearm via `pendingRearmAfterAbort`; `call-cq` fires only after WS confirms `Idle` |
| `273c195` | D-CALLER-010 | Removed D-CALLER-005 (WaitAnswer→TxReport sweep); promoted abort to double-click; added single-click no-op guard |

All three addressed real and demonstrable issues; none delivered a working
end-to-end abort-and-recq flow as at 2026-06-27.

---

## 3. D-CALLER-010 acceptance criteria — verification status

| AC | Description | Status |
|---|---|---|
| AC-1 | WaitAnswer rows persist into TxReport/WaitRr73 (D-CALLER-005 sweep removed) | **Unknown — not isolated** |
| AC-2 | Single-click during TxReport/WaitRr73 is a no-op | **Unknown — not isolated** |
| AC-3 | Double-click during TxReport fires abort + deferred rearm | **FAIL — end-to-end** |
| AC-4 | Double-click during WaitRr73 fires abort + deferred rearm | **FAIL — end-to-end** |
| AC-5 | Double-click in WaitAnswer fires select-responder exactly once | **Unknown — not isolated** |
| AC-6 | Abort TX button clears `pendingRearmAfterAbort` (D-CALLER-009 regression) | **Unknown** |
| AC-7 | Stop CQ button clears `pendingRearmAfterAbort` (D-CALLER-009 regression) | **Unknown** |
| AC-8 | D-CALLER-008 WaitAnswer entry sweep still fires on new WaitAnswer | **Unknown** |
| AC-9 | Build 0 errors / tests 0 failures | **Likely PASS** (pure JS change) |

---

## 4. Likely failure modes (for next investigator)

The feature depends on a precise sequence of events across three layers:

1. **JS layer** — `dblclick` event fires on a `decode-responder` row while
   `currentTxState` is `TxReport` or `WaitRr73`.
2. **Network** — `POST /api/v1/tx/abort` returns 200.
3. **WebSocket** — daemon delivers `txState` event with `state: 'Idle'`.
4. **JS layer** — `pendingRearmAfterAbort` flag is set; WS handler detects Idle
   and fires `POST /api/v1/tx/call-cq`.

Candidate failure points to investigate with DevTools open (Network + Console + Elements):

- **Are the rows still `decode-responder` at the moment of double-click?**
  If D-CALLER-008 is sweeping too aggressively (e.g., firing on the decode event
  that coincides with TxReport entry), the rows may already be deactivated.
- **Is the `dblclick` event reaching the handler?** Verify with a `console.log`
  at the top of the `dblclick` listener and `currentTxState` value at that moment.
- **Is `postTxAbort()` succeeding?** Check Network tab for 200 vs 4xx.
- **Is the WS `txState` Idle event arriving?** Check WS frame log.
- **Is `pendingRearmAfterAbort` being cleared prematurely?** Check if any
  other code path (state change handler, Stop CQ, Abort TX button) resets the flag
  before the Idle event arrives.
- **Double-click triggering both `click` and `dblclick`?** A `dblclick` always
  fires two `click` events first. The `click` handler returns immediately if
  `currentTxState !== 'WaitAnswer'`, so this should be a no-op, but verify that
  `selectInFlight` is not being set to `true` by the click before `dblclick` fires.

---

## 5. Scope of deferral

This defect defers **only** the abort-and-recq feature. The following items
on the `fix/caller-ux-fixes` branch are independent and are **not** deferred:

- D-CALLER-004 (None-mode retry hold — C# `QsoCallerService.cs`)
- D-CALLER-006 (partner reselect API endpoint)
- D-CALLER-007 (ghost row cleanup)
- D-CALLER-008 (WaitAnswer entry sweep)
- D-CALLER-009 (deferred rearm race — JS `pendingRearmAfterAbort` mechanism)
- FR-TX-UI-004 (Enable TX button armed/transmitting colour distinction)
- FR-WF-001 (Ctrl-guard on waterfall frequency clicks)
- FR-CQ-STOP-001 (Stop CQ / Abort TX button state management)
- FR-CQ-COLOUR-001 (CQ button colour states)

The Captain should decide whether to:
(a) merge `fix/caller-ux-fixes` as-is (D-CALLER-010 commit stays but the feature
    is known-broken and documented here), or
(b) revert `273c195` before merging (removes the dblclick handler; single-click
    abort-and-recq from D-CALLER-006 / `aea1081` would be restored — also broken,
    but less confusingly so).

---

## 6. References

- `273c195` — D-CALLER-010 implementation (currently HEAD of `fix/caller-ux-fixes`)
- `dev-tasks/2026-06-27-d-caller-010-dblclick-abort.md` — full AC list and code spec
- `web/js/main.js` — dblclick handler (around line 456; see `// D-CALLER-010`)
- `web/js/main.js` — WS rearm logic (around line 1168; `pendingRearmAfterAbort`)
