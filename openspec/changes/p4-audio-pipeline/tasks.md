## 1. STA thread helper

- [x] 1.1 Create `src/OpenWSFZ.Audio/StaThread.cs` — internal static class with a single method `Task<T> Run<T>(Func<T> func)` that creates a background `Thread` with `ApartmentState.STA`, runs the delegate, and marshals the result (or exception) back via `TaskCompletionSource<T>`.

## 2. Fix WASAPI device enumeration

- [x] 2.1 Modify `WasapiAudioDeviceProvider.GetDevicesAsync` to call `StaThread.Run(EnumerateDevices)` instead of calling `MMDeviceEnumerator` directly on the calling thread. Extract the COM-touching code into a private `static IReadOnlyList<AudioDeviceInfo> EnumerateDevices()` method.
- [x] 2.2 Add unit test `"FR-003: WasapiAudioDeviceProvider.GetDevicesAsync succeeds when called from an MTA thread"` in `OpenWSFZ.Audio.Tests` — calls `GetDevicesAsync()` from a `Thread` explicitly set to `ApartmentState.MTA` and asserts it returns without throwing (result may be empty in CI; the test proves no exception is thrown).

## 3. `IAudioSource` interface and `AudioCaptureException`

- [x] 3.1 Replace the stub body of `src/OpenWSFZ.Abstractions/IAudioSource.cs` with the full interface: `int SampleRate { get; }`, `int ChannelCount { get; }`, `IAsyncEnumerable<float[]> CaptureAsync(string deviceId, CancellationToken ct)`. Inherit `IAsyncDisposable`.
- [x] 3.2 Create `src/OpenWSFZ.Abstractions/AudioCaptureException.cs` — a `public sealed class AudioCaptureException : Exception` with `string deviceId` and `string reason` constructor parameters; message format: `"Cannot capture from device '{deviceId}': {reason}"`.

## 4. `IConfigStore` — `OnSaved` event

- [x] 4.1 Add `event Action<AppConfig>? OnSaved` to the `IConfigStore` interface in `src/OpenWSFZ.Abstractions/IConfigStore.cs`.
- [x] 4.2 Raise `OnSaved` in `JsonConfigStore.SaveAsync` (after the file rename) and in `InMemoryConfigStore.SaveAsync` (in `OpenWSFZ.Web`).

## 5. `CaptureManager`

- [x] 5.1 Create `src/OpenWSFZ.Audio/CaptureManager.cs` — a `public sealed class CaptureManager : IAsyncDisposable`. Fields: `IAudioSource _source`, `Channel<float[]> _channel` (bounded, capacity 16, `DropOldest`), `CancellationTokenSource? _cts`, `Task? _captureTask`. Properties: `bool IsCapturing`, `ChannelReader<float[]> Samples`.
- [x] 5.2 Implement `Task StartAsync(string deviceId, CancellationToken ct = default)` — cancels any running session, creates a new `CancellationTokenSource`, starts a background `Task` that runs `await foreach (var chunk in _source.CaptureAsync(deviceId, linkedCt)) { await _channel.Writer.WriteAsync(chunk); }`, sets `IsCapturing = true`.
- [x] 5.3 Implement `Task StopAsync()` — cancels the `CancellationTokenSource`, awaits the running task (with a 2 s timeout; swallow `OperationCancelledException`), resets `IsCapturing = false`.
- [x] 5.4 Implement `DisposeAsync` — calls `StopAsync()` and completes the channel writer.

## 6. Windows — `WasapiAudioSource`

- [x] 6.1 Create `src/OpenWSFZ.Audio/WasapiAudioSource.cs` guarded by `#if WASAPI_SUPPORTED`. Class implements `IAudioSource`.
- [x] 6.2 Implement `CaptureAsync(string deviceId, CancellationToken ct)` as an `async IAsyncEnumerable` method (with `[EnumeratorCancellation]`). Use `StaThread.Run(...)` to open the `MMDevice` by ID and create a `WasapiCapture`. Wire the NAudio pipeline: `BufferedWaveProvider` → stereo-to-mono if needed → `WdlResamplingSampleProvider` targeting 12 000 Hz → chunk reads into a local `Channel<float[]>` whose reader is yielded. Start capture; loop `await channel.Reader.ReadAsync(ct)` and `yield return` each chunk. On loop exit or exception: stop capture, complete channel, rethrow `AudioCaptureException` if device not found.
- [x] 6.3 Set `SampleRate = 12_000` and `ChannelCount = 1` as properties.
- [x] 6.4 Implement `DisposeAsync` — stops the `WasapiCapture` on the STA thread if it is running.

## 7. Linux — `ArecordAudioSource`

- [x] 7.1 Create `src/OpenWSFZ.Audio/ArecordAudioSource.cs`. Class implements `IAudioSource` with `SampleRate = 12_000`, `ChannelCount = 1`.
- [x] 7.2 Implement `CaptureAsync(string deviceId, CancellationToken ct)`: start `arecord -D <deviceId> -f FLOAT_LE -r 12000 -c 1 -t raw -` with `RedirectStandardOutput = true`; read stdout in `chunkBytes = 2048 * 4` byte blocks; convert via `MemoryMarshal.Cast<byte, float>()` into a rented `float[]`; yield each chunk. If `arecord` exits non-zero before cancellation, throw `AudioCaptureException`. On cancellation: kill the process, complete the enumerable cleanly.

