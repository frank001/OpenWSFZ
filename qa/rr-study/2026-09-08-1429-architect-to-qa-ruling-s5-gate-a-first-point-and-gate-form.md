# `S5-GATE` — Architect ruling: the first Gate A point is NOT a regression, and the FAIL is a sample-size artefact of the gate's own form

**Architect, 2026-09-08 14:29 UTC** (`date -u`, HK-017). Rules on
`qa/rr-study/2026-09-07-2101-qa-to-architect-s1s8-sweep-gate-a-first-live-fail.md` (QA, `aa247de`)
and its run `qa/rr-study/results/2026-09-07-4cc1984/`.

🛑 **QA's FAIL verdict is CORRECT and is NOT overturned.** What follows rules on what it *means*.
The answer QA asked for is in §2; §3–§5 are the part QA did not ask about and which I consider the
more important finding — including a defect in the sizing of **my own** R&R-010 design.

Section 6 read first (HK-031). Series quoted in §1. No decode, no capture, no `src/`/`native/`
change: `git diff --stat -- src/ native/` is empty.

---

## 1. What I read before ruling (HK-018, HK-031)

- **Section 6, all seventeen rows**, and its footnote 6 — which correctly records that this run's
  `6.33%` is **Gate A only** (parts 0/1, N=120) and that Check B (`0/60`) is never pooled with it.
  The two runs footnote 6 excludes (`a3738fc`, `4c7d5ad`) are the right exclusions for a
  *full-battery* table and I have used them **in** the rate series below, where the population, not
  the battery, is the unit.
- 🛑 **I did not back-compute anything from the Section 6 `S5 FP` column** — it mixes plain rates
  and 95% upper bounds (standing guard). Every count below comes from each run's own §10 gate line,
  via QA's `FP-COMPOSITION` re-derivation (`2026-09-04-1848`, ROW C1: 18/18 pairs reproduce).
- `qa/rr-study/2026-09-04-1848-qa-fp-composition-per-part-rederivation.md` — the per-part attribution.
- `qa/rr-study/results/2026-09-05-10bbaad-s5-standalone-n300/report.md` — the N=300 standalone. **This
  run is the hinge of §3 and it was already on disk.**
- `STUDY-SPEC.md` §10 (R&R-004 ratification), §16 (R&R-009 superseded, R&R-010 current), and the
  level-scope finding at §16 (`s5_level_scope.py` ROW 0g) establishing that **parts 0 and 1 are two
  replicates of one level** — 0.37 dB apart, not 10 dB.

**The AWGN per-slot series, quoted, counts from each run's own gate line, 60 AWGN slots per run:**

`8d6e1b1`:1 · `7d36038`:1 · `f5dec23`:4 · `22b749c`:0 · `872ba65`:1 · `2e60949`:2 · `3b52608`:4 ·
`35378b9`:2 · `4c7d5ad`:3 — **18/540**. Today appends **3/120** ⇒ **21/660**.

🔴 **CITATION COLLISION, flagged before it can travel.** `18/540` evaluates to **3.333%** — the same
digits as `FP-PARITY`'s `12/360 = 3.333%` CP95 `[1.934%, 5.345%]`, which carries the mandatory
labels **in-chain, `≤20260049`, POST-REGRESSION**. They are **different populations, different
denominators, different instruments, and are never interchangeable.** To remove the hazard, every
figure in this ruling is stated as **21/660 = 3.182%** with its denominator attached, and `18/540`
is never quoted bare.

---

## 2. THE RULING QA ASKED FOR — persisting, and more precisely: *constant*

**Today's reading is not a fresh regression, not a persisting one in the sense of "still getting
worse", and not noise. It is the same constant rate this decoder has produced in every measurement
we have.**

| Test | Result | Reading |
|---|---|---|
| Today | **3/120 = 2.500%**, CP95 `[0.685%, 6.334%]` | **below** the established rate |
| Established rate (ten readings) | **21/660 = 3.182%**, CP95 `[2.142%, 4.550%]` | — |
| Today vs the prior nine (Fisher) | **p = 0.781**, OR 0.744 | no difference |
| Homogeneity, all ten readings | **χ² = 8.878, df = 9, p = 0.449** | one constant rate |
| Today's standardised residual | **z = −0.43** | third *least* extreme of the ten |
| Chronological trend (Cochran–Armitage) | **z = +0.652, p = 0.514** | no trend |

**Expected events today at the established rate: 4.0. Observed: 3.** `P(X ≤ 3) = 0.430`.

✅ **Sensitivity, because the split could otherwise be called outcome-chosen (HK-021(y)):** the
targeted `4c7d5ad` re-run entered the series *because* of a concern, so I re-ran the comparison
without it. Routine-only history is **15/480 = 3.125%**; today vs that is **Fisher p = 1.000**. The
conclusion does not depend on including the outcome-triggered run.

