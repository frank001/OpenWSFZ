# Developer Briefing — p5-ft8-decoder (Round 3)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Commit reviewed:** `bc77ea7` (FR-019 and FR-020)

---

## Status of briefing-2 items

| # | Item | Status |
|---|---|---|
| B9 | `CaptureManager.CaptureFailed` event + test | ✅ Done |
| B6 | WAV fixture — obtain, commit, un-skip e2e test | ❌ Still required before merge |
| FR-017 | Start/stop control (AppConfig.DecodingEnabled, UI toggle) | ❌ Still required before merge |
| PR | Open draft PR to `main` (task 13.5) | ❌ Do last |

FR-019 and FR-020 are correctly implemented and approved, with one dead variable to tidy.
This document adds one new blocking defect (B10) found during the FR-020 smoke test.

---

## FR-019 and FR-020 — Verdict: ✅ Approved (pending B10 fix and dead variable)

Both features are well-structured, match the specification, and are covered by meaningful
tests. The issues below are not in the FR-019/FR-020 code itself; they are in
`WasapiAudioSource.cs` (pre-existing) and `Program.cs` (cosmetic).

---

## B10 — Silent, permanent hang when WASAPI fires `RecordingStopped` unexpectedly

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker — capture stops silently with no log, no event, no auto-restart.
**Observed symptom:** Audio activity indicator (FR-020) goes dark a few seconds after
startup and stays dark. No `[fail]` or `[info]` line appears in the log. `IsCapturing`
reads `true` permanently.

### Root cause

In `WasapiAudioSource.CaptureAsync` the `RecordingStopped` NAudio event is handled by
completing the inner channel:

```csharp
capture.RecordingStopped += (_, _) =>
    innerChannel.Writer.TryComplete();
```

This works correctly for a graceful stop (cancellation-driven). It fails silently
for any unexpected stop — device format change, exclusive-mode conflict, audio session
interrupt — because the STA thread is still alive, blocking on `ct.WaitHandle.WaitOne()`:

```
WASAPI fires RecordingStopped unexpectedly
  └── innerChannel.Writer.TryComplete()          ← channel is done
       └── CaptureAsync ReadAllAsync loop ends normally (no exception)
            └── CaptureManager await foreach ends normally
                 └── iterator disposal runs CaptureAsync finally block:
                      └── try { await staTask; } catch { }
                           └── staTask is STILL RUNNING
                                └── STA thread blocks on ct.WaitHandle.WaitOne()
                                     └── WaitOne only returns when ct is CANCELLED
                                          └── ct is only cancelled by StopAsync()
                                               └── StopAsync() is never called
                                                    └── await staTask HANGS FOREVER

CaptureManager._captureTask:
  ├── never reaches LogInformation("Capture stream ended")
  ├── never reaches the finally { _isCapturing = false; } block
  └── CaptureFailed is never raised (no exception was thrown)
```

Everything appears frozen. The operator sees the indicator go dark; the log is silent.
FR-020's indicator is what made this visible — prior to this commit, there was no
runtime signal that data had stopped flowing.

### The fix

Introduce a `staCts` (`CancellationTokenSource`) that is linked to the caller's `ct`
*and* can be cancelled by the `RecordingStopped` handler. The STA thread waits on
`staCts.Token` instead of `ct` directly. When `RecordingStopped` fires for any reason,
the handler cancels `staCts`, the STA thread wakes, and `staTask` completes promptly.

Additionally, pass the `StoppedEventArgs.Exception` (if any) into the channel so that
WASAPI errors propagate through `CaptureAsync` to `CaptureManager`'s existing
`catch (Exception ex)` block, which raises `CaptureFailed`.

**Replace the entire `staTask` setup and `RecordingStopped` handler in `WasapiAudioSource.CaptureAsync`:**

