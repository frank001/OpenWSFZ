# D-002 Fix — Developer Instructions: Shim Constant Adjustment

**Issued by:** QA  
**Date:** 2026-06-11  
**Reason:** Two R&R S1 runs at target RMS 0.08 and 0.20 both produced bias = +2.283 dB.
PCM normalisation is mathematically invariant to amplitude when both `signal_db` and
`noise_floor_db` are derived from the same waterfall. The residual +0.28 dB gap cannot be
closed by any choice of `PcmNormalisationTargetRms`. The root cause is the shim SNR constant.

**QA will re-run S1 immediately when you notify that the build is deployed.**

---

## What to change

### 1 — `ft8_shim.h` — bump `FT8_SHIM_VERSION`

File: `src/OpenWSFZ.Ft8/Native/ft8_shim.h`

Change the `#define` and its comment to reflect the new version:

```c
// Before
#define FT8_SHIM_VERSION 20260005

// After
#define FT8_SHIM_VERSION 20260006
```

Add a version history entry in the file's header comment block to describe the change:

```
 * 20260006 — D-002 fix: SNR calibration; bandwidth constant -26.0 → -26.5 dB
 *            to bring OpenWSFZ SNR bias within ±2.0 dB (R&R S1 gate).
```

---

### 2 — `ft8_shim.c` — adjust the SNR constant

File: `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

Line 442. Change:

```c
float snr = signal_db - noise_floor_db - 26.0f;
```

to:

```c
float snr = signal_db - noise_floor_db - 26.5f;
```

Also update the version history comment in the file's preamble (near the existing `20260005`
entry) to document 20260006.

---

### 3 — Rebuild native binaries (all three platforms)

The instructions below are taken verbatim from `BUILD.md`. Follow them in order.
All three binaries must be rebuilt from the updated `ft8_shim.c`/`ft8_shim.h` before
any R&R run.

#### Windows x64 — MSVC (x64 Native Tools Command Prompt)

```batch
cd native/ft8_lib

cl /I. /std:c11 /O2 /W3 /c ^
   ft8/constants.c ft8/crc.c ft8/decode.c ft8/encode.c ft8/ldpc.c ft8/message.c ft8/text.c ^
   common/monitor.c ^
   fft/kiss_fft.c fft/kiss_fftr.c

cl /I. /std:c11 /O2 /W3 /c ^
   ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

link /DLL /OUT:libft8.dll /EXPORT:ft8_lib_version_check /EXPORT:ft8_decode_all /EXPORT:ft8_get_last_pass_counts /EXPORT:ft8_get_max_passes /EXPORT:ft8_get_last_noise_floor_db ^
   constants.obj crc.obj decode.obj encode.obj ldpc.obj message.obj text.obj ^
   monitor.obj kiss_fft.obj kiss_fftr.obj ft8_shim.obj

copy libft8.dll ..\..\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll
```

#### Linux x64 — GCC (WSL2 Debian)

```bash
cd native/ft8_lib

gcc -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -c \
    ft8/constants.c ft8/crc.c ft8/decode.c ft8/encode.c ft8/ldpc.c \
    ft8/message.c ft8/text.c \
    common/monitor.c \
    fft/kiss_fft.c fft/kiss_fftr.c

gcc -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -c \
    ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

gcc -shared -o libft8.so \
    constants.o crc.o decode.o encode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o \
    -lm

cp libft8.so ../../src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so
```

Verify all five symbols are exported before copying:

```bash
nm -D libft8.so | grep "ft8_"
```

#### macOS ARM64 — Clang (GitHub Actions)

No Mac is available locally. Trigger the `workflow_dispatch` rebuild workflow as done
previously for `20260005`. The workflow produces `libft8.dylib` for `arm64-apple-macos11.0`
and commits it to `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`.

---

### 4 — `libft8.version.txt` — update provenance record

File: `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`

Update:

- **Shim version line** — `FT8_SHIM_VERSION = 20260005` → `20260006`; update the parenthetical description to name the SNR constant change.
- **SNR formula line** — update to show `- 26.5` instead of `- 26`.
- **Build date lines** — update each platform's build date to today (2026-06-11) as each binary is rebuilt.

---

### 5 — `Ft8LibInterop.cs` — update expected version constant

File: `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`

Line 36. Change:

```csharp
// Before
/// 20260005 (D-003 diagnostics: add ft8_get_last_noise_floor_db TLS getter; no decode change).
private const int ExpectedShimVersion = 20260005;

// After
/// 20260006 (D-002 fix: SNR bandwidth constant -26.0 → -26.5 dB; bias calibration).
private const int ExpectedShimVersion = 20260006;
```

---

### 6 — `Ft8Decoder.cs` — update class docstring version history

File: `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

The docstring version history (lines 23–26) currently ends at `20260003`. Add the missing entries:

```csharp
/// 20260004 — fix-d001-revised: Option B soft SNR-scaled tile attenuation.
/// 20260005 — diag(D-003): ft8_get_last_noise_floor_db() TLS getter added.
/// 20260006 — fix(D-002): SNR bandwidth constant -26.0 → -26.5 dB (bias calibration).
```

---

### 7 — `openspec/specs/ft8lib-interop/spec.md` — update version constant

Three locations in this file reference `20260005`. Update all three to `20260006`:

1. The `ABI self-test` requirement body — expected constant and its parenthetical description.
2. The `Correct library passes the ABI self-test` scenario — `FT8_SHIM_VERSION = 20260005` → `20260006`.
3. The `Native library binaries are committed` requirement — the `FT8_SHIM_VERSION = 20260005` sentence describing what the binaries were built from.

Also add a new failure scenario for `20260005` (alongside the existing `20260004` and `20260002` scenarios):

```markdown
#### Scenario: Previous library (20260005) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260005`
  (D-003 diagnostics, pre-D002-calibration)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode
  call is attempted, with a message identifying the library path and the version mismatch
```

---

## Checklist

- [ ] 1. `ft8_shim.h` — `FT8_SHIM_VERSION` → `20260006`
- [ ] 2. `ft8_shim.c` — SNR constant `−26.0f` → `−26.5f`; version history comment added
- [ ] 3a. Windows `libft8.dll` rebuilt and copied to `Native/win-x64/`
- [ ] 3b. Linux `libft8.so` rebuilt and copied to `Native/linux-x64/`
- [ ] 3c. macOS `libft8.dylib` rebuilt via GitHub Actions and committed to `Native/osx-arm64/`
- [ ] 4. `libft8.version.txt` updated (version, SNR formula, build dates)
- [ ] 5. `Ft8LibInterop.cs` — `ExpectedShimVersion` → `20260006`
- [ ] 6. `Ft8Decoder.cs` — docstring version history completed (20260004, 20260005, 20260006)
- [ ] 7. `openspec/specs/ft8lib-interop/spec.md` — version constant and new failure scenario
- [ ] `dotnet test OpenWSFZ.slnx -c Release` — all tests pass (ABI self-test will catch a mismatched DLL before any test runs)
- [ ] Notify QA — R&R S1 re-run will follow

## Not required from the developer

Tasks 5.1–5.4 (R&R execution and result recording) are owned by QA.
