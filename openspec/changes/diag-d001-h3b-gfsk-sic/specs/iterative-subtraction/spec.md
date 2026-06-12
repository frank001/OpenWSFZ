## MODIFIED Requirements

### Requirement: Two-pass decode structure with GFSK quadrature PCM-domain SIC

`K_MAX_PASSES` SHALL remain **2**. Pass 0 is the full-waterfall decode (unchanged). Between
pass 0 and pass 1, the shim SHALL perform **PCM-domain successive interference cancellation
(SIC)** using a **GFSK quadrature synthesiser**: for each signal decoded in pass 0, a pair of
quadrature GFSK waveforms (I = sine component, Q = cosine component) is synthesised from the
decoded tone sequence (via `ft8_encode`) using a Gaussian smoothing pulse (BT=2.0, 3-symbol
span), and the optimal amplitude and phase are estimated analytically from a single O(N)
dot-product pass. The signal is subtracted from a heap-allocated PCM residual using both
quadrature components. After all pass-0 signals have been subtracted, the waterfall for pass 1
is rebuilt from the residual via a second `monitor_t`. Pass 1 then searches the rebuilt
waterfall. Both passes participate in the cross-pass deduplication hash table.

GFSK synthesis parameters: Gaussian smoothing filter with BT=2.0, 3-symbol kernel span
(`GFSK_KERNEL_LEN = 3 × FT8_SAMPLES_PER_SYMBOL = 5760` samples at 12 kHz). The kernel is
normalised to unit sum. Phase accumulates continuously across all 79 symbols via cumulative
summation of the Gaussian-smoothed instantaneous frequency. The I component is `sinf(phase)`;
the Q component is `cosf(phase)`. No Hann fade-in/fade-out is applied (that is an audio
artefact mitigation; not required for PCM subtraction).

Quadrature amplitude estimation:
```
a   = sqrt(dot_I² + dot_Q²) / energy(synth_sin)
phi = atan2f(dot_Q, dot_I)
a_I = a · cos(phi)     [coefficient for sin component]
a_Q = a · sin(phi)     [coefficient for cos component]
residual[j] -= a_I · synth_sin[j]  +  a_Q · synth_cos[j]  for j in signal window
```

This estimator is valid for any carrier phase and is exact (not approximate) for a single
sinusoidal signal in the absence of noise.

#### Scenario: Pass 1 uses a waterfall rebuilt from the GFSK-subtracted PCM residual

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL be built from a PCM buffer from which the
  GFSK quadrature synthesised waveforms of all pass-0 decoded signals have been subtracted
  using the analytic quadrature estimator, not from the original PCM or any spectrogram-
  attenuated version

#### Scenario: Two-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes both passes and `ft8_get_last_pass_counts` is called
  with capacity 2
- **THEN** the function SHALL return 2 and `out_counts[0]` + `out_counts[1]` SHALL equal the
  total number of unique messages returned by `ft8_decode_all`

#### Scenario: Decode loop terminates after K_MAX_PASSES (2) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 2 passes regardless of how many
  signals remain in the residual

---

### Requirement: PCM-domain SIC heap allocation — five buffers, total ≈ 2.21 MB

If a PCM-domain SIC stage executes in `ft8_decode_all`, it SHALL allocate exactly five
heap buffers and free all five before the function returns:

| Buffer | Size | Purpose |
|---|---|---|
| `residual_pcm` | `FT8_EXPECTED_SAMPLES × sizeof(float)` = 720 000 B | PCM residual |
| `synth_buf` | same | GFSK I (sin) component for current signal |
| `synth_buf_q` | same | GFSK Q (cos) component for current signal |
| `gfsk_kernel` | `GFSK_KERNEL_LEN × sizeof(float)` = 23 040 B | Gaussian pulse |
| `gfsk_prefix` | `(GFSK_KERNEL_LEN+1) × sizeof(float)` = 23 044 B | Prefix sum |

No automatic (stack) array exceeding 100 bytes SHALL be declared anywhere in the call chain
from `ft8_decode_all`. This constraint is unchanged from the H3 diagnostic.

#### Scenario: All five PCM-domain SIC buffers are heap-allocated

- **WHEN** `ft8_decode_all` is compiled with the H3b GFSK quadrature SIC path enabled
- **THEN** all five buffers SHALL be allocated via `malloc` and freed before the function
  returns, with no automatic arrays of those sizes declared anywhere in the call chain

#### Scenario: Allocation failure falls back to pass-0-only decode

- **WHEN** `malloc` returns NULL for any of the five SIC buffers
- **THEN** `ft8_decode_all` SHALL free all non-NULL allocations, skip the PCM-domain SIC
  stage, and return whatever results pass 0 produced, without crashing or invoking undefined
  behaviour

---

## REMOVED Requirements

### Requirement: CP-FSK scalar synthesiser and scalar amplitude projection

**Reason:** Replaced by GFSK quadrature synthesiser and analytic quadrature estimator (H3b).
The `synth_ft8_cpsfc` and `compute_projection_amplitude` functions are removed from
`ft8_shim.c`. The scalar projection `a = dot(pcm, synth) / dot(synth, synth)` is replaced by
the analytic estimator above.

**Migration:** No managed API or caller impact — these were internal shim implementation
details. The external behaviour (K_MAX_PASSES=2, pass-count TLS getter) is unchanged.

### Requirement: Two heap buffers (residual_pcm + synth_buf = 1.44 MB) — H3 version

**Reason:** Superseded by the five-buffer, 2.21 MB allocation above. `synth_buf_q`,
`gfsk_kernel`, and `gfsk_prefix` are additions; `residual_pcm` and `synth_buf` are retained.

**Migration:** None — the heap budget increases by ≈ 0.77 MB. No caller-visible change.
