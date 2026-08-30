# `NBR-A` AMENDMENT 2 — the calibration is re-specified ONCE, on the axis that matters, and ROW 1's predicate is rewritten

**Architect → QA.** 2026-08-29 23:29Z (`date -u`, HK-017 — local clock reads 2026-08-30 01:29 CEST;
the UTC stamp is the authority and the two are the same instant).

**Authority.** Captain, 2026-08-29 (this session): *"go with your recommendations"*, taken on the
fork I put to him — option (B), a bounded corrected re-arm with a hard one-shot close, in preference
to QA's option 1 (widen `L`) and option 2 (stop).

**Supersedes:** spec `2026-08-27-2100-architect-to-qa-spec-nbr-a-near-neighbour-exclusion-fix-route.md`
(`427a5cf`) §4.4 **ROW 0c** and §4.5 **ROW 1**, and nothing else. Amendment 1
(`2026-08-29-2023-…-AUTHORISED-amendment-1.md`, `6757586`) stands in full.

**Triggered by:** `2026-08-29-2101-qa-to-architect-nbr-a-row0c-void-part-d-result.md` — a clean run
that VOIDed at ROW 0c and obeyed the STOP.

---

## 0. The one-line version

ROW 0c did not fail because the calibration band was in the wrong place. It failed because **I wrote
it on the wrong axis** — it calibrates a single anchor point, when what the sweep needs is a *window*.
Widening `L` repeats the same error three decibels to the right. Amendment 2 replaces it with a
**readable-window probe**, rewrites ROW 1's predicate so it has a method rather than a bar, and
attaches a **hard close**: if the probe fires, `NBR-A` is finished and no third calibration re-spec
is authorised.

---

## 1. The evidence this rests on — all of it already committed

| source | condition | data |
|---|---|---|
| `f-nbr-a/results/nbr-a-results.json` (08-29) | Δ = 12 Hz, sweep `L` | `L` = 0 / −1 / −2 / −3 dB → R = 0.000 / 0.100 / 0.000 / 0.000 |
| `f-nbr-a/results/f-nbr-a-results.json` → `c2` (08-23) | **`L` = −3 dB**, sweep Δ | 6.25 → 0.00 · 12 → 0.00 · 18.75 → 0.00 · **25 → 0.27** · 31.25 → 0.98 · 50 → 1.00 · 100 → 1.00 |
| same → `c3` (08-23) | **Δ = 12 Hz**, sweep level | deficit 0 → 0.00 · **+3 → 1.00** · −3 → 0.00 · −6 → 0.00 |
| S8 G/H, four runs (board, 08-29 19:40Z) | Δ = 0 Hz, `L` = −6 dB | 30/35 — the victim decodes at **zero** separation |

**The reading (a reading, not a measurement — it is two cross-sections of a surface, not the surface):**

1. At `L` = −3 the Δ-response transition is **≈ 12 Hz wide** (0.00 at 18.75 → 0.98 at 31.25).
2. Changing `L` **slides** that transition rather than widening it: at `L` = +3, Δ = 12 Hz already
   reads 1.00, so the whole transition has moved below 12 Hz.
3. ROW 1 hunts a **6.25 Hz** period. A ≈12 Hz unsaturated window holds **≈2 periods**, with §4.3's
   ±10 pp noise floor on top.

⇒ A widened `L` can deliver a ROW 0c PASS at some anchor and leave ROW 1 **still unreadable**. That
is strictly worse than the VOID, because it would look like a result. **Option 1 is rejected on
this basis.**

4. ⚠️ **R is not monotone in Δ.** It is high at Δ = 0 (S8 G/H), zero across ≈6–19 Hz, partial at 25,
   recovered by 31.25. Whatever the mechanism is, "further apart is easier" does not describe it.
   The probe below must therefore **measure** the window rather than assume where it sits.

---

## 2. Two defects in the original spec. Both are mine

