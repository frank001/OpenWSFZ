# iterative-subtraction Specification

## Purpose
Specifies the multi-pass iterative decode capability introduced in p15 (spectrogram-domain
suppression, 2 passes) and updated in fix-d001-revised Option B (soft SNR-scaled attenuation).
After the first decode pass, decoded signals have their waterfall tiles attenuated by a factor
derived from the decoded signal's SNR; a second pass operates on the attenuated waterfall to
recover weaker co-channel signals. At high SNR (≥ +15 dB) the factor is 0.0 (full suppression,
matching the original hard-zero behaviour). At low SNR (≤ −5 dB) the factor is 1.0 (no change),
avoiding collateral damage on adjacent weaker signals when a borderline decode shares tile bins.
This capability is implemented in the native `ft8_shim.c` and exposed to managed code via the
`ft8lib-interop` layer.

## Requirements

### Requirement: Two-pass decode structure with spectrogram-domain suppression

`K_MAX_PASSES` SHALL be set to **2**. Pass 0 is the full-waterfall decode (unchanged). Pass 1 is a
spectrogram-domain suppression decode: for each decoded candidate from pass 0, the shim attenuates
that signal's energy in the waterfall using a soft SNR-scaled factor for the exact decoded tone bin
and its ±1 nearest neighbours for each of the 79 FT8 symbols, then re-runs `ftx_find_candidates`
and `ftx_decode_candidate` on the modified waterfall. Both passes participate in the cross-pass
deduplication hash table so no message is reported more than once.

#### Scenario: Pass 1 uses the spectrogram-suppressed waterfall

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL have the tile energy of all pass-0 decoded signals
  attenuated (or zeroed, for strong signals) before candidate search begins

#### Scenario: Two-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes both passes and `ft8_get_last_pass_counts` is called with
  capacity 2
- **THEN** the function SHALL return 2 and `out_counts[0]` + `out_counts[1]` SHALL equal the total
  number of unique messages returned by `ft8_decode_all`

#### Scenario: Decode loop terminates after K_MAX_PASSES (2) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 2 passes regardless of how many signals
  remain

---

### Requirement: Soft SNR-scaled tile attenuation (fix-d001-revised Option B)

Rather than hard-zeroing suppressed tiles (which over-suppresses borderline decodes whose tile
bins may overlap with an adjacent co-channel signal), the suppression SHALL use a linear
attenuation factor derived from the decoded signal's SNR:

```
factor = 1.0 − clamp((snr_db − K_SOFT_SUPP_SNR_MIN_DB) / (K_SOFT_SUPP_SNR_MAX_DB − K_SOFT_SUPP_SNR_MIN_DB), 0.0, 1.0)
tile_value = noise_raw + factor * (tile_value − noise_raw)
```

where `K_SOFT_SUPP_SNR_MIN_DB = −5.0f` and `K_SOFT_SUPP_SNR_MAX_DB = 15.0f`.

- At SNR ≥ +15 dB: factor = 0.0 → tile is fully suppressed (assigned noise_raw, equivalent to the previous hard-zero behaviour).
- At SNR ≤ −5 dB: factor = 1.0 → tile is unchanged (no suppression).
- Between: factor varies linearly between 0.0 and 1.0.

Both constants SHALL be defined as named C preprocessor constants in `ft8_shim.c`; no magic
numbers for the SNR gate boundaries.

#### Scenario: Strong signal (SNR ≥ K_SOFT_SUPP_SNR_MAX_DB) is fully suppressed

- **WHEN** a signal decoded in pass 0 has SNR ≥ K_SOFT_SUPP_SNR_MAX_DB (+15 dB)
- **THEN** all suppressed tiles SHALL be assigned noise_raw (attenuation factor = 0.0)

#### Scenario: Weak signal (SNR ≤ K_SOFT_SUPP_SNR_MIN_DB) is not suppressed

- **WHEN** a signal decoded in pass 0 has SNR ≤ K_SOFT_SUPP_SNR_MIN_DB (−5 dB)
- **THEN** no tile energy is removed from the waterfall (attenuation factor = 1.0)

