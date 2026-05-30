## Context

The p12-ft8lib-port change shipped a working FT8 decoder on Windows x64, but included a deliberate platform guard (`IsOSPlatform(Windows)`) that returns an empty array on Linux and macOS. This was accepted as a short-term workaround to unblock p12, with an implicit expectation that a follow-up change would complete the cross-platform work. A post-merge QA audit recognised the workaround as a high-severity defect: the decoder silently produces zero decodes on two of the three required platforms, and the `[WindowsOnlyFact]` / `[WindowsOnlyTheory]` test attributes cause the G6 fixture tests to be skipped on the Linux and macOS CI legs, masking the failure entirely. This change removes the guard, commits the missing native binaries, and ensures CI exercises the decoder on all three legs.

The shim source (`ft8_shim.c`) and the `kgoba/ft8_lib` submodule already contain everything needed to build for Linux and macOS. The MSVC-specific VLA patches committed in `native/ft8_lib_build/patched/` are not needed on GCC/Clang — those compilers support C11 VLAs natively. The struct layout and export ABI of the shim are platform-independent by design.

## Goals / Non-Goals

**Goals:**

- `libft8.so` (Linux x64) and `libft8.dylib` (macOS x64) compiled from the committed shim source and committed to the repo
- All three binaries declared in `OpenWSFZ.Ft8.csproj` and copied to the output directory on every build
- `Ft8LibInterop.cs` loads the correct binary on every platform via `NativeLibrary.SetDllImportResolver` — no platform guard
- G6 real-signal fixture tests run and pass on all three CI legs, with zero skips
- `BUILD.md` documents the exact build steps for each platform

**Non-Goals:**

- ARM64 / Apple Silicon support (not a reference platform for this project)
- .NET NativeAOT or linker-trimming compatibility for the P/Invoke layer
- CI-time compilation of native binaries (pre-compiled binaries committed to repo, same as Windows)
- Recovery-rate improvements or decoder algorithm changes

## Decisions

### D1 — Committed pre-compiled binaries (not CI-compiled)

**Decision:** Commit `libft8.so` and `libft8.dylib` to the repo as tracked binary files, identically to how `libft8.dll` is committed for Windows.

**Rationale:** The Windows precedent (p12) established this pattern. It simplifies CI significantly — CI does not need a full C toolchain, build steps, or per-platform artefact uploads. The shim source and submodule provide full reproducibility; anyone with the appropriate toolchain can rebuild from `BUILD.md`. The binaries are small (~60–200 KB) and change infrequently (only when the shim ABI version bumps).

**Alternative rejected:** CI compilation (`makefile` step in the workflow) would ensure binaries are always fresh but adds toolchain dependencies and build complexity. Deferred to a future change if the maintenance cost of pre-compiled binaries proves problematic.

---

### D2 — `NativeLibrary.SetDllImportResolver` for cross-platform P/Invoke

**Decision:** Register a `DllImportResolver` on the assembly that maps the `"libft8.dll"` DllImport token to the platform-appropriate filename (`libft8.so` on Linux, `libft8.dylib` on macOS, `libft8.dll` on Windows), loaded from `AppContext.BaseDirectory`.

**Rationale:** The `[DllImport("libft8.dll")]` attributes throughout `Ft8LibInterop.cs` work fine on Windows because the OS loader finds `libft8.dll` in the probe path. On Linux/macOS, the loader does not find a file named `libft8.dll` even if `libft8.so` is present. `NativeLibrary.SetDllImportResolver` intercepts the load before the OS sees it and directs it to the correct file. This is the idiomatic .NET cross-platform pattern; it does not require changing the `[DllImport]` attribute strings.

**Alternative rejected:** Renaming `[DllImport]` attributes to use a platform-neutral token (e.g., `"libft8"`) and relying on default OS probing rules (`libft8.dll` on Windows, `libft8.so` on Linux, `libft8.dylib` on macOS). This would work in theory but the OS probing rules for `[DllImport]` differ subtly between .NET versions and platforms. The `SetDllImportResolver` approach gives explicit, auditable control.

---

### D3 — Original submodule sources for Linux/macOS build (no VLA patches)

**Decision:** Build `libft8.so` and `libft8.dylib` directly from `native/ft8_lib/` (the unpatched submodule sources). Do not apply the VLA patches in `native/ft8_lib_build/patched/`.

**Rationale:** The VLA patches in `patched/` were necessary only because MSVC does not support C99/C11 variable-length arrays. GCC (≥10) and Clang (≥3.3) support VLAs natively under `-std=c11`. Using the unpatched sources keeps the Linux and macOS builds identical to what upstream `kgoba/ft8_lib` intends and avoids any risk of the patches introducing subtle divergence.

---

### D4 — Remove `WindowsOnlyAttributes.cs` entirely

**Decision:** Delete `tests/OpenWSFZ.Ft8.Tests/WindowsOnlyAttributes.cs` and replace every `[WindowsOnlyFact]` / `[WindowsOnlyTheory]` usage with `[Fact]` / `[Theory]`.

**Rationale:** These attributes exist solely to skip tests on platforms where the decoder previously did nothing. Once the decoder works on all three platforms, there is no justification for the skip. Keeping a `[WindowsOnlyFact]` attribute in the codebase would be a standing invitation to re-introduce platform-specific test skips.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| macOS binary must be built on Apple hardware | Developer builds it locally; committing it to the repo removes the CI dependency. If Apple Silicon is the dev machine, target `x86_64-apple-macos10.15` explicitly with `-target`. |
| Struct packing differs between compilers | The shim uses `int` (4-byte), `float` (4-byte), `int` (4-byte), `char[36]` — all standard C types with no compiler extensions. Size verified by the managed `Marshal.SizeOf` assertion that runs on every call. If packing drifted, the ABI self-test would catch it at startup. |
| `SetDllImportResolver` must be registered before the first P/Invoke call | The resolver is registered in the static constructor of `Ft8LibInterop`, before `LoadAndVerify()` is called. .NET guarantees static constructors run once before any instance method. |
| G6 tests were previously never run on Linux/macOS | Removing the `[WindowsOnly*]` guard means CI will run those tests for the first time. If the Linux/macOS binary is not ABI-compatible, CI will fail. This is the intended outcome — the gate correctly blocks until the issue is resolved. |

## Migration Plan

1. Build `libft8.so` (Linux x64) on an Ubuntu x64 machine per the commands in `BUILD.md`.
2. Build `libft8.dylib` (macOS x64) on a macOS machine per the commands in `BUILD.md`.
3. Commit both binaries to the repo under `src/OpenWSFZ.Ft8/Native/{linux-x64,osx-x64}/`.
4. Update `OpenWSFZ.Ft8.csproj` to declare all three `<Content>` items.
5. Update `Ft8LibInterop.cs`: add resolver, remove guard, update `LoadAndVerify()`.
6. Delete `WindowsOnlyAttributes.cs`; replace all `[WindowsOnly*]` usages with `[Fact]`/`[Theory]`.
7. Update `BUILD.md` with Linux and macOS sections.
8. Push to CI; verify all three matrix legs pass the G6 tests with zero skips.

No database migrations, no API changes, no user-visible behaviour changes on Windows.

## Open Questions

*(none — the defect document and specs fully specify the required changes)*
