# Developer Handoff — fix: answer-cq phase detection fails for silence cycles

**Date:** 2026-06-22  
**Prepared by:** QA Engineer  
**Defect ID:** D-TX-UI-004  
**Branch:** `feat/gui-tx-panel` (extend in place — do NOT open a new branch)  
**Diagnosed from:** `logs/openswfz-20260622T183806Z.log` (live QSO session 20:38–20:42 local)

---

## 1. Context

The CQ click feature (`answer-cq` endpoint, `AnswerCqAsync`, CQ row click handler) was
implemented as requested in `dev-tasks/2026-06-22-gui-tx-panel-cq-click-highlights.md`.
The log shows the endpoint is reachable, returns HTTP 200, and the `QsoAnswererService`
does receive and store the pending target. However, **the QSO never begins** — the TX never
fires.

Root cause: the phase check inside `HandleIdleAsync` uses `DeriveCycleStartFromBatch` to
determine whether a batch is A-phase or B-phase. For empty batches (silence cycles, which
are the windows where OpenWSFZ should transmit), the fallback computes the wrong phase,
so the pending target is never executed.

---

## 2. Root Cause Analysis

### The cycle framing timing

The `CycleFramer` emits a 15-second audio window at its **closing boundary**, not its
opening boundary:

| Actual cycle start (UTC) | Phase | Emitted at (UTC) |
|---|---|---|
| 16:40:00 | **A** | 16:40:15 |
| 16:40:15 | B | 16:40:30 |
| 16:40:30 | **A** | 16:40:45 |
| 16:40:45 | B | 16:41:00 |

### What `DeriveCycleStartFromBatch` does for empty batches

When the RMS silence guard fires, `DecodeAsync` returns an empty `IReadOnlyList<DecodeResult>`.
The decode pump still writes this empty batch to `qsoAnswererChannel`. In `HandleIdleAsync`,
`DeriveCycleStartFromBatch([])` falls back to:

```csharp
var utcNow    = DateTimeOffset.UtcNow;            // ≈ emission time, e.g. 18:40:15 UTC
var totalSecs = utcNow.Hour * 3600 + ...;
var cycleSecond = (totalSecs / 15) * 15;          // snaps to 18:40:15
return new DateTimeOffset(..., 18, 40, 15, ...);  // B-phase!
```

By the time the QsoAnswererService processes the empty batch, `UtcNow` is approximately at
the *next* cycle's start boundary. For an A-phase cycle starting at 18:40:00, the emission
time is 18:40:15, which snaps to 18:40:15 — a **B-phase** boundary. The fallback therefore
returns B-phase for every silent A-phase cycle.

### Why this kills the QSO

When a B-phase CQ is heard (e.g. 16:39:45), the pending target is set for A-phase
(`_pendingTargetIsAPhase = true`). The only cycles where the pending target can fire are
A-phase cycles. A-phase windows carry no received audio (OpenWSFZ would be transmitting
then) → they produce empty batches → the fallback returns B-phase → phase check fails →
pending target is never fired.

The log confirms this sequence for every eligible cycle in the session:

```
20:40:01  answer-cq called → pending for A-phase set, AutoAnswer=true
20:40:15  cycle 16:40:00 (A-phase, silence) → empty batch → fallback gives B-phase → mismatch
20:40:30  cycle 16:40:15 (B-phase, decode) → correct B-phase → mismatch (pending is A)
20:40:45  cycle 16:40:30 (A-phase, silence) → empty batch → fallback gives B-phase → mismatch
20:41:00  cycle 16:40:45 (B-phase, decode) → correct B-phase → mismatch
20:41:04  user aborts → /api/v1/tx/abort → saves AutoAnswer=false
20:41:15  cycle 16:41:00 (A-phase, silence) → AutoAnswer now false → discard
```

---

## 3. Branch

Work on: **`feat/gui-tx-panel`**  
These are defects within the current feature branch; fix before merge.