#### Scenario: Mid-range SNR produces linear interpolation

- **WHEN** a signal decoded in pass 0 has SNR at the midpoint (+5 dB)
- **THEN** each suppressed tile SHALL be set to noise_raw + 0.5 × (tile − noise_raw) (factor ≈ 0.5)

---

### Requirement: K_MAX_PASSES is a named constant, not a magic number

The maximum number of decode passes SHALL be defined as a named C preprocessor constant
`K_MAX_PASSES` in `ft8_shim.c` with a value of 2. No literal integer representing the pass
count SHALL appear in the loop-control logic.

#### Scenario: Named constant is used for loop termination

- **WHEN** the source of `ft8_shim.c` is inspected
- **THEN** the decode iteration loop SHALL reference `K_MAX_PASSES` as its upper bound, not a
  bare integer literal

---

### Requirement: Per-pass decode counts are queryable after each call

After `ft8_decode_all` returns, the calling thread SHALL be able to query the number of new
decoded messages produced by each individual pass via `ft8_get_last_pass_counts(int* out_counts,
int capacity)`. This function SHALL populate `out_counts[i]` with the count of new
(non-duplicate) messages decoded in pass `i` (0-indexed) for both passes. The return value
SHALL be **2** (the number of passes executed). The data SHALL be stored in thread-local storage.

#### Scenario: Per-pass counts reflect actual new decodes across two passes

- **WHEN** `ft8_decode_all` decodes N₀ messages in pass 0 and N₁ new messages in pass 1
- **THEN** `ft8_get_last_pass_counts` SHALL return 2 and populate `out_counts[0] = N₀`,
  `out_counts[1] = N₁`

#### Scenario: Per-pass counts are zero when no signals are present

- **WHEN** `ft8_decode_all` is called with a silent PCM buffer
- **THEN** `ft8_get_last_pass_counts` SHALL return 2 and all entries in `out_counts` SHALL be 0

---

### Requirement: C# decoder logs per-pass stats at Debug level

After each decode cycle, `Ft8Decoder` SHALL log one Debug-level message per pass of the form
`"Iterative subtraction: pass {n} of {max}, {k} new decodes"`, where `{n}` is the 1-based pass
number, `{max}` is **2**, and `{k}` is the number of new messages decoded in that pass.

#### Scenario: Two per-pass log messages appear at Debug level

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle with an ILogger configured at Debug
  level
- **THEN** the log output SHALL contain **2** messages matching the pattern
  `"Iterative subtraction: pass N of 2, K new decodes"` for N = 1, 2

---

### Requirement: Option C approval gate — PoC SHALL demonstrate improvement before PCM-domain SIC implementation proceeds

*(Gated on Captain approval — only applicable if Option C is approved in fix-d001-revised task 5.2)*

If a PCM-domain SIC approach (per-symbol amplitude estimation + linear frequency trajectory) is
considered for implementation, a Python proof-of-concept SHALL demonstrate ≥ +5 percentage-point
improvement on at least 10 synthetic S7 co-channel trial cases before any production native code
is written. The Captain SHALL explicitly approve the PoC results before implementation begins.

This requirement exists to prevent a repeat of the `fix-d001-pcm-sic` pattern, in which
production-quality three-platform infrastructure was built before the core hypothesis was validated
on even the simplest synthetic test cases.

#### Scenario: PoC gate blocks production implementation

- **WHEN** a PCM-domain SIC PoC is completed
- **AND** the PoC improvement on synthetic S7 cases is < +5 pp
- **THEN** production implementation SHALL NOT proceed; the Captain is informed and Option D is evaluated

#### Scenario: Captain approval gate is recorded before Option C implementation

- **WHEN** the PoC improvement on synthetic S7 cases is ≥ +5 pp
- **THEN** the Captain SHALL review the PoC results and provide explicit approval before any
  production changes to `ft8_shim.c` are authored

---

