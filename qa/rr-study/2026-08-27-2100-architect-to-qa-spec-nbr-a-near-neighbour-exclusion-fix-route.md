# Architect → QA — `NBR-FIX` route: scoping the near-neighbour exclusion zone

**Author:** Architect, 2026-08-27 21:00Z (`date -u`, HK-017).
**Follows:** `2026-08-27-2043-architect-to-qa-review-s1s8-sweep-22b749c.md` §6 (commit `dee9d90`),
`2026-08-23-1214-qa-to-architect-f-nbr-a-results.md` (F-NBR-A).
**Status:** SPEC, **not yet authorised**. Requires a Captain/PO decision at §5 before QA runs
anything. Authorises no `src/` change on its own (HK-015: the `dev-tasks/*.md` is QA's to author;
HK-011: any decode change needs a separate Developer session and Captain sign-off).

---

## 0. An honest correction to my own recommendation, up front

In the review that produced this spec I told the PO to *"treat the near-neighbour exclusion zone as
the named performance work item, and scope it as a **fix** rather than another measurement arm."*

**I have to partially walk that back, and the reason matters more than the retraction.** On
checking the code and the closed-arms list rather than reasoning from the measurement, three of the
four obvious fixes are already closed by standing prohibition, and the fourth is blocked on a
precondition that has not cleared:

| Candidate fix | Status | Source |
|---|---|---|
| Subtract the strong signal and re-decode | 🛑 **DEAD** — three builds, three reverts | closed-arms prohibitions |
| Add a decode pass / raise the candidate budget | 🛑 **CLOSED TWICE** — no caps, no passes | closed-arms prohibitions |
| Normalise / AGC / equalise the input | 🛑 **CLOSED** (P2) | closed-arms prohibitions |
| Raise `K_FREQ_OSR` / `K_TIME_OSR` 2→4 | ⚠️ **Not closed, but earns its own pre-registration with FP primary** | closed-arms prohibitions |
| Coherent multi-symbol extraction (D-001 limb 2) | ⚠️ **Built but NOT shippable** — see §3 | `refine/coherent_llr.c`; Phase B wrap-up |

So "just scope the fix" was the wrong instruction to give. **The fix space is narrow, and picking
inside it without knowing the mechanism is exactly how this project burned three builds on
subtract-and-resynthesise.** What I can do — and what this spec is — is define **one bounded arm
whose every outcome maps to a named consequence**, so it cannot become a round.

I am stating this because the PO's standing complaint is that measurement keeps displacing
delivery, and that complaint is correct. This spec is written to end that pattern on this
defect, not to extend it.

---

## 1. The prize, sized

Worth stating first, because it decides whether any of this is worth doing.

From the 2026-08-27 sweep (all figures re-derived from the matched CSVs, review §6.2):

| Scenario | OpenWSFZ now | Misses attributable to the near-neighbour family | If that family were fixed |
|---|---|---|---|
| S7 | 78.60% (169/215) | 26 of 46 (P4, P12, P13, P14, P15) | **≈ 90.7% (+12.1 pp)** |
| S8 | 91.67% (55/60) | **5 of 5** (all station F) | **100% (+8.3 pp)** |

For reference, WSJT-X scores 97.67% (S7) and 96.67% (S8). **Closing this one family would take
S8 past the reference decoder and close roughly two-thirds of the S7 gap.** The remaining S7
residual is dominated by P2's 3-stack co-channel case (15 misses), which is structural and was
Captain-waived on 2026-06-22.

⚠️ **This sizing assumes the family shares one mechanism and one fix. That is exactly what is not
established** — see §4. Treat it as the upper bound on the prize, not a forecast.

---

## 2. Prohibition check — why this is NOT retired spectral locality

**Required before proposing anything that sounds familiar, per the standing rule. Recording it so
nobody has to re-litigate it later.**

Spectral locality is retired permanently — four attempts, zero readings, "do not re-propose under
any name," with LOCAL-vs-DIFFUSE left permanently unanswered. **This is a different question, and
the distinction is not cosmetic:**

