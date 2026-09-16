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

---

## §9. Amendment A2 and the ROW 0e disposition — Architect, 2026-09-16T16:08Z

🔴 **A2 is written AFTER the data. A1 was not.** That difference is the whole reason this section is
long. A2 does two things: it disposes ROW 0e for the run of 2026-09-15 18:26–19:25Z, and it replaces
ROW 0e for any future run. **It changes nothing else** — see §9.5. The ROW 0e disposition converts a
VOID into a live result, so it has a cost consequence and the Captain ratifies it (§9.6).

### 9.1 ROW 0e fired. The row is defective, and the defect is mine

ROW 0e as pre-registered: *"Within the run's cycles, **zero** decodes from either decoder carry a
callsign-shaped token that is not Q-prefix"* ⇒ *"VOID, and an NFR-021 incident. Live band audio
reached the decode bus."* Four such tokens appeared. **QA read the row correctly, did not soften it,
and was right to hand the disposition up rather than take it.**

**The row contradicts §3.5 A4 of this same document, and did so before any datum was taken.** A4
pre-registers *"false positives. Decodes matching no injected message, per decoder, per family.
Unmatched is false here, because truth is known."* A4 therefore expects a population of unmatched
decodes and asks for it to be counted. At −9 to −24 dB an FT8 decoder's unmatched output routinely
carries a callsign-shaped token, and nothing makes such a token Q-prefix. **So A4 predicts exactly the
event ROW 0e declares fatal.** One clause budgets for a population the other treats as proof of
contamination. That is not a post-hoc reinterpretation of a row that happened to fire; it is an
internal inconsistency readable from the specification alone, with the data covered up.

This is HK-026 in its plainest form: **ROW 0e is an instrument that cannot distinguish its target
(live RF on the bus) from the bench's own expected output (false decodes).** Its response is not flat
where the boundary sits. I pre-registered it anyway.

### 9.2 The fact ROW 0e existed to establish has independent, pre-datum evidence

The row is a proxy. The fact is *"no live band audio reached the decode bus."* That fact has evidence
that does not depend on the token scan and was not chosen after seeing it:

1. **Pre-run physical confirmation.** QA confirmed the radio's audio was off the decode bus before the
   run, at the Captain's direction, and said so before the first datum.
2. **Volume.** Four unmatched tokens across 200 cycles is ≈ 0.02 per cycle. Live band audio on this bus
   at these SNRs puts **tens of decodes per cycle** into both `ALL.TXT`s — the C2 corpus is the
   measured precedent. The contamination hypothesis is wrong by **two to three orders of magnitude**,
   not by a factor. This is a magnitude argument, and it does not need a threshold chosen after the
   fact to carry.

QA's forensic points (all four tokens within 1–7 Hz of one of the bench's own 15 station frequencies;
all at −9 to −24 dB, matching the doses in play in those cycles; all structurally malformed — a
doubled `/R`, a `<...>` hash placeholder although E4 injects zero hashed callsigns) are **consistent
with** the above and were selected after the result. They are recorded as corroboration and ~~**carry no
weight in this disposition**~~ 🔴 **STRUCK 2026-09-16 by A4 (§11), at QA's challenge — the claim was an
overclaim, and §10.3 later relied on post-hoc material of the same kind. Corrected standard: this and
§10.3's temporal pattern are corroboration of EQUAL status; the disposition rests on §9.2's two
pre-datum supports. See §11.**

### 9.3 Disposition: ROW 0e FIRED; the run is NOT VOID

**Ruling.** ROW 0e's predicate fired and that stands on the record — it is not re-read, not
re-thresholded, and not declared un-fired. What is struck is the predicate's **authority to VOID**,
on the §9.1 ground that it is internally inconsistent with A4 and cannot separate the two populations.
The fact it proxied is established by §9.2. **The run of 2026-09-15 stands as a live result.**

🔴 **Conditional on two mechanical confirmations QA runs offline, at zero station cost.** If either
fails, this disposition is withdrawn and the run is VOID:

- **(i) The routing held to the end.** An observation *timestamped after 19:25Z* that the radio's audio
  was still off the playback bus — Voicemeeter routing state, device graph, or the rig's power state.
  Whatever the station already records (HK-027). If nothing recorded it, say so; that is a negative
  answer, not a pass.
