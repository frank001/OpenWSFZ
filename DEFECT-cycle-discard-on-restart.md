# Defect: Spurious Cycle Discard After Restart — "Dial Frequency Changed from Unknown"

**Raised by:** QA  
**Severity:** High — valid FT8 decode cycles are silently discarded for up to 15 seconds after every application restart when CAT is enabled  
**Requirement violated:** FR-039 — *"The last polled CAT frequency must be persisted and used as the effective dial frequency across restarts."*  
**Affects:** `src/OpenWSFZ.Daemon/Program.cs`

---

## What is Wrong

After every application restart with CAT enabled, the following log appears for the first
capture window that completes:

```
[19:07:15 INF] Cycle 17:07:00: discarded — dial frequency changed from unknown to 7.074 MHz during capture window.
```

The operator has not changed radio frequency. The discard is spurious.

The decode pump in `Program.cs` contains a legitimate band-change guard: it snapshots the
dial frequency when a capture window opens and compares it against the live value when the
window closes. If they differ, the audio spans two bands and the cycle is discarded. This
guard is correct. The defect is that **both sides of the comparison read only the live
in-session CAT state** (`catState.DialFrequencyMHz`), which is `null` at startup until the
first successful CAT poll — regardless of the persisted `LastPolledFrequencyMHz` value
introduced by FR-039.

---

## Sequence That Produces the Discard

| Time | Event |
|------|-------|
| T + 0 ms | Capture window opens. `catState.DialFrequencyMHz = null` (no poll yet). `windowDialFreq = null` ("unknown"). |
| T + ~500 ms | CAT service completes its first poll. `catState.DialFrequencyMHz = 7.074`. |
| T + 15 s | Window closes. `currentDialFreq = catState.DialFrequencyMHz = 7.074`. |
| Comparison | `null ≠ 7.074` → cycle discarded. Log emitted. |

`LastPolledFrequencyMHz = 7.074` is present in the config store throughout — FR-039 persisted
it correctly — but the two comparator sites in the decode pump do not consult it.

---

## Location of the Defect

**File:** `src/OpenWSFZ.Daemon/Program.cs`

### Site 1 — `dialFreqProvider` delegate (inside `StartPipeline`, line ~435)

This delegate is invoked by `CycleFramer` at the moment each capture window opens. It
captures only the live CAT state:

```csharp
var cycleFramer = new CycleFramer(
    captureManager.Samples,
    clock,
    loggerFactory.CreateLogger<CycleFramer>(),
    dialFreqProvider: () => catState.DialFrequencyMHz);   // ← Tier 1 only
```

### Site 2 — `currentDialFreq` read (inside the decode-pump loop, line ~267)

The end-of-window comparison also reads only the live state:

```csharp
var currentDialFreq = catState.DialFrequencyMHz;          // ← Tier 1 only
if (windowDialFreq != currentDialFreq)
{
    startupLogger.LogInformation(
        "Cycle {CycleStart:HH:mm:ss}: discarded — dial frequency changed " +
        "from {Before} to {After} MHz during capture window.", ...);
    continue;
}
```

Both sites must instead use the **three-tier effective frequency resolution** defined by
FR-039, which falls through from live CAT → persisted last-known → operator manual entry.

---

## Required Fix

### Step 1 — Make `ResolveEffectiveFrequency` accessible from `OpenWSFZ.Daemon`

`WebApp.ResolveEffectiveFrequency` is currently `internal static`. `Program.cs` is in
`OpenWSFZ.Daemon` — a different assembly — and cannot call it.

**Change the access modifier to `public static`** in `src/OpenWSFZ.Web/WebApp.cs`:

```csharp
// Before
internal static double ResolveEffectiveFrequency(ICatState? catState, AppConfig config)

// After
public static double ResolveEffectiveFrequency(ICatState? catState, AppConfig config)
```

The function is a pure, stateless helper with no web-layer side effects. Promoting it to
`public` is safe and avoids duplicating the three-tier logic.

### Step 2 — Update `dialFreqProvider` in `StartPipeline`

```csharp
// Before
dialFreqProvider: () => catState.DialFrequencyMHz

// After
dialFreqProvider: () => WebApp.ResolveEffectiveFrequency(catState, configStore.Current)
```

The return type of the delegate is `Func<double?>`. `ResolveEffectiveFrequency` returns
`double`, which converts to `double?` implicitly — no cast required.

### Step 3 — Update `currentDialFreq` in the decode-pump loop

```csharp
// Before
var currentDialFreq = catState.DialFrequencyMHz;
if (windowDialFreq != currentDialFreq)

// After
var currentDialFreq = (double?)WebApp.ResolveEffectiveFrequency(catState, configStore.Current);
if (windowDialFreq != currentDialFreq)
```

The cast to `double?` preserves the existing comparison type so no further changes to the
discard branch or log format are needed.

### Step 4 — Minor housekeeping (non-blocking)

With `windowDialFreq` now sourced from `ResolveEffectiveFrequency`, it will never be `null`
(the three-tier rule always returns at least `0.0`). The null-coalescing fallback on the
ALL.TXT path (line ~282) becomes dead code:

```csharp
// This ?? chain is now unreachable for the left-hand side:
var dialFreq = windowDialFreq ?? configStore.Current.DecodeLog?.DialFrequencyMHz ?? 0.0;
```

It may be left as a harmless defensive guard or simplified to `windowDialFreq!.Value`. The
developer's preference; it is not a blocking item.

---

## Why This Was Not Caught

FR-039 was tested in isolation and its unit tests correctly validate the three-tier helper
and the `CatPollingService` persistence path. However, no test exercises the
**decode-pump comparator** under the condition that matters: CAT enabled, first poll
completing during an active capture window after a restart. The discard is logged at `INF`,
not `WRN`, so it does not appear in default log-level output during CI runs.

---

## Regression Test

Add one test to `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs` or a new
file `DecodeFrequencyGuardTests.cs`. The scenario to cover:

> Given CAT is enabled and `LastPolledFrequencyMHz = 7.074` is persisted, when
> `catState.DialFrequencyMHz` is `null` at window-open time and `7.074` at window-close
> time, the effective frequency resolves to `7.074` at both points and the comparison
> does not trigger a discard.

The test does not require wiring up a full capture pipeline; it is sufficient to call
`WebApp.ResolveEffectiveFrequency` directly with the two states and assert equal values.

---

## Acceptance Criteria

- [ ] `WebApp.ResolveEffectiveFrequency` is `public static`.
- [ ] `dialFreqProvider` in `StartPipeline` uses `ResolveEffectiveFrequency`.
- [ ] `currentDialFreq` in the decode-pump loop uses `ResolveEffectiveFrequency`.
- [ ] Application started with CAT enabled and `LastPolledFrequencyMHz` persisted produces **no** discard log for the first capture window after startup.
- [ ] A regression test is added covering the null-live / persisted-value scenario.
- [ ] All existing tests remain green.
