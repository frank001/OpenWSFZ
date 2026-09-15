# `E4-BENCH` — pre-registration: is our decoder more fragile than WSJT-X to real-signal impairments (transmitter drift, fading), on a bench where the truth is known?

**Architect, 2026-09-15 16:45Z** (`date -u`, HK-017). Branch `arch/e4-channel-impairments` (cut from
`origin/main` at `e5c79aa4`). Docs-only; `git diff --stat origin/main...HEAD -- src/ native/` is empty.

**Status: cleared to specify.** The Captain, 2026-09-15: *"go with E4, spec it"*. **The run is NOT yet
cleared.** It needs about two hours of the station with the radio's audio kept off the decode bus
(§5 Q2), so the Captain schedules it. ~~`BAR_E` (§3.4) is Architect-set, not PO-ratified.~~
**`BAR_E` = 0.10 ratified by the Captain, 2026-09-15: *"10-point bar is fine (for now)"*.** "For now"
is read as the standing rule already here: he may still move it **before the first datum**. After that
it is frozen, and anyone proposing to move it (me included) gets refused.

**Amendment A1, 2026-09-15 17:26Z, before any datum (§8):** the message pool, ROW 0a(ii) and
ROW 0a(iii), and one generator rule in §2.3. They came from QA's build questions. **No bar, gate row,
dose or block changes.**

**Authorised by:** C-ASYM-A ROW C3 (2026-08-23, `qa/rr-study/2026-08-23-1032-qa-to-architect-c-asym-a-results.md`
§6), which fired and named E4 the leading candidate. That spec's §8 said ROW C3 is the row that
authorises opening E4, and nothing else does. E4 has been unopened for 23 days.

---

## §0. What this is, why now, and what it reuses

### 0.1 The one-line reason

On clean synthetic audio we decode strong signals every time. On live audio, from **the same radio on
the same audio path as WSJT-X**, we miss a large share of strong signals that WSJT-X decodes. Clean
synthetic audio has no drift and no fading. Real signals have both. **E4 asks whether that difference
is the reason.** The bench can answer it because the truth is known there.

### 0.2 The size of the question, counted while drafting (HK-018)

Corpus C2 (`artefacts/20260908_live_run_1827-fp-floor-live-2/`, from `260908_193645` to `260909_172200`).
OpenWSFZ and WSJT-X #1 both listened on `Voicemeeter Out B1`, the FT-991A chain (`contents.md`,
provenance). **So every row below is a decoder difference on identical audio.** REF = WSJT-X FT991A
`ALL.TXT`, A only. Matcher = `live-gap-now/matcher.recovery()`. Live logs only, no replay. It reproduces
A1 to the digit (`n_ref` 91,046, `R_wild` 61.09%).

| REF SNR (dB) | REF rows | our `R_wild` | misses | share of all misses |
|---|---:|---:|---:|---:|
| ≤ −21 | 6,600 | 23.77% | 5,031 | 14.2% |
| −20 … −16 | 10,136 | 35.79% | 6,508 | 18.4% |
| −15 … −11 | 14,071 | 46.44% | 7,536 | 21.3% |
| **−10 … −6** | 15,110 | 58.58% | 6,259 | 17.7% |
| **−5 … −1** | 13,777 | 69.03% | 4,267 | 12.0% |
| **0 … +4** | 11,351 | 75.94% | 2,731 | 7.7% |
| **+5 … +9** | 8,113 | 80.51% | 1,581 | 4.5% |
| **≥ +10** | 11,888 | 87.24% | 1,517 | 4.3% |

⇒ **16,355 of 35,430 misses (46.2%) are signals WSJT-X itself rates at −10 dB or better.** If every one
were recovered, `R` would rise by **17.96 pp**. That is a ceiling for anything that acts above the
threshold, not an expectation. E4 is one candidate for that ceiling. Density (co-channel overlap) is the
other (§6).

**What the bench already says about those SNRs.** On S8HN (C-ASYM-A Part C, 25 trials, −15…+3 dB,
AWGN), OpenWSFZ decoded every injected message on 11 of 12 stations in every trial. The only misses
were station F, the 12 Hz near-collision, at 0/25. So on clean signals above threshold we do not lose.
The known synthetic deficit is **below** threshold: S1b −21 dB, ours 0/24 vs WSJT-X 13/24. THRESH-A put
that loss in bit formation, and the Captain parked it (route A, 2026-09-14). **This arm does not reopen
it.** §3.4 bounds how much of it can leak into a fading reading.

⚠️ **Qualifiers that travel with A1:** binary `6b2e16a6…`, `nhard` 60, 20m, REF = WSJT-X FT991A alone,
2026-09-08/09. Since PR #175 it is a **pre-G2(b)** figure.

