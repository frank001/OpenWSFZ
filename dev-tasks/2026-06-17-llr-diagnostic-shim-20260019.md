# Developer Handoff — LLR Diagnostic Instrumentation (shim 20260019)

**Date:** 2026-06-17  
**Branch:** `diag/d001-llr-mean-abs`  
**Shim version:** 20260019  
**Relates to:** D-001 (co-channel decode gap), GitHub Issue #3

---

## 1. Context

The shim-20260018 diagnostic run (`abd6190`, 2026-06-17) confirmed that in every
co-channel failure cycle, pass 1 delivers **15–28 candidates** to the LDPC decoder
and the LDPC decoder successfully decodes **zero** of them. Candidate generation is
not the bottleneck — LDPC convergence is.

The working hypothesis (from `qa/rr-study/results/2026-06-17-abd6190/report.md §5`)
is that **equal-SNR mutual interference drives all 174 LDPC input LLR values toward
zero**, making every bit maximally ambiguous and preventing belief-propagation from
converging regardless of iteration budget.

This change adds a minimal read-only diagnostic probe to measure **mean abs(LLR)**
per failing candidate per pass, exposed via the established TLS-getter pattern.
The managed layer logs the value per cycle. A single diagnostic R&R run then either
confirms or refutes the near-zero LLR hypothesis with a concrete number.

This is **purely diagnostic** — no change to decode logic, candidate search, pass
configuration, or LDPC parameters.

---

## 2. Branch name

```
diag/d001-llr-mean-abs
```

Branch from current `main` HEAD (`d73858b`). Do **not** commit directly to `main`.

---

## 3. Actions

Work through the tasks in order. Each is self-contained; do not combine steps.

### Task 1 — Add `ftx_compute_candidate_llr_mean_abs` to `patched/ft8/decode.c`

**File:** `native/ft8_lib_build/patched/ft8/decode.c`

Add the following function **after** the closing brace of `ftx_decode_candidate`
(currently around line 388), before the `max2` / `max4` static helpers:

```c
/*
 * ftx_compute_candidate_llr_mean_abs — diagnostic probe for D-001.
 *
 * Replicates the first two steps of ftx_decode_candidate (likelihood
 * extraction + variance-normalisation) and returns the mean absolute
 * LLR across all FTX_LDPC_N (174) elements.
 *
 * A high value (> ~1.5) indicates healthy soft-decision input to LDPC.
 * A near-zero value (< ~0.5) indicates that the waterfall provides no
 * useful bit confidence — the LDPC convergence failure hypothesis
 * for D-001 co-channel scenarios.
 *
 * Does NOT call bp_decode.  Read-only with respect to the waterfall.
 * Safe to call for any candidate, including those that subsequently
 * fail ftx_decode_candidate.
 */
float ftx_compute_candidate_llr_mean_abs(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand)
{
    float log174[FTX_LDPC_N];

    if (wf->protocol == FTX_PROTOCOL_FT4)
        ft4_extract_likelihood(wf, cand, log174);
    else
        ft8_extract_likelihood(wf, cand, log174);

    ftx_normalize_logl(log174);

    float sum = 0.0f;
    for (int i = 0; i < FTX_LDPC_N; ++i)
        sum += fabsf(log174[i]);

    return sum / (float)FTX_LDPC_N;
}
```

Also add the forward declaration near the top of the file (alongside the existing
static forward declarations, around line 32–50):

```c
/* Non-static diagnostic probe — called from ft8_shim.c */
float ftx_compute_candidate_llr_mean_abs(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand);
```

Note: `fabsf` requires `<math.h>`, which is already `#include`d via `<math.h>` at
line 6. `FTX_LDPC_N` (174) is defined in `ldpc.h`, already included at line 4.

**Verification:** `ftx_compute_candidate_llr_mean_abs` must be non-static so it is
visible to `ft8_shim.c` at link time. Confirm no `static` keyword is present.

---

### Task 2 — Add TLS diagnostic state to `ft8_shim.c`

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

#### 2a. Add the declaration for the new decode.c function

Near the top of `ft8_shim.c`, after the `#include` block (around line 255), add:

