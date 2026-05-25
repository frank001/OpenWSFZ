# Developer Briefing — p5-ft8-decoder (Round 2)

**Date:** 2026-05-22
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Build:** ✅ CI green (G3 fixed in `3f9a3ac`)
**Test suite (local):** ✅ 121 passed, 1 skipped, 0 failed

---

## Status of briefing-1 items

| # | Item | Status |
|---|---|---|
| 1 | FR-001 / FR-009 DisplayName markers | ✅ Done — `3f9a3ac` |
| 2 | CycleFramer — don't TryComplete on cancellation (B5) | ✅ Done — `3f9a3ac` |
| 3 | FR-017 CycleFramer test | ✅ Done — `3f9a3ac` |
| 4 | WAV fixture — obtain, commit, un-skip e2e test (B6) | ❌ Still required before merge |
| 5 | Implement FR-017 (start/stop control, config, UI) | ❌ Still required before merge |
| 6 | Open draft PR to `main` (task 13.5) | ❌ Do last |
| S5 | Remove redundant freqShift inner loop in CostasSynchroniser | deferred |

This document adds one new blocking defect (B9) that must be fixed before item 6.

---

## B9 — Audio capture failures are silently discarded

**File:** `src/OpenWSFZ.Audio/CaptureManager.cs`
**Severity:** Blocker — prevents the operator from ever knowing capture has failed.
**Observed symptom:** Application starts, countdown timer runs, decode payload is
permanently empty; breakpoints in all WASAPI audio classes never fire; terminal
shows no error output.

### Root cause

`CaptureManager.StartAsync` spawns `_captureTask` via `Task.Run` and returns
**without awaiting it**. The `ContinueWith(t.IsFaulted)` guard in `Program.cs`
watches `StartAsync`'s own Task — which always succeeds. When the inner
`_captureTask` faults (e.g. `MMDeviceEnumerator.GetDevice` cannot find the stored
GUID), the exception is unobserved and silently discarded:

```
WasapiAudioSource.CaptureAsync
  └── enumerator.GetDevice(deviceId) throws
       └── AudioCaptureException propagates to the async enumerable caller

CaptureManager._captureTask
  └── await foreach throws AudioCaptureException
       └── catch (OperationCanceledException) — DOES NOT MATCH
            └── _captureTask becomes FAULTED; nobody observes it

Program.cs
  └── captureManager.StartAsync(…).ContinueWith(t => t.IsFaulted)
       └── t is StartAsync's Task — completed normally — t.IsFaulted is FALSE
            └── error message is NEVER printed
```

The `CycleFramer` and decode pump start normally but wait forever for data that
never arrives. The UI shows "Decoding"; nothing decodes.

### How the operator hit this

The config file stores the WASAPI device GUID
(`{0.0.1.00000000}.{eaf691c7-8f15-4559-9591-8287520e768b}`). Virtual device GUIDs
(Voicemeeter) can change after a driver update or Windows audio graph rebuild.
When the stored GUID no longer matches any real device, `GetDevice` throws, the
exception is swallowed, and the application silently does nothing.

**Immediate workaround for the operator:** open Settings in the browser,
re-select the audio device from the dropdown, Save. This writes a fresh GUID and
triggers the `OnSaved` pipeline restart.

### The fix

**Step 1 — add a `CaptureFailed` event to `CaptureManager`.**

Expose the fault so any subscriber (logger today, UI status in FR-017 tomorrow)
can react to it. Add the event declaration and change the `_captureTask` lambda
to catch non-cancellation exceptions:

```csharp
// CaptureManager.cs

/// <summary>
/// Raised when the capture session terminates abnormally (device not found,
/// device disconnected, or any other unrecoverable error).
/// Invoked on a thread-pool thread; subscribers must be thread-safe.
/// </summary>
public event Action<Exception>? CaptureFailed;
```

In `StartAsync`, extend the existing `try/catch` inside the `Task.Run` lambda:

```csharp
_captureTask = Task.Run(async () =>
{
    try
    {
        await foreach (var chunk in _source.CaptureAsync(deviceId, linkedCt))
        {
            await _channel.Writer.WriteAsync(chunk, linkedCt);
        }
    }
    catch (OperationCanceledException) when (linkedCt.IsCancellationRequested)
    {
        // Normal shutdown — swallow.
    }
    catch (Exception ex)
    {
        // Device not found, device disconnected, or any other capture failure.
        // Surface via event; the finally block still resets IsCapturing.
        CaptureFailed?.Invoke(ex);
    }
    finally
    {
        _isCapturing = false;
    }
});
```

**Step 2 — subscribe in `Program.cs`.**

Add the subscription immediately after `captureManager` is constructed (before
`StartPipeline` is ever called):

```csharp
captureManager.CaptureFailed += ex =>
    Console.Error.WriteLine($"[OpenWSFZ] Audio capture error: {ex.Message}");
```

That is the complete fix. No other files require changes for B9.

> **Note for FR-017:** when the start/stop control is implemented, the
> `CaptureFailed` event is the correct hook for transitioning the UI badge from
> "Decoding" to "Stopped" on unexpected device loss — not just on an explicit
> operator Stop. Wire `CaptureFailed` to the same pipeline-stop path used by the
> Stop button.

### Test to add (`CaptureManagerTests.cs`)

Add the `FaultyAudioSource` test double alongside the existing `InfiniteAudioSource`,
then add the fact:

```csharp
/// <summary>
/// <see cref="IAudioSource"/> that throws a given exception on the first iteration.
/// Used to simulate device-not-found and other capture failures.
/// </summary>
internal sealed class FaultyAudioSource : IAudioSource
{
    private readonly Exception _exception;

    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public FaultyAudioSource(Exception exception) => _exception = exception;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        await Task.Yield(); // ensure the exception is thrown asynchronously
        throw _exception;
#pragma warning disable CS0162
        yield break;        // satisfies the compiler's async-enumerable requirement
#pragma warning restore CS0162
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
```

```csharp
[Fact(DisplayName = "B9: CaptureManager raises CaptureFailed when IAudioSource throws AudioCaptureException")]
public async Task StartAsync_WhenSourceThrows_RaisesCaptureFailed()
{
    // Arrange
    var exception = new AudioCaptureException("test-device", "device not found");
    await using var cm = new CaptureManager(new FaultyAudioSource(exception));

    var failureTcs = new TaskCompletionSource<Exception>(
        TaskCreationOptions.RunContinuationsAsynchronously);
    cm.CaptureFailed += ex => failureTcs.TrySetResult(ex);

    // Act
    await cm.StartAsync("test-device");

    // Assert — the event must fire and carry the original exception.
    var caughtEx = await failureTcs.Task.WaitAsync(TimeSpan.FromSeconds(5));

    caughtEx.Should().BeSameAs(exception,
        "CaptureFailed must surface the original exception to the subscriber");

    cm.IsCapturing.Should().BeFalse(
        "IsCapturing must be false once the capture task has faulted");
}
```

Assign `DisplayName = "B9: ..."`. This does not need a `FR-` marker — it is a
defect regression test, not a requirements-traceability test. No debt-file
change is needed.

---

## Updated merge checklist

| # | Item | Effort | Status |
|---|---|---|---|
| B9 | Fix `CaptureManager` — add `CaptureFailed` event, catch non-cancellation exceptions | ~30 min | ❌ |
| B9 | Add `FaultyAudioSource` + `StartAsync_WhenSourceThrows_RaisesCaptureFailed` test | ~20 min | ❌ |
| B9 | Subscribe `captureManager.CaptureFailed` in `Program.cs` | ~5 min | ❌ |
| B6 | Obtain WAV fixture, commit, un-skip end-to-end test | ~2–4 hrs | ❌ |
| FR-017 | Start/stop control — `AppConfig.DecodingEnabled`, UI toggle, daemon wiring | ~1 day | ❌ |
| PR | Open draft PR to `main` (task 13.5) | ~5 min | ❌ |

Work top-to-bottom. All items are required before merge.
