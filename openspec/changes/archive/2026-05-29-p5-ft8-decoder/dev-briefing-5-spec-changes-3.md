# Specification Change Request — dev-briefing-5.md (Round 3)

**Date:** 2026-05-23
**Raised by:** Developer review
**Target document:** `openspec/changes/p5-ft8-decoder/dev-briefing-5.md`
**Supersedes:** `dev-briefing-5-spec-changes-2.md` (both items from that document are now applied)
**Status:** Awaiting QA action

One substantive change required (SCR-7). One cosmetic change recommended (SCR-8).

---

## SCR-7 — Correct AO2 Claim That S6 Restarts a Case 2 Exit (REQUIRED)

### Problem

The AO2 section currently states:

> *"Once the watchdog (S6) is in place this becomes less critical — the 15-second
> window will trigger a restart."*

This is factually incorrect. S6 cannot restart a Case 2 exit.

### Root Cause Analysis

A Case 2 exit occurs when `CaptureAsync`'s async enumerable ends without an
exception and without the caller's `ct` being cancelled. In `WasapiAudioSource`,
this happens when `RecordingStopped` fires with `e.Exception == null` — a
graceful WASAPI stop not initiated by the application.

The termination sequence in `CaptureManager` is:

```
1. RecordingStopped fires (e.Exception == null)
   → innerChannel.Writer.TryComplete()   // no exception
   → staCts.Cancel()                     // STA unblocks

2. WasapiAudioSource.CaptureAsync enumerable ends normally

3. CaptureManager captureTask:
   await foreach completes
   linkedCt.IsCancellationRequested == false
   → LogWarning("Capture ended unexpectedly…")   // Case 2 path
   // CaptureFailed is NOT invoked

4. finally → _isCapturing = false          // line 141 of CaptureManager.cs
```

Steps 1–4 complete in microseconds. `_isCapturing` is `false` long before the
next watchdog tick (up to 5 seconds away).

The watchdog trigger condition requires **all three** of:

```
audioActive          == false       ← true (no audio after stop)
captureManager.IsCapturing == true  ← FALSE — already false after Case 2
silentWindows        >= 3           ← irrelevant; second condition already fails
```

The second condition never holds in a Case 2 scenario. The watchdog resets its
counter and never fires. The daemon remains permanently idle.

### Required Change

Replace the two sentences in AO2 that follow the `CaptureFailed` description:

**Current (incorrect):**
> It does **not** call `CaptureFailed`. Nothing restarts the pipeline. Once the
> watchdog (S6) is in place this becomes less critical — the 15-second window
> will trigger a restart. But note that without S6, a Case 2 exit leaves the
> daemon permanently idle.

**Replace with:**
> It does **not** call `CaptureFailed`. Nothing restarts the pipeline.
>
> **S6 does not cover this case.** The watchdog is gated on
> `captureManager.IsCapturing == true`, but a Case 2 exit sets `_isCapturing =
> false` (line 141 of `CaptureManager.cs`) before the next heartbeat tick
> fires. The watchdog sees `!_isCapturing()`, resets its counter, and never
> triggers. A Case 2 exit leaves the daemon permanently idle regardless of
> whether S6 is in place.
>
> A complete fix requires one of:
> - **(a)** Invoke `CaptureFailed` from the Case 2 branch in `CaptureManager`
>   so the existing restart path handles it identically to Case 3; or
> - **(b)** A separate `IsCapturing`-off watchdog that detects the transition
>   and restarts the pipeline.
>
> Both options are out of scope for this round. Tracking as a follow-on item.

---

## SCR-8 — Update Work Order Table File(s) Column for S6 (MINOR)

### Problem

The Work Order table File(s) column for S6 (line 591) reads:

```
`WebSocketHub.cs` or new `AudioWatchdog.cs`
```

The S6 section header was updated by SCR-6 to list all four affected files.
The work order table was not updated and is now inconsistent with it.

### Required Change

Update the S6 row in the Work Order table:

| # | Item | File(s) | Effort |
|---|---|---|---|
| **S6** | Implement watchdog in heartbeat loop (3 × 5 s threshold) | `AudioWatchdog.cs` (new), `WebSocketHub.cs`, `WebApp.cs`, `Program.cs` | 2–3 hrs |

---

## Summary

| # | Change | Section | Blocking? |
|---|---|---|---|
| **SCR-7** | Correct AO2 — S6 cannot restart a Case 2 exit; replace incorrect claim with accurate analysis and follow-on tracking note | AO2 | **Yes — incorrect claim misrepresents S6 scope to developer and operator** |
| SCR-8 | Update Work Order File(s) column for S6 to list all four files | Work Order table | No |

SCR-7 must be applied before the briefing is handed to the developer. SCR-8
may be applied at any point.
