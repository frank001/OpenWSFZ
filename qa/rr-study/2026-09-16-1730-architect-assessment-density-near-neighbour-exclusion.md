# Assessment — near-neighbour exclusion ("density"): is the mechanism question worth reopening?

**Architect, 2026-09-16T17:30Z** (`date -u`, HK-017). Branch `arch/e4-channel-impairments` (docs-only;
`git diff --stat -- src/ native/` empty). **An ASSESSMENT, not a pre-registration.** It specifies
nothing and authorises nothing. The Captain asked for the reasoning before anyone builds.

---

## 0. Correction first

🔴 **I twice told the Captain density was "completely unexplored" and used it to justify stopping the
drift work. That was wrong.** Density has a Captain-authorised arm (`F-NBR-A`, 2026-08-23) that
**established causality**, and a follow-up (`NBR-A`) whose calibration closed 2026-08-30 with named
re-entry conditions. The drift decision still stands on its own merits; the characterisation did not.
**Fourth assertion-before-checking in one day.**

---

## 1. What is already established — not hypothesised

From `F-NBR-A` (`2026-08-23-1214-qa-to-architect-f-nbr-a-results.md`), synthetic scenes, truth known:

- **C1 — causality, unambiguous.** Station F: **0/100** with neighbour E present, **100/100** with E
  removed. Nothing else changed, same 100 seeds. CIs non-overlapping by the widest possible margin.
  **E is necessary and sufficient.**
- **C2 — the exclusion zone, in separation.** E at 1150 Hz/−5 dB, F at −8 dB:

  | Δ | 6.25 | 12.0 | 18.75 | **25.0** | **31.25** | 50 | 100 |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | tone bins | 1 | 1.9 | 3 | 4 | 5 | 8 | 16 |
  | `R` | 0/100 | 0/100 | 0/100 | **27/100** | **98/100** | 100/100 | 100/100 |

  **Complete exclusion through 3 bins (18.75 Hz); sharp transition at 4; resolved by 5 (31.25 Hz).**
- **C3 — a level knife-edge, not a weak-signal tail.** At 12 Hz separation, F recovers **100/100 when
  3 dB stronger** than E and **0/100 when merely equal**. The flip happens inside one 3 dB step.
  **It is a level-*ratio* effect.**
- **Cross-decoder:** WSJT-X takes the same station **5/5** where we take it **0/25** (C-ASYM-A).

🔴 **This is categorically different from DRIFT and FADE.** There I predicted a mechanism and the
measurement found nothing. Here there is a deterministic, reproducible, causally-established failure
with a reproducer, and a cross-decoder differential. **My measured bias — over-predicting findable
defects — is not what is operating here. The defect is already found.**

---

## 2. 🔴 NEW — how big is it? Computed while drafting (HK-018), no new run

The one thing nobody had: **how often the failing geometry occurs live.** Computed directly from C2's
REF `ALL.TXT` (WSJT-X FT991A), valid window from the `19:36:45Z` Amendment-3 boundary.
🔒 **NFR-021: numeric fields only — `[0]` cycle, `[4]` SNR, `[6]` Hz. Message text never parsed.**

