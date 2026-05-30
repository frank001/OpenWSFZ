## Why

The p12-ft8lib-port change ported the FT8 decoder to `kgoba/ft8_lib` but introduced a silent, total functional failure on Linux and macOS: a platform guard in `Ft8LibInterop.cs` returns an empty array on every non-Windows call, `WindowsOnlyAttributes.cs` skips the G6 real-signal tests on those CI legs, and no Linux or macOS native binaries were ever built or committed. This violates **NFR-001** (the application SHALL build and run on Windows, Linux, and macOS) and was captured as a high-severity defect in `DEFECT-cross-platform-decoder.md`. The defect must be resolved before any further decode-pipeline work proceeds.

## What Changes

- **Build `libft8.so` (Linux x64)** from `ft8_shim.c` + `kgoba/ft8_lib` submodule using GCC; commit to `src/OpenWSFZ.Ft8/Native/linux-x64/`.
- **Build `libft8.dylib` (macOS x64)** from `ft8_shim.c` + `kgoba/ft8_lib` submodule using Clang; commit to `src/OpenWSFZ.Ft8/Native/osx-x64/`.
- **Update `OpenWSFZ.Ft8.csproj`** — declare all three native binaries as `<Content CopyToOutputDirectory="Always" />` items.
- **Update `Ft8LibInterop.cs`** — remove the `IsOSPlatform(Windows)` platform guard; add `NativeLibrary.SetDllImportResolver` to map the `"libft8.dll"` import token to the platform-appropriate filename; update `LoadAndVerify()` to resolve the correct filename per platform.
- **Delete `WindowsOnlyAttributes.cs`** — remove `[WindowsOnlyFact]` and `[WindowsOnlyTheory]` from all test files; revert to plain `[Fact]` and `[Theory]` so the G6 real-signal tests run and pass on all three CI legs.
- **Update `Native/BUILD.md`** — add Linux and macOS build sections with exact compiler commands, prerequisites, and export verification steps.

## Capabilities

### New Capabilities

*(none — no new capabilities are introduced)*

### Modified Capabilities

- `ft8lib-interop`: The implementation must be brought into compliance with the already-written spec requirements for cross-platform P/Invoke loading. The spec (`openspec/specs/ft8lib-interop/spec.md`) already states that a platform guard returning empty on non-Windows is a violation; this change makes the code match the spec.
- `ft8-decoder`: The G6 real-signal gate must pass on all three CI legs (not just Windows). The spec already requires Linux and macOS scenarios; the `[WindowsOnly*]` test attributes that currently skip those scenarios must be removed.

## Impact

- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — code changes (platform resolver, guard removal, path resolution)
- `src/OpenWSFZ.Ft8/OpenWSFZ.Ft8.csproj` — new `<Content>` items for Linux and macOS binaries
- `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` — new binary (Linux x64, GCC)
- `src/OpenWSFZ.Ft8/Native/osx-x64/libft8.dylib` — new binary (macOS x64, Clang)
- `src/OpenWSFZ.Ft8/Native/BUILD.md` — updated with Linux and macOS build instructions
- `tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs` — deleted
- `tests/OpenWSFZ.Ft8.Tests/RealSignalFixtureTests.cs` — `[WindowsOnlyFact]` → `[Fact]`
- Any other test file using `[WindowsOnlyFact]` or `[WindowsOnlyTheory]`
- CI (`ubuntu-latest`, `macos-latest` legs) — G6 tests will now execute and must pass
