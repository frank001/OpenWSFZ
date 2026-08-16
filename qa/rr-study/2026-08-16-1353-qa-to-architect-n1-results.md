# N1 results — BER at the refiner's vs. the grid position: ROW 2 fires, limb 1 is dead

**QA → Architect** · 2026-08-16 13:53Z · branch `feat/r1b-sync-refiner-instrument-correction`
**Spec:** `qa/rr-study/2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-spec.md`
**Harness:** `qa/rr-study/n1-ber-at-refined-position/` (`population.py`, `n1_stats.py`,
`sign_unit_test.py`, `run_n1.py`), results in `results/`.

---

## 0. Preconditions — both cleared before this run

- **§3.1 (BER harness recovery/reproduction):** cleared 2026-08-16 11:21Z, report
  `2026-08-16-1121-qa-n1-precondition-ber-harness-recovery-and-bar-reproduction.md`.
  `B50=11.3%` reproduced at 11.65% (0.35 pp), matched-hit control 2.9%→2.87% (exact),
  THE 135 median 44.0%→43.97% (exact). ROW 0a did not fire.
- **§3.2 (`ft8_extract_llrs_at` export):** applied by a separate Developer session
  (`n1-extract-llrs-at-position`), reviewed and **MERGED to `main`** as PR #125
  (2026-08-16 12:57:58Z), plus a follow-up native-binaries PR #126. **This is new since
  the board's last entry** — the board still said "not pushed" as of 11:53Z; it has
  since been reviewed and merged by the Captain. DLL `src/OpenWSFZ.Ft8/Native/win-x64/
  libft8.dll`, SHA256 `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`,
  shim `20260042`, asserted by the harness before every run.

Both preconditions satisfied, N1 itself run for the first time this session.

## 1. Mandatory sign unit test — PASSED, run first, harness refuses to arm without it

`sign_unit_test.py`: synthetic rows (every REFINED row perfect, every GRID row maximally
wrong, and the negation) gave `d_ber = +1.000000` / `-1.000000` exactly, CI entirely on
the correct side of zero in both directions, and `f_cross` correctly one-directional
(above→below counts, below→above does not). `run_n1.py` calls this module first and
exits without arming if it fails (it did not).

## 2. Population

Combined **THE 135 + THE 567** (candidate-present-and-failed, the "87.9%" decomposition
— reusing `c2_phase2c_ber_measurement.py`'s own population functions unchanged, not
re-derived, to avoid a second implementation drifting from the first):

| population | WSJT-X rows | grid-matched | measured (true codeword + all 3 extractions rc=0) |
|---|---|---|---|
| THE 135 (K10/cap140, score≥10) | 135 | 135 | 126 |
| THE 567 (K4/cap2000, score 5-9) | 567 | 306 | 279 |
| **Combined** | | **441** | **405** |

36 rows dropped, all `no_true_codeword` (message text not re-encodable — same category
`c2_phase2c_ber_measurement.py` already tracks). Zero rows dropped on any extraction or
refinement return code — `ft8_extract_llrs_at` never returned `-3` (off-passband) on
this population, `ft8_refine_candidate` never returned non-zero.

## 3. Gate — strict order, as pre-registered (spec §5)

| Row | Result | Detail |
|---|---|---|
| **0a** | cleared (precondition, §0 above) | not re-run this session; the bar is not re-derived from N1's own data (that would be the HK-026 violation ROW 0a exists to forbid) |
| **0b** | **clear** | matched-hit control: n=195 grid-matched, 171 measured, median BER **2.87%** (bound ≤5%), 0 non-zero rcs. 🔴 **2.87% is an EXACT match to §3.1's independent reproduction of the same quantity via the OLD raw-LLR-capture instrument** — two different extraction pathways (captured-and-read-back vs. live `ft8_extract_llrs_at`) landing on the identical number is strong evidence the new export is correctly wired, beyond the pre-registered bound alone. |
| **0c** | **clear** | 405 paired rows ≥ 200 |
| **0d** | **clear** | median `|Δt| = 54 ms` (floor 5 ms), median `|Δf| = 1.5 Hz` (floor 0.25 Hz) — the refiner moves real distances on this population, so GRID and REFINED are genuinely different positions |
| **ROW 1** | did not fire | `d_ber = -0.57 pp`, nowhere near `≥15 pp` |
| **ROW 2** | 🔴 **FIRES** | `|d_ber| = 0.57 pp ≤ 5 pp` **and** `CI_hi = +0.00 pp < 15 pp` |
| ROW 3 | n/a (ROW 2 fired first) | |

## 4. Primary and secondary statistics

**Primary — `d_ber`, paired median `BER_grid − BER_refined`, cluster bootstrap over
`ts`** (HK-021(i), 2000 draws, seed 20260816):

| | point estimate | mean | CI95 | p (two-sided) | n rows | n clusters |
|---|---|---|---|---|---|---|
| **Combined** | **−0.57 pp** | −0.49 pp | **[−1.15, +0.00] pp** | 0.689 | 405 | 67 |

Positive would mean refinement helps; the point estimate is slightly negative and the
CI straddles zero (p=0.69) — **no detectable effect**, consistent with ROW 2.

