## Why

The R&R synthesiser's `channel.mix_to_shared_floor()` limits noise bandwidth via a frequency-domain brickwall (FFT bin zeroing), which causes a physically real Gibbs-phenomenon ridge at the cutoff frequency and a non-flat in-band noise PSD. Both artefacts degrade the fidelity of the synthesised audio as a model of a real SSB receiver, and the non-flat noise floor is a credible contributing factor to D-002 (SNR bias +2.43 dB).

## What Changes

- Replace the brickwall FFT zero-out in `channel.py` with a windowed FIR lowpass filter (Kaiser window) for all bandlimited noise generation paths.
- Add a PSD verification helper (`verify_noise_psd`) that asserts the generated noise is flat within ±1 dB across the passband — usable both as a diagnostic and as a lightweight regression guard.
- No change to the public interface of `mix_to_shared_floor()` or any other function; the `noise_cutoff_hz` parameter contract is preserved.
- No change to the product decoder (`src/OpenWSFZ.Ft8/`) or any non-synthesiser code.

## Capabilities

### New Capabilities

- `rr-synth-channel`: Requirements for the R&R synthesiser channel module — noise generation quality, bandlimiting filter type, and PSD flatness tolerance. This spec did not previously exist; the channel module's behaviour was undocumented at spec level.

### Modified Capabilities

*(none — no existing spec-level requirements change)*

## Impact

- `qa/rr-study/synth/channel.py` — primary implementation change
- `qa/rr-study/synth/` — scan for any other brickwall noise paths (e.g., single-signal paths in S1/S2/S3/S5 that use `np.fft` zero-out)
- `qa/rr-study/gen_decoder_fixtures.py` — review; likely unaffected (fixture noise does not use `noise_cutoff_hz`), but must be confirmed
- All R&R scenarios (S4, S7, S8) that pass `noise_cutoff_hz` to `mix_to_shared_floor()` will produce perceptibly different (more accurate) audio; a fresh R&R run is required after this fix
- D-002 (SNR bias) — this fix is a prerequisite investigation step; if the corrected noise floor reduces the bias, D-002 may be resolved or downgraded
