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

---

## §13. Amendment B6 — ROW 0i's STOP stands. The bar is defective and the bar is mine

**Architect, 2026-09-17T18:05Z**, on QA's full-power B5 run (`qa/e4-bench` `3f7be761`).

- ✅ **ROW 0h PASS**, n=992: `iqr(dt_off)` = **0.06** (bar 0.10), `sharpness ≥ 3×` on **99.0%** of rows
  (bar 90%). **B5's origin fix is real and robust.** That part is settled.
- 🔴 **ROW 0i STOP**, n=855: `median(ρ₁_full)` = **0.7537**, bar 0.80.
- 🔴 **New, not in B5: median `ρ₁_full` is FLAT across SNR** — 0.746 / 0.738 / 0.736 / 0.786 / 0.795
  from 10 dB to 25+ dB. **No rise toward a clean ceiling where the channel should be cleanest.**

🛑 **I am NOT moving the bar.** In B2 I refused to widen QA's drift tolerance when ROW 0a(v) failed
against me — *"per the Architect's own standing instruction, tolerance NOT widened."* **A bar that may
only be adjusted when it fires in my favour is not a bar.** What follows is a defect in how 0.80 was
*derived*, not a case for relaxing it.

### 13.1 🔴 Correction to QA's diagnosis — checked against the scripts, and it matters

QA attributed the 0.907 → 0.754 gap to my ad-hoc scripts requiring **both** decoders to have decoded the
row (`set(w) & set(o)`), a cleaner biased subsample. **Checked line by line; that is not what those
scripts do:**

