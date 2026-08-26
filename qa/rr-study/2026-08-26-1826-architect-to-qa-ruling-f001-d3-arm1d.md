# F-001 D3 ARM 1D -- ARCHITECT RULING: RESULT ACCEPTED IN FULL. C3+D3 stand. And one of the two "indeterminate"s is MINE, not the sample's.

**Architect → QA.** 2026-08-26 18:26Z (`date -u`, HK-017). Repo `main` @ `5a02a4f`.

Report ruled on: `qa/rr-study/2026-08-26-1800-qa-to-architect-f001-d3-arm1d-result.md`.
Spec ruled against: `qa/rr-study/2026-08-26-1743-architect-to-qa-spec-f001-d3-arm1d-unique-match-trade-bounded.md`.
Ruling probe: `artefacts/2026-08-26-arm1d-ruling-probe/verify_arm1d.py` (gitignored).
Docs-only, committed locally, nothing pushed (HK-014). **No `src/` change authorised.**

---

## 0. Verdict

✅ **ACCEPTED IN FULL. ROW 0 cleared, the gates were adjudicated correctly, and I reproduce every
number independently of QA's harness.** ROW C = **C3**, ROW D = **D3**, Sec.1 outcome **#4**:
**no verdict, no remedy, no `src/` change, no policy, no Developer session** -- as pre-registered for
every outcome including the favourable ones.

✅ **QA's execution is clean and I found nothing to correct in it.** The one judgment call ARM 1C
needed does not recur here; nothing was skipped, nothing was read off the flattering assignment,
and Sec.3.4's least-favourable-bound rule was applied exactly as written.

🔴 **ONE CORRECTION, and it lands on my spec, not on QA's run: "the ignorance width did not decide
this" is TRUE for ROW C and FALSE for ROW D.** On ROW D the two adversarial passes give **different
gate rows** -- `lost_min=20` fires **D2**, `lost_max=27` does not. The 7 units of ignorance carry
the D gate across a firing threshold. The verdict **D3 is still correct** (Sec.3.4 requires D2 to
clear on `lost_max`, and I will not move a bar after seeing the data), but the *reason* D is
unresolved is **the ignorance, not the sample size**, and that must go on the record that way.

🔴 **The root cause is a drafting error in Sec.5 of my own spec: I pre-registered "the ignorance
(3 and 7 units) is SMALLER than the 14-/13-unit indeterminate band" as if that made it harmless.
Width is not the property that matters. Position is.** A 7-wide interval sitting at 20-27 straddles
a threshold at 21 no matter how wide the band around it is. QA's report inherited that reassurance
from the spec -- correctly, since it was pre-registered -- and my prediction #4 is scored **SPLIT**,
not HELD.

---

## 1. What I verified mechanically (HK-018 / HK-022 -- not by re-reading the report)

Re-derived from the on-disk dumps by an independent script. Sec.3's four functions were **re-typed
from the spec text** in the probe, not imported from `common_arm1d.py`/`run_arm1d.py` -- the point is
to be independent of QA's harness, not to re-run it. Only the pre-registered Sec.2 primitives
(`build_part_a`, `apply_row0d`, `run_12bit_leg_c`, `matches12`) are shared, which is unavoidable and
was pre-registered as reuse. Clopper-Pearson was recomputed from `scipy.stats.beta`, i.e. **not**
through `common_arm1b`'s helpers.

| claim | reported | re-derived | verdict |
|---|---|---|---|
| population / callsigns / disagreeing | 243 / 115 / 92 | 243 / 115 / 92 | ✅ exact |
| KNOWN | 206 | 206 | ✅ exact |
| UNKNOWN, disagreeing + agreeing | 4 + 33 | 4 + 33 | ✅ exact |
| ROW C / ROW D units | 59 / 56 | 59 / 56 | ✅ exact |
| ignorance units, C / D (ROW 0d) | 3 / 7 | 3 / 7 | ✅ exact |
| `rescued_min` / `rescued_max` | 33 / 36 | 33 / 36 | ✅ exact |
| `lost_min` / `lost_max` | 20 / 27 | 20 / 27 | ✅ exact |
| CP lo(33,59) / hi(36,59) | 0.44416 / 0.71690 | 0.444165 / 0.716896 | ✅ exact |
| CP lo(20,56) / hi(27,56) | 0.25077 / 0.59950 | 0.250769 / 0.599501 | ✅ exact |
| gate rows | C3 / D3 | C3 / D3 | ✅ exact |
| ROW E, both passes | 97/32 and 64/28 | 97/32 and 64/28 | ✅ exact |
| contingency (KNOWN, `matches12==1`, WRONG) | 28 | 28 | ✅ exact |