---

## 4. Actions

### 4.1 — Introduce `DecodeBatch` record

**File: `src/OpenWSFZ.Daemon/DecodeBatch.cs`** (new file)

```csharp
using OpenWSFZ.Ft8;

namespace OpenWSFZ.Daemon;

/// <summary>
/// A completed decode cycle: the authoritative UTC cycle-start timestamp and the
/// list of decode results (empty when the silence guard fired).
/// </summary>
/// <param name="CycleStart">UTC instant at which the CycleFramer began accumulating this window.</param>
/// <param name="Results">Decoded messages; empty when the RMS silence guard fired.</param>
internal sealed record DecodeBatch(
    DateTimeOffset             CycleStart,
    IReadOnlyList<DecodeResult> Results);
```

---

### 4.2 — Update the channel type throughout `Program.cs`

**File: `src/OpenWSFZ.Daemon/Program.cs`**

Change the channel declaration from:

```csharp
var qsoAnswererChannel = Channel.CreateBounded<IReadOnlyList<DecodeResult>>(
    new BoundedChannelOptions(1) { FullMode = BoundedChannelFullMode.DropOldest });
```

to:

```csharp
var qsoAnswererChannel = Channel.CreateBounded<DecodeBatch>(
    new BoundedChannelOptions(1) { FullMode = BoundedChannelFullMode.DropOldest });
```

And update the write site (currently `qsoAnswererChannel.Writer.TryWrite(results)`) to:

```csharp
qsoAnswererChannel.Writer.TryWrite(new DecodeBatch(cycleStart, results));
```

`cycleStart` is already in scope at that point (it comes from the framer output tuple).

Also update the `ChannelReader` passed to `QsoAnswererService`:

```csharp
// Before:
new QsoAnswererService(qsoAnswererChannel.Reader, ...)

// After: unchanged signature, but the type argument changes — see §4.3
```

---

### 4.3 — Update `QsoAnswererService` to use `DecodeBatch`

**File: `src/OpenWSFZ.Daemon/QsoAnswererService.cs`**

**a) Change the channel field type:**

```csharp
// Before:
private readonly ChannelReader<IReadOnlyList<DecodeResult>> _decodeChannel;

// After:
private readonly ChannelReader<DecodeBatch> _decodeChannel;
```

Update the constructor parameter accordingly.

**b) Update `ReadNextBatchAsync` return type:**

```csharp
// Before:
private async ValueTask<IReadOnlyList<DecodeResult>?> ReadNextBatchAsync(CancellationToken stoppingToken)

// After:
private async ValueTask<DecodeBatch?> ReadNextBatchAsync(CancellationToken stoppingToken)
```

**c) Update `ProcessBatchAsync` to accept `DecodeBatch`:**

```csharp
// Before:
private async Task ProcessBatchAsync(IReadOnlyList<DecodeResult> batch, CancellationToken stoppingToken)

// After:
private async Task ProcessBatchAsync(DecodeBatch batch, CancellationToken stoppingToken)
```

Pass `batch.Results` where the existing code uses `batch` as a list, and `batch.CycleStart`
where the cycle-start timestamp is needed.

**d) In `HandleIdleAsync` — replace `DeriveCycleStartFromBatch` with `batch.CycleStart`:**

In the pending-target block (currently at the top of `HandleIdleAsync`), change:

```csharp
// Before:
var  currentCycleStart = DeriveCycleStartFromBatch(batch);
bool currentIsAPhase   = IsAPhase(currentCycleStart);

// After:
bool currentIsAPhase = IsAPhase(batch.CycleStart);
```

**e) In `HandleIdleAsync` — pass `batch.Results` to the CQ scan:**

The foreach loop and `TryParseCq` calls currently iterate `batch` directly. Change to
`batch.Results`:

```csharp
// Before:
foreach (var r in batch) { ... }

// After:
foreach (var r in batch.Results) { ... }
```