| script | row selection | how the origin is LOCATED | full-msg `ρ₁` |
|---|---|---|---|
| `b5_02` | `set(w) & set(o)` — **intersection** | Costas-only power | *(not reported — peak location only)* |
| `b5_03` | **REF only** (`w`), ≥+10 dB | 🔴 **full-message power, all 79 symbols** | **0.907** |
| `b5_04` | **REF only** (`w`), ≥−10 dB | **Costas-only power** (§12.6's method) | **0.793** |

**Only `b5_02` used the intersection, and `b5_02` did not produce 0.907.** `b5_03` and `b5_04` are both
REF-only, so selection between decoders explains none of the gap.

🔴 **What does explain it is sitting inside my own two scripts: same corpus, same estimator, same REF-only
population — 0.907 when the origin is located by maximising FULL-MESSAGE power, 0.793 when located by
COSTAS-ONLY power.** A −0.114 step from the location method alone.

**§12.6 specifies Costas-only location. I set ROW 0i's bar from `b5_03`, which locates the other way.**
⇒ **I calibrated the bar with one instrument and then specified a different one.** QA's 0.754 against a
bar built on 0.907 is measuring that mistake, not the model.

> 🔴 **LESSON, and it is the fourth variant in three days: a COMPUTED prediction is only as good as the
> identity between what you measured and what you specified.** B1/B2 — an instrument must not assume the
> thing it measures is small. B4 — a calibration against your own generator validates the estimator, not
> the model. B5 — a control on your own clock validates the correlator, not the alignment. **B6 — a bar
> calibrated on a different instrument than the one you specified is not a bar.**

⚠️ **Why locating on full-message power inflates `ρ₁`:** it maximises `Σ|g|²` over ~350 grid candidates,
and `ρ₁` is built from the same `g`. Picking the grid point where noise happens to align constructively
selects for high `ρ₁` — a winner's curse on the statistic itself. **Costas-only location puts the
selection in a different subspace from the readout, which is why §12.6 is right and `b5_03` was not.**
**§12.6 is unchanged. It is the better method. It simply reads lower than the number I set the bar from.**

### 13.2 🔴 The real open object: a PEDESTAL, and it is uncharacterised

QA's flat-vs-SNR curve is the important finding, and it is not a repeat of §11.1's struck reasoning:
0.75 is **nowhere near** the noise null (median 0.093, §12.4), so this is signal, not noise. It is a
**fixed ~0.2 deficit that does not shrink as the channel gets cleaner.**

🛑 **So `ρ*` = 0.577 is mis-referenced on real rows by an unknown amount, and `φ` computed now would be
inflated by that amount.** Lowering 0i's bar to sit under the pedestal would admit an uncharacterised
systematic into the census — precisely the HK-026 error.

**Three candidates, and they have opposite consequences:**

| | pedestal cause | consequence for the census |
|---|---|---|
| **P1** | real fading genuinely is this common | `ρ₁` is *measuring*, not confounded — census is fine, `φ` is just large |
| **P2** | receive-chain waveform mismatch (SSB filter / AGC) vs our ideal-GFSK reference | additive pedestal; `ρ*` can be re-referenced once measured |
| **P3** | 🔴 **near-neighbour interference** — 6.25 Hz bins, ~24 simultaneous signals, and reported SNR is noise-relative, not interference-relative | **`ρ₁ < ρ*` would count CROWDING as FADING ⇒ the census double-counts density** |

### 13.3 ROW 0k — the decisive test, and it is non-circular by construction

> **Take REAL captured rows, apply a KNOWN Watterson fade on top (`B` = 0, 1, 2, 5, 10 Hz), run §12.6,
> and measure the `ρ₁` response curve against the bench's own curve at the same doses.**

Real audio is a reference we did not produce; the perturbation is one we control entirely. **That
combination escapes the circularity that killed ROW 0a.**

| outcome | predicate | meaning |
|---|---|---|
| **K1** | real curve = bench curve shifted down by a constant, slopes agree within 20% | `ρ₁` **discriminates fading**; pedestal is additive ⇒ re-reference `ρ*` by the measured pedestal, census survives |
| **K2** | real curve is **compressed** (slope < 50% of bench) | `ρ₁` **does not discriminate fading on real rows** ⇒ 🛑 the census cannot be built on `ρ₁`; close the exposure limb and report the bench result alone |
| **K3** | otherwise | report, do not interpret |

### 13.4 ROW 0l — is the pedestal the neighbours? Synthetic, and it sidesteps the prohibition entirely

> **Render victim + ONE neighbour at `Δf` ∈ {6.25, 12.5, 18.75, 25, 31.25, 50, 100, absent} Hz, NO fading
> at any dose, and measure the victim's `ρ₁` under §12.6.**

**Controlled synthetic scenes, self-consistent use, no live stratification, no real-audio reference** —
so this touches neither B4's scope question nor the blocked live-concentration ruling. **If `ρ₁` falls
with crowding, P3 is live and `φ` would double-count density.**

⚠️ **Do not over-read 0l as density evidence.** It measures whether **our channel-gain estimator** is
disturbed by a neighbour — not whether the **decoder's** exclusion zone is. Any read-across to the
`F-NBR-A` mechanism question (M1/M2) is secondary and **authorises nothing there.** 🔴 I flag this
explicitly because my ledger's named bias is over-predicting a findable localised defect, and P3 is
exactly the shape of hypothesis I am historically worst at.

### 13.5 One nearly-free check first — grid width

`b5_04` searched `DT` over 0.40–0.60 s; §12.6 searches 0.20–0.80 s, **3× wider ⇒ ~3× the candidates for a
weak row to mis-lock onto.** Before anything else: **re-run 0i's own rows under both grid widths and
report both medians.** If the narrow grid recovers a materially higher median, part of the pedestal is
mis-location, not channel. Cheap, and it partitions the problem.

### 13.6 Sequence, and the honest opportunity-cost statement

➡️ **§13.5 grid check → ROW 0l → ROW 0k.** `0l` first of the two rows: it is hours of synthetic compute
and it is the one that can convert a FADE blocker into a finding.

🔴 **Stated plainly, because this arm has now produced three methodology blockers in three days (B1/B2
drift, B4/B5 origin, B6 pedestal) and no `φ`:** the census's entire deliverable is *how often ≥5 Hz
fading occurs live*. The `E4` bench already stands on its own without it (5 Hz `Δ` = +0.087 at −8 dB and
vanishing at 0 dB; 10 Hz `R_O` = 0/200 at both SNRs, still an OPEN HYPOTHESIS per B3, AP confound
unresolved). **Meanwhile density has a reproducer, a ≈5.9 pp sizing, and — as of today's `NBR-RERUN` G1 —
confirmation that the sizing holds on the shipped binary.**

🛑 **Stop-loss, pre-registered now rather than argued later: if ROW 0k returns K2, the FADE exposure limb
is CLOSED as unmeasurable by this method.** No fourth estimator, no fifth cycle. **Whether to spend the
cycle at all is the Captain's call, and I am not neutral: I think `0l` is worth it and `0k` is worth it
only if `0l` comes back clean.**

### 13.7 Ledger

| prediction | P | class | outcome |
|---|---|:---:|---|
| `NBR-RERUN` reads G1 | 0.78 | H | ✅ **HIT** |
| ROW 0h PASSES | 0.95 | C | ✅ **HIT** |
| ROW 0i PASSES | 0.90 | C | 🔴 **MISS** |

🛑 ~~**The 0i miss is the first COMPUTED-class miss on the ledger** (was 3/3, now 4/6 across 0h/0i).~~ **STRUCK 2026-09-17 by B11 (§18): BOTH figures are wrong and `3/3` is a RETIRED figure the ledger explicitly forbids re-quoting.** The ρ₁-saturation call (2.5–3.5 Hz vs ≈10 Hz measured) was **already** a COMPUTED miss on 09-16, so 0i is the **second**, not the first. Mechanical count: **COMPUTED 6/9.** It did
not miss from noise: **I predicted from my own measurement without noticing that the measurement used a
different origin-location method than the spec I wrote in the same document.** 🛑 A computed prediction
inherits every assumption of the run it was computed from.

### 13.8 Status

- 🛑 **ROW 0i STOP STANDS. Bar NOT moved. No `φ`.** `BAR₅`/`BAR₁₀` still ratified, still movable.
- ✅ **ROW 0h PASS stands. §12.6 is unchanged and is the correct method.**
- ⏸️ **ROW 0j** — not yet reported; still open.
- 🟢 **`NBR-RERUN` CLOSED, G1.** The density sizing stands on the shipped binary.

---

## §14. Amendment B7 — ROW 0j fires, and my own rule makes `E1` unreachable for ANY `φ`

**Architect, 2026-09-17T18:10Z.** QA returned `d` = **10.76%** (538/5000 non-re-encodable) on the full
pre-registered sample, same seed and frame as 0h/0i. QA also confirmed, against its own copies, that
§13.1's three-line reading of the scripts is correct, and — **materially** — that its census pipeline's
`locate_origin()` already builds its reference from the Costas tones only and scores on the Costas
indices only. ⇒ 🔴 **The 0.7537 at n=855 IS the §12.6-correct reading. The pedestal is not a
winner's-curse artefact.** That is the single most useful thing in QA's message and it stands.

### 14.1 The arithmetic nobody had done

§12.7 says `d > 0.10` ⇒ report `φ` as the band `[φ(1−d), φ(1−d) + d]`, and a bar inside the band does
not close. With `d` = 0.1076 the band's **upper end is `φ·0.8924 + 0.1076`, whose minimum over all
possible `φ` is 0.1076** — attained at `φ` = 0.

| bar | value | closes when | verdict |
|---|---|---|---|
| `BAR₁₀` | 0.05 | never — `0.1076 > 0.05` for **every** `φ` | 🛑 **UNREACHABLE BY CONSTRUCTION** |
| `BAR₅` | 0.25 | only if `φ_obs < 0.1596` | reachable, but see §12.9's indicative ~28% |

🔴 **`E1` — "FADE closes on exposure" — cannot fire under my own ROW 0j, whatever the data say.** The
dropped-row band is **twice the width of the bar it has to fit inside.** This is independent of the
pedestal, independent of 0i, and independent of any measurement: it is arithmetic I should have done
when I wrote 0j, and it means the census has been carrying a second, silent blocker since B5.

🛑 **A row that can only return one answer is not a check.** I wrote exactly that about ROW E4 in the
drift work, where the row could only return the *comforting* answer. **Here it can only return the
uncomforting one. The defect is the same defect.**

### 14.2 🔴 The rule is wrong, and I am changing it — with the asymmetry stated openly

**I refused to move 0i's bar three hours ago. I am now changing 0j's rule. The Captain should check that
distinction rather than take it from me**, so here it is plainly:

- **0i's bar is a measurement threshold.** It fired on data. Moving it would relax a standard because the
  answer displeased me. **Not done, and still not being done.**
- **0j's rule is an inference procedure.** §14.1 shows it returns the same verdict for every possible
  input. **It is not a threshold that fired; it is a rule that cannot discriminate.**

⚠️ **The honest risk is that this distinction is self-serving, because the change happens to unblock my
own arm.** It is recorded here for exactly that reason. **If the Captain reads it as special pleading,
the correct fallback is §14.5's stop, not a negotiated bar.**

### 14.3 ROW 0j′ — replace worst-case with a test of the assumption that worst-case was hiding

The band assumes dropped rows could **all** be faded. **There is no physical reason to expect that: a
message's type is chosen by the operator, and the ionosphere does not read callsigns.** The worst case is
not the honest case — it is the case you assume when you have no way to look. **We do have a way to look.**

🔴 **`ρ₁` computed on the Costas symbols alone needs no re-encode, so it is available on all 538 dropped
rows** — and §12.8 measured it tracking the full-message statistic at rank correlation **0.887**.

> **ROW 0j′ — compare the Costas-only `ρ₁` distribution of the 538 dropped rows against the kept rows,
> on the same sample.** Report both medians, both share-below-`ρ*`, and a two-sample test.

| | predicate | consequence |
|---|---|---|
| **J1** | `|median_drop − median_kept| ≤ 0.05` **and** the share-below difference ≤ 0.05 | dropped rows are **missing at random w.r.t. the channel** ⇒ `φ` over kept rows is unbiased; **no band**, widen the CI only |
| **J2** | either exceeds 0.05 | dropped rows **are** channel-different ⇒ the band stands, **and `E1` is unreachable per §14.1** |
| **J3** | Costas-only `ρ₁` unavailable on the dropped rows for any reason | report and stop |

⚠️ **Cost on the complement, stated (HK-021(t)): J1 does not make the census sound** — it removes *this*
blocker only. **The pedestal (§13.2) is untouched by 0j′ and still gates everything.**

### 14.4 §13.5 is now sharper than when I wrote it

QA's confirmation that its pipeline matches `b5_04`'s method leaves **grid width as the one remaining
methodological difference** between `b5_04`'s 0.793 and QA's 0.7537 (0.40–0.60 s vs 0.20–0.80 s; the
populations differ too, ≥−10 dB n=36 vs ≥+10 dB n=855). ⇒ **Run both widths on the SAME rows.** That
controls population and isolates the only variable left. Still nearly free, now decisive rather than
merely cheap.

### 14.5 Ledger

| prediction | P | class | outcome |
|---|---|---:|:---:|
| ROW 0j returns `d ∈ [0.05, 0.15]` | 0.80 | C | ✅ **HIT** (0.1076) |
| *(original)* dropped share **2–4%** | — | C | 🔴 **MISS** (0.1076, ~3× the top of the range) |

🛑 ~~**COMPUTED class: 3/3 → 5/7**~~ — **STRUCK by B11 (§18): `3/3` is RETIRED and was hand-recalled, not counted. Mechanical count: COMPUTED 6/9.** Across 0h/0i/0j and the original dropped-share row. 🔴 **Both misses are
the same failure**: a number carried forward from an earlier run without re-checking that the run matched
what was later specified.

### 14.6 Status — unchanged where it matters

- 🛑 **ROW 0i STOP STANDS. Bar NOT moved. No `φ`.** Nothing in B7 touches it.
- 🔴 **`E1` is unreachable until 0j′ returns J1.** Even then the pedestal gates the census.
- ➡️ **Sequence unchanged: §13.5 grid check → ROW 0l → ROW 0k**, with **0j′ folded into §13.5** (same
  sample, same run, no extra pass).
- 🔴 **The stop-loss stands and now has a second trigger: `0k` returns K2, OR `0j′` returns J2 — either
  one CLOSES the FADE exposure limb.** No fourth estimator.
- 🔴 **My recommendation is unchanged and this strengthens it.** Two independent blockers now sit on an
  arm that has produced no `φ` in three days, while density has a reproducer, a ≈5.9 pp sizing and
  shipped-binary confirmation. **Whether to spend the cycle is the Captain's call.**

---

## §15. Amendment B8 — P3 is dead, the "pedestal" is probably ordinary fading, and ROW 0i tests the wrong thing

**Architect, 2026-09-17T18:50Z. Captain granted the cycle (*"1. spend the cycle. 2. await results of 1"*).**
Before dispatching, I ran two prior-setting checks of my own. Both changed the plan, and one of them
dissolves a row I wrote yesterday.

### 15.1 ROW 0l-A, pre-empted: the neighbour hypothesis fails on reach AND on magnitude

**Architect run, `qa/rr-study/architect-checks/b8_01_prior_0l_neighbour_reach.py`** — victim + ONE
equal-level neighbour, **no fading at any dose**, victim at +15 dB, n = 12 messages per cell, §12.6
estimator throughout:

| neighbour `Δf` | 6.25 | 12.5 | 18.75 | 25 | 31.25 | **50** | 100 | 200 | none |
|---|---|---|---|---|---|---|---|---|---|
| median `ρ₁` | 0.9357 | 0.9395 | 0.9515 | 0.9564 | 0.9596 | **0.9880** | 0.9879 | 0.9880 | **0.9880** |
| deficit as % of the 0.234 pedestal | 22.4% | — | 15.6% | — | 12.1% | **0.0%** | 0.0% | 0.0% | — |

**And the reach requirement, computed from C2's own occupancy** (`b8_02_neighbour_reach_requirement.py`,
90,958 rows / 4,113 cycles): **median nearest-neighbour separation = 47.0 Hz.** Share of rows with a
neighbour within 18.75 Hz = 0.223; within 50 Hz = 0.533. ⇒ **to move a MEDIAN, the disturbance must
reach ≈47 Hz.**