**D1 — ROW 0c calibrates one anchor (Δ = 12 Hz) for a reading taken across a range.**
Apply HK-022's drafting question — *what error can this row NOT detect?* — and the answer is: a
transition too narrow to carry the sweep. The row was written to prove the instrument is off its
floor at one point; §4.2's actual requirement is that the metric **moves across the domain ROW 1
integrates over**. Those are different conditions and I conflated them.

**D2 — ROW 1 is a bar without a method. Again.**
`nbr_a.py:205-227` implements the predicate exactly as §4.5 specified it: mean-centre, then take the
**first local maximum at lag ≥ 1**. There is **no detrending, no null, no significance test, and no
predicate shipped as code before the fact** (HK-021(r)).

🔴 **The base rate that condemns it (HK-021(u)):** over the `[3, 44] Hz` domain the sweep has 27
points, so lags 1…25 are scanned; the `6.25 ± 1.6 Hz` acceptance window is lags **3, 4, 5** —
**3 of 25 ⇒ ≈12% under a uniform-lag null.** A row that fires one time in eight on noise must not
carry the consequence "this defect and D-001 limb 2 are the same work item." ⚠️ The uniform-lag null
is itself only an argument — for noisy data the first local max concentrates at short lags, so the
true rate could be higher or lower. **That is precisely why ROW 1′ measures its null instead of
arguing about it.**

This is the same error class as `WIN-A`'s ROW 0e, which I recorded against myself on 2026-08-29.
Twice in two days, both in preflight/reading rows I authored. **HK-021(r) applies to every row I
write, not only to the headline gate.**

---

## 3. What Amendment 2 changes — the supersession map

| item | status |
|---|---|
| ROW 0a (DLL identity) | **UNCHANGED** |
| ROW 0b (determinism) | **NARROWED to ROW 0b′** — §4.1 below, disclosed, with the reason |
| ROW 0c (level calibration) | 🔴 **REPLACED by ROW 0c′** — the readable-window probe, §4.2 |
| **ROW 0f** (predicate power) | 🆕 **NEW**, §4.3 — evaluated after 0c′, before 0d |
| ROW 0d (positive control), ROW 0e (Δ = 0 reproduction) | **UNCHANGED**, character for character |
| ROW 1 | 🔴 **REPLACED by ROW 1′** — §5 |
| ROW 2 / ROW 3 / ROW 4 | **UNCHANGED as predicates.** ROW 2's *reporting requirement* is extended, §6 |
| Part D | **DONE, reported, not re-run.** Its reading stands as filed |

🛑 **This amendment TIGHTENS. It must never be read as loosening a bar.**
ROW 0c′ is **not** a superset of ROW 0c and I am not claiming it is — it is a different and strictly
more demanding condition: ROW 0c could pass on one point while the sweep stayed unreadable; ROW 0c′
cannot. Any reading of this document that lets the arm proceed on evidence ROW 0c would have
rejected is a **misreading, and the original spec wins.**

---

## 4. The corrected preconditions — strict order, any fire ⇒ STOP, no partial run

🔴 **HK-025 stands undiminished.** QA may refuse any row here on HK-021(k) grounds without my
agreement, Captain authorisation notwithstanding. Classify (validity vs precision), evaluate both
branches, and if the same row follows either way it is diagnostic and refusal is correct.

**Pre-registered build (HK-021(p)):** `libft8.dll` SHA256 `bc8efcf1…b051d7f`, shim `20260046`, **both
copies** — ROW 0a as written. 🔴 **`nbr_a_probe.py`, the ROW 1′ predicate, and the §4.3 power check
must be COMMITTED BEFORE the probe runs**, and their commit SHA recorded in the result. A predicate
written after its data exists is not pre-registered.

### 4.1 ROW 0b′ — determinism, narrowed (disclosed)

Re-run **one probe level (`L` = 0 dB, all 11 Δ points)** twice, independently; the two result JSONs
must be **byte-identical, mechanically diffed** — never asserted.

**Fires when** they differ ⇒ every `R` below is unreadable ⇒ **STOP.**

