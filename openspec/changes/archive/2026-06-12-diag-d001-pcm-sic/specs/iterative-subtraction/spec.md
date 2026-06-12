## MODIFIED Requirements

### Requirement: Two-pass decode structure with PCM-domain SIC

`K_MAX_PASSES` SHALL be set to **2**. Pass 0 is the full-waterfall decode (unchanged). Between
pass 0 and pass 1, the shim SHALL perform **PCM-domain successive interference cancellation
(SIC)**: for each signal decoded in pass 0, a CP-FSK waveform is synthesised from the decoded
tone sequence (via `ft8_encode`), scaled to the input PCM via least-squares amplitude projection,
and subtracted from a heap-allocated copy of the input PCM (`residual_pcm`). After all pass-0
signals have been subtracted, the waterfall for pass 1 is rebuilt from `residual_pcm` using a
second `monitor_t` initialised with the same configuration as pass 0. Pass 1 then operates on
the rebuilt waterfall. Both passes participate in the cross-pass deduplication hash table so no
message is reported more than once.

CP-FSK synthesis parameters: continuous-phase FSK; tone spacing 6.25 Hz; phase initialised to
0.0 for all signals (no carrier phase estimation); no Gaussian or raised-cosine shaping filter.

Amplitude projection: `a = dot(residual_pcm[window], synth_buf[window]) / dot(synth_buf[window], synth_buf[window])`.

#### Scenario: Pass 1 uses a waterfall rebuilt from the PCM residual

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL be built from a PCM buffer from which the
  synthesised waveforms of all pass-0 decoded signals have been subtracted, not from the
  original input PCM or a spectrogram-attenuated version of it

#### Scenario: Two-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes both passes and `ft8_get_last_pass_counts` is called with
  capacity 2
- **THEN** the function SHALL return 2 and `out_counts[0]` + `out_counts[1]` SHALL equal the
  total number of unique messages returned by `ft8_decode_all`

#### Scenario: Decode loop terminates after K_MAX_PASSES (2) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 2 passes regardless of how many
  signals remain in the residual

---

### Requirement: Any PCM residual buffer SHALL use heap allocation, not stack allocation

If a PCM-domain residual buffer of size `FT8_EXPECTED_SAMPLES * sizeof(float)` (720 000 bytes)
is required in `ft8_decode_all`, it SHALL be allocated via `malloc` and freed before function
return. A synthesised-signal scratch buffer of the same size SHALL also be heap-allocated.
Stack allocation of any buffer exceeding 100 bytes in a function called via P/Invoke from a
.NET thread-pool thread is prohibited — the combined managed + native stack frame approaches
the 1 MB thread-pool thread stack limit. This applies to ALL buffers used in or called from
`ft8_decode_all`, including any internal synthesis helpers.

#### Scenario: PCM residual and synth buffers are heap-allocated

- **WHEN** `ft8_decode_all` is compiled with the PCM-domain SIC path enabled
- **THEN** both `residual_pcm` and `synth_buf` SHALL be allocated with
  `malloc(FT8_EXPECTED_SAMPLES * sizeof(float))` and freed before the function returns,
  with no automatic (stack) arrays of those sizes declared anywhere in the call chain

#### Scenario: Allocation failure falls back to pass-0-only decode

- **WHEN** `malloc` returns NULL for either `residual_pcm` or `synth_buf`
- **THEN** `ft8_decode_all` SHALL free any buffer that was successfully allocated, skip
  the PCM-domain SIC stage entirely, and return whatever results pass 0 produced, without
  crashing or invoking undefined behaviour

---

## REMOVED Requirements

### Requirement: Soft SNR-scaled tile attenuation (fix-d001-revised Option B)

**Reason:** Replaced by PCM-domain SIC for the H3 diagnostic. The `suppress_candidate_tiles`
function is retained in the shim source but is no longer called in the inter-pass stage. If H3
is rejected, this requirement may be reinstated in a follow-on change.

**Migration:** No managed API or caller impact — this was an internal shim implementation detail.
The external behaviour (K_MAX_PASSES=2, pass-count TLS getter) is unchanged.

---

### Requirement: Option C approval gate — PoC SHALL demonstrate improvement before PCM-domain SIC implementation proceeds

**Reason:** Superseded by H3 diagnostic decision. The Captain has explicitly approved proceeding
with a PCM-domain SIC diagnostic implementation without a prior Python proof-of-concept. The H3
diagnostic experiment itself serves the PoC validation role. The S7 R&R study result (T3) is the
acceptance gate.

**Migration:** None.
