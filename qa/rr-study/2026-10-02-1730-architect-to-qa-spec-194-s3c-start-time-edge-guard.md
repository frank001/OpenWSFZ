# SPEC — #194 part B step 2: S3c, a lean start-time edge guard in the S1–S8 battery

- **To:** QA (owner) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~17:30Z (HK-017)
- **Branch:** `arch/194-rr-improvements`. Docs only: `git diff --stat -- src/ native/` empty. **QA tooling under `qa/` only.**
- **Depends on:** the start-time edge run, i.e. the LATENESS spec `qa/rr-study/2026-10-02-0720-architect-to-qa-spec-lateness-tolerance.md` **as of Amendment 2** (`arch/subtraction-feasibility` `7de98336`). That run is #194 part B step 1 (late and early sides, ≈ 51 min). **S3c is not built until that run has reported and the Architect has ruled on it.**
- **Status:** PRE-REGISTERED. The rule that picks S3c's points from the edge run is fixed here, before the edge run has produced any data, so that the points cannot be chosen after looking.
- **Cost per battery:** **12 cycles ≈ 3 min.**

## 1. Purpose

S3 sweeps start time to ~2.7 s, but it measures **DT reporting** (bias and linearity), and every one of its parts decodes. It cannot see a decoder's start-time **edge** moving. S3c can: it sits a few points **on** OpenWSFZ's measured edges, where a regression in the sync search shows first. The August negative-DT SNR-collapse bug is the kind of defect it would have caught.

**Additive only:** S1–S3, S3b and every other existing part stay unchanged, so their history stays comparable. S3c gets its own `trend.csv` columns.

## 2. Parts (picked mechanically from the edge run; QA writes this rule as code)

From the edge run's OpenWSFZ results at **−8 dB**:

| Part | `L` | Block |
|---|---|---|
| S3c-L90 | `E90(OpenWSFZ, −8)` | late (truncated at the slot end) |
| S3c-L50 | `E50(OpenWSFZ, −8)` | late |
| S3c-E90 | `E90e(OpenWSFZ, −8)` | early (early-armed, followed by an idle cycle) |
| S3c-E50 | `E50e(OpenWSFZ, −8)` | early |

- If `E90 = E50` on a side, the second part moves one grid step outward (`E50 + 0.25` late, `E50e − 0.25` early).
- If an edge was reported beyond the grid ("> 6.00", "< −3.00"), the part sits at the grid end, and the report labels it "edge beyond grid; part guards the grid end only".
- **Reference rate `r_ref(part, d)`** = the **lower** Wilson 95 % bound of decoder `d`'s rate at that cell in the edge run. The lower bound is used because that rate rests on 32 signals and is itself uncertain.
- The four `L` values, both decoders' `r_ref`, the edge run's commit and the build it measured go into the scenario JSON, committed with its SHA-256 **before** the first battery that includes S3c.

## 3. Render and playback

Identical to the edge run's blocks, so that S3c is directly comparable with it: reuse that run's render, truncation, assignment and early-arm code (no copy), at −8 dB, 16 signals per cycle on the same 150 Hz slots, every text unique and Q-prefix synthetic, **32 signals per part**. Late parts: 64 signals ⇒ 4 cycles. Early parts: 64 signals ⇒ 4 planted + 4 idle cycles. **12 cycles in all.** Seed per battery: the battery's existing seed formula, with `'S3c'` as the scenario key.

## 4. Rows (per battery; mechanical)

For each part and decoder, `X` = matched of 32 (planted text exact, same cycle, |Δf| ≤ 10 Hz).

- `k*(part, d)` = the largest integer `k` such that `P(X < k | n = 32, p = r_ref) ≤ 0.01` (binomial, computed in code and printed).
- **S3c-WSJT-X (validity):** every WSJT-X part has `X ≥ k*`. **FAIL ⇒ the chain or the harness has changed, not our build. The OpenWSFZ S3c rows of that battery are not read**, and the report says so.
- **S3c-OWSFZ (the guard):** every OpenWSFZ part has `X ≥ k*`. A FAIL is a **flag to the Architect**, not a verdict: one battery's 32 signals cannot by themselves tell a regression from bad luck at the 1 % level across four parts and many batteries. The Architect may order a repeat or a full edge run.
- **Multiplicity, stated:** 4 parts × 2 decoders at 1 % each give roughly an 8 % chance per battery of at least one false FAIL somewhere. That is accepted for a guard whose FAIL triggers a repeat, not a ruling.
- Flag-state record: `subtractionEnabled` as run (main ships ON since 2026-10-02 10:23:45Z). S3c is a sync-search guard. Its `r_ref` comes from a flag-OFF run, so if the battery runs flag ON, the report labels it, and QA records which in `arm_config.json`. 🛑 Never pool flag-ON with flag-OFF S3c rows in the trend.

## 5. Not in scope

The full edge characterisation (that is the edge run, and a repeat of it is the Architect's call); WSJT-X's edges as a guard target (WSJT-X is the fixed reference, and its rows here only check validity); any change to S3 or S3b.

## 6. Predictions (blind; scored at the first three batteries that include S3c)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| S3C1 | No S3c-WSJT-X FAIL in the first three batteries | 0.80 | H |
| S3C2 | No S3c-OWSFZ FAIL in the first three batteries (no sync-search change is planned) | 0.75 | H |