⚠️ **Disclosed narrowing, with the reason:** ROW 0b as written doubles the whole pipeline. Determinism
is a property of the harness and its seeding (`compute_seed`/`trial_seed`), not of a particular level,
and QA already demonstrated byte-identity across two full pipelines on this exact build hours ago. The
narrowing buys ~40 minutes. It is **weaker** than the original and I am saying so rather than
presenting it as equivalent; if QA judges the full doubling is warranted, take it — that is QA's call
and I will not overrule it.

### 4.2 ROW 0c′ — the readable-window probe (replaces ROW 0c)

**Grid.** Δ ∈ {0, 4.6875, 9.375, 14.0625, 18.75, 23.4375, 28.125, 32.8125, 37.5, 42.1875, 46.875} Hz
— **every 3rd point of the sweep's own 1.5625 Hz lattice**, 11 points, so the measurement transfers to
the sweep without re-interpolation.
**Levels.** `L` ∈ {+3, 0, −3, −6, −9} dB, `L` = victim − interferer as QA fixed it (E held at −5 dB).
**N = 100 per point.** 5 × 11 × 100 = **5 500 trials.**

⚠️ **The probe is a WIDTH measurement and must not be read as a periodicity measurement.** Its 4.6875 Hz
step is 3/4 of a tone spacing, so it re-samples the same ripple phase every 18.75 Hz. It cannot see a
6.25 Hz feature and no statement about periodicity may be drawn from it.

**Definitions, mechanical:**
- A probe point is **readable** iff `0.15 ≤ R ≤ 0.85`.
- The **readable run** at a level is the longest *contiguous* set of readable probe points at that
  level; its **span** = (max Δ − min Δ) in Hz. A run of `k` points has span `(k − 1) × 4.6875` Hz.

🔴 **ROW 0c′ FIRES when: no level in the probe set has a readable run of ≥ 5 consecutive points**
(span ≥ **18.75 Hz** = **3 periods** of 6.25 Hz).

| branch | consequence — asserted, not discussed |
|---|---|
| **fires** | The near-neighbour Δ-response is a **cliff**, not a gradient: at every level tested, the unsaturated window is too narrow to carry a 6.25 Hz reading at N = 100. 🛑 **`NBR-A` is CLOSED — see §8. This is a RESULT, to be reported as one, not a failed setup.** |
| **passes** | `L*` = the level with the **longest** readable run; ties → the run whose **mean R is nearest 0.50**; further ties → the **more negative** `L`. The window `W` = that run's Δ interval, **fixed here and NEVER adjusted after the sweep data exists.** Proceed to ROW 0f. Cost on this branch: the full sweep, ≈39 min (§7). |

**Why 3 periods and not 2:** an autocorrelation at one-period lag computed over a window holding two
periods is dominated by its endpoints. Three is the minimum at which the statistic has a null worth
measuring. It is a hard threshold, chosen now, and it is not to be moved after the probe reports —
moving it would be exactly the error Amendment 1 forbade.

### 4.3 ROW 0f — predicate power (NEW; evaluated after 0c′, before 0d)

Before any real sweep, run the ROW 1′ predicate against **synthetic** `R(Δ)` curves over `W`: the
measured probe trend plus an injected sinusoidal ripple of period 6.25 Hz at amplitudes
**A ∈ {0, 10, 20, 30, 40} pp**, binomial noise at N = 100, **100 seeded draws per amplitude**.
Report, for each `A`, the fraction of draws with `p ≤ 0.01`. `A_min` = the smallest `A` reaching
**≥ 90%**.

| branch | consequence |
|---|---|
| **`A_min` > 30 pp, or undefined** | The predicate cannot see an effect of a size the mechanism plausibly produces ⇒ a null would be uninterpretable. **STOP and report.** 🛑 Same close as §8 — no re-spec. |
| **`A_min` ≤ 30 pp** | Proceed. **`A_min` is published in the result and quoted beside every ROW 2 statement** (§6). |

This is the HK-021(q) unit — exhibit a metric that MOVES under a known treatment before letting it
judge anything — and it costs seconds of numpy, no decoder.
✅ It also discharges D2's other half: at `A = 0` the observed firing fraction **is** the measured
false-positive rate of the row, replacing my ≈12% argument with a number.

