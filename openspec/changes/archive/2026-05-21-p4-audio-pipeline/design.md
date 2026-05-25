## Context

Phase 4 has two distinct jobs: fix a latent runtime defect and implement a new subsystem.

**Defect.** `WasapiAudioDeviceProvider` dispatches `MMDeviceEnumerator` on whatever thread ASP.NET Core happens to use — always an MTA thread-pool thread. WASAPI COM objects require STA initialisation. The `catch {}` in the provider swallows the resulting `COMException`, returning an empty device list on every call. The operator's Settings page device selector is therefore always empty on Windows.

**Missing subsystem.** `IAudioSource` in `OpenWSFZ.Abstractions` is an empty stub. Nothing in the codebase opens a device, reads PCM samples, or delivers them to any consumer. The FT8 decoder (Phase 5) needs a continuous stream of 32-bit float mono PCM at 12 000 Hz before it can do anything.

Current relevant code paths:
- `PlatformAudioDeviceProvider` → `WasapiAudioDeviceProvider` (broken on Windows) / `SubprocessAudioDeviceProvider` (Linux, macOS)
- `IAudioSource` stub → nothing
- `DaemonStatus` record — no capture state field
- `Program.cs` — no capture lifecycle

## Goals / Non-Goals

**Goals:**
- `GET /api/v1/audio/devices` returns real devices on Windows.
- `IAudioSource` carries a working contract for P5 to depend on.
- Three platform implementations of that contract deliver `float[]` chunks at 12 000 Hz mono.
- The daemon auto-starts capture when a device is configured at startup, re-starts on device change, and stops cleanly on shutdown.
- `GET /api/v1/status` exposes `captureActive` so tests can assert audio is flowing.

**Non-Goals:**
- FT8 decoding (Phase 5).
- Resampling quality optimisation (WDL is good enough for initial correctness).
- Dynamic device hot-plug (device list is refreshed on each GET, not watched).
- Audio monitoring / level metering UI (deferred).

## Decisions

### 1. STA thread helper — `StaThread.Run<T>(Func<T>)`

```csharp
internal static class StaThread
{
    public static Task<T> Run<T>(Func<T> func)
    {
        var tcs = new TaskCompletionSource<T>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var t = new Thread(() =>
        {
            try   { tcs.SetResult(func()); }
            catch (Exception ex) { tcs.SetException(ex); }
        });
        t.IsBackground = true;
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        return tcs.Task;
    }
}
```

`WasapiAudioDeviceProvider.GetDevicesAsync` and `WasapiAudioSource` internal setup both call into this helper. The thread is short-lived for enumeration; for capture it is kept alive for the session.

*Alternatives considered:* `[STAThread]` main thread — not applicable (ASP.NET); `SynchronizationContext` — overly complex for this use.

### 2. `IAudioSource` — `IAsyncEnumerable<float[]>` contract

```csharp
public interface IAudioSource : IAsyncDisposable
{
    /// <summary>Sample rate delivered by this source (Hz). Always 12 000 in Phase 4.</summary>
    int SampleRate { get; }

    /// <summary>Channel count. Always 1 (mono) in Phase 4.</summary>
    int ChannelCount { get; }

    /// <summary>
    /// Opens the specified device and yields PCM chunks until cancellation.
    /// Each chunk is exactly <c>ChunkSize</c> float samples.
    /// Throws <see cref="AudioCaptureException"/> if the device cannot be opened.
    /// </summary>
    IAsyncEnumerable<float[]> CaptureAsync(string deviceId, CancellationToken ct);
}
```

`IAsyncEnumerable` gives the decoder a natural pull model (`await foreach`) with built-in cancellation. Phase 5 accumulates chunks into 15-second windows.

Chunk size: **2 048 samples** (~170 ms at 12 kHz). Small enough to keep latency low; large enough that channel overhead is trivial.

*Alternatives considered:* `ChannelReader<float[]>` — isomorphic but less ergonomic for consumers; `event DataAvailable` — callback style breaks composability.

### 3. `WasapiAudioSource` (Windows)

Runs entirely on a dedicated STA thread created by `StaThread`. Pipeline:

```
WasapiCapture (device native format)
  → BufferedWaveProvider
  → ISampleProvider (float32 conversion)
  → StereoToMonoSampleProvider  [if stereo]
  → WdlResamplingSampleProvider  [to 12 000 Hz]
  → Channel<float[]>.Writer      [chunked at 2 048 samples]
```