⚠️ **Disclosure (de-blinding check).** Beyond the table above I computed one more thing: a count of REF
rows with no other REF row within ±60 Hz in the same cycle (34,240 of 91,046; 22,763 of the 60,239 at
≥ −10 dB). **I did not compute recovery on that subset**, because of the spectral-locality bar (§6). No
impairment bench datum exists anywhere. No impairment generator exists. The bars below were set
knowing only the numbers in this section.

### 0.3 What "impairment" means here, and the two that are left out on arithmetic

C-ASYM-A's E4 row named four: fading, Doppler spread, transmitter drift and timing spread.

- **Transmitter drift** is family **DRIFT** (§2.2).
- **Fading and Doppler spread** are one family, **FADE**. The Doppler spread is the fading's own rate
  (§2.3).
- **Timing spread (multipath delay) is left out, because it cannot matter at FT8's bandwidth.** A second
  path delayed by τ puts spectral nulls every `1/τ` Hz. HF delays are about 0.5–2 ms, so the nulls are
  500–2,000 Hz apart. The whole FT8 signal is 50 Hz wide, so it sees a flat channel. The delay is also
  ≤ 1.3% of a 0.16 s symbol. FADE carries a fixed 1 ms second path, so the effect is present, just not
  laddered.
- **Transmit sound-card clock error is left out for the same reason.** 100 ppm moves a 1,500 Hz tone by
  0.15 Hz and stretches the 12.64 s transmission by 1.3 ms. Both are far below anything in DRIFT's
  ladder.

### 0.4 Reused, not rebuilt (HK-018)

| what | where | note |
|---|---|---|
| encoder, modulator | `qa/rr-study/synth/` (`modulate()`, `modulator.py:34`) | DRIFT hooks into `inst_freq` (`modulator.py:85`). **The default path must stay byte-identical** (ROW 0a). |
| shared-floor mixer | `synth/channel.py` `mix_to_shared_floor()` | one noise floor per slot, SNR set per station, as S4/S8 |
| band-scene runner | `harness/run_scenario.py` / `run_study.py` | the band-scene path, keyed on the `"signals"` schema (generalised for S8HN, C-ASYM-A §7.2) |
| matcher | `harness/matcher.py` | 🔴 **restrict it to this run's own `cycle_utc` set from `truth.csv`.** It tallies every bucket in `ALL.TXT`, and an uncleared log inflated a false-positive count 55× once (C-ASYM-A §6). |
| warm-up | read the warm-up decode from both `ALL.TXT`s (C-ASYM-A §6, HK-027) | the interactive `y/r/n` prompt hits EOF under `nohup` |
| supervisor | HK-013 / HK-023 pattern | the run is > 1 h |

🔴 **HK-020 traps, named in advance:**
- `run_study.py --device` defaults to `"CABLE Input"`, which is unreliable here. **Pass
  `--device "Voicemeeter AUX Input"`.**
- `run_scenario.py` **appends** to `truth.csv`, and a `--dry-run` on the same day shares the directory.
  Delete dry-run leftovers first (C-ASYM-A §7.3).
- **The station runs `nhard` 40**, and that is also `main`'s code default. Read it back from the daemon
  (read-only, HK-035) and record it.

---

## §1. Population

**Synthetic only.** No corpus, no capture run, no replay. Every signal is injected, so truth is known
exactly: a decode is a hit, a miss or a false positive, and nothing is inferred.

**Unit of independence = the trial slot** (HK-021(i)). All stations in one slot share one noise
realisation. Each dose appears exactly once per slot (§2.4), so a dose's statistic has one observation
per slot, and a paired bootstrap over slots is the cluster bootstrap.

## §2. The bench

### 2.1 Who builds it

**QA, entirely.** The generator, scenario and harness changes are all under `qa/`. HK-011 does not bite:
**no Developer session, no `src/`/`native/` change.** The decoders are the shipped ones (ROW 0b).

### 2.2 DRIFT: linear transmitter drift

Instantaneous frequency gets a linear ramp across the transmission, centred so the mean frequency is
unchanged:

```
inst_freq(t) += delta_hz * (t / T_tx - 0.5)      for t in [0, T_tx), T_tx = 79 * 0.16 s = 12.64 s
```

`delta_hz` is the total drift over the transmission. Its **sign alternates by trial** (+ on even trials,
− on odd). Doses: **`delta_hz` ∈ {0, 0.5, 1, 2, 4, 8, 16} Hz.** Dose 0 is the shared AWGN control. The top
dose puts the ends 8 Hz off, which is 1.28 tone spacings, so it must break both decoders (ROW 0f).

### 2.3 FADE: two-path Rayleigh fading (Watterson model)

Rendered on the complex signal `z(t) = exp(jφ(t))` from the modulator's own phase, then the real part
is taken:

```
y(t) = Re{ g1(t) * z(t) + g2(t) * z(t - tau) },   tau = 1 ms
```

