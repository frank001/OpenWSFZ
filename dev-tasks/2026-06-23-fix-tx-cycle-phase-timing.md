# Handoff — D-TX-UI-005 (remaining) + D-TX-UI-007 (new): TX timing fixes

**Branch:** `feat/gui-tx-panel` (continue on current branch)  
**Date issued:** 2026-06-23  
**Issued by:** QA engineer  
**Blocking merge:** yes — Captain has blocked `feat/gui-tx-panel` pending resolution of both defects below.

---

## Context

`feat/gui-tx-panel` commit `03907bb` fixed D-TX-UI-006 (async-save race) correctly, and the
`SlowConfigStore` regression test passes. However, live testing on 2026-06-23 revealed two
blocking defects.

**D-TX-UI-005 (partially fixed, remaining gap):** The `inFlight` guard in `web/js/main.js`
resets too quickly. The HTTP round-trip completes in ~5–15 ms, so `inFlight` becomes `false`
long before the second human click at ~130–185 ms. AC-8a ("exactly ONE POST per double-click")
still fails — log analysis confirmed two POSTs per test session.

**D-TX-UI-007 (new):** OpenWSFZ transmits in the WRONG FT8 phase, one full cycle (15 s) late.
Live sessions show TX firing at B-phase :45 when answering a B-phase :15 CQ — the same phase
as the CQ sender, producing simultaneous transmission and immediate abort. This is the root
cause of the "transmitting together → goes out of TX mode" symptom in all five test sessions.

The Captain's exact requirement (blocking):
> "When a user double-clicks a CQ before the next available TX window is expired, the response
> should be within the next immediate cycle."

---

## Root-cause analysis

### D-TX-UI-005

In `web/js/main.js`, the click handler resets `inFlight` in the `finally` block:

```javascript
} finally {
    inFlight = false;
    tr.style.pointerEvents = '';
}
```

This runs ~5–15 ms after the click (HTTP latency). A human double-click arrives ~130–185 ms
later — well after `inFlight` has already been reset. The guard only blocks browser-queued
sub-millisecond events, not human input.

### D-TX-UI-007

**Framer semantics (critical):** The `CycleFramer` emits a cycle's `DecodeBatch` at the END of
that cycle — i.e., at wall-clock time `cycleStart + 15 s`. So:

| Cycle | `batch.CycleStart` | Batch emitted at (wall clock) |
|---|---|---|
| B-phase :15 | 15:XX:15 | 15:XX:30 |
| A-phase :30 | 15:XX:30 | 15:XX:45 |
| B-phase :45 | 15:XX:45 | 15:XX:00 (next min) |
| A-phase :00 | 15:XX:00 | 15:XX:15 |

`HandleIdleAsync` (lines 341–350, `QsoAnswererService.cs`) uses:

```csharp
bool currentIsAPhase = IsAPhase(batch.CycleStart);   // ← evaluates COMPLETED cycle
if (currentIsAPhase != pendingIsAPhase)
    return;
```

**Scenario (sessions 1–4 in live log):** User clicks B-phase :15 CQ → `_pendingTargetIsAPhase = TRUE` (A-phase).

- Batch for cycle :15 (B-phase, `CycleStart = :15`) arrives at wall clock **:30**.  
  `IsAPhase(:15) = FALSE` → `FALSE ≠ TRUE` → **skip**.
- Batch for cycle :30 (A-phase, `CycleStart = :30`) arrives at wall clock **:45**.  
  `IsAPhase(:30) = TRUE` → `TRUE == TRUE` → **FIRE at :45 (B-phase window)**.

TX plays at B-phase :45 — the CQ sender's own TX window. Simultaneous TX → abort.

**The fix:** the batch for cycle C is processed at `C.CycleStart + 15 s`. That expression equals
the start of the cycle BEGINNING NOW. The phase check must use this value:

```
IsAPhase(batch.CycleStart + 15 s)   // phase of cycle starting NOW
```

Verify with the same scenario:
- Batch for cycle :15 arrives at :30: `:15 + 15 = :30` → A-phase → **FIRE at :30** ✓  
- Batch for cycle :30 arrives at :45: `:30 + 15 = :45` → B-phase → **skip** ✓

