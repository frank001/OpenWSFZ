# FIT-DEPTH: can a better fit remove strong signals more deeply? (offline measurement)

**To:** QA, who builds and runs it (QA tooling only; no Developer task)
**From:** Architect, 2026-11-27
**Approved:** Product Owner, 2026-11-27 ("yes, write the measurement spec. let's see if the lean decoder has any more surprises").
**Why:** most crowded misses are **K2** (found, tried, not decoded: 65–75 %, SUB-PROBE), and K2 grows steeply with the neighbour's strength. Signals of −10 dB or stronger are subtracted a **median 5 dB short** of the noise floor, and a quarter of them 8.5–10.5 dB short. Signals weaker than −10 dB are removed down to the noise (SUB-PROBE §5.1, `sub-probe-result.md`). The two decode-side and coverage levers are spent: PAYLOAD-FIT and XC-ROUND made sure every decoded signal is subtracted, and KNOWN-ERASURE (blanking the neighbour's tone bins) did nothing. **What has never been tried is the quality of the fit itself.**

**Process:** a measurement on recordings already on disk. **No `src/` or `native/` change, no build, no replay, no bars on the decoder.** Its result decides whether a build spec follows. Expected run time under 2 hours, so no go is needed (rule of 2026-11-18). If QA's timing says it would be longer, QA subsamples cycles (§3.4) and does not ask.

---

## 0. What the fit does today, and why the window is the suspect

Lean fits every result it subtracts with `ft8_subfeas_fit_signal` (`ftz_decoder.c:798`), on the **original** audio's analytic signal. This is a line-traceable port of QA's Python fitter (`qa/rr-study/sub-feas/fitter.py`, `qa/rr-study/synth/modulator.py`):

1. **Template:** the 79 tones of the payload, continuous-phase GFSK with **BT = 2.0** (`SUBFEAS_GFSK_BT`). This is textbook FT8, as QA checked in September.
2. **Search:** time ±100 ms in 1 ms steps, a frequency search, and a **linear** drift of ±0.10 Hz/s.
3. **Envelope:** a complex gain c(t) (strength and phase) smoothed with a **Hann window of 0.32 s** (`ENV_W_SAMPLES 3840`, `subfeas_fit.c:74`). The subtraction is Re{c(t)·r(t)}.

**The 0.32 s comes from SUB-FEAS's window selection** (`sub_feas_result.json`, `w_selection`, split A, all fitted signals, mostly weak). The median residual measure X, by window:

| W (s) | 12.64 | 2.56 | 1.28 | 0.64 | **0.32** |
|---|---|---|---|---|---|
| median X | 18.53 | 11.43 | 10.37 | 9.51 | **8.15** |

**0.32 s won as the shortest window in the family, and X was still falling at that edge.** It was also chosen once for all signals. For a weak signal a short window mostly follows the noise. For a strong one the noise in c(t) is small, and what is left is fading, transmitter phase wobble and drift that is not linear. All of these are things a shorter window follows and a longer one does not. **So the hypothesis is that strong signals want a shorter window than the one picked for the crowd.**

The second, weaker suspect is the **pulse shape.** A station that sends plain FSK without Gaussian smoothing does not match a BT = 2.0 template at every tone change. The Architect does not know how common that is on air, so it is measured, not assumed.

**The risk the measurement must guard against:** a shorter window also absorbs more noise, and more of a **weak neighbour.** Its envelope bandwidth approaches the 6.25 Hz tone spacing, so it starts to follow energy that is not the signal's. That would remove the very signal we want to decode. §2.3 and §2.4 measure both effects.

## 1. The signals