- `g1` and `g2` are independent, zero-mean complex Gaussian processes with **ensemble** power
  `E|gk|² = 1/2`, so the average power is 1 and the average SNR is the nominal SNR.
- 🔴 **Never normalise a realisation to unit power.** That would delete the slow-fade lottery, which is
  half of what fading is.
- Each process has a Gaussian Doppler spectrum. Its **frequency spread `B` is defined as 2σ** of that
  spectrum (the ITU-R F.1487 convention). Generate it by shaping complex white Gaussian noise in the
  frequency domain.
  - **(A1, §8.3) "That spectrum" is the Doppler POWER spectrum `S(f) = |H(f)|²`,** so the magnitude
    filter's own σ is `√2 · B/2`. QA caught this during the build.
  - 🔴 **(A1, §8.3) Generate each `g` on a buffer of at least `T_tx + 2/B` seconds and keep the
    transmission's `n` samples.** Frequency-domain shaping is circular. On a buffer only `T_tx` long,
    the gain at the last symbol is the gain at the first symbol again, at every `B`.
- Seeds come from `(trial, position)` and are independent of the AWGN seed.
- Doses: **`B` ∈ {0.1, 0.25, 0.5, 1, 2, 5, 10, 20} Hz.** 0.1/0.5/1 Hz bracket F.1487's quiet, moderate
  and disturbed mid-latitude conditions. 10 Hz is flutter. 20 Hz smears each tone across three tone
  spacings, so it must break both decoders (ROW 0f).

### 2.4 The slot

- **15 stations per slot = one full ladder.** That is DRIFT's 7 doses and FADE's 8.
- **Positions:** base frequency `300 + 170·p` Hz, `p` = 0…14, so 300–2,680 Hz. Stations are 170 Hz apart,
  and each is 50 Hz wide plus at most ±10 Hz of impairment, so no two can interact. **This is a bench of
  isolated signals by construction.** The highest tone of the top station stays below 2,740 Hz, even
  with jitter and 8 Hz of drift, which is well inside the shipped passband.
- **Latin rotation:** in trial `t`, ladder item `i` sits at position `(i + t) mod 15`. That way no dose is
  tied to a frequency.
- **Lattice jitter:** every station's base frequency gets `U(−1.5625, +1.5625)` Hz, seeded per
  `(trial, position)`. Our 3.125 Hz lattice makes sub-lattice placement matter (P3). Without jitter, a
  dose could be confounded with a fixed lattice offset.
- **Messages:** ~~15 distinct standard Q-prefix messages from `scenarios/study-messages.json`.~~
  **(A1, §8.1) `MSG-01` … `MSG-15`. The file held only 10 standard messages; QA appends
  `MSG-11` … `MSG-15` with the texts in §8.1.** **No
  hashed or non-standard callsigns**, so `<...>` rendering cannot touch recovery. The message
  assignment rotates with a stride independent of the dose rotation.
- `dt_s` = 0.0, as in S8.

### 2.5 Blocks and cost

| block | SNR (every station) | trials | role |
|---|---|---:|---|
| **P** | **−8 dB** | **150** | primary, gated. The centre of the heaviest above-threshold miss band (§0.2). |
| **S** | 0 dB | 50 | secondary, descriptive only (§3.5) |

**Interleaved P, P, P, S, repeating 50 times; the order is fixed before the run.** At about 30 s per trial (S8HN's
rate), 200 trials take about 100 minutes, plus warm-up. **Supervise it** (HK-013 / HK-023).

## §3. Measurement

### 3.1 Definitions (predicates as code, HK-021(r))

- `hit_O(t, i)` = 1 if OpenWSFZ's `ALL.TXT` holds item `i`'s injected message text in trial `t`'s cycle.
  `hit_W` is the same for WSJT-X. The matcher is restricted to the run's `cycle_utc` set (§0.4).
- `R_O(i)`, `R_W(i)` = the mean of `hit` over trials in a block.
- **`Δ(i) = mean_t [hit_W(t, i) − hit_O(t, i)]`.** It is **positive when WSJT-X survives the dose and we
  do not.** It is signed, never `|Δ|` (HK-021(l)).
- **Paired bootstrap over trials.** N_BOOT = 2000, seed `20260915`. Both decoders are resampled on the
  same draw, and `Δ` is taken per draw.
- **Bonferroni interval, used by F1 and F2:** the percentiles `[α/(2k), 1 − α/(2k)]` with α = 0.05.
  `k` = 6 for DRIFT (the doses above 0) and `k` = 8 for FADE.
- **90% interval, used by F3:** the 5th/95th percentiles, unadjusted. F3 claims that *every* dose is
  equivalent, which is an intersection-union test, and that needs no multiplicity correction.

### 3.2 ROW 0: strict order

