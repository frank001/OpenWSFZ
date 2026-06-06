# iterative-subtraction Specification

## Purpose
Specifies the multi-pass iterative decode capability. Starting with p15 (spectrogram-domain
suppression, 2 passes) and extended in fix-D001 (PCM-domain SIC, 3 passes). After the first
decode pass, decoded signals are cancelled from the signal buffer and/or their waterfall tiles
are suppressed; subsequent passes operate on the residual to recover weaker co-channel signals.
This capability is implemented in the native `ft8_shim.c` and exposed to managed code via the
`ft8lib-interop` layer.

## Requirements

### Requirement: PCM-domain carrier frequency estimation for decoded signals

After pass 0 completes, the shim SHALL estimate each decoded signal's carrier frequency to
sub-Hz precision using DFT parabolic interpolation on the Costas-array column (first 7 symbols,
tone sequence 3,1,4,0,6,5,2 of the 6.25 Hz grid). For each Costas symbol window of 1920
samples, the shim SHALL compute the DFT magnitude at the expected tone bin and its two immediate
neighbours and apply parabolic interpolation:
`δf = 0.5 × (M[k+1] − M[k−1]) / (2×M[k] − M[k−1] − M[k+1]) × bin_width_hz`.
The refined carrier frequency SHALL be the average centre-frequency offset across the 7 Costas
symbols added to the waterfall-derived `freq_hz` value. Estimation SHALL only be applied to
signals with SNR ≥ −10 dB; signals below this threshold SHALL use the waterfall bin-centre
frequency without interpolation.

#### Scenario: Carrier estimation improves frequency precision over bin centre

- **WHEN** the shim processes a PCM buffer containing a synthetic FT8 signal whose true carrier
  is 850.4 Hz (between waterfall bin centres at 3.125 Hz spacing)
- **THEN** the estimated carrier SHALL be within ±0.5 Hz of 850.4 Hz after parabolic
  interpolation across the 7 Costas symbols

#### Scenario: Low-SNR signals fall back to bin-centre frequency

- **WHEN** the shim decodes a signal with reported SNR = −12 dB in pass 0
- **THEN** the signal's PCM reconstruction SHALL use the waterfall-derived `freq_hz` without
  interpolation and SHALL still be subtracted from the residual buffer

---

### Requirement: CP-FSK waveform synthesis for decoded signals

For each pass-0 decoded signal, the shim SHALL synthesise a continuous-phase FSK (CP-FSK)
waveform in PCM using the decoded tone sequence, the estimated carrier frequency, the reported
DT, and an amplitude derived from the SNR estimate. The waveform SHALL be synthesised as:
`sample[t] = A × cos(φ(t))` where `φ(t)` is the continuous phase accumulator advanced by
`2π × f_sym_hz / 12000` per sample and `f_sym_hz = f_carrier + tone[sym] × 6.25` Hz for each
1920-sample symbol window. Amplitude `A` SHALL be computed as `sqrt(2) × 10^(SNR/20) × noise_rms`
where `noise_rms` is derived from the measured `noise_floor_db` in the current cycle. The phase
accumulator SHALL be maintained in `double` precision and cast to `float` only at the sample
output step. The synthesised waveform SHALL be placed starting at sample index
`max(0, round(dt_s × 12000))` in the residual buffer.

#### Scenario: Synthesised waveform covers all 79 symbols

- **WHEN** the shim synthesises a waveform for a decoded signal with DT = 0.5 s
- **THEN** the synthesised waveform SHALL have exactly 79 × 1920 = 151 680 non-zero samples
  starting at sample 6000 (= 0.5 × 12000)

#### Scenario: Waveform synthesis uses continuous phase across symbol boundaries

- **WHEN** the shim synthesises two consecutive symbols with different tones
- **THEN** the phase at the start of the second symbol SHALL equal the accumulated phase at the
  end of the first symbol, with no discontinuity

---

### Requirement: PCM-domain in-place subtraction and waterfall rebuild

