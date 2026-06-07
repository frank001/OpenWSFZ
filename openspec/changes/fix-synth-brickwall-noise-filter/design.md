## Context

The R&R synthesiser's `channel.py` contains `_lowpass_fft()` — a rectangular (brickwall) frequency-domain filter applied to the AWGN noise vector before it is mixed with FT8 signals. The function works by zero-ing all `rfft` bins above `cutoff_hz` and then calling `irfft`.

A brickwall FFT lowpass has two well-known physical defects:

1. **Gibbs phenomenon** — the step discontinuity in the frequency domain is equivalent to convolving the ideal response with a sinc in the time domain; the sinc's first overshoot (~9% amplitude, ~0.8 dB power) creates a real spectral ridge exactly at the cutoff frequency. This ridge is visible in WSJT-X's spectrum analyser and constitutes spurious energy that was not in the original white noise.

2. **Non-flat in-band PSD** — because the noise is generated as time-domain white noise (Gaussian samples) and *then* FFT-filtered, the signal's autocorrelation at the filter boundary creates a non-flat spectral envelope inside the passband. The WSJT-X spectrum trace shows a rising slope from 0 → 4 kHz rather than the flat profile expected from properly bandlimited white noise. This non-flat noise floor biases SNR estimates and is a credible contributor to D-002 (+2.43 dB).

## Goals / Non-Goals

**Goals:**
- Replace `_lowpass_fft` with a windowed FIR lowpass that produces a flat in-band PSD (≤ ±1 dB ripple across the passband)
- Eliminate the Gibbs spectral ridge at the cutoff frequency
- Preserve the existing `noise_cutoff_hz` public API and in-band SNR contract
- Add a `verify_noise_psd` diagnostic helper for use in tests and future regressions
- Add `scipy` as an explicit dependency (required for `scipy.signal.firwin`)

**Non-Goals:**
- Modifying the product decoder (`src/OpenWSFZ.Ft8/`)
- Fixing D-001 (co-channel gap) or D-002 directly — this change may narrow D-002's bias; that will be confirmed by a fresh R&R run
- Changing the SNR calibration maths (the `noise_sigma_for_snr` formula is correct)
- Altering any scenario file, truth CSV format, or analysis script

## Decisions

### Decision 1 — Windowed FIR with Kaiser window via `scipy.signal.firwin`

**Chosen:** `scipy.signal.firwin(numtaps, cutoff, window=('kaiser', beta), fs=sample_rate_hz)`.

**Why Kaiser over Hann/Hamming:** The Kaiser window's `beta` parameter allows the transition width and stopband attenuation to be traded off independently — ideal here because we want a fixed ±500 Hz transition band without caring too much about stopband depth. A beta of 6.0 gives ~60 dB stopband attenuation and a well-controlled transition band with minimal passband ripple.

**Why not numpy-only FIR:** The `firwin` function in scipy is a single well-tested line and handles edge cases (even/odd tap count, normalisation). Reimplementing it in pure numpy would be correct but adds maintenance burden for zero gain.

**Why not `lfilter` (causal IIR):** IIR filters introduce group delay variation (phase distortion) and can ring on the noise. FIR is linear-phase and has no ringing within the passband. For a noise signal the phase doesn't matter acoustically, but a flat group delay means the resulting noise has the correct statistical properties (circular autocorrelation).

**Why not just use `np.fft.rfft` with a Hann-windowed transition:** The brickwall zero-out was the problem; applying a smooth taper to the FFT bins is effectively a windowed filter but computed inefficiently and without the precision of `firwin`'s optimal tap calculation.

**Filter parameters:**
- `numtaps = 255` — gives a transition band of ~94 Hz at 48 kHz, more than adequate; odd count ensures linear phase. (At 48 kHz a 15 ms FT8 symbol is 720 samples; 255 taps is a small fraction of the ~720,000-sample slot.)
- `cutoff = noise_cutoff_hz` — `firwin` places the −6 dB point here; passband is flat to within ±0.5 dB well inside the cutoff.
- `window = ('kaiser', 6.0)` — beta=6.0 → ~60 dB stopband attenuation.
- `fs = sample_rate_hz` — passed explicitly so `firwin` works in Hz directly.