```csharp
public async IAsyncEnumerable<float[]> CaptureAsync(
    string deviceId,
    [EnumeratorCancellation] CancellationToken ct)
{
    var innerChannel = Channel.CreateBounded<float[]>(
        new BoundedChannelOptions(32)
        {
            FullMode     = BoundedChannelFullMode.DropOldest,
            SingleWriter = true,
            SingleReader = true,
        });

    Exception?  setupException = null;
    var         setupTcs       = new TaskCompletionSource(
        TaskCreationOptions.RunContinuationsAsynchronously);

    // staCts is cancelled either when ct is cancelled (normal StopAsync path)
    // or when RecordingStopped fires (unexpected stop path).  The STA thread
    // blocks on staCts.Token so both signals unblock it promptly.
    using var staCts = CancellationTokenSource.CreateLinkedTokenSource(ct);

    var staTask = StaThread.Run<bool>(() =>
    {
        WasapiCapture? capture = null;

        try
        {
            using var enumerator = new MMDeviceEnumerator();

            MMDevice device;
            try
            {
                device = enumerator.GetDevice(deviceId);
            }
            catch (Exception ex)
            {
                throw new AudioCaptureException(deviceId, ex.Message);
            }

            capture = new WasapiCapture(device);

            var buffer = new BufferedWaveProvider(capture.WaveFormat)
            {
                BufferDuration          = TimeSpan.FromSeconds(5),
                DiscardOnBufferOverflow = true,
            };

            ISampleProvider samples = buffer.ToSampleProvider();

            if (capture.WaveFormat.Channels == 2)
                samples = new StereoToMonoSampleProvider(samples);

            var resampler = new WdlResamplingSampleProvider(samples, 12_000);

            capture.DataAvailable += (_, e) =>
            {
                buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

                var outBuf = new float[2048];
                int read;
                while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
                {
                    var chunk = new float[read];
                    outBuf.AsSpan(0, read).CopyTo(chunk);
                    innerChannel.Writer.TryWrite(chunk);
                    outBuf = new float[2048];
                }
            };

            capture.RecordingStopped += (_, e) =>
            {
                // Propagate any WASAPI error through the channel so CaptureManager
                // surfaces it via CaptureFailed.  A null Exception means a graceful
                // stop (e.g. capture.StopRecording() was called from the finally block).
                if (e.Exception is not null)
                    innerChannel.Writer.TryComplete(e.Exception);
                else
                    innerChannel.Writer.TryComplete();

                // Wake the STA thread so staTask completes promptly.
                // Without this, await staTask in the finally block below would
                // hang until the caller's ct is cancelled (which may never happen).
                staCts.Cancel();
            };

            capture.StartRecording();

            setupTcs.SetResult();

            // Block the STA thread alive while the session is running.
            // Uses staCts.Token so RecordingStopped can also unblock it.
            staCts.Token.WaitHandle.WaitOne();
        }
        catch (Exception ex)
        {
            setupException = ex;
            setupTcs.TrySetResult();
            innerChannel.Writer.TryComplete(ex);
        }
        finally
        {
            if (capture is not null)
            {
                try { capture.StopRecording(); } catch { }
                try { capture.Dispose();       } catch { }
            }
        }

        return true;
    });

    await setupTcs.Task;

    if (setupException is AudioCaptureException)
        throw setupException;

    if (setupException is not null)
        throw new AudioCaptureException(deviceId, setupException.Message);

    try
    {
        await foreach (var chunk in innerChannel.Reader.ReadAllAsync(ct))
            yield return chunk;
    }
    finally
    {
        try { await staTask; } catch { }
    }
}
```

The only meaningful changes from the original are:

1. `using var staCts = CancellationTokenSource.CreateLinkedTokenSource(ct);` — declared before `staTask`.
2. `RecordingStopped` handler calls `staCts.Cancel()` after completing the inner channel.
3. `RecordingStopped` handler passes `e.Exception` when non-null.
4. STA thread blocks on `staCts.Token.WaitHandle.WaitOne()` instead of `ct.WaitHandle.WaitOne()`.

Everything else is unchanged.

### Post-fix behaviour

