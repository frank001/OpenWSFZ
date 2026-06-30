# Handoff: Caller UX fixes — D-CALLER-004/005 + FR-TX-UI-004 + FR-WF-001

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action
**Session log:** `logs/openswfz-20260626T145015Z.log`

---

## 1. Context

Four issues identified during manual testing of the QSO Caller role
(`feat/qso-caller`, `f92d062`).  Two are defects in the caller state
machine and decode table; two are UX improvements requested by the
Captain.

---

## 2. Branch

`fix/caller-ux-fixes` — new branch from `main`.

---

## 3. Actions

### 3.1 — D-CALLER-004: None-mode retries CQ after a single silent
inter-cycle even when a responder was seen the preceding decode cycle

**File:** `src/OpenWSFZ.Daemon/QsoCallerService.cs`

**Root cause:**  
In `HandleWaitAnswerAsync`, when `CallerPartnerSelect == None` and a
responder is found, the method returns early without refreshing
`_skipNextRetry`.  In normal FT8 half-duplex the remote station
transmits only on alternating 15-second slots, so the cycle
immediately following a visible response is always silent.  Since
`_skipNextRetry` is already consumed (by the silent slot immediately
after entering `WaitAnswer`), that second silent slot immediately
triggers `RetryOrAbortAsync` — never giving the operator time to
double-click.

**Evidence from log:**
```
16:51:15.559  TryParseResponder match=true (PD2FZ/P PD2FZ +33) → hold
16:51:30.089  Cycle 14:51:15 silent
16:51:30.126  no response to CQ (retry 1/200) — retransmitting CQ  ← premature
16:52:15.559  TryParseResponder match=true → hold again
16:52:30.133  no response to CQ (retry 2/200)                      ← premature again
```

**Fix — one line change (lines 515–522):**

Current:
```csharp
if (tx.CallerPartnerSelect == CallerPartnerSelectMode.None)
{
    foreach (var r in batch.Results)
    {
        if (TryParseResponder(r.Message, ours, out _, out _, _logger))
            return; // responses present — hold in WaitAnswer
    }
}
```

Replace with:
```csharp
if (tx.CallerPartnerSelect == CallerPartnerSelectMode.None)
{
    foreach (var r in batch.Results)
    {
        if (TryParseResponder(r.Message, ours, out _, out _, _logger))
        {
            _skipNextRetry = true; // re-arm for the expected silent inter-cycle
            return;                // responses present — hold in WaitAnswer
        }
    }
}
```

**Why this is correct:**  
When a response appears in cycle N, `_skipNextRetry = true` is set.
Cycle N+1 (the expected silent A-slot) is skipped.  If cycle N+2 is
also silent (remote station has abandoned the response), `_skipNextRetry`
is now false and the retry fires correctly.  The result is that the
operator can take one full FT8 period (two cycles, 30 s) to double-click
rather than having roughly 5 s before the CQ retransmits.

---

### 3.2 — D-CALLER-005: Old `decode-responder` rows remain clickable after
a new decode cycle arrives; operator can accidentally double-click a
superseded row

**File:** `web/js/main.js`

**Root cause:**  
`handleDecodes` attaches click handlers and the `decode-responder` class
at row creation time and never removes them.  When WSJT-X changes its
transmitted callsign between cycles (e.g. `PD3QA` → `PD2FZ`), both
rows are simultaneously visible in the decode table, both teal,
both clickable.  A misclick on the older row sends the wrong callsign
to `/api/v1/tx/select-responder`.

**Evidence from log:**
```
16:53:15  PD2FZ/P PD3QA +33  decoded  → row built, click handler for 'PD3QA'
16:53:45  PD2FZ/P PD2FZ +33  decoded  → row built, click handler for 'PD2FZ'
16:53:49  POST /api/v1/tx/select-responder → 'PD3QA' sent
           ↑ Captain intended to click the PD2FZ row
```

**Fix — add a sweep at the top of `handleDecodes` (after the `if (!results…)` guard):**

```javascript
function handleDecodes(results) {
  if (!results || results.length === 0) return;

  // Deactivate any decode-responder rows from previous cycles.
  // Only rows produced by this call should be clickable.
  // The selectInFlight guard inside the handler is belt-and-suspenders;
  // pointer-events:none is the visual+behavioural fix for old rows.
  decodesBody.querySelectorAll('tr.decode-responder').forEach(oldRow => {
    oldRow.classList.remove('decode-responder');
    oldRow.style.cursor       = '';
    oldRow.style.pointerEvents = 'none';
  });

  // ... remainder of function unchanged ...
```