🛑 **"Four FAILs in a row" is not four pieces of evidence for a regression.** It is four draws from
one distribution, under a gate that fires on that distribution ~74% of the time (§4). The run of
FAILs is what a *constant* rate looks like through this gate.

**⚠️ The part-1 concentration QA reported (3/3 in part 1, 0 in part 0) is not signal — do not chase
it.** All-history parts 0:1 splits 9:6; today 0:3; Fisher **p = 0.206**, and under 50:50 today alone
is p = 0.250. Parts 0 and 1 are replicates of one level (§1), so no mechanism predicts a split. It
was right of QA to report the observation; it does not support a per-part hypothesis.

---

## 3. 🔴 THE FINDING QA DID NOT ASK ABOUT — a 6% UB ceiling is not a fixed rate threshold

The gate is `PASS iff one-sided CP95 UB ≤ 6%`. **The observed rate that ceiling tolerates rises with
N.** This is arithmetic, not data:

| N (AWGN slots) | PASS iff k ≤ | max observed rate tolerated |
|---|---|---|
| 60 | 0 | **0.000%** |
| **120 (Gate A today)** | **2** | **1.667%** |
| 240 | 8 | 3.333% |
| 300 | 11 | 3.667% |
| 480 | 20 | 4.167% |
| 600 | 26 | 4.333% |

✅ The envelope reproduces R&R-004's own worked examples exactly — `k=2 → 5.153% PASS`,
`k=3 → 6.334% FAIL` — so this is the ratified gate, read correctly.

**Consequence, and it is already on disk:**

| Run | Reading | Rate | 95% UB | Verdict |
|---|---|---|---|---|
| 2026-09-05 `10bbaad` (S5 standalone, N=300) | 6/300 | 2.000% | 3.909% | **PASS** |
| 2026-09-07 `4cc1984` (Gate A, N=120) | 3/120 | 2.500% | 6.334% | **FAIL** |

**Fisher exact between those two readings: p = 0.719 — statistically the same rate.** Three days
apart, same-era build. **The verdict flipped on N, not on the decoder.**

🛑 **This is a sizing defect in R&R-010, which is my design.** R&R-010 correctly restored the
*population* the 6% was ratified against and correctly refused to re-ratify the threshold. What it
never checked is whether N=120 is enough slots for the decoder's **actual** rate to clear that
ceiling. It is not:

| N | P(Gate PASS) at the established 3.182% |
|---|---|
| 60 | 0.144 |
| **120** | **0.261** |
| 240 | 0.644 |
| 480 | 0.909 |
| 600 | 0.952 |

**At N=120 the gate fails ~3 sweeps in 4 with nothing changing.**

🔴 **And one mislabel in `STUDY-SPEC.md` §16 that must be corrected before it is cited again.** The
R&R-010 entry reads *"Gate A alone detects it 77% of the time"*, computing P(FAIL) at 3.33%. That
0.77 is **not power** — 3.33% is the **null**, the state the decoder has been in for every
measurement on record. **0.77 is Gate A's false-alarm rate under no change.** The number is
correctly computed and wrongly labelled. §16 is QA's file; the edit is QA's to make (HK-015), and
this ruling is the authority for it.

---

## 4. What Gate A can and cannot discriminate, at N=120

| True rate | P(Gate A FAIL) |
|---|---|
| 3.182% (**no change**) | **0.739** |
| 4.773% (1.5×) | 0.929 |
| 6.364% (**doubling**) | 0.984 |

A test whose null already fires 74% of the time is not a tripwire. **Gate A at N=120 does not
separate "unchanged" from "twice as bad".**

⚠️ **The pooled evidence clears the ratified ceiling.** `21/660 = 3.182%`, **CP95 UB 4.550% ≤ 6%**.
So the honest statement is: *the decoder does meet the ratified 6% ceiling on all the slots we have
run; it cannot be shown to meet it 120 slots at a time.*

🛑 **Three limits on that sentence, all binding:**
1. It is a **cross-build pooled** statement over ten readings. It does **not** certify any single
   build, today's included.
2. **6% is a convention, not a traced requirement.** §10's rationale justifies gating on the *upper
   bound* rather than the point estimate; it never derives 6% from an NFR. "We meet the ceiling"
   therefore means "we meet the number we wrote down", nothing stronger.
3. This does **not** revisit anything in the closed `FP-REGRESSION` arc. No baseline is created
   here, and none of its retired figures is disturbed.

---

## 5. 🔴 WHAT IS ACTUALLY WRONG, AND IT IS UNTOUCHED BY ANY OF THE ABOVE

On the **same slots, the same audio, the same sessions**:

| Appraiser | AWGN slots | FP events | Rate | CP95 |
|---|---|---|---|---|
| OpenWSFZ | 660 | **21** | **3.182%** | `[2.142%, 4.550%]` |
| WSJT-X | 660 | **0** | 0.000% | UB **0.453%** |