### Requirement: Any PCM residual buffer SHALL use heap allocation, not stack allocation

*(Gated on Captain approval — only applicable if Option C is approved in fix-d001-revised task 5.2)*

If a PCM-domain residual buffer of size `FT8_EXPECTED_SAMPLES * sizeof(float)` (720 000 bytes)
is required in `ft8_decode_all`, it SHALL be allocated via `malloc` and freed before function
return. Stack allocation of any buffer exceeding 100 KB in a function called via P/Invoke from
a .NET thread pool thread is prohibited, as the combined managed + native stack frame approaches
the 1 MB thread pool thread stack limit.

#### Scenario: PCM residual is heap-allocated

- **WHEN** `ft8_decode_all` is compiled with any PCM-domain SIC path enabled
- **THEN** the residual buffer SHALL be allocated with `malloc(FT8_EXPECTED_SAMPLES * sizeof(float))`
  and freed with `free()` before the function returns, with no automatic (stack) array of that size declared

#### Scenario: Allocation failure is handled gracefully

- **WHEN** `malloc` returns NULL for the residual buffer
- **THEN** `ft8_decode_all` SHALL fall back to the single-pass (no SIC) decode path and return
  whatever results pass 0 produced, without crashing

---

## Acceptance Criteria

### AC-IS-1 — Recovery rate: co-channel improvement target

**Status: NOT MET (D-001 Open) — Option B improves overall S7 recovery but P0/P8 remain at 0/6.**

History:
- **p15 spectrogram-domain hard-zero (baseline, `6bab388`):** 46.2% S7 synthetic co-channel;
  69.1% ground-truth corpus (613/887).
- **fix-D001 PCM-domain SIC (reverted, `efc0920`):** No improvement; two P1 crashes.
- **fix-d001-revised Option A audit:** kgoba/ft8_lib has one post-v2.0 commit (non-standard
  callsign support only) — decode pipeline unchanged; no upstream update taken.
- **fix-d001-revised Option B (`15b220b`, FT8_SHIM_VERSION=20260004):** Soft SNR-scaled
  tile attenuation deployed. R&R run `2026-06-07-15b220b`: S7 overall **57.0%** (+10.8 pp vs
  46.2% baseline). Near-collision +13.3 pp, capture +16.7 pp. S1–S6 all PASS. Ground-truth
  corpus 69.2% (614/887). **P0 (2-stack equal 0 dB) 0/6 — unchanged. P8 (co-freq dt 0.5 s)
  0/6 — unchanged.**
- **Option C (PCM-domain amplitude-tracked SIC):** Not pursued at this time (Captain decision
  2026-06-07). Gate criterion: ≥ +5 pp PoC improvement on synthetic S7 before any production
  C code. Available as future research path.

**The ≥ 1/6 improvement target on P0 and P8 is not yet met.** D-001 remains Open; further
iteration deferred. Soft attenuation (Option B) is the current production configuration.

**Current production baseline (`15b220b`):** 69.2% (614/887 matched overall); S7 overall 57.0%;
P0 (2-stack equal SNR) 0/6, P8 (time-freq co-freq dt 0.5 s) 0/6.

### AC-IS-2 — Fixture answer-key: G6 gate

Three committed synthetic fixtures (`synth-qso-01`, `synth-qso-02`, `synth-qso-03`) decode
correctly with K_MAX_PASSES=2. G6 gate: 3/3 passed.

### AC-IS-3 — False-positive rate

False-positive rate must remain ≤ 6% (same threshold as p15 baseline).

### AC-IS-4 — Per-pass Debug logging

`Ft8Decoder.cs` emits exactly 2 Debug-level messages per cycle:
`"Iterative subtraction: pass 1 of 2, N new decodes"`,
`"Iterative subtraction: pass 2 of 2, M new decodes"`.

### AC-IS-5 — Timing budget

Two passes complete within the 13 s / 30 s CI budget (pass 0 ~700 ms + spectrogram suppress
~5 ms + pass 1 ~700 ms ≈ 1.4 s total).
