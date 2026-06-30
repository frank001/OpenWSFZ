# D-CALLER-013 — Late TX start: FT8 signal overruns into adjacent window

**Date:** 2026-06-27  
**Raised by:** QA engineer (analysis of `logs/openswfz-20260627T154903Z.log`)  
**Severity:** High — active transmission bleeds into the partner's next TX window, preventing decode at the remote station.

---

## 1. Context

When the operator clicks a CQ row `N` seconds into the target 15-second window (operator latency), `AnswerCqAsync` pushes a wakeup batch whose phase check passes immediately, causing TX to start at second `N`. Because an FT8 signal is 12.64 seconds, any `N > 2.36 s` causes the signal to overrun into the *adjacent* window. In the test session `openswfz-20260627T154903Z.log`, the overruns were 4–8 seconds — large enough to collide with the partner's next A-phase transmission and explain the repeated "PD2FZ is working CQ — aborting" cycles.

Observed instances (all pre-existing; not introduced by D-CALLER-012):

| Attempt | Click offset into window | TX overrun into next window |
|---------|--------------------------|------------------------------|
| 1       | +6 s                     | +4 s                         |
| 2       | +10 s                    | +8 s                         |
| 5       | +7 s                     | +5 s                         |

The same late-start risk applies to the D-CALLER-012 jump-in path (`EngageAtAsync`), which uses identical phase-check logic in `HandleIdleAsync`.

---

## 2. Branch name

`fix/d-caller-013-late-tx-guard`

---

## 3. Actions

### 3.1 — Add a late-start constant to `QsoAnswererService`

In `src/OpenWSFZ.Daemon/QsoAnswererService.cs`, add a private constant near the other timing constants (e.g., near the watchdog durations):

```csharp
/// <summary>
/// Maximum number of seconds into a 15-second FT8 window that TX may still be started.
/// An FT8 signal is 12.64 s; starting later than this causes overrun into the next window.
/// A 1.5 s threshold leaves ~0.86 s margin (15 - 12.64 - 1.5 = 0.86).
/// </summary>
private const double MaxLateStartSeconds = 1.5;
```

### 3.2 — Add the late-start guard in the pending-target block

In `HandleIdleAsync`, immediately after the phase check passes for the pending-target (after `if (nextCycleIsAPhase != pendingIsAPhase) return;`, line 521), insert the guard **before** the `_logger.LogInformation("pending CQ target ...")` call:

```csharp
// Late-start guard: if we are more than MaxLateStartSeconds into the target window,
// the 12.64-second FT8 signal would overrun into the adjacent window.
// Skip this occurrence and wait for the next cycle with the correct phase (30 s later).
var nowUtc            = DateTimeOffset.UtcNow;
var currentWindowStart = RoundDownTo15s(nowUtc);
var secondsIntoWindow  = (nowUtc - currentWindowStart).TotalSeconds;
if (secondsIntoWindow > MaxLateStartSeconds)
{
    _logger.LogDebug(
        "QsoAnswererService: pending target '{Callsign}' — late start ({SecondsIn:F1} s into window); deferring to next occurrence.",
        pendingCallsign, secondsIntoWindow);
    return; // Retain _pendingTargetCallsign; fires at next correct-phase window (30 s later).
}
```

The `_pendingTargetSetAt` timestamp is NOT reset here — the existing 60-second expiry continues to run from the original click time. This is correct: if the operator clicked 55 seconds ago, the intent is stale regardless.

### 3.3 — Add the late-start guard in the jump-in block

Immediately after the jump-in phase check passes (`if (nextCycleIsAPhase != jumpIsAPhase) return;`, around line 454), insert the same guard **before** `lock (_stateLock) { _jumpPartner = null; }`:

```csharp
// Late-start guard (same logic as pending-target block).
var nowUtc            = DateTimeOffset.UtcNow;
var currentWindowStart = RoundDownTo15s(nowUtc);
var secondsIntoWindow  = (nowUtc - currentWindowStart).TotalSeconds;
if (secondsIntoWindow > MaxLateStartSeconds)
{
    _logger.LogDebug(
        "QsoAnswererService: jump-in '{Partner}' — late start ({SecondsIn:F1} s into window); deferring to next occurrence.",
        jumpPartner, secondsIntoWindow);
    return; // Retain _jumpPartner; fires at next correct-phase window (30 s later).
}
```

