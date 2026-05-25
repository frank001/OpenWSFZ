# Dev-Briefing-5 Review — p5-ft8-decoder

**Date:** 2026-05-23
**Reviewed by:** Developer
**Briefing reviewed:** `dev-briefing-5.md` (head commit `eb0eaaf`)
**Branch:** `feat/p5-ft8-decoder`

---

## Overall Assessment

The briefing is technically sound and the work order is correctly sequenced.
B15 root-cause analysis, B16 fix, B17 fix, and the S6 elevation to Blocker are
all accepted without objection.

Four items require QA adjudication before implementation begins. Items **C1**
and **C2** could affect the design of `AudioWatchdog` and `WasapiAudioSource`
respectively — resolving them first avoids a rework mid-implementation.

---

## C1 — `Tick()` Synchronicity Mismatch Between Design and Tests (MUST RESOLVE)

**Section:** S6 — Watchdog
**Risk:** Test suite with a built-in race condition; incorrect `AudioWatchdog`
interface locked in before the problem is visible.

### The Problem

The briefing states the restart must be fire-and-forget to avoid blocking the
heartbeat emission:

> *"The restart call is fire-and-forget (`_ = Task.Run(...)`) to avoid blocking
> the heartbeat emission."*

The test code, however, calls `watchdog.Tick()` synchronously and asserts the
restart count immediately afterward with no `await` and no synchronisation:

```csharp
watchdog.Tick();
watchdog.Tick();
watchdog.Tick();

restarts.Should().Be(1, "watchdog must trigger exactly once after threshold is reached");
```

If `Tick()` fires the restart as `_ = Task.Run(onRestart)` (as the design
requires), `onRestart` runs on a thread-pool thread. `restarts` may still be
`0` when `Should().Be(1)` executes. This is a data race: the test will sometimes
pass and sometimes fail depending on thread-pool scheduling.

### Two Options — QA to Choose

**Option A — `Tick()` returns `ValueTask`; caller fire-and-forgets**

```csharp
// AudioWatchdog
public async ValueTask TickAsync()
{
    bool active = _monitor.ConsumeAndReset();
    if (active)
    {
        _silentWindows = 0;
        return;
    }
    if (!_isCapturing()) { _silentWindows = 0; return; }
    if (++_silentWindows >= _threshold)
    {
        _silentWindows = 0;
        await _onRestart();   // awaited inside Tick; caller sees completion
    }
}

// Heartbeat loop (production)
_ = watchdog.TickAsync();   // fire-and-forget at the call site, not inside

// Tests
await watchdog.TickAsync();
await watchdog.TickAsync();
await watchdog.TickAsync();
restarts.Should().Be(1);    // deterministic — onRestart completed before assertion
```

**Option B — `Tick()` stays synchronous; tests use `TaskCompletionSource`**

```csharp
// AudioWatchdog — Tick() is void; fires restart internally as Task.Run
public void Tick()
{
    bool active = _monitor.ConsumeAndReset();
    if (active) { _silentWindows = 0; return; }
    if (!_isCapturing()) { _silentWindows = 0; return; }
    if (++_silentWindows >= _threshold)
    {
        _silentWindows = 0;
        _ = Task.Run(_onRestart);
    }
}

// Tests — use TCS to observe async completion
var tcs = new TaskCompletionSource<bool>();
var watchdog = new AudioWatchdog(
    monitor,
    isCapturing: () => true,
    onRestart:   () => { tcs.SetResult(true); return Task.CompletedTask; },
    threshold:   3);

watchdog.Tick();
watchdog.Tick();
watchdog.Tick();

var triggered = await tcs.Task.WaitAsync(TimeSpan.FromSeconds(1));
triggered.Should().BeTrue();
```

**QA recommendation requested:** Which option should the developer implement?
Option A is simpler and the heartbeat loop already uses `_ =` for fire-and-forget.
Option B preserves a synchronous `Tick()` but complicates the tests.

---

## C2 — AO1 May Understate the `AudioSessionManager` Lifetime Risk (SHOULD RESOLVE)

**Section:** AO1 — `sessionControl` device reference lifetime
**Risk:** B15 fix resolves `sessionControl` GC eligibility but a sibling problem
on `AudioSessionManager` may remain.

### The Problem

The briefing notes that `MMDevice.AudioSessionManager` may create a new instance
on each property access and is not cached by NAudio. The access pattern in the
fix is:

```csharp
sessionControl = device.AudioSessionManager.AudioSessionControl;
```

If `AudioSessionManager` is not stored anywhere, the `AudioSessionManager`
instance created by this call has no strong root after the line completes — only
the `sessionControl` variable holds a reference, and only if `AudioSessionControl`
internally keeps a back-reference to its parent manager (not guaranteed).

Should the GC collect the `AudioSessionManager` while capture is in progress, its
finalizer would release the underlying `IAudioSessionManager2` COM pointer. Whether
this silently unregisters the event client or corrupts the COM call chain depends on
NAudio's internal reference counting — but either outcome would silently break B11.

### Recommended Resolution

Add a `sessionManager` local alongside `sessionControl` in the outer scope:

```csharp
AudioSessionManager?    sessionManager = null;
AudioSessionControl?    sessionControl = null;

try
{
    sessionManager = device.AudioSessionManager;
    sessionControl = sessionManager.AudioSessionControl;
    sessionControl.RegisterEventClient(
        new WasapiSessionEventClient(innerChannel, staCts));
}
catch (Exception ex) { /* B16 log */ }

// finally block — dispose in reverse order
try { sessionControl?.Dispose(); } catch { }
try { sessionManager?.Dispose(); } catch { }
```

This costs one extra variable and eliminates the risk entirely, regardless of
NAudio's caching behaviour.

**QA action requested:** Confirm whether NAudio's `MMDevice.AudioSessionManager`
property caches its result (check `NAudio.CoreAudioApi.MMDevice` source). If it
caches, AO1 is a non-issue and no change is needed. If it does not cache, add
`sessionManager` to the outer scope as shown above and document it in the B15
fix description.

---

## C3 — `async Task` Test Methods Without `await` (MINOR)

**Section:** Tests — B17 regression test, S6 watchdog tests
**Risk:** Compiler warning `CS1998`; xUnit anti-pattern.

All three watchdog test methods are declared `async Task` but contain no `await`
expression. This will generate `CS1998` warnings in the build output and is an
xUnit anti-pattern (the test runner does not require `async Task` unless there is
actual async work to observe).

Once C1 is resolved, the correct signature becomes clear automatically:
- If **Option A** is chosen, tests `await watchdog.TickAsync()` and `async Task`
  is correct.
- If **Option B** is chosen, tests are synchronous and the `async` keyword should
  be removed.

**No action needed until C1 is resolved.** Flagged here so the developer does not
copy the test stubs verbatim before QA answers C1.

---

## C4 — DIAG Table Has Ambiguous Duplicate Rows (MINOR)

**Section:** First Diagnostic Step
**Risk:** Developer misreads the table under time pressure.

The diagnostic table contains two rows with identical `captureActive` / `audioActive`
values:

| `captureActive` | `audioActive` | What it means |
|---|---|---|
| `false` | `false` | Capture task COMPLETED. Case 2 or Case 3. Check log. |
| `false` | `false` | Capture task completed; log level filtered the message. |

The distinction (log present vs. log absent) is important but is lost because the
key columns are identical. The two rows should be merged or the distinguishing
condition moved into the key columns:

| `captureActive` | `audioActive` | Log entry present? | What it means |
|---|---|---|---|
| `false` | `false` | Yes | Capture task completed. Check log for Case 2 (warning) or Case 3 (error). |
| `false` | `false` | No | Log level filtered the message. Confirm log-level configuration. |

**QA action requested:** Update the DIAG table before the developer reaches that
step, to avoid a misread at a stressful moment.

---

## Summary — Actions Required Before Implementation

| # | Concern | Action | Owner |
|---|---|---|---|
| **C1** | `Tick()` synchronicity: design says fire-and-forget, tests assume synchronous | **Choose Option A or B and update the test stubs in the briefing** | QA |
| **C2** | `AudioSessionManager` lifetime risk understated in AO1 | **Check NAudio source; confirm or add `sessionManager` to outer scope** | QA |
| C3 | `async Task` without `await` in test stubs | No action until C1 resolved | — |
| C4 | DIAG table duplicate rows | Update table formatting | QA |

C1 and C2 must be resolved before the developer starts. C3 resolves itself once
C1 is answered. C4 is polish and can be addressed at any point.

All other items in dev-briefing-5.md (B15, B16, B17, S6 design, work order,
merge checklist) are accepted as written.