🛑 **P3 fails twice, independently:**
1. **Reach** — at 50 Hz the deficit is **0.0000 to four decimals**, identical to no neighbour at all.
   The estimator's disturbance is gone by ~50 Hz; it needs to be alive at 47 Hz.
2. **Magnitude** — even at `Δf` = 6.25 Hz, equal level, the worst cell tested, the deficit is **0.052 =
   22% of the 0.234 pedestal**. *Every row maximally crowded* still would not produce it.

⇒ 🔴 **Near-neighbour interference is NOT the cause of the pedestal. P3 is OUT.** ⚠️ **What is NOT
pre-empted:** many-neighbour cumulative effect and level ratios ≫ 0 dB. Those are deferred, not answered
(§15.5). ⚠️ **This says nothing about the decoder's exclusion zone** — it is about our estimator only,
exactly as §13.4 warned.

### 15.2 🔴 The bench already held the conversion, and it reframes everything (HK-018)

`row0a_calibration_result.json` — committed 09-16, 50 trials per dose — maps `ρ₁` to Watterson spread:

| `B` (Hz) | none | 0.5 | 1 | 2 | 5 | 10 | 20 |
|---|---|---|---|---|---|---|---|
| bench median `ρ₁` | 0.978 | 0.943 | 0.86 | 0.61 | 0.19 | 0.13 | 0.05 |

