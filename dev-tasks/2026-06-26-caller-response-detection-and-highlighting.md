# Handoff: Two caller defects — response detection and partner highlighting

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action

---

## 1. Context

Found during live QSO testing of the `feat/qso-caller` branch immediately after
merging the state-machine bug fixes (`ee4a742`).  Two independent defects:

- **D-CALLER-001** — `TryParseResponder` rejects a valid class of CQ responses:
  signal reports (`+NN`, `-NN`) as the third token.  This caused the first CQ
  session (log 13:57–13:58) to silently miss `PD2FZ/P PD2FZ +32` responses in
  cycles 11:57:30 and 11:58:00, forcing the operator to abort and retry.

- **D-CALLER-002** — Three categories of decode rows that directly reference the
  caller are NOT highlighted with the `decode-partner` CSS class despite being
  exchanged with/from the active partner:
  1. Rows from the decode batch in which the partner is first identified
     (timing: `txState` WS event fires *after* the `decode` event is rendered).
  2. The final `73` confirmation from the partner, which arrives one cycle after
     QSO completion when `currentTxPartner` has already been cleared to null.

Session log: `logs/openswfz-20260626T115654Z.log`

---

## 2. Branch

`feat/qso-caller` (existing) — add one or more commits directly to this branch.

---

## 3. Actions

### 3.1 — Fix `TryParseResponder`: accept signal reports as third token

**File:** `src/OpenWSFZ.Daemon/QsoCallerService.cs`
**Method:** `TryParseResponder` (~line 938)

**Current (rejects signal reports):**
```csharp
// Third token must look like a Maidenhead grid: 4 chars, first two letters.
var grid = parts[2];
if (grid.Length < 2 || !char.IsLetter(grid[0]) || !char.IsLetter(grid[1]))
    return false;
```

**Correct:**
```csharp
// Third token must be either a Maidenhead grid (first two chars are letters)
// or a signal report (+NN / -NN / R+NN / R-NN).
// Some operators skip the grid-square exchange and respond to a CQ directly
// with a signal report; this is valid FT8 behaviour.
var thirdToken = parts[2];
var isGrid   = thirdToken.Length >= 2
               && char.IsLetter(thirdToken[0])
               && char.IsLetter(thirdToken[1]);
var isReport = IsSignalReport(thirdToken);
if (!isGrid && !isReport)
    return false;
```

`IsSignalReport` is already a static method on `QsoCallerService` — no new
dependency needed.

---

### 3.2 — Regression tests for D-CALLER-001

Add to `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`:

1. **`TryParseResponder_AcceptsPositiveSignalReport`**
   — `TryParseResponder("PD2FZ/P Q1ABC +32", "PD2FZ/P", ...)` → `true`, partner
   `"Q1ABC"`.

2. **`TryParseResponder_AcceptsNegativeSignalReport`**
   — `TryParseResponder("PD2FZ Q1ABC -05", "PD2FZ", ...)` → `true`, partner
   `"Q1ABC"`.

3. **`TryParseResponder_AcceptsRogerSignalReport`**
   — `TryParseResponder("PD2FZ/P Q1ABC R+33", "PD2FZ/P", ...)` → `true`, partner
   `"Q1ABC"`.

4. **`TryParseResponder_Rejects73AsThirdToken`**
   — `TryParseResponder("PD2FZ/P Q1ABC 73", "PD2FZ/P", ...)` → `false`.
   (`73` is a QSO termination token, not a valid CQ response.)

---

### 3.3 — Fix `decode-partner` retroactive scan (D-CALLER-002 gap 1)

**File:** `web/js/main.js`
**Function:** `renderTxPanel` (the function that updates `currentTxPartner`)

When `currentTxPartner` is assigned a new **non-null** value (i.e. the partner
has just been identified), scan all existing `<tr>` elements in the decode table
and retroactively apply `decode-partner` to any row whose token list matches.
This closes the timing gap: the `txState` event arrives fractionally after the
decode batch is rendered, so the batch rows would otherwise be missed.

Suggested implementation pattern (add immediately after `currentTxPartner` is
set to the new partner value):

```javascript
// Retroactive scan: apply decode-partner to rows already in the table that
// match the newly identified partner (handles timing gap vs txState event).
if (partner && partner !== previousPartner) {
  const partnerBase = partner.split('/')[0];
  document.querySelectorAll('#decodes-tbody tr').forEach(row => {
    const tokens = (row.dataset.message ?? '').split(' ');
    const callMatch = tokens.includes(txCallsign)
                   || (txCallsignBase && tokens.includes(txCallsignBase));
    const partMatch = tokens.includes(partner)
                   || tokens.includes(partnerBase);
    if (callMatch && partMatch) {
      row.classList.add('decode-partner');
    }
  });
}
```

