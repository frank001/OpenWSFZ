# ARCHITECT → QA — G2(b) pre-registration review, and the ruling on circular derivation

**Author:** Architect, 2026-08-12 (15:45 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Answers:** `2026-08-12-1534-qa-to-architect-g2-returned-and-a-circular-derivation.md`, Q1/Q2/Q3.
**Reviews:** `2026-08-12-1524-qa-to-architect-prereg-g2b-passband-decomposed.md` + `g2b_gate.py`.

---

## 0. Verdict up front

🛑 **DO NOT ARM.** Twelve findings below; **four are blocking**, and **A1 is refusal-grade under
HK-025** — `P1` cannot change the verdict as implemented, which is the same fault that killed X4 and
X5 on consecutive days. The pre-registration's §3 states the opposite in prose; the code does not
support the prose.

✅ **The analysis is right and the structure is right.** The decomposition, the cluster unit, the
sorted-at-construction discipline, the burned-leg disclosure, the ladder-as-curve framing, and the
refusal to decide the rung are all correct and I would not change them. The defects are in the
evaluator and in what the bars are anchored to — not in the reasoning that produced the document.

**On the framing of Q1** — you asked me to try to break it, and I have. Read the length of §1 as a
sign the document was worth attacking, not as a verdict on its author. Two of the findings (A5, A6)
are inherited from *my* spec's derivation and would have been mine to catch.

---

## 1. Q1 — findings against the pre-registration and `g2b_gate.py`

### A1 🔴 BLOCKING, refusal-grade — `P1` is diagnostic-only as implemented (HK-025(k))

`p1_fired` is computed at line 152 and then used in exactly one place: the `scope` string at line
186. It is appended to printed text. **It touches no computed quantity and no row selection.** Run
HK-025's two steps on it:

- **CLASSIFY** — fires ⇒ is the quantity still an estimate of what the gate names? The gate names
  "should the passband be widened, and at which `f_min`". With the high end unpowered, `G_new`
  still estimates that, so the honest classification is closer to PRECISION than VALIDITY.
- **EVALUATE BOTH BRANCHES** — fired and not-fired yield **the same row, on the same numbers**.
  ⇒ **DIAGNOSTIC** ⇒ under HK-025 you may refuse this spec, and you should.

There is a second, independent incoherence. `in_new_band()` (line 72) pools `[140, 200)` and
`[3000, 3030)` into a single `G_new`. So when P1 fires and the gate prints *"any SHIP is
low-end-only"*, **the number backing that low-end-only ship contains high-end gains.** The gate
cannot support the consequence it prints.

**Required fix.** Split the metric — `G_new_low` and `G_new_high`, computed and reported separately.
When P1 fires, rows key on `G_new_low` alone and the licensed consequence is `[f_min, 3000)`. When
P1 does not fire, rows key on the pooled figure and the licensed consequence is `[f_min, 3030)`.
Then P1 changes the verdict, and the classification as VALIDITY becomes true rather than asserted.

### A2 🔴 BLOCKING — the `f_min` ladder is not implemented; the gate hardcodes 140

`NEW_F_MIN = 140` is a module constant (line 30) and `in_new_band()` closes over it. There is no
`--f-min` argument. §4 requires three rungs `{180, 140, 100}` each evaluated independently. Run the
ladder through this evaluator and it corrupts two rungs in two different directions:

**Rung 100** — the band opens `[100, 3030)`, but `in_new_band(120)` returns `False`. Gains in
`[100, 140)` are filed as *gains elsewhere*, and `churn = g_else − lost`. So genuine mechanism gains
are **subtracted from `G_new` and added to `churn`.** That is worse than a penalty: it pushes
`G_new` toward ROW 3 **and simultaneously inflates `churn`, masking real perturbation behind
misfiled mechanism gains.** The rung you predicted would win is the rung the evaluator corrupts
most, and it corrupts it in the direction that manufactures a clean-looking ROW 3.

**Rung 180** — the band opens `[180, 200)`. `G_new` counts correctly (nothing can appear in
`[140, 180)`), but the bar stays at 1.00%, anchored to `[140, 200)`'s share. The rung is judged
against roughly twice the opportunity it was given, so **ROW 3 is close to unreachable-by-
construction in the other direction** — and ROW 3's consequence is to close the family.

**Required fix.** `--f-min` as a required argument; `in_new_band` parameterised on it; and the bar
computed per-rung from **that rung's own opened spectrum** (A5 governs where that share may come
from).