Note: `_jumpPartner` is NOT cleared here — the 60-second expiry guard (`if (DateTimeOffset.UtcNow - jumpSetAt > TimeSpan.FromSeconds(60))`) at the top of the jump-in block handles stale entries.

### 3.4 — Add unit tests for the late-start guard

In `tests/OpenWSFZ.Daemon.Tests/`, add tests covering:

**Test A — Pending target: late click is deferred.**  
Set up an idle `QsoAnswererService`. Call `AnswerCqAsync` with a `cqCycleStart` whose opposite phase matches the current UTC window, but inject a fake `UtcNow` that is >1.5 s into that window. Push a wakeup batch. Assert TX does **not** fire (no `ITxController.KeyDownAsync` call). Wait 30 s (or manipulate time) for the next correct-phase window; assert TX **does** fire.

*Implementation note:* Use the `TimeProvider` injection pattern (the same mechanism as for the watchdog duration) so that the "current time" can be controlled in tests without sleeping. If `TimeProvider` is not yet injected into `HandleIdleAsync`, add it as part of this change — consistent with the deferred R1-D2 item for `QsoAnswererService`.

**Test B — Pending target: timely click fires immediately.**  
Same setup, but `UtcNow` is 0.5 s into the window. Assert TX fires on the first wakeup batch.

**Test C — Jump-in: late double-click is deferred.**  
Call `EngageAtAsync` with a `theirCycleStart` whose opposite phase matches the current window, but `UtcNow` is 5 s into that window. Assert TX does not fire on the wakeup. Assert TX fires on the next correct-phase batch.

**Test D — Jump-in: timely double-click fires immediately.**  
`UtcNow` is 0.2 s into the window. Assert TX fires on the wakeup batch.

---

## 4. Acceptance criteria

**AC-1.** When `answer-cq` is called more than 1.5 seconds into the target window, the TX does **not** fire in that window. Log output contains "deferring to next occurrence" at Debug level.

**AC-2.** The TX fires at the **start** of the next correct-phase window (within ≤500 ms of the window boundary), as confirmed by the `TX KeyDown — starting playback` log timestamp.

**AC-3.** When `answer-cq` is called within 1.5 seconds of a window start, TX fires in that same window (no spurious deferral).

**AC-4.** The same guard applies to the `engage-decode` / `EngageAtAsync` jump-in path.

**AC-5.** The pending-target 60-second expiry is not reset or extended by the late-start guard — it continues to expire 60 seconds from the original click.

**AC-6.** All four unit tests pass.

**AC-7.** Build: `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

**AC-8.** Full test suite: 0 failures (≥716 passed; new tests add to the count).

---

## 5. References

- `logs/openswfz-20260627T154903Z.log` — test session in which the defect was observed (attempts 1, 2, 5)
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `HandleIdleAsync` (pending-target block lines ~506–531; jump-in block lines ~440–468), `AnswerCqAsync` (wakeup formula line ~257), `RoundDownTo15s` (line ~1177)
- Deferred item R1-D2 — `QsoAnswererService` `TimeProvider` injection (pre-existing deferral); recommended to resolve as part of this change to enable deterministic unit tests for the late-start guard
- D-CALLER-012 review (2026-06-27) — approved; D-CALLER-012 did not introduce this defect

---

## Annex — D-CALLER-014 (observation, not blocking)

A second anomaly was observed in the same session: attempt 4 fired TX in A-phase, colliding with PD2FZ's A-phase transmissions. Root cause: during attempt 3's B-phase TX window (15:51:15), the decoder found PD2FZ's CQ in the captured audio (cycle 15:51:15 — 1 decode from 15 candidates). The browser added a new row with `cqCycleStartUtc = 15:51:15` (B-phase). The operator clicked this row; the server correctly computed A-phase as the response to a B-phase CQ. PD2FZ then resumed A-phase transmissions, causing the collision.

This is most likely a test-environment artefact (VB-CABLE loopback routing causing PD2FZ's A-phase signal to appear in the B-phase capture window during our TX). On-air, TX audio does not enter the RX capture path. No code change is required to fix D-CALLER-014 in a real operating environment. If the Captain observes this behaviour on-air rather than in a loopback test, raise a separate investigation.

Mitigation for loopback testing: ensure the TX and RX audio devices are fully isolated so that our own playback does not appear in the capture stream. Confirm with VB-CABLE's multi-instance configuration.
