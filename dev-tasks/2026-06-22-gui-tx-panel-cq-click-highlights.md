# Handoff: TX panel — CQ click, CQ highlight, partner highlight

**Date:** 2026-06-22  
**Branch:** `feat/gui-tx-panel` (extend in place — do NOT open a new branch)  
**Change artefact:** `openspec/changes/gui-tx-panel/`  
**QA contact:** QA engineer (current session)

---

## Context

The `feat/gui-tx-panel` branch already carries the TX panel UI and the D-TX-UI-001/002/003
disarm fixes (546 tests green). Before it merges to main, three new requirements have been
approved by the Captain (2026-06-22) and are to land in this same change:

1. **CQ row highlighting** — decode table rows where the message begins with `"CQ "` are
   visually highlighted with a warm accent colour.
2. **Clickable CQ rows** — clicking a CQ row starts an aimed QSO answer (TX-D01). The
   system fires the TX at the next FT8 cycle boundary of the **correct answer phase**
   (opposite to the CQ station's phase), switching phase automatically if needed.
3. **Partner interaction highlighting** — during an active QSO, decode table rows that
   contain BOTH the operator's callsign and the partner's callsign as space-delimited tokens
   are highlighted in subdued red.

Full specifications in:
- `openspec/changes/gui-tx-panel/specs/qso-controller/spec.md` (§ AnswerCqAsync, § POST /api/v1/tx/answer-cq)
- `openspec/changes/gui-tx-panel/specs/web-frontend/spec.md` (§ CQ row highlighting, § Clickable CQ rows, § Partner interaction highlighting)
- `openspec/changes/gui-tx-panel/design.md` (D10, D11, D12)

---

## FT8 Phase Primer (read before implementing)

FT8 cycles start at :00, :15, :30, :45 of each UTC minute. Every station picks one of two
phases and alternates with its partner:

- **A-phase:** cycles starting at :00 and :30 (second-within-minute % 30 == 0)
- **B-phase:** cycles starting at :15 and :45 (second-within-minute % 30 == 15)

If PD2FZ CQs during a B-phase window (:15–:30), the correct answer is transmitted during
the next A-phase window (:30–:45). If the system fires TX during a B-phase window (same
as the CQ), both stations transmit simultaneously — **TX collision, nothing is decoded**.

The click-on-CQ handler must therefore:
1. Know the CQ's cycle start time (from the decode row's timestamp)
2. Derive the required answer phase (opposite of CQ phase)
3. Arm a pending target that only fires when `HandleIdleAsync` runs at the correct phase

---

## Actions

### 1 — Add `AnswerCqAsync` to `IQsoController`

File: `src/OpenWSFZ.Abstractions/IQsoController.cs`

Add:

```csharp
Task AnswerCqAsync(string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct);
```

### 2 — Implement `AnswerCqAsync` in `QsoAnswererService`

File: `src/OpenWSFZ.Daemon/QsoAnswererService.cs`

**New fields (private):**

```csharp
// Pending-target fields — protected by _stateLock (or equivalent sync in this class)
private string?    _pendingTargetCallsign;
private double     _pendingTargetFrequencyHz;
private bool       _pendingTargetIsAPhase;   // true = wait for A-phase (:00/:30); false = B-phase (:15/:45)
private DateTimeOffset _pendingTargetSetAt;
```

**Phase helper (private static):**

```csharp
/// <summary>
/// Returns true if the cycle starting at <paramref name="cycleStart"/> is A-phase (:00 or :30).
/// Returns false for B-phase (:15 or :45).
/// </summary>
private static bool IsAPhase(DateTimeOffset cycleStart)
    => cycleStart.Second % 30 == 0;
```

**`AnswerCqAsync` implementation:**

```csharp
public async Task AnswerCqAsync(
    string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
{
    lock (_stateLock)
    {
        if (_state != QsoState.Idle)
            return;   // HTTP layer already returned 409; this is a safety guard

        // CQ was on phase P → answer on the opposite phase
        bool cqIsAPhase     = IsAPhase(cqCycleStart);
        _pendingTargetCallsign    = callsign;
        _pendingTargetFrequencyHz = frequencyHz;
        _pendingTargetIsAPhase    = !cqIsAPhase;   // opposite phase
        _pendingTargetSetAt       = DateTimeOffset.UtcNow;
    }

    // Arm the system
    try
    {
        var current = _configStore.Current;
        var tx      = current.Tx ?? new TxConfig();
        await _configStore.SaveAsync(
            current with { Tx = tx with { AutoAnswer = true } }, ct)
            .ConfigureAwait(false);
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "AnswerCqAsync: failed to save autoAnswer=true — ignoring.");
    }
}
```