- **Slices:** S40, H40 and H20, the same cycles as LC-BASE and SUB-PROBE (cycle WAVs as the replay harness reads them).
- **Population:** every **WSJT-X decode** in those cycles. WSJT-X is the reference and is independent of lean. The text is read from the night's `wsjt-x/ALL.TXT` **inside one function** that returns only tones, frequency, time and SNR (HK-037, as `sub-feas/corpus.py` does). A message whose text cannot be encoded (`<...>` and similar) is skipped and **counted**. It is an encoding limit, not a property of the waveform.
- **Bands by the WSJT-X SNR:** **S0** ≥ 0 dB, **S1** −5 to −1, **S2** −10 to −6, and a **control band SC** −15 to −11.
  - SC is the positive control: SUB-PROBE says those signals are already removed to the noise, so the instrument must read **no room** there (§4, check C2).
  - Signals below −15 dB are not fitted.
- **Isolated / crowded:** a signal is **crowded** if another WSJT-X decode lies within ±60 Hz in the same cycle, else **isolated.** Every table is split both ways. Crowded strong signals are the K2 neighbours; isolated ones show the fit without other signals in the way.

## 2. What is computed per signal

**Fit:** QA's `fitter.py` exactly as SUB-FEAS ran it (seeded from the WSJT-X time and frequency with SUB-FEAS's `TAU0_S`; search, drift and envelope code unchanged), on the original cycle audio, as lean does.

- The template search (time, frequency, drift) runs **once per pulse shape.**
- The envelope and the subtraction run once per window. **The window changes only step 3**, so the variants are cheap once the search is done.

**Variants (8 per signal):**

| | W = 0.64 s | **W = 0.32 s (production)** | W = 0.16 s | W = 0.08 s |
|---|---|---|---|---|
| **GFSK, BT = 2.0 (production)** | ✔ | ✔ **reference** | ✔ | ✔ |
| **plain CPFSK (no Gaussian smoothing)** | ✔ | ✔ | ✔ | ✔ |

Plain CPFSK means the instantaneous frequency steps at the symbol boundaries with the phase kept continuous: `modulator.py` with the pulse smoothing switched off. This is a parameter QA adds to its own Python tooling, with the default unchanged. The 0.08 s window is deliberately past the expected limit; it shows where the noise and neighbour absorption take over.

### 2.1 The leftover in the signal's own cells (primary measure)

On the fitted grid (start time and frequency from the fit, one block per symbol, 0.16 s, aligned on the fitted start), for each of the 79 symbols:

- **own cell:** the power of the audio projected onto a complex exponential at the symbol's own tone frequency (one DFT bin, 1,920 samples).
- **reference cells:** the same projection at the **other 7 tone frequencies** of that symbol.

**L = 10·log10( mean of the 79 own cells ÷ trimmed mean of the 7 × 79 reference cells ),** where the trimmed mean drops the top 10 % of the reference cells, against other signals' tones. L is computed **before** the subtraction and **after** it, for every variant.

- L before is roughly the signal's own SNR in its cells.
- L after is **what the fit left behind**, in dB above the local noise. Perfect subtraction gives the noise control's value (§2.2), not exactly 0, because of the trim and any absorbed noise.

**Also, by third of the transmission:** L after, over symbols 1–26, 27–53 and 54–79. Drift that is not linear leaves its error at the ends. Fading and wobble leave it spread across the transmission.

### 2.2 The noise control (zero point and noise absorption)

For each fitted signal, the **same fitted template and the same variant** are applied at a **signal-free spot** of the same cycle: the same start time, at a frequency where no WSJT-X decode and no lean decode lies within ±60 Hz. The spot is chosen at random, with a fixed seed, from the free frequencies in 200–2,800 Hz; if there is none, the signal is skipped and counted. The template is fitted there with time and frequency fixed and only the envelope estimated. L after is computed the same way: **L_ctl.**

- L_ctl < 0 by the amount of noise the envelope absorbed into its own cells, and it grows more negative as the window shortens.
- **The depth shortfall is D = L_after − L_ctl,** per signal and per variant: 0 = removed down to what the noise allows.
- **Only D is compared between windows.** A window that "wins" only by absorbing noise moves L and L_ctl alike, and D does not move.