| | Retired spectral-locality line | This work |
|---|---|---|
| Population | Live off-air corpora | Controlled synthetic two-signal scenes |
| Question | Is the *crowding penalty* local or diffuse? (a population-level statistic) | Why does a *specific* neighbour geometry produce a deterministic zero? |
| Readings obtained | **Zero, four times** | F-NBR-A: 0/100 → 100/100 on ablation, CIs non-overlapping by the widest possible margin |
| Causality | Never established | **Established** — E is necessary and sufficient (C1) |

The retired line failed because it could never get a reading. This line already has strong,
reproducible, causal readings from a Captain-authorised arm. It is not a re-read of a closed gate
with a better metric (also prohibited) — it is a *different gate on a different population* that
has already fired cleanly.

⚠️ **What DOES carry over:** X1/X2 remain citable, crowding as a first-order term stands, and
**nothing in this spec may be used to reopen the LOCAL-vs-DIFFUSE question.** If any outcome here
starts being read as evidence about diffuse crowding, that reading is out of scope and prohibited.

---

## 3. Why the coherent extractor cannot simply be switched on

This is the route most likely to fix a magnitude-only extraction defect, and I checked whether it
is ready. **It is not, and I want the reason on the record because it is easy to misread the
code as "already done".**

What exists, confirmed by reading the tree:

- `native/ft8_lib_vendor/refine/coherent_llr.c` (574 lines) — `ft8_coherent_llr_at()`, a coherent
  multi-symbol LLR extractor over 1/2/3-symbol windows, with B1's origin correction and B2's
  fusion normalisation.
- `ftx_ldpc_decode_llrs()` in `decode.c` — converts a raw LLR vector into a CRC-verified decode
  through production's own BP → OSD → CRC-14 path.

So the pipeline is built end-to-end. **But `decode.c` states plainly: "No production call site:
reachable only from test code and QA harnesses."** And the Phase B wrap-up (2026-08-22 18:34Z)
records that its own **§4.3 Phase 1 kill gate is VOID: ROW 0g-2 still fires** —
`d_real = -3.000`, CI95 `[-5.000, -2.000]`, `CI_hi < 0`.

Read plainly: the coherent extractor still produces a *worse* median bit-error count than
production, and its **instrument-gain precondition has not cleared**. The gap closed dramatically
(−67 → −3, ~96%), which is real evidence B1/B2 did substantial work — but per the pre-registered
rule, **no ROW may be read and Route B2 must not be called dead.**

⇒ **Wiring the coherent extractor into production today would be shipping an unvalidated
instrument as a fix.** It is not available as a remedy until ROW 0g clears.

---

## 4. The one arm — `NBR-A`, a mechanism discriminator

### 4.1 Why an arm at all, given §0

Because the two surviving fix routes lead to **different places**, and the observable that
separates them is cheap:

- **M1 — tone-set contention in extraction.** FT8 is 8-FSK at 6.25 Hz spacing, so one signal
  occupies a **43.75 Hz tone span**. A neighbour inside that span puts energy into the victim's own
  8 tone bins, and a magnitude-only, single-symbol max-log cannot tell "my tone 3" from
  "neighbour's tone 0". ⇒ the remedy is in how extraction forms bit metrics ⇒ **this defect and
  D-001 limb 2 are the same work item**, and the priority becomes clearing ROW 0g (§3).
- **M2 — pass-1 / tile suppression.** The zone is set by a waterfall/tile implementation constant,
  not by the tone span. ⇒ a candidate-selection-adjacent remedy ⇒ ⚠️ **the candidate-budget family
  is closed twice**, so this outcome requires a NEW pre-registration naming the specific tile
  parameter, with FP primary.

Getting this wrong costs a Developer session on the wrong subsystem. Getting it right costs one
offline sweep on a harness that already exists.

### 4.2 The critical design point F-NBR-A could not have known

F-NBR-A swept ΔF at a **−3 dB level deficit, where `R` is pinned at 0 across the entire zone**
(0/100 at 6.25, 12.00 and 18.75 Hz). **A saturated instrument cannot resolve structure** — every
mechanism predicts a flat zero there, so the sweep cannot discriminate. This is HK-021(q) (exhibit
a unit whose metric MOVES under treatment before the gate runs) and HK-026 (an instrument's output
may not bound its own blind spot).