| row | check (as code) | on failure |
|---|---|---|
| **0a** generator | **(i)** With no impairment fields, the render of every scenario in `scenarios/` (at its standard seeds) is **byte-identical** to `origin/main`'s synth output, mechanically diffed. **(A1: run it after `MSG-11`…`15` are appended.)** ~~**(ii) DRIFT:** on a noiseless render, the fitted slope of instantaneous frequency (Hilbert phase derivative, smoothed over one symbol) × `T_tx` is within ±2% of `delta_hz` at every dose, and `< 0.01` Hz at dose 0.~~ **(ii) DRIFT: REPLACED by §8.2 (differential).** ~~**(iii) FADE:** at every `B`, a 2,000 s noiseless carrier gives a measured 2σ spread within ±10% of `B`; mean `|g1|² + |g2|²` within ±3% of 1; `|corr(g1, g2)| < 0.05`.~~ **(iii) FADE: REPLACED by §8.3 (a pooled long carrier, plus two checks through the bench's own call).** | **STOP** |
| **0b** pin and config | The daemon's loaded `libft8.dll` SHA-256 = **`91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6`** (`origin/main` `win-x64`, shim 20260051, hashed while drafting). Effective `nhard` = 40, read back. WSJT-X is the **FT991A instance**, and its decode depth and AP settings are copied from its `.ini` into the report. | **STOP** |
| **0c** chain health | `captureActive` true; playback on `Voicemeeter AUX Input`; the warm-up message present in **both** `ALL.TXT`s at the warm-up timestamp | **STOP** |
| **0d** control | At dose 0 in block P, `R_O ≥ 0.95` **and** `R_W ≥ 0.95` | **VOID.** The bench loses clean signals, so no differential means anything. |
| **0e** contamination | Within the run's cycles, **zero** decodes from either decoder carry a callsign-shaped token that is not Q-prefix | **VOID, and an NFR-021 incident.** Live band audio reached the decode bus. |
| **0f** the ladder stresses (HK-021(q)) | Per family, at the top dose in block P, `min(R_O, R_W) ≤ 0.50` | **Not a STOP.** F3 cannot fire for that family (it reads F4). |
| **0g** balance | In block P every `(item, position)` pair occurs exactly 10 times (150/15); DRIFT signs are 75/75 | **STOP** |

**Why each row changes the verdict (HK-021(k), both branches evaluated):**
- **0a:** a generator that did not deliver its dose makes every row a statement about a different
  impairment. Byte-identity at default protects S1–S8, which share `modulate()`.
- **0b:** a differential measured on a binary nobody ships, or at `nhard` 60, answers the wrong
  question. The WSJT-X settings decide whether its AP decoding is in play. That is part of what it
  really does, so it is recorded, not changed.
- **0d:** if the clean control already loses, `Δ` at a dose mixes the impairment with whatever broke
  the control.
- **0e:** real signals in the slot break "truth is known", and so break the whole arm.
- **0f:** a ladder too gentle to hurt either decoder would read F3, "no differential", for the wrong
  reason. With 0f failed, that reading is F4, which is the truth.
- **No power row.** An underpowered interval lands in F4 anyway. §3.3 reports power instead.

⚠️ **What ROW 0 cannot detect (HK-022, HK-026).**
- **Impairments that are not modelled.** Transmitter audio distortion, phase noise, receiver AGC
  pumping, and impairment combined with density are all absent. **An F3 closes DRIFT and FADE, not E4.**
- **Whether live signals actually carry these doses.** The bench shows fragility at a dose. The live
  exposure is Stage 2's question (§3.7). The live ship gate for any treatment is a replay contrast on
  C2, as in PASSBAND-140.
- **Anything about density.** The stations are isolated by construction (§2.4).

### 3.3 Resolution (HK-021(m), (o), (v)), computed while drafting

- **Readout quantum:** one trial in 150 = **0.0067**.
- **Power of F1** (P(CI_lo^Bonf ≥ `BAR_E`) at the dose where the true `Δ` peaks), with 2% reverse
  discordance:

  | true peak `Δ` | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 |
  |---|---:|---:|---:|---:|---:|
  | FADE (`k` = 8) | 0.11 | 0.50 | 0.87 | 0.98 | 1.00 |
  | DRIFT (`k` = 6) | 0.13 | 0.54 | 0.89 | 0.99 | 1.00 |

  **My own central estimate for DRIFT is a peak `Δ` ≈ 0.35, conditional on fragility existing (§4).
  Power there is ≈ 1.0.** If the fragility is milder than I expect (peak 0.20), power is about 0.5.
- **Reach of F3, per dose, at true `Δ` = 0:** it depends on how often the two decoders disagree on the
  same trial (discordance). Discordance 0.10 ⇒ P = 0.97. 0.20 ⇒ 0.73. 0.30 ⇒ 0.45. Doses where both
  decoders sit near 100% or near 0% have discordance close to 0. Only the doses mid-curve cost
  anything, typically two or three per family. **F3 is demanding on purpose, so F4 is a likely reading
  when there is no effect.** §3.7 says what F4 leads to.

