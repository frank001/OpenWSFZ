# `cycle-audio-archive` D-001 diagnostic: raw-audio cross-correlation check (tasks.md §9, addendum)

**Author:** QA, 2026-07-25 (21:45). Follow-on to `2026-07-25-2030-cycle-audio-archive-parity-result.md`
(§9.3/9.4), at the Captain's request to push the comparison one level deeper than decoded text.

> **Superseded 2026-07-26.** §2–§4 corrected by `2026-07-25-2300-alignment-root-cause.md`: the
> search window here was ±50 ms, 10× too narrow (true lags run to −504 ms); with it widened,
> 68/68 pairs lock (not 11/68), on invariant lag ≡ 76 (mod 120) — a 10 ms grid — not the mod-12
> reading below. Body retained as history; do not cite §2–§4 as current.

---

## 0. Why this check exists

Everything in the 20:30 report — and the entire `D001ParamSweep`/message-set comparison it's built
on — compares **decoded text**: does `Ft8Decoder` produce the same messages from our capture as from
WSJT-X's capture of the same RF? That answered "does the capture chain cost us decodes" (no, at this
scale). It does not answer a narrower, harder question: **is the audio our capture chain hands to the
decoder actually the same underlying signal WSJT-X recorded, sample for sample** — or could two
captures happen to decode similarly well while actually being different audio (independent noise
realizations that each separately clear the decode threshold on different content)? Decode-count
parity can't distinguish those two cases; only looking at the waveforms directly can.

## 1. Method

- Script: `qa/cycleframer-alignment-replay/_work/compare_raw_audio.py` (git-ignored `_work/`, no
  message text or callsigns touched at all — reads only `.wav` PCM, per NFR-021).
- Same 68 filename-matched cycles as the 20:30 report, from `artefacts/20260725_live_run_1806/`.
- Confirmed both arms' `.wav` headers are byte-identical in format first: 12000 Hz, mono, 16-bit,
  exactly 180 000 frames, on both `owsfz/wav/260725_180615.wav` and `wsjt-x/wav/260725_180615.wav`
  (spot-checked; holds for all 68 by the unmodified `CycleWavWriter`/WSJT-X contract).
- For each pair: RMS level (dBFS), clipped-sample count, and a full integer-lag search
  (±600 samples = ±50 ms at 12 kHz) for the normalized cross-correlation peak — i.e., does shifting
  one waveform against the other by some small number of samples make them line up, and how well.

## 2. Result: bimodal, and the "locked" cases are the interesting part

| | value |
|---|---|
| pairs compared | 68 |
| level delta (ours − WSJT-X), dB | mean +0.15, median +0.17, range [−0.55, +0.55], σ=0.23 |
| clipped samples, either side | 0 (all 68 pairs, both arms) |
| pairs with peak correlation > 0.9 | **11 / 68** |
| pairs with peak correlation < 0.5 | 57 / 68 |
| correlation values in between 0.5 and 0.9 | **none** — the distribution is cleanly bimodal |

The 11 "locked" pairs correlate at 0.95–0.99; every other pair sits at 0.03–0.42 with no crisp peak.
There is no middle ground, which is itself informative (see §3).

The 11 locked pairs, with the lag (in 12 kHz samples) at which the peak occurs:

| file | lag (samples) | lag (ms) | corr | lag mod 12 |
|---|---:|---:|---:|---:|
| 260725_180715 | −404 | −33.667 | 0.956 | **4** |
| 260725_180845 | −284 | −23.667 | 0.966 | **4** |
| 260725_181145 | −524 | −43.667 | 0.962 | **4** |
| 260725_181430 | −44 | −3.667 | 0.992 | **4** |
| 260725_181545 | −164 | −13.667 | 0.963 | **4** |
| 260725_181715 | −164 | −13.667 | 0.956 | **4** |
| 260725_181945 | −44 | −3.667 | 0.962 | **4** |
| 260725_182100 | +316 | +26.333 | 0.953 | **4** |
| 260725_182230 | −404 | −33.667 | 0.957 | **4** |
| 260725_182345 | −164 | −13.667 | 0.965 | **4** |
| 260725_182615 | −164 | −13.667 | 0.969 | **4** |

**All eleven, independently, land on a lag that is ≡ 4 (mod 12) samples — i.e. every one of them is
an integer number of whole milliseconds apart, plus the same fixed 4/12 ms (0.333 ms) fractional
residual.** The whole-millisecond part varies cycle to cycle (−43.667 ms up to +26.333 ms, no trend
with time-of-session); the fractional part does not vary at all across 11 independent measurements.

## 3. Interpretation

**This is strong, independent corroboration of the 20:30 parity verdict, at a level decode-count
comparison cannot reach.**

- A fixed sub-millisecond residual recurring across 11 separately-measured cycles, drawn from a
  ~21-minute span, is not plausible by chance for two genuinely independent noise sources — thermal/
  quantization noise from two unrelated ADCs would not produce a stable 0.333 ms alignment. The
  simplest explanation consistent with the data: both capture chains ultimately derive from the
  **same ADC clock domain** (the same physical USB Audio CODEC device, per the session README), and
  the whole-millisecond jitter that does vary is exactly what you'd expect from two independent
  WASAPI client buffer/scheduling boundaries layered on top of one shared clock — not from two
  differently-clocked devices drifting against each other. This directly rules out the more
  worrying alternative the capture-chain investigation needed to exclude: that `WasapiAudioSource`'s
  resampling path could be introducing a *growing* timing error. An accumulating clock-rate error
  would show up as lag trending with elapsed session time; it does not (compare 181430 at −3.667 ms
  against 182100, twenty minutes later, at +26.333 ms — no monotonic drift, just buffer-boundary
  scatter around a fixed sub-ms anchor).
- **The other 57 pairs are inconclusive by this method, not contradictory.** A full-bandwidth,
  whole-15-second time-domain cross-correlation is dominated by whichever component carries the most
  energy. FT8 signals routinely decode several dB under the audible noise floor — the decoder's
  processing gain comes from FFT/sync accumulation the raw waveform doesn't have. Most 15 s windows
  on a working band are noise-dominated in the time domain even when they contain several genuine,
  decodable FT8 signals, so a clean single-lag correlation peak only emerges when one signal happens
  to be strong enough to rise above the noise floor in raw amplitude terms too (a nearby/strong
  station). The clean bimodal split (nothing between 0.5 and 0.9) is consistent with exactly this:
  either a dominant tone exists and the correlation locks on hard, or it doesn't and the statistic is
  just measuring uncorrelated noise-floor structure. **It would take a frequency-domain approach
  (band-limited coherence, e.g. `scipy.signal.coherence` restricted to the ~200–2500 Hz FT8 passband)
  to get a comparably sharp answer on the other 57 — not attempted here, flagged as a possible further
  step if the Captain wants it, not started unilaterally.**
- Level match is tight and one-sided-consistent (mean +0.15 dB, ours slightly hotter, σ=0.23 dB,
  zero clipping either side across all 68) — no evidence of a gain-staging or attenuation difference
  between the two chains.

## 4. Consequences for `tasks.md`

This sharpens, and does not change, the §9.4 verdict: capture-chain parity confirmed, now on two
independent lines of evidence (decoded-message counts, and — for the subset of cycles strong enough
to test this way — raw-waveform alignment at a stable sub-millisecond offset with no session-length
drift). Recorded as an addendum; §9.5 (disposition of paused PR #108) is unaffected and remains open,
pending the Captain's decision.