**f) In `HandleWaitReportAsync` and `HandleWaitRr73Async`:**

Same substitution — replace `batch` with `batch.Results` in all `foreach` loops.

**g) Delete `DeriveCycleStartFromBatch`:**

The method is no longer needed. Remove it entirely. If a callee uses it, fix the call
site as described above.

---

### 4.4 — Update test infrastructure

**Files: all files in `tests/OpenWSFZ.Daemon.Tests/` that construct a
`Channel<IReadOnlyList<DecodeResult>>`.**

Change `Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>()` to
`Channel.CreateUnbounded<DecodeBatch>()`. Where tests write raw result lists, wrap them:

```csharp
// Before:
channel.Writer.TryWrite(new List<DecodeResult> { ... });

// After:
channel.Writer.TryWrite(new DecodeBatch(
    DateTimeOffset.UtcNow,            // or a specific UTC timestamp for phase-sensitive tests
    new List<DecodeResult> { ... }));
```

For phase-sensitive tests (§4.5 below), use a specific `CycleStart` value:

```csharp
// A-phase cycle (second = 0 or 30)
var aPhaseStart = new DateTimeOffset(2026, 1, 1, 12, 0, 0, TimeSpan.Zero);

// B-phase cycle (second = 15 or 45)
var bPhaseStart = new DateTimeOffset(2026, 1, 1, 12, 0, 15, TimeSpan.Zero);
```

---

### 4.5 — Add unit tests for the pending-target path

**File: `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`**

Add the following eight tests (minimum). Use only Q-prefix callsigns (NFR-021).

1. **`AnswerCqAsync_BPhaseCq_SetsPendingAPhase`**  
   Call `AnswerCqAsync("Q1ABC", 1000, bPhaseStart, ct)`. Assert `_pendingTargetIsAPhase == true`
   (via reflection or a test-visible property). *(Optional: mark internal with `InternalsVisibleTo`.)*

2. **`AnswerCqAsync_APhaseCq_SetsPendingBPhase`**  
   Call `AnswerCqAsync("Q1ABC", 1000, aPhaseStart, ct)`. Assert pending phase is B.

3. **`HandleIdle_PendingTarget_WrongPhase_DoesNotFire`**  
   Arm with a B-phase CQ (pending = A-phase). Write a batch with `CycleStart` = B-phase.
   Assert no TX call and state remains Idle.

4. **`HandleIdle_PendingTarget_CorrectPhase_FiresTx`**  
   Arm with a B-phase CQ (pending = A-phase). Write a batch with `CycleStart` = A-phase
   (empty results or irrelevant results). Assert `PttController.KeyDownAsync` was called
   and state transitions to `TxAnswer` / `WaitReport`.

5. **`HandleIdle_PendingTarget_SilentAPhase_FiresTx`**  
   Same as test 4 but with an empty results list — explicitly verifies that a silence-guard
   cycle (RMS = 0) does not prevent the TX from firing when the phase is correct.

6. **`HandleIdle_PendingTarget_60sTimeout_DiscardsWithoutTx`**  
   Set `_pendingTargetSetAt` to 61 seconds in the past. Write a correct-phase batch.
   Assert no TX and no state change.

7. **`Abort_ClearsPendingTarget`**  
   Set a pending target. Call `AbortAsync`. Assert pending callsign is null (no TX on
   subsequent correct-phase batch).

8. **`POST_TxAnswerCq_WhenIdle_Returns200WithAutoAnswerEnabled`** (web integration test in
   `OpenWSFZ.Web.Tests`)  
   `POST /api/v1/tx/answer-cq` with a valid JSON body. Assert HTTP 200 and
   `response.autoAnswerEnabled == true`.

9. **`POST_TxAnswerCq_WhenNotIdle_Returns409`** (web integration test)  
   Force `qsoController.State != Idle`. Assert HTTP 409.

