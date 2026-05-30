# Defect: FT8 Decoder is Windows-Only — NFR-001 Violation

**Raised by:** QA  
**Severity:** High — two of three required platforms are non-functional  
**Requirement violated:** NFR-001 — *"The application SHALL build and **run** on Windows, Linux, and macOS from a single source tree."*  
**Affects:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, `src/OpenWSFZ.Ft8/OpenWSFZ.Ft8.csproj`, `tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs`, `src/OpenWSFZ.Ft8/Native/BUILD.md`

---

## What is Wrong

The p12 port delegated FT8 decoding to a native library (`kgoba/ft8_lib`) compiled only for Windows x64 (`libft8.dll`). Three changes were made that together make the decoder a Windows-only feature:

1. **`Ft8LibInterop.cs` line 88** — a platform guard returns an empty array without calling native code on any non-Windows OS:
   ```csharp
   if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
       return [];
   ```

2. **`Ft8LibInterop.cs` lines 44, 58** — `[DllImport]` attributes hardcode `"libft8.dll"` as the library name, which the OS loader will not find on Linux or macOS even if the correct binary were present.

3. **`Ft8LibInterop.cs` line 124** — `LoadAndVerify()` constructs the path as `libft8.dll` unconditionally.

4. **`OpenWSFZ.Ft8.csproj` line 23** — only `Native\win-x64\libft8.dll` is declared as a content file; no Linux or macOS binaries are committed or referenced.

5. **`tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs`** — `[WindowsOnlyFact]` and `[WindowsOnlyTheory]` cause the G6 real-signal fixture tests to be **skipped** on Linux and macOS CI legs. The gate appears green on those legs but has never actually exercised the decoder.

The result: on Linux and macOS the application starts, audio is captured, decode cycles are triggered — but `DecodeAll()` returns empty immediately. No FT8 messages are ever decoded. This is a silent, total functional failure on two of the three required platforms.

---

## Required Changes

### 1. Build native shared libraries for Linux x64 and macOS x64

On a **Linux x64** machine (GCC ≥ 10, C11):

```bash
cd native/ft8_lib

# Compile ft8_lib sources (VLAs are fine on GCC — use the submodule source directly)
gcc -std=c11 -O2 -Wall -fPIC -I. -c \
    ft8/constants.c ft8/crc.c ft8/decode.c ft8/ldpc.c \
    ft8/message.c ft8/text.c \
    common/monitor.c \
    fft/kiss_fft.c fft/kiss_fftr.c

# Compile the shim
gcc -std=c11 -O2 -Wall -fPIC -I. -c \
    ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

# Link shared library
gcc -shared -o libft8.so \
    constants.o crc.o decode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o \
    -lm

# Install
mkdir -p ../../src/OpenWSFZ.Ft8/Native/linux-x64
cp libft8.so ../../src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so
```

On a **macOS x64** machine (Xcode Command Line Tools, Clang, targeting x86_64):

```bash
cd native/ft8_lib

# Compile ft8_lib sources
clang -std=c11 -O2 -Wall -fPIC -I. -target x86_64-apple-macos10.15 -c \
    ft8/constants.c ft8/crc.c ft8/decode.c ft8/ldpc.c \
    ft8/message.c ft8/text.c \
    common/monitor.c \
    fft/kiss_fft.c fft/kiss_fftr.c

# Compile the shim
clang -std=c11 -O2 -Wall -fPIC -I. -target x86_64-apple-macos10.15 -c \
    ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

# Link dynamic library
clang -dynamiclib -target x86_64-apple-macos10.15 \
    -o libft8.dylib \
    constants.o crc.o decode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o

# Install
mkdir -p ../../src/OpenWSFZ.Ft8/Native/osx-x64
cp libft8.dylib ../../src/OpenWSFZ.Ft8/Native/osx-x64/libft8.dylib
```

**Notes on the shim source:**
- The `#ifdef _MSC_VER` block (the `stpcpy` compat function) is automatically skipped by GCC/Clang. No source modification is needed.
- `_Thread_local` is C11 standard and supported by both GCC ≥ 5 and Clang ≥ 3.3.
- The VLA patches in `native/ft8_lib_build/patched/` were applied for MSVC only. Use the original submodule source (`native/ft8_lib/`) on Linux and macOS.
- Verify the exports: `nm -D libft8.so | grep "ft8_"` (Linux) or `nm -gU libft8.dylib | grep "ft8_"` (macOS) — both `ft8_lib_version_check` and `ft8_decode_all` must appear.

Commit both binaries to the repo. Add build notes for each to `BUILD.md` and update `libft8.version.txt` with platform-specific rows.

---

### 2. Update `OpenWSFZ.Ft8.csproj` — include all three binaries

Replace the single Windows content item with all three:

```xml
<!-- libft8 native shim — pre-compiled for each reference platform.
     All three files are included; the OS ignores the ones it cannot load.
     NativeLibrary.Load selects the correct file by name at runtime.    -->
<Content Include="Native\win-x64\libft8.dll"    CopyToOutputDirectory="Always" Link="libft8.dll"    />
<Content Include="Native\linux-x64\libft8.so"   CopyToOutputDirectory="Always" Link="libft8.so"    />
<Content Include="Native\osx-x64\libft8.dylib"  CopyToOutputDirectory="Always" Link="libft8.dylib" />
```