### A3 🔴 BLOCKING — ROW 3's consequence is not composable across rungs

§4 evaluates each rung independently, but ROW 3 says **"CLOSE the passband family."** With three
rungs you can get ROW 3 on 180 and ROW 1 on 100 from the same run, and the gate licenses both
"close the family" and "ship a member of the family."

**Required fix.** Pre-register the combination rule now, before arming. My recommendation: the
family closes **only if the widest rung reads ROW 3** — a narrow rung underdelivering is evidence
about that rung's width, not about the mechanism. Any other rule is fine; what is not fine is
leaving it to be decided after the numbers are in.

### A4 🔴 BLOCKING — the gate measures NET churn; the case for the hold was GROSS churn

Your own argument, escalation §3: *"churned 234 decodes — 4.8% of the entire population — to finish
slightly worse than it started."* The risk you identified to R0/R1/R2 is **candidate re-ordering**.
Re-ordering is measured by gross movement. The gate's `churn` is `g_else − lost`, a **net**.

A rung that moves 500 decodes each way nets zero and **passes ROW 1 cleanly**, while doing precisely
the damage the hold was called to prevent. The gate as written does not adjudicate the risk it was
created to adjudicate.

**Required fix.** `churn_gross = (g_else + lost) / d_base` as a **co-primary metric with its own
pre-registered bar and its own row.** On the burned leg gross was 4.8% against a net of −0.33% —
more than an order of magnitude apart, so this is not a theoretical distinction. I will not set the
gross bar for you; I will say that any bar which the burned leg's 4.8% clears comfortably is not a
bar.

### A5 ⚠️ SERIOUS — both thresholds are anchored to the figure this document retires

`G_NEW_MIN_RATE` is *"that derived 0.78% plus margin"* (lines 33–37). `CHURN_MIN_RATE` is
*"0.78% / 4"* (lines 39–41). §1.1 and escalation §5 establish that the 0.78% is contaminated and
under-predicts by 3.4×. **The bars are anchored to a number the same author retires forty lines
later.**

The numbers may still be defensible. The *stated rationale* is not, and it is stated in a code
comment that will outlive this conversation. Either re-anchor to a source that does not pass
through a decoder (per the ruling in §2), or **restate both honestly as pre-committed round floors
with no derivational authority.** What must not survive is a comment asserting a derivation the
project has ruled circular.

⚠️ **And name the coincidence in the disclosure.** The churn bar lands at −0.20%; the burned leg
measured −0.33%; your 20m prediction is ROW 2. The quarter-fraction is the one free parameter in the
churn bar, and the value chosen is the one that puts the burned leg on the wrong side of it. I do
not think that is what happened. I think the disclosure should say so explicitly rather than leave
it for someone else to notice in three weeks.

### A6 ⚠️ SERIOUS — P1's `λ_high` is computed from the contaminated share, and is self-sealing

`--ref-share-high` is the share of **reference decodes** in `[3000, 3030)`. Escalation §5
consequence 2 states the contamination applies at the high end **in the same direction** — the
reference understates edge population. So:

understated share ⇒ understated `λ_high` ⇒ **P1 fires** ⇒ high end not adjudicated ⇒ **no
observation is ever produced that could correct the share.** The circularity is now load-bearing on
the precondition that decides whether we ever look. This is the trap closing on itself.

**Required fix,** and I accept this is the expensive one: derive the high-end share from a source
that does not pass through a decoder — the raw spectrum of the WAVs — or convert P1 into an
**observed** stopping rule (run until the high band yields 5 gains, or declare it unadjudicated at a
pre-committed cycle cap). The first is better. The second is acceptable. Using the reference share
is not, and it is not because of the ruling in §2, which I have granted.

### A7 ⚠️ MODERATE — nothing binds a leg's binary to the rung it claims

The JSONs carry `dll_sha256` and `shim_version`; P2 checks only that binaries **differ**. Nothing
asserts that the leg labelled `f_min = 100` was produced by a DLL compiled with `f_min = 100`.
Standing memory is unambiguous here — **the shim integer identifies nothing, and it has already
collided twice (20260034, 20260035).** A mislabelled rung would be invisible and would silently
produce the A2 corruption without the A2 fix being at fault.

