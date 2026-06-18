# Developer Handoff — D-001: H6 Directed AP Decode + LLR Probe Redesign

**Date:** 2026-06-18  
**Prepared by:** QA Engineer  
**Branch:** `diag/d001-h6-ap-probe`  
**Shim bump required:** Yes — shim 20260020

---

## 1. Context

**Defect:** D-001 — Co-channel decode gap (GitHub Issue #3). S7 co-channel recovery is 0% for equal-SNR signals (P0/P1/P2) versus WSJT-X at 38–100%.

**Root cause confirmed (shim 20260018):** LDPC convergence failure. Pass 1 finds 15–35 candidates per co-channel cycle; LDPC decodes 0.

**H_LLR hypothesis inconclusive (shim 20260019):** The LLR mean-abs probe returned ≈ 3.84 — indistinguishable from the theoretical constant `√(48/π) ≈ 3.91` that `ftx_normalize_logl` always produces for any non-degenerate distribution. The post-normalisation domain cannot distinguish healthy from degraded LLRs. The correct metric is **pre-normalisation variance**.

**This handoff covers two tasks that must land in the same shim bump:**

- **Task A — H6 directed AP decode** (decode strategy change; priority 1 for D-001)
- **Task B — LLR probe redesign** (add pre-normalisation variance; required to test H_LLR; completes the shim 20260019 investigation)
- **Task C — NaN guard** (minor housekeeping; include in same change)

---

## 2. Branch name

```
diag/d001-h6-ap-probe
```

NEVER commit directly to `main`.

---

## 3. Actions

### Shim version bump (do this first)

In `src/OpenWSFZ.Ft8/Native/ft8_shim.h`, increment:
```c
#define FT8_SHIM_VERSION 20260020
```
Add a history entry block in the same file, following the established pattern for previous shim entries.

In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, update:
```csharp
private const int ExpectedShimVersion = 20260020;
```

---

### Task A — H6 directed AP decode

#### Background

In FT8, the standard-mode 77-bit payload encodes:
- 28 bits for mycall (field 1)
- 28 bits for hiscall (field 2)
- ~21 bits for report/grid/suffix (field 3)

During an active QSO, the decoder knows `mycall` (the local station) and — once a CQ has been answered — `hiscall` (the remote station). Directed AP (a priori) decode uses these known bits as **hard constraints** on the LDPC input: instead of the soft LLR value extracted from the waterfall, the known bit positions receive a large fixed magnitude (±LLR_HARD) that drives belief-propagation to anchor on the correct bit value.

This gives LDPC ~36% of the payload as reliable anchors, which can pull convergence even when the remaining 64% of LLRs are ambiguous (as expected in equal-SNR co-channel interference).

#### What to implement in `ft8_shim.c`

**Step A-1: Expose an AP decode setter**

Add a thread-safe (mutex-protected or caller-serialised — see note below) mechanism to supply `mycall_bits` and `hiscall_bits` to the decode pipeline. The simplest approach: two global `uint8_t` arrays in `ft8_shim.c` for the 28-bit packed form of each callsign, plus a count of valid bits.

Add to `ft8_shim.h`:
```c
/* H6 directed AP decode — supply known callsign bit constraints.
   Call before ft8_decode_all. Pass num_mycall_bits=0 to disable.
   Bits are packed MSB-first; only the low num_bits of each byte matter. */
void ft8_set_ap_bits(
    const uint8_t* mycall_bits,  int num_mycall_bits,
    const uint8_t* hiscall_bits, int num_hiscall_bits);
```

**Step A-2: Apply AP constraints in the LDPC input path**

In `ft8_shim.c`, after `ft8_extract_likelihood` / `ft4_extract_likelihood` populates `log174` (and **before** `ftx_normalize_logl`), apply the AP override:

```c
#define LLR_HARD 40.0f   /* strong prior — large enough to override any waterfall LLR */

for (int i = 0; i < num_ap_bits; i++) {
    int bit_pos = ap_bit_positions[i];   /* pre-computed index into log174 */
    float bit_val = ap_bit_values[i];    /* +1.0f or -1.0f */
    log174[bit_pos] = LLR_HARD * bit_val;
}
```

The bit-to-log174-index mapping follows the FT8 bit layout (mycall occupies bits 0–27 of the 77-bit message, hiscall bits 28–55). Consult `ft8_lib/ft8/message.c` (`pack_callsign`) for the exact encoding — the AP bits must be packed in the same order and sign convention as `ft8_extract_likelihood` produces.

> **Note on threading:** `ft8_decode_all` runs on its own `Task.Run` thread. The AP bits are set from the C# side before the decode call and not changed during the decode. A simple copy-at-decode-start into a local variable is sufficient for safety — no mutex needed if the C# caller serialises `ft8_set_ap_bits` and `ft8_decode_all`.

**Step A-3: Apply only during pass 1; disable for pass 2**

Pass 2 uses spectrogram suppression to find residual candidates after pass 1. AP constraints should only be applied during pass 1 (when the candidate count and LLR quality are highest). Apply the bit override only when `pass == 0` inside `ft8_decode_all`.

**Step A-4: Expose in C# interop**

Add to `IFt8NativeInterop.cs`:
```csharp
/// <summary>Sets known AP bit constraints for the next decode cycle (H6 directed AP decode).</summary>
/// <param name="mycallBits">28-bit packed mycall, or empty to disable.</param>
/// <param name="hiscallBits">28-bit packed hiscall, or empty to disable.</param>
void SetApBits(byte[] mycallBits, byte[] hiscallBits);
```

Add the P/Invoke and adapter delegation following the existing `GetLastLlrStats` pattern.

**Do NOT wire up the C# caller yet.** The `Ft8Decoder` and `QsoAnswererService` integration is deferred to a follow-on change once the native path is verified by the R&R. For this shim, expose the interop seam and confirm it builds.

---

### Task B — LLR probe redesign (pre-normalisation variance)

#### What to change in `native/ft8_lib_build/patched/ft8/decode.c`

Modify `ftx_compute_candidate_llr_mean_abs` to return **two values**: the existing post-normalisation mean|LLR| **and** the pre-normalisation variance of the raw `log174` array.

Change the function signature to:
```c
/* Returns post-normalisation mean|LLR| via return value.
   Sets *out_prenorm_variance to the variance of log174 BEFORE normalisation.
   A small out_prenorm_variance (< threshold TBD) indicates degraded / ambiguous LLRs.
   Returns NaN if variance is zero (degenerate candidate). */
float ftx_compute_candidate_llr_stats(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand,
    float* out_prenorm_variance);
```

Implementation:
```c
float ftx_compute_candidate_llr_stats(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand,
    float* out_prenorm_variance)
{
    float log174[FTX_LDPC_N];
    if (wf->protocol == FTX_PROTOCOL_FT4)
        ft4_extract_likelihood(wf, cand, log174);
    else
        ft8_extract_likelihood(wf, cand, log174);

    /* Compute pre-normalisation variance */
    float sum = 0.0f, sum2 = 0.0f;
    for (int i = 0; i < FTX_LDPC_N; ++i) {
        sum  += log174[i];
        sum2 += log174[i] * log174[i];
    }
    float mean = sum / (float)FTX_LDPC_N;
    float variance = sum2 / (float)FTX_LDPC_N - mean * mean;
    *out_prenorm_variance = variance;

    /* Normalise and compute mean|LLR| */
    ftx_normalize_logl(log174);
    float abs_sum = 0.0f;
    for (int i = 0; i < FTX_LDPC_N; ++i)
        abs_sum += fabsf(log174[i]);
    return abs_sum / (float)FTX_LDPC_N;
}
```

Update the forward declaration in `ft8_shim.h` to match the new signature.

#### What to change in `ft8_shim.h` and `ft8_shim.c`

Add a second TLS array for pre-normalisation variance accumulation:

```c
/* In ft8_shim.c, alongside tls_llr_mean_abs_sum: */
static _Thread_local float tls_llr_prenorm_var_sum[K_MAX_PASSES];
```

Initialise both arrays at the top of `ft8_decode_all` (same pattern as `tls_llr_mean_abs_sum`).

In the failing-candidate accumulation block, call `ftx_compute_candidate_llr_stats` and guard against NaN:
```c
float prenorm_var;
float mean_abs = ftx_compute_candidate_llr_stats(&mon.wf, cand, &prenorm_var);
if (isfinite(mean_abs)) {
    tls_llr_mean_abs_sum[pass]    += mean_abs;
    tls_llr_prenorm_var_sum[pass] += prenorm_var;
}
/* Degenerate (NaN) candidates: skip — do not contaminate the sum */
```

Update `ft8_get_last_llr_stats` in `ft8_shim.h` and `ft8_shim.c` to add a third output array for pre-normalisation variance:
```c
/* Updated signature in ft8_shim.h: */
int ft8_get_last_llr_stats(
    float* out_mean_abs,
    float* out_prenorm_variance,
    int*   out_fail_count,
    int    capacity);
```

Update the C# P/Invoke and `IFt8NativeInterop` accordingly.

Update the `LogDebug` call in `Ft8Decoder.cs` to log both values:
```csharp
_logger?.LogDebug(
    "Iterative subtraction: pass {Pass} LDPC fail stats — " +
    "failCands={FailCount} meanAbsLLR={MeanAbs:F3} prenormVar={PrenormVar:F4}",
    p + 1, llrStats.LlrFailCount[p], llrStats.LlrMeanAbs[p], llrStats.LlrPrenormVariance[p]);
```

---

### Task C — NaN guard (housekeeping)

Already incorporated into the Task B implementation above — the `isfinite(mean_abs)` guard before accumulation prevents NaN contamination of the running sum. No additional changes needed beyond what Task B specifies.

---

### Native binary rebuild

After all C changes:

1. **Windows:** run `native/ft8_lib_build/rebuild_shim.bat`; copy the resulting DLL to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`.
2. **Linux (if available):** run `native/ft8_lib_build/build_linux.sh`; copy to `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`.
3. **macOS:** CI will rebuild and upload the artifact; commit it after CI passes (same workflow as shims 20260018 and 20260019).
4. Commit all three binaries with message `chore(native): rebuild all platforms at shim 20260020`.

---

## 4. Acceptance criteria

| ID | Criterion |
|---|---|
| AC-1 | `FT8_SHIM_VERSION` is 20260020 in `ft8_shim.h` and `ExpectedShimVersion` is 20260020 in `Ft8LibInterop.cs`. |
| AC-2 | `ft8_set_ap_bits` is exported from the shim, declared in `ft8_shim.h`, P/Invoked in `Ft8LibInterop.cs`, exposed on `IFt8NativeInterop`, and delegated in `Ft8NativeInteropAdapter`. |
| AC-3 | `ft8_get_last_llr_stats` now accepts a third `float* out_prenorm_variance` array. The C#, interface, and adapter are updated to match. |
| AC-4 | The `LogDebug` line in `Ft8Decoder.cs` logs `prenormVar` alongside `meanAbsLLR` and `failCands`. |
| AC-5 | NaN guard (`isfinite` check) is present in `ft8_decode_all` before accumulating into `tls_llr_mean_abs_sum` and `tls_llr_prenorm_var_sum`. |
| AC-6 | `ftx_compute_candidate_llr_stats` (renamed from `ftx_compute_candidate_llr_mean_abs`) is in `patched/ft8/decode.c` and its new signature is forward-declared in both `decode.c` and `ft8_shim.h`. |
| AC-7 | AP decode is NOT applied during pass 2 (only pass 0). |
| AC-8 | `SetApBits([], [])` (empty arrays / zero bits) disables AP constraints entirely; the decode path behaves identically to shim 20260019 in this case. |
| AC-9 | All three platform binaries are committed at shim 20260020. CI staleness check passes on all platforms. |
| AC-10 | `dotnet test` passes with **457 tests** (no regression). `AvContainmentTests` must assert `GetLastLlrStatsCalled.Should().BeFalse()` and must also assert `SetApBitsCalled.Should().BeFalse()` (add tracking to `ThrowingNativeInterop` for the new method). |
| AC-11 | `ftx_compute_candidate_llr_stats` does NOT call `bp_decode`. It is a pure measurement function — no decode logic. |

---

## 5. References

- D-001 working hypothesis: MEMORY.md §"Deferred next steps / NS-001 / D-001 working hypothesis"
- Shim 20260018 diagnostic: `qa/rr-study/results/2026-06-17-abd6190/report.md`
- Shim 20260019 diagnostic (H_LLR inconclusive): `qa/rr-study/results/2026-06-18-dde0617/report.md` §5.2
- H6 AP decode concept: WSJT-X source `lib/apfft.f90`; K1JT original paper "Soft-Decision LDPC Decoding in FT8" (reference only — do not reproduce copyrighted code)
- Prior shim handoff (pattern to follow): `dev-tasks/2026-06-17-llr-diagnostic-shim-20260019.md`
- GitHub Issue #3 (open)