⇒ **`NBR-A` must first calibrate to a level ratio where `R` is intermediate, then sweep ΔF there.**
This is the single reason this arm can answer what F-NBR-A's could not, and if it is dropped the
arm is worthless.

### 4.3 Instrument

Existing harness `qa/rr-study/f-nbr-a/` (`scene_render.py`, `dll_common.py`, `stats_common.py`,
`part_c.py`), offline, synthetic, Q-prefix callsigns, **no `src/` change, no live capture, no
transmit**. Metric `R(Δ, L)` = fraction of trials in which the victim station is recovered
(matcher's own `FREQ_TOLERANCE_HZ`), interferer fixed, victim at offset Δ and level deficit L.

**Resolvable distance, stated while drafting (HK-021(m)):** at N = 100 per point the 95% binomial
CI half-width is ≈ ±10 pp at `R` = 0.5 and ≈ ±9 pp at `R` = 0.3. **Structure smaller than ~20 pp
in amplitude is NOT readable at N = 100.** If §4.5's ROW 1 periodicity test is wanted at finer
amplitude, N must rise to 400/point and the Captain should be told the cost before arming, not
after.

### 4.4 ROW 0 — preconditions, evaluated in strict order; any fire ⇒ STOP, no partial run

🔴 **HK-025 applies: QA may refuse this spec outright on HK-021(k) grounds without Architect
agreement.** Every row below is written to change the VERDICT, not merely to annotate it; if QA
evaluates any row and finds it lands on the same conclusion either way, that row is diagnostic,
not a precondition, and refusal is the correct response.

| row | check | fires when | consequence if it fires |
|---|---|---|---|
| **0a** | `libft8.dll` SHA256 asserted against the pre-registered value `bc8efcf1…b051d7f`, shim `20260046` | mismatch | Binary identity unestablished. **STOP** — never infer the build from a label. |
| **0b** | Two full runs produce byte-identical results JSON | differ | Harness non-deterministic ⇒ every `R` below is unreadable. **STOP.** |
| **0c** | **Level calibration.** Sweep L ∈ {0, −1, −2, −3} dB at Δ = 12 Hz, N = 100. Choose L\* = the L giving `R` nearest 0.35 | **no** L in the set yields `0.15 ≤ R ≤ 0.60` | The instrument is saturated at every level tested and a ΔF sweep cannot resolve structure (§4.2). **STOP and report** — do NOT run the sweep and read a flat zero as "no structure". Widen L and re-spec. |
| **0d** | Positive control: Δ = 100 Hz at L\*, N = 100 | `R < 0.95` | The victim is not reliably decodable even unobstructed ⇒ scene defect, not a neighbour effect. **STOP.** |
| **0e** | **Δ = 0 reproduction.** Δ = 0 Hz, L = −6 dB, N = 100 | `R < 0.80` | The S8 G/H observation (5/5 at ΔF = 0, −6 dB) does **not** generalise off the S8 scene ⇒ review §6.2's central mechanism lead is **VOID**. **STOP and report** — this is a real possible outcome and must not be silently absorbed into the sweep. |

### 4.5 Reading rows — mutually exclusive, strict order, first match wins

Sweep: Δ ∈ [0, +50] Hz in 1.5625 Hz steps (33 points) at L\*, N = 100/point; plus a mirrored
sign-check at Δ ∈ {−6.25, −12.5, −18.75, −25, −31.25, −37.5, −43.75, −50}, N = 100/point.

| row | fires when | consequence — asserted, not discussed |
|---|---|---|
| **ROW 1** (M1) | first non-zero-lag peak of the autocorrelation of `R(Δ)` over Δ ∈ [3, 44] Hz lies at **6.25 ± 1.6 Hz**, AND `R ≥ 0.90` by `\|Δ\|` = 43.75 ± 6.25 Hz, AND sign-symmetry holds per ROW 3's negation | **The exclusion is tone-set contention in extraction.** ⇒ this defect and **D-001 limb 2 are the same work item**; the near-neighbour zone stops being separate work. ⇒ **Escalate to Captain: the priority question becomes clearing ROW 0g (§3), and the S7/S8 prize in §1 becomes limb 2's business case.** No separate fix is specced. |
| **ROW 2** (M2) | no 6.25 Hz periodicity per ROW 1, AND `R` recovers to ≥ 0.90 at a `\|Δ\|` **outside** 43.75 ± 6.25 Hz | **The exclusion is a pass-1/tile artefact**, not tone-set overlap. ⚠️ The candidate-budget family is CLOSED — so this outcome authorises **nothing** directly; it requires a NEW pre-registration naming the specific tile parameter, **with FP primary**. Report and stop. |
| **ROW 3** (sign-dependent) | `\|R(+Δ) − R(−Δ)\| ≥ 0.30` at ≥ 3 of the 8 mirrored points | A sign-dependent mechanism neither M1 nor M2 predicts. **Escalate. Do not fix, and do not average the two sides** — averaging destroys the only signal the row found. |
| **ROW 4** | none of the above | Partial/ambiguous. **Escalate; do not average rows, do not pick the nearest.** |

---

## 5. The decision I need from the Captain / PO

This spec is deliberately stopped here. Three options, and I recommend the first:

1. **Run `NBR-A` (recommended).** One offline arm, existing harness, no `src/` change, no live
   capture. It is the only thing that tells us whether the performance lead in §1 is limb 2's
   business case or a separate defect. **Cost: hours, not days.**
2. **Skip the arm and go straight at ROW 0g / limb 2.** Defensible — §1's prize is real either way
   and limb 2 is the only live route. But if the mechanism is M2, that effort does not touch this
   defect at all.
3. **Do neither; accept the gap.** Legitimate. S8 is 91.67% and the failures are confined to a
   geometry that is rare off-bench. If the PO's priority is elsewhere, **say so and I will stop
   proposing arms against this defect** rather than re-queuing it a fourth time.

⚠️ **The one thing I recommend against is re-queuing "a targeted look at Station F"** — that has
now been requested three times and delivered once, and the sweep reports keep asking for it because
they are not reading the D-001 thread (review §R3, HK-018).

---

## 6. Architect's prediction — recorded, nothing gates on it

Per project convention. **P(ROW 1) ≈ 55% · P(ROW 2) ≈ 20% · P(ROW 3) ≈ 5% · P(ROW 4) ≈ 10% ·
P(any ROW 0) ≈ 10%**, with ROW 0e the most likely of those.

Reasoning, so it can be scored honestly: F-NBR-A's measured zone closes by 31.25 Hz, whereas M1's
43.75 Hz tone span predicts it should persist further — that is **evidence against my own leading
hypothesis**, and it is why P(ROW 1) is 55% rather than higher. The ΔF = 0 survival is the strongest
thing pointing at M1, and it rests on **a single scenario with N = 5** (S8's G/H pair), which is
why ROW 0e exists at all.

🛑 **My calibration record on this programme is mediocre** (categorical 5/8, directional 1.5/3.5,
and I flipped position on the sync-refinement route after arguing it for four days). **No row above
turns on this prediction, and it should not move the Captain's §5 decision.**

---

## 7. Handoff

- **HK-015** — this is Architect → QA. The `dev-tasks/*.md`, if one is ever needed here, is QA's
  to author, not mine.
- **HK-011** — `NBR-A` itself touches no `src/`, so it needs no Developer session. Any remedy that
  follows ROW 1 or ROW 2 does.
- **HK-014** — this document is committed locally. Nothing pushed, no merge.
- **HK-025** — QA may refuse this spec on HK-021(k) grounds, naming the row and its evaluation,
  with no Architect agreement required. §4.4's rows are the ones to test that against.
- **NFR-021** — `NBR-A` is 100% synthetic, Q-prefix callsigns only; no live corpus is read, so the
  contamination path that affects `*_matched.csv` does not apply.
