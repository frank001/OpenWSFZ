# Handoff: Revert Enable TX hide (§3.6.2 of caller-cq-stop)

**Date:** 2026-06-26  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action  
**Reverts:** commit `045d41d` — "fix(caller-ux): FR-CQ-STOP-001 §3.6.2 — hide Enable TX during caller session"

---

## 1. Context

The QA engineer specified `txEnableBtnEl.hidden = (currentTxRole === 'caller')` as a fix
for the Enable TX re-arm loop.  The condition is wrong: it hides the button whenever the
daemon role is 'caller', including when sitting at Idle on page load — before any CQ
session has started.  The button disappears immediately and does not come back until the
role reverts to answerer.  The Captain cannot work without visible controls.

The hiding approach is the wrong remedy.  Enable TX is confusing during an active caller
session (WS events re-arm it because `autoAnswerEnabled: true` is hardcoded), but that
confusion is tolerable now that the **Stop CQ** button exists as the correct caller
control.  Removing a button is worse than a confusing button.

The fix: delete the hidden line entirely.  No replacement.

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch.

---

## 3. Actions

### 3.1 — `web/js/main.js`: Remove the `hidden` assignment and its comment block

In `renderTxPanel`, inside the Enable TX block (currently around line 204), delete the
8 lines that were added in `045d41d`:

```javascript
    // FR-CQ-STOP-001: Hide Enable TX in caller mode.
    // The caller service always publishes autoAnswerEnabled=true; showing this button
    // armed during a CQ session creates an unbreakable re-arm loop — the operator
    // clicks disarm, the response briefly shows disarmed, then the next WS txState
    // event re-arms it.  Enable TX is an answerer concept; hide it in caller mode.
    // It reappears correctly when the role reverts to Answerer after the session ends.
    txEnableBtnEl.hidden = (currentTxRole === 'caller');

```

After deletion, the Enable TX block should read exactly as it did after `82c5324`:

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

No other files are touched.

---

## 4. Acceptance criteria

1. On page load — Enable TX button is visible regardless of configured role or state.
2. During an active caller CQ session — Enable TX button remains visible.
3. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
4. Full test suite — 0 failures (pure front-end change; no C# tests affected).

---

## 5. References

- Commit `045d41d` — the commit being reverted
- Commit `82c5324` — the prior good state; Enable TX block should match this exactly
- `web/js/main.js` line 202 — Enable TX block location