Insert the sweep block immediately after the existing placeholder-removal
block (currently line 311–312), before the `for (const r of results)`
loop.

---

### 3.3 — FR-TX-UI-004: TX "Enable TX" button must visually distinguish
"armed but idle" from "actively transmitting"

**Files:** `web/js/main.js`, `web/css/app.css`

**Problem:**  
The `tx-btn-armed` class makes the Enable TX button uniformly red when
TX is enabled.  When the application is actively keying (sending audio)
there is no additional visual signal — the button looks identical to
the armed-but-waiting state.  The Captain cannot see at a glance whether
the radio is on-air.

**Specification:**
- **Armed, not transmitting:** Dark/muted red (background `#6b1515`,
  border `#8b2020`) — "ready, standing by"
- **Actively transmitting (any `Tx…` state):** Bright red
  (`--color-danger`, `#f85149`) — "on air right now"

The transmitting states (all begin with `Tx`) are:
`TxAnswer`, `TxReport`, `Tx73` — these cover both the answerer and
caller roles as currently mapped through `QsoState`.

**Fix A — `app.css` (replace existing `tx-btn-armed` block, add new `tx-btn-transmitting` block):**

Current (around line 207):
```css
#tx-enable-btn.tx-btn-armed {
  background: var(--color-danger);
  border-color: var(--color-danger);
  color: #fff;
  font-weight: 700;
}
#tx-enable-btn.tx-btn-armed:hover:not(:disabled) {
  background: #da3b36;
  border-color: #da3b36;
}
```

Replace with:
```css
/* Armed — dark red: TX enabled, not currently transmitting */
#tx-enable-btn.tx-btn-armed {
  background:   #6b1515;
  border-color: #8b2020;
  color:        #fff;
  font-weight:  700;
}
#tx-enable-btn.tx-btn-armed:hover:not(:disabled) {
  background:   #7d1a1a;
  border-color: #a02828;
}

/* Transmitting — bright red: radio is currently on air */
#tx-enable-btn.tx-btn-transmitting {
  background:   var(--color-danger);
  border-color: var(--color-danger);
  color:        #fff;
  font-weight:  700;
}
#tx-enable-btn.tx-btn-transmitting:hover:not(:disabled) {
  background:   #da3b36;
  border-color: #da3b36;
}
```

**Fix B — `main.js`, inside `renderTxPanel` (after the existing
`tx-btn-armed` add/remove block, around line 207):**

Add these lines immediately after the `txEnableBtnEl.classList.remove('tx-btn-armed')` / `.add('tx-btn-armed')` block:

```javascript
  // FR-TX-UI-004: bright red when actively transmitting, dark red when armed-idle.
  if (autoAnswerEnabled && state.startsWith('Tx')) {
    txEnableBtnEl.classList.add('tx-btn-transmitting');
  } else {
    txEnableBtnEl.classList.remove('tx-btn-transmitting');
  }
```

The `state.startsWith('Tx')` predicate is reliable: `TxAnswer`,
`TxReport`, and `Tx73` are the only transmitting states and all begin
with `Tx`; `Idle`, `WaitAnswer`, `WaitReport`, `WaitRr73`,
`QsoComplete` do not.

---

### 3.4 — FR-WF-001: Waterfall frequency clicks must require Ctrl key to
prevent accidental RX/TX changes

**File:** `web/js/main.js`

**Problem:**  
Any click on the waterfall immediately repositions RX or TX cursors and
POSTs the new audio offset to the daemon.  An accidental click during
a QSO silently retuned the station.

**Specification:**

| Gesture (current) | New gesture | Effect |
|---|---|---|
| Left-click | Ctrl+left-click | Set RX frequency |
| Shift+left-click | Ctrl+Shift+left-click | Set RX and TX to same frequency |
| Right-click | Ctrl+right-click | Set TX frequency |
| *(bare click)* | Left/right-click without Ctrl | No-op (ignore) |

**Fix — add a `ctrlKey` guard at the top of each handler
(around lines 897–916):**

