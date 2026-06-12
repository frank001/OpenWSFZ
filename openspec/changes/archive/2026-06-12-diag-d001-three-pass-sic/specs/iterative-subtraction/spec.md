## MODIFIED Requirements

### Requirement: Two-pass decode structure with spectrogram-domain suppression

`K_MAX_PASSES` SHALL be set to **3**. Pass 0 is the full-waterfall decode (unchanged). Pass 1
is a spectrogram-domain suppression decode: for each decoded candidate from pass 0, the shim
attenuates that signal's energy in the waterfall using a soft SNR-scaled factor for the exact
decoded tone bin and its ±1 nearest neighbours for each of the 79 FT8 symbols, then re-runs
`ftx_find_candidates` and `ftx_decode_candidate` on the modified waterfall. Pass 2 repeats the
same suppression-and-decode step, additionally suppressing the signals decoded in pass 1 before
re-running candidate search. All three passes participate in the cross-pass deduplication hash
table so no message is reported more than once.

#### Scenario: Pass 1 uses the spectrogram-suppressed waterfall

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL have the tile energy of all pass-0 decoded signals
  attenuated (or zeroed, for strong signals) before candidate search begins

#### Scenario: Pass 2 uses the doubly-suppressed waterfall

- **WHEN** pass 1 decodes at least one new signal not already decoded in pass 0
- **THEN** the waterfall used by pass 2 SHALL have the tile energy of all pass-0 and pass-1
  decoded signals attenuated before candidate search begins

#### Scenario: Three-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes all three passes and `ft8_get_last_pass_counts` is called
  with capacity 3
- **THEN** the function SHALL return 3 and `out_counts[0]` + `out_counts[1]` + `out_counts[2]`
  SHALL equal the total number of unique messages returned by `ft8_decode_all`

#### Scenario: Decode loop terminates after K_MAX_PASSES (3) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 3 passes regardless of how many signals
  remain

---

### Requirement: K_MAX_PASSES is a named constant, not a magic number

The maximum number of decode passes SHALL be defined as a named C preprocessor constant
`K_MAX_PASSES` in `ft8_shim.c` with a value of **3**. No literal integer representing the pass
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
SHALL be **3** (the number of passes executed). The data SHALL be stored in thread-local storage.

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
number, `{max}` is **3**, and `{k}` is the number of new messages decoded in that pass. The
implementation SHALL use a loop over `passCounts.Length` rather than hard-coded per-pass
statements, so the log output scales correctly with `K_MAX_PASSES` without further code changes.

#### Scenario: Three per-pass log messages appear at Debug level

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle with an ILogger configured at
  Debug level
- **THEN** the log output SHALL contain **3** messages matching the pattern
  `"Iterative subtraction: pass N of 3, K new decodes"` for N = 1, 2, 3
