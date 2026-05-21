# Defect Report — Audio Device Enumeration Returns Empty List

**Branch:** `feat/p4-audio-pipeline`
**Filed by:** QA
**Date:** 2026-05-21
**Severity:** High — the Settings page cannot populate the device dropdown; the user cannot select a capture device

---

## Symptom

`GET /api/v1/audio/devices` returns an empty JSON array `[]` on Windows despite one or more capture devices being present in the system.

---

## Root Cause 1 — Silent Exception Swallowing

**File:** `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`, lines 24–39

```csharp
try
{
    using var enumerator = new MMDeviceEnumerator();
    var endpoints = enumerator.EnumerateAudioEndPoints(
        DataFlow.Capture, DeviceState.Active);

    foreach (var ep in endpoints)
    {
        devices.Add(new AudioDeviceInfo(
            Id:   ep.ID,
            Name: ep.FriendlyName));
    }
}
catch
{
    // Return whatever we collected; never throw.
}
```

The bare `catch` block swallows **every** exception thrown during WASAPI enumeration — COM errors, Windows Audio service failures, NAudio internal errors — and returns an empty list. There is no log entry, warning, or any other indication that something went wrong. The call chain from `StaThread.Run` → `GetDevicesAsync` → the API endpoint completes successfully with an empty result, making the fault entirely invisible.

### Required fix

Inject `ILogger<WasapiAudioDeviceProvider>` via the constructor and log the exception at `Warning` level before returning the partial list. Do not silently discard it.

```csharp
[SupportedOSPlatform("windows")]
internal sealed class WasapiAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly ILogger<WasapiAudioDeviceProvider> _log;

    public WasapiAudioDeviceProvider(ILogger<WasapiAudioDeviceProvider> log)
        => _log = log;

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => StaThread.Run(EnumerateDevices);

    private IReadOnlyList<AudioDeviceInfo> EnumerateDevices()
    {
        var devices = new List<AudioDeviceInfo>();
        try
        {
            using var enumerator = new MMDeviceEnumerator();
            var endpoints = enumerator.EnumerateAudioEndPoints(
                DataFlow.Capture, DeviceState.Active | DeviceState.Disabled);

            foreach (var ep in endpoints)
            {
                devices.Add(new AudioDeviceInfo(
                    Id:   ep.ID,
                    Name: ep.FriendlyName));
            }
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex,
                "WASAPI device enumeration failed; returning {Count} device(s) collected before the error.",
                devices.Count);
        }
        return devices;
    }
}
```

Because `WasapiAudioDeviceProvider` is constructed inside `PlatformAudioDeviceProvider` via `new WasapiAudioDeviceProvider()`, you will also need to thread the logger through. The simplest approach is to accept an `ILoggerFactory?` in `PlatformAudioDeviceProvider` and pass a typed logger down:

```csharp
public PlatformAudioDeviceProvider(ILoggerFactory? loggerFactory = null)
{
    _inner = ResolveForCurrentPlatform(loggerFactory);
}

private static IAudioDeviceProvider ResolveForCurrentPlatform(ILoggerFactory? loggerFactory)
{
#if WASAPI_SUPPORTED
    if (OperatingSystem.IsWindows())
    {
        var log = loggerFactory?.CreateLogger<WasapiAudioDeviceProvider>()
                  ?? NullLogger<WasapiAudioDeviceProvider>.Instance;
        return new WasapiAudioDeviceProvider(log);
    }
#endif
    // ... remainder unchanged
}
```

Then update `Program.cs` to resolve `ILoggerFactory` from the host before constructing `PlatformAudioDeviceProvider`, or wire it through DI after `builder.Build()`.

---

## Root Cause 2 — `DeviceState.Active` Excludes Disabled Devices

**File:** `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`, line 28

```csharp
var endpoints = enumerator.EnumerateAudioEndPoints(
    DataFlow.Capture, DeviceState.Active);
```

`DeviceState.Active` returns only devices that are currently connected **and** enabled in Windows Sound Settings. A device that is present but disabled will not appear in the list, giving the user no way to enable it via the application.

### Required fix

Broaden the filter to include disabled devices:

```csharp
var endpoints = enumerator.EnumerateAudioEndPoints(
    DataFlow.Capture, DeviceState.Active | DeviceState.Disabled);
```

If the design intent is to show only ready-to-use devices, the current behaviour is correct and this item may be resolved as *by design*. Please confirm either way.

---

## Suggested Diagnostic Step (Before Writing the Fix)

If the root cause is still unclear after reading this document, temporarily remove the `catch` block entirely. Any exception thrown by NAudio or COM will propagate through `StaThread.Run` as a faulted `Task`, the endpoint handler will return HTTP 500, and the exact exception message will appear in the application log. This takes thirty seconds and will identify the problem unambiguously.

---

## Tests Required Alongside the Fix

| # | Description |
|---|---|
| T-1 | `WasapiAudioDeviceProvider` logs a `Warning` (not throws) when `MMDeviceEnumerator` throws; result is an empty list |
| T-2 | `PlatformAudioDeviceProvider` resolves to `WasapiAudioDeviceProvider` on Windows (compile-time gate test) |
| T-3 | `GET /api/v1/audio/devices` returns HTTP 200 with an empty array when the provider returns no devices (existing integration test — verify it still passes) |

T-1 can be covered with a unit test using a mock/stub `MMDeviceEnumerator` wrapper, or by extracting the NAudio call behind a seam. T-2 is a compile-time concern and may be documented rather than tested.

---

## Files to Change

| File | Change |
|---|---|
| `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs` | Add `ILogger`, log caught exception, broaden `DeviceState` |
| `src/OpenWSFZ.Audio/PlatformAudioDeviceProvider.cs` | Accept `ILoggerFactory?`, pass logger to `WasapiAudioDeviceProvider` |
| `src/OpenWSFZ.Daemon/Program.cs` | Pass logger factory when constructing `PlatformAudioDeviceProvider` |
| `tests/OpenWSFZ.Audio.Tests/` | Add T-1 unit test |