After synthesising waveforms for all pass-0 decoded signals, the shim SHALL subtract each
synthesised waveform from a working copy of the original PCM buffer (`pcm_residual`). The
original `const float* pcm` argument SHALL NOT be modified. After all subtractions are complete,
the shim SHALL free the existing `monitor_t` waterfall and rebuild it by running the full
`monitor_init()` and `monitor_process()` sequence on `pcm_residual`. Pass 1 (the PCM-residual
decode) SHALL use this rebuilt waterfall.

#### Scenario: Original PCM buffer is not modified

- **WHEN** `ft8_decode_all` processes a buffer containing at least one decoded signal
- **THEN** the original `pcm` argument SHALL be byte-identical before and after the call
  (verifiable by checksum over the 180 000 samples)

#### Scenario: Waterfall is rebuilt from residual before pass 1

- **WHEN** at least one signal is decoded in pass 0
- **THEN** the waterfall used by pass 1 SHALL reflect the PCM-subtracted residual, not the
  original PCM

#### Scenario: PCM subtraction step is skipped when pass 0 decodes nothing

- **WHEN** pass 0 decodes zero signals
- **THEN** the shim SHALL skip PCM synthesis, subtraction, and waterfall rebuild entirely and
  proceed directly to pass 1 using the original waterfall (no unnecessary allocations)

---

### Requirement: Three-pass decode structure with PCM-domain SIC as pass 1

`K_MAX_PASSES` SHALL be set to 3. Pass 0 is the full-waterfall decode (unchanged). Pass 1 is a
decode of the PCM-cleaned waterfall rebuilt from the residual PCM buffer after subtracting all
pass-0 decoded signals. Pass 2 is a spectrogram-domain suppression decode (unchanged from the
p15 pass 1, but now operating on top of the PCM-cleaned waterfall). All three passes participate
in the cross-pass deduplication hash table so no message is reported more than once.

#### Scenario: Pass 1 uses the PCM-residual waterfall

- **WHEN** pass 0 decodes at least one signal and the residual waterfall is rebuilt
- **THEN** `tls_pass_counts[1]` SHALL reflect new decodes found in the PCM-residual waterfall
  that were NOT in pass 0

#### Scenario: Pass 2 uses spectrogram suppression on the already-PCM-cleaned waterfall

- **WHEN** passes 0 and 1 complete
- **THEN** the spectrogram tile suppression for pass 2 SHALL operate on the waterfall already
  cleaned by PCM subtraction, compounding the two suppression approaches

#### Scenario: Three-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes all three passes and `ft8_get_last_pass_counts` is called
  with capacity 3
- **THEN** the function SHALL return 3 and `out_counts[0]`, `out_counts[1]`, `out_counts[2]`
  SHALL sum to the total number of unique messages returned by `ft8_decode_all`

---

### Requirement: Second-pass spectrogram-domain residual decode

After pass 0 decodes and PCM-domain subtraction completes (pass 1), the shim SHALL perform a
spectrogram-domain suppression pass (pass 2) on the PCM-residual waterfall. For each
successfully decoded candidate from passes 0 and 1, the shim SHALL suppress that signal's
energy in the waterfall by setting the exact decoded tone bin and its ±1 nearest neighbours to
the noise-floor median byte for each of the 79 FT8 symbols. The shim SHALL then re-run
`ftx_find_candidates` and `ftx_decode_candidate` on the modified waterfall and merge new results
with pass 0 and pass 1 results, deduplicating via the cross-pass message hash table. The total
number of passes SHALL equal `K_MAX_PASSES` (3).

#### Scenario: Pass 2 recovers a signal masked after PCM subtraction

- **WHEN** the shim processes a buffer containing at least two FT8 signals where the weaker
  signal was not decoded in passes 0 or 1
- **THEN** pass 2 spectrogram suppression SHALL decode the weaker signal and include it in the
  returned `FT8Result` array

