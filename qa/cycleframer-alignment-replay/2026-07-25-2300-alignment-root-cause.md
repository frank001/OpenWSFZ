# D-001: cycle-window alignment — root cause, and correction to the 21:45 cross-correlation note

**Author:** Architect, 2026-07-25 (23:00). Supersedes the analysis in
`2026-07-25-2145-raw-audio-crosscorrelation-check.md` §2–§4. The 20:30 parity result
(`2026-07-25-2030-cycle-audio-archive-parity-result.md`) is **unaffected and strengthened**.

Reproduce with:
- `qa/cycleframer-alignment-replay/measure_capture_alignment.py` (waveform, full-range FFT)
- `qa/cycleframer-alignment-replay/measure_dt_alignment.py` (decoder DT, 2×2 design)

Both read `artefacts/20260725_live_run_1806/`. Per NFR-021 neither retains or prints message
text or callsigns; the DT script parses only the numeric DT column and emits aggregates.

---

## 1. Headline

Three findings, in descending order of consequence:

1. **Our `Ft8Decoder` reports DT with a systematic +0.735 s offset** relative to WSJT-X's
   decoder **on byte-identical audio**. This is a decoder-side defect, not a capture defect.
2. **Our capture window is the *more* stable of the two** — per-cycle alignment σ = 59 ms
   versus WSJT-X's 208 ms. WSJT-X's saved-WAV window sawtooths over ±500 ms; ours does not
   drift. This is positive evidence that **there is no cycle-boundary clock drift in
   `CycleFramer` to fix**, which bears directly on §9.5 / PR #108.
3. The 21:45 note's central claim — that 57 of 68 pairs were "inconclusive" because FT8 sits
   below the noise floor — **was an artefact of a truncated search window**. With the search
   widened, **68/68 pairs correlate at 0.933–0.992**. Capture-chain parity is confirmed far
   more strongly than the note claimed.

## 2. What was wrong with the 21:45 note

The method was sound in the one way I first suspected it might not be: `best_lag_correlation`
genuinely evaluates every integer lag, so the modular structure it found was real, not a
search-grid artefact. The problems were elsewhere.

**2.1 The search window was too narrow, and the note read the truncation as a result.**
`MAX_LAG_SAMPLES = 600` (±50 ms). The true lags run to **−6044 samples (−504 ms)** — 10× the
window. The evidence was already visible in the note's own data: locked lags reached −524 with
19/57 unlocked pairs reporting |lag| > 500, and the script's own guard line
(`pairs with |lag| == MAX_LAG`) fired. The 57 "misses" were argmax-of-noise, not measurements
— they scatter uniformly mod 12 and **0/57** sit on the grid the locked pairs occupy.

