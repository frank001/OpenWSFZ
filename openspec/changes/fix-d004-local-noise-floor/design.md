## Context

The SNR formula in `ft8_shim.c` is:

```c
float snr = signal_db - noise_floor_db - 26.5f;
```

where `noise_floor_db` is the histogram median across the **entire** 200–3000 Hz waterfall (all time blocks × all time/freq sub-samples). `signal_db` is the mean of per-symbol waterfall magnitudes at the decoded tone bins.

Live endurance data (2026-06-13, 1h42m) demonstrates that `noise_floor_db` stays essentially constant at −66.7 dB regardless of signal frequency, while back-computed `signal_db` drops from −39.7 dB at 800–1000 Hz to −67.5 dB at 2800–3000 Hz — below the noise floor itself. The audio chain (transceiver SSB output + USB Audio CODEC) has significant frequency rolloff that attenuates signals at both band edges. Because the global noise floor is anchored to mid-band levels and does not follow this rolloff, the SNR is under-reported by up to −22 dB at high frequencies. WSJT-X compensates automatically via a local noise reference; OpenWSFZ does not.

D-003 (2.1% incidence, SNR ≤ −30 dB) is confirmed to be the extreme tail of D-004 (frequency-dependent SNR bias) affecting weak-to-moderate signals at 2600–3000 Hz. There is no separate D-003 mechanism.

---

## Goals / Non-Goals

**Goals:**

- Replace the global `noise_floor_db` used in the per-signal SNR formula with a local noise floor sampled from waterfall bins adjacent to the signal's frequency.
- Make the SNR formula invariant to audio chain frequency response.
- Resolve D-003 and D-004 with a single principled fix.
- Retain the global noise floor for the per-cycle diagnostic log line (it remains useful for band health monitoring).

**Non-Goals:**

- Change `FT8Result` struct layout (remains 48 bytes).
- Change decode logic, candidate detection, or spectrogram suppression.
- Alter `signal_db` computation (it is correct; only the denominator is wrong).
- Fix D-001 (co-channel decode gap) — unrelated.
- Recalibrate the −26.5 dB bandwidth constant within this change; re-validation (S1 R&R run) happens after the fix is deployed.

---

## Decisions

### Decision 1: Local sideband window rather than a per-bin lookup table

**Chosen**: Sample noise from waterfall bins in a sideband window on each side of the signal's 8-tone span. Take the histogram median of those samples across all time blocks and all time/freq sub-samples.

**Alternatives considered**:

- *Empirical correction table keyed by freq_offset*: fragile — breaks when the audio device, gain, or band condition changes. Not device-agnostic.
- *Percentile of adjacent bins in signal's own time blocks only*: fewer samples → noisier estimate. Full-waterfall time integration is more stable.
- *WSJT-X-style split into fast and slow noise tracks*: significant complexity; overkill for this application.

---

### Decision 2: Window width of K_LOCAL_NOISE_WINDOW = 32 bins (200 Hz each side)

**Chosen**: 32 bins on each side of the 8-tone signal span:
- Left sideband: `[max(0, freq_offset − 32), freq_offset)` 
- Right sideband: `[freq_offset + 8, min(num_bins, freq_offset + 40))`

With 187 blocks × 4 sub-samples, each sideband bin contributes 748 samples. Total available at mid-band: 64 × 748 = 47 872 samples. Even at extreme edges where one sideband is fully clipped, the opposite provides 32 × 748 = 23 936 samples — more than sufficient for a stable median.

**Why not wider**: A wider window (e.g., 100 bins = 625 Hz) could capture adjacent strong stations and inflate the noise estimate. 200 Hz is narrow enough to track local rolloff without significant contamination from neighbouring transmissions.

**Why not narrower**: At 16 bins (100 Hz), clipping at band edges could leave only 8–10 bins — potentially too few samples for a reliable estimate near one edge.

---

### Decision 3: Histogram median (consistent with global estimator)

**Chosen**: Same histogram-median approach as `compute_noise_floor`. Avoids a different statistical model that would be harder to reason about in comparison to existing diagnostics.

**Alternative**: 25th or 30th percentile to bias toward quieter bins and reduce contamination from adjacent stations. Considered, but the median is simpler and re-validation (S1) will catch any bias introduced. Can be adjusted if S1 shows a systematic shift.

---

### Decision 4: Fallback to global noise floor when window is empty

**Chosen**: If the combined sideband window yields zero samples (only theoretically possible if `num_bins = 8` — far below any real configuration), fall back to the TLS-stored `tls_last_noise_floor_db`. This is a safety guard, not an expected code path.

---

### Decision 5: Global noise floor retained for diagnostic logging, not for SNR

**Chosen**: `compute_noise_floor` is still called; its result is stored in `tls_last_noise_floor_db` and logged per cycle by the managed layer. It is no longer used in the per-signal SNR formula. The log line `noise_floor=X dB` continues to work unchanged.

**Rationale**: The per-cycle noise floor log has proven useful for D-003 diagnosis and band health monitoring. Removing it would reduce observability without benefit.

---

### Decision 6: FT8_SHIM_VERSION advances to 20260012

Version 20260011 is reserved (was used for the H5 diagnostic, then reverted). The new version is 20260012. `ExpectedShimVersion` in `Ft8LibInterop.cs` and the version constant in `ft8lib-interop/spec.md` must be updated to match. The struct layout is unchanged; this version bump tracks the algorithm change, not an ABI break.

---

### Decision 7: Recompile all three platform binaries

The fix is entirely in `ft8_shim.c`. All three platform binaries (win-x64, linux-x64, osx-arm64) must be rebuilt and committed. The G6 CI gate validates all three.

---

## New Function: `compute_local_noise_floor_db`

