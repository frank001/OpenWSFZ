# ARCHITECT RULING — S.1's VOID is upheld. The defect is in the ESTIMATOR, not the null.
# `n_local` proxies `n_cycle`; a within-cycle shuffle cannot break a between-cycle confound. Mine.

**Author:** Architect, 2026-07-31 (17:30 UTC, `date -u`, per HK-017). Repo at `d9057af`.
**Answers:** `2026-07-31-1725-qa-arm-s1-result-VOID-on-mandatory-null.md`.
**Corrects:** `2026-07-31-1649-…-arm-s1-spec-rev3-…md` §3.3 (the estimator) and §5 (my stated
justification for the null's validity).
**For:** QA — **this closes the escalation.** And the Captain (§6 — S.1b needs authorisation).

---

## 0. Verdict

| # | ruling |
|---|---|
| **V1** | **The VOID stands.** Arm S.1 produced no reading. **QA executed the spec exactly and correctly** — including stopping rather than interpreting |
| **V2** | **The null is not defective. It worked.** It detected a real defect in the estimator before that estimator reached a decision. This is the pre-registration system functioning |
| **V3** | **The defect is in the estimator, and it is mine.** `n_local` proxies `n_cycle`; a *within-cycle* shuffle cannot break a *between-cycle* confound. Mechanism measured at §2 |
| **V4** | **QA's §4 lead is correct in mechanism** and is hereby promoted from lead to diagnosis — with one sharpening (§2.1): it needs no assumption about SNR composition |
| **V5** | **The +29.2 / +26.9 figures stay struck.** §4 rejects the "the effect is 12× the bias, just proceed" argument explicitly, because someone will make it |
| **V6** | **The fix is a new estimator (S.1b), not a new null.** Design at §5. **One redesign only** — §5.4 pre-commits the retirement rule now |
| **V7** | **Nothing opens.** S.2a stays gated; S.1 fired no row |

## 1. QA executed correctly — stated first because it matters

All six self-checks passed, self-check 6 **exactly** (1620/1631, 4359/3410, to the decode). That
exactness is not incidental: self-check 6 existed precisely to catch an implementation divergence
from the pre-registered cuts, and its passing is what allows this ruling to locate the fault in the
*design* rather than leaving it ambiguous between design and implementation. The check I added
because I'd been burned once did the job I added it for.

QA then hit a failing null, reported the void, declined to interpret, declined to try a different
locality definition, and escalated. **That is exactly right**, and §6 of that report anticipated the
failure mode this ruling has to avoid. This is the third time in this programme QA has correctly
executed a check that my drafting got wrong (HK-021's standing note). Saying so is not a courtesy;
it is the finding.

## 2. The mechanism, measured

**The claim:** `n_local` is a proxy for `n_cycle`. Decodes in busier cycles have more neighbours, so
they land in the `hi` cell more often — *even within a density stratum*, because a stratum is a
**range** of densities, not a single density.

Measured on segment 1 (exposure variables only — no recall computed):

| stratum | stratum's density range | mean `n_cycle` in `lo` | mean `n_cycle` in `hi` | gap |
|---|---|---:|---:|---:|
| sparse | 4 – 23 | 19.00 | 19.87 | **+0.86** |
| dense | 41 – 63 | 48.80 | 50.59 | **+1.79** |

So the `hi` cells systematically draw from **denser cycles**. Density has a large, already-measured
effect on recall (+22.33 pts across segment 1's strata). Therefore, **even with locality entirely
destroyed, `Δ_local` is positive by construction.** That is the +2.432 pts QA measured, and it is
why all 20 shuffles came out positive — 20/20 one-sided is not noise, it is a bias term.

**The within-cycle shuffle cannot touch this.** Permuting `freq_hz` inside a cycle leaves that
cycle's `n_local` multiset invariant, so a decode in a 22-decode cycle still tends to be `hi` and one
in a 6-decode cycle still tends to be `lo`. The shuffle randomises *which* decode holds which label
inside a cycle; it does nothing to the *between-cycle* gradient that the estimator is reading.

### 2.1 Sharpening QA's §4

QA's report offered the confound as *"larger/busier cycles … also happen to carry a different SNR
composition than smaller cycles."* **The mechanism is simpler and stronger than that**, and needs no
auxiliary assumption: the density→recall effect is **already measured**, in this exact corpus, at
+22.33 pts. Residual density variation inside a stratum is sufficient on its own. SNR composition
may contribute additionally, but the confound does not depend on it.

### 2.2 Honest limit on this diagnosis

Scaling segment 1's own density–recall relation linearly, a gap of +0.86 / +1.79 decodes/cycle
predicts roughly **+1 pt** of spurious Δ_local, against **+2.43** observed. Same sign, same order,
but a naive linear extrapolation **under-predicts by about half**.

The density–recall curve is convex — steeper at low density — which plausibly closes much of that,
but **I am not claiming this mechanism is proven to be the sole contributor.** It is proven to be
present, correctly signed, and large enough to matter. Settling whether it is the whole story needs
a specific diagnostic, specified at §5.3, and that diagnostic is part of S.1b rather than a
precondition for it.

## 3. My error, precisely located

Rev3 §5 asserted, as justification for the null:

> Permuting `freq_hz` within a cycle preserves that cycle's frequency multiset exactly, so the
> *marginal distribution* of `n_local` is preserved to the decode — only its pairing with
> (SNR, matched) is destroyed.

**The first clause is true. The inference drawn from it is wrong, and it is wrong in the direction
that matters.** Preserving the marginal is exactly what makes the null *powerless* against
between-cycle structure. I presented invariance as evidence the null was clean, when invariance is
precisely the property that guarantees it cannot see this confound. I even called the null "exact"
and said the cut points "need no re-derivation under it" — both true, and both irrelevant to
validity.

Stated plainly: **I wrote the correct null for a within-cycle estimator, then paired it with a
between-cycle estimator.** The null was right. The thing it was pointed at was not (HK-022 —
a green result answers whatever it was pointed at; this is the same lesson with the sign flipped,
a *red* result correctly answering a question about the wrong estimator).

## 4. Why the size of the real effect does not license proceeding

Someone will observe that the observed Δ_local is +29.2 against a null bias of +2.43 — a ratio of
about 12 — and argue the bias is immaterial. **Reject this.** Three reasons, in increasing order of
seriousness:

1. **The null measures the bias under the null**, where all locality signal is destroyed. There is
   no guarantee the contamination is the same magnitude on real data, where `n_local` and `n_cycle`
   covary differently.
2. **The bias inflates `Δ_local` specifically**, which is one of the two quantities the reading rule
   compares. The rule's row 1 vs row 2 turns on `Δ_local` being large while `Δ_cycle` is small.
   A term that inflates `Δ_local` alone is not a wash — it pushes toward the **expensive**
   conclusion (frequency-local ⇒ subtraction architecture ⇒ row 5 up).
3. **The pre-registered consequence of a failed null is VOID, without qualification.** Renegotiating
   that after seeing the numbers is exactly the failure the pre-registration exists to prevent, and
   this programme has already had to strike results twice for less.

**The descriptive figures stay struck.** They are on the record as the magnitude of a contaminated
quantity, not as a result, and they must not be cited, averaged, or carried into any pricing.

## 5. S.1b — the corrected estimator ⟨design; needs the Captain, §6⟩

### 5.1 The change

**Hold `n_cycle` constant by construction rather than by stratification.** Compute the locality
contrast **within each cycle**, then pool across cycles — each cycle its own stratum, matched on
SNR bin as before. A cycle has exactly one density, so `n_local` cannot proxy `n_cycle` at all.

Everything else is unchanged: the same `n_local(W)` definition, the same W-ladder, the same W = 50 Hz
reading width, the same matching, **the same ±2 pt null bar**, and the same reading-rule thresholds.
This is not a new locality metric — it is the same metric with the confounder removed by design.

### 5.2 Feasibility — measured, not assumed

| stratum | cycles carrying **both** `lo` and `hi` decodes | pooled minority-side decodes |
|---|---|---:|
| sparse | **172 / 176 (97.7%)** | 1,213 |
| dense | **159 / 159 (100%)** | 3,155 |

Ample support — 4,368 decodes on the constraining side. The four sparse cycles lacking a `hi` cell
contribute nothing and drop out harmlessly.

### 5.3 The null becomes valid — and this is the point

Under a within-cycle estimator, the within-cycle `freq_hz` shuffle randomises **precisely the
variation the estimator reads**, and nothing else. The same null that correctly voided S.1 becomes
exactly the right test for S.1b. **The null bar is unchanged at ±2 pts** and is re-registered as-is;
it is not being loosened to accommodate a redesign.

**Additionally mandatory**, to settle §2.2: report the mean `n_cycle` gap between `lo` and `hi`
cells. **Under S.1b it must be 0.00 by construction.** If it is not, the implementation is not
doing within-cycle contrasts and the arm is void on that alone.

### 5.4 Retirement rule — pre-committed now, before any S.1b number exists

QA's §6 correctly warned that redesigning until a null passes is a researcher degree of freedom.
The guard, fixed now:

> **One redesign. If S.1b's null also fails, the spectral-locality approach is RETIRED** — not
> revised a third time. The question "is the density penalty frequency-local or cycle-global?" then
> goes to the Captain as **not answerable from this corpus by this method**, and the menu decision
> is taken without it.

I am writing that down while I still do not know the answer, which is the only time it is worth
anything.

### 5.5 Cost

~half a QA session. Frozen artefacts, Python only, no `src/`, no rebuild, no new capture. Same
class as S.1 — and the work is an edit to `measurement_s1_spectral_locality.py`'s aggregation, not
a new script.

## 6. What this needs from the Captain

**S.1b is a redesign of an authorised arm, not a new arm** — same question, same corpus, same cost
class, same reading rule. I read the standing authorisation for S.1 as covering it. **But S.1 has
now consumed a session and produced no reading, and the honest position is that the Captain should
decide whether to spend another half-session on the same question rather than have me assume it.**

The case for spending it, briefly: this question splits row 4's engineering cost by roughly an order
of magnitude, it is still the cheapest thing on the board, and §5.4 caps the total exposure at one
more attempt.

The case against: two instrument defects in two attempts is evidence the question is harder to
measure cleanly from this corpus than I priced it, and §5.4's retirement outcome is a real
possibility rather than a formality.

**Not my call. Nothing starts until it is made.**

## 7. Citation blacklist — additions

Extends `1222` §7, `1530` §7, `1602` §7 and `1702` §6.

| do not cite | instead |
|---|---|
| *"S.1's Δ_local = +29.2 pts"* / *"Δ_cycle = +26.9"* / *"S.1 fired row 3"* | **VOID on the mandatory null.** No reading was produced. Contaminated by a measured between-cycle confound |
| *"the null bias is small relative to the effect, so S.1 is readable"* | **Rejected at §4**, on three independent grounds |
| *"the within-cycle shuffle is an exact null"* ⟨mine, rev3 §5⟩ | **Exact and invalid.** Invariance is what makes it blind to the confound (§3) |
| *"S.1 failed"* / *"QA's S.1 run failed"* | **False framing.** The instrument was defective; the run executed it correctly and the null caught it |

## 8. Boundaries

- **No `src/`, no rebuild** (HK-011). **No push, no merge** (HK-014/HK-010) — committed locally, and
  I do not ask. **No `pre_merge_check.py`** (HK-006).
- **No new arm.** S.1b is a corrected estimator for an authorised question; §6 puts the spend
  decision to the Captain regardless.
- **S.2a unchanged** — still gated on S.1 firing row 2 or 3, still needs a Developer session and the
  Captain per `1702`. S.1 fired no row; nothing about §5's descriptive figures opens it.
- **Per HK-015** this is Architect → QA. `dev-tasks/` and the S.1 report's errata are QA's to author.
- **NFR-021:** §2 and §5.2 are aggregate counts over exposure variables only.

## 9. Cross-references

- `2026-07-31-1725-qa-arm-s1-result-VOID-on-mandatory-null.md` — the result ruled on; §4's lead
  promoted at V4 and sharpened at §2.1.
- `2026-07-31-1649-…-spec-rev3-…md` §3.3, §5 — corrected here.
- `2026-07-31-1719-…-drift-screen-8081-20m-per-segment-result.md` — prerequisite, cleared,
  unaffected; S.1b inherits it.
- `2026-07-31-1602-…-segment-2-void-on-self-check-2.md` — the precedent QA correctly followed for
  reporting a void.
- `measurement_s1_spectral_locality.py` — S.1b edits its aggregation; the `n_local` and matching
  code is unchanged and already validated by self-check 6.

---

*Per HK-015 this is Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge, and I do
not ask for one. Per HK-011 nothing touches `src/`. Per HK-017 filename and byline carry `date -u`
UTC. Per HK-018 §2's confound table and §5.2's feasibility table were computed from the corpus
before this ruling was written, not argued — the previous two things I asserted from reasoning in
this arm's design were both wrong, which is the whole reason §2 is a measurement. Per HK-021 §5.3's
added check is stated as an assertion with a hard value (0.00) and an explicit consequence, and
§5.4 fixes the retirement rule before the numbers exist.*
