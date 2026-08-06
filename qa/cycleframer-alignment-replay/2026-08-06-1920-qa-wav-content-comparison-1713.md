# WAV content comparison — OpenWSFZ vs WSJT-X captures, `20260803_live_run_1713`

**Author:** QA, 2026-08-06 (19:20 UTC, `date -u`, per HK-017). Repo `main` at `f6c5b46`.
**Requested by:** the Captain, 2026-08-06 — "look at the actual contents of the captured
wav files and any differences between the files captured by openwsfz and wsjt-x. look at
volume, frequency, etc."
**Scope:** exploratory raw-audio characterisation only. **Not** Arm R.D (still not
authorised, not touched here) and not a VOID-gate execution — no `src/` change, no
capture run, no decode. NFR-021: reads WAV PCM only, never `ALL.TXT`, no message text or
callsigns anywhere in script, output, or this note.

---

## 1. What was done

Corpus: `artefacts/20260803_live_run_1713/` — chosen because it is the corpus the
Architect's R.D scouting already flagged as "one verified audio path" (8-pair spot check,
median |r| = 0.987, 2026-08-05) and explicitly asked to be re-checked wider. This note
does that re-check, plus adds frequency content, which nothing on record covered before.

Script: `qa/cycleframer-alignment-replay/_work/wav_content_compare_1713.py`. 60 filename-
matched WAV pairs, drawn by fixed seed spread across the **entire ~20 h session**
(prior spot-checks were 8 and 68 pairs respectively, both from single short windows).
Per pair: RMS/peak level (dBFS), clipped-sample count, FFT cross-correlation (best lag +
peak Pearson r, ±50 ms search), then — after aligning at that lag — a Welch PSD on each
side, averaged in **linear power** across all 60 pairs before conversion to dB (avoids
dB-averaging bias), reported per frequency band plus spectral centroid.

Raw output: `qa/cycleframer-alignment-replay/_work/wav_content_compare_1713/`
(`pairs.csv`, `psd_summary.csv`, `psd_plot.png`, `scatter_plot.png`).

## 2. Findings

**Level (volume).** Mean delta 0.03 dB, median 0.05 dB, stdev 0.27 dB (ours − WSJT-X).
RMS ratio 1.003 on average, range [0.871, 1.055] across all 60 pairs. One outlier at
elapsed hour ≈10 (`260804_032345`, both sides near −75 dBFS — an effectively silent
cycle, so the ratio is noise-dominated there, not a real level disagreement). No
clipping on either side, any pair. **No material volume difference.**

**Alignment.** Best-lag median 17.1 ms, range [−6.75, 37.75] ms — consistent with, and
marginally wider than, the Architect's ±34.1 ms spot check (expected: 60 pairs across
the full session vs. 8). Peak correlation median 0.990; only 1/60 pairs fell below 0.95
(0.9395, at elapsed hour ≈2.5). No drift trend in either lag or level across the ~20 h
span (see `scatter_plot.png`) — this reads as sub-cycle timing jitter, not a clock-rate
effect, matching the corpus's already-established drift-screen PASS.

**In-band frequency content (≈200–2800 Hz, where FT8 tones live): essentially
identical.** Band-power deltas are all ≤ 1.2 dB:

| band (Hz) | ours (dB) | wsjt-x (dB) | delta |
|---|---:|---:|---:|
| 0–300 | 18.19 | 18.53 | −0.34 |
| 300–600 | 28.09 | 28.16 | −0.06 |
| 600–1200 | 31.36 | 30.95 | +0.41 |
| 1200–1800 | 28.26 | 28.32 | −0.06 |
| 1800–2400 | 23.66 | 24.55 | −0.89 |
| 2400–3000 | 15.52 | 16.67 | −1.15 |

Spectral centroid delta: mean −34.9 Hz, stdev 24.8 Hz — small relative to the ~1–1.5 kHz
centroids themselves. **This corroborates the Architect's r=0.987 finding at 7.5× the
sample size and full session span: the two legs are capturing the same signal, at the
same gain, in the band that matters for decoding.**

**Out-of-band content (>3000 Hz, above where FT8 activity lives): a real and
substantial difference.**

| band (Hz) | ours (dB) | wsjt-x (dB) | delta |
|---|---:|---:|---:|
| 3000–4000 | −21.05 | −18.31 | −2.73 |
| 4000–5000 | −32.65 | −25.96 | −6.69 |
| 5000–6000 | −46.30 | −38.25 | −8.06 |
| ≥5500 (near-Nyquist) | −47.77 | −38.96 | −8.81 |

Visible in `psd_plot.png`: both legs roll off sharply at the same ~2800 Hz point (almost
certainly the transceiver's own SSB/audio-out filter, common to both — consistent with
the "one antenna, one radio, split feed" hardware fact already on record for this run),
but above that shared knee WSJT-X's captured audio retains a visibly higher, spurrier
floor — periodic bumps around 3.3, 4.0, and 4.3–4.5 kHz roughly 6–9 dB above ours,
climbing to ~9 dB by the Nyquist edge. Most plausible explanation: the two capture
chains resample differently downstream of the shared analogue signal (ours: explicit
`WdlResamplingSampleProvider`, 48 kHz → 12 kHz; WSJT-X's path is a different resampler
or driver-level SRC) with different anti-alias filter steepness. This was not visible in
either prior script, which only measured level and lag, never spectral shape.

## 3. What this does and does not answer

- **Confirms, at a much larger sample, that this corpus's "one verified audio path"
  claim holds**, and specifically that it holds **in the FT8-relevant passband**, which
  the prior 8-pair check did not break out separately from level/lag.
- **Does not explain the 29.9% decoder agreement anomaly** (open TODO,
  `project-state-2026-08-05-d001-reciprocal-asymmetry.md` §6). If anything it weakens
  the "one leg is looking at different audio" hypothesis for that gap, since the only
  measured difference sits well outside the passband either decoder would plausibly
  use. The remaining candidates for that gap are software-side (decode depth, passband
  *setting*, sync/candidate threshold) rather than the captured audio itself.
- **Does not touch Arm R.D, Measurement D, or any pre-registered gate.** No VOID
  condition was evaluated; this is not V3 and must not be cited as satisfying it — V3
  requires ≥20 pairs specifically over the decisive epoch with its own reporting
  obligations, which this note did not follow (this sample spans the whole session, not
  the decisive epoch, and was not run as part of Arm R.D's authorisation).
- The out-of-band spectral difference is a genuine capture-chain characteristic worth
  knowing about, but at −38 to −48 dBFS it sits ~50+ dB below the in-band signal region
  and above the frequency range either decoder decodes in — flagging it for the record,
  not raising it as a defect.

## 4. Cross-references

- `qa/cycleframer-alignment-replay/2026-08-05-1459-architect-to-qa-spec-reciprocal-density-asymmetry.md`
  §1 — the 8-pair spot check this widens.
- `qa/cycleframer-alignment-replay/_work/compare_raw_audio.py`,
  `compare_raw_audio_fft.py` — prior level/lag-only scripts (2026-07-25 corpus), whose
  method this one ports and extends with PSD.
- `qa/ARTEFACT_INVENTORY.md` — corpus row for `20260803_live_run_1713`.
