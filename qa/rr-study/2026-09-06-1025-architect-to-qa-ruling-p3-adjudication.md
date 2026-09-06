# `FP-PARITY` P3 — Architect ruling: all rows accepted, the level explanation is CLOSED, and the citable offline rate is now `10.325%`

**Architect, 2026-09-06 10:25Z** (`date -u`, HK-017). Adjudicates QA's P3 execution
(`qa/rr-study/fp-parity/results/2026-09-06-p3-normalisation-param-parity-report.md`, commits
`628f070` + `cf500d4`, branch `qa/2026-09-06-fp-parity-p3-execution`) against
`FP-PARITY` **Amendment 3** (`…-1025…` is this ruling; the spec is
`qa/rr-study/2026-09-06-0951-architect-to-qa-spec-fp-parity-p3-normalisation-and-param-parity.md`,
`1311d55`).

🔴 **Numbering: `AWGN-FP` also has an `A3.x`. Everything `A3.x` here is `FP-PARITY`.**

Docs-only; `git diff --stat -- src/ native/` **empty**, verified before commit (HK-014). Local, not
pushed.

---

## 1. Rows accepted — re-derived from the raw CSVs, not read off the report (HK-018)

I recomputed every row independently from
`qa/rr-study/fp-parity/_out/p3_norm_slots.csv` + `…_decodes.csv` and the committed
`m1m4_s5_20260050_slots.csv`, joining on `(scenario, part, trial, seed)`. **4,000 keys on both
sides, key sets identical.**

| Quantity | QA | Architect re-derivation | |
|---|---|---|---|
| Un-normalised events (ROW 0s) | 435 / 4,000 = 10.875% | **435 / 4,000 = 10.8750%** | ✅ exact |
| Normalised events (ROW 0n) | 413 / 4,000 = 10.325% | **413 / 4,000 = 10.3250%** | ✅ exact |
| `b` (event un-normalised only) | 363 | **363** | ✅ exact |
| `c` (event normalised only) | 341 | **341** | ✅ exact |
| `Δ` signed | −0.550 pp | **−0.5500 pp** | ✅ exact |
| Exact McNemar two-sided `p` | 0.4287 | **0.4287** | ✅ exact |
| `C′` (ROW 0n-C) | +1.652 dB | **+1.652 dB**, n=432 rows, min −2.113, median −0.018 | ✅ exact |
| Excess above `T = 2.622` | none | **0 of 432** | ✅ exact |

**⚠️ One immaterial discrepancy, recorded rather than glossed:** QA's 95% CI on `Δ` is
**[−1.870, +0.774] pp**; my paired-Wald recomputation gives **[−1.850, +0.750] pp**. A method
difference (QA should name theirs in the record), **0.02 pp apart, and the verdict is insensitive
to it** — both include 0, and `|Δ| = 0.55 pp` sits far below the 2.0 pp band either way.
**QA's figure is the citable one**, per the standing convention when a re-derivation differs by a
rounding-class amount.

**Verdicts stand exactly as reported: ROW 0o, ROW 0p, ROW 0s and ROW 0n-C do not fire; ROW 0n
lands 0n-iii.**

---

## 2. 🔴 What P3 establishes

### 2.1 The level explanation for the offline-vs-in-chain gap is CLOSED

This was pre-registered as 0n-iii's consequence before any normalised decode existed, and it is the
result that matters: **the ≈6.9 dB level difference between the offline seam and production is
excluded as an explanation of the gap.** The offline seam was running ≈6.9 dB quieter than the
daemon's fixed 0.20 RMS contract; brought to parity on the identical 4,000 slots, the false-accept
event rate moves by **−0.55 pp, p = 0.4287** — indistinguishable from no change.

🛑 **What that is NOT.** It does **not** explain the gap; it **removes one candidate explanation**
and leaves the others (spectral colouring, quantisation, downsampling — QA's own §9
recommendation 1) untouched. **A closed candidate is not a solved problem.**

### 2.2 `10.325%` is the citable offline absolute rate. `10.875%` is superseded, not restored.

Per the spec's own all-branches clause: the normalised figure becomes the only citable offline
absolute rate **because it is the only one measured under the production input contract**, and a
non-fire does not restore the old number — **it agrees with it.**

🛑 **MANDATORY LABEL on every future citation: `10.325%` (offline, `20260050`, normalised, n=4,000
slots).** Pooling it with any `≤20260049` offline figure is a **new pre-registration** (A3.2).

### 2.3 The gap ratio moves to `3.098×` — and it is a CROSS-ERA ratio, which must be said every time

`10.325% / 3.333% = **3.098×**` (was 3.263×).

🔴 **This ratio's numerator and denominator are from different binaries and different eras, and
neither label may be dropped:** numerator **offline, `20260050`, normalised**; denominator
**in-chain, `≤20260049`, POST-REGRESSION** (A2.2 + A2.4). A2.2 bars *pooling* a `20260050` sweep
into the comparator; it does not bar forming this ratio — **but the ratio inherits both labels, and
quoting `3.098×` bare is exactly the citation failure this arm has now corrected four times.**

⚠️ **And the honest precision statement:** the comparator's own CP95 `[1.934%, 5.345%]` alone puts
the gap anywhere in **1.93× – 5.34×**. The move from 3.263× to 3.098× is **far inside that** — it
is a relabelling to the correct instrument, **not a measured narrowing.** Do not report it as
progress on the gap's size.

### 2.4 `T = 2.622 dB` carries forward to `20260050`, normalised

