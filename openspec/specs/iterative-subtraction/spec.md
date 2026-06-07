# iterative-subtraction Specification

## Purpose
Specifies the multi-pass iterative decode capability introduced in p15 (spectrogram-domain
suppression, 2 passes). After the first decode pass, decoded signals have their waterfall tiles
zeroed; a second pass operates on the suppressed waterfall to recover weaker co-channel signals.
This capability is implemented in the native `ft8_shim.c` and exposed to managed code via the
`ft8lib-interop` layer.

## Requirements

### Requirement: Two-pass decode structure with spectrogram-domain suppression

`K_MAX_PASSES` SHALL be set to **2**. Pass 0 is the full-waterfall decode (unchanged). Pass 1 is a
spectrogram-domain suppression decode: for each decoded candidate from pass 0, the shim suppresses
that signal's energy in the waterfall by zeroing the exact decoded tone bin and its ±1 nearest
neighbours for each of the 79 FT8 symbols, then re-runs `ftx_find_candidates` and
`ftx_decode_candidate` on the modified waterfall. Both passes participate in the cross-pass
deduplication hash table so no message is reported more than once.

#### Scenario: Pass 1 uses the spectrogram-suppressed waterfall

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL have the tile energy of all pass-0 decoded signals
  zeroed before candidate search begins

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

## Acceptance Criteria

### AC-IS-1 — Recovery rate: co-channel improvement target

**Status: NOT MET — PCM-domain SIC reverted.**

The fix-D001 implementation was validated against the R&R study (synthetic S7 scenario +
185-file real-signal baseline, 2026-06-07):

- Synthetic S7: 46.24% both baseline and fix — no change.
- Real-signal: 54.7% (fix) vs 54.8% (baseline), delta −0.1 pp.

The ≥ 1/6 improvement target on P0 and P8 was not achieved. Two fatal `0xC0000005` crashes
also occurred in production during the fix-D001 period. The PCM-domain SIC implementation was
reverted (`revert-fix-d001-pcm-sic`); **D-001 remains Open** as a future research item.
A different approach will be required to close D-001 and make progress toward NFR-018.

**Baseline (p15 spectrogram-domain, `6bab388`):** 69.1% (613/887 matched overall); S7
co-channel scenarios: P0 (2-stack equal SNR) 0/6, P8 (time-freq co-freq dt 0.5 s) 0/6.

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