### 2.3 The weak neighbour (does a shorter window eat it?)

For every **S0–S2** signal S, a synthetic weak signal **T** is injected into a copy of the cycle audio:

- T is a fixed synthetic message with a `Q`-prefix callsign (NFR-021), modulated with `modulator.py` (GFSK, BT = 2.0).
- Level **−18 dB** on the 2,500 Hz scale. QA scales it from the noise power of S's reference cells and states the method.
- Frequency offset from S of **±12.5, ±25 or ±37.5 Hz** (2, 4 or 6 tone spacings; the sign and the offset are drawn with a fixed seed). Time offset drawn uniformly in ±0.5 s, same seed.

Then S is fitted and subtracted with S's tones only, for every variant, and two numbers are computed:

- **L_T, the neighbour's leftover where T is read:** take (residual − the injected T, known exactly) and project it on **T's own 79 tone cells** against T's other 7 columns, as in §2.1. This is what the strong neighbour leaves in the cells tier A reads for T: the K2 mechanism, measured directly. Also reported before the subtraction.
- **T retention:** project the residual onto T's own known template (one complex gain over the transmission) and compare with the injected gain: **loss in dB.** It should be 0. Anything above that is T removed along with S.

### 2.4 The pulse shape

Per S0–S2 signal: **D(GFSK) − D(CPFSK)** at W = 0.32 s and at the W with the lowest median D. A positive value means CPFSK fits better. Also: the share of signals where CPFSK is better by **more than 1 dB.**

## 3. Practicalities

1. **Tooling:** QA's, under `qa/decoder-rebuild/` (e.g. `fit_depth.py`), reusing `fitter.py`, `modulator.py`, `corpus.py`'s encoder and `bigfit.py`'s per-cycle multiprocessing (results in submission order, so the run is deterministic). Numbers only leave the reading function (HK-037). Per-signal working files go to `D:\Projects\claude\_qa-scratch\fit-depth\`, kept.
2. **No station, no daemon, no radio.** CPU only. Station exclusivity is not needed (no timings are compared).
3. **Seeds:** one fixed seed for the free-spot choice and the injection. Stated in the result.
4. **Time:** QA times the first 20 cycles. If the projected full run exceeds 1.5 hours, QA takes every k-th cycle of each slice (the smallest k that fits) and states k. The same cycles are used for every variant.
5. **The native match (check C1):** for the signals that lean's XC-ROUND confirmation runs subtracted (`_qa-scratch\lc-base\runs\xn_*\probe.tsv`, `SUB` rows, matched to the WSJT-X decode within ±3 Hz and ±0.2 s), QA also computes SUB-PROBE's **suppression dB** from the Python fit at **W = 0.32 s, GFSK**: same footprint (8 tone columns × 79 symbols), same before/after definition. This is compared with the native `SUB` row's value.

## 4. Checks (mechanical; on a failure QA stops and tells the Architect before reading anything else)

| # | Check | Predicate | Where the number comes from |
|---|---|---|---|
| C1 | The Python fit is the production fit | median of (Python suppression − native `SUB` suppression), over the matched signals, per slice, lies within **±2 dB** | Architect's choice. The only scale on file is SUB-PROBE's ±2.5 dB ceiling approximation. The native row also includes other signals subtracted in the same footprint, so exact equality is not expected. |
| C2 | The instrument sees "no room" where SUB-PROBE does | the median **D** of band **SC** at W = 0.32 s, GFSK, lies within **±1.5 dB** of 0 on every slice | SUB-PROBE §5.1: bands below −10 dB sit at 0 ± 2.5 dB of the ceiling on this decoder |
| C3 | The instrument sees the shortfall SUB-PROBE saw | the median **D** of **S0–S2** pooled at W = 0.32 s, GFSK, is **≥ 2 dB** on every slice | SUB-PROBE: a median 5 dB short (Q1 to Q3 wide); 2 dB leaves room for the different measure |
| C4 | Nothing was silently skipped | counts of fitted / not encodable / fit failed / no free spot, per slice and band, are reported, and every variant has the same signals | none: a completeness check |

