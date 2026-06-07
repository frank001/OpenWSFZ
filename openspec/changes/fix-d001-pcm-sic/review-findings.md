# Code Review Findings — `fix/d001-pcm-sic`

Reviewed by QA against the committed diff on 2026-06-07.  
CI is green; 8 findings require attention before merge.  
**Findings 1 and 2 are blocking.** Findings 3–8 are strongly recommended and must not be left as tech debt on `main`.

Native binaries must be rebuilt after any change to `ft8_shim.c`.

---

## Finding 1 — 🔴 BLOCKING — Phase pre-advancement missing in `synthesise_cp_fsk`

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `synthesise_cp_fsk`, lines 372–375  
**Severity:** High — actively degrades SIC effectiveness for a common class of candidate

### What is wrong

When `dt_s < 0` (signal frame starts before the PCM buffer window), `t_start` is correctly clamped to `0` so the loop does not write before the buffer. However, the `phase` accumulator is unconditionally initialised to `0.0` regardless of how many samples were skipped. The true phase of the signal at buffer sample 0 is not 0 — it is whatever the phase accumulator would have reached after advancing through those skipped pre-buffer samples.

```c
// CURRENT — wrong when dt_s < 0
int t_start = (int)roundf(dt_s * (float)sample_rate);
if (t_start < 0) t_start = 0;

double phase = 0.0;   // ← always starts at 0, regardless of skipped samples
```

The ft8_lib candidate search iterates `time_offset` from **−10 to +19**, so negative `dt_s` values are not edge cases — they are routine. For a 1500 Hz carrier at `dt_s = −0.1 s` (1200 pre-buffer samples), the actual signal phase at sample 0 is `2π × 1500 × 0.1 ≈ 942 rad (mod 2π ≈ 2.83 rad)`, meaning the actual waveform value at that sample is approximately `cos(2.83) ≈ −0.95`. The code subtracts `amplitude × cos(0) = amplitude × 1.0`, which **adds** energy rather than removing it. PCM-SIC is counterproductive for every candidate with `time_offset ≤ −1`.

### Required fix

When `dt_s < 0`, pre-advance `phase` through the skipped samples at the first symbol's frequency before entering the main synthesis loop.

```c
int t_start_raw = (int)roundf(dt_s * (float)sample_rate);
int t_start     = (t_start_raw > 0) ? t_start_raw : 0;

double phase = 0.0;

/* If the frame started before the buffer, advance phase past the skipped samples
 * so the replica at buffer sample 0 has the correct phase.
 * Use the first symbol's frequency (tones[0]) for the pre-advancement. */
if (t_start_raw < 0) {
    int skipped = -t_start_raw;
    double f0        = (double)carrier_hz + (double)tones[0] * FT8_TONE_SPACING_HZ;
    double step0     = 2.0 * M_PI * f0 / (double)sample_rate;
    phase = fmod(step0 * (double)skipped, 2.0 * M_PI);
}
```

> **Note:** `fmod` with `2.0 * M_PI` keeps the phase in `[0, 2π)` and avoids double-precision accumulation error over potentially thousands of skipped samples. Include `<math.h>` — already present.

### Tests to add / update

- Add a unit test in `PcmSicTests.cs` or `Ft8LibInteropTests.cs` that synthesises a signal with a known negative DT (e.g. `dt_s = −0.16 s`, `time_offset = −1`), calls `ft8_decode_all`, and confirms the residual PCM RMS is lower after subtraction than before. This is the regression test for this bug.

### Native rebuild required

Yes — `libft8.dll` and `libft8.so` at minimum. Update `libft8.version.txt` build dates.

---

## Finding 2 — 🔴 BLOCKING — `MaxResults = 480` is undersized; comment is factually wrong

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — lines 37–42  
**Severity:** Medium — silent result dropping + misleading maintenance documentation

### What is wrong

The comment and the constant claim pass 2 uses `K_MAX_CANDIDATES = 140`:

```csharp
/// Sized to the three-pass output capacity: K_MAX_CANDIDATES (pass 0, 140)
/// + K_MAX_CANDIDATES_PASS2 (pass 1, 200) + K_MAX_CANDIDATES (pass 2, 140) = 480.
private const int MaxResults = 480;  // 140 + 200 + 140 (three-pass capacity)
```

This is wrong. In `ft8_shim.c`, `k_pass_cfg[2]` is:

```c
{ K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }, /* pass 2: spectrogram */
```

Pass 2 uses `K_MAX_CANDIDATES_PASS2 = 200`, identical to pass 1. The true theoretical maximum is `140 + 200 + 200 = 540`. This is confirmed by `K_MAX_DECODED = 140 + 200 + 200 = 540` in the C file, which sized the dedup table correctly. `MaxResults = 480` is 60 entries short; when passes 0 and 1 together produce more than 280 decodes and pass 2 finds additional signals pushing the total past 480, those results are silently dropped by the `num_decoded < max_results` guard in the C code.