### 3.4 Why `BAR_E` = 0.10

- **What it would buy.** 60,239 of C2's REF rows (66%) are at ≥ −10 dB. If a fraction φ of them carried
  a dose where the bench differential is 0.10, fixing it would raise `R` by at most 0.10 × φ × 66 pp,
  which is 2 pp at φ = 0.3. That is about the size of PASSBAND-140's whole ceiling (2.1 pp). **So a
  differential below 0.10 is not worth building for.** That rests on no number this arm will produce.
- **What the known threshold deficit can produce alone (HK-021(w)).** Slow fading is an SNR lottery. At
  −8 dB average, a flat Rayleigh fade lands the instantaneous SNR in the deficit region
  (−24 … −18 dB) with probability **0.0704**. The largest deficit on record there is 13/24 vs 0/24
  (0.54). So **the known deficit alone can put at most ≈ 0.04 into any FADE `Δ`**. `BAR_E` is 2.5× that,
  so the old deficit cannot fire F1 by itself. DRIFT has no SNR lottery, and ROW 0d proves both decoders
  are clean at −8 dB.

### 3.5 Descriptive, no row (report every one)

- **A1: dose-response curves.** `R_O` and `R_W` at every dose, both families, both blocks, with 95%
  intervals, plus `Δ` and its Bonferroni and 90% intervals.
- **A2: `d50` per decoder per family.** The dose where recovery crosses 0.5, interpolated linearly on
  log-dose, where a crossing exists. Descriptive only; `d50` is not gated.
- **A3: block S (0 dB).** The same curves. **They bear on the 5,829 live misses at ≥ 0 dB (16.5%)**: if
  a differential seen at −8 dB is gone at 0 dB, impairment cannot explain the strong-signal misses.
- **A4: false positives.** Decodes matching no injected message, per decoder, per family. Unmatched is
  false here, because truth is known.
- **A5: position and sign.** Recovery by slot position (a frequency check) and, for DRIFT, by sign.
- **A6: realised fading power.** The distribution of per-trial mean `|g1|² + |g2|²` for each `B`, to
  show the slow-fade lottery was present.

### 3.6 Gate rows (block P; each family read on its own; first match wins)

| row | predicate | reading |
|---|---|---|
| **F1** | some dose has `CI_lo^Bonf(Δ) ≥ +BAR_E` | **We are more fragile.** WSJT-X survives a dose of this impairment that we do not. |
| **F2** | not F1, and some dose has `CI_hi^Bonf(Δ) ≤ −BAR_E` | **We are more robust.** This family cannot explain our live deficit. |
| **F3** | ROW 0f passed for this family, **and** every dose's 90% interval lies inside `(−BAR_E, +BAR_E)` | **No material differential** at any dose on the ladder. |
| **F4** | otherwise | **Unresolved.** |

Mutually exclusive. F2 is gated on not-F1. F3 cannot hold alongside F1: F1 needs a Bonferroni lower
bound ≥ `BAR_E`, but that bound sits below the 90% interval's lower bound, which F3 keeps under `BAR_E`.
F2 is the mirror image. F4 is the remainder. **If the F2 predicate also holds under an F1, report it as a flag.** That
would mean we are more fragile at one dose and more robust at another.

### 3.7 Consequences

- **DRIFT F1 ⇒ the first buildable lead on the above-threshold gap.** In the acceptance ruling the
  Architect scopes a treatment spec for `decoding_improvement`: a drift/frequency-track hypothesis
  search inside extraction. It is native work (Developer, HK-011), and **its ship gate is a C2 replay
  contrast** through the managed chain, as in PASSBAND-140. 🛑 It may not reuse `ft8_refine_candidate()`'s
  position output: limb 1 is dead on real signals (08-19). The Architect also decides whether Stage 2
  (below) is worth running first.
- **FADE F1 ⇒ fading fragility is established, but the treatment space is narrow.** Input
  normalisation, AGC and equalisation are closed (P2), and an OSR change needs its own
  pre-registration. The Architect scopes it in the acceptance ruling, or reports that nothing is
  licensed.
- **F2 ⇒ that family is struck** as an explanation of our live deficit.
- **F3 on both families ⇒ drift and fading are closed as explanations of the above-threshold gap on
  this binary.** The ledger records it. Density becomes the leading remaining candidate, and the
  Architect brings the Captain that question. Subtraction stays barred.
- **F4 ⇒ report every figure.** The Architect decides between one extension run on the unresolved doses
  only (bars unchanged, written as an amendment **before** any extension datum) and stopping. `Δ` may not
  be cited as fragility or as its absence.