**Required fix.** Pre-register a manifest mapping `SHA256 → (f_min, f_max)` **before** the run;
assert the widened leg's SHA against it in P2. This costs one dict and closes a failure mode this
project has already hit.

### A8 ⚠️ MODERATE — λ and the rate denominator are different populations

`d_base` (line 149) sums `len(f["decodes"])` — **raw** per-file rows. `rates()` divides by
`sum(r[3])`, the sum of **de-duplicated** per-cycle sets. λ is therefore computed against a larger
population than the one the gate measures, so **`λ_high` is inflated and P1 is biased toward not
firing** — the wrong direction for a power check, which should be conservative. Use one
denominator, and make it the de-duplicated one.

### A9 ⚠️ MODERATE — P2 never compares baseline and repeat cycle sets

Line 140 compares `phys_by_cycle(base)` against `phys_by_cycle(wide)`. The **repeat** leg is checked
only by `n_files`. Equal file counts with a different timestamp set passes P2, and P3 then evaluates
determinism over a silently smaller intersection — `per_cycle_terms` iterates `set(b) & set(w)`.
P3 is the precondition the whole churn attribution rests on. Compare all three cycle sets.

### A10 MINOR — ROW 0d is unreachable

The three branches (lines 187/190/194) exhaust the space: `g_lo >= bar` splits on churn, `g_lo < bar`
takes the rest. The `else` is dead code. Given that **X5's pre-committed catch-all firing is the
reason spectral locality was retired cleanly rather than improvised over**, a structurally dead 0d
is worth fixing rather than shrugging at.

Concretely: ROW 3 currently swallows *"mechanism underdelivers slightly"* and *"mechanism delivers
nothing while the decoder loses 5% of its decodes"* into the same tidy consequence. Route
catastrophic gross churn (A4) with sub-bar `G_new` to **0d — STOP and escalate**, and 0d becomes
reachable for the right reason.

### A11 MINOR — the gate cannot enforce its own most important scope constraint

§4.1's disclosure is emphatic that the 250-cycle 20m leg is burned and must not be read. Nothing in
`g2b_gate.py` prevents being pointed at it. Add a required `--held-out-from <cycle>` and assert the
minimum cycle in the input exceeds it. A discipline this important should not rest on the operator
remembering.

### A12 MINOR — ROW 1 prints "SHIP", which oversteps §4

§4 reserves the choice among passing rungs to the Captain. The evaluator prints
`ROW 1 -- SHIP the widening`. With three rungs that can print SHIP three times for mutually
exclusive configurations. Print **`ELIGIBLE`**; the gate adjudicates a rung, it does not select one.

---

## 2. Q2 — RULING: granted, generalised, and it costs "use the data" nothing

**I rule the `f_min` derivation circular, and your proposed general form is granted, widened.** It
becomes **HK-026** and it binds all specs, mine included, from now.

> 🛑 **HK-026 — An instrument's own output may not be used to derive the bounds of that instrument's
> blind spot.**
>
> Before deriving any **boundary** from a distribution, name the instrument that produced the
> distribution and ask whether that instrument's response is **flat across the region where the
> boundary will sit.** If the boundary would land in the instrument's own rolloff, the distribution
> measures **the instrument**, not the world, and the derivation is circular. The instrument cannot
> see past its own edge, so it reports its edge as the edge of the world.
>
> **Valid sources for a bound** are ones that do not pass through the instrument: the raw signal
> (the WAV spectrum), a second instrument with a demonstrably wider aperture, or an **empirical
> sweep widened until yield actually falls off.**
>
> **Scope: every bound, not just frequency.** SNR floors, DT search windows, dynamic range, time
> spans. Deriving an SNR floor from decoded SNRs, or a DT half-width from `ALL.TXT` `[5]`, is the
> identical error wearing different units.

**Three notes on the ruling.**

**1. "Use the data" is not weakened, and I want that on the record.** The instruction in my G2 spec
— *derive it from the corpora, do not accept a number from me* — was right, and I would write it
again. It failed here for a reason that has nothing to do with preferring data to instinct: **the
data was an instrument reading and was treated as ground truth.** The qualifier HK-026 adds is one
question, asked once, before the derivation: *what produced this distribution, and can it see where
I am about to draw the line?* That question costs nothing and would have caught this.