**Update `HandleIdleAsync` — add phase-aware pending-target logic:**

At the START of `HandleIdleAsync`, before the existing CQ-detection logic, add:

```csharp
// --- Phase-aware pending-target handling ---
string?        pendingCallsign;
double         pendingFrequencyHz;
bool           pendingIsAPhase;
DateTimeOffset pendingSetAt;

lock (_stateLock)
{
    pendingCallsign    = _pendingTargetCallsign;
    pendingFrequencyHz = _pendingTargetFrequencyHz;
    pendingIsAPhase    = _pendingTargetIsAPhase;
    pendingSetAt       = _pendingTargetSetAt;
}

if (pendingCallsign is not null)
{
    // Timeout guard: stale pending target (e.g. decode loop stalled)
    if (DateTimeOffset.UtcNow - pendingSetAt > TimeSpan.FromSeconds(60))
    {
        _logger.LogWarning(
            "AnswerCqAsync: pending target '{Callsign}' expired after 60s — discarding.",
            pendingCallsign);
        lock (_stateLock) { _pendingTargetCallsign = null; }
        return;
    }

    // Phase check: only fire on the correct answer phase
    bool currentIsAPhase = IsAPhase(batch.CycleStart);   // batch.CycleStart = UTC cycle boundary
    if (currentIsAPhase != pendingIsAPhase)
    {
        // Wrong phase — skip this cycle, retain pending target
        return;
    }

    // Correct phase — fire TX
    lock (_stateLock) { _pendingTargetCallsign = null; }
    await ExecuteTxAnswerAsync(pendingCallsign, pendingFrequencyHz, ct).ConfigureAwait(false);
    return;
}
// --- End pending-target handling ---

// Existing autoAnswer CQ detection follows here (unchanged) ...
```

`batch.CycleStart` is the UTC timestamp of the cycle boundary the batch belongs to.
Check the existing `DecodeBatch` (or equivalent) type for the correct property name.
If the type does not currently carry this, it will need to be added — see Action 2b below.

**Action 2b — Ensure `DecodeBatch` (or equivalent) carries `CycleStart`:**

The phase check requires knowing the UTC cycle-start time of the current batch. If the
decode batch type already has such a property (e.g. `WindowStart`, `CycleStartUtc`,
`Timestamp`), use it directly. If not, add a `DateTimeOffset CycleStart` property to the
batch type and populate it when the batch is created from the decoded audio window.

**Clear pending target in `SafeAbortToIdleAsync`:**

```csharp
lock (_stateLock)
{
    _pendingTargetCallsign    = null;
    _pendingTargetFrequencyHz = 0.0;
    _pendingTargetIsAPhase    = false;
    _pendingTargetSetAt       = default;
}
```

### 3 — Add `AnswerCqRequest` DTO and source-gen registration

File: `src/OpenWSFZ.Web/AppJsonContext.cs`

Add the record:

```csharp
internal sealed record AnswerCqRequest(
    string Callsign,
    double FrequencyHz,
    string CqCycleStartUtc);    // ISO 8601 UTC, e.g. "2026-06-22T17:29:15Z"
```

Add to the `[JsonSerializable]` attribute list on `AppJsonContext`:

```csharp
[JsonSerializable(typeof(AnswerCqRequest))]
```

### 4 — Add `POST /api/v1/tx/answer-cq` route

File: `src/OpenWSFZ.Web/WebApp.cs`

After the existing `/api/v1/tx/abort` handler:

```csharp
app.MapPost("/api/v1/tx/answer-cq", async (
    IConfigStore store,
    [FromBody] AnswerCqRequest req,
    CancellationToken ct) =>
{
    if (qsoController is null)
        return Results.Problem("TX controller not available.", statusCode: 503);

    if (qsoController.State != QsoState.Idle)
        return Results.Conflict();

    if (!DateTimeOffset.TryParse(
            req.CqCycleStartUtc,
            null,
            System.Globalization.DateTimeStyles.RoundtripKind,
            out var cqCycleStart))
    {
        return Results.BadRequest("cqCycleStartUtc is not a valid ISO 8601 date-time.");
    }

    await qsoController.AnswerCqAsync(req.Callsign, req.FrequencyHz, cqCycleStart, ct);

    var state   = qsoController.State;
    var partner = qsoController.Partner;
    return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: true));
});
```

The double Idle check (HTTP layer + service `AnswerCqAsync`) is intentional. The HTTP
check returns 409 fast; the service check is the authoritative guard against races.

### 5 — `web/js/api.js` — add `postTxAnswerCq`

```javascript
export function postTxAnswerCq(callsign, frequencyHz, cqCycleStartUtc) {
  return fetchJson('/api/v1/tx/answer-cq', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ callsign, frequencyHz, cqCycleStartUtc }),
  });
}
```

Import alongside the other TX functions in `main.js`.

### 6 — `web/js/main.js` — CQ row highlighting + timestamp storage

When a decode row is rendered:

```javascript
// Store the cycle-start UTC string as a data attribute for use in the click handler
row.dataset.cqCycleStartUtc = parseFt8CycleStartUtc(decode.timestamp);

if (decode.message.startsWith('CQ ')) {
  row.classList.add('decode-cq');
}
```

Add the parser function (module scope):

```javascript
function parseFt8CycleStartUtc(ft8Ts) {
  // ft8Ts format: "YYMMDD_HHMMSS" (UTC), e.g. "260622_172915"
  const [date, time] = ft8Ts.split('_');
  return `20${date.slice(0,2)}-${date.slice(2,4)}-${date.slice(4,6)}` +
         `T${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}Z`;
}
```

`decode.timestamp` is whichever field in the decode object holds the `YYMMDD_HHMMSS`
string (the leftmost column of ALL.TXT). Verify the actual field name against the
WebSocket decode event schema and adjust accordingly.

### 7 — `web/js/main.js` — clickable CQ rows

Add the click handler inside the CQ-highlighting block:

```javascript
if (decode.message.startsWith('CQ ')) {
  row.classList.add('decode-cq');
  row.style.cursor = 'pointer';

  row.addEventListener('click', async () => {
    const callsign = extractCqCallsign(decode.message);
    if (!callsign) return;
    const cqCycleStartUtc = row.dataset.cqCycleStartUtc;

    try {
      const status = await postTxAnswerCq(callsign, decode.offsetHz, cqCycleStartUtc);
      renderTxPanel(status.state, status.partner, status.autoAnswerEnabled);
    } catch (err) {
      if (err?.status === 409) {
        console.warn('TX not Idle — CQ click ignored.');
      } else {
        console.error('postTxAnswerCq error:', err);
      }
    }
  });
}
```

Callsign extractor:

```javascript
function extractCqCallsign(message) {
  const tokens = message.split(' ');
  if (tokens.length === 3) return tokens[1]; // CQ callsign grid
  if (tokens.length >= 4)  return tokens[2]; // CQ modifier callsign grid
  return null;
}
```

### 8 — `web/js/main.js` — partner interaction highlighting

```javascript
function tokenMatchesCallsign(token, callsign) {
  return token === callsign || token.startsWith(callsign + '/');
}

function isPartnerInteractionRow(message, txCallsign, partner) {
  if (!partner || !txCallsign) return false;
  const tokens = message.split(' ');
  return tokens.some(t => tokenMatchesCallsign(t, txCallsign))
      && tokens.some(t => tokenMatchesCallsign(t, partner));
}
```

Apply at row-creation time (after the CQ block):

```javascript
if (isPartnerInteractionRow(decode.message, txCallsign, currentTxPartner)) {
  row.classList.add('decode-partner');
}
```

`txCallsign` (from `config.tx.callsign`) and `currentTxPartner` (from `txState` WS events)
are existing module-level variables.

### 9 — `web/css/app.css` — new classes

