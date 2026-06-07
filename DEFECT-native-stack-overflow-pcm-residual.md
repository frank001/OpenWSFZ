# DEFECT — Native Stack Overflow: `pcm_residual` in `ft8_decode_all`

**Severity:** P1 — Fatal crash, process termination  
**Component:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` + `Native/win-x64/libft8.dll`  
**Status:** ✅ Fixed — all three platform binaries rebuilt and committed; PR #5 merged to `main`  
**Raised by:** QA, 2026-06-07  
**Resolved:** 2026-06-07 (commit `48e35c1` + `f7c9b3a`)  
**Crash signature:** `0xC0000005` in `Ft8LibInterop.NativeDecodeAll`

---

## 1. Observed Behaviour

The application crashes with a fatal access violation after one or more successful decode
cycles. The crash is intermittent but reproducible under real-signal load.

Console output immediately preceding the crash:

```
Block size = 1920
Subblock size = 960
N_FFT = 3840
Fatal error.
0xC0000005
   at OpenWSFZ.Ft8.Interop.Ft8LibInterop.NativeDecodeAll(Single[], Int32, ...)
   at OpenWSFZ.Ft8.Interop.Ft8LibInterop.DecodeAll(Single[])
   at OpenWSFZ.Ft8.Ft8Decoder+<>c__DisplayClass6_0.<DecodeAsync>b__0()
   ...
   at System.Threading.Thread.StartCallback()