**Read the real-row numbers through it:**
- **median `ρ₁` = 0.754 ⇔ `B` ≈ 1.4 Hz.** That is **ordinary mild HF Doppler spread**, not an anomaly.
- **`ρ*` = 0.577 ⇔ `B` ≈ 2.2 Hz.**
- ⇒ 🔴 **the median row does not trip the bar.** The deficit sits **above** `ρ*`; the ~28% below it is a
  tail, not the bulk.

🛑 **I named it a "pedestal" and called it a defect before checking what it corresponds to physically.
0.754 is what a WORKING instrument should report over a real 20 m path.** **P1 — real, mild, common
fading — is now the parsimonious reading**, and neither B6 nor B7 said so.

⚠️ **QA's inference from the flat curve does not hold, and I let it stand in B6.** QA read flat-`ρ₁`-vs-SNR
as arguing against real fading. **There is no physical reason Doppler spread should track SNR** — power
and path dynamics are different quantities; a strong signal can be heavily faded. Flatness is fully
consistent with P1 and is **not** evidence for an instrument effect.

### 15.3 🔴 ROW 0i is MIS-SPECIFIED. It is WITHDRAWN, not relaxed

0i's predicate is `median(ρ₁_full) ≥ 0.80` — **a LEVEL test.** §15.2 shows the level is set by the real
channel. **So 0i asks "is the channel clean?" while claiming to ask "does the model match?"** Those are
different questions, and a row that requires a real ionospheric path to look nearly clean cannot validate
a model against it. **Its null assumed a fact about the physical world that is false.**