---

### 4.6 — Minor: fix CQ row double-click in main.js

The log shows two `POST /api/v1/tx/answer-cq` requests 186 ms apart (double-click). Add a
pointer-events guard to the click handler:

```javascript
tr.addEventListener('click', async () => {
    const callsign = extractCqCallsign(r.message);
    if (!callsign) return;
    tr.style.pointerEvents = 'none';           // prevent double-fire while request is in flight
    const cqCycleStartUtc = tr.dataset.cqCycleStartUtc;
    try {
        const status = await postTxAnswerCq(callsign, r.freqHz, cqCycleStartUtc);
        renderTxPanel(status.state, status.partner, status.autoAnswerEnabled);
    } catch (err) {
        if (/** @type {any} */ (err)?.status === 409) {
            console.warn('TX not Idle — CQ click ignored.');
        } else {
            console.error('postTxAnswerCq error:', err);
        }
    } finally {
        tr.style.pointerEvents = '';           // restore after response
    }
});
```

---

### 4.7 — Tick task checklist

**File: `openspec/changes/gui-tx-panel/tasks.md`**

Mark tasks 9.1–9.9 complete once all changes above are implemented and all tests pass.
Task 9.10 (live verification) will be signed off by the QA engineer during review.

---

## 5. Acceptance Criteria

QA will verify all of the following before approving merge to `main`:

- [ ] **AC-1 (Root cause fixed):** With TX callsign and grid configured, clicking a B-phase
  CQ row arms the pending target; the application transmits during the next A-phase cycle.
  Confirmed in a live QSO session or via `run_h6_probe.py`-style harness.

- [ ] **AC-2 (Silence cycles processed correctly):** `HandleIdleAsync` receives the correct
  cycle-start timestamp even when the batch has zero decode results.

- [ ] **AC-3 (Phase arithmetic correct):** A-phase CQ → pending B-phase; B-phase CQ → pending
  A-phase. Confirmed by unit tests 1 and 2.

- [ ] **AC-4 (Wrong-phase skip):** Pending target is NOT fired when the current cycle is the
  wrong phase. Confirmed by unit test 3.

- [ ] **AC-5 (Correct-phase fire):** Pending target IS fired when the current cycle is the
  correct phase — including silent (empty-results) cycles. Confirmed by unit tests 4 and 5.

- [ ] **AC-6 (60 s timeout):** Stale pending target is discarded with a `[WRN]` log entry and
  does not cause TX. Confirmed by unit test 6.

- [ ] **AC-7 (Abort clears pending):** `POST /api/v1/tx/abort` clears the pending target; no
  TX fires on subsequent correct-phase cycle. Confirmed by unit test 7.

- [ ] **AC-8 (Double-click safe):** Clicking a CQ row rapidly twice sends only one POST
  request. Confirmed in browser.

- [ ] **AC-9 (Tests green):** `dotnet test OpenWSFZ.slnx -c Release` — all tests pass.
  Expected count: existing 541 + 9 new tests = ≥ 550 passing.

- [ ] **AC-10 (Build clean):** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero
  warnings.

---

## 6. References

- Original feature handoff: `dev-tasks/2026-06-22-gui-tx-panel-cq-click-highlights.md`
  (Action 2b describes passing `CycleStart`; this bug was caused by a deviation from that action)
- Defect log: `logs/openswfz-20260622T183806Z.log`
  - answer-cq calls at 20:40:01.625 and 20:40:01.831
  - discard messages at 20:41:15.086 and 20:42:00.553
- OpenSpec change: `openspec/changes/gui-tx-panel/`
- Task checklist: `openspec/changes/gui-tx-panel/tasks.md` §9
- NFR-021: ALL test callsigns must use Q-prefix (e.g. `Q1ABC`, `Q9XYZ`).
  PD2FZ / PD2FZ/P may appear only where the operator is the data subject.
