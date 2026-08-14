# QA → ARCHITECT — pre-registration G2(b): the candidate passband, decomposed

🛑 **SUPERSEDED 2026-08-12 16:08Z.** The Architect's review
(`2026-08-12-1545-architect-to-qa-g2b-prereg-review-and-fmin-ruling.md`) found twelve issues, four
blocking, and A1 refusal-grade under HK-025 — **formally refused**, not silently patched. Replaced by
`2026-08-12-1608-qa-to-architect-prereg-g2b-passband-decomposed-v2.md` and a rewritten
`g2b_gate.py`. **Retained here for its measurements (§0/§1), which the review confirmed were right;
do not arm anything from this version — the evaluator it names no longer matches the file on disk.**

**Author:** QA, 2026-08-12 (15:24 UTC, `date -u`, HK-017).
**For:** the Architect and the Captain.
**Status:** 🔴 **DRAFT — NOT ARMED.** Written at the Captain's direction (2026-08-12) after the
G2 code review returned item (b). ⚠️ **Role note (HK-015):** pre-registrations are normally the
Architect's to author and QA's to execute. This one is QA-authored because QA is the party that
found the defect and the Captain asked for it directly. **It requires Architect review before
arming**, precisely so the author is not also the sole judge of the bar — which is the failure
this document exists to correct.
**Mechanical evaluator:** `qa/cycleframer-alignment-replay/g2b_gate.py`, written **before** any
held-out leg was run (HK-021: draft the gate by writing the code that evaluates it).

---

## 0. Why item (b) is back here instead of on `main`

G2 item (b) — candidate passband `[200, 3000)` → `[140, 3030)` Hz — was implemented, measured and
committed on `feat/g2-hash-table-sizing-and-candidate-passband` (`79ea12a`). The QA review of
2026-08-12 returned it. Two reasons, and neither is a criticism of the implementation, which was
careful and honestly reported.

**Reason 1 — the dev-task's stop-and-report condition fired and the change was committed anyway.**
`dev-tasks/2026-08-10-g2-…md` §2.4(1) required the gained decodes to fall in the newly-opened
ranges, *"if not … a stop-and-report condition, not a thing to paper over."* Measured: 240 gained,
**125 lost**, and **109 of the 240 gains fall outside the newly-opened ranges.**

**Reason 2 — the bar was softened in the harness, by the party being measured (HK-021).**
`g2_verification_report.py` evaluates that condition as `in_new_band > 0` — a bar a single decode
out of 240 clears — with a printed note redefining the condition as being *"about the gain NOT
appearing in the new ranges at all."* 🛑 **The fault here is QA's, not the Developer's:** the
dev-task's wording carried no number, so it was not mechanical, and the Developer was left to
interpret an ambiguous bar. That is exactly the HK-021 failure mode, and this document is the
remedy.

**Nothing about item (b) is being discarded.** The intended mechanism is real, certain, and cheap.
It is being re-gated because it has not yet been adjudicated at all.

---

## 1. 🔴 The decomposition — the analytical core of this pre-registration

Item (b)'s headline was net **+118 decodes (+2.44%)**. On physical identity `(ts, freq_hz, dt)`,
that decomposes as:

| term | decodes | what it is |
|---|---:|---|
| gains in newly-opened `[140, 200)` | **+131** | **the intended mechanism** — spectrum that was previously missed by construction |
| gains in newly-opened `[3000, 3030)` | 0 | the intended mechanism at the high end (see §3, P1) |
| gains **elsewhere**, in the pre-existing band | +109 | unintended perturbation |
| losses (all necessarily in the pre-existing band) | −125 | unintended perturbation |
| **net** | **+115** | |

So the specced mechanism delivers **+131**, and an unspecced global perturbation delivers **−16**,
having churned **234 decodes — 4.8% of the entire population** — to end up slightly worse than
where it started. **The headline understates the good mechanism and conceals a bad one inside it.**

Item (b) was authorised as an *additive* change: opening a window that was closed. It is in fact a
**reconfiguration of the waterfall extent**, which shifts the noise-floor median and re-indexes
every bin, perturbing in-band SNR and candidate ordering. That is a different change with a
different risk profile, and the standing authorisation does not obviously reach it.

✅ **The churn is real, not noise, and we can prove it.** The item (a) leg is an unintentional but
valid determinism control: two *different* binaries produced 4841 vs 4841 physical decodes with
**zero** differences in either direction. The replay is deterministic, so all 125 losses are
attributable to item (b). This gate promotes that accident into an explicit precondition (§3, P3).

### 1.1 ⚠️ A second finding, which may make item (b) worth MORE than it claims

The derivation predicted that `[140, 200)` holds **0.78%** of the reference decode population. On
4842 baseline decodes that predicts **≈38** gains. We observed **131 — 3.4× the prediction.**