**91,076 REF rows in 4,113 cycles, median 24 decodes per cycle.** For each row, is there another
decode in the same cycle within Δ Hz whose SNR is **≥ its own** (C3's exclusion condition)?

| separation | bench `R` there | share of **all** REF rows | share of rows **≥ −10 dB** |
|---|---|---:|---:|
| **18.75 Hz (3 bins)** | **0/100 complete** | **11.61%** | **8.90%** |
| 25.00 Hz (4 bins) | 27/100 | 15.35% | 11.71% |
| 31.25 Hz (5 bins) | 98/100 | 18.63% | 14.29% |

**Sizing, on the complete-exclusion geometry only:**

- 8.90% of the 60,239 REF rows at ≥ −10 dB = **≈ 5,361 rows**.
- As decode rate: 5,361 / 91,046 = **≈ 5.9 pp**.
- ✅ **Sanity check against the budget:** above-threshold misses are 16,355. 5,361 is **32.8%** of
  them — large, but **inside** the budget. Had it exceeded 27.1% of the population the model would be
  refuted; it is not.

**For comparison, everything else this programme has sized:**

| candidate | ceiling | status |
|---|---:|---|
| **Near-neighbour exclusion** | **≈ 5.9 pp** | causal reproducer, mechanism open |
| `PASSBAND-140` | 2.1 pp | **shipped** |
| FADE (`E4`) | ≤ 1.0 pp, likely ≈ 0.3 | census running |
| DRIFT (`E4`) | 0 | closed, `F3` |

🔴 **Near-neighbour exclusion is the largest identified contributor on the board by roughly 3×, and
the only one with a reproducer.**

### 2.1 What this sizing is NOT — three caveats that must travel with the number

1. ⚠️ **It counts only neighbours WSJT-X decoded.** Real RF carries more signals than that, so true
   neighbour density is **higher**. The bias is **down**, which makes 5.9 pp a floor on exposure — but
   see (2), which cuts the other way.
2. 🔴 **It assumes the 0/100 generalises from one synthetic scene to all live near-neighbour pairs.**
   That is a large step. `F-NBR-A` measured one geometry (E/F in S8HN) with sweeps in separation and
   level, not a population of geometries. **5.9 pp is a ceiling, not an expectation.**
3. 🛑 **It is a SIZING calculation, not a mechanism claim, and it may not be read as one.** Nothing
   here says anything about whether crowding is local or diffuse. **If this number starts being cited
   as evidence about diffuse crowding, that reading is prohibited and out of scope** (the boundary the
   2026-08-27 spec §2 drew).

---

## 3. What is actually open, and why the last attempt failed

**Open: M1 vs M2** — and they lead to completely different places.

- **M1 — tone-set contention in extraction.** One FT8 signal spans 43.75 Hz (8 tones × 6.25). A
  neighbour inside that span puts energy in the victim's own bins, and a **magnitude-only,
  single-symbol** max-log cannot tell "my tone 3" from "neighbour's tone 0". ⇒ **the same work item as
  D-001 limb 2.** The ≈5.9 pp attaches to extraction work and becomes its business case.
- **M2 — pass-1 / tile suppression.** The zone is set by an implementation constant, not the tone span.
  ⚠️ **The candidate-budget family is closed twice**, so this outcome **authorises nothing directly** —
  it needs a new pre-registration naming the specific tile parameter, FP primary.

**Why `NBR-A` closed:** ROW 0c′, the calibration meant to find a level where `R` varies *continuously*
with Δ so the sweep could see structure. **No level sustained a 5-point readable run** (`0.15≤R≤0.85`);
best was one isolated point. 🔴 **The reason is C3: `R` is a knife-edge.** A binary decode indicator at
a knife-edge is 0 or 1 with nothing in between, so `R(Δ)` is a step function and the periodicity ROW 1
looks for cannot appear **whatever the truth is.**

🔴 **That is today's lesson again, third instance: an instrument built to measure `X` must not assume
`X` is small or absent.** ROW 1 needs graded degradation; the instrument only reports total success or
total failure.

---

## 4. "What changed other than appetite for the answer"

`NBR-A`'s closure requires this be named. It can be:

1. **A metric with dynamic range — exactly what the closure asked for.** Not "did it decode" but **how
   corrupted the bit metrics are**: BER of the extracted LLRs against known truth on a synthetic scene.
   Range 0–174 bits instead of {0,1}, and it does not saturate at the knife-edge.
2. **The tooling was built after `NBR-A` was specced.** `N1` ("extract LLRs at position", openspec
   change **archived**), `R2` coherent-LLR instrument (archived), and
   `native/ft8_lib_vendor/refine/coherent_llr.c` is in the tree and compiled.
   ⚠️ **Whether it is callable from the CURRENT shipped shim without a Developer change is NOT
   established and I am not asserting it** — after two feasibility claims of mine failed today, that is
   a ROW 0 question for the arm, not a premise of this assessment.
3. **The sizing in §2 did not exist.** `NBR-A` was specced without knowing the exposure was ≈ 5.9 pp.

**All three are real changes. None of them is appetite.**

---

## 5. 🔴 The reason I am NOT recommending the mechanism arm next

**Read C2 against ROW 1's own predicate.** ROW 1 (M1) requires `R ≥ 0.90` by `|Δ|` = 43.75 ± 6.25 Hz,
i.e. **not before 37.5 Hz**. Measured: **`R` = 0.98 already at 31.25 Hz.** That satisfies **ROW 2**'s
predicate instead — recovery *outside* the tone-span window — which reads **M2**.

**So the existing data leans M2, and M2 authorises nothing directly.** Spending a build cycle to land
on "this is a tile artefact, now write another pre-registration" is poor value.

⚠️ **Held loosely, and logged.** C2's Δ grid is coarse (6.25 / 12 / 18.75 / 25 / 31.25 / 50 / 100) and
cannot resolve the 6.25 Hz periodicity ROW 1 actually tests, and it is one level pair. **And my last
mechanism call was backwards** (FADE §4). This is a lean, not a finding.

---

## 6. What I recommend instead, and the one thing that gates it

**The decisive question is not "which mechanism" — it is "does the geometry actually cost us live?"**
§2 establishes exposure. It does **not** establish that our live misses concentrate there. That check
is worth more than the mechanism arm, it needs **no new run**, and it would either promote this to the
programme's main line or deflate it.

🔴 **But it needs a Captain ruling first, and I will not write it without one.** Stratifying our live
recovery by neighbour distance is **close to retired spectral locality** — four attempts, zero
readings, *"do not re-propose under any name."*

| | retired spectral locality | the proposed check |
|---|---|---|
| question | is the crowding penalty local or diffuse? (exploratory) | does a geometry with **already-established synthetic causality** show its predicted signature live? (confirmatory) |
| population | live corpora, fished | live rows **partitioned by a predicate fixed in advance from C2/C3** |
| prior readings | **zero, four times** | C1/C2/C3 fired cleanly |

**My reading is that it is a different question** — the same distinction the 2026-08-27 spec §2 drew
and that the Captain accepted then. **But it uses the same data and the same stratification machinery
that failed four times, and "under any name" is deliberately strong wording. That is his call, not
mine.**

---

## 7. Recommendation

1. ➡️ **Captain rules on §6's prohibition question.** Nothing proceeds without it.
2. **If cleared:** a small, pre-registered live-concentration check — does our miss rate inside the
   18.75 Hz equal-or-stronger geometry exceed our miss rate outside it, by a margin fixed in advance?
   No station time, one corpus, one predicate.
3. **Only if that fires:** the M1/M2 mechanism arm, on a BER-style continuous metric, with the shim
   feasibility question as its ROW 0.
4. 🛑 **Not now:** any fix, any `src/`/`native/` work, any reopening of the candidate-budget family.

## 8. Predictions, blind, logged (`architect-prediction-ledger.md`)

| # | prediction | P | class |
|---|---|---:|:---:|
| 1 | Live-concentration check, if run, fires — misses concentrate in the geometry | **0.70** | H |
| 2 | Mechanism, if ever resolved, reads **M2** (tile artefact), not M1 | 0.60 | H-mech |
| 3 | LLR extraction is **not** callable from the shipped shim without a Developer change | 0.65 | C |
| 4 | True live exposure at 18.75 Hz exceeds the 8.90% measured here (undecoded neighbours) | 0.80 | C |

🔴 **Weight accordingly: 1 of 7 on hypothesised calls, and my last mechanism call was backwards.**