Adapt to the actual variable names and the location where `currentTxPartner`
is written in `renderTxPanel`.  Store `previousPartner` before the assignment
to detect genuine changes.

**Prerequisite:** Each `<tr>` in the decode table must carry the decoded message
string in `row.dataset.message` so the scan can tokenise it without re-parsing
the visible cell text.  Verify this attribute is already set in `handleDecodes`;
if not, add `tr.dataset.message = r.message` at row-creation time.

---

### 3.4 — Preserve partner for one cycle after QSO completion (D-CALLER-002 gap 2)

**File:** `web/js/main.js`
**Function:** `renderTxPanel`

After a QSO completes, the `QsoCallerService` broadcasts `QsoComplete` (partner
set) and then immediately `Idle` (partner null).  The partner's `73`
confirmation arrives in the *next* 15-second decode cycle — after `currentTxPartner`
has been cleared.

Fix: do not clear `currentTxPartner` immediately when an `Idle` state event
arrives.  Instead, schedule a clearance after one full FT8 cycle (≈ 16 seconds):

```javascript
// In renderTxPanel, where currentTxPartner is assigned from the partner arg:
if (partner !== null) {
  clearTimeout(_partnerClearTimer);
  _partnerClearTimer = null;
  currentTxPartner = partner;
} else {
  // Delay clearing so the partner's final 73 (arriving in the next cycle)
  // is still highlighted.  16 s ≈ one FT8 cycle with a 1-second margin.
  _partnerClearTimer = setTimeout(() => {
    currentTxPartner = null;
    _partnerClearTimer = null;
  }, 16_000);
}
```

Declare `let _partnerClearTimer = null;` at module level alongside the other
state variables.

Cancel the timer immediately when a *new* non-null partner arrives (the
`clearTimeout` call above handles this).  This ensures back-to-back QSOs
switch partner highlighting immediately without a stale 16-second tail.

---

### 3.5 — No new backend tests required for D-CALLER-002

The highlighting gaps are frontend-only; they do not affect state machine
correctness.  No daemon-level regression tests are required for 3.3/3.4.
The existing `QsoCallerServiceTests` suite is unchanged.

---

## 4. Acceptance criteria

QA will verify the following before approving merge to `main`:

1. **Signal-report response accepted (D-CALLER-001):** With operator callsign
   `PD2FZ/P` and a simulated decode batch containing `"PD2FZ/P Q1ABC +32"` in
   `WaitAnswer` state, `QsoCallerService` transitions to `TxReport` without
   retrying the CQ.  (Verify via unit tests 3.2.1–3.2.3 and/or daemon log.)

2. **`73`-token response still rejected:** `"PD2FZ/P Q1ABC 73"` in `WaitAnswer`
   state does NOT trigger a transition; the service remains in `WaitAnswer`.
   (Unit test 3.2.4.)

3. **Retroactive highlighting (gap 1):** After clicking "Call CQ" and a response
   batch arrives, the response rows in that same batch gain the `decode-partner`
   CSS class within one event-loop tick (observable in browser DevTools →
   Elements panel).

4. **73-confirmation highlighting (gap 2):** After a successful QSO, the final
   `73` response from the partner (arriving in the next 15-second cycle) is
   highlighted with `decode-partner`.  The highlight clears naturally on its own
   within ~16 seconds of that cycle completing, or immediately when the next QSO
   starts.

5. **No stale highlighting between QSOs:** Starting a second CQ session
   immediately after the first clears the previous partner highlight and
   transitions to the new partner without a 16-second overlap on the new
   partner's rows.

6. **Existing tests green:** `dotnet test OpenWSFZ.slnx -c Release` — zero
   failures.

7. **Zero build warnings:** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors,
   0 warnings.

8. **Answerer unaffected:** `QsoAnswererService` is not modified; answerer-mode
   QSO flow is unchanged.

---

## 5. References

- Session log confirming D-CALLER-001 (signal report missed):
  `logs/openswfz-20260626T115654Z.log` — 13:57:27→13:58:27: no match logged
  despite `PD2FZ/P PD2FZ +32` present in cycles 11:57:30 and 11:58:00.
- `QsoCallerService.IsSignalReport` — existing static helper, already handles
  `+NN`, `-NN`, `R+NN`, `R-NN`.
- `QsoCallerService.TryParseResponder` — internal static, ~ line 916 of
  `src/OpenWSFZ.Daemon/QsoCallerService.cs`.
- `handleDecodes` / `decode-partner` logic — `web/js/main.js` ~ line 374.
- `renderTxPanel` — `web/js/main.js` ~ line 182.
- Lesson learned #6 (MEMORY.md) — STJ source-gen and `init` property defaults:
  not directly applicable here but keep in mind for any new DTO fields.