### 4.4 ROW 0d, ROW 0e — unchanged

Character for character as `427a5cf` §4.4. ROW 0e keeps its `R < 0.80` bar at Δ = 0, `L` = −6 dB;
I refused to move it on 2026-08-29 and I refuse again here. **30/35 across four runs is four runs of
ONE scene, and ROW 0e tests scene change.**

---

## 5. ROW 1′ — the rewritten predicate (replaces ROW 1)

Computed **only over `W`**, the window fixed by ROW 0c′ before the sweep ran.

1. **Detrend.** Least-squares **straight line** in Δ over `W`; residuals `r(Δ)`. A line, not a spline
   and not a filter — no tuning parameter, nothing to choose after seeing the data.
2. **Statistic.** `P` = normalised autocorrelation of `r` at **lag exactly 4 lattice steps
   (= 6.25 Hz)**. A **named lag**, not "the first peak" — this removes the which-peak judgement that
   carried the 12% base rate.
3. **Null, measured not argued.** 10 000 random permutations of `r` within `W`; seed **20260830**,
   **sorted at construction** (the hash-randomised-iteration trap on the board — a fixed seed does
   not save you if the index set iterates per-process-randomly).
   `p = (1 + #{P_perm ≥ P_obs}) / 10 001`, one-sided **upward**.
4. **Readout quantum (HK-021(o)):** `p` resolves to 1/10 001 ≈ 1.0e−4. Quote `p`, never a bootstrap SE.

🔴 **ROW 1′ FIRES when ALL THREE hold:**
- **(i)** `P_obs > 0` **AND** `p ≤ 0.01` — signed upward, never `|P|` (HK-021(l)); M1 predicts
  *coincident dips* at tone-spacing multiples, i.e. positive correlation at that lag. A significant
  **negative** correlation is not M1 and falls to ROW 4;
- **(ii)** first **sustained** `R ≥ 0.90` lies within `43.75 ± 6.25 Hz` (`_first_sustained_recovery_hz`,
  unchanged);
- **(iii)** ROW 3 does not fire (sign-symmetry holds).

**Consequence if it fires — unchanged from `427a5cf`:** the exclusion is tone-set contention in
extraction ⇒ this defect and **D-001 limb 2 are the same work item** ⇒ escalate to the Captain; the
priority question becomes clearing ROW 0g. **No separate fix is specced, and no `src/` change is
authorised by this row.**

---

## 6. ROW 2, ROW 3, ROW 4 — predicates unchanged; ROW 2 gains a reporting duty

ROW 2's predicate is untouched. But it now rests on a *measured-power* null instead of an unmeasured
one, and that cuts both ways:

🔴 **Every ROW 2 statement must be published as: "no 6.25 Hz periodicity detectable at amplitude
≥ `A_min` pp (N = 100, `p ≤ 0.01`)" — never as "no periodicity", and never as "M1 is excluded."**
Absence of evidence at a measured sensitivity is a bounded negative, and the bound must travel with
the claim wherever it is quoted.

⚠️ **ROW 2 still authorises NOTHING.** The candidate-budget family is closed twice; a tile-parameter
remedy needs a fresh pre-registration with **FP primary**. Report and stop.

📌 **A prediction worth scoring, recorded before the run (gates nothing).** The committed C2 curve
reaches sustained `R ≥ 0.90` at **31.25 Hz** — **12.5 Hz inside** the 43.75 Hz tone span that M1's
conjunct (ii) requires. On its face that leans **ROW 2 / M2**, i.e. *against* the tone-contention
reading now underwriting Route B2's premise. ⚠️ **It is confounded by level** (C2 sits at `L` = −3;
a weaker victim needs more separation) and the grid is coarse — which is exactly what a sweep at `L*`
settles. 🛑 **Do not cite "31.25 Hz" as evidence for M2 in any document. It is a reason to run the
arm, not a result of it.**

---

## 7. Cost, derived from this harness's own measured rate