```c
/* Forward declaration — defined in patched/ft8/decode.c */
float ftx_compute_candidate_llr_mean_abs(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand);
```

#### 2b. Add TLS variables

In the TLS block (around line 344–348, alongside `tls_pass_counts` etc.), add:

```c
static _Thread_local float tls_llr_mean_abs_sum[K_MAX_PASSES];
static _Thread_local int   tls_llr_fail_count[K_MAX_PASSES];
```

#### 2c. Initialise TLS variables at the start of `ft8_decode_all`

In the initialisation block (around line 877, alongside the existing zero-fills for
`tls_pass_counts` and `tls_candidate_counts`), add:

```c
for (int i = 0; i < K_MAX_PASSES; i++) tls_llr_mean_abs_sum[i] = 0.0f;
for (int i = 0; i < K_MAX_PASSES; i++) tls_llr_fail_count[i]   = 0;
```

#### 2d. Populate TLS in the failing-candidate branch

In the decode loop (around line 926), `ftx_decode_candidate` returns false when
LDPC fails. The current code is:

```c
if (!ftx_decode_candidate(&mon.wf, cand, pass_ldpc, &msg, &status))
    continue;
```

Replace with:

```c
if (!ftx_decode_candidate(&mon.wf, cand, pass_ldpc, &msg, &status))
{
    /* D-001 diagnostic: accumulate mean|LLR| for failing candidates */
    tls_llr_mean_abs_sum[pass] +=
        ftx_compute_candidate_llr_mean_abs(&mon.wf, cand);
    tls_llr_fail_count[pass]++;
    continue;
}
```

#### 2e. Add the getter function

After `ft8_get_last_candidate_counts` (around line 813), add:

```c
/* ── Per-pass mean abs(LLR) query for failing candidates ────────────── */
/*
 * ft8_get_last_llr_stats — return per-pass mean abs(LLR) across all
 * LDPC-failing candidates from the most recent ft8_decode_all call on
 * this thread.
 *
 * out_mean_abs[i] receives the mean abs(LLR) for pass i, averaged across
 * all candidates that failed ftx_decode_candidate in that pass.
 * Returns 0.0f for passes where no candidates failed (i.e. all decoded
 * successfully, or no candidates were found).
 *
 * out_fail_count[i] receives the count of LDPC-failing candidates in
 * pass i.  This allows the caller to distinguish "no failures" (count=0,
 * mean=0) from "high mean — decode succeeded on all" (count=0, mean=0).
 *
 * Parameters and threading contract identical to ft8_get_last_pass_counts.
 */
int ft8_get_last_llr_stats(float* out_mean_abs, int* out_fail_count, int capacity)
{
    int n = (tls_num_passes < capacity) ? tls_num_passes : capacity;
    for (int i = 0; i < n; i++)
    {
        if (tls_llr_fail_count[i] > 0)
            out_mean_abs[i] = tls_llr_mean_abs_sum[i] / (float)tls_llr_fail_count[i];
        else
            out_mean_abs[i] = 0.0f;
        out_fail_count[i] = tls_llr_fail_count[i];
    }
    return n;
}
```

#### 2f. Bump `FT8_SHIM_VERSION`

Change the existing `#define FT8_SHIM_VERSION 20260018` to `20260019`.

Add the history entry in the block comment at the top of `ft8_shim.c`, after the
`diag-d001-candidate-counts` entry (around line 202):

```
 * diag-d001-llr-mean-abs (FT8_SHIM_VERSION 20260019):
 *
 *   Adds ft8_get_last_llr_stats() — a TLS getter exposing, per pass, the
 *   mean absolute LLR across all LDPC-failing candidates from the most
 *   recent ft8_decode_all call.  For each candidate where
 *   ftx_decode_candidate() returns false, ftx_compute_candidate_llr_mean_abs()
 *   is called (defined in patched/ft8/decode.c); it replicates the likelihood-
 *   extraction + variance-normalisation steps and returns mean(|log174[i]|)
 *   over all 174 elements without calling bp_decode.  Two new TLS arrays
 *   (tls_llr_mean_abs_sum, tls_llr_fail_count) accumulate per-pass totals;
 *   the getter computes the per-pass mean and returns alongside the fail count.
 *   Diagnostic goal: confirm the near-zero LLR hypothesis for D-001 co-channel
 *   failure cycles (expected: mean|LLR| < 0.5 for P0/P1/P2 failures vs > 1.5
 *   for successful co-channel captures).  No change to decode logic, candidate
 *   search, pass configuration, or struct layout.
 */
```

