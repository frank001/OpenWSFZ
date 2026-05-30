# p13 Pre-Implementation QA Review — Cross-Platform Decoder

**Reviewer:** QA  
**Branch:** `feat/p13-cross-platform-decoder`  
**Date:** 2026-05-30  
**Status:** 🔴 Defect confirmed — implementation required before CI G6 passes on Linux/macOS  
**Source defect:** `DEFECT-cross-platform-decoder.md` (repo root, merged to `main`)

---

## Summary

This document records QA's pre-implementation review of the p13 change. The defect was originally raised by QA after the p12 merge. This review confirms the defect by direct code inspection, identifies the exact change points, flags one implementation risk not covered in the defect document, and provides the acceptance checklist the developer must satisfy before merge.

---

## Confirmed Defect Evidence

### D1 — Platform guard returns empty without calling native code

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, lines 85–89  
**Severity:** Critical (total silent failure on Linux and macOS)

```csharp
// libft8.dll is Windows x64 only in p12. On other platforms return empty rather than
// crashing — the decoder reports "no decodes" which is correct: the native backend is
// not available. Cross-platform support is deferred to a future change.
if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
    return [];
```

The comment itself confirms this is an intentional deferral — not an oversight, not a dead branch. On Linux and macOS every call to `DecodeAll()` exits here. The application processes audio, frames cycles, calls `Ft8Decoder.DecodeAsync`, and logs `Cycle {Time}: 0 decode(s) found` indefinitely. There is no exception, no log warning, no indication that the native backend was never reached.

---

### D2 — `[DllImport]` token is hardcoded to `"libft8.dll"`

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, lines 44 and 58

```csharp
[DllImport("libft8.dll", EntryPoint = "ft8_lib_version_check", CallingConvention = CallingConvention.Cdecl)]
private static extern int NativeVersionCheck();

[DllImport("libft8.dll", EntryPoint = "ft8_decode_all", CallingConvention = CallingConvention.Cdecl)]
private static extern int NativeDecodeAll(…);
```

The .NET runtime resolves `[DllImport("libft8.dll")]` by passing `"libft8.dll"` verbatim to the OS loader. On Linux the loader searches for files named `libft8.dll` — it does not search for `libft8.so`, `libft8.dll.so`, or any variant. On macOS the loader searches for `libft8.dll`, `libft8.dll.dylib`, etc. Even if the `.so` or `.dylib` binary were present in the output directory, the OS would not find it under this name. A `NativeLibrary.SetDllImportResolver` must intercept the load and redirect it to the correct filename before the OS loader is consulted.

---

### D3 — `LoadAndVerify()` hardcodes `"libft8.dll"` as the path

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, line 124

```csharp
string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");

if (!File.Exists(dllPath))
    throw new InvalidOperationException(
        $"libft8.dll not found at '{dllPath}'. …");
```

Even if D2 were resolved (resolver registered, DllImport redirected), `LoadAndVerify()` would throw `InvalidOperationException: libft8.dll not found at '…/libft8.dll'` on Linux and macOS because the existence check targets the wrong filename. This is a second independent failure point.

---

### D4 — csproj declares only the Windows binary

**File:** `src/OpenWSFZ.Ft8/OpenWSFZ.Ft8.csproj`, line 23

```xml
<Content Include="Native\win-x64\libft8.dll" CopyToOutputDirectory="Always" Link="libft8.dll" />
```

There are no `linux-x64` or `osx-x64` entries. `dotnet build` on Linux or macOS copies nothing. Even if the native binaries were built and placed in the native subdirectories, they would not appear in the output directory and no native call could succeed.

---

### D5 — `[WindowsOnlyTheory]` hides the failure from CI

**File:** `tests/OpenWSFZ.Ft8.Tests/RealSignalFixtureTests.cs`, line 52  
**File:** `tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs`, lines 20–22

```csharp
[WindowsOnlyTheory(DisplayName = "FR-029: …")]
```

```csharp
public WindowsOnlyTheoryAttribute()
{
    if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        Skip = "libft8.dll is Windows x64 only. Cross-platform support is a future phase.";
}
```

The `Skip` message records this as a future phase, which is now. The three G6 fixture theories are reported as **skipped** (not failed) on `ubuntu-latest` and `macos-latest`. xUnit treats skips as successful, so the CI gate appears green. A reader of the CI log sees three yellow skips on each non-Windows leg and must know to interpret them as a missing feature, not a test gap.

**Consequence:** The combined effect of D1–D5 is that the current `main` branch has a fully green CI with a non-functional decoder on two out of three reference platforms. This is the worst form of silent failure: the gates say nothing is wrong.

---

## New Finding — Load Ordering Risk in Static Initialiser

**Severity:** Medium — potential runtime failure at first call, correctness issue if ordering is wrong  
**Not covered in the defect document**

The `SetDllImportResolver` must be registered **before** the first P/Invoke call. Any P/Invoke call that fires before the resolver is registered will use the OS default loader, which will fail (or load the wrong library) on Linux/macOS.

The current code flow is:

```
DecodeAll()
  └─ EnsureInitialized()          // double-checked lock
       └─ LoadAndVerify()
            └─ NativeVersionCheck()  // <── first DllImport call
```

The resolver must be registered inside `EnsureInitialized()` (or in the lock body of `LoadAndVerify()`) **before** `NativeVersionCheck()` is called. If the developer places the resolver registration after `NativeVersionCheck()` or in a separate method that might not be called first, the P/Invoke will fire without a resolver and the OS loader will try to find `libft8.dll` on Linux — which it won't.