🛑 **This is NOT the bar moving.** The bar is not being lowered to 0.70 so it passes; **the predicate is
being withdrawn because it measures the wrong quantity.** The right question — *does `ρ₁` RESPOND
correctly to a known change in fading?* — is a **discrimination** test, and that is exactly **ROW 0k**.
⇒ **0k SUBSUMES 0i.** If 0k passes, discrimination is demonstrated and 0i was never needed; if 0k fails,
we stop, and 0i's verdict is irrelevant either way.

### 15.4 ⚠️ The pattern, stated plainly because the Captain should judge it, not me

**I have now withdrawn or replaced three of the four calibration rows I wrote for this census:** ROW 0a
(circular, B4), ROW 0j (verdict invariant to input, B7), ROW 0i (tests the wrong quantity, here). **Only
ROW 0h — which passed — has survived contact with data.**

🛑 **Each withdrawal has a defensible reason, and each one happens to unblock my own arm. That pattern is
itself evidence about my spec quality under time pressure, and the Captain is entitled to read it as
grounds to stop rather than as three independent corrections.** I am not the right judge of that. **If
the ruling is stop, §14.6's stop-loss applies and nothing here is orphaned** — the `E4` bench result
stands on its own.

### 15.5 What actually remains — smaller than B6/B7 asked for

| item | status |
|---|---|
| **ROW 0h** | ✅ PASSED. Done. |
| **§13.5 grid width + ROW 0j′** | ➡️ **RUN** — one pass, same sample, nearly free |
| 🆕 **Spread check** | ➡️ **RUN** — free, data already in `artefacts/e4-stage2-b5-full/` (§15.6) |
| **ROW 0k** | ➡️ **RUN** — the only real build, and it now subsumes 0i |
| **ROW 0l** | ⏸️ **DEFERRED** — 0l-A pre-empted by §15.1; the multi-neighbour/level-ratio remainder is not worth a build cycle against a hypothesis already dead on reach |
| **ROW 0i** | 🛑 **WITHDRAWN** (§15.3), subject to the Captain |

### 15.6 🆕 The free discriminator — P1 vs P2 separates on SPREAD, not median

A fixed receive-chain mismatch (P2) is **the same for every row** ⇒ narrow `ρ₁` distribution. Real fading
(P1) varies with path ⇒ wide. **QA reported medians only; the per-row values already exist.**

> **Report the IQR and p10/p90 of `ρ₁_full` over the 0i calibration set.** Bench reference at a FIXED
> dose, from the table's own 50-trial spreads: `B` = 1 gives IQR ≈ 0.03. **IQR ≤ 0.10 ⇒ P2-like (one
> common cause). IQR ≥ 0.20 ⇒ P1-like (per-row channel).** Diagnostic, **not a gate.**

⚠️ The cleanest P1/P2 test — one signal, two receive chains — is **not available**: I checked, C2 archived
audio from **one** path only (`wsjtx-2-sdruno/` holds `ALL.TXT`, no WAVs). It would need new capture,
which is outside this grant.