Current left-click handler:
```javascript
canvas.addEventListener('click', (e) => {
  const hz = freqFromEvent(e);
  if (e.shiftKey) {
    applyAudioOffset(hz, hz, holdTxFreqEl?.checked ?? false);
    postAudioOffsetSilently(hz, hz, holdTxFreqEl?.checked ?? false);
  } else {
    applyAudioOffset(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
    postAudioOffsetSilently(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
  }
});
```

Replace with:
```javascript
canvas.addEventListener('click', (e) => {
  if (!e.ctrlKey) return;          // FR-WF-001: Ctrl required to prevent accidental retune
  const hz = freqFromEvent(e);
  if (e.shiftKey) {
    applyAudioOffset(hz, hz, holdTxFreqEl?.checked ?? false);
    postAudioOffsetSilently(hz, hz, holdTxFreqEl?.checked ?? false);
  } else {
    applyAudioOffset(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
    postAudioOffsetSilently(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
  }
});
```

Current right-click handler:
```javascript
canvas.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  const hz = freqFromEvent(e);
  applyAudioOffset(currentRxHz, hz, holdTxFreqEl?.checked ?? false);
  postAudioOffsetSilently(currentRxHz, hz, holdTxFreqEl?.checked ?? false);
});
```

Replace with:
```javascript
canvas.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  if (!e.ctrlKey) return;          // FR-WF-001: Ctrl required to prevent accidental retune
  const hz = freqFromEvent(e);
  applyAudioOffset(currentRxHz, hz, holdTxFreqEl?.checked ?? false);
  postAudioOffsetSilently(currentRxHz, hz, holdTxFreqEl?.checked ?? false);
});
```

Note: `e.preventDefault()` must remain **before** the `ctrlKey` guard
so the browser context menu is always suppressed on a right-click on
the canvas, regardless of modifier state.

---

## 4. Acceptance criteria

QA will verify the following before approving merge:

### D-CALLER-004
1. In Caller role, `CallerPartnerSelect = None`, with a remote station
   sending a response on alternating cycles: the service holds in
   `WaitAnswer` through at least two consecutive response/silence cycles
   without retransmitting CQ.
2. If the remote station stops responding for two consecutive cycles,
   the service retransmits CQ as normal.
3. Existing D-CALLER-003 (None-mode hold guard on silence) still passes.
4. No regression in `QsoCallerServiceTests` — all tests green.

### D-CALLER-005
1. After a new decode cycle arrives, rows from previous cycles no longer
   carry the `decode-responder` class and are not clickable
   (`pointer-events: none`).
2. Double-clicking any row from the current cycle sends the correct
   responder callsign (the second space-delimited token of that row's
   message).
3. Rows that lost `decode-responder` still retain `decode-partner`
   (red background) if applicable — the sweep only removes the
   responder class.

### FR-TX-UI-004
1. Button shows dark red (`#6b1515` background) when TX is armed
   (`autoAnswerEnabled = true`) but the state is `Idle`, `WaitAnswer`,
   `WaitReport`, or `WaitRr73`.
2. Button shows bright red (`#f85149`, `--color-danger`) when the state
   is `TxAnswer`, `TxReport`, or `Tx73`.
3. Button reverts to standard styling when TX is disarmed.
4. No change to button text ("Enable TX" / armed label behaviour per
   D-TX-UI-002).

### FR-WF-001
1. A plain left-click on the waterfall does not change RX or TX
   frequency and does not POST to `/api/v1/audio-offset`.
2. Ctrl+left-click sets RX as before.
3. Ctrl+Shift+left-click sets both RX and TX as before.
4. A plain right-click on the waterfall does not change TX frequency.
5. Ctrl+right-click sets TX as before.
6. A plain right-click still suppresses the browser context menu (the
   `e.preventDefault()` fires regardless of Ctrl state).

### General
7. `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
8. Full test suite (675 tests) — 0 failures.

---

## 5. References

- Session log: `logs/openswfz-20260626T145015Z.log`
- `feat/qso-caller` merge: `f92d062` (2026-06-26)
- `QsoCallerService.cs` — `HandleWaitAnswerAsync` None-mode block
  (lines 515–527)
- `main.js` — `handleDecodes` row builder (lines 307–440)
- `main.js` — `renderTxPanel` (lines 189–237)
- `main.js` — waterfall click handlers (lines 896–916)
- `app.css` — `tx-btn-armed` block (line 207)
- D-TX-UI-002 (resolved): "Enable TX" label fixed; armed state uses
  red background. This change refines that: armed-idle is dark red,
  transmitting is bright red.
