## 1. Build libft8.so — Linux x64

> **Environment**: Ubuntu (or Debian) x64 with GCC ≥ 10 and `build-essential` installed.
> **WSL is acceptable**: WSL2 running Debian satisfies this requirement. GCC 14.2.0 is confirmed available in the Debian WSL distribution on this machine. The repository is accessible inside WSL at `/mnt/d/Projects/claude/OpenWSFZ` (adjust drive letter if the repo is on a different drive). Open a WSL terminal and run all commands below from within that WSL session.
> Use the **unpatched** submodule sources (`native/ft8_lib/`) — not the MSVC-patched files in `native/ft8_lib_build/patched/`.
> Run from the repository root.

- [ ] 1.0 Open a WSL Debian terminal (`wsl -d Debian`). Navigate to the repo root: `cd /mnt/d/Projects/claude/OpenWSFZ`. Verify the submodule sources are present: `ls native/ft8_lib/ft8/` — should list `.c` files.
- [ ] 1.1 Confirm GCC ≥ 10 is available: `gcc --version`
- [ ] 1.2 Compile all ft8_lib source files and the shim as position-independent objects:
      ```bash
      cd native/ft8_lib
      gcc -std=c11 -O2 -Wall -fPIC -I. -c \
          ft8/constants.c ft8/crc.c ft8/decode.c ft8/ldpc.c \
          ft8/message.c ft8/text.c \
          common/monitor.c \
          fft/kiss_fft.c fft/kiss_fftr.c
      gcc -std=c11 -O2 -Wall -fPIC -I. -c \
          ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c
      ```
- [ ] 1.3 Link the shared library:
      ```bash
      gcc -shared -o libft8.so \
          constants.o crc.o decode.o ldpc.o message.o text.o \
          monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o \
          -lm
      ```
- [ ] 1.4 Verify exports — both `ft8_lib_version_check` and `ft8_decode_all` must appear:
      ```bash
      nm -D libft8.so | grep "ft8_"
      ```
- [ ] 1.5 Install binary to repo:
      ```bash
      mkdir -p ../../src/OpenWSFZ.Ft8/Native/linux-x64
      cp libft8.so ../../src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so
      ```

## 2. Build libft8.dylib — macOS ARM64 (via GitHub Actions)

> **Environment**: No Mac is available on the developer machine. The binary is produced by a
> temporary, `workflow_dispatch`-only GitHub Actions workflow that runs on the `macos-latest`
> runner (ARM64 / Apple Silicon). The produced artifact is downloaded, committed to the
> repository, and the temporary workflow file is then deleted.
>
> **Architecture note**: The CI matrix uses `macos-latest` with `rid: osx-arm64`. The .NET
> runtime on that runner is ARM64. A P/Invoke native library loaded by an ARM64 .NET process
> must itself be ARM64. Targeting `x86_64` would cause a fatal load failure on the CI macOS
> leg. The library therefore targets `arm64-apple-macos11.0` (macOS 11 Big Sur — the first
> macOS release available on Apple Silicon hardware).
>
> Use the **unpatched** submodule sources (`native/ft8_lib/`).

- [ ] 2.1 Create `.github/workflows/build-macos-dylib.yml` with the following content:

      ```yaml
      name: Build macOS native library (one-shot)

      on:
        workflow_dispatch:

      jobs:
        build-macos-dylib:
          runs-on: macos-latest
          steps:
            - uses: actions/checkout@v6
              with:
                submodules: recursive

            - name: Build libft8.dylib (ARM64)
              working-directory: native/ft8_lib
              run: |
                clang -std=c11 -O2 -Wall -fPIC -I. -target arm64-apple-macos11.0 -c \
                    ft8/constants.c ft8/crc.c ft8/decode.c ft8/ldpc.c \
                    ft8/message.c ft8/text.c \
                    common/monitor.c \
                    fft/kiss_fft.c fft/kiss_fftr.c
                clang -std=c11 -O2 -Wall -fPIC -I. -target arm64-apple-macos11.0 -c \
                    ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c
                clang -dynamiclib -target arm64-apple-macos11.0 \
                    -o libft8.dylib \
                    constants.o crc.o decode.o ldpc.o message.o text.o \
                    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o

            - name: Verify exports
              working-directory: native/ft8_lib
              run: nm -gU libft8.dylib | grep "ft8_"

            - name: Upload artifact
              uses: actions/upload-artifact@v7
              with:
                name: libft8-dylib-osx-arm64
                path: native/ft8_lib/libft8.dylib
                retention-days: 7
      ```

- [ ] 2.2 Commit the workflow file and push to `feat/p13-cross-platform-decoder`.
- [ ] 2.3 Navigate to **GitHub → Actions → Build macOS native library (one-shot)** and trigger
      via **Run workflow** (select branch `feat/p13-cross-platform-decoder`).
- [ ] 2.4 Wait for the workflow to complete. Download the `libft8-dylib-osx-arm64` artifact
      (a ZIP). Extract `libft8.dylib` from it.
- [ ] 2.5 Copy the **Verify exports** step log output (the `nm -gU` output) for the PR description —
      both `_ft8_lib_version_check` and `_ft8_decode_all` must appear.
- [ ] 2.6 Install binary to repo:
      ```bash
      mkdir -p src/OpenWSFZ.Ft8/Native/osx-arm64
      cp libft8.dylib src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib
      ```