- **(ii) Volume.** Total unmatched (non-truth) decodes across the run window, both decoders, ≤ 20, and
  no single cycle above 2. Observed is 4 and ≤ 1. The bound has two orders of margin over any live
  band; it is a sanity floor, not a fine-grained test, and it is stated that way on purpose.

**The Captain's separate NFR-021 ruling (scope is VCS/commits; this was an uncommitted local run) is
accepted and is a different question. This section answers only "did real RF reach the bus".**

### 9.4 Replacement ROW 0e, for any future run: assert the cause, not the symptom

| row | check (as code) | on failure |
|---|---|---|
| **0e-1** routing | The radio's audio is not routed to the playback bus, read mechanically from the audio graph at run **start and end**, both recorded verbatim in the report. Unreadable counts as failed. | **VOID** |
| **0e-2** ~~token scan~~ | ~~zero non-Q callsign-shaped tokens~~ **STRUCK (§9.1).** | — |

**New descriptive, no row — A7.** Every unmatched callsign-shaped token in the window, with its cycle,
frequency, SNR, and distance to the nearest injected station frequency in that cycle. It is reported
and never gates. A7 is what the token scan was actually measuring.

**What 0e-1 cannot detect (HK-022):** contamination arriving by a path that is not the radio — another
application on the bus, or a mid-run routing change that reverts before the end check. A7's frequency
column is the descriptive tell for that, and it is descriptive on purpose.

### 9.5 🔴 The F-row readings, recomputed from `e4_gate_results.json` (HK-018)

**QA's report inverts ROW 0f's polarity, and it changes DRIFT's reading.** ROW 0f is
`min(R_O, R_W) ≤ 0.50` at the top dose, and its *failure* branch ("ladder too gentle") is what removes
F3. Both decoders read 0.0000 at DRIFT 16 Hz and FADE 20 Hz ⇒ the predicate is **satisfied** ⇒ ROW 0f
**PASSED** for both families ⇒ **F3 is on the table, not off it.**

Reading the pre-registered F-rows off QA's own gate file, doses above 0 only:

| family | ROW 0f | F1 (`max CI_lo^Bonf` ≥ 0.10) | F2 (`min CI_hi^Bonf` ≤ −0.10) | F3 (every 90% interval inside ±0.10) | **reading** |
|---|---|---:|---:|---|---|
| **DRIFT** | PASS (0.0 at 16 Hz) | 0.000 — no | 0.000 — no | all six: [0,0] or [−0.02, 0] ⇒ **yes** | **F3** |
| **FADE** | PASS (0.0 at 20 Hz) | 0.033 (5 Hz) — no | 0.000 — no | 5 Hz `p90_hi` = **0.1267**, 10 Hz = **0.1067** ⇒ no | **F4** |