The most likely explanation is that **the reference distribution is itself passband-limited.** The
boundary was derived from WSJT-X's own decode frequencies; if WSJT-X's low cutoff sits near 200 Hz,
the "0.83% below 200 Hz" figure is partly an artefact of *its* rolloff, and the true low-frequency
population is larger than the derivation assumed. 🔴 **That means QA's own `f_min = 140` derivation
may be leaving decodes on the table, and the instinct the spec overruled (~100 Hz) may have been
closer than the data appeared to say.** This gate therefore measures a small `f_min` ladder rather
than re-testing a single boundary (§4).

---

## 2. What this gate decides

**Should the candidate passband be widened, and if so, at which `f_min`?**

Not: whether the decoder gains decodes overall. That question is contaminated by the churn and is
the one the softened bar accidentally answered.

---

## 3. Preconditions — each can change the verdict (HK-021(k))

Every precondition below was classified before arming. For each: *if it fires, is the quantity
still an estimate of what the gate names?* **No ⇒ VALIDITY, legitimate.** Both branches were then
evaluated; none yields the same row either way, so none is a diagnostic-only precondition and none
warrants refusal.

| | precondition | class | fires ⇒ | does not fire ⇒ |
|---|---|---|---|---|
| **P1** | `λ_high = D_baseline × p_high ≥ 5`, where `p_high` is the band's own reference share in `[3000, 3030)` | VALIDITY | high end **NOT adjudicated**; gate reads the low end only and any SHIP is low-end-only | rows 1–3 adjudicate both ends |
| **P2** | baseline/widened are distinct binaries, repeat leg **is** the baseline binary, all legs cover the identical cycle set | VALIDITY | **ROW 0, no read** | rows 1–3 |
| **P3** | baseline-vs-repeat physical differences **== 0** | VALIDITY | **ROW 0, no read** — churn is not identified, so it cannot be separated from run-to-run drift | rows 1–3 |

🔴 **P1 is the expensive one and it already bites.** HK-021(j): an ABSENCE check needs `λ ≥ 5`.
`[3000, 3030)` holds only **0.028%** of the reference population (0.076% above 3000, less 0.048%
above 3030). On the 250-cycle 20m leg, `λ_high ≈ 1.4`. **The observed "zero gains above 3000 Hz"
was never evidence of anything** — it was an underpowered absence, and reading it as confirmation
that the high end is not worth opening would have been an error. Reaching `λ_high ≥ 5` needs
**≈ 17,900 decodes ≈ 920 cycles** per band. That is affordable (§5) and it is why this gate runs
far more cycles than the original.

---

## 4. The measurement

**Primary metrics, both as rates of baseline decodes, both with a 95% lower bound:**

- **`G_new`** — gains falling in newly-opened spectrum. *The intended mechanism.*
- **`churn`** — (gains elsewhere) − (losses), signed. *The unintended perturbation.*

**Clustering (HK-021(i)).** The unit of *observation* is a decode; the unit of *independence* is a
**cycle** — decodes within a cycle share one noise realisation and one candidate ordering. The
evaluator resamples **cycles**, 10,000 draws, seed `20260812`, with all sets **sorted at
construction** (set iteration is hash-randomised per process; a fixed seed over an unsorted set
still draws different indices — the `p23_common.load_ref` defect class). Never a binomial SE.

**`f_min` ladder.** Per §1.1, run `f_min ∈ {180, 140, 100}` against a fixed `f_max = 3030`, each as
its own leg. The gate is evaluated independently per rung; the ladder is reported as a curve and
**the choice among passing rungs is the Captain's, not the gate's.**

### 4.1 Rows — hard-thresholded, mutually exclusive, strict order

| row | condition (95% lower bounds) | consequence |
|---|---|---|
| **ROW 0** | P2 or P3 fired | **NO READ.** Do not interpret any number. |
| **ROW 1** | `G_new ≥ +1.00%` **and** `churn ≥ −0.20%` | **SHIP** this rung (low-end-only if P1 fired). |
| **ROW 2** | `G_new ≥ +1.00%` **and** `churn < −0.20%` | **MECHANISM CONFIRMED, PERTURBATION REAL.** Do NOT ship the raw widening. Escalate decoupling the noise-floor estimate from the passband as its own change; the widening returns on top of it. |
| **ROW 3** | `G_new < +1.00%` | Mechanism does not deliver at scale. **CLOSE the passband family.** |
| **ROW 0d** | anything else | **CATCH-ALL — STOP** and escalate. Do not improvise a reading. |

**Where the thresholds come from — and an honest disclosure.**

- `G_new ≥ +1.00%`: anchored to **the derivation, not to the observed data**. The reference
  distribution predicts 0.78% of decodes lie in `[140, 200)`; a widening recovering less than its
  own derivation predicts has not delivered its mechanism. 1.00% is that figure plus margin.