### Required fix

```csharp
/// Sized to the three-pass output capacity: K_MAX_CANDIDATES (pass 0, 140)
/// + K_MAX_CANDIDATES_PASS2 (pass 1, 200) + K_MAX_CANDIDATES_PASS2 (pass 2, 200) = 540.
/// The <c>results[..count]</c> slice in <see cref="DecodeAll"/> returns only the
/// populated portion.
private const int MaxResults = 540;  // 140 + 200 + 200 (three-pass capacity)
```

No native rebuild required — this is purely a managed-side buffer size.

---

## Finding 3 — 🟡 RECOMMENDED — PCM subtraction block runs before the buffer-full guard

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — lines 499–551  
**Severity:** Efficiency — ~5–50 ms wasted work per call when pass 0 fills the result buffer

### What is wrong

The loop structure is:

```c
for (int pass = 0; pass < K_MAX_PASSES; pass++)
{
    if (pass == 1) {              // ← PCM subtraction runs here first
        if (num_decoded > 0) {
            // memcpy 720 KB + replica synthesis + monitor_free/init/process
        }
    }

    if (num_decoded >= max_results) {   // ← buffer-full guard runs second
        ...
        continue;
    }
    // ... candidate search
}
```

If pass 0 fills the result buffer (`num_decoded == max_results`), the code still performs the full 720 KB memcpy, synthesises replicas for all pass-0 signals, tears down and rebuilds the waterfall — then the buffer-full guard fires and discards all of that work before pass 1 ever searches for candidates.

### Required fix

Hoist a `num_decoded >= max_results` early-out for pass 1 *before* the PCM subtraction block:

```c
for (int pass = 0; pass < K_MAX_PASSES; pass++)
{
    /* ── Early-exit: skip everything if result buffer is already full ─── */
    if (num_decoded >= max_results) {
        tls_pass_counts[pass] = 0;
        tls_num_passes        = pass + 1;
        /* Spectrogram suppression must still run before pass 2 */
        if (pass == 1) {
            for (int i = 0; i < n_all_supp; i++)
                suppress_candidate_tiles(&mon.wf, &all_supp_cands[i],
                                         &all_supp_msgs[i], noise_raw);
        }
        continue;
    }

    /* ── PCM subtraction: execute before pass 1 ────────────────────── */
    if (pass == 1) {
        if (num_decoded > 0) {
            // memcpy + synthesise + rebuild waterfall (only reached when useful)
        }
    }
    // ... rest of pass body
}
```

Remove the duplicate `if (pass == 1) { spectrogram suppression }` block that currently sits inside the old buffer-full guard (lines 556–560) — it is superseded by the hoisted version above.

### Native rebuild required

Yes.

---

## Finding 4 — 🔵 CLEANUP — `pass0_count` is dead code

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — lines 465, 661–662, 676

`pass0_count` is declared at line 465, set once at line 662 (`pass0_count = num_decoded`), and suppressed with `(void)pass0_count` at line 676. Nothing reads it. The comment "used implicitly for snapshot only" is incoherent — a snapshot that is never read is dead code.

### Required fix

Delete all three references:

```c
// DELETE: int pass0_count = 0;          (line 465 — declaration)
// DELETE: if (pass == 0)                (lines 661–662 — assignment block)
//             pass0_count = num_decoded;
// DELETE: (void)pass0_count;            (line 676 — suppressor)
```

### Native rebuild required

Yes (but no behaviour change).

---

## Finding 5 — 🔵 CLEANUP — `FT8_NUM_TONES` macro is never used

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — line 87

```c
/* FT8 number of tones in the alphabet */
#define FT8_NUM_TONES        8
```

This macro is not referenced anywhere in the file. Either delete it or use it where the 8-tone alphabet is assumed — for example in the `synthesise_cp_fsk` loop bounds comment, or as a guard `if (tones[sym] >= FT8_NUM_TONES) continue;` in the synthesis loop.

### Required fix

Simplest: delete the definition. If you want the constant to be self-documenting, add a use in `synthesise_cp_fsk`:

```c
/* Validate tone is in [0, FT8_NUM_TONES) — should always be true for a
 * correctly decoded payload, but guard against corrupt data. */
assert(tones[sym] < FT8_NUM_TONES);
```

### Native rebuild required

Yes (no behaviour change if deleted; minor improvement if used as guard).

---

## Finding 6 — 🔵 CLEANUP — Dead `idx >= 0` lower bound in `synthesise_cp_fsk`

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — line 385

```c
if (idx >= 0 && idx < buf_len)   // idx >= 0 is always true — t_start is clamped above
```