```css
/* CQ row — warm accent; operator's eye is drawn to CQing stations */
.decode-cq {
  background-color: rgba(200, 150, 50, 0.15);
}
.decode-cq:hover {
  background-color: rgba(200, 150, 50, 0.28);
  cursor: pointer;
}

/* Partner QSO exchange — subdued red; clearly readable, not harsh */
.decode-partner {
  background-color: rgba(180, 40, 40, 0.18);
}
```

Adjust colour values to taste. Constraints:
- `.decode-cq`: warm (amber/gold range); NOT red; ≤20 % opacity; readable text.
- `.decode-partner`: red family; subdued (≤20 % opacity); NOT neon; readable.
- Prefer `var(--color-*)` custom properties where the palette already defines them.

---

## Acceptance Criteria

The QA engineer will verify ALL of the following before approving merge:

### Backend
- [ ] `IQsoController` contains `Task AnswerCqAsync(string, double, DateTimeOffset, CancellationToken)`.
- [ ] `POST /api/v1/tx/answer-cq` responds HTTP 200 (+ JSON body) when Idle; HTTP 409 when not Idle.
- [ ] `autoAnswerEnabled: true` in the 200 response body.
- [ ] A pending target set for A-phase answer is NOT fired when `HandleIdleAsync` runs at B-phase.
- [ ] The same pending target IS fired when `HandleIdleAsync` next runs at A-phase.
- [ ] Pending target > 60 s old is cleared with a warning log; no TX.
- [ ] `POST /api/v1/tx/abort` clears the pending target; no subsequent TX.
- [ ] `dotnet test OpenWSFZ.slnx -c Release` — all tests green (≥551 passing).

### Frontend
- [ ] CQ rows have `decode-cq` class and warm accent background.
- [ ] Clicking a 3-token CQ row sends the request with `callsign = token[1]`.
- [ ] Clicking a 4-token CQ row sends the request with `callsign = token[2]`.
- [ ] `cqCycleStartUtc` is a valid ISO 8601 UTC string parsed from the row timestamp.
- [ ] HTTP 200 response triggers `renderTxPanel` (TX panel updates to armed appearance).
- [ ] HTTP 409 produces only a `console.warn`; no UI change.
- [ ] Partner QSO exchange rows have `decode-partner` class (subdued red).
- [ ] Third-party rows (partner present, operator's callsign absent) have NO `decode-partner` class.
- [ ] CQ rows of the partner are NOT also `decode-partner` (operator's callsign not present).

---

## Test cases to add

Minimum five new automated tests:

1. `AnswerCqAsync_WhenIdle_BPhaseAnswer_SetsPendingAPhase` — cqCycleStart at :15 → pending phase is A
2. `AnswerCqAsync_WhenIdle_APhaseAnswer_SetsPendingBPhase` — cqCycleStart at :00 → pending phase is B
3. `HandleIdle_PendingTarget_WrongPhase_DoesNotFire`
4. `HandleIdle_PendingTarget_CorrectPhase_Fires`
5. `HandleIdle_PendingTarget_TimedOut_ClearsAndDoesNotFire`
6. `TxAbort_ClearsPendingTarget`
7. `POST_TxAnswerCq_WhenIdle_Returns200` (web integration test)
8. `POST_TxAnswerCq_WhenNotIdle_Returns409`

Tests 1–6 in `OpenWSFZ.Daemon.Tests`; tests 7–8 in `OpenWSFZ.Web.Tests`.
All test callsigns MUST use Q-prefix (NFR-021). PD2FZ/PD2FZ/P may appear only in
fixtures where the operator is the relevant subject.

---

## References

- OpenSpec change: `openspec/changes/gui-tx-panel/`
- Design decisions: `design.md` §D10, §D11, §D12
- QSO controller spec: `specs/qso-controller/spec.md` §AnswerCqAsync, §POST /api/v1/tx/answer-cq
- Frontend spec: `specs/web-frontend/spec.md` §CQ row highlighting, §Clickable CQ rows, §Partner interaction highlighting
- Task checklist: `tasks.md` §9.1–9.10
- Current branch base: `e81241d` (chore: mark 7.6 test-suite task complete, 546 tests)
- NFR-021: ALL example callsigns in tests and documentation MUST use Q-prefix (e.g. `Q1ABC`, `Q9XYZ`). PD2FZ and PD2FZ/P are the operator's own callsigns (consented 2026-06-22) and may appear where the operator is the data subject.
