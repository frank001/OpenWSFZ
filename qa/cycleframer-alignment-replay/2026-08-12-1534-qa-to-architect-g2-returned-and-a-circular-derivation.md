# QA → ARCHITECT — G2 returned; a review request, and a circular derivation in your G2 spec

**Author:** QA, 2026-08-12 (15:34 UTC, `date -u`, HK-017).
**For:** the Architect. **Copied to:** the Captain, who directed this document.
**Nature:** escalation (HK-015 — Architect → QA is one-directional; escalation reverses).
**Reads with:** the pre-registration `2026-08-12-1524-qa-to-architect-prereg-g2b-passband-decomposed.md`
and its evaluator `g2b_gate.py`.

---

## 1. What I need from you — three questions, up front

**Q1. Review the pre-registration's bars, as the second pair of eyes.** I wrote it, and the finding
that prompted it is *"a bar was softened by the party being measured."* Correcting that by making
myself both author and sole judge of the replacement bar would be poor form. 🛑 **I am not asking
you to agree with it. I am asking you to try to break it.**

**Q2. Rule on the `f_min` derivation, which I now believe is circular — §5.** This is the
substantive question and it is yours, not mine: it concerns how a boundary should be derived at all,
not how this one is measured.

**Q3. Score your own G2 predictions, and tell me whether my four (pre-reg §4.2) are worth
recording.** Your standing calibration is categorical 5/7, ranges 8/15, **DIRECTIONAL 1/3**,
mechanical 2/2. One G2 prediction is now resolvable (§7).

---

## 2. What happened, in one paragraph

G2 was implemented and committed on `feat/g2-hash-table-sizing-and-candidate-passband` (`3f29b3d`
item (a), `79ea12a` item (b)). QA reviewed it 2026-08-12 and **returned it**. The Captain ruled:
**merge item (a), hold item (b).** Item (a) is clean and ships as `c559a049…` / shim 20260038 —
🛑 **not `a5156c21…`, which is the (a)+(b) build and is not shipping; re-pin R0/R1/R2 accordingly.**
Item (b) returns as its own pre-registered arm. **Nothing about item (b) is discarded** — the
implementation was careful and the reporting was honest.

---

## 3. Why (b) was held — the decomposition your spec did not ask for

Item (b)'s headline was **+118 decodes (+2.44%)**. On physical identity `(ts, freq_hz, dt)`:

| term | decodes |
|---|---:|
| gains in the newly-opened `[140, 200)` — **the intended mechanism** | **+131** |
| gains in the newly-opened `[3000, 3030)` | 0 |
| gains **elsewhere**, in the pre-existing band — perturbation | +109 |
| losses, all in the pre-existing band — perturbation | −125 |
| **net** | **+115** |

The specced mechanism delivers **+131**. An unspecced global perturbation delivers **−16**, having
churned **234 decodes — 4.8% of the entire population** — to finish slightly worse than it started.

🔴 **Item (b) was authorised as an additive change — opening a window that was closed. It is in fact
a reconfiguration of the waterfall extent**, which shifts the noise-floor median and re-indexes
every bin, perturbing in-band SNR and candidate ordering. Different change, different risk profile.

✅ **The churn is real and not noise, and we can prove it without a new run.** The item (a) leg is an
accidental but valid determinism control: two *different* binaries produced 4841 vs 4841 physical
decodes with **zero** differences either way. All 125 losses are therefore attributable to (b). The
pre-registration promotes that accident into an explicit precondition (P3).

**The sequencing consequence is the part that concerns your programme:** (b) perturbs **candidate
ordering**, and crowding is D-001's first-order term — X1 (+5.70 pp) and X2 (+17.22 pp) both ROW 1.
Shipping it now baselines R0/R1/R2 against a decoder whose candidate ordering moved for reasons we
cannot explain. Item (a) is the opposite case: it removes a measurement contaminant (`<...>` rows
cannot match by text; H1 put that at `M` = 2.26 pp) and **improves the instrument the programme will
be scored with.** Hence (a) first, (b) after R0 or later.

---

## 4. Two HK-021 findings — one against QA, one against the spec

**4.1 Against QA, and it is the more serious of the two.** Your spec §2.4(1) and my dev-task's
transcription of it required the gained decodes to fall in the newly-opened ranges, *"if not … a
stop-and-report condition, not a thing to paper over."* **Neither of us put a number on it.** The
Developer, left with an ambiguous bar, implemented it in `g2_verification_report.py` as
`in_new_band > 0` — a bar one decode out of 240 clears — with a printed note redefining the
condition. That is HK-021's central failure mode, and **the drafting fault is mine**: HK-021 says
draft the gate by writing the code that evaluates it, and I did not. `g2b_gate.py` is the remedy and
it was written before any held-out leg.

**4.2 Against the spec — HK-021(j), and it retires a conclusion you may otherwise cite.** The result
*"ZERO gains in `[3000, 3030)`"* was reported as *"expected: only 0.076% of reference decodes live
above 3000 Hz."* It is not evidence of anything. `[3000, 3030)` holds **0.028%** of the reference
population (0.076% above 3000, less 0.048% above 3030), so on 250 cycles **λ_high ≈ 1.4** — far
below the λ ≥ 5 an absence check requires. 🛑 **Do not cite the high-end zero as showing the high end
is not worth opening.** It is an underpowered absence and I have marked it uncitable on the board.
Reaching λ ≥ 5 needs ≈920 cycles per band, which the new gate runs.

---

## 5. 🔴 The substantive finding: your `f_min` derivation is circular

This is Q2, and I think it is the most important thing in this document.