**Convolution:** applied with `scipy.signal.fftconvolve(noise, taps, mode='same')` rather than `lfilter` to avoid transient effects at the signal boundaries.

### Decision 2 — `verify_noise_psd` as a module-level utility, not a test-only helper

**Chosen:** Expose `verify_noise_psd(noise, cutoff_hz, sample_rate_hz, tolerance_db=1.0)` as a public function in `channel.py` (returns `bool`; raises `AssertionError` with a diagnostic message if the check fails when called with `assert_ok=True`).

**Why public:** The function is useful both in the synthesiser tests (regression guard) and as a manual diagnostic during R&R runs. Making it private (`_verify_noise_psd`) would discourage its use as a diagnostic instrument.

**PSD estimation:** Welch's method via `scipy.signal.welch` with `nperseg=4096` — gives ~12 Hz frequency resolution, easily resolving any passband ripple.

**Flatness check:** Mean PSD in dB from 100 Hz to `cutoff_hz * 0.85` must be within `tolerance_db` of the overall mean in that band. The 100 Hz lower bound avoids any DC offset artefacts; the 0.85× upper bound gives clearance before the transition band begins.

### Decision 3 — Add `scipy` to `qa/rr-study/requirements.txt`

**Chosen:** Add `scipy>=1.13` (released 2024; numpy 2.x compatibility confirmed).

**Why not constrain tightly:** scipy's signal processing API has been stable for many major versions. A `>=1.13` lower bound is sufficient.

## Risks / Trade-offs

- **[Risk] Determinism broken by `fftconvolve` numerical precision** — The noise vector is seeded; the FIR convolution is a deterministic linear operation on that vector. The output will be bit-for-bit reproducible across runs on the same platform. Cross-platform (e.g., Windows vs Linux) float64 maths may differ at the last ULP. → *Mitigation:* The synthesiser was never cross-platform-deterministic; this does not regress. Tests assert magnitude properties, not exact bit patterns.
- **[Risk] Slightly different noise power after FIR filtering** — The FIR transition band reduces total out-of-band power, which is the intended effect. The *in-band* power (2500 Hz reference) is preserved by the existing `noise_sigma_for_snr` calibration. → *Mitigation:* `measure_inband_snr_db` verifies this; the existing channel tests will catch any in-band power change.
- **[Risk] Fresh R&R run required** — All historical runs were produced with the brickwall filter. After this fix the noise profile changes; historical results and the new baseline cannot be directly compared. → *Mitigation:* This is expected and documented. A fresh run is a planned step after the fix.
- **[Risk] scipy install not available in CI or user environment** — scipy is not in the current requirements.txt. → *Mitigation:* Adding `scipy>=1.13` to `requirements.txt` and ensuring the CI step (`pip install -r requirements.txt`) covers it.

## Migration Plan

1. Update `qa/rr-study/requirements.txt` — add `scipy>=1.13`.
2. Replace `_lowpass_fft` with `_lowpass_fir` in `channel.py`; add `verify_noise_psd`.
3. Update the module docstring to describe the new filter.
4. Run existing channel tests — all should pass (in-band SNR contract unchanged).
5. Add new tests asserting PSD flatness and absence of the Gibbs ridge.
6. Conduct a fresh full R&R run; record as the new baseline.
7. Compare new SNR bias against D-002's +2.43 dB threshold; update or close #8 accordingly.

No rollback strategy is needed — this is a QA tool change only. The product binary is unaffected.

## Open Questions

- **D-002 resolution threshold:** If the fresh R&R run shows SNR bias reduced to within ±2.0 dB, D-002 can be closed. If bias persists, further investigation (PCM conditioning in `Ft8Decoder.cs`) is warranted. This question is answered by running the study, not by this design.
