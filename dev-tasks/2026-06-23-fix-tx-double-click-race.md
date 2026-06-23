# Developer Handoff — fix: double-click race causes TX non-engagement and spurious auto-answer

**Date:** 2026-06-23  
**Prepared by:** QA Engineer  
**Defect IDs:** D-TX-UI-005 (JS double-click guard), D-TX-UI-006 (server-side pending-target race)  
**Branch:** `feat/gui-tx-panel` (extend in place — do NOT open a new branch)  
**Discovered from:** `logs/openswfz-20260623T144042Z.log` + Captain's live observations

---

## 1. Context

QA review of D-TX-UI-004 revealed two live defects reported by the Captain:

1. **"Sometimes the double click set the TX mode, but it didn't actually engage"** — TX panel shows
   armed state, but no transmission occurs.

2. **"OpenWSFZ was transmitting at the same time as WSJT-X"** — both applications transmitted in
   the same FT8 cycle window.

Both symptoms share one root cause: a race between `AnswerCqAsync`'s async `SaveAsync(AutoAnswer=true)`
call and `HandleIdleAsync`'s synchronous read of `_configStore.Current.Tx.AutoAnswer`.

The JS double-click guard (`tr.style.pointerEvents = 'none'`) is a separate, independently broken fix
that allows double-fires and exacerbates the server-side race.

---

## 2. Root Cause Analysis

### 2.1 The server-side race (D-TX-UI-006)

`JsonConfigStore.SaveAsync` is NOT serialised — there is no lock or semaphore. `_current` is
`volatile` (visibility only, not write-ordering across concurrent callers).

`AnswerCqAsync` sets `_pendingTargetCallsign` synchronously under `_stateLock`, then calls
`SaveAsync(AutoAnswer=true)` asynchronously and returns to the caller. The background service
loop is NOT awaiting this save. If the next A-phase cycle arrives while the save is in flight,
`HandleIdleAsync` reads the old `_current` (which still has `AutoAnswer=false`) and discards
the pending target:

```
AnswerCqAsync [HTTP thread]:
  lock (_stateLock) → _pendingTargetCallsign = "PD2FZ"    ← synchronous
  SaveAsync(AutoAnswer=true) ← async, not yet written to _current

[background thread: A-phase silent batch arrives, ~0–15 ms later]
HandleIdleAsync:
  pendingCallsign = "PD2FZ"                         ✓ set
  tx = _configStore.Current.Tx → AutoAnswer = FALSE  ✗ save not complete
  if (!tx.AutoAnswer) → DISCARD pending target → null
  return;                                            → TX never fires

AnswerCqAsync [HTTP thread]:
  SaveAsync completes → _current.Tx.AutoAnswer = true   ← left armed with no pending target!
```

On the NEXT batch, `HandleIdleAsync` finds `pendingCallsign = null` and falls through to the
CQ scan. `AutoAnswer = true` → auto-answers the first decoded CQ — which may be the same CQ
that WSJT-X is also answering in the same timeslot → simultaneous TX.

### 2.2 The JS double-click guard (D-TX-UI-005)

`tr.style.pointerEvents = 'none'` only prevents FUTURE pointer capture after the property is
set. It cannot drain already-queued click events. Browsers queue both click events before the
JavaScript event loop processes either one. The log shows consistent double-fires at 155–170 ms
intervals across all three test answer-cq sessions. The `pointerEvents` property is set
synchronously before the first `await`, but the second event was already queued by then.

The double-click doubles the number of `AnswerCqAsync` invocations, widening the race window
for D-TX-UI-006.

---

## 3. Branch

Work on: **`feat/gui-tx-panel`**

---

## 4. Actions

### 4.1 — Fix JS double-click guard (`web/js/main.js`)

Replace the `tr.style.pointerEvents` approach with a closure-scoped boolean. The boolean is
evaluated synchronously and cannot be bypassed by already-queued events:

**Current code (lines 256–273):**

```javascript
tr.addEventListener('click', async () => {
    const callsign = extractCqCallsign(r.message);
    if (!callsign) return;
    tr.style.pointerEvents = 'none';
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
        tr.style.pointerEvents = '';
    }
});
```

**Replacement:**

```javascript
let inFlight = false;
tr.addEventListener('click', async () => {
    if (inFlight) return;                          // guard already-queued duplicate events
    inFlight = true;
    tr.style.pointerEvents = 'none';               // belt-and-suspenders for mouse
    const callsign = extractCqCallsign(r.message);
    if (!callsign) {
        inFlight = false;
        tr.style.pointerEvents = '';
        return;
    }
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
        inFlight = false;
        tr.style.pointerEvents = '';
    }
});
```