**The comment on lines 342–344** states "Do NOT fall back to UtcNow" (correct) but then uses
`batch.CycleStart` (one cycle too old) instead of `batch.CycleStart + 15 s` (current). The
comment must be updated to explain the `+15 s` semantics.

**Wakeup batch (to enable within-cycle TX):** After fixing the phase check, the service can
only fire TX when a decode batch arrives. Batches arrive every 15 s (at cycle boundaries).
If a user clicks at second :31 (one second into the A-phase :30 window), the service won't
see a batch until :45 — 14 seconds later, when it will correctly SKIP (B-phase). TX then
waits until :00 (next A-phase). That is one full missed cycle.

The fix for this: when `AnswerCqAsync` sets `_pendingTargetCallsign`, it must immediately
push a **wakeup batch** into the background loop so the phase check runs right away, while
the A-phase :30 window is still open. See Actions 5–6 below.

---

## Actions

### Action 1 — Fix inFlight guard (D-TX-UI-005) · `web/js/main.js`

Locate the `try/catch/finally` in the CQ row click handler (around line 256). Change the
`finally` block so that `inFlight` is only reset immediately on error; on success, delay the
reset by 400 ms via `setTimeout`.

**Before:**
```javascript
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
    inFlight = false;
    tr.style.pointerEvents = '';
}
```

**After:**
```javascript
try {
    const status = await postTxAnswerCq(callsign, r.freqHz, cqCycleStartUtc);
    renderTxPanel(status.state, status.partner, status.autoAnswerEnabled);
    // Delay guard reset to block human double-clicks (~130–185 ms interval).
    // On success the operator does not need to retry; 400 ms is harmless.
    setTimeout(() => {
        inFlight = false;
        tr.style.pointerEvents = '';
    }, 400);
} catch (err) {
    // On error, reset immediately so the operator can retry.
    inFlight = false;
    tr.style.pointerEvents = '';
    if (/** @type {any} */ (err)?.status === 409) {
        console.warn('TX not Idle — CQ click ignored.');
    } else {
        console.error('postTxAnswerCq error:', err);
    }
}
```

Remove the `finally` block entirely (it is replaced by the two explicit resets above).

---

### Action 2 — Add `RoundDownTo15s` helper · `QsoAnswererService.cs`

Add this static helper near `IsAPhase` (around line 861):

```csharp
/// <summary>
/// Rounds <paramref name="t"/> down to the nearest 15-second FT8 cycle boundary (UTC).
/// </summary>
private static DateTimeOffset RoundDownTo15s(DateTimeOffset t) =>
    new DateTimeOffset(t.Year, t.Month, t.Day,
        t.Hour, t.Minute, (t.Second / 15) * 15, 0, TimeSpan.Zero);
```

---

### Action 3 — Add private wakeup channel · `QsoAnswererService.cs`

In the private state region (around line 45), add:

```csharp
/// <summary>
/// Written by <see cref="AnswerCqAsync"/> immediately after setting the pending target,
/// so the background loop wakes up and can fire TX within the current FT8 cycle window
/// without waiting for the next regular <see cref="_decodeChannel"/> batch (D-TX-UI-007).
/// </summary>
private readonly Channel<DecodeBatch> _wakeupChannel =
    Channel.CreateUnbounded<DecodeBatch>(
        new UnboundedChannelOptions { SingleWriter = true, SingleReader = true });
```

---

### Action 4 — Fix phase check in `HandleIdleAsync` · `QsoAnswererService.cs`

Replace lines 341–350 (the phase-check block under the pending-target section):

**Before:**
```csharp
// Phase check: only fire on the correct answer phase.
// Use batch.CycleStart — the authoritative timestamp from the CycleFramer.
// Do NOT fall back to UtcNow: for silence-guard cycles (empty Results) the
// emission time is at the NEXT boundary and would always return the wrong phase.
bool currentIsAPhase = IsAPhase(batch.CycleStart);
if (currentIsAPhase != pendingIsAPhase)
{
    // Wrong phase — skip this cycle; retain the pending target for next cycle.
    return;
}
```

