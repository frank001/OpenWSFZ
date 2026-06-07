## REMOVED Requirements

### Requirement: PCM-domain carrier frequency estimation for decoded signals
**Reason**: PCM-domain SIC reverted — R&R study showed no measurable improvement (−0.1 pp) and the implementation produced two fatal 0xC0000005 crashes in production. D-001 remains Open as a future research item.
**Migration**: No managed-side consumer of carrier estimation exists; no migration needed.

### Requirement: CP-FSK waveform synthesis for decoded signals
**Reason**: PCM-domain SIC reverted. See above.
**Migration**: None.

### Requirement: PCM-domain in-place subtraction and waterfall rebuild
**Reason**: PCM-domain SIC reverted. See above.
**Migration**: None.

---

## MODIFIED Requirements

### Requirement: Three-pass decode structure with PCM-domain SIC as pass 1

`K_MAX_PASSES` SHALL be set to **2**. Pass 0 is the full-waterfall decode (unchanged). Pass 1 is a spectrogram-domain suppression decode: for each decoded candidate from pass 0, the shim suppresses that signal's energy in the waterfall by zeroing the exact decoded tone bin and its ±1 nearest neighbours for each of the 79 FT8 symbols, then re-runs `ftx_find_candidates` and `ftx_decode_candidate` on the modified waterfall. Both passes participate in the cross-pass deduplication hash table so no message is reported more than once.

#### Scenario: Pass 1 uses the spectrogram-suppressed waterfall

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL have the tile energy of all pass-0 decoded signals zeroed before candidate search begins

#### Scenario: Two-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes both passes and `ft8_get_last_pass_counts` is called with capacity 2
- **THEN** the function SHALL return 2 and `out_counts[0]` + `out_counts[1]` SHALL equal the total number of unique messages returned by `ft8_decode_all`

#### Scenario: Decode loop terminates after K_MAX_PASSES (2) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 2 passes regardless of how many signals remain

---

### Requirement: Per-pass decode counts are queryable after each call

After `ft8_decode_all` returns, the calling thread SHALL be able to query the number of new decoded messages produced by each individual pass via `ft8_get_last_pass_counts(int* out_counts, int capacity)`. This function SHALL populate `out_counts[i]` with the count of new (non-duplicate) messages decoded in pass `i` (0-indexed) for both passes. The return value SHALL be **2** (the number of passes executed). The data SHALL be stored in thread-local storage.

#### Scenario: Per-pass counts reflect actual new decodes across two passes

- **WHEN** `ft8_decode_all` decodes N₀ messages in pass 0 and N₁ new messages in pass 1
- **THEN** `ft8_get_last_pass_counts` SHALL return 2 and populate `out_counts[0] = N₀`, `out_counts[1] = N₁`

#### Scenario: Per-pass counts are zero when no signals are present

- **WHEN** `ft8_decode_all` is called with a silent PCM buffer
- **THEN** `ft8_get_last_pass_counts` SHALL return 2 and all entries in `out_counts` SHALL be 0

---

### Requirement: C# decoder logs per-pass stats at Debug level

After each decode cycle, `Ft8Decoder` SHALL log one Debug-level message per pass of the form `"Iterative subtraction: pass {n} of {max}, {k} new decodes"`, where `{n}` is the 1-based pass number, `{max}` is **2**, and `{k}` is the number of new messages decoded in that pass.

#### Scenario: Two per-pass log messages appear at Debug level

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle with an ILogger configured at Debug level
- **THEN** the log output SHALL contain **2** messages matching the pattern `"Iterative subtraction: pass N of 2, K new decodes"` for N = 1, 2

---

## MODIFIED Acceptance Criteria

### AC-IS-1 — Recovery rate: PCM-domain SIC improvement target

**Status: NOT MET — SIC reverted.**

The fix-D001 implementation was validated against the R&R study (synthetic S7 scenario + 185-file real-signal baseline, 2026-06-07). Results:

- Synthetic S7: 46.24% both baseline and fix — no change.
- Real-signal: 54.7% (fix) vs 54.8% (baseline), delta −0.1 pp.

The ≥ 1/6 improvement target on P0 and P8 was not achieved. Two fatal `0xC0000005` crashes also occurred in production during the fix-D001 period. The SIC implementation has been reverted; **D-001 remains Open** as a future research item. A different approach (e.g., improved candidate search, alternative interference cancellation strategy) will be required to close D-001 and make progress toward NFR-018.