## 8. macOS — `SoxAudioSource`

- [x] 8.1 Create `src/OpenWSFZ.Audio/SoxAudioSource.cs`. Class implements `IAudioSource` with `SampleRate = 12_000`, `ChannelCount = 1`.
- [x] 8.2 Implement `CaptureAsync(string deviceId, CancellationToken ct)`: start `sox -t coreaudio "<deviceId>" -t raw -e float -b 32 -r 12000 -c 1 -` with stdout redirected; same byte-to-float pipeline as `ArecordAudioSource`. If `sox` is not found, throw `AudioCaptureException` with message `"sox is not installed — run: brew install sox"`.

## 9. `PlatformAudioSource`

- [x] 9.1 Create `src/OpenWSFZ.Audio/PlatformAudioSource.cs` — `public sealed class PlatformAudioSource : IAudioSource`. Constructor resolves the inner `IAudioSource` using the same OS-dispatch pattern as `PlatformAudioDeviceProvider` (`#if WASAPI_SUPPORTED` + `OperatingSystem.Is*()` checks). Delegates all interface members to `_inner`.

## 10. Daemon wiring

- [x] 10.1 Register `PlatformAudioSource` as singleton `IAudioSource` and `CaptureManager` as singleton in `Program.cs` DI.
- [x] 10.2 In `Program.cs`, after `app.Lifetime.ApplicationStarted` fires, resolve `CaptureManager` and `IConfigStore` from DI; if `configStore.Current.AudioDeviceName` is not null, call `captureManager.StartAsync(deviceName)` (fire-and-forget, log errors).
- [x] 10.3 Subscribe to `IConfigStore.OnSaved` in `Program.cs`; in the handler, if `newConfig.AudioDeviceName` differs from the currently-captured device, call `captureManager.StopAsync()` then (if non-null) `captureManager.StartAsync(newConfig.AudioDeviceName)`.
- [x] 10.4 Register `app.Lifetime.ApplicationStopping` handler: call `captureManager.StopAsync()` and `await captureManager.DisposeAsync()`.

## 11. Status endpoint — `captureActive`

- [x] 11.1 Add `bool CaptureActive` property to the `DaemonStatus` record in `src/OpenWSFZ.Web/DaemonStatus.cs`; add `CaptureActive` to `AppJsonContext`.
- [x] 11.2 Update `GET /api/v1/status` in `WebApp.cs` to pass `CaptureActive: captureManager.IsCapturing` — requires `CaptureManager` to be injected into `WebApp.Create` (add optional parameter, default to a no-op stub).

## 12. Unit tests — audio

- [x] 12.1 Add test `"FR-003: WasapiAudioDeviceProvider.GetDevicesAsync succeeds from MTA thread"` (task 2.2 above — move checkbox here for tracking).
- [x] 12.2 Add test `"FR-003: ArecordAudioSource yields chunks when arecord produces valid FLOAT_LE output"` — uses a fake `arecord` stub script (or a pre-built PCM byte sequence via `Process` mock) to feed known float values; asserts correct `float[]` contents in yielded chunks.
- [x] 12.3 Add test `"FR-003: ArecordAudioSource throws AudioCaptureException when process exits non-zero immediately"` — fake process exits 1; asserts `AudioCaptureException` thrown.
- [x] 12.4 Add test `"FR-003: CaptureManager.IsCapturing is false before StartAsync"` — instantiate with `NullAudioSource`; assert `IsCapturing == false`.
- [x] 12.5 Add test `"FR-003: CaptureManager.IsCapturing is true after StartAsync with NullAudioSource that yields indefinitely"` — use a test-double `IAudioSource` that yields chunks until cancelled; assert `IsCapturing == true` after start; call `StopAsync`; assert `IsCapturing == false`.

## 13. Integration tests — status endpoint

- [x] 13.1 Add test `"FR-003: GET /api/v1/status includes captureActive field"` in `OpenWSFZ.Web.Tests` — asserts the JSON response contains a `captureActive` field (value may be `false`; field presence is what matters).

## 14. TraceabilityCheck debt update

- [x] 14.1 Remove `FR-003` from `traceability-debt.md` — FR-003 was not in the debt file (already covered by existing SubprocessAudioDeviceProviderTests); this task is a no-op.

## 15. Exit gate verification (M5)

- [x] 15.1 Run `dotnet build -c Release` — confirmed zero errors, zero warnings.
- [x] 15.2 Run `dotnet test -c Release --no-build` — confirmed all 97 tests pass.
- [x] 15.3 Run TraceabilityCheck locally — confirmed FR-003 is mapped and debt file is clean.
- [ ] 15.4 Run the daemon (`dotnet run --project src/OpenWSFZ.Daemon`), open the Settings page — confirm the device selector is populated with real audio devices.
- [ ] 15.5 Select a device and Save; confirm `GET /api/v1/status` returns `captureActive: true` within a few seconds.
- [ ] 15.6 Publish AOT (`dotnet publish -c Release -r win-x64 src/OpenWSFZ.Daemon`); confirm no AOT trim warnings related to NAudio capture path.