**After:**
```csharp
// Phase check: only fire on the correct answer phase.
//
// FRAMER SEMANTICS: the CycleFramer emits a cycle's batch at the END of that cycle —
// i.e., at wall-clock time (batch.CycleStart + 15 s).  The cycle BEGINNING NOW is
// therefore (batch.CycleStart + 15 s), not batch.CycleStart.
//
// Do NOT use UtcNow directly here: it includes sub-second jitter and is redundant
// given that (batch.CycleStart + 15 s) already equals the authoritative cycle boundary.
// Do NOT use batch.CycleStart alone: that is the COMPLETED cycle — one cycle too old —
// causing TX to fire in the phase of the cycle AFTER the target (D-TX-UI-007).
bool nextCycleIsAPhase = IsAPhase(batch.CycleStart + TimeSpan.FromSeconds(15));
if (nextCycleIsAPhase != pendingIsAPhase)
{
    // Wrong phase — skip this cycle; retain the pending target for next batch.
    return;
}
```

---

### Action 5 — Push wakeup batch from `AnswerCqAsync` · `QsoAnswererService.cs`

Immediately after the `lock (_stateLock) { ... }` block in `AnswerCqAsync` (after line 176,
before the `SaveAsync` call), add:

```csharp
// Push a wakeup batch so the background loop can fire TX in the CURRENT cycle window
// if the click arrives while the correct phase is active (D-TX-UI-007).
//
// The wakeup batch's CycleStart is set to (currentCycleStart − 15 s) so that the
// phase check IsAPhase(batch.CycleStart + 15 s) evaluates to the phase of the
// cycle that is STARTING NOW — consistent with how regular decode batches are
// evaluated (see HandleIdleAsync, Action 4).
var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
_wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));
```

---

### Action 6 — Merge wakeup channel in `ReadNextBatchAsync` · `QsoAnswererService.cs`

Replace the current `ReadNextBatchAsync` implementation (lines 248–264) with a version that
races `_decodeChannel` and `_wakeupChannel` when in the Idle state:

```csharp
/// <summary>
/// Awaits the next <see cref="DecodeBatch"/> from either the main decode channel or
/// the internal wakeup channel.  When in Idle state, both channels are raced so that
/// a wakeup posted by <see cref="AnswerCqAsync"/> can fire TX in the current cycle
/// without waiting for the next regular batch (D-TX-UI-007).
/// </summary>
private async ValueTask<DecodeBatch?> ReadNextBatchAsync(CancellationToken stoppingToken)
{
    if (_state != QsoState.Idle)
    {
        // Non-Idle: only the decode channel is needed; TX CTS also cancels the wait.
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(
            stoppingToken, _txCts.Token);
        try
        {
            return await _decodeChannel.ReadAsync(linked.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!stoppingToken.IsCancellationRequested)
        {
            return null; // TX CTS fired (watchdog or abort).
        }
    }

    // Idle: race _decodeChannel and _wakeupChannel.
    // Drain any already-queued wakeup first (avoids an unnecessary Task.WhenAny allocation
    // in the common case where AnswerCqAsync has not yet been called this cycle).
    if (_wakeupChannel.Reader.TryRead(out var pending)) return pending;

    while (!stoppingToken.IsCancellationRequested)
    {
        if (_decodeChannel.Reader.TryRead(out var decode))  return decode;
        if (_wakeupChannel.Reader.TryRead(out var wakeup)) return wakeup;

        var decodeReady = _decodeChannel.Reader.WaitToReadAsync(stoppingToken).AsTask();
        var wakeupReady = _wakeupChannel.Reader.WaitToReadAsync(stoppingToken).AsTask();
        await Task.WhenAny(decodeReady, wakeupReady).ConfigureAwait(false);
        stoppingToken.ThrowIfCancellationRequested();
        // Loop back and TryRead from both channels.
    }

    stoppingToken.ThrowIfCancellationRequested();
    return null!; // Unreachable.
}
```

---

### Action 7 — Update tests · `QsoAnswererServiceTests.cs`

**Critical:** the phase check change in Action 4 inverts the relationship between
`batch.CycleStart` and the expected phase. **Every existing test that pushes a pending-target
batch must update `CycleStart`.**