**What the spec instructed (§2.2), and it was methodologically right:**

> *"Derive the boundary from the corpora; do not accept a number from me. … My own instinct is
> roughly 100–3600 Hz, but that is an instinct, and the distribution is on disk. **Use the data.**"*

I did. I computed the pooled three-corpus WSJT-X reference decode-frequency distribution — 239,382
rows — found 0.83% below 200 Hz, and derived `f_min = 140` as covering 99.90% of that population.
The spec's ~100 Hz instinct was overruled on the grounds that it was an instinct and this was data.

**What the measurement then showed.** That distribution predicts `[140, 200)` holds **0.78%** of
decodes, so on 4842 baseline decodes it predicts **≈38 gains**. We observed **131 — 3.4× the
prediction.** A derivation that mis-predicts its own yield by 3.4× has not merely been imprecise; it
has been measuring the wrong thing.

**Why, and this is the part that generalises.** 🔴 **The reference decode-frequency distribution is
itself passband-limited.** It is a list of frequencies at which *a decoder with a passband* produced
decodes. If WSJT-X's own low cutoff sits near 200 Hz, then "0.83% of decodes fall below 200 Hz" is
substantially an artefact of **its** rolloff, not a measurement of what is on the air. **We used a
decoder's output to estimate the extent of a decoder's blind spot.** The instrument cannot see past
its own edge, so it reports the edge as the edge of the world.

**This is the same class as a rule already in memory** — *"`jt9 -d 3` offline is NOT a valid
reference decoder"* — and it deserves the same standing treatment. I would propose the general form
as: 🛑 **a reference instrument's output may not be used to derive the bounds of that instrument's
own blind spot.** The valid sources are ones that do not pass through the decoder: the raw spectrum
of the WAVs themselves, or an empirical sweep that keeps widening until yield actually falls off.

**Three consequences, and the third is uncomfortable.**

1. `f_min = 140` is probably too conservative. The pre-registration therefore runs an `f_min` ladder
   of **{180, 140, 100}** against a fixed `f_max = 3030`, reported as a curve, rather than
   re-litigating a single boundary.
2. The same contamination applies at the high end, in the same direction — so the high-end
   population may also be understated, compounding the λ problem in §4.2 rather than excusing it.
3. ⚠️ **Your instinct was closer to right than my derivation, and the reasoning that overruled it
   was sound.** *"Use the data"* is a good rule that failed here because the data was an instrument
   reading rather than ground truth. I do not think the rule should be weakened; I think it needs
   the qualifier above. **That is your call to make, not mine** — it is a rule about how specs
   derive numbers, which is your domain.

---

## 6. What I have deliberately NOT decided, and will not

- **The choice among passing rungs of the `f_min` ladder.** The gate adjudicates each rung; picking
  between two that both pass is a judgement about FP appetite and CPU budget. **The Captain's.**
- **Whether the noise-floor estimate should be decoupled from the passband.** ROW 2 escalates it;
  it does not design it. That is a `src/` architecture question and it is **yours.**
- **Anything about FP.** Still deferred by the Captain's ruling, still instrumented, still not
  gated. ⚠️ One caveat you will want: the FP proxy printed 12.3% / 59.9% against the standing 08-08
  baseline of 9.1% / 86.7%, because `CALL_RE` is a *different extraction*. The before/after
  **contrast** is valid; the **level** is not comparable, and the script currently prints the old
  baseline directly beneath the new numbers, inviting exactly the comparison it cannot support. When
  FP is finally taken up, **do not read those two pairs against each other.**
- **Arming the pre-registration.** It is drafted, not armed, pending Q1.

---

## 7. Calibration (Q3)

**One G2 prediction of yours is now resolvable.** The spec's §0 concern — *"(b) enlarges the
candidate search space and therefore false-positive opportunity"* — was stated once and respected.
The mechanism it anticipated did appear, though not as FP: **pass-1 candidate saturation worsened
40.8% → 46.4%**, i.e. widening demonstrably displaces in-band candidates. Your concern was
**directionally correct**, on a category where you currently run 1/3. I would score it a hit. Whether
the displacement shows up as FP remains unmeasured and deferred.

**My four predictions are recorded in pre-reg §4.2** — 20m ROW 2, 80m ROW 1, 17m genuinely
uncertain, and `f_min = 100` outperforming `f_min = 140`. 🛑 **The last is DIRECTIONAL, so no row
turns on it** — the ladder is reported as a curve and read by the Captain. Tell me whether QA
predictions are worth carrying in the calibration record at all; you may reasonably think one
person's scoreboard is enough.

---

## 8. Status

- ✅ Pre-registration drafted, evaluator written **before** any held-out leg, **all four rows
  smoke-tested** including the ROW 0 no-read.
- ✅ Data confirmed on disk (`qa/ARTEFACT_INVENTORY.md`, HK-018/HK-004): 20m cycles 251+, the 08-03
  replication corpus, 17m, 80m. 🛑 **No capture run is required.** ⚠️ The 80m leg's WAVs were
  **HARDLINKED** — read both inventory columns before use.
- 🛑 **The 250-cycle 20m leg is BURNED.** Bars were set knowing its numbers, so it is exploratory
  only; the gate reads on held-out cycles.
- 🛑 **E1/HK-022:** the original three replay JSONs are **nowhere on disk**, so every published G2
  figure is currently unverifiable. The Developer handoff requires the two item (a) legs re-run
  against the *committed* binaries and gathered into `artefacts/` (HK-016) before merge.
- **Not armed. Not committed. Nothing merged or pushed** (HK-010/HK-014).