---

### 4.2 — Remove `AutoAnswer` guard from pending-target path (`QsoAnswererService.cs`)

The `if (!tx.AutoAnswer)` check in the pending-target block of `HandleIdleAsync` must be removed.
The pending-target abort mechanism is `_pendingTargetCallsign = null` (set under `_stateLock` by
`SafeAbortToIdleAsync`). Gating on the asynchronously-saved `AutoAnswer` flag creates the race.

**In `HandleIdleAsync`, locate the pending-target block (currently lines ~324–364).**

**Remove these lines:**

```csharp
// If AutoAnswer was rescinded (abort/disable saved AutoAnswer=false), discard.
if (!tx.AutoAnswer)
{
    _logger.LogInformation(
        "QsoAnswererService: pending target '{Callsign}' discarded — AutoAnswer was disabled.",
        pendingCallsign);
    lock (_stateLock) { _pendingTargetCallsign = null; }
    return;
}
```

After removal the pending-target block reads: null-check, timeout guard, phase check, fire.
The abort path is already covered by `_pendingTargetCallsign = null` in `SafeAbortToIdleAsync`.

**Add a guard comment above the timeout check to explain the absence of the AutoAnswer check:**

```csharp
// NOTE: do NOT gate on tx.AutoAnswer here. The pending target is set synchronously
// under _stateLock, but SaveAsync(AutoAnswer=true) in AnswerCqAsync is async. If
// AutoAnswer is read before the save completes, the pending target is incorrectly
// discarded (D-TX-UI-006). Abort detection uses _pendingTargetCallsign = null
// (set by SafeAbortToIdleAsync under _stateLock), not the AutoAnswer flag.
```

---

### 4.3 — Update the existing `TxAbort_ClearsPendingTarget` test

The test currently uses `AutoAnswer=false` as the abort signal (simulating what the endpoint does).
After §4.2 the pending-target path no longer consults `AutoAnswer`, so the test must be updated
to use the real abort mechanism: calling `SafeAbortToIdleAsync` indirectly via `AbortAsync`.

**Current test approach (lines 1043–1066):**
```csharp
// Simulate abort: set AutoAnswer = false in the config (what the abort endpoint does).
await store.SaveAsync(store.Current with { Tx = ... with { AutoAnswer = false } });

// Feed correct-phase batch — pending target should be discarded because AutoAnswer=false.
channel.Writer.TryWrite(new DecodeBatch(...));
await Task.Delay(400);

sut.State.Should().Be(QsoState.Idle, "abort (AutoAnswer=false) must suppress the pending TX");
```

**Replace with:**
```csharp
// AbortAsync clears the pending target via SafeAbortToIdleAsync._pendingTargetCallsign=null.
// The service must be non-Idle for AbortAsync to do anything; arm the pending target
// THEN make the service non-Idle by sending a CQ first.
// Since the service starts Idle with AutoAnswer=true, arm a pending target in A-phase,
// then send a B-phase CQ to make the service enter WaitReport, THEN abort.

// Step 1: arm pending target for A-phase.
var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero); // B-phase (:15)
await sut.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);

// Step 2: send B-phase batch with the CQ so the CQ-scan path doesn't fire.
//   The pending target is for A-phase; B-phase batch: wrong phase → skipped (target retained).
var bPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero);
channel.Writer.TryWrite(new DecodeBatch(bPhaseStart,
    [new DecodeResult("17:29:15", -5, 0.1, AudioFreqHz, $"CQ Q2NOISE IO91")]));
await Task.Delay(200);

// Pending target still armed; service still Idle (wrong phase, didn't fire).
sut.State.Should().Be(QsoState.Idle);

// Step 3: call AbortAsync directly. AbortAsync → no-op when Idle. So instead call the 
// internal mechanism: send an A-phase batch that fires TX first, then abort mid-QSO.
// This is the most realistic abort scenario.
var aPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 30, 0, TimeSpan.Zero);
channel.Writer.TryWrite(new DecodeBatch(aPhaseStart,
    [new DecodeResult("17:30:00", -5, 0.1, AudioFreqHz, $"CQ Q2NOISE IO91")]));

await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

// Now abort the active QSO.
await sut.AbortAsync();
await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));

// Feed a correct-phase A-phase batch. No pending target remains (cleared by SafeAbortToIdleAsync).
// AutoAnswer was also saved as false by SafeAbortToIdleAsync, so CQ scan is also suppressed.
channel.Writer.TryWrite(new DecodeBatch(
    new DateTimeOffset(2026, 6, 22, 17, 30, 30, TimeSpan.Zero),  // A-phase (:30)
    [new DecodeResult("17:30:30", -5, 0.1, AudioFreqHz, $"CQ Q2NOISE IO91")]));
await Task.Delay(400);

sut.State.Should().Be(QsoState.Idle, "abort must clear pending target; no TX fires");
await ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());  // 1 TX (TxAnswer) only
```

