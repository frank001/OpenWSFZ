## ADDED Requirements

### Requirement: Second-pass spectrogram-domain residual decode

After the first decode pass completes, the shim SHALL perform a second decode pass on the residual waterfall. For each successfully decoded candidate from the first pass, the shim SHALL suppress that signal's energy in `ftx_waterfall_t.mag` by setting all waterfall tiles covering the signal's 79-symbol window and all 8 FT8 tone bins (across all time and frequency over-sampling sub-bins) to the noise-floor median raw byte. The shim SHALL then re-run `ftx_find_candidates` and `ftx_decode_candidate` on the modified waterfall and merge new results with first-pass results, deduplicating via the existing message hash table. The total number of passes SHALL not exceed the named constant `K_MAX_PASSES` (default value: 2).

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
