# Developer Briefing — p5-ft8-decoder (Round 16)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Address QA review findings — 3 blockers, 2 recommended fixes, 3 advisory items

---

## Overview

The Round 15 implementation has been reviewed. Eight defects were identified across three
independent review angles and verified by direct code inspection. Three are blockers that
prevent merge. Two are recommended fixes that should accompany the blockers. Three are
advisory items that may be addressed at your discretion.

Address the blockers **in the order listed** — B1 affects B2, and B2 affects B3.

---

## Blockers (must fix before merge)

---

### B1 — Decode pump permanently silenced after the first `CaptureFailed` restart

**File:** `src/OpenWSFZ.Ft8/CycleFramer.cs`, line 90

**What happens:**
When capture fails, `captureManager.Samples` (the internal `Channel`) completes
because the capture task has ended. `CycleFramer.RunAsync`'s `await foreach` exits
*normally* — not via `OperationCanceledException` — because the source channel closed
before the framer's CT was cancelled. The framer falls through to line 90 and calls
`output.TryComplete()` on the shared `framerOutput` channel.

The decode pump's `ReadAllAsync()` loop then exits and the fire-and-forget pump `Task`
ends permanently. Every subsequent `StartPipeline()` call creates a new `CycleFramer`
that calls `framerOutput.Writer.TryWrite(window)` — which silently returns `false` on
every call because the writer is already completed. No FT8 decodes are produced for the
remainder of the daemon's lifetime, with no error logged anywhere.

The comment on lines 93–97 correctly documents the intent. The bug is that this guard
only fires for the `OperationCanceledException` path; a natural channel-end on the same
device failure event takes the wrong path.

**Fix — do not complete the output channel on a natural source-end:**

```csharp
// Before (current — WRONG):
// Source channel ended naturally (e.g. CaptureManager disposed on shutdown).
// Signal downstream that no more windows will arrive.
_logger?.LogInformation("CycleFramer source ended; completing output channel.");
output.TryComplete();
```

```csharp
// After — treat natural end identically to cancellation.
// Program.cs owns the output channel lifetime and calls TryComplete() on
// ApplicationStopping. Do NOT complete it here; the decode pump must survive
// device-failure restarts.
_logger?.LogInformation(
    "CycleFramer source ended (device failure or natural completion) — " +
    "exiting without completing output channel.");
```

Remove the `output.TryComplete()` call entirely from the non-cancellation path.
The `ApplicationStopping` handler in `Program.cs` already calls
`framerOutput.Writer.TryComplete()` for clean shutdown.

---

### B2 — Unsynchronised `framerCts` / `framerTask` writes; concurrent restart paths leak a framer and violate `SingleWriter`

**File:** `src/OpenWSFZ.Daemon/Program.cs`, line 289 (`StartPipeline`) and line 300 (`StopFramerAsync`)

**What happens:**
Three independent `Task.Run` paths can invoke `StartPipeline` concurrently:
the `CaptureFailed` 5-second backoff, the `configStore.OnSaved` handler, and the
watchdog `restartPipeline`. Neither `StopFramerAsync` nor `StartPipeline` holds any
lock.

If two callers race through `StartPipeline`:
- Both write `framerCts` and `framerTask` (plain field assignments, no lock)
- The first framer's `CancellationTokenSource` is orphaned — `StopFramerAsync` can no
  longer cancel it
- Two `CycleFramer` instances write to `framerOutput.Writer` concurrently
- `framerOutput` is declared `SingleWriter = true`; concurrent writers produce
  undefined behaviour in the channel implementation

**Fix — serialise all restart paths through a `SemaphoreSlim`:**

Add a restart semaphore at the top-level declarations (alongside `framerCts`):

```csharp
var restartSemaphore = new SemaphoreSlim(1, 1);
```

Wrap both `StopFramerAsync` and `StartPipeline` calls wherever a restart is performed.
The cleanest approach is a single `RestartPipelineAsync` helper:

```csharp
async Task RestartPipelineAsync(string? device,
                                bool stopCaptureManager = false)
{
    await restartSemaphore.WaitAsync();
    try
    {
        await StopFramerAsync();
        if (stopCaptureManager)
            await captureManager.StopAsync();
        audioMonitor.Reset();
        dataFlowMonitor.Reset();
        spectrumAnalyser.Reset();
        if (device is not null)
            StartPipeline(device);
    }
    finally
    {
        restartSemaphore.Release();
    }
}
```

Replace the three inline restart sequences with calls to this helper:

| Caller | `stopCaptureManager` |
|---|---|
| `CaptureFailed` handler | `false` (capture already stopped) |
| `configStore.OnSaved` | `true` (device change requires full stop) |
| `restartPipeline` (watchdog) | `true` (watchdog restarts everything) |

Update `ApplicationStopping` to `await restartSemaphore.WaitAsync()` before its
teardown sequence so it cannot race with an in-progress restart.

---

### B3 — Per-client `AudioWatchdog` construction causes N concurrent pipeline restarts

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`, line 95

**What happens:**
`HandleAsync` is called once per connected WebSocket client. Each call constructs a new
`AudioWatchdog` with its own independent `_silentWindows` counter. With N connected
clients, all N watchdogs observe the same data-flow state and accumulate silence in
parallel. After 15 seconds of silence, all N fire `restartPipeline` concurrently —
directly compounding B2 above, regardless of whether that semaphore is in place.

**Fix — make the watchdog a singleton:**

Remove the `AudioWatchdog` construction from `HandleAsync` entirely.

Construct the watchdog once in `Program.cs`, after `restartPipeline` is defined:

```csharp
// Program.cs — after restartPipeline is declared
var audioWatchdog = configStore.Current.AudioDeviceName is not null
    ? new AudioWatchdog(
          isCapturing: () => captureManager.IsCapturing,
          onRestart:   restartPipeline,
          threshold:   3)
    : null;
```

Pass it into `WebApp.Create` (add a parameter) and on to `WebSocketHub.HandleAsync`
(replace the current `restartPipeline` parameter with `AudioWatchdog? watchdog`).

Inside `HandleAsync`, tick the passed-in watchdog instead of constructing one:

```csharp
// Before:
var watchdog = captureManager is not null && restartPipeline is not null
    ? new AudioWatchdog(...)
    : null;

// After — watchdog is an injected parameter, already constructed:
// (remove the local construction entirely)
```

The `HandleAsync` signature change:

```csharp
public static async Task HandleAsync(
    WebSocket ws,
    IConfigStore configStore,
    AudioActivityMonitor? audioMonitor,
    DataFlowMonitor? dataFlowMonitor,
    CaptureManager? captureManager,
    AudioWatchdog? watchdog,          // ← replaces Func<Task>? restartPipeline
    ILogger logger,
    CancellationToken ct)
```

Update `WebApp.cs` accordingly to thread the singleton through.

---

## Recommended Fixes

---

### R1 — `ComputeLeadingSamples` ignores milliseconds when `offsetSecs == 0`

**File:** `src/OpenWSFZ.Ft8/CycleFramer.cs`, line 110

**What happens:**
If the daemon starts at a time where `utcNow.Second % 15 == 0` but milliseconds are
non-zero (e.g. `HH:MM:15.750`), `offsetSecs = 0` and the function returns `0`
immediately. The millisecond term is never reached. The first emitted window is
misaligned by up to 999 ms (~12 000 samples at 12 kHz).

**Fix — remove the early return:**

```csharp
// Before:
if (offsetSecs == 0) return 0; // already at a boundary

int elapsedSamples = offsetSecs * SampleRate
                   + (int)(utcNow.Millisecond / 1000.0 * SampleRate);
return Math.Min(elapsedSamples, SamplesPerCycle);
```

```csharp
// After:
int elapsedSamples = offsetSecs * SampleRate
                   + (int)(utcNow.Millisecond / 1000.0 * SampleRate);
return Math.Min(elapsedSamples, SamplesPerCycle);
```

The case where `elapsedSamples == 0` (daemon started at an exact 15-second UTC boundary
with zero milliseconds) is handled correctly by returning 0.

Update the existing `ComputeLeadingSamples` unit tests to add a case covering
`offsetSecs == 0` with non-zero milliseconds.

---

### R2 — `SendWithTimeoutAsync` calls `ws.CloseAsync` with no timeout on an already-unresponsive socket

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`, line 252

**What happens:**
The `ws.CloseAsync(..., default)` call executes when the per-socket send-lock acquisition
timed out after 1 second — meaning a prior send on this socket has been unresponsive for
at least that long. Sending a graceful close handshake to the same unresponsive socket
with `CancellationToken.None` can block a thread-pool thread indefinitely. Accumulated
across multiple stuck clients this degrades the thread pool for all active connections.

**Fix — abort instead of close, or apply a short timeout:**

Option A (preferred — immediate, no handshake required):
```csharp
// Replace the two ws.CloseAsync calls in the catch blocks with:
try { ws.Abort(); } catch { /* best-effort */ }
```

