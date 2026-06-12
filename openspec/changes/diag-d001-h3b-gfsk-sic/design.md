## Context

H3 (diag-d001-pcm-sic, shim 20260008) was rejected: −13.98 pp regression overall, P0/P1
co-channel unchanged at 0/6. Post-mortem confirmed two compounding model errors in the
CP-FSK/cosine cancellation synthesiser:

1. **Modulation mismatch:** Real FT8 uses GFSK — the instantaneous frequency is shaped by a
   Gaussian filter (BT=2.0, 3-symbol span). The H3 shim synthesised CP-FSK — rectangular
   frequency pulses with instantaneous symbol transitions. The waveforms are orthogonal near
   symbol boundaries; dot-product energy from the actual signal is lost there.

2. **Phase basis mismatch:** `synth_ft8_cpsfc` wrote `cosf(phase)` and assumed phase zero.
   A real signal arrives at an unknown carrier phase φ. Correlating `cos(ω·t)` against
   `A·sin(ω·t + φ)` yields `A·cos(φ − π/2) = A·sin(φ)`, which is near-zero for many φ.
   No phase-sweep or estimation was performed, so the projection amplitude `a ≈ 0` for most
   signals, removing nothing from the residual.

The combination drove the cancellation amplitude to near-zero for every decoded signal.
Spectrogram suppression — which had provided modest benefit — was removed as part of H3 with
nothing to replace it, producing the regression.

H3b corrects both errors simultaneously, advancing to the correct signal model.

**Current shim state:** `FT8_SHIM_VERSION = 20260008`, `K_MAX_PASSES = 2`, PCM-domain SIC
with CP-FSK synthesis and scalar amplitude projection.

**Key constraint (unchanged from H3):** All buffers > 100 bytes MUST be heap-allocated.
No VLAs. No automatic arrays > ~100 bytes in any function reachable from `ft8_decode_all`.

---

## Goals / Non-Goals

**Goals:**

- Replace `synth_ft8_cpsfc` with a GFSK quadrature synthesiser that matches the Python QA
  synthesiser model (BT=2.0, 3-symbol Gaussian pulse, sine phase — the same model used to
  generate S7 test signals).
- Replace `compute_projection_amplitude` with a quadrature estimator that recovers the correct
  amplitude and phase analytically without sweeping.
- Maintain all heap-allocation constraints (≤100 bytes on stack).
- Validate H3b via an S7 R&R study run after merge.
- Keep the implementation split into two independently-CI-green tasks.
- Maintain all existing tests green.

**Non-Goals:**

- Channel estimation or equalisation (multipath, Doppler).
- Iterating or refining the amplitude estimate (single-pass, O(N) only).
- Combining spectrogram suppression with PCM-domain SIC (clean single-variable diagnostic).
- Changes to `K_MAX_PASSES` (stays 2), `MaxDecodePasses` (stays 2), or `MaxResults` (stays 340).
- Matching the Python synthesiser's 10 ms Hann fade-in/fade-out (that is an audio artefact
  mitigation for playback; the shim is subtracting from PCM, not playing audio).

---

## Decisions

### Decision 1 — GFSK quadrature synthesis matching the Python QA synthesiser

**Chosen:** Replace `synth_ft8_cpsfc` with `synth_ft8_gfsk_quad`, which produces both the
I (sine) and Q (cosine) quadrature components of the GFSK waveform using the same algorithm
as the Python QA synthesiser in `qa/rr-study/synth/modulator.py`.

**Algorithm:**

```
// Step 1: Gaussian pulse kernel (precomputed once — see Decision 6)
//
// BT      = 2.0  (GFSK bandwidth-time product, per FT8 standard and QA synthesiser)
// span    = 3    (kernel spans 3 symbol periods)
// K       = span * SPS                          // K = 5760 at 12 kHz
// sigma   = sqrt(ln(2)) / (2π × BT)            // ≈ 0.06622 symbol periods
//
// For j in [0, K):
//   t_j    = ((float)j - (float)(K/2) + 0.5f) / (float)SPS   // symbol-period units
//   pulse[j] = expf(-t_j * t_j / (2.0f × sigma × sigma))
// Normalise: pulse /= sum(pulse)
//            (ensures convolution preserves tone-index magnitude, not time-integral)

// Step 2: Convolve the tone sequence with the kernel — mode "same"
//
// tone_arr is piecewise constant: tone_arr[n] = tones[n / SPS] for n in [0, FT8_NN * SPS)
//
// For efficiency, use prefix sums of the kernel (cumulative sum of pulse[]):
//   prefix[0] = 0;  prefix[j+1] = prefix[j] + pulse[j]
//
// For each output sample i in [0, FT8_NN * SPS):
//   half = K / 2        // = 2880
//   smoothed[i] = 0
//   for each symbol sym such that [sym*SPS, (sym+1)*SPS) overlaps the kernel window:
//     k_lo = max(0, sym * SPS - (i - half))
//     k_hi = min(K, (sym+1)*SPS - (i - half))
//     if k_lo >= k_hi: continue
//     smoothed[i] += tones[sym] * (prefix[k_hi] - prefix[k_lo])
//   (at most 4 symbols contribute for any i, given BT=2.0's narrow kernel)

// Step 3: Phase accumulation and I/Q output
//
// phase = 0.0f
// for i in [start_sample, start_sample + FT8_NN * SPS):
//   i_tone = i - start_sample                                  // index into smoothed[]
//   inst_freq = base_freq_hz + smoothed[i_tone] * TONE_SPACING_HZ
//   phase += 2π × inst_freq / FT8_SAMPLE_RATE_F               // cumulative integral
//   if i in [0, buf_len):
//     buf_sin[i] = sinf(phase)    // I component
//     buf_cos[i] = cosf(phase)    // Q component
```

