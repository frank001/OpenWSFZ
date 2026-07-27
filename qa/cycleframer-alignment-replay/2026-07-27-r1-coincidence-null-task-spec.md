# D-001 R.1 — the coincidence null, QA task spec

**Author:** QA, 2026-07-27. **Operationalises:**
`2026-07-27-1730-architect-row4-scoping-design.md` §4 (R.1), §3.1's geometry, §6's sequencing
("R.1 first, alone, report before anything else starts"). Reading rules (§4's table) fixed by the
Architect in advance and reused verbatim below — this spec does not restate a judgement call, it
operationalises one already made.
**QA-runnable directly: no `src/`/native change, HK-011 does not apply, no `dev-tasks/` entry** —
same posture as B.1/B.2/B.1b. Confirmed this session: the design's claim that R.1 needs "frozen
artefacts only" checks out — `artefacts/20260725_live_run_1806/c4_min_score/{k10,k4_cap2000}/
k10_c0.10_n60/candidate_diag.csv` and `owsfz/wav68/` (the 68-cycle list) are present on disk from
C.4; nothing new to capture or rebuild.

---

## 1. Question

Does "a candidate exists within ±10 Hz / ±0.5 s of a WSJT-X-reported message" (C.4's `recov648`
metric) measure detection, or the density of our own candidate set at the tested settings?

## 2. Method — two comparison conditions, both offline, against C.4's own frozen output

Reuses `c4_min_score_sweep_analysis.py`'s `compute_648_population`, `load_candidate_diag`,
`has_any_candidate_nearby`, `parse_all_txt` directly (imported, not copied) to re-derive the fixed
648-message population and re-match it under new conditions. Settings tested: **k10** (K_MIN_SCORE
10, K_MAX_CANDIDATES 600 — "K=10@600") and **k4_cap2000** (K_MIN_SCORE 4, K_MAX_CANDIDATES 2000 —
"K=4@2000"), the design's stated minimum pair.

1. **Frequency-displaced null.** For each of the 648 targets, displace its WSJT-X-reported
   frequency by δ ∈ {±150, ±300, ±450, ±600} Hz, wrapping inside the 200–3000 Hz band (`new_freq =
   200 + ((freq - 200 + δ) mod 2800)`), keep `dt` and cycle unchanged. Re-match at the published
   tolerance (±10 Hz / ±0.5 s). Report `recov648` for each δ, both settings.
2. **Tolerance ladder.** Re-match the true (undisplaced) 648 at freq tolerances {10, 5, 3.125,
   1.5625} Hz, each crossed with dt tolerances {0.5, 0.16, 0.08} s (12 cells), both settings.

## 3. Reading rule — fixed by the Architect, reused verbatim (design doc §4, R.1 table)

| result | reading |
|---|---|
| Null ≈ true within a few points at K=4@2000 | The published `recov648` series measures candidate density, not detection. The Architect's 17:00 §5 inference is withdrawn; sync accuracy is un-eliminated and R.2/R.3 become the main event. |
| True ≫ null at every tolerance | Detection is real at those locations; residue is genuinely downstream; the 17:00 ruling stands as written; R.2/R.3 proceed to separate estimation from demodulation. |
| True ≫ null at ±10 Hz but converging to null as tolerance tightens | The most informative outcome: detection is real but imprecise. The convergence point measures sync-estimator error; R.2 prices what it costs. |

QA computes and reports the numbers against this table; no new judgement call is introduced at this
step, same convention as B.1b's task spec.

## 4. Self-check before trusting any number

`compute_648_population` must reproduce C.3's published split exactly (`shared_hit=1235
matched_missed_failed=135 near_decoded=10 no_candidate_anywhere=648`) against the same frozen
artefacts — it already prints this comparison. If it does not match, stop and report the mismatch
rather than the arm's result (design doc §6's stop rule).

## 5. What this does not authorise

Same guardrails as the design doc §7: no native/`src/` change, no push/merge, no
`pre_merge_check.py` (HK-006), NFR-021 (aggregate counts only — the 648 population's messages stay
inside frozen `artefacts/`, never printed in full to a committed script or findings doc).

## 6. Cross-references

- `2026-07-27-1730-architect-row4-scoping-design.md` — the design this operationalises, §3, §4 (R.1), §6.
- `c4_min_score_sweep_analysis.py` — matching machinery reused verbatim.
- `2026-07-26-c4-min-score-sweep-findings.md` — the published `recov648` series this arm audits.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — origin of the 648 population.
