# Handoff: FR-WF-001 hint-text correction + Call CQ button role colours

**Date:** 2026-06-26  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action

---

## 1. Context

Two items arising from Captain's live-session feedback (`openswfz-20260626T152226Z.log`)
following successful UAT of `fix/caller-ux-fixes`:

1. **FR-WF-001 hint-text omission (mandatory pre-merge correction)** — The waterfall
   gesture hint in `index.html` still reads the old text.  Waterfall clicks now require
   Ctrl (FR-WF-001, `722115b`) but the hint does not mention it, actively misleading users.

2. **FR-CQ-COLOUR-001 (new UX requirement)** — The Call CQ button shall use colour to
   communicate the current caller role/state:

   | Button colour | Condition |
   |---|---|
   | Bright green (`var(--color-success)`, `#3fb950`) | Role = caller AND state = `"TxAnswer"` (i.e. `CallerState.TxCq` — radio is on air calling CQ) |
   | Dark green (`#1b4d26` / `#266636`) | Role = caller AND state ≠ `"Idle"` AND state ≠ `"TxAnswer"` (QSO in progress: WaitReport, TxReport, WaitRr73, Tx73, QsoComplete) |
   | Default (no modifier class) | Role = answerer, OR state = `"Idle"` |

   Note: `CallerState` is an internal enum; the JS receives `QsoState` strings from the
   daemon.  The mapping `TxCq → "TxAnswer"` is in `QsoCallerService.State` (line 156).

---

## 2. Branch

`fix/caller-ux-fixes` — amend the existing branch (do NOT open a new branch).
Both fixes are small and belong in the same PR.

---

## 3. Actions

### 3.1 — FR-WF-001: update waterfall gesture hint (`web/index.html:60`)

**Current:**
```html
<span class="freq-readout-hint">Left-click: RX &middot; Right-click: TX &middot; Shift+click: both</span>
```

**Replace with:**
```html
<span class="freq-readout-hint">Ctrl+click: RX &middot; Ctrl+right-click: TX &middot; Ctrl+Shift+click: both</span>
```

One line change only.

---

### 3.2 — FR-CQ-COLOUR-001: CSS — add Call CQ button state classes (`web/css/app.css`)

Insert immediately after the existing `tx-btn-transmitting` block (after line 231):

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
  opacity: 1;   /* override the default disabled dimming so the colour reads clearly */
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

### 3.3 — FR-CQ-COLOUR-001: JS — apply/remove classes in `renderTxPanel` (`web/js/main.js`)

Locate the Call CQ button block (currently lines 216–220):

```javascript
  // ── Call CQ button — enabled only when Idle ───────────────────────────
  // Spec (task 11.8): enabled when currentTxState === 'Idle'; disabled otherwise.
  if (txCallCqBtnEl) {
    txCallCqBtnEl.disabled = (state !== 'Idle');
  }
```

Replace with:

```javascript
  // ── Call CQ button — enabled only when Idle; role-state colour feedback ──
  // Spec (task 11.8): enabled when currentTxState === 'Idle'; disabled otherwise.
  // FR-CQ-COLOUR-001: bright green = actively calling CQ (TxAnswer while role=caller);
  //   dark green = QSO in progress (any non-Idle caller state that is not TxAnswer);
  //   default = answerer mode or Idle.
  if (txCallCqBtnEl) {
    txCallCqBtnEl.disabled = (state !== 'Idle');

    const effectiveRole = role ?? currentTxRole;
    const isCalling     = effectiveRole === 'caller' && state === 'TxAnswer';
    const inProgress    = effectiveRole === 'caller' && state !== 'Idle' && state !== 'TxAnswer';

    txCallCqBtnEl.classList.toggle('cq-btn-calling',     isCalling);
    txCallCqBtnEl.classList.toggle('cq-btn-in-progress', inProgress);
  }
```

`classList.toggle(name, force)` is available in all evergreen browsers and is cleaner
than separate add/remove calls.  The `effectiveRole` local mirrors the existing pattern
used at line 132 (`renderMessageRows`).

---

## 4. Acceptance criteria

QA will verify the following before approving merge:

### FR-WF-001 hint text
1. The waterfall hint reads: `Ctrl+click: RX · Ctrl+right-click: TX · Ctrl+Shift+click: both`
2. No other instance of the old hint text exists in `web/`.

### FR-CQ-COLOUR-001
3. With TX disabled (or role = answerer): Call CQ button shows no colour modifier — default button appearance.
4. Immediately after clicking Call CQ (state transitions to `TxAnswer`, role = `caller`): button shows bright green (`#3fb950` background). Button is disabled at this point; the `opacity: 1` override ensures the colour is not dimmed by the browser.
5. Once a partner responds and a QSO is in progress (state = `WaitReport` / `TxReport` / `WaitRr73` / `Tx73`): button shows dark green (`#1b4d26` background). Still disabled; same opacity override applies.
6. On QSO complete / abort → state returns to `Idle`: button reverts to default appearance and becomes enabled again.
7. Pressing Abort TX mid-QSO: state returns to `Idle`; button reverts to default appearance.
8. Role = answerer throughout an answered QSO: Call CQ button remains default at all times.

### General
9. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
10. Full test suite — 0 failures (these are pure front-end changes; no C# tests expected).

---

## 5. References

- Captain's session feedback: `openswfz-20260626T152226Z.log` (live QSO session)
- `QsoCallerService.cs:153–162` — `CallerState` → `QsoState` mapping (reason `"TxAnswer"` is the correct JS string for the CQ-transmitting phase)
- `web/index.html:60` — hint text to update
- `web/css/app.css:207–231` — existing `tx-btn-armed` / `tx-btn-transmitting` pattern to follow
- `web/js/main.js:216–220` — Call CQ button enable/disable block to extend
- `web/js/main.js:132` — `effectiveRole` pattern already in codebase
- FR-TX-UI-004 (this PR) — precedent for layered button-state CSS classes on TX panel buttons