**Implementation note for the developer:** The idiomatic pattern is:

```csharp
private static void LoadAndVerify()
{
    // Step 1: register the resolver FIRST — before any DllImport call
    NativeLibrary.SetDllImportResolver(
        typeof(Ft8LibInterop).Assembly,
        static (libraryName, assembly, searchPath) =>
        {
            if (libraryName != "libft8.dll") return IntPtr.Zero;
            string fileName = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                            : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                            : "libft8.so";
            return NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, fileName));
        });

    // Step 2: THEN check existence and call DllImport functions
    string fileName2 = …;
    string libPath = Path.Combine(AppContext.BaseDirectory, fileName2);
    if (!File.Exists(libPath)) throw …;
    int actual = NativeVersionCheck();   // resolver is now active
    …
}
```

Note: `NativeLibrary.SetDllImportResolver` throws `InvalidOperationException` if called more than once per assembly. The existing double-checked lock ensures `LoadAndVerify()` is called exactly once, so this is safe.

---

## Additional Observations

### O1 — `Marshal.SizeOf<Ft8NativeResult>()` check runs at first load, not every call

**File:** `Ft8LibInterop.cs`, lines 146–151  
**Status:** Observation only; no action required

The XML doc comment on `LoadAndVerify()` states "Runs exactly once during lazy init so the reflection cost… is paid only at first load, not on every decode call." This is correct — the check is inside `LoadAndVerify()` which is guarded by the double-checked lock. The minor note from the p12 QA review (that the comment incorrectly said "cached by the runtime after the first call") was already addressed. Confirming the current code and comment are consistent.

### O2 — `new Ft8NativeResult[MaxResults]` allocated on every decode call

**File:** `Ft8LibInterop.cs`, line 93  
**Status:** Low — deferred per p12 QA note N2 carry-through; not merge-blocking for p13

The 140-element `Ft8NativeResult[]` is heap-allocated on every decode cycle. At 48 bytes per struct this is 6 720 bytes per call — negligible for a 15-second cycle but a clear candidate for `ArrayPool<Ft8NativeResult>` if profiling ever identifies GC pressure. No action for p13.

### O3 — `libft8.version.txt` only documents the Windows binary

**File:** `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`  
**Status:** Must be fixed in p13 (task 3.1)

The existing `libft8.version.txt` tracks only the Windows build. After the Linux and macOS binaries are built and committed, the developer must add platform rows for each. The file should record at minimum: platform, compiler toolchain + version, build date, source commit SHA, and SNR formula version. QA will verify these rows are present before approving merge.

---

## Required Fixes Before Merge

| ID | File | Issue | Task |
|---|---|---|---|
| **R1** | `Ft8LibInterop.cs` L85–89 | Remove platform guard | 5.2 |
| **R2** | `Ft8LibInterop.cs` | Add `SetDllImportResolver` before first DllImport call | 5.3 |
| **R3** | `Ft8LibInterop.cs` `LoadAndVerify()` | Replace hardcoded `"libft8.dll"` path with platform-appropriate name | 5.4 |
| **R4** | `OpenWSFZ.Ft8.csproj` | Add `<Content>` items for `libft8.so` and `libft8.dylib` | 4.2 |
| **R5** | `Native/linux-x64/libft8.so` | Build and commit Linux x64 binary | 1.1–1.5 |
| **R6** | `Native/osx-x64/libft8.dylib` | Build and commit macOS x64 binary | 2.1–2.5 |
| **R7** | `WindowsOnlyAttributes.cs` | Delete file; replace all `[WindowsOnly*]` uses | 6.1–6.3 |
| **R8** | `libft8.version.txt` | Add Linux and macOS build rows | 3.1 |
| **R9** | `Native/BUILD.md` | Add Linux and macOS build sections | 7.1–7.2 |

All nine items are required. The merge gate is blocked until CI confirms G6 passes (not skips) on all three matrix legs.

---

## Acceptance Checklist

The developer must provide the following evidence before this change goes to QA for final sign-off:

- [ ] `dotnet build -c Release` — 0 errors, 0 warnings on Windows (G1)
- [ ] `dotnet test -c Release` on Windows — suite count ≥ 208, 0 failures; G6 fixture tests: 3/3 pass
- [ ] CI run with all three matrix legs **green**; the `ubuntu-latest` and `macos-latest` legs must show G6 fixture tests as **passed** (3/3 each), not skipped
- [ ] `grep -rn "WindowsOnly" tests/` — no output (zero remaining uses)
- [ ] `git ls-files src/OpenWSFZ.Ft8/Native/` lists:
  - `win-x64/libft8.dll`
  - `linux-x64/libft8.so`
  - `osx-x64/libft8.dylib`
- [ ] `libft8.version.txt` contains rows for all three platforms
- [ ] `nm -D libft8.so | grep "ft8_"` output (paste in PR or commit message) — both `ft8_lib_version_check` and `ft8_decode_all` visible
- [ ] `nm -gU libft8.dylib | grep "ft8_"` output — both symbols visible
- [ ] `dotnet run --project tools/TraceabilityCheck` — G3 green
- [ ] `dotnet run --project tools/LicenseInventoryCheck` — G5 green

QA's final sign-off is a CAPTAIN gate (task 9.3). Merge proceeds only after all checklist items are confirmed and CI is green with zero skips on all three legs.