The §3 explanation of those 57 was also internally contradictory: it argued the two arms'
noise is independent (so weak FT8 can't lock), while the bullet above it argued both arms
share one ADC clock domain (which makes the noise *common*, and predicts a lock on all 68).
The second bullet was right; the first was rationalising a measurement failure.

**2.2 The invariant was stated on the wrong modulus.** The note reports lag ≡ 4 (mod 12) and
builds a "fixed 0.333 ms fractional residual" story on it. The actual invariant is
**≡ 76 (mod 120)** — a 10 ms grid, matching the WASAPI shared-mode device period — and it now
holds across **all 68** pairs, including lags out to 6044 samples. The mod-12 statement is a
weak corollary. This also deflates the note's probability argument: once the lags are known to
lie on a 10 ms grid, mod 12 = 4 follows deterministically, and there were only 6 distinct lag
values, not 11 independent coincidences. The conclusion (shared clock domain) survives — a
10 ms grid held to a fixed 76-sample residue over 68 cycles is overwhelming — but it needed
restating on the real invariant.

**2.3 Two smaller method issues,** both fixed in `measure_capture_alignment.py`: the
correlation was normalised by a single global denominator rather than per-overlap-window
(harmless at 0.33% overlap loss, badly wrong at second-scale lags); and the §4 verdict was
more confident than §3's body supported. §4's conclusion turns out to be correct anyway.

## 3. The measurements

### 3.1 Waveform, full-range FFT cross-correlation (all 68 pairs)

| | value |
|---|---|
| pairs locking at corr > 0.9 | **68 / 68** (was 11/68) |
| peak correlation | mean 0.972, median 0.975, range 0.933–0.992 |
| lag range | −6044 … +1876 samples (−504 … +156 ms) |
| lag ≡ 76 (mod 120) | **68 / 68** |
| sub-sample refined residual | 75.93 samples (mod 120) |

The lag is a **sawtooth**: it ramps by roughly −1860 samples (−155 ms) per cycle for 4–5
cycles, reaching about −500 ms, then resets by ~+7500 samples. **Every reset is immediately
preceded by a cycle that WSJT-X did not save.** The 16 cycles present in our arm but absent
from WSJT-X's are exactly the 16 reset points. Our arm writes a complete, unbroken 15 s grid
(84 files for 84 slots); WSJT-X drops one slot every 5–6 cycles.

### 3.2 Our own framer telemetry (`cycle-archive.csv`, 84 rows)

`dropped_before` = **0 on every cycle**. Consecutive `window_closed_utc` deltas are
14987–15056 ms — 15.000 s ± 50 ms with no accumulation over the 21-minute session.

### 3.3 Absolute alignment, 2×2 decoder × audio

DT is an absolute reference: the transmitting stations are collectively time-locked, so a
cycle's median DT measures the receiver's own window alignment. A correct receiver reads ≈ 0.

| | n | per-cycle median DT | σ |
|---|---:|---:|---:|
| our decoder / our audio (live) | 1749 | **+0.681 s** | 57 ms |
| our decoder / our audio (offline) | 1284 | **+0.679 s** | 59 ms |
| our decoder / WSJT-X audio (offline) | 1288 | **+0.546 s** | 208 ms |
| WSJT-X decoder / WSJT-X audio (live) | 2684 | **−0.189 s** | 263 ms |

Reading the table two ways:

- **Same decoder, two audio sources** → +0.679 − 0.546 = **+0.133 s**. That is the genuine
  capture-window difference, and it independently reproduces the waveform measurement
  (mean lag −1793 samples = +0.149 s) to within 16 ms.
- **Same audio, two decoders** → +0.546 − (−0.189) = **+0.735 s**. Identical input samples, so
  this is entirely our decoder.

A regression of per-cycle (DT_ours − DT_wsjtx) against the waveform lag gives
**slope 1.036, r = +0.972, residual σ = 51 ms** — the waveform instrument and the decoders'
sync estimates measure the same physical quantity, which validates both.

## 4. Root cause

**The +0.796 s live DT gap decomposes into 0.133 s of capture offset and 0.735 s of decoder
offset.** Only the second is a defect worth acting on.

The 0.735 s is in `Ft8Decoder`'s DT derivation. `ft8_lib` reports a candidate's time offset
relative to the **start of the sample buffer**; WSJT-X reports DT relative to the **nominal
transmission start, 0.5 s into the cycle**. A missing 0.5 s subtraction accounts for most of
the constant, with the balance plausibly from `ft8_lib`'s sync-search quantisation
(symbol 0.16 s ÷ `time_osr`). I have not confirmed the exact term — that is a code question,
and per HK-011/HK-015 it belongs to a Developer session, not to me.

Whether it costs decodes is **not yet established, and I do not want to assert it either way**.
The offline arm decoded 1284 on our audio versus 1288 on WSJT-X's, so the 0.133 s capture
difference costs essentially nothing. If `ft8_lib`'s internal sync search is symmetric about
the true position and only the *reported* value is offset, the defect is confined to logged
and displayed DT. If instead the search interval is anchored on the biased value, we are
spending ~0.7 s of a ~±2.5 s search range on one side, which would cost marginal decodes and
would be a candidate contributor to the standing sensitivity gap (1749 vs 2684 live). §5.1
distinguishes these.

Regardless of which it is, the offset is already wrong where DT is consumed: it is written to
ADIF and shown in the UI, and any future alignment-feedback logic keyed on DT would be driven
0.735 s off.

## 5. Next steps

Ordered by value. §5.1 and §5.2 are the ones I would actually do next.

**5.1 — Determine whether the DT offset is cosmetic or costs sensitivity.** Offline, no live
run, deterministic, uses data already in hand. Take the 68 WSJT-X WAVs; decode each three
times with the sample buffer pre-rolled by −0.5 s, 0, +0.5 s of silence. If total decode count
is flat across the three, the sync search is symmetric and the defect is report-only (fix it
as a logging correctness bug). If the count peaks off-centre, the search window is genuinely
mis-anchored and this is a sensitivity defect that belongs in the D-001 thread. This is the
single highest-value next action: it converts an open question into a routed one.

**5.2 — Recommend closing PR #108 (`fix-cycle-boundary-clock-drift`) unfixed.** §9.5's
disposition is open. The measurement now says our framer holds absolute alignment to σ = 59 ms
over 94 cycles with zero dropped samples, and is 3.5× more stable than the reference
implementation it was being compared against. Three fix rounds were defeated by live testing
because they were correcting a drift that is not in our arm. Closing it is a Captain decision
under HK-010; I am recommending, not doing.

**5.3 — Correct the 21:45 note.** It is on `main` at `7a04928` and its §2–§4 are wrong in the
ways set out in §2 above. Options: supersede it with a pointer to this document, or amend it
in place. It is QA's document, so per HK-015 the call and the edit are QA's; I have deliberately
not touched it. My recommendation is a superseded-by banner plus leaving the body intact, since
the failure mode (a truncated correlation search reading as a physical result) is worth keeping
visible.

**5.4 — Fold the two scripts into the standing D-001 harness.** They are now out of
git-ignored `_work/` and reproducible, and `measure_dt_alignment.py`'s 2×2 is a general
instrument for separating capture faults from decoder faults — it would have resolved this in
one run. Worth having available for the next alignment question rather than rebuilt ad hoc.

**5.5 — Not recommended: the band-limited coherence check** floated in the 21:45 note §3. It
was proposed to rescue the 57 "inconclusive" pairs. Those pairs were never inconclusive, and
the widened search already answers the question at full strength. Skip it.

## 6. What this does not change

The 20:30 parity verdict stands, on stronger evidence than before: 68/68 waveform lock at a
fixed 10 ms-grid residue, plus level match within 0.15 dB mean and zero clipping. The capture
chain is exonerated. The decode-sensitivity gap versus WSJT-X remains open and remains a
decoder question — §5.1 tests one specific, newly-identified candidate contributor to it, and
does not claim to explain the whole gap.

---

*Per HK-014 nothing here is pushed or merged, and per HK-015 `tasks.md` and `dev-tasks/` are
untouched — §5.1 and §5.3 are written for QA to route.*