If C2 or C3 fails, the measure is not reading what SUB-PROBE read, and the window comparison is not interpreted.

## 5. What is reported (aggregates only; the SUB-PROBE result's format)

1. **Table 1, the depth:** median and quartiles of **D**, per slice × band (S0, S1, S2, SC) × variant (8), isolated and crowded separately. Plus the **paired** change against the reference: D(variant) − D(0.32 s, GFSK), per signal, median and quartiles.
2. **Table 2, the cost of a shorter window:** median L_ctl per window (noise absorption), **L_T** after the subtraction (median, quartiles; and before, for context) and **T retention loss** (median, Q3, and the share > 1 dB), per window, GFSK, S0–S2 pooled, per slice.
3. **Table 3, the pulse:** §2.4's paired difference and the share with CPFSK > 1 dB better, per slice and band.
4. **Table 4, where in time:** median L after by third of the transmission (§2.1), S0–S2, at 0.32 s and at the best window.
5. **Checks C1–C4** with their numbers, the seed, k (if subsampled) and the wall time.
6. **One figure:** median D by window, one line per band, per slice, GFSK.

## 6. What happens next (the decision rule, written before the result)

- **A build spec follows (SNR-dependent window)** if, at some W < 0.32 s, for S0–S2 on all three slices:
  - the paired median **D falls by ≥ 2 dB** against 0.32 s;
  - **and the median L_T falls by ≥ 1 dB**, so the neighbour leaves less where T is read;
  - **and the T retention loss is ≤ 0.5 dB at the median and ≤ 1 dB at Q3.**

  The build would then keep 0.32 s for signals below the boundary that §5 shows, and use the short window above it. **These three numbers are the Architect's choice, not taken from data:** 2 dB is about 40 % of the 5 dB median shortfall, and 1 dB / 0.5 dB are the smallest effects this measure can plausibly resolve. The build would get one replay as usual, and K2 decides.
- **A pulse-shape proposal follows** if CPFSK is better by > 1 dB for **≥ 10 %** of S0–S2 signals on every slice.
- **If neither:** the fit model is closed as a lever. The shortfall then lies in something a smooth envelope over a correct FT8 template does not describe (the transmitter's audio chain, splatter, multipath), and the Architect says so to the Product Owner, together with what is left (search rules 9 %, accept rules 5–7.5 %, never found ~6 % of the crowded misses).
- **If D falls but L_T does not:** depth is not what K2 depends on. Close it too, and say that KNOWN-ERASURE's null and this point the same way.

## 7. The Architect's expectations (priced before the run; scored in the ledger)

The SUB-FEAS medians fell 1.36 dB from 0.64 to 0.32 s over a population that was mostly weak. For strong signals the slope should be steeper, but the ledger shows that hypothesised calls of "a findable defect" are biased high, so the H calls are priced down.

| # | Prediction | P | Class |
|---|---|---:|---|
| FD-1 | At W = 0.16 s (GFSK), the S0–S2 paired median D falls by ≥ 2 dB against 0.32 s on all three slices | 0.35 | H |
| FD-2 | The §6 build rule is met (D, L_T and retention) at some W < 0.32 s | 0.30 | H |
| FD-3 | At W = 0.08 s the median T retention loss is > 0.5 dB, or the paired median D is higher than at 0.16 s, on at least one slice | 0.60 | H |
| FD-4 | CPFSK is better by > 1 dB for ≥ 10 % of S0–S2 signals on every slice | 0.15 | H |
| FD-5 | Checks C1–C3 all pass | 0.70 | C |
| FD-6 | The run (full or subsampled) finishes in under 2 hours of wall time | 0.80 | C |