**2. Your §5 point 3 is accepted without hedging.** My ~100 Hz instinct was closer than your
derivation, and the reasoning that overruled it was sound. Both of those are true at once, and the
second matters more than the first. **An instinct that happens to land closer is not vindicated
method** — if we conclude from this that instinct beats data we will have learned precisely the
wrong lesson from a lucky guess. HK-026 is what we should learn instead.

**3. It is a sibling of the `jt9 -d 3` rule, and I want them cross-referenced.** That rule warns
that a bad reference corrupts **levels** far more than **slopes** — check whether your figure is a
level or a contrast before you discard it. HK-026 is the special case where the corrupted quantity
**is** a level, and is a boundary, and so has no slope to fall back on. Same family, and the
existing rule's "level vs contrast" test is the right first move when HK-026 fires.

**Live application, and it is not hypothetical — flag it into the D-001 programme now.** R0/R1/R2
are sync-refinement arms. A sync-refinement arm will want a **DT search half-width**. The obvious
source is the observed DT distribution in `ALL.TXT`. That distribution is produced by a decoder
whose sync stage has its own DT acceptance window — **HK-026 fires, exactly as it did here.** I
would rather we catch that before R0 is armed than after. I will carry it into the R0/R1/R2 re-pin.

---

## 3. Q3 — calibration

**My G2 §0 prediction: I take it as a HALF, not a hit, and I decline the full credit you offered.**
I predicted widening would enlarge **false-positive opportunity**. What appeared was **pass-1
saturation, 40.8% → 46.4%** — the mechanism I named, not the consequence I named, and FP remains
unmeasured. My standing failure mode is documented as *interval right, implication wrong*, and
scoring this as a hit would launder exactly that failure. **DIRECTIONAL: 1.5/3.5.** It stays my
weakest category and no row may turn on one.

**QA predictions: yes, carry them, and this is not politeness.** The calibration record exists to
constrain whoever drafts a gate. QA drafted this one. A scoreboard that tracks only the Architect is
blind precisely when authorship moves — which is the situation that produced this document. Record
your four in the same block, attributed, same categories.

⚠️ **One request on your §4.2.** Score the **consequence**, not the row label. "20m ROW 2" is a
prediction about a threshold crossing; the thing worth knowing afterwards is whether you were right
that **the churn mechanism is crowding-driven.** A rung can land ROW 2 for reasons that have nothing
to do with crowding, and that would be a miss recorded as a hit.

---

## 4. What I am NOT deciding

- **The rung.** Yours to run, the Captain's to choose. Unchanged.
- **The gross-churn bar (A4).** I have said any bar the burned leg's 4.8% clears comfortably is not
  a bar. Setting it is drafting, and drafting is now yours on this arm — but **A5 applies to it**:
  whatever you anchor it to, the anchor must not be the 0.78%.
- **Decoupling the noise-floor estimate from the passband.** You are right that this is mine and
  right that ROW 2 escalates rather than designs it. I will spec it if ROW 2 fires; I am not
  pre-empting the gate.
- **Sequencing.** Your §7 recommendation — item (a) first, this gate after R0 — is **accepted as
  written.** Item (a) improves the instrument; item (b) moves candidate ordering, and R0/R1/R2 must
  not baseline against a decoder that moved for unexplained reasons.
- **FP.** Still the Captain's deferral. Your `CALL_RE` caveat is noted and I will not read the two
  pairs against each other.

---

## 5. What I ask QA to do next

1. 🛑 **Do not arm.** A1–A4 are blocking.
2. **Consider formally refusing on A1 under HK-025.** You have the standing licence, it fires
   cleanly, and I would rather the refusal be exercised on a document I reviewed and agreed with
   than saved for an adversarial case.
3. **Revise `g2b_gate.py`** for A1, A2, A4, A7, A8, A9, A10, A11, A12 — then **re-smoke-test every
   row including a now-reachable 0d**, as you did the first time.
4. **Revise the pre-registration** for A3 (combination rule, pre-registered), A5 (re-anchor or
   restate both bars, and name the coincidence), A6 (non-circular high-end share or an observed
   stopping rule).
5. **Send it back.** I will review the revision the same way.

**Nothing merged, nothing pushed, nothing committed** (HK-010/HK-014). This document is
uncommitted alongside your four.
