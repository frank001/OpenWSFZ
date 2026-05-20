# QA Review — p2-audio-config (PR #6)

**Reviewer:** QA Gate  
**Date:** 2026-05-20  
**Branch:** `feat/p2-audio-config` → `main`  
**Verdict:** ❌ BLOCKED — CI failures on Linux and macOS must be resolved before merge

---

## CI Status

| Leg | Run 1 | Run 2 |
|---|---|---|
| `windows-latest` | ❌ fail | ✅ pass |
| `ubuntu-latest` | ❌ fail | ❌ fail |
| `macos-latest` | ❌ fail | ❌ fail |

Linux and macOS have failed on **both** runs. The Windows leg now passes. This PR cannot merge until all three legs are green.

---

## 🔴 Blocker — CS0246 on Linux and macOS

### Root Cause

`WasapiAudioDeviceProvider.cs` is compiled on every platform. The NAudio package reference in the `.csproj` is correctly conditional on Windows, but the C# compiler does not know this — it still attempts to resolve `using NAudio.CoreAudioApi` on Linux and macOS, where the assembly is absent.

`[SupportedOSPlatform("windows")]` is a runtime analyser attribute. It does **not** exclude the file from compilation.

**Error (identical on both failing legs):**
```
error CS0246: The type or namespace name 'NAudio' could not be found
  → src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs(2,7)
```

### Fix — Three files require changes

---

#### 1. `src/OpenWSFZ.Audio/OpenWSFZ.Audio.csproj`

Add a `WASAPI_SUPPORTED` compile constant, gated on the build OS. Place it after the existing `<PropertyGroup>`:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>

  <!-- Define WASAPI_SUPPORTED only when building on Windows so that
       WasapiAudioDeviceProvider.cs (which references NAudio) is excluded
       from compilation on Linux and macOS. -->
  <PropertyGroup Condition="$([MSBuild]::IsOSPlatform('Windows'))">
    <DefineConstants>$(DefineConstants);WASAPI_SUPPORTED</DefineConstants>
  </PropertyGroup>

  <ItemGroup>
    <ProjectReference Include="..\OpenWSFZ.Abstractions\OpenWSFZ.Abstractions.csproj" />
  </ItemGroup>

  <ItemGroup>
    <!-- Windows WASAPI device enumeration -->
    <PackageReference Include="NAudio" Condition="$([MSBuild]::IsOSPlatform('Windows'))" />
  </ItemGroup>
</Project>
```

---

#### 2. `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`

Wrap the entire file in `#if WASAPI_SUPPORTED`:

```csharp
#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using NAudio.CoreAudioApi;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Enumerates WASAPI capture endpoints on Windows using NAudio's
/// <see cref="MMDeviceEnumerator"/>. COM initialisation is handled internally
/// by NAudio.Wasapi.
/// </summary>
[SupportedOSPlatform("windows")]
internal sealed class WasapiAudioDeviceProvider : IAudioDeviceProvider
{
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
    {
        var devices = new List<AudioDeviceInfo>();

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

        return Task.FromResult<IReadOnlyList<AudioDeviceInfo>>(devices);
    }
}
#endif
```

---

#### 3. `src/OpenWSFZ.Audio/PlatformAudioDeviceProvider.cs`

Gate the `WasapiAudioDeviceProvider` instantiation with the same symbol. Without this, the reference to `WasapiAudioDeviceProvider` in `ResolveForCurrentPlatform` will itself fail to compile on non-Windows once the class is conditionally excluded:

```csharp
private static IAudioDeviceProvider ResolveForCurrentPlatform()
{
#if WASAPI_SUPPORTED
    if (OperatingSystem.IsWindows())
        return new WasapiAudioDeviceProvider();
#endif

    if (OperatingSystem.IsLinux())
        return SubprocessAudioDeviceProvider.ForLinux();

    if (OperatingSystem.IsMacOS())
        return SubprocessAudioDeviceProvider.ForMacOs();

    // Unknown platform → safe no-op.
    return new NullAudioDeviceProvider();
}
```

The `using System.Runtime.InteropServices;` import at the top of `PlatformAudioDeviceProvider.cs` is no longer used after this change — remove it to keep `TreatWarningsAsErrors` happy.

---

### Verification

After applying all three changes, run locally:

```bash
dotnet build -c Release   # must produce 0 errors, 0 warnings on all three platforms
dotnet test  -c Release --no-build
```

If you do not have Linux/macOS available, push the branch — CI will confirm. The Windows build continues to compile `WasapiAudioDeviceProvider` because `WASAPI_SUPPORTED` is defined, so Windows behaviour is unchanged.

---

## 🟡 Required Before Merge (code quality)

### `Results.Ok` vs `TypedResults.Ok` in `POST /api/v1/config`

**File:** `src/OpenWSFZ.Web/WebApp.cs`