```c
/* ── Local noise floor for per-signal SNR computation ────────────────────── */
/*
 * K_LOCAL_NOISE_WINDOW — number of waterfall bins sampled on each side of the
 * decoded signal's 8-tone span.  With freq_osr=2 and 6.25 Hz/bin, 32 bins =
 * 200 Hz of audio bandwidth per sideband.
 */
#define K_LOCAL_NOISE_WINDOW 32

/*
 * compute_local_noise_floor_db — histogram-median noise floor estimated from
 * waterfall bins adjacent to the decoded signal's frequency.
 *
 * Samples bins in [max(0, freq_offset − K_LOCAL_NOISE_WINDOW), freq_offset)
 * and [freq_offset + 8, min(num_bins, freq_offset + 8 + K_LOCAL_NOISE_WINDOW))
 * across ALL time blocks and ALL time/freq sub-samples.
 *
 * Falls back to tls_last_noise_floor_db if no bins are available.
 *
 * This makes the SNR formula invariant to audio-chain frequency response:
 * both signal and noise are measured in the same frequency region.
 */
static float compute_local_noise_floor_db(
    const ftx_waterfall_t* wf,
    int                    freq_offset)
{
    uint32_t hist[256];
    memset(hist, 0, sizeof(hist));
    int total = 0;

    int lo_start = freq_offset - K_LOCAL_NOISE_WINDOW;
    if (lo_start < 0) lo_start = 0;
    int lo_end   = freq_offset;                        /* exclusive; clipped signal tones */

    int hi_start = freq_offset + 8;                   /* skip 8-tone signal span          */
    int hi_end   = freq_offset + 8 + K_LOCAL_NOISE_WINDOW;
    if (hi_end > wf->num_bins) hi_end = wf->num_bins;

    int pt = wf->freq_osr * wf->num_bins;             /* per-time_sub stride in a block   */

    for (int b = 0; b < wf->num_blocks; b++) {
        const WF_ELEM_T* block = wf->mag + b * wf->block_stride;
        for (int ts = 0; ts < wf->time_osr; ts++) {
            for (int fs = 0; fs < wf->freq_osr; fs++) {
                const WF_ELEM_T* row = block + ts * pt + fs * wf->num_bins;
                for (int f = lo_start; f < lo_end; f++) { hist[row[f]]++; total++; }
                for (int f = hi_start; f < hi_end; f++) { hist[row[f]]++; total++; }
            }
        }
    }

    if (total == 0) return tls_last_noise_floor_db;   /* safety fallback — never expected  */

    uint32_t cum = 0; int med = 0;
    for (int v = 0; v < 256; v++) {
        cum += hist[v];
        if (cum * 2 >= (uint32_t)total) { med = v; break; }
    }
    return (float)med * 0.5f - 120.0f;
}
```

**Call site change** — in `ft8_decode_all`, replace:

```c
// BEFORE
float snr = signal_db - noise_floor_db - 26.5f;
```

with:

```c
// AFTER
float local_noise_db = compute_local_noise_floor_db(&mon.wf, (int)cand->freq_offset);
float snr = signal_db - local_noise_db - 26.5f;
```

The variable `noise_floor_db` (global, computed once per cycle) is unchanged and is retained for `tls_last_noise_floor_db` and the diagnostic log.

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| The −26.5 dB constant was calibrated against the global noise floor at ~1000 Hz. With local noise, the effective relationship may shift slightly. | S1 R&R run is a required post-fix task. If S1 bias shifts outside ±2.0 dB, adjust the constant. |
| Adjacent FT8 stations within the ±200 Hz sideband window could elevate the local noise estimate, causing SNR under-report for densely-packed signals. | 32 bins ≈ 200 Hz is narrower than a typical inter-station gap (FT8 stations cluster on integer-Hz boundaries; the decoder separates them). Effect is expected to be small. |
| The local noise estimate is computed per decoded signal — up to 340 calls per cycle. Per call: 64 bins × 187 blocks × 4 sub-samples = ~47 872 byte reads. Total: ~16M reads/cycle worst case. | The waterfall is ~335 KB; fits in L2 cache. Benchmark on the dev machine (current mean elapsed: 46 ms); confirm no regression past 100 ms. |
| D-003 issue record (#11) attributes the defect to `signal_db` row-index lookup — an incorrect diagnosis. | Close #11 as duplicate of #12 with a note explaining the corrected root cause. |

---

## Migration Plan

1. Implement `compute_local_noise_floor_db` in `ft8_shim.c`; replace call site.
2. Bump `FT8_SHIM_VERSION` to 20260012 in `ft8_shim.h` and `ft8_shim.c` comment block.
3. Update `Ft8LibInterop.cs` `ExpectedShimVersion` constant and its doc comment.
4. Rebuild all three platform binaries via the existing native build process (see `src/OpenWSFZ.Ft8/Native/BUILD.md`).
5. Verify build passes (`dotnet build`, all 330 tests green).
6. Run S1 R&R synthetic study. Accept if bias ≤ ±2.0 dB; adjust −26.5 dB constant and repeat if not.
7. Close GitHub #11 (D-003) as duplicate of #12. Update #12 description with corrected bias characterisation and frequency-dependent data from endurance run.

**Rollback**: Revert `ft8_shim.c` and restore `FT8_SHIM_VERSION` to 20260010. The ABI sentinel prevents a version mismatch from silently loading the wrong binary.

---

## Open Questions

- **−26.5 dB constant**: Will S1 show a residual bias requiring adjustment? Unknown until S1 is run post-fix. The design keeps the constant as-is; the S1 task will determine whether an update is needed.
- **Window width tuning**: The 32-bin width is a reasonable first choice. S1 and S6 results will indicate whether adjustment improves accuracy.