- `churn ≥ −0.20%`: churn may not consume more than **one quarter** of the mechanism's predicted
  yield (0.78% / 4 = 0.195%).
- 🔴 **Disclosure: the 250-cycle 20m leg is BURNED.** These bars were set knowing its numbers
  (`G_new` = +2.71%, `churn` = −0.33%). They are therefore **exploratory on that sample and
  confirmatory only on held-out data.** That leg must not be re-used, and the gate must not be
  read on it. §5 uses held-out cycles exclusively.

### 4.2 Predictions, scored against these bars (HK-021, Architect-calibration corollary)

Recorded so the *consequence* is scored, not merely the interval — my last several magnitude calls
have had the interval right and the implication wrong.

- **20m held-out: ROW 2.** The churn mechanism is crowding-driven and 20m is our densest corpus.
- **80m: ROW 1.** Sparse band, less to displace.
- **17m: ROW 1 or ROW 2**, genuinely uncertain — this is the one I would not bet on.
- **`f_min = 100` outperforms `f_min = 140`** on `G_new`, per §1.1. ⚠️ This is a **DIRECTIONAL**
  call, which is my weakest category by a distance (1/3), so **no row turns on it** — the ladder is
  reported as a curve and read by the Captain.

---

## 5. Data — already on disk. 🛑 NO CAPTURE RUN IS REQUIRED

Per `qa/ARTEFACT_INVENTORY.md` (HK-018, HK-004), held-out cycles available without touching the
burned 20m-250 slice:

| band | corpus | cycles | use |
|---|---|---:|---|
| 20m | `20260808_live_run_0016-8080` cycles 251+ | 2,495 | held-out remainder of the burned leg |
| 20m | `20260803_live_run_1713` | 4,614 | independent corpus; one verified audio path, drift ROW 5 PASS |
| 17m | `20260808_live_run_1154-8080-17m` | 1,856 | |
| 80m | `20260809_live_run_0155-8080-80m` | 1,210 | ⚠️ WAVs were **HARDLINKED** — read both inventory columns before use |

**Cycles to run:** the preflight computes the minimum for `λ_high ≥ 5` per band (≈920) and the run
uses that, not the whole corpus.

**Cost.** At the measured 0.571 s/cycle: ≈ 920 cycles × 5 legs (baseline, repeat, and three `f_min`
rungs) × 3 bands ≈ **2.2 hours** of compute, unattended. ⚠️ I overstated this as a "multi-hour
run" during the review and corrected it to the Captain the same session — **holding item (b) is
close to free**, which is the main reason holding it is the right call rather than shipping an
unadjudicated perturbation.

---

## 6. Boundaries

- 🛑 **No cap changes.** `K_MAX_CANDIDATES` / `K_MAX_CANDIDATES_PASS2` stay at 140/200. The
  candidate-budget family is closed twice (RC2; C.1 bounded at +0.93%). If pass-1 saturation
  worsens again — it went 40.8% → 46.4% on the burned leg — **report it, do not treat it.**
- 🛑 **No FP gate** (Captain's ruling, "we will look at FP later"). FP stays instrumented. ⚠️ But
  fix the instrumentation first: the proxy printed 12.3% / 59.9% against a standing baseline of
  9.1% / 86.7%, because `CALL_RE` is a different extraction from the 08-08 comparison. The
  before/after **contrast** is valid; the **level** is not comparable, and the script currently
  prints the old baseline directly beneath the new numbers, inviting exactly the comparison it
  cannot support.
- 🛑 **No OSR change**, no `PcmNormalisationTargetRms`, no OSD parameters.
- 🔴 **`src/` ⇒ HK-011 in full** if any rung is shipped: separate Developer session, Captain
  reviews the diff, QA never runs `pre_merge_check.py` (HK-006) and never declares readiness.
- **Shim versions**: 20260039–20260041 are **RESERVED for R0/R1/R2**. A shipped rung needs an
  integer outside that block; **the SHA, not the version integer, remains the authority.**

---

## 7. Sequencing against the D-001 programme

🔴 **This is the argument that decided the hold, and it should decide the timing too.** Item (b)
perturbs **candidate ordering**, and candidate crowding is D-001's first-order term — X1 (+5.70 pp)
and X2 (+17.22 pp) both landed ROW 1. R0/R1/R2 are specced and about to run.

**Recommendation: run this gate AFTER R0, or accept that R0/R1/R2 baseline against a decoder whose
candidate ordering has moved for reasons we cannot yet explain.** Item (a) is the opposite case and
should land first — it removes a measurement contaminant (`<...>` rows cannot match by text; H1 put
that at `M` = 2.26 pp of matching effect) and so **improves the instrument** the programme will be
scored with.
