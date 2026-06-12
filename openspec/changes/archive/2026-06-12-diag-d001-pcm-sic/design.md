## Context

D-001 (co-channel decode gap, High severity) has resisted two diagnostic attempts:

- **H1 (fix-D001, reverted):** PCM-domain SIC with a 720 KB automatic (stack) residual buffer.
  Crashed (`0xC0000005`) on two production runs — the combined managed + native stack frame
  exceeded the 1 MB .NET thread-pool thread stack limit. The algorithm was never validated;
  the crash was a pure implementation failure.
- **H2 (diag-d001-three-pass-sic, reverted):** Three-pass spectrogram-domain SIC. Result: −4.30 pp
  regression; P0/P1 co-channel remained at 0/6. Root cause confirmed: when two FT8 signals occupy
  exactly the same frequency at the same time, their waterfall tiles are superimposed before the
  waterfall is built. No number of spectrogram-domain passes can recover information destroyed at
  that stage.

H3 re-attempts PCM-domain SIC with the H1 crash fixed — heap allocation throughout — and phase
estimation deferred (phase-zero assumption for diagnostic simplicity). This is a controlled
diagnostic experiment, not a production fix. The goal is a single clean data point: does
PCM-domain SIC produce measurable improvement on P0/P1 before further investment is made.

**Current shim state:** `FT8_SHIM_VERSION = 20260006`, `K_MAX_PASSES = 2`, two-pass
spectrogram-domain SIC with soft SNR-scaled attenuation.

**Key constraint from Captain (explicitly confirmed):** All buffers > a few hundred bytes MUST be
heap-allocated. No VLAs. No automatic arrays > ~100 bytes in any function reachable from
`ft8_decode_all`. This is a hard architectural constraint, not a suggestion.

---

## Goals / Non-Goals

**Goals:**

- Implement PCM-domain SIC as a drop-in replacement for the spectrogram-domain suppression step
  in `ft8_decode_all`, using heap-allocated buffers and CP-FSK synthesis.
- Validate H3 via an S7 R&R study run after merge.
- Keep the implementation split into two small, independently-CI-green tasks so no context-window
  overflow can strand an incomplete implementation.
- Maintain all 319 existing tests green.

**Non-Goals:**

- Gaussian pulse shaping — CP-FSK only (no BT filter).
- Phase estimation — phase zero throughout; phase mismatch produces a residual, not a crash.
- Re-implementing spectrogram suppression in parallel with PCM-domain SIC — spectrogram
  suppression is *replaced*, not combined, to keep H3 a clean single-variable test.
- Production-quality amplitude estimation beyond the least-squares projection described below.
- Changes to `K_MAX_PASSES` (stays 2), `MaxDecodePasses` (stays 2), or `MaxResults` (stays 340).

---

## Decisions

### Decision 1 — CP-FSK synthesis: continuous-phase, tone-stepped, phase zero

**Chosen:** For each decoded signal, compute the 79-tone CP-FSK waveform from the `ft8_encode`
tone sequence. The instantaneous frequency steps at each symbol boundary to
`freq_hz + tones[i] * TONE_SPACING_HZ` (where `TONE_SPACING_HZ = 6.25f`). Phase accumulates
continuously across symbol boundaries; no phase discontinuities at symbol transitions.
Synthesis starts at phase 0. No Gaussian or raised-cosine frequency shaping.

```
phase = 0.0
for sym in 0..78:
    f_tone = freq_hz + tones[sym] * 6.25
    for s in 0..SAMPLES_PER_SYMBOL-1:
        synth_buf[start + sym*SAMPLES_PER_SYMBOL + s] = amplitude * cosf(phase)
        phase += 2π * f_tone / SAMPLE_RATE
```

**Rationale:** Matches the modulation model ft8_lib decodes against. Simpler than GFSK. Phase zero
is the correct starting assumption for a diagnostic when carrier phase is unknown.

**Alternative considered:** Phase estimation via peak-correlation over ±π — rejected because it
adds implementation complexity and is a confounding variable in a diagnostic experiment. If H3
produces partial improvement, phase estimation becomes H3b.

---

### Decision 2 — Amplitude via least-squares projection (dot-product scaling)