| Scenario | Before fix | After fix |
|---|---|---|
| Normal `StopAsync()` call | ✅ Correct | ✅ Correct (ct → staCts linked) |
| WASAPI stops with error | ❌ Silent hang | ✅ Exception surfaces via CaptureFailed |
| WASAPI stops without error | ❌ Silent hang | ✅ "Capture stream ended" logged; `_isCapturing = false` |
| Audio indicator | ❌ Goes dark, no explanation | ✅ Goes dark; log line or CaptureFailed event explains why |

### Tests to add (`CaptureManagerTests.cs`)

Add a second test double alongside the existing `InfiniteAudioSource` and `FaultyAudioSource`:

```csharp
/// <summary>
/// <see cref="IAudioSource"/> that yields a fixed number of chunks and then
/// ends the enumeration normally (simulating an unexpected WASAPI stop with
/// no exception, e.g. RecordingStopped fired with e.Exception == null).
/// </summary>
internal sealed class FiniteAudioSource : IAudioSource
{
    private readonly int _chunkCount;

    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public FiniteAudioSource(int chunkCount) => _chunkCount = chunkCount;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        for (int i = 0; i < _chunkCount; i++)
        {
            await Task.Yield();
            yield return new float[2048];
        }
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
```

Add the fact:

```csharp
[Fact(DisplayName = "B10: CaptureManager sets IsCapturing=false when source ends without cancellation")]
public async Task StartAsync_WhenSourceEndsNaturally_SetsIsCapturingFalse()
{
    // Arrange — source yields 3 chunks then ends (simulates unexpected WASAPI stop).
    await using var cm = new CaptureManager(new FiniteAudioSource(chunkCount: 3));

    // Act
    await cm.StartAsync("test-device");

    // Allow the capture task to drain the finite source and reach its finally block.
    var deadline = Task.Delay(TimeSpan.FromSeconds(5));
    while (cm.IsCapturing)
    {
        if (await Task.WhenAny(Task.Delay(10), deadline) == deadline)
            break;
    }

    // Assert
    cm.IsCapturing.Should().BeFalse(
        "once the source ends naturally, the capture task must exit and clear IsCapturing");
}
```

Assign `DisplayName = "B10: ..."`. No debt-file change is needed.

---

## S5 — Dead variable `configLogger` in `Program.cs`

**File:** `src/OpenWSFZ.Daemon/Program.cs`
**Severity:** Suggestion — remove or wire up properly.

```csharp
// Re-attach a logger to the config store now that the factory is available.
var configLogger = loggerFactory.CreateLogger<JsonConfigStore>();
```

`JsonConfigStore` does not accept a logger in its constructor. `configLogger` is created,
never passed anywhere, and never read. The comment implies a re-attachment that does not
happen. Either:

- **Option A (recommended):** Delete these two lines. Config-store operations are not
  currently logged and the intent is not established.
- **Option B:** Add `ILogger<JsonConfigStore>?` to the `JsonConfigStore` constructor, pass
  `configLogger`, and add logging inside the store at the appropriate level (e.g. `Debug`
  on each save).

Choose one and be consistent. A dead variable with a misleading comment is a trap for
the next developer reading this file.

---

## Updated merge checklist

| # | Item | Effort | Status |
|---|---|---|---|
| B10 | Fix `WasapiAudioSource` — add `staCts`, wire `RecordingStopped` to cancel it and pass `e.Exception` | ~30 min | ❌ |
| B10 | Add `FiniteAudioSource` + `StartAsync_WhenSourceEndsNaturally_SetsIsCapturingFalse` test | ~20 min | ❌ |
| S5 | Remove dead `configLogger` variable (or wire it) | ~5 min | ❌ |
| B6 | Obtain WAV fixture, commit, un-skip end-to-end test | ~2–4 hrs | ❌ |
| FR-017 | Start/stop control — `AppConfig.DecodingEnabled`, UI toggle, daemon wiring | ~1 day | ❌ |
| PR | Open draft PR to `main` (task 13.5) | ~5 min | ❌ |

Work top-to-bottom. B10 and S5 require changes to `WasapiAudioSource.cs` and `Program.cs`
only — no changes to the FR-019 or FR-020 files. All items remain required before merge.