**Secondary — `f_cross`** (fraction crossing ABOVE `B50=11.3%` → AT-OR-BELOW it under
refinement): **0.0%**. Median BER sits at ~44–50% in both arms — nowhere near the
11.3% correction threshold, so no row is close enough to cross either direction. This
is the number that would convert to recall if ROW 1 had fired; it did not.

**Per-population breakdown** (reported per spec's own instruction to include a
per-stratum table, not average to a verdict):

| population | n | `d_ber` point est. | CI95 | p | f_cross |
|---|---|---|---|---|---|
| THE 135 | 126 | **−4.02 pp** | **[−6.90, −2.30] pp** | **0.000** | 0.0% |
| THE 567 | 279 | +0.00 pp | [+0.00, +0.00] pp | 1.000 | 0.0% |

🔴 **THE 135 stratum shows a statistically significant HARMFUL effect** — CI entirely
below zero, refinement makes hard-decision BER *worse* by ~4 pp on the higher-score
(≥10) subpopulation specifically. THE 567 (score 5-9, lower initial sync quality) shows
no detectable effect either way. Read together this is not evidence the refiner
sometimes helps and sometimes doesn't cancel out to zero by coincidence — it is
evidence that **on rows where the coarse/grid position already sits closer to correct
(higher score), nudging it by the refiner's `(Δf, Δt)` more often moves it slightly
away than toward the extraction the decoder needs**, while on weaker candidates the
refiner's correction is directionally noise. Neither stratum shows a *beneficial*
effect large enough to matter, so this does not change the combined ROW 2 verdict, but
it is reported per the spec's own "do not average to a verdict" instruction and because
it sharpens rather than softens ROW 2's conclusion.

## 5. Verdict — ROW 2, limb 1 is dead as a D-001 treatment

**Extracting at the refiner's position instead of the grid position does not fix the
reading.** `|d_ber|` is within 1 pp of zero, the CI upper bound sits at 0.00 pp (nowhere
close to the 15 pp bound that would justify ROW 1), and `f_cross = 0%`. Per spec §5 ROW
2's pre-written consequence:

> limb 1 is DEAD as a D-001 treatment. Extracting at a better position does not fix the
> reading, so the failure is in **how the bits are formed**, not **where they are
> read** — i.e. the non-coherent, magnitude-only, single-symbol metric. R2 as framed is
> dead; the next work is limb 2 (coherent multi-symbol LLRs off the complex baseband
> `sync_refiner.c:417-449` already builds and `free()`s).

This is a real finding, not a void (spec's own framing) — it closes limb 1 on outcome
evidence (BER against a bar that was measured, not a proxy), the first N1-class result
in this thread to do so after M1/M2/M4 all failed on proxy-statistic grounds.

## 6. Predictions scoring (spec §8, nothing gated on these)

The Architect's own pre-registered prediction was **ROW 2 at ~55% credence** ("I now
think limb 2 is more likely to be the answer than limb 1"), explicitly flagged as
worth little and gating on nothing. **ROW 2 fired.** Categorical prediction record
updates to 6/9 (was 5/9 going in); this specific call was correct.

## 7. HK-025 re-derivation

Independently re-checked against spec §6's table: all four VALIDITY rows (0a-0d) are
genuinely "does this row's firing/non-firing still answer what the gate names, on both
branches" — none merely change printed text, none are DIAGNOSTIC. Agree with the
spec's own classification; did not need to refuse.

## 8. Scope discipline (spec §9, unaffected)

No `src/` or native change in this session (the one native change, §3.2's export, was
already applied by the prior Developer session and reviewed/merged separately). No
capture run. M5 not run. R0/R1/R1b's ~1.1 ms/0.5 Hz accuracy figures still not cited for
real signals — this result is about the *consequence* of using the refiner, not its
accuracy, consistent with the standing prohibition. R2 stays unscoped — ROW 2 firing
means R2 (wiring refinement into the decode path) is now **excluded**, not merely
"not yet scoped": there is nothing left to scope on limb 1.

## 9. Deliverables (spec §10)

1. §3.1 harness recovery — delivered 11:21Z (prior report).
2. §3.2 dev-task — delivered 11:34Z, applied 11:53Z, **merged to `main` 12:57:58Z** (new
   since the board's last entry, noted in §0 above).
3. `qa/rr-study/n1-ber-at-refined-position/` — harness, with the §4 sign unit test and
   the anchor-rounding assertion in code (`run_n1.py`'s `_anchor()` docstring names the
   M1/M2 confound explicitly, per spec's instruction).
4. `results/n1_results.json` (405 rows, `ts` + numeric fields only — NFR-021, no
   message text), `results/n1_gate_report.json`, `results/harness_run.log`.
5. This report.
6. **Board update — in the same edit as this result** (HK-024), see next message.

## 10. What QA does not do

Per HK-015, QA does not author the next spec. ROW 2 firing means R2 (as previously
framed — wiring `ft8_refine_candidate` into the decode path) is dead; limb 2 (coherent
multi-symbol LLR extraction off the complex baseband) is the Architect's to scope next,
if the Captain agrees with the direction. Nothing here is authorised to run beyond what
this report already ran.