`WdlResamplingSampleProvider` is pure managed code — no Media Foundation dependency — and is AOT-safe (no reflection).

Device selection: match `deviceId` (the `MMDevice.ID` GUID string from `WasapiAudioDeviceProvider`) to the correct `MMDevice` at capture start via `MMDeviceEnumerator.GetDevice(id)` — also on the STA thread.

### 4. `ArecordAudioSource` (Linux)

```
arecord -D <deviceId> -f FLOAT_LE -r 12000 -c 1 -t raw -
  → stdout byte pipe
  → MemoryMarshal.Cast<byte, float>() per 4-byte word
  → Channel<float[]>.Writer  [chunked at 2 048 floats]
```

`deviceId` is already in ALSA hw-notation (`hw:0,0`) from `SubprocessAudioDeviceProvider.ForLinux()`.

### 5. `SoxAudioSource` (macOS)

```
sox -t coreaudio "<deviceName>" -t raw -e float -b 32 -r 12000 -c 1 -
  → stdout byte pipe  →  same as ArecordAudioSource
```

`sox` is assumed installed (`brew install sox`). Device is selected by the CoreAudio device name. macOS support is best-effort in Phase 4; if `sox` is absent, capture returns an `AudioCaptureException` with a clear install message.

### 6. `PlatformAudioSource` dispatch

Mirrors `PlatformAudioDeviceProvider`:

| OS | Implementation |
|----|----------------|
| Windows | `WasapiAudioSource` |
| Linux | `ArecordAudioSource` |
| macOS | `SoxAudioSource` |
| Other | `NullAudioSource` (throws `AudioCaptureException("unsupported platform")`) |

### 7. `CaptureManager` — lifecycle orchestration

A new singleton class (not an interface; promoted to one if Phase 6 needs it) registered in DI:

```csharp
public sealed class CaptureManager : IAsyncDisposable
{
    public bool IsCapturing { get; }
    public Task StartAsync(string deviceId, CancellationToken ct);
    public Task StopAsync();
}
```

`Program.cs` wires:
- `ApplicationStarted` → `StartAsync(config.AudioDeviceName)` if non-null
- `IConfigStore.OnSaved` (new event) OR checked in the POST handler after `SaveAsync` → if device name changed, `StopAsync()` then `StartAsync(newDevice)`
- `ApplicationStopping` → `StopAsync()`

`CaptureManager` holds the `Channel<float[]>` and the running `Task` that drains `IAudioSource.CaptureAsync`. Phase 5 injects `CaptureManager` to read from the channel.

### 8. `DaemonStatus.CaptureActive`

```csharp
public sealed record DaemonStatus(
    string  State,
    string  Version,
    string? AudioDevice,
    bool    CaptureActive);   // ← new
```

Populated from `CaptureManager.IsCapturing`.

### 9. AOT considerations

`WasapiCapture` and `MMDeviceEnumerator` are primarily P/Invoke wrappers with no significant dynamic dispatch. NAudio 2.2.1 compiles clean under AOT in P2 for the enumeration path; the capture path adds `BufferedWaveProvider` and `WdlResamplingSampleProvider`, both pure managed with no `Activator.CreateInstance` usage. If the AOT publish produces trim warnings for NAudio internals, suppress with `<TrimmerRootDescriptor>` entries rather than disabling trimming entirely.

## Risks / Trade-offs

- **`WdlResamplingSampleProvider` accuracy** → The WDL resampler is good enough for FT8 (weak-signal tolerance is high). High-fidelity resampling is not a Phase 4 goal.

- **`sox` dependency on macOS** → macOS capture is gated on a third-party tool. `AudioCaptureException` message will include install instructions. If this proves too fragile, Phase 6 can introduce a native CoreAudio binding.

- **`IConfigStore.OnSaved` event** → Adding an event to `IConfigStore` is a minor breaking change to the abstraction. The only callers today are in `OpenWSFZ.Web` and `OpenWSFZ.Config`; impact is contained.

- **Channel back-pressure** → If the decoder (Phase 5) stalls, the `Channel` fills. `BoundedChannelOptions` with `DropOldest` is used (capacity = 16 chunks = ~2.7 s) so the pipeline never blocks the capture thread; old audio is silently dropped during stall. This is acceptable for FT8 — a missed 15-second window is obvious to the operator.

## Open Questions

*(none — all decisions are made above)*
