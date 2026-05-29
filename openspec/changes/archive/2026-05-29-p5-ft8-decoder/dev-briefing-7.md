# Developer Briefing — p5-ft8-decoder (Round 7)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Priority:** BLOCKING — audio capture must always be running

---

## Situation

B10–B20 and S6 have all been applied. The pipeline still stops after a few seconds.
Deep code review has now identified two compounding problems:

1. **The D1 and D2 diagnostics were removed when B19 was implemented.** The chunk
   counter and first-buffer probe that were added to identify the scenario are gone.
   We are blind.

2. **`RecordingStopped` has never been logged.** Across every session of this issue,
   nobody has ever captured whether it fires with `null` (graceful) or with an
   exception (error). This single fact determines the entire diagnosis.

This briefing prescribes the minimum changes to end the ambiguity, plus the single
code change most likely to fix the underlying cause.

---

## Part 1 — Mandatory Logging (implement first, test, read the log)

These changes must be made to `src/OpenWSFZ.Audio/WasapiAudioSource.cs`.
They are not permanent — mark each with a `// DIAG` comment so they can be
removed cleanly after the cause is confirmed.

### 1.1 — Log `RecordingStopped` (the missing smoking gun)

The `RecordingStopped` handler currently completes the channel silently.
Replace it with this version that logs before acting:

```csharp
capture.RecordingStopped += (_, e) =>
{
    // DIAG: this is the one log entry that has never existed in this codebase.
    // null exception = graceful stop (doStop was set) → Case 2 in CaptureManager.
    // non-null exception = WASAPI error → Case 3.  The exception type and message
    // tell us exactly why WASAPI stopped.
    if (e.Exception is not null)
    {
        _logger?.LogError(e.Exception,
            "DIAG RecordingStopped — WASAPI error on '{DeviceId}': {ExType} — {ExMessage}",
            deviceId, e.Exception.GetType().Name, e.Exception.Message);
        innerChannel.Writer.TryComplete(e.Exception);
    }
    else
    {
        _logger?.LogWarning(
            "DIAG RecordingStopped — null exception on '{DeviceId}' " +
            "(graceful/unexpected stop; doStop was set internally by NAudio).",
            deviceId);
        innerChannel.Writer.TryComplete();
    }

    try { staCts.Cancel(); }
    catch (ObjectDisposedException) { }
};
```

### 1.2 — Log `OnSessionDisconnected` reason (already completes channel but never logs)

```csharp
public void OnSessionDisconnected(AudioSessionDisconnectReason disconnectReason)
{
    // DIAG
    // (add this line before the existing TryComplete call)
    _logger?.LogError(
        "DIAG OnSessionDisconnected on '{DeviceId}': reason = {Reason}",
        "unknown", disconnectReason);

    var ex = new AudioCaptureException(
        "unknown",
        $"WASAPI audio session disconnected: {disconnectReason}");
    _channel.Writer.TryComplete(ex);
    try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
}
```

To do this cleanly, pass `deviceId` into `WasapiSessionEventClient` as a constructor
parameter (it already has `channel` and `staCts`; add `string deviceId`).

### 1.3 — Restore D1 (first DataAvailable probe)

Add back before the `buffer.AddSamples` line inside the DataAvailable handler:

```csharp
// D1 (DIAG): log the first buffer to confirm WASAPI is actually delivering data.
if (!dataAvailableFired)
{
    dataAvailableFired = true;
    _logger?.LogInformation(
        "DIAG DataAvailable: first buffer on '{DeviceId}' — " +
        "BytesRecorded={Bytes}, WaveFormat={Format}",
        deviceId, e.BytesRecorded, capture.WaveFormat);
}
```

And declare `var dataAvailableFired = false;` immediately before the
`capture.DataAvailable += ...` line.

### 1.4 — Restore D2 (chunk counter in CaptureManager)

Add `var chunksReceived = 0;` at the top of the capture task lambda in
`CaptureManager.StartAsync`. Increment on every chunk: `chunksReceived++`.
Append `"Chunks received: {ChunksReceived}."` and `chunksReceived` to every
exit-path log message (Case 1 operator-stop, Case 1 race, Case 2 unexpected end,
Case 3 exception header).

---

## Part 2 — What to read in the log

After applying the above, run the daemon, wait for capture to stop, then read
the log from the beginning of the capture session.

| What you see | What it means | Next step |
|---|---|---|
| `DIAG DataAvailable: first buffer` present | WASAPI IS delivering data | Scenario A |
| NO `DIAG DataAvailable` message at all | WASAPI opened but never called DataAvailable | Scenario B |
| `DIAG RecordingStopped — WASAPI error … ExType — ExMessage` | WASAPI threw — Case 3 | Read the exception type/message — that IS the root cause |
| `DIAG RecordingStopped — null exception` | NAudio's doStop was set — Case 2 | See analysis below |
| `DIAG OnSessionDisconnected: reason = …` | Windows terminated the session | The reason enum value IS the root cause |
| `Capture stopped … (operator-stopped)` ONLY, no RecordingStopped entry | Case 1 — StopAsync was called | Something in Program.cs is calling StopAsync unexpectedly |

---

## Part 3 — Most likely fix (implement in parallel with Part 1)

The single code change most likely to fix the persistent stop is in
`WasapiAudioSource.cs`:

```csharp
// BEFORE (line 77):
capture = new WasapiCapture(device);

// AFTER:
capture = new WasapiCapture(device, useEventSync: true);
```