---

### Task 3 — Update `ft8_shim.h`

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.h`

#### 3a. Bump the version constant and add history

Change `#define FT8_SHIM_VERSION 20260018` to `20260019`.

Add the 20260019 history bullet after the 20260018 entry (around line 163):

```
 *   20260019 — diag-d001-llr-mean-abs: add ft8_get_last_llr_stats() exposing
 *              per-pass mean abs(LLR) across LDPC-failing candidates.
 *              ftx_compute_candidate_llr_mean_abs() added to decode.c (non-static)
 *              computes likelihood + normalisation without calling bp_decode.
 *              No change to existing entry points, struct layout, or return codes.
```

#### 3b. Declare the new exported function

After the declaration of `ft8_get_last_candidate_counts` (around line 257), add:

```c
/*
 * ft8_get_last_llr_stats — return per-pass mean abs(LLR) statistics from
 * the most recent ft8_decode_all call on this thread.
 *
 * out_mean_abs[i]   — mean abs(LLR) across all LDPC-failing candidates in pass i.
 *                     0.0f if no candidates failed in that pass.
 * out_fail_count[i] — count of LDPC-failing candidates in pass i.
 * capacity          — size of both output arrays; ≥ K_MAX_PASSES for full data.
 *
 * Returns: number of passes actually executed (≤ capacity).
 * Threading contract: identical to ft8_get_last_pass_counts.
 */
int ft8_get_last_llr_stats(float* out_mean_abs, int* out_fail_count, int capacity);
```

---

### Task 4 — Update the build scripts

#### 4a. Windows — `native/ft8_lib_build/rebuild_shim.bat`

Add `/EXPORT:ft8_get_last_llr_stats` to the `link` command, alongside the existing
`/EXPORT:ft8_get_last_candidate_counts` line.

The decode.c object file (`native/ft8_lib_build/obj/decode.obj`) must be
**recompiled** from the patched source, since `ftx_compute_candidate_llr_mean_abs`
is a new non-static function. Verify the batch file compiles `patched/ft8/decode.c`
into `obj/decode.obj`. If the batch file currently uses a pre-built `decode.obj`
without a compile step for it, add one:

```bat
echo === Compiling patched decode.c ===
cl ^
  /I "C:\Temp\ft8_lib_headers" ^
  /I "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\decode.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\patched\ft8\decode.c"
```

#### 4b. Linux — `native/ft8_lib_build/build_linux.sh`

Add `-Wl,--export-dynamic` is already present; ensure `ft8_get_last_llr_stats` is
included in the link step. If the script uses explicit `-Wl,-e` or `--dynamic-list`
exports, add `ft8_get_last_llr_stats`. If it relies on all non-static symbols being
visible (the usual shared-library default on Linux), no change is needed — the new
non-static function in decode.c will be exported automatically.

Also verify that `patched/ft8/decode.c` is compiled as part of the Linux build.
If it currently uses the pre-built `linux_obj/decode.o`, add a compile step for
the patched version.

---

### Task 5 — Update `Ft8LibInterop.cs` (managed layer)

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`

#### 5a. Update `ExpectedShimVersion`

Change `private const int ExpectedShimVersion = 20260018;` to `20260019`.

Update the doc-comment history entry for 20260018, and add the 20260019 entry:

```csharp
/// 20260019 (diag-d001-llr-mean-abs): Adds <c>ft8_get_last_llr_stats</c> —
///   per-pass mean abs(LLR) across LDPC-failing candidates. Counterpart
///   function <c>ftx_compute_candidate_llr_mean_abs</c> added to decode.c
///   (non-static); replicates likelihood extraction + normalisation without
///   calling bp_decode.  No change to existing entry points or struct layout.
```

#### 5b. Add P/Invoke declaration

After the P/Invoke for `NativeGetLastCandidateCounts` (around line 219), add:

```csharp
/// <summary>
/// Return per-pass mean abs(LLR) statistics for LDPC-failing candidates
/// from the most recent <see cref="NativeDecodeAll"/> call on this thread.
/// </summary>
[DllImport("libft8.dll", EntryPoint = "ft8_get_last_llr_stats",
           CallingConvention = CallingConvention.Cdecl)]