Rate: the 08-29 official run did ROW 0a + 400 trials in **226 s** (`run_started_utc` 20:57:49 →
`run_finished_utc` 21:01:35) ⇒ **≈0.565 s/trial**. Derived, not guessed.

| stage | trials | ≈time |
|---|---|---|
| ROW 0b′ (one level, twice) | 1 100 | 10 min |
| ROW 0c′ probe | 5 500 | 52 min |
| ROW 0f power check | 0 (numpy) | < 1 min |
| **subtotal — the decision point** | **6 600** | **≈1 h 02 m** |
| ROW 0d + 0e | 200 | 2 min |
| Sweep (33 + 8 points) | 4 100 | 39 min |
| **total, only if 0c′ and 0f both pass** | **10 900** | **≈1 h 45 m** |

**Told before arming, per the spec's own §4.3 rule, not after.** If the probe fires, the spend stops
at ≈1 hour.

---

## 8. 🛑 THE HARD CLOSE — the condition of this amendment

**If ROW 0c′ fires, or ROW 0f fires, `NBR-A` is CLOSED.**

- The finding is reportable and real: **the near-neighbour Δ-response is a cliff whose unsaturated
  window is too narrow to carry a 6.25 Hz periodicity reading at N ≤ 100.** That is a property of the
  decoder and the instrument together, and it is worth recording as one.
- 🛑 **No third calibration re-spec is authorised. Not by me, not by QA, and this document may not be
  cited as precedent for one.** "Widen it again" is a calibration chase, and one re-spec is the whole
  licence the Captain granted.
- Any future attempt at the M1/M2 discrimination earns a **fresh pre-registration built on a
  different instrument** — a finer `R` (N = 400/point, which §4.3 already prices), or a metric with
  more dynamic range than a binary decode indicator, or a route that does not depend on resolving
  6.25 Hz structure at all. It must **name what changed** other than our appetite for the answer.
- 🔴 Record in `closed-arms-prohibitions.md` on close: *`NBR-A` calibration — re-specced once
  (Amendment 2), closed on the readable-window probe. Do not re-spec a third time.*

---

## 9. Architect predictions — recorded now, scored later, gating nothing

- **ROW 0c′ fires: ≈70%.** From §1's slide-not-widen reading.
- If 0c′ passes, `L*` is **−3 or −6 dB**: ≈65%.
- **ROW 0f passes (`A_min` ≤ 30 pp): ≈55%.** Genuinely uncertain; 13 points is not many.
- If the sweep runs, **ROW 2 rather than ROW 1**: ≈60%, on the 31.25 Hz recovery point.

⚠️ **Calibration disclosure: my categorical ROW calls run 6/11.** Read these as weakly informative.
🛑 **No pre-registration may cite or gate on any of them** — they exist to be scored against, and to
stop me quietly rewriting my expectations after the fact.

---

## 10. What this amendment does NOT authorise

🛑 No `src/` change. No `native/` change. No rebuilt DLL. No Developer session. No live capture, no
transmit, no radio time. **No Route B2 work** — B2 remains unauthorised and P2 remains its
*acceptance test*, never a target. It re-opens no closed family: subtract-resynthesise, input
scaling/AGC, the candidate-budget family, OSR, spectral locality and the analysis-window family are
all closed and stay closed. Part D is **done** and is not re-run. The S7 headline stays at the
unadjusted **19.07 pp**; **14.50 pp is withdrawn and is never quoted.**

---

## 11. Deliverable

One QA → Architect report (HK-001 sections, HK-017 timestamps) carrying: the ROW 0a build assertion;
the pre-run commit SHA of the probe and predicate code; ROW 0b′'s mechanical diff; the full probe
table (all 55 points); `L*` and `W` with the tie-break actually applied; `A_min` and the `A = 0`
false-positive fraction; then either the close under §8 or the sweep with ROW 1′'s `P_obs` and `p`.
Plus explicit citation limits, and predictions scored against §9.

🔴 **If any row fires, STOP there and report. Do not run the next row to "see what it says."**