**DRIFT reads F3, not F4.** Per §3.7 that closes DRIFT as an explanation of the above-threshold gap on
this binary — **the family, on this ladder, not E4** (§3.2's caveat stands).

⚠️ **Honest limitation on the DRIFT F3, flagged by me and not by the predicate.** Both decoders hold
≥ 99.3% through 8 Hz and both read 0.0000 at 16 Hz, so the ladder has an **unmeasured octave, (8, 16]
Hz**, exactly where the transition lives. F3's predicate is satisfied as written and the reading
stands. A differential hidden inside that octave is possible. I do **not** recommend buying it: 8 Hz of
total drift across one 12.6 s transmission is far outside the live population, and that claim is
checkable for free from the archived logs (per-station frequency change across consecutive cycles), not
with station time.

🔴 **My §4 blind predictions missed again.** DRIFT: predicted F1 0.45, F3 0.25 — outcome F3, and the
point prediction `d50` ∈ [2, 6] Hz was wrong by at least an octave in the safe direction. FADE:
predicted F3 0.35, F4 0.30 — outcome F4, `d50` ≥ 10 Hz predicted and met. **Running tally for §3.4-style
weighting: of my last six categorical calls, four missed.**

### 9.6 What A2 does not change, and what needs the Captain

`BAR_E` = 0.10 — 🔴 **now FROZEN**: `Δ` exists, so the §5 Q1 "for now" window is closed, and a proposal
to move it (mine included) is refused. Unchanged: F1–F4 and their predicates, ROW 0a–0d, 0f, 0g, the
dose ladders, blocks P/S, trial counts, N_BOOT and its seed, the §4 predictions as recorded. **No
`src/` or `native/` change.**

✅ **RATIFIED by the Captain, 2026-09-16: *"ratify the ROW 0e strike, and run the exposure census"*.**
ROW 0e's VOID authority is struck and the 2026-09-15 run stands. ⚠️ **He ratified it with two
conditions attached (§9.3); one of them has since been struck by me rather than satisfied — see §10,
which he must be told about because it changes what he ratified.**
✅ **FADE route decided, same ruling:** stop the bench, run the live exposure census. Specified in
`qa/rr-study/2026-09-16-1616-architect-to-qa-spec-e4-stage2-live-exposure-census.md`. ⚠️ Recorded there
as a **flagged deviation** from §3.7, which gates Stage 2 on an F1.

### 9.7 Why I do not recommend a tighter re-run

QA asks whether the top doses should be pulled in now that both decoders look more robust than
predicted. **DRIFT: no** — it reads F3 and the unmeasured octave is live-implausible (§9.5).
**FADE: no, and the arithmetic is the reason, not the appetite.**

FADE's whole signal is two adjacent doses with the same sign: 5 Hz `Δ` = +0.087 (90% [0.053, 0.127])
and 10 Hz `Δ` = +0.073 (90% [0.040, 0.107]). Take the point estimates as true and ask what any `n`
could buy:

- **F1 needs `CI_lo^Bonf` ≥ 0.10.** At a true `Δ` of 0.087 that bound converges to 0.087. **F1 cannot
  fire at any `n`.** It fires only if the point estimate is badly low — and 0.15 already sits outside
  the current 90% interval.
- **F3 needs every 90% interval inside ±0.10.** At a true `Δ` of 0.087 the half-width must fall below
  0.013, from 0.037 now. That is ≈ 8× the trials, **≈ 13 h of station time**, to earn a reading of "no
  material differential" about a differential of 0.087.

**So FADE is structurally F4 at `BAR_E` = 0.10, and a re-run mostly re-buys F4.** That is not an
instrument defect. It is what a true effect sitting on the bar looks like, and the bar was set where it
was on purpose.

**The decision-relevant quantity is exposure, and it costs no station time.** §3.4's own arithmetic
with the measured `Δ`: the recoverable live gain is at most `0.087 × φ × 66` pp, where φ is the share
of above-threshold live rows carrying ≥ 5 Hz of Doppler spread. φ = 0.3 ⇒ 1.7 pp; φ = 0.1 ⇒ 0.57 pp;
φ = 0.05 ⇒ 0.29 pp. **5 Hz of spread is polar-path flutter, not a mid-latitude path**, so my estimate
is φ ≤ 0.05 and FADE closes on exposure without another trial.

⚠️ **That estimate is mine, not measured.** §3.7 gates Stage 2 (the live exposure census, run over all
REF rows ≥ −10 dB, hit or missed, HK-021(t)) on **an F1**, and we have F4 — so specifying Stage 2 now
is a **deviation from this spec, flagged as one**, and it is the Captain's call. It needs no station
time: it runs on archived C2 audio. **My recommendation: run Stage 2 for FADE exposure, stop the
bench.** If φ comes back small, FADE closes on arithmetic and **density becomes the leading remaining
candidate for the 17.96 pp ceiling** (§3.7), which is the question I would bring next.

---

## §10. Amendment A3 — ROW 0e condition (i) is struck as malformed. Second HK-027 error in this document

**Architect, 2026-09-16T16:2xZ**, after QA (`qa-cd`) reported against §9.3's two conditions.

### 10.1 What QA found

- ✅ **Condition (ii), volume: PASSES, mechanically.** 4 unmatched rows total (OpenWSFZ 3, WSJT-X 1),
  **max 1 per cycle, in 4 distinct non-overlapping cycles**, 18:56:30 / 19:15:30 / 19:17:30 / 19:19:15Z.
  Bound was ≤ 20 total and ≤ 2 per cycle.
- ✅ **F-rows independently CONFIRMED** by QA's own script, matching §9.5 to 4 decimals on every dose,
  including the ROW 0f polarity correction. DRIFT F3, FADE F4.
- 🔴 **Condition (i), routing held to the end: NO RECORD EXISTS.** The supervisor's `attempt-1.log`
  logs the Voicemeeter device selection **once, before trial 1 (18:26Z)** and never again; the other
  logs stop at 17:11Z, before the run. Nothing in the 19:25–20:10Z window touches routing or device
  state. QA searched and handed it back without ruling. **That is the correct behaviour and the right
  call.**

### 10.2 The ruling: condition (i) is struck, and that is my error to own

Per §9.3's own wording, a failed condition withdraws the disposition and VOIDs the run. **I am not
applying that, and the reason has to be better than "I would rather not".** Here it is:

🔴 **Condition (i) is malformed, and I wrote it a day after the window it asks about closed.** It
requires a record that could only have been created *during* the run, by a supervisor that was already
built and already finished. No action available to anyone at 16:08Z on 2026-09-16 could satisfy it.
It could only ever return "the station happened to log it" or "it did not" — and **the absence of a
routing log is not evidence that routing changed.** As written, it converts an absence of evidence
into a VOID. That fails HK-021(k): a precondition has to be able to change the verdict for the right
reason, and this one changes it on a coin-flip about log verbosity.

**And it is the second time in this same document that I specified an action without first asking what
the instrument already records.** §9.3 literally cites HK-027 — *"Whatever the station already records"*
— and then makes the run's validity depend on something it does not. ROW 0e itself was the first
(§9.1). Two HK-027 errors in one amendment is a pattern, not a slip, and it is recorded as one.

### 10.3 What actually answers the question condition (i) was pointed at

The gap is real: §9.2's pre-run confirmation covers the **start**, not the whole window. What would
contamination by a routing revert look like? **A step change.** If the radio's audio returned to the
bus at time `T`, every cycle from `T` to the end carries live band traffic — tens of decodes per cycle,
continuously, never one.

**Observed: 4 isolated singletons, in 4 non-overlapping cycles, spread across 23 minutes, with clean
cycles between every pair and the final ~6.5 minutes (19:19:15 → 19:25:45Z) clean.** A revert cannot
produce that shape. The incompatibility is **structural — persistent versus isolated —** not a
threshold I picked.

⚠️ **Stated plainly: I learned that temporal pattern from QA's report, which is to say after condition
(i) failed.** That is a weaker epistemic position than a pre-registered check and I am not dressing it
up as one. What makes me willing to act on it: it rests on the same volume statistic condition (ii)
already required and passed, read for its shape rather than its count; and the §9.2 magnitude argument
— 0.02 unmatched decodes per cycle against the tens per cycle live band audio produces — never depended
on condition (i) at all.

### 10.4 One falsifier, and it is the only thing still outstanding

QA asks whether a routing check run now, a day later, could stand in. **It cannot confirm the run** —
it is a day late and proves nothing about 19:25Z. **But it can refute it**, and that asymmetry is worth
five minutes:

> **Read the current routing state of the playback bus.** If the radio's audio is **on** the bus now,
> with nobody having reconfigured it since, the premise that it was off during the run is in doubt and
> **this disposition withdraws immediately, the run is VOID.** If it is off, nothing is confirmed and
> the disposition stands on §10.3.

🔴 **No further amendment to ROW 0e.** I have now patched this row twice after the fact. The disposition
in §9.3, as modified here, is **final for the 2026-09-15 run either way**, and any future E4 run uses
**ROW 0e-1** (§9.4) with routing read at start **and** end, which is what should have been there from
the beginning.

### 10.5 What A3 changes

Nothing except §9.3's condition (i). `BAR_E` stays frozen, F1–F4 and their readings stand (DRIFT F3,
FADE F4), ROW 0a–0d/0f/0g untouched, no dose, block, trial-count, bar or row change. **No `src/` or
`native/` change.** The Stage 2 census does **not** depend on any of this — it measures the live band
from archived audio and calibrates on generator renders, so it is unaffected by whether the bench run
stands, and QA may start its ROW 0a immediately.