**Chosen:** The synthesised waveform is scaled to unit amplitude, then a projection coefficient is
computed:

```
a = dot(residual_pcm[start..end], synth_buf[start..end])
  / dot(synth_buf[start..end], synth_buf[start..end])
```

The subtraction is then `residual_pcm[i] -= a * synth_buf[i]` for `i` in `[start, end)`.

**Rationale:** Self-calibrating — no dependency on waterfall encoding internals. Works even with
multiple simultaneous signals; extracts the projection of the PCM onto the synthesised waveform.
At phase zero, `a ≈ A_signal * cos(phase_error)` — under-estimates when phase error is large
(a known limitation for this diagnostic). Requires no additional heap allocation beyond the two
buffers described in Decision 3.

**Alternative considered:** Estimate amplitude from `signal_db` by inverting the waterfall
encoding formula. Rejected — requires knowledge of ft8_lib's internal quantisation scale factor,
which is not exposed via the current ABI and would change if the library is updated.

---

### Decision 3 — Two heap-allocated buffers: `residual_pcm` and `synth_buf`

**Chosen:** Two explicit `float*` buffers, each of size `FT8_EXPECTED_SAMPLES * sizeof(float)`
(720 000 bytes), allocated at the start of the PCM-domain SIC phase and freed before
`monitor_free(&mon)`:

```c
float* residual_pcm = malloc(FT8_EXPECTED_SAMPLES * sizeof(float));
float* synth_buf    = malloc(FT8_EXPECTED_SAMPLES * sizeof(float));
if (!residual_pcm || !synth_buf) {
    free(residual_pcm); free(synth_buf);
    /* fallback: skip PCM-domain SIC, proceed with original waterfall */
    goto skip_pcm_sic;
}
memcpy(residual_pcm, pcm, FT8_EXPECTED_SAMPLES * sizeof(float));
```

`synth_buf` is zeroed (`memset`) before each signal's synthesis so out-of-window samples
are zero. `residual_pcm` is updated in-place after each subtraction. Both are freed via the
single cleanup label `cleanup_pcm_sic:` before waterfall rebuild.

**Rationale:** Two explicit named buffers are clearer and easier to review than a single buffer
with on-the-fly synthesis (which would require two passes over the signal window anyway for
dot-product amplitude estimation). The total allocation is 1.44 MB heap — modest and bounded.

**Key safety rules:**
- Both allocations must be checked for NULL before use.
- If *either* allocation fails, both must be freed (the one that succeeded and the NULL one —
  `free(NULL)` is defined as a no-op in C11 §7.22.3.3, so the pattern `free(p1); free(p2)` on
  failure is always safe).
- Both must be freed on ALL exit paths, including the early-exit if `n_all_supp == 0`.
- No other buffer in `ft8_decode_all` or any function it calls may use automatic allocation
  > ~100 bytes.

---

### Decision 4 — Waterfall rebuild via a second `monitor_t` on `residual_pcm`