`C′ = +1.652 dB` vs the standing `C = +1.622 dB` — **signed difference +0.030 dB**, i.e. the
production input contract does not move the false-accept ceiling. **0 of 432 decode rows exceed
`T`.**

⚠️ **The non-fire branch's limit, as the spec required it be stated in the same breath:** this shows
no false accept exceeded `T` **on this 4,000-slot noise-only population.** It does **not** show `C`
is stable, and a sample maximum at `n = 432` is not a stable statistic. The distribution is the
evidence (min −2.113, median −0.018, top five 1.247 / 1.399 / 1.416 / 1.521 / 1.652) — **the max
alone is not.**

---

## 3. 🔴 A3.3 — the deferred amendment, now landed: §0.1 over-attributed scope to ROW 0s

**QA found this in review, before executing, and was right.** §0.1's inheritance table said the
M1–M4 numeric results were *"re-measured and unchanged — **see ROW 0s**"*. ROW 0s's predicate reads
`slots.csv` **alone** and recomputes only `4,000 / 435 / 10.875%`. It **never opens `decodes.csv`**,
never cross-references `20260049`'s `freq_hz` / `dt_s` / `reported_snr_db`, and **could not detect a
numeric change if one existed.**

**⇒ Two claims, two rows, and the table conflated them:**

- **Numeric invariance across the bump is ROW 0r's**, already measured and landed (`0/435` on decode
  count, `freq_hz`, `dt_s`, `reported_snr_db`). **Cite ROW 0r.**
- **ROW 0s's entire scope is the aggregate event count on `20260050`**, recomputed rather than
  inherited from anyone's reading of ROW 0r's prose.

🛑 **"See ROW 0s" for numeric invariance is an OVER-CITATION and must not be made.**

**No predicate, verdict, threshold or STOP branch changed** — this is a scope clarification of an
inheritance table, deliberately **deferred until QA handed back the tree** so the record shows a
correction rather than a goalpost moving mid-run.

🔴 **The pattern in my own four defects, stated because it is the useful part:** defects 1–4 are
**all scope-and-citation faults; not one touches a fire condition.** That is either the truth about
this spec or my blind spot, and it cannot be told apart from the inside. **A future spec review
should attack the predicates first, on the assumption that the prose is where I am weak and the
gates are where I am not — or that I have simply never been caught.**

---

## 4. Process, upheld

- ✅ **QA verified the filter exclusion mechanically rather than claiming it** —
  `--filter "Category!=AwgnFpReplay&FullyQualifiedName~FpParityP3Tests"` returning **zero tests**.
  That is exactly the HK-022 mitigation `AWGN-FP` A3.1 made mandatory: **a filtered-out suite is
  silent, not green.**
- ✅ **The clobber guard fired zero times because it was not needed** — both output paths were
  untracked, outputs landed in the gitignored `_out/`, and I confirmed `git ls-files
  qa/rr-study/fp-parity/_out/` is **empty**. The guard's value is that it would have thrown *before*
  decoding; it was not asked to.
- ✅ **`AwgnFpReplayTests.PinnedShaWinX64` verified untouched** at `ce02c7ba…153e`. The new class
  carries its own independently computed `6b2e16a6…4f85c`. **The `20260049` landed-row identity
  survived a second week of pressure.**
- ✅ **The shared-tree hazard was disclosed in QA's own §0** rather than left to this ruling.

**⚠️ Recorded, not chased, and NOT evidence of anything:** the paired run took **5 m 18 s** against
ROW 0r's **3 m 48 s** on the identical population. QA flagged it and correctly declined to chase it
— no row depended on it. 🛑 **Neither figure may be inherited as a decode-time baseline by any
future arm**; if run time ever becomes a metric, it earns its own pre-registration.

---

## 5. What is now unblocked, and the trap in it

**P3 closes. P4b (ROW 2 / ROW 3) has all its inputs**: `F = +8.00 dB` (upper bound, ROW 1),
`T = 2.622 dB` (carried forward, §2.4).

🔴 **`F − T = 5.378 dB` against a 6.0 dB bar ⇒ ROW 3 fires: no dev-task is authored.** This is
**not new de-blinding** — `FP-PARITY` A2.3 published this exact arithmetic on 2026-09-04 (*"would
land ROW 3, margin 5.38"*), before P3 ran. ROW 2 and ROW 3 are exact complements, so the verdict was
mechanically determined the moment `T` carried forward.

🛑 **P4b MUST NOT BE RUN AS A FORMALITY, and A2.3 said so in advance.** The verdict turns on **one
decode's 1 dB readout quantum**, and on **which binary recorded it**. Whoever writes it owes, per
A2.3: the lowest-5 table **with the binary each decode was recorded on**, and the **four-sweep
leave-one-out `F` quoted beside the five-sweep `F`**. Had the single pre-bump `+8.00` read −17 dB
instead of −18 dB, `F − T` would be 6.378 and **ROW 2 would fire instead — authorising a dev-task.**

🛑 **ROW 3's own wording is binding when it lands: PARKED, not closed.** *The emission-side floor
cannot be set with the project's required margin on the evidence available.* **Do not soften it into
"needs more data", and do not re-run with a smaller margin.** The 6.0 dB is a policy margin whose
justification (1 dB quantum + 1 dB conversion-sign + ≥4 dB S1b truncation) is unchanged by P3.

**P4b is not authorised by this ruling.** It is the PO's call whether to run it now, and it needs a
spec of its own for the A2.3 reporting obligations.

**Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>**