The new rule: to fire TX for a pending target on phase P, push a batch whose
`CycleStart` is 15 seconds BEFORE an instance of phase P:

| Pending phase | Old `CycleStart` example | New `CycleStart` example |
|---|---|---|
| A-phase (`:00`/`:30`) | `HH:MM:30` (A-phase) | `HH:MM:15` (B-phase, 15 s before `:30`) |
| B-phase (`:15`/`:45`) | `HH:MM:15` (B-phase) | `HH:MM:00` (A-phase, 15 s before `:15`) |

**Wakeup batch side-effects in tests:** `AnswerCqAsync` now immediately writes a wakeup batch
to `_wakeupChannel`. In tests, the background loop may fire from this wakeup batch before the
test's manually pushed batch arrives. Two acceptable approaches:

- **Preferred:** push the test batch to the main channel BEFORE calling `AnswerCqAsync`, so
  the background loop drains the wakeup (which skips on wrong phase for the test's setup) and
  then processes the main channel batch.
- **Alternative:** call `AnswerCqAsync`, then drain the wakeup channel by calling
  `_wakeupChannel.Reader.TryRead(out _)` via `internal` visibility before pushing the test
  batch. This requires exposing `_wakeupChannel` as `internal readonly` for test access.

The `HandleIdle_PendingTarget_FiresWhenAutoAnswerSaveIsDelayed` test (SlowConfigStore,
D-TX-UI-006) must also update its `CycleStart` to the new convention.

**New tests to add:**

| Test name | What it verifies |
|---|---|
| `HandleIdle_PendingTarget_Wakeup_FiresInCurrentCycle` | Push wakeup via `AnswerCqAsync`; don't push any main-channel batch; assert TX fires from wakeup. |
| `HandleIdle_PendingTarget_Wakeup_SkipsWrongPhase` | Push wakeup where `CycleStart + 15s` is wrong phase; assert TX does NOT fire from wakeup but fires from subsequent correct-phase batch. |
| `DoubleClickGuard_SecondClickWithin400ms_SendsOnePost` | Integration test (or manual): two rapid HTTP POSTs within 150 ms; assert second POST is blocked by `inFlight`. This is a JS-level concern — manual verification is acceptable; document in the test file as a comment referencing AC-8a. |

---

## Acceptance criteria

**AC-8a (D-TX-UI-005):** A human double-click (two clicks ~150 ms apart) on a CQ row sends
exactly ONE `POST /api/v1/tx/answer-cq` to the server. Verified manually by log inspection.

**AC-TT-1 (D-TX-UI-007 — correct phase):** When answering a B-phase (:15) CQ, OpenWSFZ
transmits in the next A-phase (:30) window, not in B-phase (:45). WSJT-X and OpenWSFZ do NOT
transmit simultaneously.

**AC-TT-2 (D-TX-UI-007 — within-cycle response):** When the user clicks a CQ row during the
A-phase :30 window (i.e., click arrives within ~14 s of the window opening), OpenWSFZ begins
TX within that same :30 window — not deferred to the :00 window of the next minute.

**AC-TT-3 (D-TX-UI-007 — QSO completes):** A full QSO sequence (TxAnswer → WaitReport →
TxReport → WaitRr73 → Tx73 → QsoComplete) completes without phase-conflict abort. ADIF record
logged.

**AC-9 (regression):** `dotnet test OpenWSFZ.slnx -c Release` — 0 failures. Test count
≥ 556 (count at entry to this task); new tests may increase the count.

**AC-10 (build):** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

---

## References

- `dev-tasks/2026-06-23-fix-tx-double-click-race.md` — prior handoff (D-TX-UI-005/006)
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `HandleIdleAsync` lines 301–361; `AnswerCqAsync` lines 162–191; `ReadNextBatchAsync` lines 248–264; `IsAPhase` line 861
- `web/js/main.js` — click handler lines ~256–280
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` — pending-target and D-TX-UI-006 tests
- `logs/openswfz-20260623T151321Z.log` / `logs/openswfz-20260623T152146Z.log` — live evidence; TX KeyDown timestamps confirm B-phase (:45) firing in sessions 1–4
- OpenSpec: `openspec/changes/gui-tx-panel/`