private static extern int NativeGetLastLlrStats(
    [Out] float[] outMeanAbs,
    [Out] int[]   outFailCount,
    int           capacity);
```

#### 5c. Add public wrapper method

After `GetLastCandidateCounts` (around line 352), add:

```csharp
/// <summary>
/// Return per-pass mean abs(LLR) statistics from the most recent
/// <see cref="DecodeAll"/> call on this thread.
/// <para>
/// <c>meanAbs[i]</c> is the mean absolute LLR across all LDPC-failing
/// candidates in pass <c>i</c>, after variance-normalisation.
/// A value below ~0.5 indicates near-zero bit confidence (the D-001
/// co-channel failure hypothesis); above ~1.5 indicates healthy soft-
/// decision input.  Returns 0.0f for passes with no failing candidates.
/// </para>
/// <para>
/// <c>failCount[i]</c> is the number of LDPC-failing candidates in pass
/// <c>i</c>; allows distinguishing zero-failure from zero-candidate cases.
/// </para>
/// Must be called on the same thread that called <see cref="DecodeAll"/>.
/// </summary>
public static (float[] MeanAbs, int[] FailCount) GetLastLlrStats(int maxPasses)
{
    EnsureInitialized();

    var meanAbs   = new float[maxPasses];
    var failCount = new int[maxPasses];
    int numPasses = NativeGetLastLlrStats(meanAbs, failCount, maxPasses);

    if (numPasses <= 0)
        return ([], []);

    return (meanAbs[..numPasses], failCount[..numPasses]);
}
```

---

### Task 5d — Add `GetLastLlrStats` to `IFt8NativeInterop.cs`

**File:** `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs`

After the `GetLastCandidateCounts` declaration, add:

```csharp
/// <summary>
/// Return per-pass mean abs(LLR) statistics for LDPC-failing candidates
/// from the most recent <see cref="DecodeAll"/> call on this thread.
/// MUST be called on the same thread as <see cref="DecodeAll"/>.
/// </summary>
(float[] MeanAbs, int[] FailCount) GetLastLlrStats(int maxPasses);
```

---

### Task 5e — Implement in `Ft8NativeInteropAdapter.cs`

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8NativeInteropAdapter.cs`

After the `GetLastCandidateCounts` implementation, add:

```csharp
public (float[] MeanAbs, int[] FailCount) GetLastLlrStats(int maxPasses)
    => Ft8LibInterop.GetLastLlrStats(maxPasses);
```

---

### Task 6 — Wire logging in `Ft8Decoder.cs`

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

The LLR stats must be retrieved on the same thread as `DecodeAll` — i.e. inside
the `Task.Run` lambda. Do **not** call `GetLastLlrStats` after the `await`.

**6a.** Expand the `Task.Run` return tuple to include LLR stats. The lambda
currently returns `(r, p, c, n)`; change it to `(r, p, c, n, l)`:

```csharp
(float[] LlrMeanAbs, int[] LlrFailCount) llrStats;

(native, passCounts, candidateCounts, noiseFloorDb, llrStats) = await Task.Run(() =>
{
    var r = _interop.DecodeAll(normalisedPcm);
    var p = _interop.GetLastPassCounts(_interop.MaxDecodePasses);
    var c = _interop.GetLastCandidateCounts(_interop.MaxDecodePasses);
    var n = _interop.GetLastNoiseFloorDb();
    var l = _interop.GetLastLlrStats(_interop.MaxDecodePasses);
    return (r, p, c, n, l);
}, ct);
```

**6b.** After the per-pass candidate/decode log (the existing `for (int p = 0; ...)` loop
around line 227), add:

```csharp
for (int p = 0; p < llrStats.LlrMeanAbs.Length; p++)
{
    _logger?.LogDebug(
        "Iterative subtraction: pass {Pass} LDPC fail stats — " +
        "failCands={FailCount} meanAbsLLR={MeanAbs:F3}",
        p + 1, llrStats.LlrFailCount[p], llrStats.LlrMeanAbs[p]);
}
```

Log at `LogDebug` — not `LogInformation` — so it is only captured when file
logging is enabled at Debug level (per Lesson 8: pre-configure
`Logging.FileEnabled = true` and `Logging.FileLogLevel = "Debug"` before any
diagnostic run).

---

### Task 7 — Rebuild all three platform binaries

After all source changes:

1. **Windows:** run `native/ft8_lib_build/rebuild_shim.bat`  
   — recompile `patched/ft8/decode.c` → `obj/decode.obj` first  
   — recompile `src/OpenWSFZ.Ft8/Native/ft8_shim.c` → `obj/ft8_shim.obj`  
   — relink `libft8.dll`, copy to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`

2. **Linux:** run `native/ft8_lib_build/build_linux.sh`  
   — ensure patched `decode.c` is compiled in this build  
   — copy output to `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`

3. **macOS:** rebuild via CI (or cross-compile if available)  
   — copy output to `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`

The ABI staleness gate (`check_native_version.py`) will fail hard if any committed
binary does not return `ft8_lib_version_check() == 20260019`. All three binaries
must be committed on the branch.

---

### Task 8 — Run the test suite; verify no regressions

```
dotnet build OpenWSFZ.slnx -c Release
dotnet test  OpenWSFZ.slnx -c Release
```

All 457 existing tests must pass (FR-009 in `OpenWSFZ.Web.Tests` is a pre-existing
CI-only race; it may also fail locally — this is expected and acceptable).

---

## 4. Acceptance criteria

The QA engineer will check the following before approving the merge:

| # | Criterion |
|---|---|
| AC-1 | `FT8_SHIM_VERSION` is `20260019` in both `ft8_shim.h` and `ft8_shim.c` |
| AC-2 | `ExpectedShimVersion` in `Ft8LibInterop.cs` is `20260019` |
| AC-3 | `ftx_compute_candidate_llr_mean_abs` in `decode.c` is **non-static** and forward-declared correctly |
| AC-4 | TLS arrays `tls_llr_mean_abs_sum` and `tls_llr_fail_count` are initialised to zero at the start of every `ft8_decode_all` call |
| AC-5 | `ft8_get_last_llr_stats` is exported in both `rebuild_shim.bat` and `build_linux.sh` |
| AC-6 | All three platform binaries (`win-x64`, `linux-x64`, `osx-arm64`) rebuilt and committed; `ft8_lib_version_check()` returns `20260019` on each |
| AC-7 | `dotnet test` passes: 457 tests, 0 failures (FR-009 exempted) |
| AC-8 | `GetLastLlrStats` declared in `IFt8NativeInterop.cs`, implemented in `Ft8NativeInteropAdapter.cs`, called via `_interop` **inside** the `Task.Run` lambda (same thread as `DecodeAll`); log output appears at `LogDebug` with `failCands` and `meanAbsLLR` fields |
| AC-9 | No change to `FT8Result` struct layout (still 48 bytes); no change to `ft8_decode_all` return codes or decode logic |
| AC-10 | `ftx_compute_candidate_llr_mean_abs` does **not** call `bp_decode` — confirmed by code review |

---

## 5. References

- D-001 working hypothesis: `qa/rr-study/results/2026-06-17-abd6190/report.md §5`
- Diagnostic log confirming 15–28 candidates / 0 decodes: `logs/openswfz-20260617T161933Z.log`
- `ftx_decode_candidate` source: `native/ft8_lib_build/patched/ft8/decode.c` lines 327–388
- Established TLS-getter pattern: `ft8_get_last_candidate_counts` in `ft8_shim.c` lines 807–813
- HK-000 (developer handoff procedure): `memory/MEMORY.md`
- Lesson 8 (pre-configure file logging before diagnostic runs): `memory/MEMORY.md`
- GitHub Issue #3 (D-001, open)