**Stage 2 (sketched, not armed): a live exposure census.** It would estimate drift and fade depth on
C2's REF rows at ≥ −10 dB, from the archived audio and each decode's known tone sequence. It runs over
**all** such rows, hit or missed, so that the population is not chosen on the outcome (HK-021(t)).
Combined with the bench curves, it would predict how much live loss a family explains. **It is only
worth specifying after an F1.** If it is ever armed, it needs a Captain ruling on one point first:
excluding overlapped signals as an **estimator-validity** filter is not the same thing as stratifying
recovery by neighbour distance, but it sits close to the spectral-locality bar.

---

## §4. Architect predictions: blind, on the record, before any datum

| family | F1 | F2 | F3 | F4 | reasoning |
|---|---:|---:|---:|---:|---|
| **DRIFT** | 0.45 | 0.05 | 0.25 | 0.25 | We never refine frequency, so a drifting tone spends part of the transmission between our bins, on top of a lattice offset of up to 1.56 Hz. WSJT-X refines a constant offset, which removes the lattice part of its error, and it can fall back to single-symbol metrics. A shifted curve is plausible. |
| **FADE** | 0.20 | 0.15 | 0.35 | 0.30 | Both decoders are hit by a fade. WSJT-X's multi-symbol coherent metrics should suffer at flutter rates, and our single-symbol magnitudes should not, so F2 at high `B` is live. At slow rates it is an SNR lottery for both. |

**Point predictions:** DRIFT `d50`: ours ∈ [2, 6] Hz, WSJT-X ∈ [3, 10] Hz. FADE `d50` ≥ 10 Hz for both.
Block S shrinks any DRIFT differential by at least half. **ROW 0d** PASS 0.9. **ROW 0f** PASS 0.85 per
family. Calibration: of my last four categorical calls in this programme, three missed (LIVE-GAP-NOW
ROW 0d, THRESH-A T2, `Δ50`) and one hit (PASSBAND-140 G1, at 0.45). Weight these accordingly.

---

## §5. PO questions (before the first datum only)

- **Q1: `BAR_E` = 0.10?** ✅ **Ratified 2026-09-15** (*"fine (for now)"*). It can still be moved **before
  QA produces any `Δ`** and is frozen after. A move proposed once `Δ` is known is refused and VOIDs the
  arm.
- **Q2: station time.** About two hours, during which **the radio's audio must be kept off the decode
  bus** (ROW 0e). OpenWSFZ and WSJT-X are off the air for decoding for that window. The Captain picks the
  slot, and QA's procedure keeps the band out. ✅ **Granted 2026-09-15 17:32Z: *"2 hours right now is
  fine."*** The window is open now, but the run still starts only after ROW 0a (as amended by A1) and
  the `--dry-run` pass. Station time does not waive ROW 0. **That window was not used.** At 17:3xZ QA
  reported 2–3+ h of build left (the runner integration, the scenario file, 0a(iii)(b)/(c) at 48 kHz,
  the gate-WAV decodes, 0b/0c), and the run needs ~100 min on top. Q2 is **re-asked** once QA reports
  the bench armed.

## §6. What this arm does NOT do

- 🛑 **No `src/` or `native/` change, no Developer session, no push, no merge** (HK-011, HK-014, HK-010).
- 🛑 **No capture run, no replay.** It is synthetic playback only.
- 🛑 **It does not reopen THRESH-A** (route A, parked), subtraction (dead), input scaling (P2, closed),
  the analysis-window family (closed), the candidate budget (closed twice), or any closed gate.
- 🛑 **It does not use `ft8_refine_candidate()`** or cite its precision on anything.
- 🛑 **Spectral locality stays barred.** Nothing here stratifies recovery by distance to a neighbouring
  decode. The bench's stations are isolated by construction, and the §0.2 isolation count is a count.
- **It does not test density.** Density is E4's rival for the above-threshold gap, not part of it.
- **It cannot see:** impairments that are not modelled (§3.2), live exposure (Stage 2), any band, or
  `nhard` 60.