The `POST /api/v1/config` endpoint uses `Results.Ok(store.Current)` on its happy path while every other endpoint in the file uses `TypedResults.Ok(...)`. This is an inconsistency and, more importantly, `Results.Ok` (non-generic) does not give the Request Delegate Generator a compile-time type hint. `AppConfig` is in `AppJsonContext`, so AOT trimming is unlikely to bite — but relying on runtime discovery when the type is already registered is unnecessary.

**Change:**
```csharp
// Before
return Results.Ok(store.Current);

// After
return TypedResults.Ok(store.Current);
```

---

## 🔵 Advisory (non-blocking; please acknowledge or defer with a note)

### A. Thread safety on `JsonConfigStore._current`

**File:** `src/OpenWSFZ.Config/JsonConfigStore.cs`

`_current` is a plain field read by `Current` and written by `SaveAsync`. C# reference assignments are atomic on 64-bit hardware, so data corruption is not possible, but the field is not `volatile` — the JIT may cache the value in a register across a context switch. In practice, `await` introduces memory barriers that make a stale read essentially impossible, but it is a formal data race.

Suggested fix: declare the field `volatile`.
```csharp
private volatile AppConfig _current;
```

---

### B. `OperationCanceledException` swallowed in `SubprocessAudioDeviceProvider`

**File:** `src/OpenWSFZ.Audio/SubprocessAudioDeviceProvider.cs`

The bare `catch` block swallows all exceptions, including `OperationCanceledException`. The interface contract ("never throw") is intentional for enumeration failures, but most .NET developers would expect cancellation to propagate. If a request is aborted mid-enumeration, the caller receives an empty list rather than learning the operation was cancelled.

If the "never throw including cancellation" contract is deliberate, add a comment to that effect. If not, call `ct.ThrowIfCancellationRequested()` before `return []`.

---

### C. Test isolation — shared mutable fixture

**File:** `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs`

`AudioConfigIntegrationTests` uses `IClassFixture<AudioConfigFixture>`, so a single `TestConfigStore` instance is shared across all ten tests. Task 9.3 (`PostConfig_PersistsUpdatedConfig_...`) mutates the store. xUnit does not guarantee execution order within a class. Current assertions are loose enough that this does not currently cause failures, but any future test that asserts a specific initial device name will be silently order-dependent.

Consider resetting the config store state at the start of any test that depends on a known initial value.

---

### D. No log message when corrupt config falls back to defaults

**File:** `src/OpenWSFZ.Config/JsonConfigStore.cs` — `Load` method `catch` block

When the config file is unreadable or malformed, defaults are returned silently. The operator has no indication that their persisted settings were discarded. The `Console.Error.WriteLine` pattern already used in `Program.cs` for config-path logging would be appropriate here.

There is also no test for this scenario. A test case `"FR-004: JsonConfigStore returns defaults and does not throw when config file is corrupt"` would close the gap.

---

### E. `Path` as a value-tuple member name

**File:** `src/OpenWSFZ.Config/ConfigPathResolver.cs`

```csharp
public static (string Path, string Source) Resolve(string? cliOverride = null)
```

`Path` as a member name shadows the `System.IO.Path` static class. It compiles correctly but will momentarily confuse any reader. `FilePath` or `ResolvedPath` would be clearer.

---

### F. `LicenseInventoryCheck` test — prefer `[Theory]` as the table grows

**File:** `tests/LicenseInventoryCheck.Tests/NuGetEnumeratorTests.cs`

`Enumerate_LicenceTypeFile_ResolvedViaKnownTable` iterates all `KnownFileLicences` entries in a single `[Fact]`. With one entry (NAudio) this is fine. Once the table grows, a single entry failure will report as the entire fact failing. Convert to `[Theory, MemberData(...)]` before the table has more than two entries.

---

## Summary

| # | Severity | File | Issue |
|---|---|---|---|
| 1 | 🔴 Blocker | `OpenWSFZ.Audio.csproj` / `WasapiAudioDeviceProvider.cs` / `PlatformAudioDeviceProvider.cs` | CS0246 — NAudio not available on Linux/macOS; missing `#if WASAPI_SUPPORTED` guards |
| 2 | 🟡 Required | `WebApp.cs` | `Results.Ok` → `TypedResults.Ok` in POST /api/v1/config |
| A | 🔵 Advisory | `JsonConfigStore.cs` | `_current` not `volatile` |
| B | 🔵 Advisory | `SubprocessAudioDeviceProvider.cs` | `OperationCanceledException` swallowed |
| C | 🔵 Advisory | `AudioConfigIntegrationTests.cs` | Shared mutable fixture state |
| D | 🔵 Advisory | `JsonConfigStore.cs` | No log / no test for corrupt config fallback |
| E | 🔵 Advisory | `ConfigPathResolver.cs` | `Path` tuple member shadows `System.IO.Path` |
| F | 🔵 Advisory | `NuGetEnumeratorTests.cs` | Single `[Fact]` iterates multi-entry table |

The underlying design and test coverage are sound. Items 1 and 2 must be addressed; advisory items A–F should be acknowledged or deferred with a written rationale in the next commit message.
