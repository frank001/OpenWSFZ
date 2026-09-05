# `S5-STANDALONE` — Architect ruling: the regression claim is not supported, and `3.25×` should be retired

**Architect, 2026-09-05 15:17 UTC** (`date -u`, HK-017). Adjudicates
`2026-09-05-1505-qa-to-architect-s5-standalone-result.md` (QA, commit `bc023a4`), which executed
`2026-09-05-1311-architect-to-qa-spec-s5-standalone-current-build.md`.

🛑 **Nothing was measured by the Architect. No new live run. No board figure moves until the PO
ratifies §7.** Recommendation to the PO is in **§7**; the guards that survive it are in **§4**.

---

## 1. QA's result reproduces exactly, from primary sources (HK-018)

Re-derived independently of QA's report and independently of the board — each count taken from
the owning run's own `report.md` §10 gate line, each statistic recomputed:

| Quantity | QA reported | Architect re-derived | Source |
|---|---|---|---|
| Today, `main`@`df13da0`, standalone/cold | 6/300 = 2.000% | **6/300 = 2.000%** | `results/2026-09-05-10bbaad-s5-standalone-n300/report.md:86` |
| Today, exact CP95 | [0.737%, 4.302%] | **[0.737%, 4.302%]** | recomputed |
| July `a3738fc`, standalone/cold, `f-002` shipped | 8/300 = 2.667% | **8/300 = 2.667%** | `results/2026-07-04-a3738fc-f002-s5-n300/report.md:112` |
| July, exact CP95 | [1.158%, 5.187%] | **[1.158%, 5.187%]** | recomputed |
| Fisher one-sided (upper) | p = 0.7908 | **p = 0.7908** | recomputed |
| Ratio today/July | 0.75× | **0.75×** | recomputed |
| Firing rule `k ≥ 18` | k=17 p=0.0502, k=18 p=0.0346 | **identical to the digit** | recomputed against spec §5 |
| WSJT-X control | 0/300 | **0/300** (UB95 0.99%) | same gate line, line 85 |

**The pre-registered firing rule was applied as written.** `k = 6` against a gate of `k ≥ 18`.
**ROW 1 does not fire, and the point estimate moved the wrong way for a regression.**

ROW 0a–0e and ROW 2/3 outcomes accepted as reported. ROW 0b (300/300 byte-identical stimulus) is
the row that lets ROW 1 be read as a ratio at all, and it is clean.

---

## 2. One correction to QA's own analysis — §6.1 is a cosmetic defect, not a measurement-integrity one

QA reports (§6.1) that `matcher.py`'s pass-2 mis-attributed the warm-up decode as an FP, that this
was corrected by hand-filtering the logs, and that "all counts reported are the corrected counts" —
implying today's `6` rests on an operator's manual step. **It does not.** Traced through the code:

- `matcher.py:184–186` — pass 2 does emit an FP row for every unconsumed decode, with no time
  window. **QA's description of the defect is correct.**
- But `analyse.py:703–716` — the §10 gate quantity is computed from **`fp_in_window`**, where
  `fp_in_window = fp_sub[fp_sub["cycle_utc"].isin(s5_cycles)]` and `s5_cycles` is the set of
  `cycle_utc` values carried by the S5 truth rows. **The gate line never sees a decode outside the
  S5 injection cycles.**
- Today's warm-up landed at cycle `13:36:45Z`; the first S5 truth cycle is **`2026-09-05T13:38:30Z`**
  (`truth.csv` row 1). The warm-up is outside the window ⇒ **excluded automatically**, filter or no
  filter.

**Three consequences, all of which strengthen the result rather than weaken it:**

1. **Today's `6/300` does not depend on a manual correction.** The over-emission is confined to
   `S5_matched.csv` (a gitignored intermediate); the gate line is windowed by construction.
2. 🔴 **The historical battery series is NOT contaminated, and this is the load-bearing point.** I
   went looking for the opposite: in a battery run the log carries S1/S4/S7 decodes, and an
   unwindowed pass-2 would have reported those as S5 FPs — which would have made every battery count
   in the series junk, and with it the entire contrast I am ruling on. The downstream window is why
   battery runs read 0–4 and not dozens. **Both contexts' counts come off the same windowed
   instrument**, so the standalone-vs-battery comparison is instrument-consistent.
3. QA's recommended fix (a `--since` on `matcher.py`) is still worth doing, but it is **hygiene on an
   intermediate file, not a correction to any published number** — and it must not be logged on the
   board as "the FP counts needed manual correction", because that is not what happened.

⚠️ **Residual that does survive:** a stray decode landing *inside* an S5 cycle would still be
counted. In a rotated-log standalone run only the warm-up is stray and it sits outside; in a battery
run other scenarios occupy other cycles. So the exposure is real but empty in every run to date.