**Note:** `ptt.Received(1)` for the TxAnswer TX (from step 3), and `DidNotReceive` for any
further TX after the abort. If the test infra is too complex, an alternative is to verify that
after abort and re-arming via a second `AnswerCqAsync`, the second arm correctly fires. See §4.4.

---

### 4.4 — Add regression test for D-TX-UI-006

**File: `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`**

Add the following test. It verifies that the pending target fires correctly even when the
config store's `AutoAnswer` has NOT yet been updated (simulating a slow save). This is the
exact scenario that caused D-TX-UI-006.

```csharp
[Fact(DisplayName = "D-TX-UI-006: pending target fires even when AutoAnswer is false in config (slow-save regression)")]
public async Task HandleIdle_PendingTarget_FiresWhenAutoAnswerFalseInConfig()
{
    // This test verifies that the pending-target path does NOT gate on tx.AutoAnswer.
    // Simulates the D-TX-UI-006 race: AnswerCqAsync sets the pending target synchronously
    // but its SaveAsync(AutoAnswer=true) hasn't completed yet → AutoAnswer=false in config.
    // Before the fix, HandleIdleAsync discarded the pending target in this scenario.
    // After the fix, it fires TX regardless of the AutoAnswer flag.

    // Arrange: use a store that keeps AutoAnswer=false throughout this test.
    // (Simulates the race where the async save hasn't completed.)
    var config = new AppConfig() with
    {
        Tx = new TxConfig
        {
            AutoAnswer      = false,   // ← deliberately false; save "hasn't completed"
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 2,
            WatchdogMinutes = 4,
        }
    };
    var store = new MutableConfigStore(config);

    // Override SaveAsync to NOT update AutoAnswer — simulate a slow/pending save.
    // The store always returns AutoAnswer=false regardless of what AnswerCqAsync saves.
    // This models the race window exactly.

    // (MutableConfigStore already persists saves to _current; we need a store whose
    //  Current.Tx.AutoAnswer stays false even after AnswerCqAsync calls SaveAsync.
    //  Use a new subclass or intercept via SaveAsync side-effect.)

    // Simplest approach: use a separate store instance whose Current.Tx.AutoAnswer
    // is controlled directly in this test.

    var ptt = Substitute.For<IPttController>();
    ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
    ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

    var channel = Channel.CreateUnbounded<DecodeBatch>();
    var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
    var sut     = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                      adifLog, new AudioOffsetEventBus(),
                      NullLogger<QsoAnswererService>.Instance);
    using var stopCts = new CancellationTokenSource();
    await sut.StartAsync(stopCts.Token);

    // Arm the pending target via AnswerCqAsync. The underlying store will update
    // AutoAnswer=true (MutableConfigStore persists it), but we DON'T reset it to false
    // between arming and batch delivery in this test — we test the no-save scenario
    // by verifying the pending target fires regardless.
    //
    // To truly simulate the race, we need a store that ignores the AutoAnswer save.
    // Simplest: deliver the batch BEFORE the save's Task is awaited. Since both
    // happen on different threads in real code, we approximate it by calling
    // AnswerCqAsync and immediately (synchronously) sending the batch before
    // await-ing AnswerCqAsync.
    var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero); // B-phase
    var answerTask   = sut.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);

    // Send the correct-phase batch immediately — pending target is set, but
    // AnswerCqAsync may not have completed its SaveAsync yet.
    var aPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 30, 0, TimeSpan.Zero);
    channel.Writer.TryWrite(new DecodeBatch(aPhaseStart, Array.Empty<DecodeResult>()));

    await answerTask; // let AnswerCqAsync complete (including SaveAsync)

    // Assert: TX must fire despite any timing uncertainty around the save.
    await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
    _sut = null; // prevent DisposeAsync from using the wrong service
    await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

    await stopCts.CancelAsync();
    await sut.StopAsync(CancellationToken.None);
    await ptt.DisposeAsync();
}
```

**Note:** This test may not reliably reproduce the race since the save usually completes before
the background thread picks up the batch. It serves as a documentation test. The definitive fix
is §4.2 (removing the AutoAnswer check); the test confirms the behaviour.