### 15.7 ROW 0k — executable, with the saturation confound fixed

🔴 **The confound B6 missed:** real rows are **already faded** (`B` ≈ 1.4 Hz), so added fade composes into
a saturating region. **A clean bench arm would show a steeper slope for that reason alone**, and K2 would
fire on saturation, not on instrument failure.

**Fix — match the starting point:**
1. **Bench arm:** render clean, then pre-fade at `B_pre` chosen so the bench arm's **median `ρ₁` matches
   the real rows' median within 0.02**. From §15.2's table, `B_pre` ≈ **1.4 Hz**; QA solves for it against
   the table rather than assuming it.
2. **Both arms** then receive the **same** additional dose ladder `B_add` ∈ {0, 1, 2, 5, 10} Hz.
3. `Δ_arm = median ρ₁(B_add=0) − median ρ₁(B_add=10)`, per arm. n ≥ 100 real rows, ≥ 100 bench trials.

| row | predicate | meaning |
|---|---|---|
| **K1** | `|Δ_real − Δ_bench| / Δ_bench ≤ 0.20` | `ρ₁` **discriminates fading on real audio** ⇒ census proceeds; `ρ*` re-referenced by the measured offset |
| **K2** | `Δ_real < 0.50 × Δ_bench` | response **compressed** ⇒ 🛑 stop-loss fires, FADE exposure limb CLOSES |
| **K3** | otherwise | report, do not interpret |

⚠️ `fade.py`'s wrap guard derives its buffer from `n` itself (`_wrapped_shaped_gaussian_process`), so it
**does** extend correctly on a 15 s cycle buffer. **Checked — no special handling needed.**

### 15.8 Predictions

| prediction | P | class |
|---|---|---:|
| **K1** — `ρ₁` discriminates on real audio | **0.75** | H |
| **K2** — compressed, limb closes | 0.15 | H |
| Spread check returns **P1-like** (IQR ≥ 0.20) | **0.70** | H |
| §13.5: narrow grid recovers ≤ 0.02 of the gap | 0.60 | C |
| **0j′ returns J1** (dropped rows missing-at-random) | 0.80 | H |

🔴 **All five are "no defect here" calls, which is the opposite direction to my ledger's named bias.
Recorded before the data, as the ledger requires.** ⚠️ **§15.1 was a case where I declined to predict and
measured instead — that is the behaviour the ledger asks for, and it is why P3 died in 20 minutes rather
than in a QA build cycle.**

### 15.9 Status

- 🛑 **No `φ`. `BAR₅`/`BAR₁₀` still ratified, still movable.**
- ➡️ **Dispatch: §13.5 + 0j′ + spread check in one pass, then ROW 0k.**
- 🔴 **For the Captain: §15.3's withdrawal of ROW 0i, and §15.4's pattern.** 0k's result makes 0i moot
  either way, so QA is not blocked on this ruling.

---

## §16. Amendment B9 — ROW 0k fires K1. `ρ₁` discriminates fading on real audio

**Architect, 2026-09-17T19:35Z**, on QA's 0k run (`artefacts/e4-stage2-b8-row0k/row0k_result.json`).

| `B_add` | 0 | 1 | 2 | 5 | 10 | `Δ` |
|---|---|---|---|---|---|---|
| **real** (n=111) | 0.8607 | 0.7440 | 0.5129 | 0.1643 | 0.1205 | **0.7402** |
| **bench** (n=150/dose, `B_pre`=1.5) | 0.7684 | 0.6769 | 0.4617 | 0.1586 | 0.1234 | **0.6450** |

**ratio = 0.1476, bar 0.20 ⇒ 🟢 K1 FIRES.** Architect's prediction 0.75 — **HIT**.

### 16.1 QA's disclosed baseline mismatch — verified conservative, NO re-run

QA calibrated `B_pre` against the study's global n=855 median (0.7537), not against this 120-row sample's
own `B_add`=0 baseline (0.8607), and flagged it rather than burying it. **I re-derived the direction
rather than accepting the argument** (`b9_01`):

| bench baseline | `Δ_bench` | ratio | |
|---|---|---|---|
| **0.7684 (as run)** | 0.6450 | **0.1476** | PASS |
| 0.8607 (properly matched) | 0.7373 | **0.0039** | PASS |
| **0.7500** | 0.6266 | 0.1813 | **first passing value** |

🔴 **Correcting the mismatch drives the ratio to ≈0.004. The mismatch made K1 HARDER, and the run sat
0.018 from its own failure point and passed anyway.** ⇒ **No re-run. The margin absorbs it and the
correction can only help.** QA's direction claim is confirmed, not merely accepted.

### 16.2 🔴 What QA did not flag, and it is the more interesting number

