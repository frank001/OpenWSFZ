## ADDED Requirements

### Requirement: Reported SNR is correct for candidates whose sync position precedes the decode window

The FT8 decoder SHALL compute a decoded candidate's `signal_db` term (the numerator of
the SNR formula, `snr = signal_db - local_noise_db - 26.5`) by averaging only the
waterfall samples that correspond to the candidate's own 79-symbol re-encoding at the
correct symbol position, for every candidate regardless of whether its sync position
(`time_offset`) is non-negative or negative (i.e. the signal's true start precedes the
nominal 15-second decode window). Specifically, for absolute waterfall block `b`, the
symbol index used to select the expected tone SHALL be `b - time_offset` computed from
the candidate's true, **unclamped** `time_offset` — never from a value that has been
clamped to a non-negative floor before the subtraction. Blocks whose derived symbol
index would fall outside `[0, FT8_NN)` SHALL be excluded from both the sum and the count
(never re-anchored to a different, wrong symbol), matching `ft8_lib`'s own out-of-range
convention (`patched/ft8/decode.c:160,226`: `if (block_abs < 0) continue;`).

This requirement exists because a defect present through `FT8_SHIM_VERSION 20260045`
computed the symbol index from the **clamped** `time_offset` (floored to zero before the
block-to-symbol subtraction) while still iterating a full 79-block range, causing every
sample for a `time_offset < 0` candidate to be read from the wrong tone bin — a silent,
total corruption (not a partial-data effect) that under-reported SNR by roughly 15–20 dB.
Confirmed mechanically: `qa/rr-study/2026-08-22-1454-qa-to-architect-b-dt-c3-results.md`
(arm B-dt-C3) measured a 17.4 dB step in reported SNR co-located exactly with the block
at which `time_offset` turns negative, against a "signal partly outside the window"
alternative explanation that could account for at most 0.083 dB at that point.

#### Scenario: SNR does not collapse for a signal arriving before the nominal slot boundary

- **WHEN** the B-dt-C3 offline sweep (`qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py`) is run against a build under test, sweeping `true_dt` from `+0.08 s` to `−1.20 s` on the decoder's own 0.08 s sub-block lattice
- **THEN** the maximum per-step drop in mean reported SNR across adjacent parts (`Δ(p)`, as defined by the harness) SHALL be less than **8.0 dB** at every step, and mean reported SNR SHALL NOT differ by more than a few dB between the most-negative and least-negative parts of the sweep that both produce at least 3 matched decodes out of 5 trials

#### Scenario: A candidate with a negative sync position derives its symbol index from the true offset, not a clamped one

- **WHEN** `ft8_decode_all` computes `signal_db` for a candidate whose `time_offset < 0`
- **THEN** the symbol index used for waterfall block `b` SHALL be `b - time_offset` using the true (unclamped) `time_offset` value, so that the averaged samples correspond to the candidate's actual re-encoded tones, not tones offset by `|time_offset|` positions

#### Scenario: The averaged sample count is thinned, not corrupted, for early-arriving signals

- **WHEN** a candidate's `time_offset < 0` places some of its 79 symbols before the start of the retained waterfall
- **THEN** the count of samples contributing to `signal_db` (`cnt`) SHALL be less than 79 by exactly the number of blocks that fall outside the retained waterfall, and none of the remaining samples SHALL be drawn from the wrong tone bin as a result

#### Scenario: Existing real-decode replays are unaffected (regression)

- **WHEN** any of the eight committed AC-N1 replay corpora (`qa/rr-study/r2-coherent-llr-instrument/results/replay_*.json`, every recorded decode having `time_offset >= 0`) is replayed against a build under test
- **THEN** the decode results (message set, frequency, DT, and SNR for every decode) SHALL be bit-identical to the committed pre-fix replay, since this requirement only changes behaviour on the `time_offset < 0` branch
