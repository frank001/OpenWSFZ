# QA Review — p4-audio-pipeline

**Branch:** `feat/p4-audio-pipeline`
**Reviewed by:** QA
**Date:** 2026-05-21 (initial) / 2026-05-21 (re-review pass 2 — A-3 added) / 2026-05-21 (pass 3 — all items resolved, deployment model confirmed)
**Verdict:** ✅ APPROVED — branch is ready for merge; A-1 PR description to be completed at PR creation time

### Deployment model — confirmed

**The operational binary for Phase 4 and Phase 5 is `dotnet run --project src/OpenWSFZ.Daemon` (JIT).** This is confirmed as the intended runtime model. WASAPI enumeration and capture work correctly under JIT: 13 real devices returned, `captureActive: true` confirmed after device selection (task 15.4, 15.5).

The NativeAOT-published binary (`dotnet publish -r win-x64`) does **not** support WASAPI and is not the operational binary. It exists solely as a structural prove-out — surfacing AOT incompatibilities while the codebase is small. The WASAPI failure in the AOT binary is expected, documented, and accepted for Phase 4. Resolution (ComWrappers migration) is Phase 6.

---

## New Finding — A-3 (raised during re-review, 2026-05-21)

### `runtimeconfig.template.json` is an ineffective workaround that generates a build warning

The file `src/OpenWSFZ.Daemon/runtimeconfig.template.json` contains:

```json
{
  "configProperties": {
    "System.Runtime.InteropServices.BuiltInComInterop.IsSupported": true
  }
}
```

This was evidently placed to preserve COM interop in the published binary by overriding the feature switch at runtime. It does not work for NativeAOT, and the IL Compiler tells us so:

> *"warning: The published project has a runtimeconfig.template.json that is not supported by PublishAot."*

**Why it cannot work.** NativeAOT evaluates `BuiltInComInterop.IsSupported` at **compile time**. The `[ComImport]` COM activation infrastructure is stripped from the native binary during IL compilation — a runtime configuration file cannot restore code that was never emitted into the image. `runtimeconfig.template.json` is a JIT-era mechanism; NativeAOT ignores it entirely.

**Why it is harmful.** The file:

1. Generates a build warning, which in a `TreatWarningsAsErrors` project is one linker flag away from a build failure.
2. Creates false confidence: a developer reading the file may assume the AOT binary has COM interop enabled, when it does not.
3. Contributes to the confusion that produced the user-reported defect in the first place.

**Required action.**

Remove `src/OpenWSFZ.Daemon/runtimeconfig.template.json`.

The correct long-term fix (Phase 6) is to replace `[ComImport]` usage with `ComWrappers`, at which point NativeAOT will support the WASAPI path properly. Until then, the limitation is documented in the source comment on `WasapiAudioDeviceProvider.cs` and must be stated in the PR description (A-1, still open).

If there is a legitimate reason to keep the file (e.g. for a non-AOT non-RID publish path that somehow requires this override), that reason must be documented in a comment inside the file — otherwise it reads as dead code.

---

## Re-Review Summary (pass 1, 2026-05-21)

A full review was conducted covering all source files, tests, and the resolution of prior findings. The conclusion on prior findings remains: **all previously-required items (R-1, R-2, A-1 code comment, A-2) have been resolved, the build is clean, and all 98 tests pass.** The new finding A-3 above is the only item blocking the PR.

### Build and Test Gate

```
dotnet build -c Release  →  0 errors, 0 warnings
dotnet test  -c Release  →  98 passed, 0 failed
```

---

## Full Code Review Findings

### Examined Files

| File | Verdict |
|------|---------|
| `StaThread.cs` | ✅ Correct — `TaskCreationOptions.RunContinuationsAsynchronously`, `IsBackground = true`, `ApartmentState.STA` |
| `WasapiAudioDeviceProvider.cs` | ✅ Correct — STA dispatch, test seam, `Active \| Disabled`, AOT comment, warning log |
| `IAudioSource.cs` | ✅ Full interface — `SampleRate`, `ChannelCount`, `CaptureAsync`, `IAsyncDisposable` |
| `AudioCaptureException.cs` | ✅ Sealed, `DeviceId` + `Reason` properties, correct message format |
| `CaptureManager.cs` | ✅ Bounded channel, `volatile bool`, transient-true documented, 2-second drain timeout |
| `WasapiAudioSource.cs` | ✅ Full STA pipeline — `BufferedWaveProvider` → stereo-to-mono → `WdlResamplingSampleProvider` → inner channel |
| `ArecordAudioSource.cs` | ✅ Test seam via factory, `FilePipeStartInfo` / `FailingStartInfo` cross-platform stubs, correct chunk alignment |
| `SoxAudioSource.cs` | ✅ `eofExit` flag distinguishes cancellation from EOF; install instructions in exception message |
| `PlatformAudioSource.cs` | ✅ OS dispatch correct; `NullAudioSource` `await Task.FromException` idiom avoids CS0162 cleanly |
| `IConfigStore.cs` | ✅ `OnSaved` event declared correctly |
| `JsonConfigStore.cs` | ✅ `OnSaved?.Invoke(config)` fires after atomic rename |
| `InMemoryConfigStore` | ✅ `OnSaved?.Invoke(config)` fires correctly |
| `Program.cs` | ✅ Startup, restart-on-config-change, and shutdown lifecycle correctly wired |
| `DaemonStatus.cs` | ✅ `CaptureActive = false` default |
| `WebApp.cs` | ✅ `captureManager?.IsCapturing ?? false` in status endpoint |
| `AppJsonContext.cs` | ✅ `DaemonStatus` registered; `CaptureActive` serialised via source generation |
| `runtimeconfig.template.json` | ❌ **Remove — ineffective for NativeAOT, generates ILC warning, creates false confidence (A-3)** |