```

The three debug lines (`Block size`, `Subblock size`, `N_FFT`) are `LOG_INFO` output from
`monitor_init()` in `common/monitor.c`. They appear **once** before a successful decode and
**twice** per cycle when the PCM-domain SIC path executes (two monitor initialisations per
cycle). The crash output shows only **one** set, meaning the crash fires during the initial
waterfall build or pass-0 decode — before the SIC path reaches its second `monitor_init`.

---

## 2. Root Cause

### 2.1 The stack allocation

`ft8_decode_all` in `ft8_shim.c` contains the following local variable declaration:

```c
/* HEAD version — still present in the DLL binary */
DECLARE_PCM_RESIDUAL();
/* which expands to: */
float pcm_residual[FT8_EXPECTED_SAMPLES];   /* FT8_EXPECTED_SAMPLES = 180 000 */
```

`180 000 × sizeof(float) = 720 000 bytes` (**703 KB**) is placed on the C call stack at
function entry by MSVC with `/O2`.

### 2.2 The stack budget

| Frame | Size |
|---|---|
| CLR internal reserve (GC, exception, overflow detection) | ~128 KB |
| Managed call chain (9 frames: `Thread.StartCallback` → `DecodeAsync` lambda) | ~5–50 KB |
| `ft8_decode_all` (720 KB `pcm_residual` + ~25 KB other locals) | ~745 KB |
| `monitor_process` (`timedata[8192]` + `freqdata[4097]`, both fixed-size VLA replacements) | ~64 KB |
| **Total** | **~942–990 KB** |

The .NET thread pool thread stack is **1 024 KB**. After deducting the CLR reserve, the
usable headroom is approximately **896 KB**. The combined frame reaches **942–990 KB**,
intermittently overflowing the guard page and producing `0xC0000005`.

The crash is *intermittent* because the managed call chain depth varies slightly between
cycles depending on the state of the .NET thread pool scheduler. Most cycles land just
below the limit; occasionally the runtime adds a frame that tips it over.

### 2.3 Why the crash appears after several successful cycles

The overflow only occurs when `monitor_process` is on the stack, which happens:

1. During the **initial waterfall build** (pass 0) — this is the most common crash site.
2. During the **residual waterfall rebuild** (PCM-SIC path, pass 1) — this would show
   two sets of debug prints before crashing; the observed pattern shows one, confirming
   site (1).

Cycles that happen to run with a shallower managed stack survive; the next cycle with a
marginally deeper stack crashes. This explains why the test run collected many WAV files
and decoded hundreds of cycles before failing.

---

## 3. The Fix (authored but not deployed)

The correct fix is present in `src/OpenWSFZ.Ft8/Native/ft8_shim.c` in the current working
tree (staged). It replaces the stack allocation with a heap allocation:

```c
/* FIXED version — in ft8_shim.c, NOT yet compiled into libft8.dll */
float* pcm_residual = (float*)malloc((size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
if (!pcm_residual) {
    tls_hash_table = NULL;
    monitor_free(&mon);
    return -2;
}
/* ... use pcm_residual ... */
free(pcm_residual);   /* step 6, cleanup */
```

With this fix, the `ft8_decode_all` stack frame shrinks from ~745 KB to ~25 KB. Peak stack
usage drops to approximately **253 KB** — well within the 896 KB limit on all three
platforms.

**The fix is correct. The memory management is clean:**
- All three `return` paths are accounted for: `return -1` fires before the `malloc`; `return -2` fires only on `malloc` failure before any use; `return num_decoded` is preceded by `free`.
- No early-exit path between a successful `malloc` and `free(pcm_residual)` exists in the multi-pass loop.
- The managed caller (`Ft8LibInterop.DecodeAll`, line 137) already treats all negative return values as fatal errors, so the new `-2` OOM sentinel requires no managed-side change.

---

## 4. The Problem: DLL Binary Not Rebuilt

**The DLL shipped in `Native/win-x64/libft8.dll` was built at 13:52 on 2026-06-07 as
"fix-D001 rev2".** Inspection of `libft8.version.txt` confirms the build description:

```
Build date: 2026-06-07 (fix-D001 rev2: review findings — phase pre-advancement for
            negative dt_s, buffer-full guard hoisted before PCM subtraction,
            dead pass0_count removed, MaxResults corrected to 540)
```

The heap-allocation fix is **not listed** in this build description. The heap fix was
applied to `ft8_shim.c` *after* the 13:52 rebuild (the file is currently staged but the
DLL binary predates it). The running application loads the 13:52 DLL, which still contains
the 720 KB stack allocation. The crash will persist until the DLL is rebuilt.

---

## 5. Required Actions

### 5.1 Rebuild the DLL immediately

Run `rebuild_shim_new.bat` from the repository root on the Windows x64 build machine:

```batch
cd D:\Projects\claude\OpenWSFZ
native\ft8_lib_build\rebuild_shim_new.bat
```

Verify the output reads `BUILD SUCCESS`. The new `libft8.dll` will be written to
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and `native/ft8_lib_build/libft8.dll`.

### 5.2 Update `libft8.version.txt`

Append a note to the Windows entry in `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`
recording the heap-allocation fix:

```
Build date: 2026-06-07 (fix-D001 rev3: heap-allocated pcm_residual — eliminates
            0xC0000005 stack overflow on .NET thread pool threads; see
            DEFECT-native-stack-overflow-pcm-residual.md)
```

Bump `FT8_SHIM_VERSION` is **not required** — the function signatures and ABI are
unchanged. The managed `ExpectedShimVersion = 20260003` remains correct.

### 5.3 Rebuild Linux and macOS binaries

The same stack overflow affects the Linux and macOS builds. Rebuild `libft8.so` and
`libft8.dylib` using the respective build procedures in `Native/BUILD.md`. The Linux build
can be performed on WSL2; the macOS build requires a CI dispatch (see BUILD.md §macOS).

### 5.4 Disable or demote the `LOG_INFO` debug output in `monitor.c`

The `LOG_INFO` calls in `monitor_init()` (`Block size`, `Subblock size`, `N_FFT`) were
valuable during development but are not appropriate for a release build. They write to
`stderr` on every decode cycle (twice when SIC runs), polluting the application log with
irrelevant native output. This is not a crash risk, but it is unnecessary noise.

**Option A — Change the log level in `monitor.c`:**

```c
/* Change LOG_LEVEL in monitor.c from LOG_INFO to LOG_WARN or higher */
#define LOG_LEVEL LOG_WARN   /* was LOG_INFO */
```

This suppresses `LOG_INFO` and `LOG_DEBUG` messages entirely. The `waterfall_init` debug
line (`LOG_DEBUG`) is already suppressed; only the three `LOG_INFO` lines would change.

**Option B — Remove the three `LOG_INFO` lines from `monitor_init`:**

Lines 77, 78, and 85 in `native/ft8_lib_build/patched/common/monitor.c`:

```c
LOG(LOG_INFO, "Block size = %d\n", me->block_size);     /* REMOVE */
LOG(LOG_INFO, "Subblock size = %d\n", me->subblock_size);  /* REMOVE */
LOG(LOG_INFO, "N_FFT = %d\n", me->nfft);                /* REMOVE */
```

Either option requires a full rebuild of all platform binaries (since `monitor.c` is in
the pre-built `.obj` files, not just `ft8_shim.c`). This makes Option B a more involved
change. Option A is recommended if a quick fix is preferred.

> **Note:** Implementing Option A or B requires recompiling `monitor.obj` — this is a
> full rebuild, not a shim-only rebuild. Follow the complete build procedure in BUILD.md.

---

## 6. Verification

After rebuilding the DLL:

1. Run the full test suite: `dotnet test OpenWSFZ.slnx -c Release` — all 310 tests must pass.
2. Run a live capture session for at least 30 minutes under real-signal conditions. There must be no `0xC0000005` crash.
3. Confirm the debug prints no longer appear in the application log (if the log-level fix was also applied).
4. Confirm that `Ft8LibInterop` loads correctly by verifying the startup log contains no `ABI version mismatch` messages.

---

## 7. Summary

| Item | Detail |
|---|---|
| **Defect type** | Native stack overflow — `float[180000]` on C call stack |
| **Crash code** | `0xC0000005` (Windows STATUS_ACCESS_VIOLATION on stack guard page) |
| **Fix** | Heap allocation (`malloc`/`free`) — correctly authored in `ft8_shim.c` |
| **Why crash persists** | DLL binary not rebuilt after fix was applied to source |
| **Action required** | Run `rebuild_shim_new.bat`; update version.txt; rebuild all platforms |
| **ABI change** | None — no version bump required |
| **Secondary fix** | Demote `monitor_init` LOG_INFO output to reduce log noise |
