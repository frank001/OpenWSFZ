# `E4-STAGE2` — pre-registration: how often does the live band actually present the impairment doses the bench found, on signals we should be decoding?

**Architect, 2026-09-16T16:16Z** (`date -u`, HK-017). Branch `arch/e4-channel-impairments` (the E4
workstream's branch — the bench, its amendments and this census are one arm, one branch). Docs-only;
`git diff --stat origin/main...HEAD -- src/ native/` is empty.

**Status: cleared to run, after §5 Q1.** The Captain, 2026-09-16: *"ratify the ROW 0e strike, and run
the exposure census"*. ⚠️ **This is a flagged deviation from the bench spec's own §3.7**, which gates
Stage 2 on an F1 and we have F4. The Captain licensed it knowing that. It is recorded here so nobody
later reads Stage 2 as having been authorised by the bench's own logic — **it was authorised by the
Captain over that logic.**

**It needs no station time.** It runs entirely on archived C2 audio and archived `ALL.TXT`s.

---

## §0. What this is, and why it is the question that actually decides FADE

### 0.1 The one-line reason

The bench (`E4-BENCH`, 2026-09-15) measured **how much** we lose at a given dose. It cannot say **how
often** that dose occurs. FADE's measured differential is `Δ` = 0.087 at 5 Hz of Doppler spread, which
sits on `BAR_E` = 0.10 and is **structurally unresolvable by more bench trials** (§9.7 of the bench
spec: F1 cannot fire at any `n`, F3 needs ≈ 13 h of station time). So the bench cannot close FADE and
cannot open it either. **Exposure can close it**, and exposure is free.

### 0.2 The arithmetic that makes exposure decisive

From the bench spec §3.4, with the measured `Δ` substituted: the most live recovery a perfect fix for
FADE fragility could buy is

```
gain_pp  <=  Delta  x  phi  x  66 pp
```

where 66 pp is C2's share of REF rows at ≥ −10 dB (60,239 of 91,046, bench spec §0.2) and **φ is the
share of those rows that actually carry ≥ 5 Hz of Doppler spread** — the only thing here we have never
measured.

| φ | gain at `Δ` = 0.087 | gain at `Δ` = 0.127 (the 90% upper) |
|---:|---:|---:|
| 0.30 | 1.72 pp | 2.51 pp |
| 0.12 | 0.69 pp | **1.01 pp** |
| 0.05 | 0.29 pp | 0.42 pp |
| 0.01 | 0.06 pp | 0.08 pp |

**φ swings the answer by more than an order of magnitude, and `Δ` does not.** That is why this runs
and another bench run does not.

### 0.3 What it reuses

| piece | where | note |
|---|---|---|
| Corpus C2 audio | `artefacts/20260908_live_run_1827-fp-floor-live-2/cycle-audio/` | **verified while drafting: 5,495 WAVs, 1.9 GB, 12 kHz mono, 15.0 s each** — full coverage of the 601-cycle valid population |
| REF decodes | same corpus, `wsjtx-1-ft991a/ALL.TXT` | ⚠️ `[4]` SNR, `[5]` DT, `[6]` frequency Hz. Confusing 5 and 6 inverts the result. |
| Encoder | `qa/rr-study/synth/encoder.py` | re-encodes a REF message to its 79 tones, which is what makes the channel estimate possible |
| FADE generator + bench renders | `qa/rr-study/synth/` (A1's `fade.py`, buffer-rule fixed) | **this is the calibration source — ROW 0a. Truth is known there.** |
| Matcher | `live-gap-now/matcher.recovery()` | only to label a row hit/missed by us. Reproduces `R_wild` 61.09% to the digit. |

🛑 **No `src/` or `native/` change. No Developer session. No decoder is run — this measures the
channel, not a decode.**

---

## §1. The estimator, and the blind spot it has by construction

### 1.1 What is extracted

For a REF row we know the message, so we know its exact 79-symbol tone sequence. At the row's known
frequency and DT, correlate the archived audio against each transmitted tone over its own symbol
window. That yields a **complex channel gain per symbol, `g[1..79]`**, sampled at one per 0.16 s, i.e.
**6.25 Hz**.

From `g`:
- **Fading:** `ρ₁` = the magnitude of the lag-1 autocorrelation of `g`, normalised — how much the
  channel decorrelates between adjacent symbols.
- **Drift:** the fitted linear trend of `arg g` across the transmission, expressed as **total Δf in Hz
  across the 12.6 s**, which is the bench's own DRIFT dose unit.

### 1.2 🔴 The blind spot, stated before the data (HK-026)

**A channel sampled at 6.25 Hz has a Nyquist limit of 3.125 Hz.** The dose that matters — 5 Hz spread —
is **above** that limit. `ρ₁` is monotone in `B` at low spread and then **saturates**: ~~somewhere around
3 Hz it reaches the floor and a 5 Hz channel becomes indistinguishable from a 15 Hz one.~~

🔴 **STRUCK 2026-09-16 by B1 (§8.3) — this was PESSIMISTIC and measurably wrong.** ROW 0a measured
median `ρ₁` at −8 dB: `B` = 1 → 0.861, 2 → 0.647, **5 → 0.215**, 10 → 0.132, 20 → 0.096, against a
statistic floor of ≈ 1/√79 = 0.112. **5 Hz is cleanly separated from both ≤ 1 Hz and from 10 Hz.**
Saturation onset is ≈ 10 Hz, not 3 Hz. 🛑 **Never cite "the estimator is blind above 3 Hz."**
**The one-sided reading below is UNCHANGED, but it now rests on leg (1) alone** — live corruption
biases `ρ₁` down — **not on saturation.**

**So this instrument cannot measure φ. It can only bound it.** Two things make that acceptable, and
both must survive ROW 0a or the census does not run:

1. **The saturation is one-sided in the safe direction.** Everything that corrupts `g` — additive
   noise, a neighbouring station's energy inside the correlation window, a DT or frequency error —
   pushes `ρ₁` **down**, which looks like *more* fading. So the share of rows reading "saturated" is an
   **upper bound** on φ, never an underestimate.
2. **Therefore the census has exactly one closing reading: "φ is small".** If the bound comes back
   large, that is **not** evidence that fading is common — it is the instrument failing to resolve, and
   the reading is UNRESOLVED (§3.2 E3). 🛑 **A large `φ_upper` may never be cited as live fading
   exposure.**

### 1.3 The consequence for the §3.7 spectral-locality question — WITHDRAWN, not asked

The bench spec §3.7 said Stage 2 would need a Captain ruling before excluding overlapped signals as an
estimator-validity filter, because that sits close to the closed spectral-locality bar. **That question
is withdrawn as unnecessary, and no such exclusion is performed.** Per §1.2(1), a neighbour's energy in
the window biases `ρ₁` down, i.e. biases `φ_upper` **up**, which is the conservative direction for the
only reading that can close anything. **So the filter buys nothing a one-sided bound needs, and the
population stays whole.** Neighbour distance is not computed, not stratified on, and not reported.

If and only if the census reads E3 (unresolved) does that question come back, and then it comes back to
the Captain before anything else happens.

---

## §2. Population

- **Frame:** every REF row in C2's valid population (from the `19:36:45Z` Amendment-3 boundary) with
  REF SNR **≥ −10 dB**. Per bench spec §0.2 that is **60,239 rows**.
- **Hit or missed by us is not a selection criterion** (HK-021(t)). Our hit/miss is *recorded per row*
  and used only in the descriptive D3. The population is fixed before any decode outcome is looked at.
- **Sample:** a simple random sample of **5,000** rows, `numpy.random.default_rng(20260916)`, drawn
  from the frame **before** any audio is read. At φ = 0.10 the standard error is 0.0042, so the bar in
  §3.1 is ≈ 5 standard errors away — resolution is not the constraint here, the estimator is.
- **Re-encodable only.** A row whose message cannot be re-encoded to a unique tone sequence — a hashed
  `<...>` callsign, a malformed line — is dropped, because there is no known waveform to correlate
  against. 🔴 **Report the dropped share. If it exceeds 5%, stop and tell the Architect before
  computing φ** — at that size the drop is a population change, not a rounding detail.
- **Q-prefix rule:** callsigns from this corpus are real. 🔒 **NFR-021: no callsign, and no `ALL.TXT`
  excerpt, enters version control.** Work in `artefacts/` (blanket-gitignored) and scan the report's
  **prose** as well as its data files before committing anything.

---

## §3. Rows

### 3.0 ROW 0a — calibration, and it is the whole ballgame (STOP)

🔴 **Run the estimator on the bench's own FADE renders, where `B` is known by construction, before it
ever touches live audio.** At every FADE dose (0.1, 0.25, 0.5, 1, 2, 5, 10, 20 Hz), at **both** −8 dB
and 0 dB, ≥ 50 trials per cell, using the A1-fixed `fade.py` with the buffer rule.

| sub-row | check (as code) | on failure |
|---|---|---|
| **0a(i)** monotone | median `ρ₁` is strictly decreasing in `B` across 0.1 → 2 Hz at −8 dB | **STOP** |
| **0a(ii)** separation | a threshold `ρ*` exists such that at −8 dB, P(`ρ₁` < `ρ*` \| `B` = 5 Hz) ≥ 0.90 **and** P(`ρ₁` < `ρ*` \| `B` ≤ 1 Hz) ≤ 0.10. **`ρ*` is fixed here, from bench data only, and never touched again.** | **STOP — and report that the census cannot answer the question.** That is a legitimate outcome, not a failure to be worked around. |
| **0a(iii)** saturation, named | report the `B` at which median `ρ₁` comes within 10% of its `B` = 20 Hz value. **This is the number that defines the blind spot; it goes in the report whatever it is.** | no STOP — it is a disclosure |
| **0a(iv)** null passes where it holds (HK-021(z)) | on the **undistorted** renders (no FADE, no DRIFT) at −8 dB, median `ρ₁` ≥ 0.90, and the drift estimator returns \|Δf\| < 0.5 Hz | **STOP** |

**Why 0a changes the verdict (HK-021(k), both branches):** with 0a(ii) passed, a row reading
`ρ₁` < `ρ*` is a row the bench's own 5 Hz dose would have produced ≥ 90% of the time, so counting those
rows means something. With 0a(ii) failed, `φ_upper` is a count of an unknown thing and no φ may be
reported at all.

### 3.1 The reading (first match wins)

Let **`φ_upper`** = the share of sampled rows with `ρ₁` < `ρ*`, and **`BAR_φ` = 0.12** (§5 Q1).

| row | predicate | reading |
|---|---|---|
| **E1** | ROW 0a passed **and** the 95% upper confidence limit on `φ_upper` < `BAR_φ` | **FADE CLOSES on exposure.** The dose exists on the bench but not on the band, at a rate that could buy ≥ 1 pp. |
| **E2** | ROW 0a passed **and** the 95% **lower** limit on `φ_upper` ≥ `BAR_φ` | **Exposure is not small enough to close FADE** — and per §1.2 this is *not* a finding that fading is common. It is E3 with a direction. Back to the Architect and the Captain. |
| **E3** | otherwise, including any ROW 0a STOP | **UNRESOLVED.** |

**Why `BAR_φ` = 0.12:** it is the φ at which a perfect FADE fix buys **1.01 pp** using the *favourable*
end of `Δ` (its 90% upper, 0.127) — §0.2's table. Below it, the fix cannot reach 1 pp even if every
assumption breaks our way, and PASSBAND-140's entire shipped ceiling was 2.1 pp. Choosing the favourable
end of `Δ` makes the closure conservative on purpose: we close FADE only when it cannot pay off even
under its best case.

### 3.2 DRIFT, on the same extraction, nearly free — and it closes the bench's one open hole

The bench's DRIFT F3 carries one Architect-flagged limitation: both decoders hold ≥ 99.3% through 8 Hz
and both read 0 at 16 Hz, so **the octave (8, 16] Hz is unmeasured**, and that is where the transition
lives. The claim that this does not matter is that ≥ 8 Hz of drift across one transmission is not a
live population — **asserted by me, never measured.** This census measures it directly.

| row | predicate | reading |
|---|---|---|
| **E4** | ~~ROW 0a(iv) passed, and the 95% upper limit on the share of sampled rows with \|Δf\| ≥ 8 Hz is **< 0.005**~~ 🔴 **SUSPENDED by B1 (§8) — the drift estimator ALIASES at exactly this threshold.** Re-armed unchanged once ROW 0a(v) passes. | **The (8,16] hole is formally dismissed and DRIFT's F3 closure stands without the caveat.** |
| **E5** | otherwise | **The caveat stands as written.** The hole stays open, and re-opening it becomes a real question rather than a theoretical one. |

🛑 **E4 and E5 MAY NOT BE COMPUTED until ROW 0a(v) passes (§8).** The predicates and the 0.005 bar are
unchanged; only the instrument underneath them is being replaced.

### 3.3 Descriptive, no row (report every one)

- **D1:** the full distribution of `ρ₁`, and of total \|Δf\|, over the sample — not just the shares.
- **D2:** both, broken out by REF SNR band using §0.2's bands. The noise floor pushes `ρ₁` down, so the
  weakest band should show the largest `φ_upper` **for reasons that are not fading** — that gradient is
  itself a check on how much of `φ_upper` is instrument.
- **D3:** `ρ₁` and \|Δf\| distributions for rows **we missed** vs rows **we hit**. 🛑 **Descriptive
  only, and it may not be cited as a cause.** It is confounded by SNR, and this arm has no design that
  separates them.
- **D4:** the dropped (non-re-encodable) share, per §2.
- **D5:** the sample's SNR-band composition against the frame's, to show the draw was not skewed.

### 3.4 ⚠️ What this cannot detect, in addition to §1.2 (HK-022, HK-026)

- **Anything about signals WSJT-X did not decode.** REF *is* WSJT-X's decodes, so a signal faded past
  even its reach is absent from the frame. That is the correct population for this question — our gap
  is defined against WSJT-X — but it means φ is **exposure among decodable signals**, not among all
  signals, and it must be written that way every time it is cited.
- **One corpus, one antenna, one 22-hour window, one season, mid-latitude.** φ is not a constant of
  nature. A polar path in a disturbed ionosphere is exactly where 5 Hz spread lives, and C2 contains
  none of that by construction.
- **Density.** Still untouched, still the other candidate for the 17.96 pp ceiling.

---

## §4. Architect predictions: blind, on the record, before any datum

| quantity | prediction |
|---|---|
| ROW 0a(ii) separation passes at −8 dB | 0.70 |
| 0a(iii) saturation point | 2.5 – 3.5 Hz |
| **E1 (FADE closes on exposure)** | **0.65** |
| E2 | 0.10 |
| E3 (unresolved, incl. 0a STOP) | 0.25 |
| `φ_upper` point value | **0.02 – 0.08** |
| **E4 (drift hole dismissed)** | **0.85** — I expect essentially no live row at ≥ 8 Hz total drift |
| dropped share (§2) | 2 – 4% |

🔴 **Weight these accordingly: of my last six categorical calls in this programme, four missed**, most
recently DRIFT, where I gave F1 0.45 and it read F3 with both decoders ≥ 99.3% through 8 Hz. The two
predictions above that I would defend hardest are E4 and the saturation point, because both are
arithmetic rather than judgement.

---

## §5. PO question — before the first datum only

- **Q1: `BAR_φ` = 0.12?** It is Architect-set, by the §3.1 reasoning, and it is the number that decides
  whether FADE closes. Like `BAR_E` it is movable **until QA produces the first `φ`** and frozen after;
  a move proposed once φ is known is refused and VOIDs the census. **No other PO input is needed — this
  arm costs no station time and touches no shipped code.**

## §6. What this arm does NOT do

- It does **not** license any treatment. An E1 closes FADE; it does not open anything.
- It does **not** re-open the bench. `BAR_E` is frozen and no further bench trials are authorised.
- It does **not** run or modify a decoder, and produces no decode-rate figure.
- It does **not** touch density. That is the next question, and it is not this one.

## §7. Ownership and sequence

| step | owner | gate |
|---|---|---|
| The bench's ROW 0e conditions | QA | ✅ **Settled 2026-09-16, bench spec §10 (A3):** (ii) volume PASSED; (i) struck as malformed. One falsifier left — read the playback bus's current routing state (§10.4). 🔴 **None of it gates this census**, which calibrates on generator renders and measures live audio; it is independent of whether the bench run stands. |
| ROW 0a calibration on bench renders | QA | STOP rows; nothing live is read until it passes |
| §5 Q1 `BAR_φ` | Captain | the census may compute ROW 0a without it, but **no φ before it is ratified** |
| The census itself (§2, §3) | QA | after ROW 0a and Q1 |
| Acceptance ruling, E1–E5 | Architect | — |

**HK-025 applies: QA may refuse any row here on mechanical grounds without my agreement.** ROW 0a(ii)
is the one I most want argued with if it looks unworkable — it is doing all the load-bearing work.

---

## §8. Amendment B1 — the drift estimator aliases at exactly the threshold E4 gates on

**Architect, 2026-09-16, after QA's ROW 0a report.** ROW 0a **PASSES**. B1 suspends E4/E5, replaces the
drift estimator, adds ROW 0a(v)–(vi), and corrects §1.2. **`BAR_φ`, `ρ*`, `BAR` 0.005, E1–E3 and the
population are untouched.**

### 8.1 What ROW 0a returned

| sub-row | result |
|---|---|
| **0a(i)** monotone | ✅ PASS — median `ρ₁` 0.970 / 0.962 / 0.943 / 0.861 / 0.647 across 0.1 → 2 Hz |
| **0a(ii)** separation | ✅ **PASS with room**: at `ρ*` = 0.577, P(`ρ₁` < `ρ*` \| 5 Hz) = **1.00**, P(\| ≤ 1 Hz) = **0.00**, against a 0.90 / 0.10 bar. `ρ*` = 0.577 is **now FIXED and never touched again.** |
| **0a(iii)** saturation | disclosed: `ρ₁` still falling at 20 Hz (0.132 → 0.096). Floor ≈ 1/√79 = 0.112, so it is at the floor by ~10 Hz. |
| **0a(iv)** null | ✅ PASS — median `ρ₁` 0.976, median \|Δf\| 0.007 Hz |

### 8.2 🔴 The defect QA found, which ROW 0a as written could not have caught

QA went past what 0a(iv) asked — it validates `drift_hz()` **only at drift = 0** — and ran the
estimator against the bench's **known DRIFT ladder**, because E4/E5 depend on that same estimator
reading real drift up to 8 Hz. Measured, −8 dB, n = 50 per dose:

| injected | 0 | 0.5 | 1 | 2 | 4 | **8** | **16** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **recovered (median)** | −0.002 | 0.501 | 1.001 | 1.998 | 3.997 | **3.305** | **2.893** |

**Exact through 4 Hz, then it folds.** This is not noise — it is the estimator's own Nyquist ceiling:
`g` is sampled once per symbol at 6.25 Hz, so the *instantaneous* offset is unambiguous only to
±3.125 Hz, which a linear ramp first violates at **6.25 Hz of total drift**. Onset matches to the Hz.

🔴 **The direction is what makes it fatal, and QA named it correctly: this biases LOW at exactly the
8 Hz line E4 gates on.** A row genuinely drifting 8 Hz reads back ≈ 3.3 Hz — **under** the threshold.
So E4 would fire, "the share is tiny, the hole is dismissed," **whether drift is rare or ubiquitous.**
It is the opposite of `φ_upper`'s safe one-sided bias, and it manufactures the reassuring answer.
**A row that can only return the comforting result is not a check** (HK-021(k), HK-026).

**And I had already written the argument that kills it, two sections earlier.** §1.2 derives the
6.25 Hz sampling limit and reasons carefully about what it does to `ρ₁` — then §3.2 builds E4 on a
second statistic drawn from *the same samples* without applying it. 🔴 **Named lesson: a sampling limit
applies to EVERY consumer of the limited quantity, not just the one you were thinking about when you
found it.** That is the error, and it is mine.

### 8.3 What is corrected, and one piece of good news

- **§1.2's saturation claim is struck in place** (marked there, HK-022). It was pessimistic: 5 Hz reads
  0.215 against a 0.112 floor and separates cleanly from 10 Hz. **Saturation onset ≈ 10 Hz, not 3 Hz.**
- 🔴 **The one-sided reading is UNCHANGED** — `φ_upper` is still only an upper bound and *"φ is small"*
  is still the only closing reading. But it now rests on **live corruption biasing `ρ₁` down** (noise,
  co-channel energy, DT/frequency error), **not on saturation.** A future reader citing "blind above
  3 Hz" is citing a struck claim.
- ✅ **FADE is NOT affected by the aliasing, and here is why, so the doubt does not spread:** `ρ₁` is a
  **magnitude**. A linear drift multiplies `g` by a near-constant phase rotation per sample, which
  rotates the lag-1 product without shrinking it. Second order, if drift pulls the tone off the
  correlation bin, `|g|` shrinks and `ρ₁` falls — **down, i.e. `φ_upper` up, the safe direction.**
  **E1–E3 proceed unchanged.**
- ✅ **Fading does not fake drift**, checked in QA's own data: on FADE-only renders with zero injected
  drift, the **share reading ≥ 8 Hz is 0.00 at every `B`**, max spurious \|Δf\| 2.2 Hz. So E4's
  threshold has ≈ 4× margin over fade-induced noise. The false-**positive** direction was already safe;
  it is the false-negative one that is broken.

### 8.4 Replacement drift estimator: no phase unwrapping, so no aliasing

**Split-window frequency difference.** No unwrapping anywhere, so there is no Nyquist ceiling to fold
across — the ambiguity limit becomes the **search range**, which we choose, and a row that pins at the
edge is **flagged out-of-range rather than silently folded**.

1. Sub-window **A** = symbols 1–26, sub-window **B** = symbols 54–79.
2. In each, estimate the frequency offset by maximising coherent correlation against that window's
   **known** tone sequence over a search grid of **±25 Hz**, coarse then fine, final step ≤ 0.05 Hz.
3. Centroids are 53 symbols apart out of 79, so
   **`Δf_total` = (`f_B` − `f_A`) × 79/53 = 1.491 × (`f_B` − `f_A`)**.
4. Any row whose `f_A` or `f_B` lands within 0.5 Hz of a search edge is **flagged out-of-range and
   counted separately**, never silently included.

### 8.5 New ROW 0a(v) — QA's check, promoted to a pre-registered gate

**It was QA's initiative that found this, so it becomes the row rather than staying an anecdote.**

| sub-row | check (as code) | on failure |
|---|---|---|
| **0a(v)** drift recovery across the range | At −8 dB, ≥ 50 trials, on the bench's own DRIFT ladder **0, 0.5, 1, 2, 4, 8, 16 Hz**: median recovered within **max(±0.5 Hz, ±10%)** of injected **at every dose, 8 and 16 Hz included**; and at dose 0, median \|Δf\| < 0.5 Hz. | **STOP.** E4/E5 stay suspended and the §9.5 DRIFT caveat stands unmeasured. A second failure means the census cannot answer the drift question, which is a legitimate outcome — **do not widen the tolerance to pass it.** |
| **0a(vi)** drift under fade, **disclosure only** | Drift recovery at injected 8 Hz combined with FADE `B` = 1 Hz and `B` = 5 Hz, if the generator composes the two cheaply. If it does not, **say so** — the combined case is then untested and that goes in the report. | no STOP |

**Why 0a(v) changes the verdict (both branches):** passed, a small measured share at ≥ 8 Hz means drift
really is rare and E4 means something. Failed, the same small share means nothing at all, which is
precisely today's defect.

### 8.6 Sequence

- **E1–E3 (FADE) are unaffected** and still gated only on `BAR_φ`, which is still with the Captain.
- **E4/E5 (DRIFT) wait on 0a(v).**
- QA's next step is the replacement estimator and 0a(v), which needs no live audio and no `BAR_φ` — so
  it runs in parallel with the Captain's decision and nothing is idle.
- 🛑 **No `src/` or `native/` change.** The estimator lives in `qa/rr-study/synth/`.

---

## §9. Amendment B2 — ROW 0a(v) STOPs a second time. E4/E5 are STRUCK, not suspended

**Architect, 2026-09-16, after QA's 0a(v) report.** My replacement estimator failed too. **E4/E5 are
abandoned. The `E4-BENCH` §9.5 DRIFT caveat stands permanently as a stated limitation.** `BAR_φ`, `ρ*`,
E1–E3 and the FADE census are untouched.

### 9.1 What 0a(v) returned, and why it is real

| injected | 0 | 0.5 | 1 | 2 | 4 | **8** | **16** |
|---|---:|---:|---:|---:|---:|---:|---:|
| recovered | 0.000 | 0.447 | 1.043 | 1.938 | 4.025 | **5.925** | **20.123** |
| tolerance | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.8 | 1.6 |
| | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |

QA eliminated both cheap explanations before reporting: the frequency-search machinery recovers a
**constant** 1/4/8/16 Hz shift exactly, and a **noiseless** render at doses 8 and 16 shows the same bias
as the 50-trial median. So it is neither a bug nor noise.

**The mechanism, confirmed by arithmetic while ruling:** a 26-symbol sub-window is 4.16 s, and the
signal is chirping *inside* it.

| dose | drift rate | sweep **within one sub-window** | in tone spacings |
|---|---:|---:|---:|
| 4 | 0.316 Hz/s | 1.32 Hz | **0.21** ✅ |
| 8 | 0.633 Hz/s | 2.63 Hz | **0.42** ❌ |
| 16 | 1.266 Hz/s | 5.27 Hz | **0.84** ❌ |

**The break is exactly where the in-window sweep passes ~0.2–0.4 of a tone spacing.** A single-frequency
correlation peak cannot track a chirp; it settles somewhere that is not the window's centroid.

🔴 **And the direction is inconsistent — dose 8 under-reads (5.93), dose 16 over-reads (20.12).** There
is no "biases safe" story to fall back on, which is what the first estimator at least had in one
direction. QA is right that this is a window-size / chirp-rate interaction in the method, not a build
defect.

### 9.2 🔴 The lesson, and it is the same error twice

Both estimators failed **the same way**, and it is sharper than the lesson I recorded in B1:

> 🔴 **An instrument built to measure X must not assume X is small or absent. Both of my drift
> estimators assumed the signal was locally non-drifting.**

- **B1's estimator** unwrapped per-symbol phase — which assumes the offset stays inside ±Nyquist, i.e.
  **assumes drift is small**. It folded at 6.25 Hz.
- **B1's replacement** fitted one frequency per sub-window — which assumes the signal is **stationary
  within the window**, i.e. again **assumes drift is small**. It broke at 0.42 tones of in-window sweep.

I replaced the first method's symptom without auditing the second method's own core assumption against
the regime it had to work in. **This supersedes B1 §8.2's narrower "a sampling limit applies to every
consumer" wording**, which was a special case of it.

### 9.3 The method that would actually work, recorded for whoever wants it

Not being built. **Fit the chirp, because a linear drift *is* a chirp** — do not estimate a frequency
and difference it:

> Two-parameter matched filter over the **whole** transmission against the known tone sequence:
> correlate against `exp(j2π(f₀t + ½kt²))`, searching `(f₀, k)`. Total drift = `k · T_tx`. Cheap in
> practice: for each candidate `k`, **dechirp then one FFT** yields every `f₀` at once. Resolution over
> 12.64 s is ≈ 0.08 Hz, far finer than the 0.5 Hz tolerance, and the model is exactly correct for the
> generator's linear drift, so the filter is optimal rather than approximate.

### 9.4 Why I am stopping rather than building it

The chirp fit is cheap and is the right method, and I am still not spending a third build cycle on it:

- **E4/E5 were always a rider.** DRIFT already reads **F3** on its own pre-registered predicate. E4 only
  converted my assertion *"≥8 Hz of drift in one 12.6 s transmission is not a live population"* into a
  measurement. **Nothing is blocked by its absence, and F3 is not weakened** — it was ruled on its own
  terms, with the ladder gap disclosed by me at the time.
- **What could hide in (8,16] is bounded and physically extreme.** 8–16 Hz across one transmission is
  0.6–1.3 Hz/s. For a differential to hide there, one decoder would have to cross substantially before
  the other inside that single octave, at drift rates no ordinary transmitter produces.
- **Allocation.** Two build cycles are already spent on a nice-to-have while **density — the other
  candidate for the same 17.96 pp ceiling — is completely unexplored.** A third belongs there.
- 🛑 **This is a forward-looking call, not sunk cost.** The two spent cycles are gone either way; the
  question is only whether the next hour is worth this rider, and it is not.

**Consequence, stated plainly so nobody has to rediscover it:** the `E4-BENCH` §9.5 caveat — that the
(8,16] Hz octave is unmeasured and a differential could in principle hide there — is now **permanent**.
It is a disclosed limitation of the programme, not an open action.

### 9.5 0a(vi), the odd result: recorded, explained as a guess, not relied on

Drift 8 Hz composed with FADE `B` = 1 and `B` = 5 recovered **8.4** and **8.3** Hz — *closer to truth*
than the no-fade case (5.93). QA flagged it without chasing it, correctly.

**Candidate explanation, not verified and not to be built on:** fading randomly reweights the energy
across the sub-window, smearing the deterministic bias that a fixed window shape imposes on a chirp —
i.e. fading acts as **dither** on a biased estimator. If true it is a median-over-50-trials effect and
would be worthless per-row, which is what E4/E5 would have needed. 🛑 **It does not rescue the
estimator, and the correct response to "our instrument works better when the signal is degraded" is
suspicion, not adoption.**

### 9.6 What B2 changes

**E4 and E5 are struck**, ROW 0a(v)/(vi) are closed, and the drift limb of this census is over.
**Untouched:** `BAR_φ` (still with the Captain), `ρ*` = 0.577, E1–E3, the population, the sample, and
every FADE row. **The FADE census — the reason this arm exists — is unaffected and still gated only on
the worth-building anchor.** No `src/` or `native/` change.

---

## §10. Amendment B3 — block S changes the bar. Two thresholds off one measurement

**Architect, 2026-09-16, on QA's block-S reduction (`e4_block_s_reduced.json`, `qa/e4-bench`
`0011b5b1`).** 🔴 **`BAR_φ` = 0.12 is WITHDRAWN.** It applied a differential measured at −8 dB to the
whole ≥ −10 dB population, and block S shows that is wrong. **This also resolves the "how to treat the
10 Hz dose" fork I put to the Captain — it is answered here, by design, and no longer his to decide.
The only thing still his is the worth-building anchor.**

### 10.1 What block S says. Two effects, not one

| FADE dose | `Δ` at −8 dB (block P, n=150) | `Δ` at 0 dB (block S, n=50) | reading |
|---|---:|---:|---|
| **5 Hz** | **+0.087** (90% [0.053, 0.127]) | **−0.020** (90% [−0.06, 0.00]) | **gone at 0 dB** — a plain SNR effect |
| **10 Hz** | +0.073 | **+0.200** (90% [0.12, 0.30], **Bonferroni [0.06, 0.36]**) | **grows with SNR** |

🔴 **`R_O` = 0.0000 at 10 Hz at BOTH SNRs — 0/150 and 0/50, zero recoveries in 200 trials — while
`R_W` improves 7.3% → 20% as the signal gets stronger.** That is not an SNR lottery. It does not move
when the signal gets stronger, which is what makes it look structural.

🛑 **Block S is DESCRIPTIVE by construction (§3.5 A3). No gate row may fire on it, and the 10 Hz
Bonferroni interval excluding zero is NOT an F1.** It informs this census's design — which is exactly
what A3 was pre-registered for — and nothing else.

### 10.2 🔴 The two-bin split is NOT available, and the reason is base rate

The obvious response is a second threshold `ρ**` separating ≥ 10 Hz from ≈ 5 Hz. **Computed from ROW
0a's own distributions (no new run), it does not work.** The `ρ₁` distributions at −8 dB overlap badly:

| `B` | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| 5 Hz | 0.090 | 0.136 | **0.215** | 0.307 | 0.348 |
| 10 Hz | 0.008 | 0.067 | **0.132** | 0.218 | 0.246 |

The best threshold, `ρ**` = 0.167, gives **detection 0.86 at a false-call rate of 0.24** — against the
0.90 / 0.10 standard `ρ*` met at 1.00 / 0.00. **And milder fading is always commoner than severe**
(HK-021(u)), so the false calls swamp the bin:

| true φ(5–10 Hz) | true φ(≥10 Hz) | measured bin | **contamination** |
|---:|---:|---:|---:|
| 0.050 | 0.005 | 0.0163 | **74%** |
| 0.050 | 0.010 | 0.0206 | 58% |
| 0.020 | 0.005 | 0.0091 | 53% |

**A bin that is majority misclassified milder fading cannot carry a bar.** So the census measures
**one** quantity, `φ_upper(≥ 5 Hz)`, exactly as before.

### 10.3 The design: one measurement, two thresholds

Since `φ_upper(≥5 Hz)` is an upper bound on **both** sub-populations, it can be read against both
effects at once. Same 1 pp anchor, same convention throughout (`Δ` at its 90% upper, the conservative
end):

| effect | population | share | `Δ` (90% upper) | threshold |
|---|---|---:|---:|---:|
| **5 Hz**, near-threshold only | REF −10 … −1 dB | 31.7% | 0.127 | **`BAR₅` = 0.25** |
| **10 Hz**, all SNR | REF ≥ −10 dB | 66.2% | 0.300 | **`BAR₁₀` = 0.05** |

**Replaces E1/E2/E3 (E4/E5 are struck by B2):**

| row | predicate | reading |
|---|---|---|
| **E1** | ROW 0a passed **and** 95% upper limit on `φ_upper` **< `BAR₁₀` (0.05)** | 🔴 **FADE CLOSES ENTIRELY.** Even if every faded row were a 10 Hz row at the most favourable `Δ`, the ceiling is under 1 pp. |
| **E2** | `BAR₁₀` ≤ upper limit, **and** 95% upper limit **< `BAR₅` (0.25)** | **The 5 Hz effect closes; the 10 Hz one does not.** Go to §10.4 before anything else. |
| **E3** | otherwise, incl. any ROW 0a STOP | **UNRESOLVED.** |

**Why E1 is clean:** it does not need the split. It closes both regimes with one number by assuming the
worst case inside the measured envelope. **That is the whole reason this design survives the loss of
`ρ**`.**

### 10.4 🔴 The confound that must be resolved BEFORE any 10 Hz treatment — conditional, not now

**WSJT-X's nonzero recovery at 10 Hz may not be fading robustness at all.** ROW 0b recorded its live
settings: **`NDepth` = 3, `TwoPass` = true**. At 10 Hz spread most soft bits are worthless, which is
precisely the regime where **a priori (AP) decoding** earns its keep — hypothesise the message, verify
the CRC. **The bench's pool is 15 standard-format messages including `CQ`, which is exactly what AP
exploits**, and AP gets *more* effective as SNR rises, which matches 7.3% → 20%.

🛑 **If that is what is happening, "fix our fading weakness" is the wrong treatment entirely** — the
difference would be a message-prior feature, not a channel-robustness one, and AP carries its own
false-accept risk that this programme has a long history with.

**It is NOT being tested now.** It costs bench time, and it only matters if the census fails to close.
**Pre-registered sequencing: on an E2 or E3, the AP question is the FIRST thing resolved, before any
fading treatment is scoped.** The test is a 10 Hz re-run with AP disabled, or with messages AP cannot
exploit. 🛑 **Until then, "OpenWSFZ is structurally weak at 10 Hz Doppler spread" is an OPEN HYPOTHESIS,
not a finding.** Do not let it harden.

### 10.5 What B3 changes

`BAR_φ` = 0.12 withdrawn, replaced by `BAR₅` = 0.25 and `BAR₁₀` = 0.05 **derived from the same single
anchor**; E1–E3 re-specified; the E1 population for the 5 Hz reading narrowed to −10 … −1 dB. Untouched:
`ρ*` = 0.577, ROW 0a, the sample, the seed, the one-sided reading, and §1.2's corrected framing. Both
thresholds **scale inversely with the anchor** — at 0.5 pp they are 0.125 and 0.025; at 2 pp, 0.50 and
0.10. **No `src/` or `native/` change.**

➡️ ~~**The Captain decides the anchor. That is now the only open input to this arm.**~~

### 10.6 ✅ ANCHOR RATIFIED — 2026-09-16. The census is GO

**The Captain: *"I agree with the 1 point."*** His reasoning, recorded because it has a standing
consequence beyond this arm:

> *"even when we can improve the decoder a slightly bit it may be worth revisiting investigations that
> we have closed or parked to see if the improvements can bring better results."*

**Fixed by that ratification, and now FROZEN once QA produces the first `φ` (§5 Q1's rule):**

| | value |
|---|---:|
| worth-building anchor | **1.00 pp** |
| **`BAR₅`** (5 Hz, REF −10…−1 dB, 31.7%, `Δ`hi 0.127) | **0.25** |
| **`BAR₁₀`** (10 Hz, REF ≥−10 dB, 66.2%, `Δ`hi 0.300) | **0.05** |

🟢 **Nothing else is outstanding. E1–E3 run as specified in §10.3, on ROW 0a's fixed `ρ*` = 0.577.**

### 10.7 🔴 The standing consequence of the Captain's reasoning — a distinction, not a loophole

His argument is that a gain's worth includes **option value on re-opening closed work**. That is
sound, and it collides with a standing prohibition unless the boundary is stated precisely:

| | status |
|---|---|
| Re-reading a closed gate **with a better metric on the same data** | 🛑 **PROHIBITED, unchanged.** This is the standing rule and the Captain's reasoning does not touch it. |
| Re-running a closed arm **against a decoder that has materially changed** | ✅ **A genuinely new experiment** — the system under test is different, so it is not a re-read. It still earns a **fresh pre-registration**. |

🔴 **What this requires of us going forward: a closure must record WHICH BINARY it was closed against.**
A closure that does not name its binary cannot be revisited under this reasoning, because there is no
way to tell whether anything changed. ✅ The `E4-BENCH` DRIFT `F3` ruling already carries this —
*"closes DRIFT … **on this binary**"* — and that phrasing is now the required form, not a stylistic
choice. **Shim `20260051` / DLL `91997e38…ad2c6` is the binary every E4 closure is pinned to.**

🛑 **This is not a licence to re-open on appetite.** NBR-A's closure already sets the bar for what a
re-entry must name: *"what changed other than appetite for the answer."* That stands.

---

## §11. Amendment B4 — the census is HELD. ROW 0a was circular, and that is my design error

**Architect, 2026-09-16, on QA's report against real rows.** 🔴 **No `φ` is to be computed. `BAR₅` and
`BAR₁₀` are NOT frozen** — the freeze triggers on the first `φ`, and QA correctly produced none.

### 11.1 What QA found, and why stopping was right

On real sampled rows using REF's reported `(DT, freq)` per §1.1: **n = 51 valid, median `ρ₁` = 0.145,
share below `ρ*` = 96%, and FLAT from −10 dB to +14 dB.**

🔴 **The flatness is the finding, not the 96%.** §1.2's safety argument is that corruption pushes `ρ₁`
down, which is one-sided and therefore tolerable. **That argument assumes the corruption is noise —
and noise shrinks as SNR rises.** A reading that does not move between −10 dB and +14 dB is not noise
being absorbed. It is signal-proportional, which means **model mismatch**, and a one-sided bound
derived from a mismatched model bounds nothing.

QA's three checks, in order, and all three are the right ones:
1. **Pipeline clean** — a bench gate WAV read back cold gives `ρ₁` = 0.988 with a sharp power peak.
2. **Not DT quantisation** — synthetic + realistic ±0.05 s rounding gives ~80% false share raw, but a
   local `(DT, freq)` refinement **fully** recovers it (0.96–0.98, 0% false). Quantisation is solved.
3. 🔴 **The same refinement run wide (±10 Hz) on real rows barely moves anything and lands on an
   unstable, row-to-row-inconsistent best fit — there is usually no sharp peak to find.**

**Check 3 is decisive on its own.** A coherent matched filter against the *correct* waveform produces a
sharp peak on a strong signal. No peak means the reference does not match what was received.

### 11.2 🔴 ROW 0a could never have caught this, and I wrote it

I called ROW 0a *"the whole ballgame"* (§3.0) and specified all four sub-rows against **the bench's own
renders**. **That correlates the generator against itself.** It is tautologically clean and validates
the *estimator*; it says nothing about whether our *model of an FT8 signal* matches one we did not
generate. **QA's diagnosis of the calibration is exactly right and the error is mine.**

> 🔴 **Lesson, third variant today: a calibration against your own generator's output validates the
> estimator, not the model. To test a model you need a reference you did not produce.**
> Siblings: B1/B2 — *an instrument built to measure `X` must not assume `X` is small or absent*.

### 11.3 ⚠️ Scope — what is NOT in question

I checked the modulator before accepting the hypothesis. **`modulator.py` is correct FT8**: true GFSK,
Gaussian pulse with `GFSK_BT` = 2.0, continuous integrated phase, `TONE_SPACING_HZ` 6.25,
`SYMBOL_PERIOD_S` 0.16, 79 symbols, Costas `(3,1,4,0,6,5,2)` at 0/36/72. **So "the synth is not really
FT8" is not supported, and QA's wording should be narrowed accordingly.**

🟢 **This does NOT touch S1–S8, the R&R sweeps, the `E4` bench, or any existing synthetic result.**
Those use the synth **self-consistently** — generate audio, decode it — which is a valid closed loop.
**What is newly in question is using the synth as an ANALYSIS REFERENCE against independently
transmitted audio, a use this spec introduced today.** Nobody should read B4 as casting doubt on
committed synthetic work.

### 11.4 The decisive diagnostic — cheap, and it splits the hypothesis in two

QA's hypothesis is one thing; it is actually **two**, and they have different consequences.
**The Costas symbols separate them: they are FIXED and MESSAGE-INDEPENDENT** (positions 0–6, 36–42,
72–78, tones `(3,1,4,0,6,5,2)`).

> **Correlate a strong real row against the COSTAS SYMBOLS ONLY**, over a `(DT, freq)` grid, and report
> whether a sharp peak exists — the same search that found one cold on the gate WAV.

| outcome | meaning | consequence |
|---|---|---|
| **Sharp Costas peak, but the full-message correlation still fails** | Waveform and timing model are FINE. The **message → tone reconstruction** is wrong — our re-encode of the REF text does not produce the tones actually transmitted (message-type packing, CRC, LDPC parity, or the text as WSJT-X printed it not round-tripping). | **Repairable.** Fix the re-encode, re-run. The census survives. |
| **No Costas peak either** | The **waveform or timing model** does not match real received audio, message content irrelevant. | 🔴 **The census cannot be built this way.** Report and stop; do not iterate on the estimator. |

**Run it on the strongest available rows (≥ +10 dB), where SNR cannot be the explanation.** Suggested
n = 20. **This is a diagnostic, not a gate — no bar, no reading, report what you see.**

### 11.5 Status

- 🛑 **Census HELD.** No `φ`, no E1/E2/E3, nothing downstream of `ρ₁` on real rows.
- ✅ `BAR₅` = 0.25 / `BAR₁₀` = 0.05 stand as ratified and **remain movable** (no `φ` exists).
- ✅ ROW 0a's `ρ*` = 0.577 is still fixed **for bench-rendered audio**; its validity as a threshold on
  real rows is exactly what is in doubt.
- ➡️ **Next: §11.4's Costas diagnostic. Nothing else.**
- 🟢 `NBR-RERUN` (`2026-09-16-1745-…`) is **unaffected** — synthetic scenes, self-consistent use, no
  real-audio reference. It can proceed ahead of this.

---

## §12. Amendment B5 — B4 is REFUTED. The census was never tested: the search sat 0.5 s away from the signal

**Architect, 2026-09-17T16:42Z.** QA executed §11.4 exactly as written and reported honestly. **The
diagnostic's conclusion is wrong, the defect is in §11.4 itself, and the defect is mine.**

🛑 **STRIKE, at the place it lives (HK-022):**
- `BOARD.md:575` — *"Per B4's own fork: NO Costas peak ⇒ the waveform/timing model itself does not
  match real received audio … The census cannot be built this way as specified."* **VOID.**
- `BOARD.md:522-524` / this spec **§11.4's outcome table** — both of its rows are conditioned on a
  search window that could not contain the answer. **The table is not wrong, it was never reached.**
- `BOARD.md:504` / **§11.1's "THE FLATNESS IS THE FINDING"** — the inference is invalid. See §12.4.

### 12.1 The one thing §11.4 did not check: which clock `DT` is measured against

§11.4 said *"over a `(DT, freq)` grid … the same search that found one cold on the gate WAV"*, and that
search is **±0.05 s** around the `DT` printed by REF. **REF is WSJT-X. The audio is OpenWSFZ's archived
cycle WAV. Those are two different time origins.**

🔴 **This is written down in my own standing memory**
(`modulator-positive-clamp-and-dt-convention-defects.md` §2): *"WSJT-X reports DT vs nominal FT8 TX
start, harness vs UTC slot boundary"*, offset measured **0.531–0.674 s**, hard-coded in June as
`wsjt_dt_correction_s: 0.55`. **That same file records HK-018 firing on the Architect for this exact
offset on 2026-08-19.** I specced the census *and* its diagnostic blind to it four weeks later.

### 12.2 The measurement — three offline runs, on data already gathered (HK-018)

Scripts committed at `qa/rr-study/architect-checks/b5_0{1,2,3,4}_*.py`; re-runnable, numeric output
only (NFR-021). Corpus is C2, the census's own.

**(1) The offset exists and is large.** All decodes matched on `(cycle, message)` between the two
decoders on the *same* audio, `n = 58,686`:

| quantity | value |
|---|---|
| `DT_wsjtx − DT_openwsfz` | **−0.700 s** (sd 0.050, p05 −0.70, p95 −0.60) |
| `freq_wsjtx − freq_openwsfz` | **0.000 Hz** (sd 1.36) |

⇒ the frequency axis was never the problem, which is why widening to ±60 Hz changed nothing.

**(2) The Costas peak was always there.** §11.4's own search, DT swept **−0.30 … +1.40 s** instead of
±0.05 s, 12 strong rows (≥ +10 dB):

| | result |
|---|---|
| Costas peak found | **12 / 12** |
| peak at | **`DT_ref` + 0.48 s**, range +0.44…+0.52 |
| sharpness (best / grid median) | 6.5–18.2×, median **12.7×** — *above* the gate-WAV control |
| frequency offset at peak | **0.0 ± 0.5 Hz** |

**The peak sat ~10× outside the window I specified.** +0.48 s is the ordinary FT8 convention gap.

**(3) The full message correlates too** — §11.4's *other* branch, n = 26 strong rows, DT located per row:

| n=26, SNR ≥ +10 dB | HELD census (B4) | corrected |
|---|---|---|
| median `ρ₁` | **0.145** | **0.907** (p10 0.621, p90 0.953) |
| share below `ρ*` = 0.577 | **96%** | **7.7%** |
| data-symbol / Costas power per symbol | — | **0.83** (≈1 iff the re-encode is right) |

⇒ **waveform model fine, timing model fine, message→tone re-encode fine.** Neither branch of §11.4's
table is the true state; the third possibility — *the search is in the wrong place* — was not on it.

### 12.3 Why the positive control could not see it — HK-026, and it is a repeat

The control was **our own gate WAV**: generated by `modulator.py` at a known `dt_s`, read back, searched
on the same convention it was written with. **Both sides of that control share the time origin**, so its
response is exactly flat where the boundary sits. It could confirm every part of the estimator *except*
the one that was broken.

> 🔴 **LESSON — B4's own lesson, one layer down.** B4 said: *to test a model you need a reference you
> did not produce.* **That applies to the TIME ORIGIN as much as to the waveform.** A control built on
> our own clock validates the correlator, never the alignment. B1/B2/B4/B5 are now four variants of one
> family in two days.

### 12.4 🔴 The specific logical hole in §11.1

§11.1 argued: a reading that does not move from −10 dB to +14 dB is not noise being absorbed, therefore
it is **signal-proportional**, therefore **model mismatch**.

**A constant time-base error reads perfectly flat too**, because `ρ₁` is **power-normalised and
therefore scale-free** — misalign the window and you correlate against noise, and the *normalised*
autocorrelation of noise is the same at +14 dB as at −10 dB.

Checked numerically rather than asserted: for uncorrelated complex gains, `n = 79`, the null gives
**median `ρ₁` = 0.093** (p90 0.169, p99 0.237), and the sample median of 51 draws sits in **[0.079,
0.109]** at 90%. **The held census read 0.145 — the 82nd percentile of pure noise.** It was never a
measurement.

🛑 **"Flat vs SNR" separates noise from non-noise. It does NOT separate model mismatch from instrument
misalignment.** §11.1 treated it as if it did.

### 12.5 What is restored

- ✅ **Census UN-HELD.**
- ✅ **`modulator.py` as an analysis reference against independently transmitted audio: RESTORED**,
  pending ROW 0i below. §11.3's narrower scope statement was right and is unchanged.
- ✅ **`ρ*` = 0.577 restored as a threshold on real rows**, pending ROW 0i.
- ⏸️ **`BAR₅` = 0.25 / `BAR₁₀` = 0.05 remain RATIFIED and still MOVABLE** — the freeze triggers on the
  first `φ`, and **no `φ` exists yet**. B4 was right about that and it still holds.
- 🛑 **ROW 0a stays struck as a calibration.** B5 does not rehabilitate it — it was circular, exactly as
  B4 said. It is *replaced* by ROW 0h/0i below, which run on audio we did not generate.

### 12.6 Normative — how `(DT, freq)` is obtained, replacing §1.1's "REF's reported values"

For every frame row, in this order:

1. Take `(DT_ref, freq_ref)` from REF **as a starting point only**.
2. Build the **Costas-only** reference: true Costas tones `(3,1,4,0,6,5,2)` at 0/36/72, fixed filler
   tone 0 in all other positions. **Message-independent by construction.**
3. Grid-search `DT ∈ [DT_ref + 0.20, DT_ref + 0.80]` step **0.01 s**, `freq ∈ [freq_ref ± 2.0]` step
   **0.25 Hz**, skipping `DT < 0` or `DT > 2.36`. Maximise `Σ|g_i|²` over the 21 Costas indices.
   Record `(DT*, freq*)` and `sharpness = best / grid-median`.
4. Compute `ρ₁` from the **full re-encoded message** at `(DT*, freq*)`.

🔴 **Why locate on Costas-only:** it makes the time origin independent of the re-encode, available on
rows that do not re-encode at all, and available on rows **OpenWSFZ missed** — which is the entire
population the census exists to characterise.

🛑 **Do NOT substitute a fixed +0.48 s constant.** The offset is not guaranteed stable: 0.531–0.674 s
across three DLL builds, 0.55 hard-coded in the harness, 0.495 measured here. **Search, don't assume** —
that assumption is what B5 is about.

### 12.7 New ROW 0h / 0i / 0j — the non-circular calibration, on audio we did not produce

Pre-registered, mechanical, run **before** any `φ`. Rows 0h/0i use `n ≥ 25` REF rows at **SNR ≥ +10 dB**
drawn with the spec's own seed. 🔴 **For 0h only, the search grid is the WIDE one** (`DT ∈ [DT_ref−0.30,
DT_ref+1.40]`), so the sharpness threshold below is transferable from §12.2(2).

| row | predicate (as code) | STOP if |
|---|---|---|
| **0h** — the origin is locatable | `iqr(dt_off) <= 0.10` **and** `mean(sharpness >= 3.0) >= 0.90`, where `dt_off = DT* − DT_ref` | either fails |
| **0i** — the model matches real audio | `median(rho1_full) >= 0.80` | fails |
| **0j** — dropped rows are bounded | report `d` = share of frame rows whose REF text does not re-encode to 79 tones | `d > 0.10` ⇒ `φ` must be reported as the band `[φ·(1−d), φ·(1−d) + d]`, and **if a bar lies inside that band that limb does not close** |

**Nulls, in independent units (HK-021(z)), each shown to PASS where it holds:**
- **0h null** — "the search is landing on noise" predicts `dt_off` uniform on a 0.6 s window ⇒
  `iqr ≈ 0.30` and `sharpness ≈ 1`. **That null is what B4's held run actually exhibited** (unstable,
  row-to-row-inconsistent best fits, 6/19 pinned at the grid edge). It passes there and fails at 0.10.
- **0i null** — the same null predicts `median ρ₁ = 0.093`, p99 0.237 (§12.4). **The held census read
  0.145 — the null PASSES on it.** 0.80 is 3.4× the null's p99.

⚠️ **Disclosure, and QA may refuse this under HK-025:** 0.10 / 3.0 / 0.80 are informed by my own n=12
and n=26 runs in §12.2, i.e. **they are not blind**. They are set well inside what I measured so that an
instrument merely *working* passes and a broken one cannot. **If QA judges any of the three unable to
change the verdict, refuse the row and say so** — that is exactly the HK-021(k) test.

### 12.8 Costas-only vs full-message `ρ₁` — measured, not assumed

A Costas-only `ρ₁` (18 lag-1 pairs inside the three blocks) would be message-independent and drop **zero**
rows, which is attractive against ROW 0j. **Measured on n = 39 rows at ≥ −10 dB:**

| | Costas-only (21 sym) | full message (79 sym) |
|---|---|---|
| noise-null median / p99 | 0.166 / **0.410** | 0.093 / **0.237** |
| rank correlation between the two | **0.887** (Pearson 0.913) | — |

**They track each other well but are not interchangeable at the threshold.** The Costas statistic's noise
floor is **2.4× higher at p99**, leaving `ρ*` = 0.577 only 1.4× above it — and it therefore reads
systematically low, inflating share-below-`ρ*` by ≈8 pp against the full-message statistic on the same
rows. ⇒ 🔴 **Full-message `ρ₁` stays the primary readout; `ρ*` = 0.577 keeps its meaning. Costas-only is
used for LOCATING the origin (§12.6 step 3) and nowhere else.** ROW 0j handles the dropped rows instead.

### 12.9 🛑 What must NOT be cited out of this amendment

- 🛑 **The share-below-`ρ*` figures from my ad-hoc runs (7.7% at ≥+10 dB; ~28% at ≥−10 dB) are NOT `φ`.**
  Wrong sample, my own seed, not the pre-registered draw, n≤39. **Citing either as `φ` is prohibited**,
  and doing so would repeat precisely the error B4 correctly stopped QA from committing.
- 🛑 **`+0.495 s` is a measurement on C2, not a constant.** See §12.6.
- 🛑 **`ρ₁` = 0.907 is a real-row figure. It does not replace the bench's 0.988 anywhere.**
- 🛑 **B5 does not reopen anything B2 struck.** E4/E5 and the drift limb stay abandoned; §9.5's (8,16] Hz
  caveat stays permanent. **This is a time-origin defect in the FADE limb only.**

### 12.10 Predictions, and one that must not be quietly rewritten

| prediction | P | class |
|---|---|:---:|
| ROW 0h PASSES | 0.95 | C |
| ROW 0i PASSES | 0.90 | C |
| ROW 0j returns `d ∈ [0.05, 0.15]` | 0.80 | C |

🔴 **The open `E1` prediction — "FADE closes on exposure" at P = 0.65 — now looks likely to MISS**: my
ad-hoc n=39 reads ~28% below `ρ*` against `BAR₁₀` = 0.05. **I am NOT revising it to 0.10. It was written
blind and it scores blind at 0.65**; a number changed after peeking at indicative data is not a
prediction. Recorded here so the revision is visible rather than silent.

⚠️ Note for the ledger: the already-open `E4-STAGE2` prediction *"dropped (non-re-encodable) share 2–4%"*
reads **7.7%–13.3%** in these runs. It scores on ROW 0j, not on this.

### 12.11 Status and sequence

- ➡️ **ROW 0h → ROW 0i → ROW 0j → census.** Nothing before 0h.
- 🛑 No `φ` until all three pass. `BAR₅`/`BAR₁₀` freeze on the first `φ`, unchanged.
- 🟢 `NBR-RERUN` remains untouched and independent. **Which of the two runs first is the Captain's
  call, not QA's and not mine.**