The real arm is a **deterministic prefix** of the calibration subset, and its baseline reads **0.8607
against the global 855-row median of 0.7537 — a gap of 0.107.**

**A prefix is not a random sample**: it is almost certainly a narrow time window, i.e. one propagation
condition. 🔴 **Under P2 (a fixed receive-chain offset) every subsample would read nearly the same.
Under P1 (real per-row channel) subsamples vary with propagation.** ⇒ **This is a free preview of the
spread check, and it points P1-like.** Corroborating, not deciding — Item 1 still rules.

⚠️ **Consequence for later: this 111-row arm is NOT representative of the census population.** Fine for a
discrimination test, 🛑 **not usable for estimating `φ`.**

### 16.3 ⚠️ Limitation of the composition mechanism — record it, do not cross-cite

§15.7 left the injection mechanism open; QA applied `B_add` to the **extracted per-symbol gain sequence
`g`**, not in the audio domain. **Two consequences, opposite signs:**

- ✅ **Better than I specified in one respect:** the audio is untouched, so the located origin is
  *exactly* invariant across doses rather than merely fairly so. Cleaner than an audio-domain injection.
- 🛑 **But the `g`-domain model holds the gain CONSTANT within each 0.16 s symbol**, so it under-models
  intra-symbol damage where coherence time approaches the symbol period (`B` = 10 Hz ⇒ ~0.1 s < 0.16 s).
  **QA's own sanity check shows exactly this:** `g`-domain 0.32/0.20 at `B` = 5/10 vs the audio-domain
  table's 0.19/0.13.

⇒ 🛑 **DO NOT cross-cite 0k's `Δ` values against §15.2's audio-domain `B`→`ρ₁` table.** They are different
units of damage. **Both arms are compressed identically, so the normalised ratio largely cancels it and
K1's verdict stands** — but the absolute `Δ`s are not audio-domain quantities.

### 16.4 🔴 Correcting what K1 licenses — QA's read is too strong in one half and unnecessary in the other

QA wrote *"census can proceed; `ρ*` gets re-referenced by the measured offset."* **Both halves need
tightening:**

1. 🛑 **K1 tests SLOPE, not ABSOLUTE calibration.** An instrument can have a correct response and a
   constant offset. **K1 alone does not license computing `φ`**, which depends entirely on absolute
   position relative to `ρ*`.
2. ✅ **And if there is no offset, no re-referencing is needed at all.** 0l-A measured our estimator at
   **0.988 on clean synthetic audio** ⇒ no intrinsic offset; §15.2 maps the real 0.754 to `B` ≈ 1.4 Hz ⇒
   physically ordinary. **"Re-reference `ρ*`" presumes the very defect that may not exist.**

🔴 **So the remaining gate is P2 — a receive-chain offset — and that is precisely what Item 1's SPREAD
CHECK decides:**

| spread result | reading | consequence |
|---|---|---|
| **IQR ≥ 0.20** | P1-like — per-row channel variation | **no offset; `φ` computable directly, `ρ*` = 0.577 stands as-is** |
| **IQR ≤ 0.10** | P2-like — one common cause | **a common offset exists; `ρ*` must be re-referenced BEFORE any `φ`** |

### 16.5 Status

- 🟢 **ROW 0k CLOSED, K1.** `ρ₁` responds to fading on real audio the way it does on the bench.
- 🛑 **Still no `φ`, and K1 does not authorise one.** `BAR₅`/`BAR₁₀` still ratified, still movable.
- ➡️ **Item 1 (grid width + `0j′` + spread check) is the last gate.** ETA ~80–90 min from QA's report.
- 🔴 **`ROW 0i` withdrawal (§15.3) and §15.4's pattern remain the Captain's to rule on.** 0k firing does
  not retroactively validate the rows that were withdrawn.

---

## §17. Amendment B10 — the spread check reads P1-like, and my own rule for it was under-specified

**Architect, 2026-09-17T19:42Z.** QA had already run Item 1(c) — the free one — before 0k started:

| n=855, ≥ +10 dB calibration set | p10 | median | p90 | **IQR** |
|---|---|---|---|---|
| `ρ₁_full` | 0.4490 | 0.7537 | 0.9475 | **0.2973** |

**IQR ≥ 0.20 ⇒ P1-like** by §16.4's rule, and ≈**10×** the bench's fixed-dose IQR (~0.03).
Architect's prediction (P1-like @ 0.70) — **HIT**.

### 17.1 🛑 I am not cashing this yet, and the reason is a defect in my own rule

§16.4 offered two readings: *narrow ⇒ one common cause (P2)* and *wide ⇒ per-row channel (P1)*.
🔴 **There is a third, and I omitted it: PER-ROW INSTRUMENT FAILURE** — e.g. a subset of rows mis-locating
on §12.6's wider grid — **which also produces a wide spread.** A wide IQR therefore rules out a *common
offset*; it does **not** establish that the variation is the channel.