Option B (if a clean status code is required):
```csharp
using var closeCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
try { await ws.CloseAsync(WebSocketCloseStatus.EndpointUnavailable,
                          "Send timeout", closeCts.Token); }
catch { /* best-effort */ }
```

The same pattern applies to both `OperationCanceledException` catch blocks inside
`SendWithTimeoutAsync` (lines ~252 and ~272).

---

## Advisory Items

These do not block merge but are noted for the developer's awareness.

---

### A1 — Hann window uses symmetric denominator `FftSize - 1` instead of periodic `FftSize`

**File:** `src/OpenWSFZ.Ft8/Dsp/SpectrumAnalyser.cs`, line 149

For an FFT used in spectral analysis, the periodic form is correct:

```csharp
// Before (symmetric — introduces a small leakage discontinuity):
w[i] = 0.5f * (1f - MathF.Cos(2f * MathF.PI * i / (FftSize - 1)));

// After (periodic — correct for spectral analysis):
w[i] = 0.5f * (1f - MathF.Cos(2f * MathF.PI * i / FftSize));
```

Impact is limited to the spectrum display. No bearing on decode quality.

---

### A2 — `ComputeLlrs` wraps tone indices with modulo 8 when `freqShift > 0`

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, line 180

For `freqShift > 0`, high-numbered tone lookups wrap past the grid boundary and read
lower-frequency bins. These candidates are duplicates of outer-loop iterations that find
the same signal at a different `baseHz` with `freqShift = 0`, so the corrupted LLRs
typically fail LDPC and are discarded. However, the computation is wasteful and the
wrapping is logically incorrect.

Consider restricting `CostasSynchroniser.FindCandidates` to only return `freqShift = 0`
candidates (removing the inner frequency sweep entirely), since the outer
frequency-domain sweep in `Ft8Decoder` already covers all 6.25 Hz offsets. This would
also reduce the number of LDPC decode attempts per cycle.

---

### A3 — Decode pump `ReadAllAsync` holds no cancellation token

**File:** `src/OpenWSFZ.Daemon/Program.cs`, line 214

```csharp
await foreach (var pcmWindow in framerOutput.Reader.ReadAllAsync())
```

On application shutdown, the pump only exits after the current `ft8Decoder.DecodeAsync`
finishes. A full-sweep decode can take several seconds; ASP.NET Core's shutdown timeout
may force-terminate the process before the pump exits cleanly. Low-severity — shutdown
latency rather than correctness. Consider passing the application stopping token and
propagating it to `DecodeAsync`.

---

## Test Requirements

The following tests must be added or updated before this branch can be considered
complete:

| # | Test class | Scenario to add |
|---|---|---|
| T1 | `CycleFramerTests` | `ComputeLeadingSamples` returns correct value when `Second % 15 == 0` and `Millisecond > 0` |
| T2 | `CycleFramerTests` | `RunAsync` does **not** complete the output channel when the source channel is completed without cancellation |
| T3 | `AudioWatchdogTests` | Single watchdog instance ticks correctly across two simultaneous simulated heartbeat callers |

T1 and T2 are regression tests for B1 and R1. T3 validates that the singleton watchdog
design (B3 fix) behaves correctly.

---

## Summary

| # | Severity | File | Line | Description |
|---|----------|------|------|-------------|
| B1 | 🔴 Blocker | `CycleFramer.cs` | 90 | Natural channel-end permanently completes decode pump |
| B2 | 🔴 Blocker | `Program.cs` | 289 | Unsynchronised restart paths; concurrent `StartPipeline` leaks a framer and violates `SingleWriter` |
| B3 | 🔴 Blocker | `WebSocketHub.cs` | 95 | Per-client watchdog; N clients trigger N concurrent restarts |
| R1 | 🟡 Recommended | `CycleFramer.cs` | 110 | `offsetSecs == 0` early-return ignores milliseconds; first window misaligned by up to 999 ms |
| R2 | 🟡 Recommended | `WebSocketHub.cs` | 252 | `ws.CloseAsync` with no timeout on an already-unresponsive socket |
| A1 | 🔵 Advisory | `SpectrumAnalyser.cs` | 149 | Symmetric Hann window (`N-1`) used where periodic (`N`) is correct |
| A2 | 🔵 Advisory | `Ft8Decoder.cs` | 180 | Tone-index modulo wrap for `freqShift > 0` produces incorrect LLRs |
| A3 | 🔵 Advisory | `Program.cs` | 214 | Decode pump `ReadAllAsync` has no CT; extends shutdown duration |