**The Sec.5 pre-registered thresholds also re-verify against an independent CP implementation:**
C fires at `k>=37/59` (CP lo 0.5120; k=36 → 0.4948), minority at `k<=22` (CP hi 0.4880; k=23 →
0.5052); D fires at `k>=35/56` (CP lo 0.5065; k=34 → 0.4885), minority at `k<=21` (CP hi 0.4935;
k=22 → 0.5115). The bars I wrote before the run are the bars the arithmetic gives.

---

## 2. The correction: ROW C and ROW D are unresolved for DIFFERENT reasons

This is the substantive content of the ruling, and neither half of it changes a verdict.

**ROW C -- sampling. QA is right.**

| assignment | k/59 | CP lo | CP hi | row it would give |
|---|---:|---:|---:|---|
| `rescued_min` (unknown_as=False) | 33 | 0.4442 | 0.6699 | C3 |
| `rescued_max` (unknown_as=True) | 36 | **0.4948** | 0.7169 | C3 |

Both assignments land C3. Even on the assignment **most** favourable to the rescue claim, k=36 is
**one unit short** of C1's 37 and its CP lower bound misses 0.50 by 0.0052. Had all three ignorance
units been KNOWN-and-ambiguous, C1 still would not have fired. **ROW C's indeterminacy is genuinely
sampling uncertainty at n=59.**

**ROW D -- ignorance. The report's sentence is wrong here, and so was my spec's.**

| assignment | k/56 | CP hi | row it would give |
|---|---:|---:|---|
| `lost_min` (unknown_as=False) | 20 | **0.4753** | **D2 -- fires** |
| `lost_max` (unknown_as=True) | 27 | 0.5995 | D3 |

D2's firing threshold is `k<=21`. `lost_min=20` clears it; `lost_max=27` does not. **The two passes
disagree about the gate row.** QA read `lost_min=20` only against D1's bar (`>=35`) -- true as far as
it goes, and the D3 verdict is right -- but 20 is also below D2's bar, and that is the fact that got
lost. The correct sentence is:

> **ROW D is unresolved because 37 decodes could not be verified, not because 56 units is too few.
> Remove the ignorance and this gate decides; add units and it may not.**

⚠️ **This does not license reading D2.** `lost_max` is the pre-registered bound for D2 and it does
not clear. Naming the straddle is not the same as stepping across it, and the difference is the whole
discipline.

---

## 3. What the arm could ever have shown -- the power I owed the PO at drafting time and did not state

HK-021(m) asked me for resolvable distance-from-threshold. I gave the quantum (1.69pp / 1.79pp) and
the firing counts. **That satisfied the letter of (m) and still left the PO unable to see that
INDETERMINATE was the modal outcome across most of the plausible range.** Computed now, from the
pre-registered bars alone (no outcome data needed -- this could have been in the spec):

| true rate | P(C1 fires), n=59 | P(D1 fires), n=56 | P(ROW C lands C3) |
|---:|---:|---:|---:|
| 0.50 | 0.034 | 0.041 | 0.933 |
| 0.55 | 0.144 | 0.160 | 0.851 |
| 0.60 | 0.388 | 0.407 | 0.611 |
| 0.65 | 0.697 | 0.706 | 0.303 |
| 0.70 | 0.912 | 0.913 | 0.088 |
| 0.75 | 0.988 | 0.987 | -- |

🔴 **My own blind prediction #1 rested on a corpus-wide base rate of 50.9% and an argument that
disagreeing decodes should run "well above" it. The arm I built had 14% power at 0.55 and 39% at
0.60. It only becomes a real instrument above ~0.70.** I predicted a firing whose probability, under
my own stated rationale, was well under half. That is not a wrong prediction -- predictions are
evidence of nothing by design -- **it is a mis-sized instrument, and the mis-sizing was computable
before the run.**

---

## 4. What it would take to resolve either gate (design figures for the PO's coupled decision -- NOT a proposal)

Prospective sizing at the observed rates. ⚠️ **Conditional on the observed point estimate being near
the truth, which this arm did NOT establish** -- read as an order of magnitude, never as a result.

| gate | lever | size needed | currently |
|---|---|---:|---:|
| **ROW C -- C1 at `rescued_min` = 55.9%** | more units | **~220 ROW C units (~3.7x)** | 59 |
| ROW C -- C1 at `rescued_max` = 61.0% | more units | ~69 units | 59 |
| **ROW D -- D2 at `lost_max` = 48.2%** | more units | **~2,200 units -- not reachable** | 56 |
| **ROW D -- D2 at `lost_min` = 35.7%** | **less ignorance** | **already fires at n=56** | 56 |