> 🛑 **This is the same defect class as §11.4's fork: a binary framing that omitted the option which
> turned out to matter.** Fourth time in this arm, and the first time it has happened on a result that
> lands **in my favour**.

🔴 **§13.5's grid-width check is exactly the test that separates them, and it is still in flight.**
**The gate is NOT cleared. No `φ` yet.**

⚠️ **Stated deliberately for the Captain's §15.4 ruling: I have withdrawn three rows that fired against
me. This one fires for me, and it gets the same scrutiny.** If that reads as consistency rather than
convenience, it should be because of cases like this one, not because I say so.

### 17.2 ✅ What does support P1 — a physical plausibility check, which is not a test

Reading the quantiles through §15.2's bench `B`→`ρ₁` map:

| | p90 | median | p10 | `ρ*` = 0.577 |
|---|---|---|---|---|
| implied Doppler spread `B` | **0.44 Hz** | **1.43 Hz** | **3.15 Hz** | 2.24 Hz |

**That is an ordinary-to-moderately-disturbed 20 m distribution.** 🔴 **A per-row instrument failure has
no reason to produce a physically plausible Doppler distribution** — which is a real argument, but it is
**plausibility, not a discriminating test.** §13.5 remains the test. ⚠️ And per §16.3 this map is
audio-domain, so it may be read against the census's own `ρ₁` but **never against 0k's `Δ` values.**

### 17.3 Direction only — no number, and `E1` is almost certainly gone

`ρ*` = 0.577 sits **between p10 and the median** ⇒ **`φ` will land in the tens of percent, not near
`BAR₁₀` = 0.05.** ⇒ 🔴 **`E1` — "FADE closes on exposure" — will almost certainly MISS. The blind 0.65
stands and scores as a miss, unrevised** (§12.10).

🛑 **No percentage is cited here and none may be derived from these three quantiles.** A crude 3-point
interpolation is not `φ`; `φ` comes from the pre-registered sample and only after §13.5 clears.

### 17.4 Status

- ✅ **P2 (a common receive-chain offset) is ruled out.** `ρ*` = 0.577 needs no re-referencing **on that
  account**.
- ⏳ **P1 vs per-row instrument failure: OPEN, pending §13.5.** This is now the only thing between us and
  a `φ`.
- 🛑 **No `φ`. `BAR₅`/`BAR₁₀` still ratified, still movable.**
- ✅ QA accepted §16's three corrections without re-litigating and is independently re-deriving §16.1's
  counterfactual. **Nothing is owed back on that.**

### 17.5 🔴 §13.5's read-out, SHARPENED — pre-registered 19:46Z, BEFORE QA's data lands

QA confirms Item 1(a) is already built the right way: same 993 rows, `GRID_A` 0.20–0.80 vs `GRID_B`
0.40–0.60, tracking per-row same-origin agreement. **That is the discriminator §17.1 asked for and it
needs no redesign.** Two read-out additions only — both are `groupby`s on data the run already produces,
no new compute:

**(i) 🔴 The decisive statistic is not the median shift — it is WHERE the mismatches sit.**
A global median shift can stay small while mis-location still owns the low tail, and the low tail is
exactly what `φ` counts.

> **Report the origin-mismatch rate stratified by `ρ₁`** — at minimum bottom decile vs top decile, or
> below-`ρ*` vs above-`ρ*`.

| | predicate | reading |
|---|---|---|
| **G-a** | bottom-decile mismatch rate ≤ **2×** the top-decile rate | mis-location is **not** concentrated in the low tail ⇒ the spread is the CHANNEL ⇒ **P1 confirmed, gate clears** |
| **G-b** | bottom-decile rate > 2× the top **and** those rows' `ρ₁` rises materially on `GRID_B` | per-row instrument failure contributes to the low tail ⇒ 🛑 **spread is contaminated, `φ` is not computable as specified** |
| **G-c** | otherwise | report, do not interpret |

**(ii) ⚠️ `GRID_B` IS NOT A GOLD STANDARD, and the mismatch count alone is ambiguous.**
A row whose **true** origin lies outside 0.40–0.60 (a genuinely late or early arrival) is **forced** to a
wrong origin by the narrow grid. A mismatch therefore does not by itself mean `GRID_A` was wrong.

> **For every mismatched row, report which grid gives the higher Costas peak power / sharpness.** That
> identifies which origin is actually better **from the data**, instead of assuming the narrow one is.

✅ **One thing this asymmetry does NOT threaten:** forcing a wrong origin *lowers* `ρ₁` (that is B5's
whole finding), so a **higher** median on `GRID_B` cannot be manufactured by over-narrowing. The
direction is safe; only the per-row attribution needs (ii).

🔴 **Pre-registered at 19:46Z, before QA reported Item 1(a). If any of this arrives after the data, it is
outcome-chosen and must be discarded** (HK-021(y)).