---

### 3. Update `Ft8LibInterop.cs`

#### 3a. Remove the platform guard (lines ~85–89)

Delete these lines entirely:

```csharp
// libft8.dll is Windows x64 only in p12. On other platforms return empty rather than
// crashing — the decoder reports "no decodes" which is correct: the native backend is
// not available. Cross-platform support is deferred to a future change.
if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
    return [];
```

#### 3b. Add a `NativeLibrary.SetDllImportResolver` call

The `[DllImport("libft8.dll")]` attributes use `"libft8.dll"` as a lookup token. The OS loader will not find that name on Linux or macOS even when `libft8.so`/`libft8.dylib` is present. Register a resolver that maps the token to the correct path before any P/Invoke call can occur.

Add this to the static initialiser block (or a `static Ft8LibInterop()` constructor), **before** any call to `LoadAndVerify()`:

```csharp
NativeLibrary.SetDllImportResolver(
    typeof(Ft8LibInterop).Assembly,
    static (libraryName, assembly, searchPath) =>
    {
        if (libraryName != "libft8.dll") return IntPtr.Zero;

        string fileName = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                        : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                        : "libft8.so";

        string fullPath = Path.Combine(AppContext.BaseDirectory, fileName);
        return NativeLibrary.Load(fullPath);
    });
```

#### 3c. Update `LoadAndVerify()` — resolve the library name per platform

Replace the hardcoded `"libft8.dll"` path with the platform-appropriate name:

```csharp
private static void LoadAndVerify()
{
    string fileName = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                    : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                    : "libft8.so";

    string libPath = Path.Combine(AppContext.BaseDirectory, fileName);

    if (!File.Exists(libPath))
        throw new DllNotFoundException(
            $"Native library not found at '{libPath}'. " +
            "Ensure the project was built and the native binary for this platform is present.");

    // SetDllImportResolver already loads the library; the call above is for
    // the existence check and for the version sentinel below.
    int actual   = ft8_lib_version_check();
    int expected = FT8_SHIM_VERSION;
    if (actual != expected)
        throw new InvalidOperationException(
            $"Native library ABI mismatch at '{libPath}'. " +
            $"Expected version {expected}, got {actual}. " +
            "Rebuild the native library from the committed shim source (see src/OpenWSFZ.Ft8/Native/BUILD.md).");
}
```

> **Note on load ordering.** `SetDllImportResolver` must be registered before the first `[DllImport]`-attributed call. If `LoadAndVerify()` calls `ft8_lib_version_check()` (a DllImport method), register the resolver first, then call `LoadAndVerify()`. If the current code registers the resolver in a static field initialiser, verify the initialisation order is deterministic.

---

### 4. Delete `WindowsOnlyAttributes.cs` and remove all uses

`tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs` must be deleted. All test attributes must revert to the standard `[Fact]` and `[Theory]` forms.

Grep for every use of `[WindowsOnlyFact]` and `[WindowsOnlyTheory]` in the test projects and replace them. After this change, the G6 real-signal fixture tests must run — and pass — on all three CI legs.

```bash
grep -rn "WindowsOnly" tests/
```

---

### 5. Update `BUILD.md`

Add sections for Linux and macOS build procedures mirroring the existing Windows section, including:
- Prerequisites (GCC version / Xcode version)
- Exact compiler commands
- How to verify exports
- Expected binary size (approximate)

---

## Acceptance Criteria

The defect is resolved when **all** of the following are true:

| Check | Command | Requirement |
|---|---|---|
| G1 gate | `dotnet build -c Release` | 0 errors, 0 warnings on all three platforms |
| G6 gate (Windows) | `dotnet test … --filter RealSignal` | 3/3 pass |
| G6 gate (Linux) | `dotnet test … --filter RealSignal` | 3/3 pass — **not skipped** |
| G6 gate (macOS) | `dotnet test … --filter RealSignal` | 3/3 pass — **not skipped** |
| Full suite | `dotnet test -c Release` | 0 failures on all three platforms |
| No `WindowsOnly` guards | `grep -r WindowsOnly tests/` | No output |
| All three binaries committed | `git ls-files src/OpenWSFZ.Ft8/Native/` | `win-x64/libft8.dll`, `linux-x64/libft8.so`, `osx-x64/libft8.dylib` all present |

CI already runs a three-OS matrix (`windows-latest`, `ubuntu-latest`, `macos-latest`). Once the binaries are committed and the code changes are made, the CI run itself is the acceptance test. All three legs must be green with 0 skips on the G6 test.

---

## Context: Why the Guard Was Accepted in p12

The `IsOSPlatform(Windows)` guard was introduced to prevent a crash during the p12 port while cross-platform build infrastructure was deferred. This was a legitimate short-term measure — but it was never flagged as a gate condition on the p12 merge, and QA did not catch the NFR-001 violation at review time. That is a process failure on QA's part, noted here for the record.

The guard is not a known-acceptable deferral. It is a defect. It must be corrected before any further feature work on the decode pipeline proceeds.