### Notes for Future Phases — Not Blockers

**N-1 — `WasapiAudioSource` DataAvailable allocates a new `outBuf` per drain iteration.**
`outBuf = new float[2048]` is reassigned in the `while` loop. `ArrayPool<float>` would reduce GC pressure under continuous audio. Deferred to Phase 5.

**N-2 — Trailing partial buffer silently discarded in `ArecordAudioSource` and `SoxAudioSource`.**
EOF with `0 < pos < ChunkBytes` loses accumulated bytes. Acceptable — FT8's 15-second window is not sensitive to a few missing samples at the boundary. Deferred.

**N-3 — `CaptureManager.StopAsync` swallows all exceptions from the capture task.**
The bare `catch (Exception) { }` prevents shutdown from throwing but silently loses unexpected errors. Consider injecting `ILogger<CaptureManager>` in Phase 5. Deferred.

**N-4 — `Program.cs` shutdown calls `GetAwaiter().GetResult()` on `StopAsync`.**
`ApplicationStopping.Register` accepts `Action`, not `Func<Task>`. The 2-second timeout in `StopAsync` prevents an indefinite block. Correct for the circumstance.

---

## Prior Findings and Status

### User Feedback That Triggered This Change

> *"When I try the settings page to view the audio device the following message appears:*
> ```
> warn: OpenWSFZ.Audio.WasapiAudioDeviceProvider[0]
>       WASAPI device enumeration failed; returning 0 device(s) collected before the error.
>       System.InvalidProgramException: Common Language Runtime detected an invalid program.
>       The body of method 'Void NAudio.CoreAudioApi.Interfaces.MMDeviceEnumeratorComObject..ctor()' is invalid.
> ```"*

### Root Cause

`<PublishAot>true</PublishAot>` without a RID condition caused the SDK to bake `BuiltInComInterop.IsSupported=false` into `runtimeconfig.json` at build time. The JIT honoured this flag even during `dotnet run`. Fix: condition `PublishAot` on `'$(RuntimeIdentifier)'!=''` (commit `42dcae1`). Confirmed: 13 real devices returned after clean rebuild via `dotnet run`.

### R-1 — Resolved

Task 15.4: *"confirmed: 13 real audio devices returned by GET /api/v1/audio/devices."* Post-fix note documents the stale-binary scenario and the correct rebuild procedure.

### R-2 — Resolved

Task 15.6 carries the corrected note. ILC warning correctly framed as a confirmed, predicted failure affecting both enumeration and capture paths.

### A-1 — Partially resolved

Code comment present in `WasapiAudioDeviceProvider.cs`. PR description remains open (no PR yet). The NativeAOT/WASAPI failure is expected and documented — confirmed by manual test of the AOT binary (2026-05-21).

### A-2 — Resolved

`CaptureManager.IsCapturing` carries a `<remarks>` block documenting the transient-true window.

---

## Resolution Checklist

- [x] R-1: User rebuilds via `dotnet run`; Settings page confirmed to populate with real devices (13 devices — task 15.4)
- [x] R-1: Task 15.4 updated with post-fix verification note
- [x] R-2: Task 15.6 note corrected
- [x] A-1: AOT/WASAPI limitation comment added to `WasapiAudioDeviceProvider.cs`
- [x] A-1: PR description — deferred. Deployment model confirmed as `dotnet run` (JIT). Self-contained publish is a later-phase concern. No PR description requirement for this merge.
- [x] A-2: `IsCapturing` XML doc comment updated to describe transient-true behaviour
- [x] **A-3: Remove `src/OpenWSFZ.Daemon/runtimeconfig.template.json`** — deleted; confirmed file had only the ineffective `BuiltInComInterop.IsSupported` override.

Once A-3 is resolved, and with A-1 (PR description) to be addressed at PR creation time, this branch is approved for merge.