**Memory requirements for this function** (all heap-allocated by the caller — see Decision 3):
- `kernel[K]` = 3 × SPS = 5 760 floats = 23 040 bytes — Gaussian pulse
- `prefix[K+1]` = 5 761 floats = 23 044 bytes — prefix sum for the convolution optimisation
- `smoothed[FT8_NN × SPS]` = 79 × 1920 = 151 680 floats = 606 720 bytes — smoothed frequency

The `smoothed` buffer is the largest. It is possible to avoid materialising it at all by
computing each sample's smoothed value on-the-fly (the prefix optimisation makes this O(4)
per sample), which would eliminate the 592 KB allocation at the cost of code complexity.
The design leaves this as an implementation choice for the Developer; the unit test must pass
regardless of approach. The `kernel` and `prefix` buffers MUST be reused across all signals
within a single SIC stage (not reallocated per signal).

**Rationale:** Matches the actual signal model used by the S7 synthetic fixtures. Both error
modes from H3 are corrected: (1) GFSK vs CP-FSK, (2) phase-aware quadrature vs cosine-only.

**Alternative considered:** Sweeping phase in [0, 2π) at discrete steps to find the maximum
projection — rejected because it is O(N × steps) and introduces a confound (optimal phase
depends on step granularity). The analytic quadrature estimator is exact at O(N).

---

### Decision 2 — Quadrature amplitude/phase estimation (analytic, O(N))

**Chosen:** Replace `compute_projection_amplitude` with `compute_quadrature_amplitude`, which
computes the optimal subtraction coefficients for both quadrature components:

```
dot_I  = dot(residual_pcm[start..end], synth_sin[start..end])
dot_Q  = dot(residual_pcm[start..end], synth_cos[start..end])
energy = dot(synth_sin[start..end], synth_sin[start..end])
         // ≈ dot(synth_cos, synth_cos) for unit-amplitude GFSK; use synth_sin's value

if energy == 0.0: return (0, 0)          // degenerate guard

a   = sqrtf(dot_I*dot_I + dot_Q*dot_Q) / energy
phi = atan2f(dot_Q, dot_I)

a_I = a * cosf(phi)                      // coefficient for sin component
a_Q = a * sinf(phi)                      // coefficient for cos component
```

The subtraction in the outer loop then becomes:
```
for j in [win_start, win_end):
    residual_pcm[j] -= a_I * synth_buf[j]   +  a_Q * synth_buf_q[j]
```

**Mathematical correctness:** For `residual ≈ A·sin(ω·t + φ)`:
- `dot_I = A·(N/2)·cos(φ)`, `dot_Q = A·(N/2)·sin(φ)`, `energy = N/2`
- `a = A`, `phi_est = φ`
- Reconstruction: `a_I·sin(ω·t) + a_Q·cos(ω·t) = A·sin(ω·t + φ)` ✓

The formula is valid for any carrier phase φ and any amplitude A ≥ 0. In co-channel
conditions (two overlapping signals), the dot products carry contributions from both signals;
the cross-correlation of two random FT8 waveforms is small on average (near-orthogonal tone
sequences), so amplitude estimation remains approximately correct.

**Note on the energy term:** `energy` is computed from `synth_sin` by dot-product, not
assumed to equal `(win_end − win_start) / 2`. Computing it explicitly is robust to boundary
effects (partial symbol windows near `FT8_EXPECTED_SAMPLES`).

**Rationale:** Analytic, exact, O(N). No iteration, no sweep, no additional heap allocation
beyond the two synth buffers.

---

### Decision 3 — Three heap-allocated buffers; kernel/prefix allocated once per SIC stage