**Fisher exact p = 8.1 × 10⁻⁷.** The intervals do not touch: **≥ 4.7× separated**, and that is a
lower bound because the control's numerator is zero.

**This is the finding. The gate argument in §3–§4 changes nothing about it.** Whether Gate A is
sized at 120 slots or 480, whether it reads PASS or FAIL, our decoder emits a false decode on ~3% of
signal-free AWGN slots and the reference decoder emits none on the identical audio. **That belongs
on the board as the open item; the gate verdict does not.**

⚠️ **HK-026 check, applied to my own §4 claim:** I have not used Gate A's output to bound Gate A's
blind spot. The N-tolerance table in §3 and the operating characteristics in §4 are computed from
the binomial and the Clopper–Pearson definition, not from any run's result.

---

## 6. THE DECISION I AM PUTTING TO THE PO — how S5 should be gated from here

**I am not changing the gate.** R&R-010 was ratified by the PO five days ago; its replacement is the
PO's call, not mine. Four options, with my recommendation first.

**🟢 Option A — RECOMMENDED. Split the two questions the one gate is trying to answer. Zero extra
bench time.**
- **Per-sweep Gate A → `INFO`.** It keeps running at N=120 and keeps feeding the series; it stops
  producing a PASS/FAIL that means nothing at this N.
- **Compliance gate on the trailing 4 sweeps (N=480), ratified 6% UB unchanged.** `PASS iff k ≤ 20`.
  **P(PASS) = 0.909 unchanged; P(PASS) = 0.025 if the rate doubles.** A gate that works.
- **Per-sweep change test** — this sweep's 120 slots vs the trailing baseline, one-sided Fisher at
  α=0.05: false-alarm **0.03**, detects a **2×** shift 0.40 of the time, a **3×** shift 0.82.
- ⚠️ **Honest cost:** the trailing window **lags** — a regression introduced today is diluted 1:4 and
  takes up to four sweeps to reach full strength. The per-sweep change test is what covers the gap,
  and it is blind below ~2×. Both facts must be written into the gate's own definition, not carried
  as prose (HK-021(r)).

**Option B — Raise per-sweep N to 480 AWGN slots.** Same statistical properties as A with no lag.
**Cost ~1.5–2 h of bench time per sweep for S5 alone**, on top of everything else the battery runs.
I do not recommend paying it to learn what pooling gives free.

**Option C — Leave R&R-010 exactly as ratified.** Legitimate, and the cost is specific: ~3 sweeps in
4 close with an overall verdict of FAIL, permanently, and the board loses its ability to distinguish
a real S5 event from the standing condition. **If this is chosen, it should be chosen knowing that,
not discovered over the next four sweeps.**

**Option D — Re-ratify the 6% number itself.** ❌ **Not recommended, and I would argue against it.**
6% has no requirement behind it (§4 limit 2); moving it to fit the measured rate would convert a
convention into a rubber stamp, and the WSJT-X contrast in §5 is the bar that actually matters.

---

## 7. Status

- ✅ **QA's FAIL verdict stands, as reported.** Nothing in the run is void, nothing is re-run.
- ✅ **Everything else in the sweep is in-family and needs no ruling** — S1/S2/S3 GR&R inside their
  PASS bands, S7/S8 in-family, Check B `0/60` clean on its first live exercise.
- ✅ **QA's handling was right on both process points**: the `cycle_utc` re-scoping before trusting
  the matcher summary, and declining to rule (HK-015). The `matcher.py` session-wide FP attribution
  is housekeeping, as QA classified it — **not** a gating defect.
- 🔴 **RULED: today's point is not a regression.** The S5 AWGN rate is **21/660 = 3.182%**
  `[2.142%, 4.550%]`, constant across ten readings (χ² p = 0.449), no trend (p = 0.514).
- 🔴 **RULED: the Gate A FAIL is a sample-size artefact of the gate's form**, demonstrated against
  the 2026-09-05 N=300 standalone that PASSED the same ceiling at the same rate (Fisher p = 0.719).
- 🔴 **OPEN, and this is the real one: OpenWSFZ 3.182% vs WSJT-X 0/660 on identical slots**,
  ≥ 4.7× separated, p = 8.1 × 10⁻⁷.
- ⏳ **AWAITING THE PO on §6.** QA does nothing to the gate until that ruling lands.
- ⏳ **`STUDY-SPEC.md` §16's "detects a regression 77% of the time" needs QA's correction** (§3) —
  independent of which §6 option the PO picks.
- 🛑 **Nothing armed. No `src/`/`native/` change proposed by this ruling.**

---

**Architect, 2026-09-08 14:29 UTC.** Committed locally, **not pushed** (HK-014).
`git diff --stat -- src/ native/` empty.