🔴 **Mechanical confirmation QA should run before this is treated as settled** (cheap, decisive, and
I am not entitled to assert it from code-reading alone): re-run `analyse.py` on the **unfiltered**
`owsfz-all.txt`/`wsjt-all.txt` and confirm the §10 gate line still reads `6/300` and `0/300`. If it
does not, §2 of this ruling is wrong and the adjudication below must be re-opened.

---

## 3. The ruling

**There is no supported false-positive regression, and there never was an established baseline to
regress from.**

`3.25×` was already carrying two unrepaired defects when it was HELD on 2026-09-04 19:2xZ:
outcome-selected window boundary (HK-021(y)), and a pre-window that is not an established baseline.
`S5-STANDALONE` adds a third, from an independent direction:

> A context-matched, stimulus-matched, cold-decoder contrast spanning the **entire** disputed era
> (July `a3738fc` → today `df13da0`) finds **0.75×**, p = 0.79, with **96.5% pre-registered power
> against `3.25×`**. Under the transportability assumption the power calculation itself rests on —
> that a code-borne multiplier shows up as a multiplier on the standalone rate — a real `3.25×`
> would have produced ≈26 events. Six were observed.

**Descriptive, and deliberately labelled non-citable (see §4(e)):** every measurement in the record
outside the pre-window sits in one narrow band.

| Population | k/N | rate | CP95 |
|---|---|---|---|
| July standalone (`a3738fc`) | 8/300 | 2.667% | [1.158, 5.187] |
| Today standalone (`df13da0`) | 6/300 | 2.000% | [0.737, 4.302] |
| Aug/Sep battery, **all 9 runs pooled** | 15/540 | 2.778% | [1.563, 4.540] |
| **All post-July AWGN slots, both contexts** | **21/840** | **2.500%** | **[1.554, 3.796]** |
| — the pre-window, for contrast | 2/180 | 1.111% | [0.135, 3.956] |

The pre-window is the **only** figure out of line, it is the **smallest** population in the table
(2 events), and its own CP95 comfortably contains 2.5%. The "step" is what you get by splitting a
nine-run series at the point the outcome looks most different and comparing a two-event low
fluctuation against everything else — which is precisely what HK-021(y) predicts, and precisely
what Defect 3 (the pre-window is not an established baseline) warned the figure was resting on.

**Recommendation: `3.25×` / `p = 0.0765` is RETIRED**, on the same footing as `4.88×`. Not
"unsupported pending more data" — retired, because all three of its defects are structural and none
is repairable by re-normalising or by collecting more of the same battery data.

---

## 4.🛑 What this does NOT establish — the guards, which are the point

Retiring `3.25×` is **not** a finding of "no regression". Do not let it become one.

**(a) The arm is nearly blind below ~2.25×.** Pre-registered power: 96.5% at `3.25×`, 71% at 2.5×,
34% at 2×, **2.5% at 1.35×**. A regression smaller than roughly 2.25× would have been missed with
near-certainty. **A non-firing ROW 1 is not evidence of absence at those magnitudes** — this was
written into the spec before the result was known, and it binds now that the result is in.

**(b) A battery-context-specific regression is not excluded.** ROW 3 is the only same-build context
pair that will ever exist and it is `6/300` vs `2/60` — wide, overlapping, pre-registered as
descriptive with no ratio and no p-value. It stays that way.

**(c) The two legs are not cadence-matched, and the mismatch flatters today.** Gap fraction 4.68%
today vs **12.7%** in July. ROW 2 found no detectable cadence association (p = 0.4448) but at n=13
runs that is low power — "not detected", not "clean". Across the corpus the most-gapped run carries
4/60 and the least-gapped 0–2/60, i.e. gapping is *associated with more* FPs, so July's looser
cadence may inflate the July leg and account for part of the 0.75×. It would take an implausibly
large cadence effect to mask a `3.25×`, but the confound is real and unmeasured.

**(d) 🔴 The WSJT-X control does NOT bound delivery equivalence between the two legs — do not use it
that way (HK-026).** It is tempting: 0/300 in July, 0/300 today, 0/840 across the battery, therefore
"the audio path didn't change". **That inference is invalid.** WSJT-X sits at a floor of zero; its
response is *flat* in exactly the 2–3% region where OpenWSFZ operates, so it cannot detect a change
there. The control does what it was always for — **excluding the rig as a source of false
positives** — and nothing more.

**(e) The pooled `21/840 = 2.500%` in §3 is descriptive and post hoc. It is NOT a ratified baseline
and must not be used to power anything.** I derived it after seeing the data, and pooling assumes
run-to-run homogeneity — which is the very thing `S5-BASELINE` ROW 2 probed and neither rejected nor
cleared (p = 0.0610). If the project wants a real baseline — and it is the thing this whole
investigation has lacked from the start — that is **its own pre-registration**, not a line in this
ruling.