**Found while drafting (not this arm's to fix):** `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`
on `main` still heads its file `CURRENT … FT8_SHIM_VERSION 20260050`. PR #175's ship commit `2546f0c6`
replaced the DLL (now shim 20260051, SHA `91997e38…`) without touching that file. ROW 0b's pin comes
from the DLL itself. The fix rides the next Developer task that touches `src/OpenWSFZ.Ft8/Native/`.

**NFR-021.** The bench is synthetic and Q-prefix only. The live band is the risk: ROW 0e is also the
privacy guard. §0.2 read C2's real logs in memory. This spec carries counts only. The report carries
counts, rates, doses and frequencies. `git check-ignore -v` every output path before committing, and
**scan the report prose** with `scan()`/`classify()`.

## §7. Running order and authorisation

| step | who | status |
|---|---|---|
| This spec | Architect | ✅ Captain: *"go with E4, spec it"* (2026-09-15) |
| Q1, Q2 | Captain | Q1 ✅ ratified (movable until the first `Δ`); Q2 granted 17:32Z for "right now", **not used (bench not ready); re-ask when armed** |
| Generator (`synth/`, DRIFT + FADE) and ROW 0a | QA | cleared: it is offline and needs no station time |
| Scenario file(s) and runner changes for §2.4 | QA | cleared, `--dry-run` only |
| Live bench run (ROW 0b–0g, blocks P and S) | QA | **waits on ROW 0a (A1), the dry-run, and then a fresh Q2 slot** |
| §3.6 → §3.5 → report, committed locally | QA | push/PR needs the Captain's go (HK-033) |

Where QA's commits land (`decoding_improvement` or their own branch) is QA's call under the Captain's
2026-09-15 workflow. This spec travels on `arch/e4-channel-impairments`.

🔴 **HK-025 is available in full.** If any row here is a diagnostic dressed as a gate, name it, evaluate
both branches, and refuse it.

---

## §8. Amendment A1: 2026-09-15 17:26Z (`date -u`), before any datum

**Trigger:** three build questions from QA (`qa-83`), about 17:1xZ. No `Δ`, no decode and no bench
render existed when this was written. It changes generator verification, one generator rule and the
message pool. **It does not change `BAR_E`, F1–F4, ROW 0b–0g, the doses, the blocks or the trial
counts.** Every original line it replaces is struck where it lives (§2.3, §2.4, §3.2).

### 8.1 Message pool: append five, specified here

`study-messages.json` holds 10 standard messages (`MSG-01`…`10`). The other two (`T4`/`T1`) are the
hash-resolution pair, and §2.4 bars them. **QA appends these five, exactly as written.** Each is a
standard Type-1 message with two Q-prefix calls, and no hash, `/P` or `/R`:

| id | text | type |
|---|---|---|
| `MSG-11` | `Q2GHI Q1ABC R-12` | R-report (the `ir` bit is set; no existing message sets it) |
| `MSG-12` | `Q1ABC Q2GHI RRR` | RRR (the packer supports it; no existing message uses it) |
| `MSG-13` | `Q6MNO Q4XYZ IO91` | grid |
| `MSG-14` | `Q4XYZ Q6MNO R+05` | R-report, positive |
| `MSG-15` | `Q7STU Q3PQR 73` | 73 |

**No new CQ.** WSJT-X applies its CQ a-priori pass to any CQ, whatever its own call is, so the pool
keeps one CQ in 15. The rotation balances it across doses anyway. `used_in: ["E4"]`. Adding `"E4"` to
`MSG-01`…`10`'s `used_in` is optional (it is metadata only).

**Why appending is safe, checked:** `run_scenario.py:_load_scenario` resolves messages **by id** from
each scenario's own pool. The only reader that loops over the whole file is `gate_render.py`, which
renders one gate WAV per message, so appending only **adds** five WAVs. ROW 0a(i), run after the
append, proves it mechanically.

**Before station time:** OpenWSFZ must decode each new text offline from its gate WAV, by any path
QA already uses. A bad encoding must turn up there, not as a ROW 0d VOID after two hours of station
time (one bad message in 15 caps dose-0 recovery at 140/150 = 0.933 < 0.95).

### 8.2 ROW 0a(ii) DRIFT: a differential. QA's reading is right, and the original wording was wrong

The original asked for an **absolute** fit of the instantaneous frequency. FT8's own tone sequence has a
trend, which is several Hz on a real message (QA measured it). So the original dose-0 check
(`< 0.01 Hz`) would have STOPped a perfect generator. That was my defect, and QA's differential is
what the row was for. **Replacement (predicate as code):**

```
y_u = render(tones, f0, drift_hz=0)          # noiseless, same tones, same f0
y_d = render(tones, f0, drift_hz=±delta)     # noiseless
dphi = unwrap(angle(hilbert(y_d) * conj(hilbert(y_u))))
df   = diff(dphi) * fs / (2*pi)              # Hz, instantaneous-frequency difference
trim the first and last symbol (click ramp + Hilbert edge)
slope, mean from a least-squares line of df against t

PASS iff, at every dose and BOTH signs:
  |slope * T_tx - signed_delta| <= 0.02 * |delta|        # the dose, sign included
  |mean(df)|                    <  0.01 Hz               # centring (§2.2): mean frequency unchanged
and dose 0: y_d is byte-identical to y_u                 # stronger than the old < 0.01 Hz
```

What this cannot see (HK-022): the drifted and undrifted paths sharing one defect. ROW 0a(i) covers
that: the default path must be byte-identical to `origin/main`.

### 8.3 ROW 0a(iii) FADE: pooled seeds, plus two checks through the bench's own call

**Two defects in the original, both mine. I checked both by simulation on a copy of QA's
`_shaped_gaussian_process`** (Architect scratch; nothing written into QA's tree).

**(1) Single-draw noise, which QA flagged at `B` = 0.1. It is wider than 0.1.** Here are the rates at
which one 2,000 s draw of a **correct** generator fails each sub-check (200 draws per `B`):

| `B` (Hz) | power ±3% | `|corr|` < 0.05 | spread ±10% |
|---|---:|---:|---:|
| 0.1 | **47%** | **44%** | 0% |
| 0.25 | **27.5%** | 9.5% | 0% |
| 0.5 | 9.5% | 0% | 0% |
| 1 | 1.5% | 0% | 0% |
| 2 | 0% | 0% | 0% |

Across the ladder, the original row STOPs a correct generator about **80%** of the time. That is a
tolerance set below the estimator's own noise (HK-021(o)). The analytic power sd at 0.1 Hz is 0.038
(one process's time-average of `|g|²` has relative variance `1/(√π·B·T)`; the two paths halve it). The
simulation measured 0.041.

**(2) The 2,000 s carrier cannot see the defect that matters (HK-022, HK-026).** `modulate_faded`
shapes `g1` and `g2` on a buffer exactly one transmission long (`n = len(z)`). Frequency-domain
shaping is circular, so the process's end wraps onto its start. The true correlation between the
gain at the first and last sample is ≤ 4×10⁻⁴ at every `B`. **The current generator gives 0.89–1.02 at
every `B`** (300 seeds). At 0.1 Hz the whole transmission is distorted. At 20 Hz only the ends are, but
those are Costas arrays 1 and 3. The check ran on a 2,000 s buffer, where the wrap sits 2,000 s away,
so it could never see this.

**Generator rule, added to §2.3:** each `g` is generated on `L ≥ T_tx + 2/B` seconds, and the
transmission uses its first `n` samples. The wrap-around term is then `exp(−2π²) ≈ 3×10⁻⁹`. Cost: the
longest buffer is 32.64 s, at `B` = 0.1.

**Replacement ROW 0a(iii), all three STOP:**

- **(a) Spectrum and power, on a long carrier.** At every `B`: **K = 32** independent 2,000 s
  noiseless realisations, with the statistics **pooled** over the K. Measured 2σ of the **power**
  spectrum within ±10% of `B`. Pooled mean `|g1|² + |g2|²` within ±3% of 1. Pooled `|corr(g1, g2)|`
  < 0.05. The sample rate may be any rate ≥ 200 Hz (the process is defined in Hz), and the report
  states it. Predicted margin at 0.1 Hz: power sd 0.0072 (±3% ≈ 4.2 sd); `P(|corr| ≥ 0.05)` ≈ e⁻²⁸.
- **(b) No wrap, through the bench's own call.** Use the function `modulate_faded` itself calls to
  make `g1` and `g2`, with the bench's own arguments: 48 kHz, transmission length, and the §2.3
  buffer rule. Take seeds 0…399 from a seed space disjoint from the bench's, and pool both paths (800
  realisations). At every `B`, the ensemble `ρ(n − 1)` must be ≤ 0.20.
- **(c) The coherence the bench actually delivers.** On the same 800 realisations, the ensemble
  `ρ(1/(2B))` must be within **±0.05** of **`exp(−π²/8)` = 0.2910**. That target is the same at every
  `B`.

```
rho(lag) = | mean_r mean_t g_r[t+lag] * conj(g_r[t]) |  /  mean_r mean_t |g_r[t]|^2
```

**Both new checks pass where the generator is right, and fail where it is wrong (HK-021(z)).**
Simulation: 40 repeats of 400 seeds, at a reduced sample rate (the statistics depend on duration, not
rate):

| check | correct generator (with the buffer rule) | current `fade.py` | the `σ_h` bug QA fixed | `B` off by ±10% |
|---|---|---|---|---|
| (b) `ρ(n − 1)` ≤ 0.20 | mean 0.03, max 0.086 | **0.89–1.02 ⇒ STOP** | (not the target) | (not the target) |
| (c) `|ρ(1/2B) − 0.291|` ≤ 0.05 | sd ≤ 0.013 (0.1 Hz), max dev 0.031 | 0.288–0.316 (blind to the wrap; (b) catches it) | **0.539 ⇒ STOP** (analytic) | 0.225 / 0.368 ⇒ STOP (analytic) |

**Families that fire together:** 8 doses × 5 FADE sub-checks. Each is set at ≳ 3.8 sd, so a correct
generator passes the whole row with high probability. An unlucky STOP on a correct generator is
re-run once on fresh seeds, and the report says so. A second STOP is a defect.

### 8.4 What A1 does not change

`BAR_E` 0.10, F1–F4, ROW 0b–0g, the DRIFT and FADE dose ladders, blocks P/S, trial counts, N_BOOT and
its seed, the §4 predictions, and Q2. **No `src/` or `native/` change.**
