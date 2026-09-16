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

➡️ **The Captain decides the anchor. That is now the only open input to this arm.**