**Chosen:** After subtraction, rebuild the waterfall by allocating a second `monitor_t` on the
stack (the struct itself is small — ~72 bytes; it is the internal `wf.mag` buffer allocated by
`monitor_init` that is large, on the heap via ft8_lib's internal malloc), initialising it with
the same `monitor_config_t cfg`, processing `residual_pcm` through it block-by-block, and using
it for pass 1's candidate search. The second `monitor_t` is freed with `monitor_free` after
pass 1 completes.

```c
monitor_t mon2;
monitor_init(&mon2, &cfg);
for (int pos = 0; pos + mon2.block_size <= FT8_EXPECTED_SAMPLES; pos += mon2.block_size)
    monitor_process(&mon2, residual_pcm + pos);
/* pass 1 candidate search uses mon2.wf instead of mon.wf */
monitor_free(&mon2);
```

**Rationale:** Clean lifecycle; identical configuration ensures the rebuilt waterfall has the
same dimensions and scaling as the original. Avoids in-place modification of `mon.wf.mag` (which
would change the pass-1 waterfall in a way that is not independent of pass-0 results — a
confound).

**Risk to verify:** `monitor_init` and `monitor_free` must have no hidden global or static side
effects that would corrupt `mon` when called a second time within the same `ft8_decode_all`
invocation. The kgoba/ft8_lib source should be read to confirm this before T2.

---

### Decision 5 — Spectrogram suppression is REPLACED, not combined

**Chosen:** The `suppress_candidate_tiles` call and its supporting accumulator loop are removed.
The `suppress_candidate_tiles` function definition is retained (it does no harm) but is not
called in H3. Pass 1 runs on the rebuilt waterfall from PCM-domain SIC.

**Rationale:** Combining both approaches introduces a confound — if H3 shows improvement, we
cannot attribute it cleanly to PCM-domain SIC vs residual spectrogram suppression. The diagnostic
value of H3 requires a clean single-variable test.

**Consequence:** The `all_supp_cands`, `all_supp_msgs`, `all_supp_snrs` accumulator arrays (and
their population loop in pass 0) are repurposed to hold the signals to be synthesised for PCM-domain
subtraction — same data, different downstream consumer. The `n_all_supp` counter and the
`K_MAX_CANDIDATES`-sized arrays are unchanged and sufficient.

---

### Decision 6 — T1/T2 iterative implementation split

**Chosen:** The change is implemented in two code tasks:

- **T1 — Synthesis function only** (`static void synth_ft8_cpsfc(...)` in `ft8_shim.c`).
  Not wired into the decode path. `FT8_SHIM_VERSION` stays at `20260006`. Zero regression risk.
  Reviewable independently; a context-window overflow in T1 does not strand an incomplete
  integration.
- **T2 — Integration + version bump.** Wires the T1 function into `ft8_decode_all`, removes
  spectrogram suppression, adds waterfall rebuild, bumps `FT8_SHIM_VERSION` to `20260008`,
  updates `ExpectedShimVersion` in `Ft8LibInterop.cs`, rebuilds all three native binaries,
  adds integration smoke-test.

**Rationale:** The previous D-001 PCM-SIC attempt ran out of context mid-implementation. Each
task must be completable in a single developer session, leave CI green, and constitute a
reviewable unit. T1 produces a function with clear inputs/outputs that can be code-reviewed
against the spec before any integration risk is introduced.

---

## Risks / Trade-offs

**[Phase mismatch → imperfect cancellation] → Accepted for diagnostic**
At phase zero, the subtraction removes `A_signal * cos(phase_error)` of the signal's amplitude.
Worst case (phase_error = π/2): no cancellation. Best case (phase_error ≈ 0): near-perfect. In
the S7 synthetic scenarios, the Python synthesiser starts at a deterministic phase, but the
recording offset introduces an unknown carrier phase. H3 will quantify the practical impact — if
P0/P1 remain at 0/6, phase mismatch is the likely culprit, and phase estimation becomes H3b.

**[`monitor_init` hidden global state] → Must verify before T2**
If `monitor_init` writes to any static or global variable, the second `monitor_t` could corrupt
the first. The ft8_lib source must be read to confirm `monitor_t` is fully self-contained. If
hidden state exists, the waterfall rebuild approach must be redesigned. **This is a pre-condition
for T2.**

**[Amplitude under-estimation in co-channel conditions] → Accepted for diagnostic**
When two signals overlap in the same PCM window, the dot-product projection of the PCM onto the
synthesised waveform for signal A includes contributions from signal B. This slightly
contaminates the amplitude estimate. For the 0-dB 2-stack case (P0), both signals have equal
amplitude, so the projection for either signal is approximately `A * (1 + cross_correlation)`.
The cross-correlation of two random FT8 signals is small (≈0) on average; the diagnostic will
reveal whether this is a practical problem.

**[Three-platform native rebuild required] → Unavoidable; see BUILD.md**
Changing `ft8_shim.c` requires rebuilding all three binaries. The Captain is responsible for
the macOS ARM64 binary (cross-compilation from Windows is not supported). CI will catch a
version mismatch via the ABI self-test.

**[Double-allocation failure degrades to pass-0 only] → Acceptable fallback**
If `malloc` returns NULL (e.g., out-of-memory), the code falls back to returning pass-0 results
only. This matches the pre-H3 behaviour (minus spectrogram suppression). No crash.

---

## Open Questions

None. All technical and scope decisions confirmed with Captain before this change was raised.
