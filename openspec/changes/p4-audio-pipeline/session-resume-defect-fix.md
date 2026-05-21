# Session Resume — Defect Fix: Audio Device Enumeration

**Branch:** `feat/p4-audio-pipeline`
**Date paused:** 2026-05-21
**Task:** Fix `defect-audio-device-enumeration.md` — all five files below

---

## What was read / understood

All five affected files were fully read before work started:

| File | Key observations |
|---|---|
| `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs` | `static EnumerateDevices`, bare `catch {}`, `DeviceState.Active` only |
| `src/OpenWSFZ.Audio/PlatformAudioDeviceProvider.cs` | `new WasapiAudioDeviceProvider()` no-arg, `ResolveForCurrentPlatform()` static |
| `src/OpenWSFZ.Web/WebApp.cs` | `audioProvider ??  new InMemoryAudioDeviceProvider()` — provider built before host |
| `src/OpenWSFZ.Daemon/Program.cs` | `audioProvider: new PlatformAudioDeviceProvider()` — no logger passed |
| `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs` | `WasapiAudioDeviceProviderTests` class already exists here (line 139); test uses `new PlatformAudioDeviceProvider()` (no-arg) — stays valid because new param is optional |

Also read:
- `tests/OpenWSFZ.Audio.Tests/OpenWSFZ.Audio.Tests.csproj` — no `WASAPI_SUPPORTED` define yet; `InternalsVisibleTo("OpenWSFZ.Audio.Tests")` is in `src/OpenWSFZ.Audio/AssemblyAttributes.cs`
- `src/OpenWSFZ.Audio/OpenWSFZ.Audio.csproj` — `WASAPI_SUPPORTED` defined via MSBuild conditional on Windows
- `Directory.Packages.props` — no `Microsoft.Extensions.Logging.*` entry (not needed; it's part of `Microsoft.NETCore.App` shared framework)

---

## Exact plan (5 files, execute in order)

### 1 — `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs` ← **FIRST file edited, Write succeeded**

Full rewrite already applied. Content is in the session — it's the **new** version. Key changes:
- Added `using Microsoft.Extensions.Logging;`
- Constructor: `public WasapiAudioDeviceProvider(ILogger<WasapiAudioDeviceProvider> log)`
- Internal test-seam constructor: `internal WasapiAudioDeviceProvider(ILogger<...> log, Func<IReadOnlyList<AudioDeviceInfo>> enumerateOverride)`
- `EnumerateDevices()` is no longer `static` (needs `_log` and `_enumerateOverride`)
- `catch {}` → `catch (Exception ex) { _log.LogWarning(ex, "...", devices.Count); }`
- `DeviceState.Active` → `DeviceState.Active | DeviceState.Disabled`
- Seam called INSIDE the try/catch so a throwing override tests the warning path

### 2 — `src/OpenWSFZ.Audio/PlatformAudioDeviceProvider.cs` ← **Write REJECTED (user interrupted)**

This is where we stopped. Needs full rewrite. Desired final content:

```csharp
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Selects the correct <see cref="IAudioDeviceProvider"/> implementation for the
/// current OS at runtime and delegates to it.
/// </summary>
public sealed class PlatformAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly IAudioDeviceProvider _inner;

    public PlatformAudioDeviceProvider(ILoggerFactory? loggerFactory = null)
    {
        _inner = ResolveForCurrentPlatform(loggerFactory);
    }

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => _inner.GetDevicesAsync(ct);

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

        if (OperatingSystem.IsLinux())
            return SubprocessAudioDeviceProvider.ForLinux();

        if (OperatingSystem.IsMacOS())
            return SubprocessAudioDeviceProvider.ForMacOs();

        return new NullAudioDeviceProvider();
    }
}

/// <summary>Safe fallback for unsupported platforms — always returns an empty list.</summary>
internal sealed class NullAudioDeviceProvider : IAudioDeviceProvider
{
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult<IReadOnlyList<AudioDeviceInfo>>([]);
}
```

### 3 — `src/OpenWSFZ.Web/WebApp.cs`

**Minimal Edit** — do NOT rewrite the whole file. Two targeted changes:

**Change A — signature** (add one parameter after `audioProvider`):
```
// OLD:
    IAudioDeviceProvider? audioProvider   = null,
    CaptureManager?       captureManager  = null)

// NEW:
    IAudioDeviceProvider? audioProvider          = null,
    Func<IServiceProvider, IAudioDeviceProvider>? audioProviderFactory = null,
    CaptureManager?       captureManager         = null)
```

**Change B — registration block** (replace the `AddSingleton<IAudioDeviceProvider>` line):
```
// OLD (single line):
        builder.Services.AddSingleton<IAudioDeviceProvider>(
            audioProvider ?? new InMemoryAudioDeviceProvider());

// NEW (4 lines):
        if (audioProviderFactory is not null)
            builder.Services.AddSingleton<IAudioDeviceProvider>(audioProviderFactory);
        else
            builder.Services.AddSingleton<IAudioDeviceProvider>(
                audioProvider ?? new InMemoryAudioDeviceProvider());
```

No other changes to `WebApp.cs`. All existing test call-sites that pass `audioProvider:` are unaffected.

### 4 — `src/OpenWSFZ.Daemon/Program.cs`

**Targeted Edit** — replace just the `WebApp.Create` call. Add two `using` directives at the top.

Add at top:
```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
```

Replace in the `// ── Audio capture` section:
```
// OLD:
var audioSource     = new PlatformAudioSource();
var captureManager  = new CaptureManager(audioSource);

// Create and configure the web application.
var app = WebApp.Create(
    port,
    configStore:    configStore,
    audioProvider:  new PlatformAudioDeviceProvider(),
    captureManager: captureManager);

// NEW:
var audioSource    = new PlatformAudioSource();
var captureManager = new CaptureManager(audioSource);

// Create and configure the web application.
// audioProviderFactory defers construction of PlatformAudioDeviceProvider until
// DI resolves it, so the app's own ILoggerFactory is available when it's built.
var app = WebApp.Create(
    port,
    configStore:          configStore,
    audioProviderFactory: sp => new PlatformAudioDeviceProvider(
                                    sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager);
```

### 5 — `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs`

Two additions to the existing file:

**A — Add `WASAPI_SUPPORTED` conditional define to the test project**

Edit `tests/OpenWSFZ.Audio.Tests/OpenWSFZ.Audio.Tests.csproj` — add after the first `<PropertyGroup>`:

```xml
  <!-- Mirror the WASAPI_SUPPORTED symbol from OpenWSFZ.Audio so that
       #if WASAPI_SUPPORTED guards in test files compile correctly. -->
  <PropertyGroup Condition="$([MSBuild]::IsOSPlatform('Windows'))">
    <DefineConstants>$(DefineConstants);WASAPI_SUPPORTED</DefineConstants>
  </PropertyGroup>
```

**B — Add `CapturingLogger<T>` helper + T-1 test to `CaptureManagerTests.cs`**

Add AFTER the existing `InfiniteAudioSource` class (around line 33), before the `CaptureManagerTests` class:

```csharp
#if WASAPI_SUPPORTED
/// <summary>
/// Minimal <see cref="ILogger{T}"/> that records whether a Warning-or-higher
/// entry was emitted. Used in T-1 to verify enumeration failures are logged.
/// </summary>
internal sealed class CapturingLogger<T> : ILogger<T>
{
    public bool HasWarning { get; private set; }

    IDisposable? ILogger.BeginScope<TState>(TState state) where TState : notnull => null;
    bool ILogger.IsEnabled(LogLevel logLevel) => true;

    void ILogger.Log<TState>(
        LogLevel logLevel,
        EventId eventId,
        TState state,
        Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
        if (logLevel >= LogLevel.Warning)
            HasWarning = true;
    }
}
#endif
```

Add at the END of the `WasapiAudioDeviceProviderTests` class (after the existing `GetDevicesAsync_Succeeds_FromMtaThread` test, before the closing `}`):

```csharp
    // T-1 — defect fix: enumeration failures must be logged, not silently swallowed.
    [Fact(DisplayName = "P4-Audio-T1: WasapiAudioDeviceProvider logs Warning and returns empty list when enumeration throws")]
    public async Task GetDevicesAsync_LogsWarningAndReturnsEmptyList_WhenEnumerationThrows()
    {
        if (!OperatingSystem.IsWindows())
            return; // WASAPI is not available on non-Windows platforms — skip silently.

#if WASAPI_SUPPORTED
        // Arrange: a logger that captures warning calls, plus a seam that simulates a COM failure.
        var capturingLogger = new CapturingLogger<WasapiAudioDeviceProvider>();
        var provider = new WasapiAudioDeviceProvider(
            capturingLogger,
            () => throw new InvalidOperationException("Simulated COM failure"));

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert
        devices.Should().BeEmpty(
            "no devices were collected before the exception was thrown");
        capturingLogger.HasWarning.Should().BeTrue(
            "a Warning must be logged so that WASAPI failures are visible in the application log");
#endif
    }
```

Also add `using Microsoft.Extensions.Logging;` to the top of `CaptureManagerTests.cs`.

---

## After all 5 files are edited

Run:
```
cd D:\Projects\claude\OpenWSFZ
dotnet build -c Release
dotnet test -c Release --no-build
```

Expected: build clean, all tests pass (including new T-1).

Then commit:
```
git add src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs
git add src/OpenWSFZ.Audio/PlatformAudioDeviceProvider.cs
git add src/OpenWSFZ.Web/WebApp.cs
git add src/OpenWSFZ.Daemon/Program.cs
git add tests/OpenWSFZ.Audio.Tests/OpenWSFZ.Audio.Tests.csproj
git add tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs
git commit -m "fix(p4-audio-pipeline): log WASAPI enumeration failures; include disabled devices"
```

---

## Critical notes

- `WasapiAudioDeviceProvider.cs` **was already successfully written** in the interrupted session. Do NOT rewrite it — only verify the file is correct.
- `PlatformAudioDeviceProvider.cs` write was **REJECTED** — still has the old content. Start here.
- `ILoggerFactory?` param is **optional** (`= null`) so all existing `new PlatformAudioDeviceProvider()` call-sites (including the existing MTA test) compile without changes.
- `NullLogger<T>` is in `Microsoft.Extensions.Logging.Abstractions` namespace — part of the shared framework, no extra NuGet package needed.
- `WASAPI_SUPPORTED` must be added to the test `.csproj` so `#if WASAPI_SUPPORTED` guards in test files work correctly.