### Why this matters

`WasapiCapture` has two operating modes:

| Mode | How it works | Problem |
|---|---|---|
| `useEventSync: false` (current) | Internal thread calls `Thread.Sleep(50ms)` between reads | On some Windows 11 drivers the sleep period mismatches the actual buffer period, causing the capture thread to read an empty buffer repeatedly until WASAPI returns `AUDCLNT_E_BUFFER_OVERRUN`. NAudio's handling of this error varies by version — it may set `doStop` rather than propagating the exception, producing a `RecordingStopped(null)`. |
| `useEventSync: true` | Internal thread waits on a Windows kernel event that WASAPI signals when a buffer is ready | Eliminates the sleep/polling entirely. More reliable on all modern Windows versions. Recommended by Microsoft for new WASAPI applications. |

Event-sync mode has been the preferred WASAPI capture mode on Windows 8+ for
over a decade. The timer-based mode exists for backward compatibility with
Windows XP-era hardware. We are targeting Windows 10+; there is no reason to
use timer mode.

**This is a one-line change. Ship it in a separate commit.**

---

## Part 4 — If Part 3 doesn't fix it (read the log from Part 1 first)

### Scenario A — DataAvailable fires, RecordingStopped null, no session event

NAudio is receiving data successfully, then stops via the `doStop` path. Something
is calling `capture.StopRecording()` that we are not. Candidates:

1. **NAudio internal**: some NAudio versions call `StopRecording()` internally
   when the audio client reports a format change. Check: does the `DIAG
   RecordingStopped` message appear before or after the `DIAG DataAvailable` has
   fired many times? A few-second gap after the first buffer = driver power
   management or format change.

2. **`staCts` cancelled by ct propagation**: `staCts = CTS.CreateLinked(ct)`.
   If `ct` (`linkedCt` from CaptureManager) gets cancelled for any reason,
   `staCts` also cancels. `WaitOne()` returns. STA `finally` calls
   `StopRecording()`. RecordingStopped(null) fires. Fix: log when `staCts`
   unblocks in the STA thread: `_logger?.LogDebug("DIAG STA WaitOne unblocked on
   '{DeviceId}'.", deviceId);` immediately after `staCts.Token.WaitHandle.WaitOne();`.

### Scenario B — DataAvailable never fires

WASAPI opened the device and started recording, but the audio engine never called
DataAvailable. Possible causes:

1. Device is in exclusive mode (another app owns it).
   Check: close all other audio applications (Teams, Discord, SDR software,
   virtual audio cables). Try again.

2. Device requires a specific format that `WasapiCapture(device)` doesn't
   negotiate. Try forcing the device format:
   ```csharp
   capture = new WasapiCapture(device, useEventSync: true);
   capture.WaveFormat = WaveFormat.CreateIeeeFloatWaveFormat(48000, 1);
   ```

3. The audio device is a virtual/loopback device that requires
   `WasapiLoopbackCapture` instead of `WasapiCapture`. If the selected device is
   a "Stereo Mix" or virtual cable output, use `WasapiLoopbackCapture(device)`.

### Scenario — Case 3, WASAPI exception

Read the `ExType` and `ExMessage` in the log. The exception tells you exactly
why. Common ones:

| Exception | Meaning |
|---|---|
| `AUDCLNT_E_DEVICE_INVALIDATED (0x88890004)` | Device was removed or default device changed |
| `AUDCLNT_E_DEVICE_IN_USE (0x88890001)` | Another app has exclusive mode |
| `AUDCLNT_E_BUFFER_OVERRUN` | NAudio didn't read fast enough (use `useEventSync: true`) |
| `COMException` with HRESULT `0x8889xxxx` | WASAPI COM error — look up the HRESULT |

---

## Commit guidance

**Commit 1 — diagnostics:**
```
diag(audio): add RecordingStopped/OnSessionDisconnected/D1/D2 logging

Restore D1 (first DataAvailable probe) and D2 (chunk counter) that were
removed in B19. Add RecordingStopped and OnSessionDisconnected log entries
that have never existed, providing the missing root-cause data.

All entries tagged DIAG for removal after the root cause is confirmed.
```

**Commit 2 — event-sync fix (independent, can ship before commit 1 result is known):**
```
fix(audio): use WASAPI event-sync capture mode

Switch WasapiCapture from timer-based (Thread.Sleep 50ms) to event-sync
mode, eliminating the polling interval that mismatches the WASAPI buffer
period on Windows 11 drivers and produces spurious AUDCLNT_E_BUFFER_OVERRUN
or silent doStop exits.

This is the most likely root cause of the persistent capture stops.
```

Files changed: `src/OpenWSFZ.Audio/WasapiAudioSource.cs` (one line).

---

## What has been ruled out

For the developer's reference — these have all been verified through code review
and implemented fixes. The current stop is NOT caused by:

- GC collecting `sessionControl` (B15 — outer scope, disposed in finally)
- Silent B11 registration failure (B16 — logged at Warning)
- `OnStateChanged(Expired)` ignored (B17 — handled, completes channel)
- Watchdog using amplitude gate instead of data-flow gate (B18 — DataFlowMonitor)
- Case 2 not invoking `CaptureFailed` (B19 — fixed)
- `CaptureFailed` not restarting (B20 — restarts after 5s)
- `IsCapturing` false blocking watchdog (watchdog is not the restart path post-B19)