A cleaner alternative: create a `SlowConfigStore` that delays `SaveAsync` by 200ms via
`Task.Delay(200)`. This guarantees the pending target is processed before the save completes:

```csharp
private sealed class SlowConfigStore : IConfigStore
{
    private AppConfig _current;
    private readonly TimeSpan _delay;
    public SlowConfigStore(AppConfig initial, TimeSpan delay) { _current = initial; _delay = delay; }
    public AppConfig Current => _current;
    public event Action<AppConfig>? OnSaved;
    public async Task SaveAsync(AppConfig config, CancellationToken ct = default)
    {
        await Task.Delay(_delay, ct);
        _current = config;
        OnSaved?.Invoke(config);
    }
}
```

Then:
```csharp
// Arrange: store whose saves take 200ms (longer than the batch delivery below)
var slowStore = new SlowConfigStore(config, TimeSpan.FromMilliseconds(200));
var sut       = new QsoAnswererService(channel.Reader, slowStore, ptt, ...);
await sut.StartAsync(stopCts.Token);

// Arm pending target — SaveAsync(AutoAnswer=true) starts but takes 200ms
var armTask = sut.AnswerCqAsync(PartnerCall, AudioFreqHz,
    new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero),
    CancellationToken.None);

// Deliver the A-phase batch immediately — before the 200ms save completes.
// Before the fix: HandleIdleAsync reads AutoAnswer=false → discards pending target.
// After the fix:  HandleIdleAsync ignores AutoAnswer for pending target → TX fires.
channel.Writer.TryWrite(new DecodeBatch(
    new DateTimeOffset(2026, 6, 22, 17, 30, 0, TimeSpan.Zero),
    Array.Empty<DecodeResult>()));

await armTask; // complete the slow save

await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
```

Use the `SlowConfigStore` approach — it deterministically reproduces the race.

---

### 4.5 — Update the log message in `HandleIdleAsync`

If the pending-target AutoAnswer discard log message (added in the removed block) was the only
logging for discard events, ensure the timeout-discard log (`[WRN]`) and the phase-skip path
(silent return) are still in place. No action needed if §4.2 removal is clean.

---

### 4.6 — Tick task checklist

**File: `openspec/changes/gui-tx-panel/tasks.md`**

No new task entry is needed. These are post-review defect fixes on the current feature branch.

---

## 5. Acceptance Criteria

QA will verify all of the following before approving merge to `main`:

- [ ] **AC-8a (double-click: one POST only):** Clicking a CQ row rapidly twice sends exactly ONE
  `POST /api/v1/tx/answer-cq` to the server. Confirmed in browser DevTools Network tab.

- [ ] **AC-8b (no spurious auto-answer after pending-target discard):** After the pending target
  fires and the QSO aborts (e.g. partner sends another CQ), `AutoAnswer` is correctly set to
  `false` and the service does NOT auto-answer the next decoded CQ.

- [ ] **AC-D006 (pending target fires when AutoAnswer=false in config):** The `SlowConfigStore`
  regression test passes: TX fires from an A-phase silent batch even when `SaveAsync` has not
  yet updated `_current.Tx.AutoAnswer`.

- [ ] **AC-D006-live (no WSJT-X overlap):** In a live session where both OpenWSFZ and WSJT-X are
  running on 7.074 MHz, clicking a CQ row in OpenWSFZ does NOT cause OpenWSFZ to transmit in
  the same cycle as WSJT-X. (Captain to confirm.)

- [ ] **AC-9 (tests green):** `dotnet test OpenWSFZ.slnx -c Release` — all tests pass (≥ 555
  existing + ≥ 1 new regression test).

- [ ] **AC-10 (build clean):** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero
  warnings.

---

## 6. References

- QA review session: 2026-06-23 (this conversation)
- Log artefact: `logs/openswfz-20260623T144042Z.log` — double-click evidence at lines 227–254,
  428–455, 617–644
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `AnswerCqAsync` (lines 162–191),
  `HandleIdleAsync` (lines 301–408 — specifically the `if (!tx.AutoAnswer)` block ~324–334)
- `src/OpenWSFZ.Config/JsonConfigStore.cs` — `SaveAsync` is async file I/O with no serialisation
  lock; `_current = config` happens after the file write at line 62
- D-TX-UI-004 handoff: `dev-tasks/2026-06-22-fix-answer-cq-phase-detection.md`
- NFR-021: all test callsigns must use Q-prefix.