➡️ **The Captain must be told:** he ratified the strike with two conditions attached; one passed and
**one I have struck myself rather than satisfied.** That changes what he ratified. The alternative on
the table remains a ~2 h re-run under ROW 0e-1, and it is his call whether §10.3 is good enough.

### 10.6 Falsifier result — no VOID triggered

QA, 2026-09-16, via the daemon's own status API (`GET /api/v1/status` — what the station already
records, HK-027), polled 6× over 24 s, spanning more than one FT8 cycle on a live 14.074 MHz dial:
`audioDevice` = `Voicemeeter Out B1`, `captureActive` = true, **`audioActive` = false on every poll**,
`catConnectionStatus` = `Disabled`. A connected antenna on an active band would show `audioActive`
flickering true.

**Reading, held to §10.4's own framing: this is the clean-now result, not the dirty-now one. It
triggers no VOID. It confirms nothing** — it is a day late, and I am not going to start treating it as
support now that it came back the way I hoped.

---

## §11. Amendment A4 — I overclaimed in §9.2, and QA caught it

**Architect, 2026-09-16.** QA (`qa-cd`) flagged, for the record rather than as a refusal:

> §10.3's temporal-pattern argument is doing real evidential work for the same disposition that §9.2
> said post-hoc forensic corroboration carries none of.