**Chosen:** The pass-1 SIC block allocates the following buffers:

| Buffer | Size (bytes) | Purpose |
|---|---|---|
| `residual_pcm` | 720 000 | PCM copy into which signals are subtracted |
| `synth_buf` | 720 000 | GFSK I (sin) component for current signal |
| `synth_buf_q` | 720 000 | GFSK Q (cos) component for current signal |
| `gfsk_kernel` | 23 040 | Gaussian pulse coefficients (reused across all signals) |
| `gfsk_prefix` | 23 044 | Prefix sum of kernel (reused across all signals) |

Total heap for PCM-domain SIC: ≈ 2.21 MB.

`gfsk_kernel` and `gfsk_prefix` are computed once at the start of the SIC stage and reused
for every signal. `synth_buf` and `synth_buf_q` are zeroed (`memset`) before each signal.

**Allocation failure policy (unchanged from H3):** If any allocation returns NULL, free all
non-NULL allocations (`free(NULL)` is a no-op per C11 §7.22.3.3) and fall back to pass-0
results only. No crash; no undefined behaviour.

**Alternative considered:** Static module-level kernel with lazy initialisation. Rejected
because it introduces a benign but formally undefined data race between threads sharing the
binary. Per-call heap allocation of the kernel is clean, auditable, and bounded.

---

### Decision 4 — Waterfall rebuild via second `monitor_t` (unchanged from H3)

No change to this mechanism. `monitor_t mon2` is initialised from `residual_pcm` after all
pass-0 signals have been subtracted. Pass 1 candidate search uses `mon2.wf`. `mon2` is freed
before `mon` in section 6. This is confirmed safe (monitor.c isolation gate verified in H3
task 1.1 and documented in the existing shim comment).

---

### Decision 5 — Spectrogram suppression REPLACED, not combined (unchanged from H3)

`suppress_candidate_tiles` remains in the source but is not called. Combining it with
PCM-domain SIC would introduce a confound: improvement cannot then be attributed cleanly to
the GFSK quadrature canceller. H3b is a clean single-variable test.

---

### Decision 6 — T1/T2 implementation split

**T1 — Synthesis and estimation functions only** (not wired into the decode path):
- Remove `synth_ft8_cpsfc` and `compute_projection_amplitude`.
- Add `synth_ft8_gfsk_quad` and `compute_quadrature_amplitude`.
- `FT8_SHIM_VERSION` stays at `20260008`. Zero regression risk.

**T2 — Integration, version bump, binary rebuild:**
- Wire T1 functions into the pass-1 SIC block.
- Add `synth_buf_q`, `gfsk_kernel`, `gfsk_prefix` heap allocations.
- Update subtraction loop.
- Bump `FT8_SHIM_VERSION` to `20260009`.
- Update `ExpectedShimVersion` in `Ft8LibInterop.cs`.
- Rebuild all three platform binaries.

**Rationale:** Identical to H3's split rationale. Each task is completable in one session,
leaves CI green, and is independently reviewable.

---

## Risks / Trade-offs

**[Low-SNR amplitude estimation noise] → Accepted for diagnostic**
At low SNR the dot products `dot_I` and `dot_Q` carry noise contributions that degrade the
amplitude estimate. The S7 gate criteria (any improvement on P0/P1; ≥ +5 pp overall) are
deliberately modest and remain unchanged from H3.

**[GFSK model mismatch vs real WSJT-X transmitters] → Residual risk**
S7 synthetic scenarios use signals generated by the Python QA synthesiser with BT=2.0. If
real WSJT-X transmitters use a slightly different BT, pulse span, or phase convention, the
cancellation amplitude will be degraded. This is immaterial for the S7 synthetic validation
gate; any real-signal impact is a separate concern for post-H3b investigation.

**[Cross-signal contamination of dot products] → Accepted**
In exact co-channel (P0) conditions, `dot_I` contains contributions from both signals. The
cross-correlation is near-zero on average for random FT8 tone sequences; the estimate is
approximately correct. The diagnostic will reveal whether this is a practical limitation.

**[Three-platform native rebuild required] → Unavoidable**
Identical constraint to H3. Captain is responsible for the macOS ARM64 binary.

**[Allocation failure degrades to pass-0 only] → Acceptable fallback**
Unchanged from H3. Any of the five allocations returning NULL triggers a graceful fallback.

**[prefix-sum smoothed array optimisation vs naive convolution] → Implementation choice**
The design specifies the prefix-sum optimisation for efficiency; the unit test (T1) constrains
correctness. The Developer may choose any implementation that passes the unit test.

---

## Open Questions

None. All technical decisions confirmed during proposal review (QA, 2026-06-12).
