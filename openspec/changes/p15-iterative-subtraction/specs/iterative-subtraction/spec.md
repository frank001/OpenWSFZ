## ADDED Requirements

### Requirement: Second-pass spectrogram-domain residual decode

After the first decode pass completes, the shim SHALL perform a second decode pass on the residual waterfall. For each successfully decoded candidate from the first pass, the shim SHALL suppress that signal's energy in `ftx_waterfall_t.mag` by setting the exact decoded tone bin and its ±1 nearest neighbours (to cancel Hann-window first sidelobes), as determined from `ft8_encode()`, to the noise-floor median raw byte for each of the 79 FT8 symbols across all time and frequency over-sampling sub-bins. The shim SHALL then re-run `ftx_find_candidates` and `ftx_decode_candidate` on the modified waterfall and merge new results with first-pass results, deduplicating via the existing message hash table. The total number of passes SHALL not exceed the named constant `K_MAX_PASSES` (default value: 2).

#### Scenario: Second pass recovers a signal masked by a stronger co-channel transmission

- **WHEN** the shim processes a 15-second PCM buffer containing at least two FT8 signals on nearby frequencies where the weaker signal was not decoded in the first pass
- **THEN** the second pass SHALL decode the weaker signal and include it in the returned `FT8Result` array

#### Scenario: First-pass results are not re-emitted in the second pass

- **WHEN** the same message is a detectable candidate in both the first and second passes
- **THEN** the shim SHALL emit that message exactly once in the result array (deduplication across passes is enforced)

#### Scenario: Decode loop terminates after K_MAX_PASSES iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly `K_MAX_PASSES` passes regardless of how many signals remain in the residual waterfall

---

### Requirement: K_MAX_PASSES is a named constant, not a magic number

The maximum number of decode passes SHALL be defined as a named C preprocessor constant `K_MAX_PASSES` in `ft8_shim.c`. No literal integer representing the pass count SHALL appear in the loop-control logic.

#### Scenario: Named constant is used for loop termination

- **WHEN** the source of `ft8_shim.c` is inspected
- **THEN** the decode iteration loop SHALL reference `K_MAX_PASSES` as its upper bound, not a bare integer literal

---

### Requirement: Per-pass decode counts are queryable after each call

After `ft8_decode_all` returns, the calling thread SHALL be able to query the number of new decoded messages produced by each individual pass via `ft8_get_last_pass_counts(int* out_counts, int capacity)`. This function SHALL populate `out_counts[i]` with the count of new (non-duplicate) messages decoded in pass `i` (0-indexed). The return value SHALL be the number of passes actually executed (≤ `capacity` and ≤ `K_MAX_PASSES`). The data SHALL be stored in thread-local storage so that concurrent calls on different threads do not interfere.

#### Scenario: Per-pass counts reflect actual new decodes per pass

- **WHEN** `ft8_decode_all` decodes N₁ messages in pass 1 and N₂ new messages in pass 2
- **THEN** `ft8_get_last_pass_counts` SHALL return 2 and populate `out_counts[0] = N₁`, `out_counts[1] = N₂`

#### Scenario: Per-pass counts are zero when no signals are present

- **WHEN** `ft8_decode_all` is called with a silent PCM buffer
- **THEN** `ft8_get_last_pass_counts` SHALL return `K_MAX_PASSES` and all entries in `out_counts` SHALL be 0

---

### Requirement: C# decoder logs per-pass stats at Debug level

After each decode cycle, `Ft8Decoder` SHALL log one Debug-level message per pass of the form `"Iterative subtraction: pass {n} of {max}, {k} new decodes"`, where `{n}` is the 1-based pass number, `{max}` is the total pass count, and `{k}` is the number of new messages decoded in that pass.

#### Scenario: Per-pass log messages appear at Debug level

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle with an ILogger configured at Debug level
- **THEN** the log output SHALL contain `K_MAX_PASSES` messages matching the pattern `"Iterative subtraction: pass N of {max}, K new decodes"` for N = 1 … K_MAX_PASSES

---

## Acceptance Criteria

### AC-IS-1 — Recovery rate: spectrogram-domain ceiling

**Post-p15 measured result:** 69.1% (613/887 matched), up from 66.6% (591/887) baseline.

The spectrogram-domain ±1-bin suppression approach achieves **69.1%** against the 42-cycle WSJT-X corpus. This is the measurable ceiling of the approach: FFT waterfall frequency resolution is ±3.125 Hz/bin (6.25 Hz FT8 tone spacing with `freq_osr=2`), and Hann-window sidelobe leakage across bins ±2 to ±5 cannot be removed without coherent PCM-domain cancellation. Extensive parametric tuning confirmed no further gain is achievable within the spectrogram domain (see `design.md §Decision 6`).

**The ≥80% target from the original proposal is a PCM-domain target**, not a spectrogram-domain target. It is deferred to `p16-pcm-iterative-subtraction`, which will implement sub-Hz carrier-frequency estimation and CP-FSK waveform synthesis for full STFT sidelobe cancellation.

**This criterion is met** for the spectrogram-domain implementation: the implementation delivers the maximum recovery achievable with the chosen approach, and the architectural reason for the gap to 80% is fully documented and understood. Captain's decision recorded 2026-05-31: Option A accepted.

### AC-IS-2 — Fixture answer-key expansion

Answer-key subsets for the three committed fixture WAVs were inspected for new medium-SNR signals recoverable via the second pass. No new signals were found in these specific cycles (iterative-subtraction gains were distributed across other cycles in the corpus, not the committed fixtures). G6 gate: 3/3 passed.

### AC-IS-3 — False-positive rate

False-positive rate: **3.8%** (24/637 total decodes). Well within the ≤6% threshold.

### AC-IS-4 — Per-pass Debug logging

`Ft8Decoder.cs` emits two Debug-level messages per cycle: `"Iterative subtraction: pass 1 of 2, N new decodes"` and `"Iterative subtraction: pass 2 of 2, M new decodes"`. Confirmed via task 7.3.

### AC-IS-5 — Timing budget

Both passes complete in ~2 s combined on development hardware. Well within the 13 s / 30 s CI budget.