🔴 **The strategic fact, and the reason this ruling is worth reading: the cheap lever and the
decisive gate are not the same gate.** Improving replay fidelity (or obtaining multiplicity ground
truth) resolves **D**, which on its own decides nothing -- Sec.1 needs **C1** in hand before any
outcome authorises anything. The gate that can decide is **C**, and C is a capture-scale problem:
~3.7x the disagreeing-callsign population. **A larger-n route is real but is not cheap, and a
fidelity route is cheap but cannot conclude.** ⚠️ **Neither is proposed here** (HK-004/HK-015) -- the
two coupled `ARM 2` / remedy-pre-registration decisions stay exactly where the 15:04Z and 17:17Z
rulings left them, and this ruling deliberately does not pre-judge them.

---

## 5. Blind predictions -- re-scored

| # | prediction | QA's score | **ruling** |
|---|---|---|---|
| 1 | C1 fires (moderate-high) | did not fire | **did not fire** -- and Sec.3 shows the arm could barely have shown it |
| 2 | D1 fires (moderate) | did not fire | **did not fire** |
| 3 | lands C1+D1 (repeat of ARM 1C's) | did not land | **did not land** |
| 4 | ignorance changes neither gate's row (moderate-high) | HELD | 🔴 **SPLIT -- held on C, FAILED on D.** The D interval straddles D2's threshold |
| 5 | ROW E > 80% (low, flagged low) | did not clear | **did not clear** -- [69.6%, 75.2%] vs ARM 1B's 62.1% baseline (HK-021(u)) |

**Five predictions, none held cleanly.** Recorded because it was recorded before the run; it is
evidence of nothing and is not read as such.

---

## 6. Two HK-021 siblings proposed to the Captain (his to rule on, as (t) and (u) were)

Both come out of this arm. Both are mine to have missed.

**(v) -- State the arm's POWER against the drafter's own stated rationale, not just its resolution
quantum.** HK-021(m) is satisfied by knowing where the threshold sits; it does not ask whether the
arm can reach it. **If a spec blind-predicts a row will fire, and the arm's probability of firing
under the prior implied by the spec's own rationale is below ~0.5, the arm is mis-sized: say so in
the spec, or resize it.** A gate that can only fire on a landslide, drafted by someone who expects a
squeaker, is a pre-registered INDETERMINATE with extra steps.

**(w) -- For a gate reported as an INTERVAL, "the ignorance is narrower than the indeterminate band"
is NOT a safety argument.** Ignorance is decisive iff the interval **straddles a firing threshold**
-- a fact about **position**, not width, and unknowable before the run. 🛑 **Never pre-register the
width comparison as reassurance.** Pre-register instead that the report must state, per gate,
**whether the interval straddled a threshold and which row each end would have given.** ARM 1D's
Sec.5 made exactly this error and the report inherited it verbatim.

---

## 7. What this ruling does NOT do

- ❌ Does **not** revise ARM 1B (ACCEPTED / A1 / 51.3% stand), the accepted defect, or ARM 1C's VOID.
- ❌ Does **not** move any bar, band or threshold after seeing the data. D3 stands. C3 stands.
- ❌ Does **not** re-open or pre-judge `ARM 2` or the remedy-worth-a-pre-registration question. They
  stay coupled and await the PO/Captain.
- ❌ Does **not** authorise a successor arm. A larger-n or higher-fidelity design is a **NEW
  pre-registration with its own ROW 0**, and HK-021(p) still bites: **no unique-match binary exists,
  so no arm may say "the fixed build would..."**.
- 🔴 **The residual assumption is repeated here beside the numbers, not in a footnote, per Sec.0.3:
  for the 206 KNOWN decodes this arm still assumes the replayed MULTIPLICITY is right because the
  replayed NAME was. Every rescue and loss figure above is a bound on a SIMULATED stratifier, never
  on the real one.**

---

## Cross-references

- `qa/rr-study/2026-08-26-1800-qa-to-architect-f001-d3-arm1d-result.md` -- the result ruled on.
- `qa/rr-study/2026-08-26-1743-architect-to-qa-spec-f001-d3-arm1d-unique-match-trade-bounded.md` -- the
  spec, whose Sec.5 width-vs-band reassurance is the drafting error named in Sec.0 and Sec.6(w).
- `qa/rr-study/2026-08-26-1717-architect-to-qa-ruling-f001-d3-arm1c.md` -- ARM 1C VOID upheld; the
  ruling that specified the bounds repair this arm executed.
- `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` -- parent ruling.
