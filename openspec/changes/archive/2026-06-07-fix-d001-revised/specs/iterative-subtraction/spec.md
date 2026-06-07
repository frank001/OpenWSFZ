## MODIFIED Requirements

### Requirement: Two-pass decode structure with spectrogram-domain suppression

`K_MAX_PASSES` SHALL be set to **2**. Pass 0 is the full-waterfall decode (unchanged). Pass 1 is a
spectrogram-domain suppression decode: for each decoded candidate from pass 0, the shim suppresses
that signal's energy in the waterfall by scaling the exact decoded tone bin and its ±1 nearest
neighbours for each of the 79 FT8 symbols by a per-signal SNR-scaled attenuation factor, then
re-runs `ftx_find_candidates` and `ftx_decode_candidate` on the modified waterfall. Both passes
participate in the cross-pass deduplication hash table so no message is reported more than once.

The attenuation factor for a signal with decoded SNR `snr_db` SHALL be computed as:

```
norm   = clamp((snr_db − K_SOFT_SUPP_SNR_MIN_DB) / (K_SOFT_SUPP_SNR_MAX_DB − K_SOFT_SUPP_SNR_MIN_DB), 0.0, 1.0)
factor = 1.0 − norm
```

Where:
- `K_SOFT_SUPP_SNR_MIN_DB` SHALL be **−5.0** (signals at or below this SNR are not suppressed; factor = 1.0).
- `K_SOFT_SUPP_SNR_MAX_DB` SHALL be **+15.0** (signals at or above this SNR are fully suppressed; factor = 0.0).
- Both constants SHALL be named C preprocessor constants in `ft8_shim.c`, not inline literals.

Tile attenuation is applied as a multiplicative scale: `tile_value *= factor`. A factor of 0.0 is equivalent to the previous hard-zero behaviour. A factor of 1.0 leaves the tile unchanged (no suppression).

#### Scenario: Pass 1 uses the SNR-attenuated waterfall

- **WHEN** pass 0 decodes at least one signal with SNR ≥ K_SOFT_SUPP_SNR_MAX_DB (+15 dB)
- **THEN** the waterfall used by pass 1 SHALL have that signal's tile energy zeroed (attenuation factor = 0.0) before candidate search begins

#### Scenario: Weak-signal tiles are partially preserved

- **WHEN** pass 0 decodes a signal with SNR = K_SOFT_SUPP_SNR_MIN_DB (−5 dB) exactly
- **THEN** the waterfall tiles for that signal SHALL be unchanged (attenuation factor = 1.0) — no suppression applied

#### Scenario: Mid-range SNR yields partial attenuation

- **WHEN** pass 0 decodes a signal with SNR = +5 dB (midpoint of the [−5, +15] range)
- **THEN** the attenuation factor SHALL be 0.5 ± floating-point rounding, and the tile values SHALL be halved

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

### Requirement: K_MAX_PASSES and soft-suppression constants are named constants, not magic numbers

The maximum number of decode passes SHALL be defined as `K_MAX_PASSES = 2`. The soft-suppression
SNR bounds SHALL be defined as `K_SOFT_SUPP_SNR_MIN_DB = −5.0f` and
`K_SOFT_SUPP_SNR_MAX_DB = +15.0f`. No literal integer representing the pass count and no literal
float representing the SNR bounds SHALL appear in the loop-control or attenuation logic.

#### Scenario: Named constants are used for loop termination and attenuation

- **WHEN** the source of `ft8_shim.c` is inspected
- **THEN** the decode iteration loop SHALL reference `K_MAX_PASSES` as its upper bound, and
  the attenuation computation SHALL reference `K_SOFT_SUPP_SNR_MIN_DB` and
  `K_SOFT_SUPP_SNR_MAX_DB`, with no bare literals in either location

---

## ADDED Requirements

### Requirement: Option C approval gate — PoC SHALL demonstrate improvement before PCM-domain SIC implementation proceeds

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

### Requirement: Any PCM residual buffer SHALL use heap allocation, not stack allocation

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
