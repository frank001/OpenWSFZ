## 1. Dependencies

- [x] 1.1 Add `scipy>=1.13` to `qa/rr-study/requirements.txt`
- [x] 1.2 Verify `pip install -r qa/rr-study/requirements.txt` completes without error (scipy + numpy 2.x compatibility)

## 2. Replace Brickwall Filter in `channel.py`

- [x] 2.1 Remove `_lowpass_fft` and replace with `_lowpass_fir` using `scipy.signal.firwin` (Kaiser window, `numtaps=255`, `beta=6.0`) and `scipy.signal.fftconvolve(..., mode='same')`
- [x] 2.2 Update the `add_awgn` function to call `_lowpass_fir` in place of `_lowpass_fft` — no change to the public signature or `noise_cutoff_hz` parameter
- [x] 2.3 Update the module docstring in `channel.py` to describe the FIR filter (remove the "brick-wall FFT lowpass" description; document Kaiser parameters and transition band)
- [x] 2.4 Confirm `mix_to_shared_floor` requires no changes — it delegates to `add_awgn` and is unaffected

## 3. Add `verify_noise_psd` Utility

- [x] 3.1 Implement `verify_noise_psd(noise, cutoff_hz, sample_rate_hz, tolerance_db=1.0, assert_ok=False)` in `channel.py`
- [x] 3.2 Use `scipy.signal.welch` with `nperseg=4096` to estimate PSD; check passband flatness from 100 Hz to `cutoff_hz * 0.85`; check Gibbs suppression (PSD at cutoff ≥ 30 dB below passband mean)
- [x] 3.3 When `assert_ok=True`, raise `AssertionError` with a descriptive message citing which criterion failed and the measured deviation; return `True`/`False` otherwise

## 4. Update Tests

- [x] 4.1 Confirm all existing tests in `qa/rr-study/synth/tests/` pass with the new FIR path (in-band SNR tolerance ±0.5 dB must still hold)
- [x] 4.2 Add test: `test_fir_no_gibbs_ridge` — generates bandlimited noise with `noise_cutoff_hz=4000`, asserts PSD at 4000 Hz is ≥ 30 dB below passband mean
- [x] 4.3 Add test: `test_fir_passband_flat_4khz` — calls `verify_noise_psd` with `assert_ok=True` on FIR-filtered noise; asserts it returns `True`
- [x] 4.4 Add test: `test_fir_passband_flat_3khz` — same check for `noise_cutoff_hz=3000`
- [x] 4.5 Add test: `test_output_length_preserved` — asserts output of `add_awgn` with `noise_cutoff_hz` set has the same length as the input
- [x] 4.6 Add test: `test_snr_preserved_with_cutoff` — calls `add_noise` with `noise_cutoff_hz=4000`, measures `measure_inband_snr_db`; asserts within ±0.5 dB

## 5. Scan for Other Brickwall Noise Paths

- [x] 5.1 Search `qa/rr-study/synth/` for any other use of `_lowpass_fft` or direct FFT-bin-zeroing on noise vectors (single-signal paths S1/S2/S3/S5)
- [x] 5.2 If found, apply the same FIR replacement; if not found, record "no other brickwall paths" in the commit message
- [x] 5.3 Confirm `qa/rr-study/gen_decoder_fixtures.py` does not use a brickwall noise path (expected: unaffected)

## 6. Verification

- [x] 6.1 Run full synthesiser test suite: `pytest qa/rr-study/synth/tests/ -v` — all tests must pass
- [ ] 6.2 Visually confirm WSJT-X waterfall no longer shows a spectral ridge at 4 kHz by running a short S7 trial and screenshotting the result