**(f) This is a bundle contrast** (~2 months of change) ⇒ **no per-commit attribution**, in either
direction.

**(g) `ac6150d`'s "provably non-perturbing" claim stays contradicted.** `AWGN-FP` ROW 0r: 246/4,000
AWGN slots changed decode set across the `20260049`→`20260050` bump. Nothing here rehabilitates it.
**Slot-identity churn without a rate change is entirely consistent with today's result** — the
decoder demonstrably changed; what this ruling says is that its AWGN false-positive *rate* did not.

---

## 5. Recommendation on the offline `AWGN-FP` seam arm (spec §8) — **do not run it now**

§8 is the only design that could settle the sub-2.25× question: paired, n=4,000, no device, cadence,
warmth or era confound, and ROW 0r already proves the seam responds to a build change (HK-021(q)
satisfied). It is cheap to *execute* — 3m48s.

**I recommend against running it now**, on three grounds:

1. **A validity threat the runtime cost hides.** The seam omits `NormalisePcm` ⇒ ≈**6.9 dB** quieter
   than production. That is a different operating point on a decoder whose FP behaviour is a
   threshold phenomenon. Effect modification is not excludable, so a null there would not transfer
   to production, and a positive would not either.
2. **The setup cost is not small** — `ExpectedShimVersion` is a compile-time constant ⇒ a second
   checkout *and build*, plus harness porting.
3. **There is now a free alternative that is strictly better over time.** The S5 AWGN gate already
   runs on every routine battery at zero marginal cost. With ~840 post-July slots of prior, a genuine
   ≥1.35× drift accumulates visible signal across the next several sweeps for nothing — turning an
   expensive, confounded one-off into ongoing surveillance on the production path.

**When §8 *would* be worth it:** if the PO needs the small-effect question answered **now** rather
than over the next several sweeps — e.g. a release decision gates on it. Then §8 is the right
instrument despite the level bias, and it needs its own pre-registration (I would not reuse this
spec's rows).

---

## 6. Process defects — disposition

| # | Defect | Severity as ruled | Owner |
|---|---|---|---|
| 6.1 | `matcher.py` pass-2 has no run-window filter | **Downgraded** per §2 — cosmetic, confined to a gitignored intermediate; the §10 gate is windowed by `analyse.py`. Fix still wanted (`--since`), because it has now cost operator attention twice and the exposure is real if a stray decode ever lands *inside* an S5 cycle | QA |
| 6.2 | `run_scenario.py --run-dir` resolves against CWD, contradicting its own `--help` | **Upheld as reported — this one is the more serious of the two.** It is an NFR-021 near-miss: it placed raw callsign-bearing logs outside the `.gitignore` coverage scoped to `results/`, and only QA catching it before `git add` prevented it. Code or help text to be made to agree | QA |

Neither touches `src/`/`native/` ⇒ HK-011 not engaged. Both are QA-owned harness tools (HK-015).

🔴 **Board-hygiene note, not a criticism of the result:** `bc023a4` landed the result without the
board being updated in the same edit (HK-024). The board's newest entry still reads
"`S5-STANDALONE`, PRE-REGISTERED, NOT RUN" while the repo carries the executed result. Corrected in
the same commit as this ruling.

---

## 7. What the PO is being asked to ratify

1. **RETIRE `3.25×` / `p = 0.0765`** — never cite again, in any form, on the three structural
   defects in §3. Add to the standing never-cite list beside `4.88×`.
2. **Adopt §4 (a)–(g) as the standing guards** on how this result may be described — in particular
   that it is **not** "no regression", and that **`21/840` is not a baseline**.
3. **Close the live-arm line of the `FP-REGRESSION` investigation.** Do not commission another live
   S5 arm to chase the same question; no economically feasible live N can reach the magnitudes that
   remain open (~17 hours of playback for n=4,000).
4. **Do not run §8 now** (§5), with the named trigger that would reverse it.
5. **Optional, and separately pre-registered if wanted:** establish a *real* AWGN FP baseline — the
   thing the investigation never had. This is the one piece of new work I would argue *for*, and
   §4(e) is why it cannot be done by pooling in a ruling.

**Concerns stated once, as required:** if the PO prefers to run §8 anyway, my objection is §5(1) —
the 6.9 dB level bias — and I would want that pre-registered as a stated limitation of the arm
rather than discovered afterwards. Beyond recording it here I will not re-litigate it.

---

**Architect, 2026-09-05 15:17 UTC.** Committed locally, **not pushed** (HK-014; `main` far ahead of
`origin/main` carrying `ac6150d`'s `src/`+`native/` diff ⇒ HK-029 exception N/A). `git diff --stat --
src/ native/` empty at `HEAD`.