Because `t_start` is guaranteed `≥ 0` (clamped on line 373), and `sym ≥ 0`, `n ≥ 0`, `FT8_SAMPLES_PER_SYMBOL > 0`, `idx` is unconditionally non-negative. The `idx >= 0` half is dead.

> **Important:** once Finding 1 is fixed and the raw (pre-clamp) `t_start_raw` drives phase pre-advancement, the **clamped** `t_start` still guarantees `idx ≥ 0`, so the lower bound remains dead after the fix.

### Required fix

```c
if (idx < buf_len)   /* t_start >= 0 guarantees idx >= 0 */
```

### Native rebuild required

Yes (no behaviour change).

---

## Finding 7 — 🔵 TEST COVERAGE — Tests 8.1 / 8.2 use a sequential QSO fixture, not a co-channel fixture

**File:** `tests/OpenWSFZ.Ft8.Tests/PcmSicTests.cs` — lines 35, 69

Both `DecodeAll_MultiSignalFixture_DoesNotMutatePcmBuffer` (8.1) and `GetLastPassCounts_AfterDecodeOnMultiSignalFixture_ThreePassSumEqualsTotal` (8.2) describe themselves as "multi-signal fixture" tests but load `synth-qso-01.wav`, which contains a single sequential QSO chain (three messages decoded from three successive symbols, no simultaneity). The PCM subtraction block fires — there is at least one decode — so the immutability and pass-count-sum assertions are valid. However, **a regression that disables PCM subtraction entirely** (e.g. the `if (num_decoded > 0)` guard inverted) would still pass both tests, because the fixture never exercises SIC in the co-channel scenario it was built for.

### Required fix — Option A (minimal, low effort)

Re-label the fixture description to remove the "multi-signal" claim; add a comment explaining what the test *does* and *does not* cover:

```csharp
// Arrange — load a single-QSO synthetic fixture.
// This verifies the immutability invariant whenever at least one signal is decoded
// and the PCM subtraction block is triggered.  It does NOT exercise co-channel SIC.
float[] pcm = LoadFixtureWav("synth-qso-01.wav");
```

### Required fix — Option B (preferred, complete coverage)

Create a co-channel synthetic fixture (two FT8 signals at the same frequency and overlapping time, one stronger and one weaker) and add a test that asserts the weaker signal is decoded in pass 1 or 2 but not pass 0. This directly validates D-001's fix. The `qa/rr-study/synth/` synthesiser can produce this; it is a Captain-decision whether to do this now or track it as a follow-on task.

---

## Finding 8 — 🔵 DOCUMENTATION — `Task.Run` comment overstates the TLS thread-safety guarantee

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — lines 103–108

```csharp
(native, passCounts) = await Task.Run(() =>
{
    var r = Ft8LibInterop.DecodeAll(pcm);
    var p = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);
    return (r, p);
}, ct);
```

The comment above this block says "both calls on the SAME thread." This holds because there is no `await` between the two calls inside the synchronous lambda body — they run sequentially on the same thread-pool thread. However, the comment uses the wrong invariant. If the lambda is ever made `async` (e.g. to add a `ct.ThrowIfCancellationRequested()` mid-body), `GetLastPassCounts` would move to a continuation that may execute on a different thread-pool thread, reading the wrong TLS slot and silently returning stale or zero counts.

### Required fix

Tighten the comment to state the actual invariant:

```csharp
// Both calls must be on the same thread — no await between them — because
// ft8_get_last_pass_counts reads from TLS written by ft8_decode_all.
// IMPORTANT: do not make this lambda async or split these two calls across
// separate Task.Run invocations; doing so would break the TLS guarantee.
(native, passCounts) = await Task.Run(() =>
{
    var r = Ft8LibInterop.DecodeAll(pcm);
    var p = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);
    return (r, p);
}, ct);
```

---

## Rebuild checklist

Once all changes are made:

```
[ ] ft8_shim.c changes committed (Findings 1, 3, 4, 5, 6)
[ ] Rebuild libft8.dll (Windows x64) — update libft8.version.txt build date
[ ] Rebuild libft8.so (Linux x64) — update libft8.version.txt build date
[ ] libft8.dylib will be rebuilt by CI (macOS ARM64)
[ ] Ft8LibInterop.cs MaxResults updated to 540 (Finding 2)
[ ] Ft8Decoder.cs comment updated (Finding 8)
[ ] PcmSicTests.cs fixture description updated (Finding 7)
[ ] dotnet test OpenWSFZ.slnx -c Release — all tests pass, 0 failures
[ ] New regression test for Finding 1 added and passing
```

No ABI change is required — `FT8_SHIM_VERSION` remains `20260003`. The native function signatures are unchanged.