#### Scenario: First- and second-pass results are not re-emitted in pass 2

- **WHEN** the same message is a detectable candidate in passes 0, 1, and 2
- **THEN** the shim SHALL emit that message exactly once in the result array

#### Scenario: Decode loop terminates after K_MAX_PASSES (3) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 3 passes regardless of how many
  signals remain

---

### Requirement: K_MAX_PASSES is a named constant, not a magic number

The maximum number of decode passes SHALL be defined as a named C preprocessor constant
`K_MAX_PASSES` in `ft8_shim.c` with a value of 3. No literal integer representing the pass
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
(non-duplicate) messages decoded in pass `i` (0-indexed) for all three passes. The return value
SHALL be 3 (the number of passes executed). The data SHALL be stored in thread-local storage.

#### Scenario: Per-pass counts reflect actual new decodes across three passes

- **WHEN** `ft8_decode_all` decodes N₀ messages in pass 0, N₁ new messages in pass 1, and N₂
  new messages in pass 2
- **THEN** `ft8_get_last_pass_counts` SHALL return 3 and populate `out_counts[0] = N₀`,
  `out_counts[1] = N₁`, `out_counts[2] = N₂`

#### Scenario: Per-pass counts are zero when no signals are present

- **WHEN** `ft8_decode_all` is called with a silent PCM buffer
- **THEN** `ft8_get_last_pass_counts` SHALL return 3 and all entries in `out_counts` SHALL be 0

---

### Requirement: C# decoder logs per-pass stats at Debug level

After each decode cycle, `Ft8Decoder` SHALL log one Debug-level message per pass of the form
`"Iterative subtraction: pass {n} of {max}, {k} new decodes"`, where `{n}` is the 1-based pass
number, `{max}` is 3, and `{k}` is the number of new messages decoded in that pass.

#### Scenario: Three per-pass log messages appear at Debug level

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle with an ILogger configured at
  Debug level
- **THEN** the log output SHALL contain 3 messages matching the pattern
  `"Iterative subtraction: pass N of 3, K new decodes"` for N = 1, 2, 3

---

## Acceptance Criteria

### AC-IS-1 — Recovery rate: PCM-domain SIC improvement target

**Baseline (p15 spectrogram-domain, `6bab388`):** 69.1% (613/887 matched overall); S7
co-channel scenarios: P0 (2-stack equal SNR) 0/6, P8 (time-freq co-freq dt 0.5 s) 0/6.

**fix-D001 target:** ≥ 1/6 improvement on both P0 and P8 vs the `6bab388` baseline (measured
by the R&R S7 scenario harness). An absolute number ≥ 1/6 indicates the PCM-domain SIC is
meaningfully closing the co-channel decode gap versus WSJT-X.

### AC-IS-2 — Fixture answer-key expansion

No new answer-key entries required for the three committed synthetic fixtures — the improvement
is expected on co-channel / overlapping signals which are not represented in the committed
fixtures. G6 gate: 3/3 passed with K_MAX_PASSES=3.

### AC-IS-3 — False-positive rate

False-positive rate must remain ≤ 6% (same threshold as p15).

### AC-IS-4 — Per-pass Debug logging

`Ft8Decoder.cs` emits exactly 3 Debug-level messages per cycle:
`"Iterative subtraction: pass 1 of 3, N new decodes"`,
`"Iterative subtraction: pass 2 of 3, M new decodes"`,
`"Iterative subtraction: pass 3 of 3, P new decodes"`.
Confirmed by test `PcmSicTests.DecodeAsync_MultiSignalFixture_LogsThreePassMessagesAtDebug`.

### AC-IS-5 — Timing budget

Three passes complete within ~2.2 s on development hardware (pass 0 ~700 ms + PCM synthesis
~5 ms + waterfall rebuild ~50 ms + pass 1 ~700 ms + spectrogram suppress ~5 ms + pass 2 ~700
ms). Well within the 13 s / 30 s CI budget.