- [ ] 2.7 Delete the temporary workflow: `rm .github/workflows/build-macos-dylib.yml`

## 3. Commit native binaries and update version file

- [ ] 3.1 Update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — add Linux and macOS rows with platform, compiler, and build date. Format mirrors the existing Windows row.
- [ ] 3.2 Commit both binaries: `git add src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`

## 4. Update OpenWSFZ.Ft8.csproj

- [ ] 4.1 Open `src/OpenWSFZ.Ft8/OpenWSFZ.Ft8.csproj`. Locate the existing `<Content Include="Native\win-x64\libft8.dll" … />` item.
- [ ] 4.2 Replace it with all three platform items:
      ```xml
      <!-- libft8 native shim — pre-compiled for each reference platform.
           All three files are included; the OS ignores the ones it cannot load.
           NativeLibrary.SetDllImportResolver selects the correct file at runtime. -->
      <Content Include="Native\win-x64\libft8.dll"     CopyToOutputDirectory="Always" Link="libft8.dll"    />
      <Content Include="Native\linux-x64\libft8.so"    CopyToOutputDirectory="Always" Link="libft8.so"    />
      <Content Include="Native\osx-arm64\libft8.dylib" CopyToOutputDirectory="Always" Link="libft8.dylib" />
      ```
- [ ] 4.3 `dotnet build -c Release` — 0 errors, 0 warnings; confirm all three binary files appear in `bin/Release/net10.0/`

## 5. Update Ft8LibInterop.cs

- [ ] 5.1 Open `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`.
- [ ] 5.2 **Remove the platform guard** (lines ~85–89) — delete the block:
      ```csharp
      if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
          return [];
      ```
      (including any associated comment)
- [ ] 5.3 **Add `NativeLibrary.SetDllImportResolver`** in the static initialiser (before the `LoadAndVerify()` call):
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
- [ ] 5.4 **Update `LoadAndVerify()`** — replace the hardcoded `"libft8.dll"` path with the platform-appropriate name:
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

          int actual   = ft8_lib_version_check();
          int expected = FT8_SHIM_VERSION;
          if (actual != expected)
              throw new InvalidOperationException(
                  $"Native library ABI mismatch at '{libPath}'. " +
                  $"Expected version {expected}, got {actual}. " +
                  "Rebuild the native library from the committed shim source (see src/OpenWSFZ.Ft8/Native/BUILD.md).");
      }
      ```
- [ ] 5.5 `dotnet build -c Release` — 0 errors, 0 warnings

## 6. Remove WindowsOnlyAttributes and fix tests

- [ ] 6.1 Delete `tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs`
- [ ] 6.2 Open `tests/OpenWSFZ.Ft8.Tests/RealSignalFixtureTests.cs`. Replace `[WindowsOnlyTheory(DisplayName = "...")]` with `[Theory(DisplayName = "...")]` (retain the DisplayName value unchanged).
- [ ] 6.3 Verify no remaining references: `grep -rn "WindowsOnly" tests/` — must produce no output
- [ ] 6.4 `dotnet build -c Release` — 0 errors, 0 warnings

## 7. Update BUILD.md

- [ ] 7.1 Add a **Build Procedure (Linux x64, GCC)** section to `src/OpenWSFZ.Ft8/Native/BUILD.md` with:
      - Prerequisites (GCC ≥ 10, `build-essential`)
      - Exact compiler commands (matching tasks 1.2–1.5)
      - Export verification command
      - Approximate expected binary size
- [ ] 7.2 Add a **Build Procedure (macOS ARM64, Clang)** section with:
      - Prerequisites (Xcode Command Line Tools — available on any macOS or `macos-latest` GitHub Actions runner)
      - Exact compiler commands (matching tasks 2.1, using `-target arm64-apple-macos11.0`)
      - Export verification command (`nm -gU libft8.dylib | grep "ft8_"`)
      - Note that in practice this binary is produced via the one-shot GitHub Actions workflow (task 2.1–2.7) since no Mac is available locally
      - Approximate expected binary size

## 8. Verify all gates

- [ ] 8.1 `dotnet build -c Release` — G1 gate: 0 errors, 0 warnings
- [ ] 8.2 `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "RealSignal"` on Windows — 3/3 pass (G6 gate)
- [ ] 8.3 `dotnet test -c Release` (full suite) — 0 failures; confirm skipped count unchanged vs. p12 (4 skips for synthetic round-trip tests, no new skips)
- [ ] 8.4 `dotnet run --project tools/TraceabilityCheck` — G3 gate green
- [ ] 8.5 `dotnet run --project tools/LicenseInventoryCheck` — G5 gate green

## 9. Branch, CI, and PR

- [ ] 9.1 Commit all changes on branch `feat/p13-cross-platform-decoder`
- [ ] 9.2 Open PR to `main`; confirm CI green on all three matrix legs (`windows-latest`, `ubuntu-latest`, `macos-latest`)
      — **Critical check**: G6 tests must PASS (not skip) on `ubuntu-latest` and `macos-latest`
- [ ] 9.3 CAPTAIN: review CI results — confirm G6 passes with zero skips on all three legs; approve for merge
      ← CAPTAIN gate
- [ ] 9.4 Merge PR; archive this change (`opsx:archive p13-cross-platform-decoder`)
