# QA — Task 4 (489135a recompute) RESULT: cross-instance claim stays WITHDRAWN, plus a
# correction — this corpus DID reach the DT cliff, in its final ~2 hours

**Author:** QA, 2026-07-31 (11:37 UTC, `date -u`, per HK-017). Repo at `8bd5cb14`.
**Answers:** `2026-07-31-1030-architect-to-qa-task4-method-ruling-dt-derived-drift.md` §3's
pre-registered reading rule, as corrected by
`2026-07-31-1044-architect-to-qa-task4-drift-definition-corrected.md`.
**Script/data:** `measurement_489135a_recompute.py`,
`measurement_489135a_recompute_report.md`, `measurement_489135a_recompute_run.log` (this
directory). Raw jt9 output at
`artefacts/20260728_live_run_2354-8080/owsfz/jt9_ALL.TXT` (70,822 lines), git-ignored.

---

## 0. Headline

**The cross-instance claim stays withdrawn.** Applying `1030` §3's reading rule exactly as
written: drift-free parity (56.6%–56.7%, both candidate cutoffs agree) lands **materially
below** where the established density-law curve predicts for this corpus's density (19.81 ref
decodes/cycle), not merely "within the overall range." Row 2 fires, not row 1.

**Separately — a correction, found while running this, not assumed:** `1030` §5.1 (and `1044`
§2's restatement of it) states 489135a "never reached the cliff... worst drift ~1.5s at h14."
That figure used the pre-`1044` drift definition. Under the **corrected** definition `1044`
itself established, drift at h=14 is **−2.397s** — inside the measured 2.34–2.48s cliff
bracket, not comfortably below it — and the raw parity data for h=13/h=14 shows a real, sharp
collapse (79.4% → 48.8% → 20.6%) exactly where that crossing happens. See §3.

## 1. Self-checks — all pass

Per `1030` §3, mandatory, before any reading:

| self-check | result |
|---|---|
| WAV cycles | 3,575 (expected 3,575) ✔ |
| Our decodes in window | 44,223 (expected 44,223) ✔ |
| jt9 decodes in window | 70,822 (expected 70,822) ✔ — exact match, not just close |
| Unrestricted matched pairs | 42,668 (expected 42,668) ✔ — reproduces the existing (suspended) `anova_report_40m.md` exactly, confirming matching/corpus identification has not drifted |
| WSJT-X DT control | 0.60 ppm — **flat, holds** |

Run is **not void**.

## 2. Headline: restricted parity at both candidate cutoffs

Reusing `anova_common.match_pairs`/`parse_all_txt` throughout, not reimplemented. One
precision bug was found and fixed during this run before anything was reported: the first
pass filtered the headline cutoffs against the integer hour-bucket index used for the display
curve (§4), which for `h<2.40` silently admitted the *entire* h=2 bucket (elapsed_h up to
3.0, not 2.4) and for `h<3.06` the entire h=3 bucket. Refiltered at the precise per-cycle
`elapsed_h` instead — the substantive conclusion doesn't move (56.7%→56.6%/56.7%), but the
number reported here is the corrected one, not the first one produced.

| cutoff | matched | ref (jt9) | parity | 95% CI |
|---|---:|---:|---:|---|
| `h < 2.40` (`1044`'s corrected definition, `drift(h) = DT_ours(h) − 0.7251`) | 10,952 | 19,342 | **56.6%** | [55.9%, 57.3%] |
| `h < 3.06` (QA's slope-only candidate, `1041` §2) | 14,107 | 24,900 | **56.7%** | [56.0%, 57.3%] |

**Agreement check (`1044` §3's added requirement):** the two cutoffs land within 0.1 point of
each other, both CIs overlapping almost completely. They select the **same** row of the
reading rule (see §5) — no disagreement to escalate. The choice of cutoff is immaterial here;
the result is robust to it.

## 3. Correction — 489135a's final ~2 hours actually reached the cliff

`1030` §5.1: *"Its worst drift is ~1.5s at h14... This session never crossed \[the cliff\]."*
`1044` §2 repeats this without re-deriving it: *"This does not affect 489135a... its worst
drift is ~1.5s against a 2.34–2.48s cliff."*

That **~1.5s figure is the raw median DT at h=14** (from the pre-`1044` reading of "drift"),
not the corrected `drift(h) = DT_ours(h) − C` `1044` itself defines. Recomputed under the
definition `1044` actually specifies:

| h | matched | ref | parity | drift (corrected, C=0.7251) |
|---:|---:|---:|---:|---:|
| 11 | 752 | 915 | 82.2% | −1.906 |
| 12 | 569 | 717 | 79.4% | −2.070 |
| **13** | 716 | 1,467 | **48.8%** | **−2.233** |
| **14** | 416 | 2,023 | **20.6%** | **−2.397** |

The cliff is bracketed at 2.34–2.48s (defect report §2.3). h=13's corrected drift (−2.233) sits
just below it; **h=14's (−2.397) sits inside it.** And the parity data — matched/ref counts,
not a fitted quantity — shows exactly the collapse signature this whole programme has been
chasing: a sharp, sustained drop precisely where the corrected drift crosses into the bracket,
not decoder noise (n=717 to 2,023 per hour, not a handful of cycles).

**Stated at the appropriate confidence, not overclaimed:** the drift figure here is a linear
*fit* extrapolated from hourly-median DT, not a direct per-cycle cross-correlation measurement
(no OpenWSFZ WAV archive exists for this session — this is exactly why the DT method was
needed at all, per `1030` §2). What is **directly measured**, not fitted, is the parity
collapse itself. The fit crossing the cliff bracket at the same hours the raw parity data
independently collapses is corroboration, not proof by itself — but it is corroboration, and
the "never crossed it" claim in two Architect documents does not survive this recomputation
unamended.

**This does not change §0's headline** — both restriction cutoffs (2.40h, 3.06h) sit hours
before h=13, so neither restricted parity figure is contaminated by this late-session
collapse. It is a correction to `1030` §5.1/`1044` §2's characterisation of the corpus, not to
the headline result.

## 4. Parity as a function of drift — the full curve

Per `1030` §3 item 3 ("publish the curve, not just the threshold — a single number discards
information that is already paid for"):

| h | matched | ref | parity | 95% CI | drift (corrected) | drift (slope-only) |
|---:|---:|---:|---:|---|---:|---:|
| 0 | 4,188 | 7,131 | 58.7% | [57.6%,59.9%] | −0.107 | −0.000 |
| 1 | 4,785 | 8,564 | 55.9% | [54.8%,56.9%] | −0.270 | −0.164 |
| 2 | 4,839 | 8,685 | 55.7% | [54.7%,56.8%] | −0.434 | −0.327 |
| 3 | 4,908 | 8,627 | 56.9% | [55.8%,57.9%] | −0.597 | −0.491 |
| 4 | 4,426 | 7,602 | 58.2% | [57.1%,59.3%] | −0.761 | −0.654 |
| 5 | 4,338 | 7,283 | 59.6% | [58.4%,60.7%] | −0.925 | −0.818 |
| 6 | 3,704 | 5,622 | 65.9% | [64.6%,67.1%] | −1.088 | −0.981 |
| 7 | 3,210 | 4,412 | 72.8% | [71.4%,74.0%] | −1.252 | −1.145 |
| 8 | 2,754 | 3,782 | 72.8% | [71.4%,74.2%] | −1.415 | −1.309 |
| 9 | 1,856 | 2,414 | 76.9% | [75.2%,78.5%] | −1.579 | −1.472 |
| 10 | 1,207 | 1,578 | 76.5% | [74.3%,78.5%] | −1.742 | −1.636 |
| 11 | 752 | 915 | 82.2% | [79.6%,84.5%] | −1.906 | −1.799 |
| 12 | 569 | 717 | 79.4% | [76.2%,82.2%] | −2.070 | −1.963 |
| 13 | 716 | 1,467 | 48.8% | [46.3%,51.4%] | −2.233 | −2.126 |
| 14 | 416 | 2,023 | 20.6% | [18.9%,22.4%] | −2.397 | −2.290 |

**Read with care, not taken at face value — the h=6→12 rise is very likely propagation, not
drift.** Parity climbs from 55.7% (h=2) to a peak of 82.2% (h=11) while drift is monotonically
*worsening* the whole time. That is not the drift-vs-parity relationship this measurement is
looking for; it is 40m's diurnal cycle (session spans 23:54 UTC → 14:51 UTC, night into day)
changing how many stations are audible and how crowded the band is, which is exactly the
*density* axis the cross-band law is about, moving underneath the drift axis this curve plots
against elapsed hour. This is presented descriptively — reading a causal drift story into the
h=6–12 rise would be the same mistake `1030` §4.1's pitfall table warns against for
Measurement D (defining/reading a stratification without controlling the other axis). Not
reading it further here.

## 5. Reading rule — applied verbatim, per `1030` §3

Quoted exactly:

| outcome | consequence |
|---|---|
| Drift-free parity lands **within the 53.2%–91.6% range** at a position consistent with 19.81 ref decodes/cycle | The fourth density-law point is **restored**. The cross-instance claim I withdrew is **supported** — two capture chains, one relationship |
| Drift-free parity lands **materially outside** that range for its density | The cross-instance claim stays **withdrawn**, and the two chains differ. Report the gap; do **not** rationalise it |
| The |drift| < 0.5s window yields **too few cycles to bound** (report the CI) | Inconclusive. Report as such. **Do not widen the window to manufacture significance** |

**Row 3 does not fire.** n=10,952–14,107 matched pairs, n=19,342–24,900 reference decodes,
tight CIs (~1.4-point width) — this is not an underpowered read.

**Row 1 vs row 2 — the position-consistency test, done properly, not eyeballed:**

The density-law fit (`2253` §3.1): `parity(%) ≈ 111.9 − 37.63·log₁₀(ref decodes/cycle)`.
At 19.81 decodes/cycle: `log₁₀(19.81) = 1.29689`, predicted parity = **63.10%**.

Residuals of the fit against its own three anchor points (all Voicemeeter/no-drift,
unaffected by anything in this document):

| corpus | density | predicted | actual | residual |
|---|---:|---:|---:|---:|
| 80m | 3.38 | 92.00% | 91.6% | −0.40 pt |
| 10m | 8.52 | 76.89% | 77.7% | +0.81 pt |
| 20m | 36.36 | 53.16% | 53.2% | +0.04 pt |
| **489135a (this measurement)** | **19.81** | **63.10%** | **56.6–56.7%** | **−6.4 to −6.5 pt** |

The three anchor points' own residuals are all under 1 point — the fit is close to exact for
same-instance data. 489135a's residual is **six to sixteen times larger**, and its own 95% CI
(56.0%–57.3% at best) does not come close to including 63.10% at either cutoff. This is not a
borderline call.

**Row 2 fires.** Drift-free parity lands materially outside the position the density law
predicts for 19.81 decodes/cycle. **The cross-instance claim stays withdrawn** — the two
capture chains do not appear to obey the same parity-vs-density relationship, even once
489135a's own drift defect is corrected for. Reporting the gap, not rationalising it, per the
rule's own instruction: 489135a decodes ~6.4–6.5 points worse, drift-corrected, than a
Voicemeeter/no-drift instance would at the same reference-decode density.

## 6. Reference-method by-product (descriptive only — not subject to the reading rule)

Per `1030` §4 — jt9's re-decode of `wsjt-x/wav/` vs the live WSJT-X application's own decodes
of the identical audio (`wsjt-x/ALL.TXT`):

- jt9 decodes: 70,822
- Live WSJT-X decodes: 67,418
- Matched: 66,173 (93.4% of jt9's, 98.2% of WSJT-X's)

The two reference methods agree closely on this audio — jt9 decoded modestly more (~5%) than
the live application did, consistent with jt9 running at a non-default depth (`-d 3`) rather
than a difference in kind. This does not resolve the still-open `2253` §3.2 reference-method
question in general (one corpus, one comparison), but on this audio the two are not materially
different reference sources. Descriptive; not pooled with §2/§5's parity recompute.

## 7. What this does not do

- Does not change the menu (row 1/4/5) — the Captain's, unaffected.
- Does not touch `src/`. No push, no merge (HK-014/HK-010) — committed locally. No
  `pre_merge_check.py` (HK-006).
- Does not re-open the diagnostic programme — this is the already-queued task 4, per the
  closing handoff §0's stop rule.
- Does not assert the h=6–12 propagation reading as a finding — flagged descriptively (§4),
  explicitly not read further.
- NFR-021: message text used only to build match keys via `anova_common`'s own convention;
  never printed beyond aggregate counts. Raw jt9 output and all WAVs stay under git-ignored
  `artefacts/`.

## 8. Cross-references

- `2026-07-31-1030-architect-to-qa-task4-method-ruling-dt-derived-drift.md` — the method and
  reading rule this applies; §5.1 corrected at this document's §3.
- `2026-07-31-1044-architect-to-qa-task4-drift-definition-corrected.md` — the drift definition
  (§1) and its added agreement-check requirement (§3), both applied above; §2's restatement of
  "never crossed it" corrected at §3 above.
- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` §3.1 — the
  density-law fit and its three anchor points, reused verbatim for the residual comparison.
- `qa/endurance/2026-07-29-489135a/anova_report_40m.md` — the suspended 62.4%, whose
  unrestricted-window figures this recompute's self-check reproduces exactly.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` §2.3 — the 2.34–2.48s cliff bracket §3
  above applies.
- `measurement_489135a_recompute.py`, `_report.md`, `_run.log` — this measurement's script,
  rendered output, and full console log (including the smoke-test validation preceding the
  full run).

---

*Per HK-015 this is QA → Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry
`date -u` UTC. Per HK-018, before reading anything the unrestricted self-check was confirmed
against the existing report, and a precision bug in the headline filter (§2) was found and
fixed before this document was written, not after. The row 2 vs row 1 determination in §5 is
mechanical (the reading rule applied as written, residuals computed, not eyeballed) — if the
Architect reads the position-consistency test differently, that is a reason to say so, not a
reason for me to have picked the more convenient row.*