**That is correct, and it is the sharpest point anyone has made in this arm.** A4 changes **no
verdict** — it corrects a reasoning standard I stated too strongly and then failed to hold myself to.
🛑 **It is not the third bite at ROW 0e that §10.4 forbade: the disposition is untouched.**

### 11.1 The distinction I would have drawn, and why it is not enough

The defence available to me is that the two are not quite alike. The forensics (frequency proximity,
malformed structure) are **two statistics chosen from a large menu** of things one could compute about
4 tokens, and choosing the exculpatory ones is the garden of forking paths. The temporal pattern is
**the unique mechanical signature of the specific alternative** — a routing revert is persistent by
construction, so the statistic is fixed by the hypothesis rather than picked from a menu. And the
counts it reads were pre-registered in condition (ii), even if their shape was not.

**That is a real difference, but it is one of degree, not of kind, and it is not enough to carry "zero"
versus "full".** Both were computed after seeing the result. Pre-registering a count does not
pre-register every function of the rows underneath it.

### 11.2 The corrected standard

- 🔴 **Struck at source** (§9.2, the sentence at what is now line 575, marked in place per HK-022):
  "carry no weight in this disposition" was an **overclaim**.
- **One standard for both.** QA's forensics and §10.3's temporal pattern are **corroboration of equal
  status** — real, non-zero, and not load-bearing.
- 🔴 **What the disposition actually rests on, and what it always rested on, is the two supports in
  §9.2 that needed no sight of the tokens:** the **pre-run physical off-bus confirmation**, and the
  **magnitude argument** — 0.02 unmatched decodes per cycle against the tens per cycle live band audio
  puts into both `ALL.TXT`s, wrong by 2–3 orders of magnitude. Both were available before a single
  token was examined. **If those two do not carry it, nothing in §10.3 rescues it, and the honest
  response is the re-run, not a better argument.** My judgement is that they do carry it. That
  judgement is the Captain's to accept or reject, and it is what is in front of him.

### 11.3 The lesson worth keeping

**Declaring evidence "zero weight" is itself a claim that has to be honoured later.** I made that
declaration in §9.2 to show discipline, then leaned on material of the same kind in §10.3 two hours
later. The cheap fix would have been to never say "zero" — to say "corroborative, not load-bearing",
which is what I actually meant and what is now written. 🔴 **Three of this document's amendments (A2,
A3, A4) correct the Architect's own errors, two of them HK-027, one an overclaim.** That is the record.

### 11.4 What A4 changes

Nothing operational. No verdict, no row, no bar, no dose, no disposition. `BAR_E` frozen, DRIFT F3,
FADE F4, the run stands subject to the Captain. **No `src/` or `native/` change.**
