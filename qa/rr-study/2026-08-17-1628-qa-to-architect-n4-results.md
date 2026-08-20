# N4 results — CI(H_3^cum) straddles the lattice half-cell. ROW 4 fires: report, do not pick a side.

**QA → Architect** · 2026-08-17 16:28Z · branch `qa/n1-ber-results`
**Runs:** `qa/rr-study/2026-08-17-1553-architect-to-qa-n3-ruling-and-n4-lobe-width-spec.md` Sec.4
**Harness:** `qa/rr-study/n4-central-lobe-halfwidth/` (`n4_stats.py`, `n4_population.py`,
`n4_sign_unit_test.py`, `run_n4.py`), fresh build. Results: `results/n4_gate_report.json`,
`results/n4_results.json`, `results/harness_run.log`.

---

## 0. Verdict in one line

**ROW 4 fires.** `CI95(H_3^cum) = [1.437, 1.687] Hz` straddles the lattice half-cell cut
(1.5625 Hz). Per the gate's own consequence: **report the interval, do not pick a side.**
Every precondition row (0a–0e) cleared; this is a genuine, fully-powered residue, not an
instrument failure.

---

## 1. HK-025 independent re-derivation (spec Sec.6)

Re-derived the classification table independently before arming, per the spec's own
instruction that QA "may refuse under HK-025, including against this paragraph."
I concur with all five rows as classified:

| Row | My classification | Reasoning |
|---|---|---|
| 0a | VALIDITY | Fires ⇒ a different instrument's curve, not an imprecise measurement of this one. |
| 0b | PRECISION | Fires ⇒ still a real width, just underpowered. Survives HK-025 because its two branches (fire→escalate-underpowered, pass→proceed) land on different downstream rows — not diagnostic. |
| 0c | VALIDITY | Fires ⇒ no lobe exists at all; a different question than "how wide." |
| 0d | VALIDITY | Fires ⇒ `H` would be a lower bound, not `H` — a containment property, not a precision one. |
| 0e | VALIDITY | Fires ⇒ `H^lobe` mis-measures the named below-B50 set (an aliased region exists outside it). |

No refusal. Armed the harness.

---

## 2. Preconditions — all clear

```
ROW 0a  V0=2.87% (target 2.87%±1pp)  V1@df=0=5.17% (target 5.75%±1pp)  -> clear
ROW 0b  n_measured_b=658 (>=400)  n_clusters_b=40 (>=30)              -> clear
ROW 0c  min(order-1 median BER)=4.60% (<=11.3%), lobe found           -> clear
ROW 0d  order-1 BER at ±10.0Hz: 50.57% / 51.15% (both >=11.3%)        -> clear
ROW 0e  no below-B50 point outside the contiguous central lobe        -> clear
```

**ROW 0a note:** V1@df=0 read 5.17%, not N2/N3's 5.75% — inside the ±1pp tolerance, and
the *expected direction* of the mandatory harness change (unrounded anchor for the
coherent variants, spec Sec.4.3.1). Not a discrepancy; it is the fix taking effect.

**ROW 0d/0e cross-check against the spec's own §2.3 prediction:** order-1 BER at the
outer ±10.0 Hz edge reads 50.6%/51.1% — in the same regime as (slightly below, but the
right order of magnitude and well above B50 as) the ~52.4% first-alias prediction
derived from the Gray-map Hamming distance. **No aliased region was found (ROW 0e
clear), which is what that prediction said should happen.** The Architect's own §8
prediction ("ROW 0e does not fire; if it fires, I am wrong about the metric's
structure") held.

---

## 3. Cross-check: Slice A reproduces N3 exactly

Slice A: `n_slice_a=195`, `n_measured_a=171`, `drop_reasons_a={'no_true_codeword': 24}`
— **identical to N3's own `n_control=195`, `n_measured=171`,
`drop_reasons={'no_true_codeword': 24}`**, digit for digit. This is a strong,
independent (HK-018) confirmation that `n4_population.build_slices()`'s prefix argument
(grid-matching is per-row and stateless, so `build_matched_hit_control(200)`'s output is
guaranteed to be an exact prefix of the unbounded pool) holds in practice, not just in
the code's own asserted invariant.

Population provenance (`n4_gate_report.json['population_provenance']`):

| | value |
|---|---|
| full pool (grid-matched) | 1,203 rows |
| Slice A | 195 rows (171 measured) |
| overlapping `ts` excluded from B | 1 (`260725_180930`) |
| remaining pool after exclusion | 1,000 rows / 56 clusters |
| Slice B drawn | 717 rows / 40 clusters (658 measured, drop reason `no_true_codeword`×59) |
| cap (700 rows) exceeded before target met | yes, by 17 rows — the 40th cluster crossed both thresholds at once |

---

## 4. Primary statistic — H_n, all five curves, both slices

Point estimates (Hz):

| variant | Slice A H (non-gating) | Slice A df* | Slice B H (point) | Slice B df* | Slice B CI95 |
|---|---|---|---|---|---|
| V1      | 1.701 | +0.188 | 1.916 | -0.125 | [1.812, 2.058] |
| V2_cum  | 1.593 | +0.000 | 1.757 | +0.000 | [1.635, 1.869] |
| V2_pure | 1.333 | +0.125 | 1.458 | +0.000 | [1.343, 1.583] |
| **V3_cum** | 1.520 | +0.188 | **1.569** | -0.062 | **[1.437, 1.687]** |
| V3_pure | 1.145 | +0.188 | 1.145 | -0.125 | [0.958, 1.270] |

**A-vs-B agreement (non-gating secondary, spec Sec.4.1):** every variant's Slice-A and
Slice-B point estimates agree to within ~0.2 Hz, `V3_cum` within 0.05 Hz (1.520 vs
1.569). Slice A does not gate anything, but the two independently-drawn populations
tell a consistent story.

**Gate reads `H_3^cum`:** point estimate 1.569 Hz, 2,000-draw cluster-bootstrap 95% CI
**[1.437, 1.687] Hz**, straddling the 1.5625 Hz lattice half-cell.

---

## 5. The gate

```
ROW 1  CI_lo >= 1.5625   -> 1.437 < 1.5625            -> does not fire
ROW 3  CI_hi <  0.5      -> 1.687 nowhere near 0.5    -> does not fire
ROW 2  CI_hi < 1.5625 and CI_lo >= 0.5  -> CI_hi=1.687 >= 1.5625  -> does not fire
ROW 4  residue -- CI straddles 1.5625   -> FIRES
```

Exclusivity held (mechanically, per the report's own row evaluation — not asserted).

**Consequence per spec Sec.5: "Report the interval and escalate. Do not pick a side."**
I am not characterising this as "requirement met" or "requirement demanding" — the CI
covers both. **This is the Architect's call**, per HK-015, on what (if anything) further
narrows it.

---

## 6. Secondary (non-gating) — does the requirement tighten with order?

`D = H_1 - H_3^cum` (paired bootstrap, same cluster draws): **0.347 Hz, CI95
[0.281, 0.462] Hz, p<0.0001.** Positive and clearly separated from zero: **the
requirement DOES tighten with coherent order** on this population. The Architect's own
directional prediction (weakest calibration class, 1.5/4.5) was correct.

**Pure vs. cumulative** (Sec.2.2's confound separator — is the tightening real
frequency-sensitivity or an artefact of the cumulative combination rule inheriting
already-corrupted lower-order terms?):

| | pure | cumulative | pure < cumulative? |
|---|---|---|---|
| order 2 | 1.458 Hz | 1.757 Hz | yes |
| order 3 | 1.145 Hz | 1.569 Hz | yes |

Both pure statistics are narrower than their cumulative counterparts, **and pure
narrows further from order 2 to order 3** (1.458 → 1.145). That is evidence the
tightening is not purely a cumulative-inheritance artefact — a genuine order-dependent
frequency-sensitivity component is present. I am not resolving Sec.2.2's confound
further than that; it is reported per spec, not gated.

---

## 7. Prediction scoring (spec Sec.8, nothing gated on these)

| Prediction | Credence | Outcome |
|---|---|---|
| P(ROW 1) ≈ 25% | | did not fire |
| P(ROW 2) ≈ 45% | | did not fire |
| P(ROW 4, straddle) ≈ 20% | | **fired** |
| P(ROW 3) ≈ 5% | | did not fire |
| P(any ROW 0) ≈ 5% | | none fired |
| `H_3^cum` ∈ 1.2–1.6 Hz (range, 8/15) | | point estimate 1.569 Hz — inside, near the top edge |
| `D = H_1 - H_3^cum` > 0 (directional, 1.5/4.5) | | **confirmed**, p<0.0001 |
| ROW 0e does not fire; alias ~52% | | **confirmed**, edges read 50.6%/51.1% |

The lowest-credence bucket (ROW 4, 20%) is the one that fired — worth flagging for the
calibration record the Architect keeps, same as N3's own ROW 0 fire was flagged against
its 5% bucket.

---

## 8. Methodology note (not a defect, disclosed proactively)

`n4_stats.cluster_bootstrap_lobe` does **not** rebuild Python lists per (variant, df,
draw) the way N3's per-row aggregation pattern would suggest — at 5 variants × 71 df ×
~700 rows × 2,000 draws that is ~500M interpreter-level operations, which I judged
impractical inside the 2h cap. Instead it precomputes one `(n_rows × n_df)` float64
matrix per variant and, per draw, gathers resampled row indices and calls
`np.median(matrix[row_idx], axis=0)` once per variant — numerically identical (same
multiset of values re-medianed either way), verified against a synthetic control before
arming (5 clusters × 10 rows, hand-checked bootstrap CI against the vectorised
function's own output). Total wall time: sign test 184s + Slice A sweep 162s + Slice B
sweep 630s + bootstrap (seconds) ≈ **16.5 minutes**, well under the 25 min estimate and
the 2h cap.

---

## 9. Scope discipline

- DLL SHA256 asserted `6890d84c4bcf2e90...` (full: `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`), shim version 20260042 confirmed — asserted against the pin, not inferred.
- NFR-021: grepped `results/*.json` and `results/*.log` individually. Every row carries
  only `{ts, v0_ber, curves}` — no message text, no callsign-shaped tokens anywhere.
- No `src/`, no Developer session, no DLL rebuild, no capture run — HK-011 not engaged.
- No per-row frequency search — one common `df` per grid point across all rows.
- Rectangular window only.

---

## 10. Next

**This is the Architect's call, not QA's** (HK-015). The gate's own consequence is
explicit: report the interval, escalate, do not pick a side. I have not attempted to
force ROW 1/2/3 by any post-hoc re-reading of this CI, and per HK-026 this data is not
to be re-read to bound anything further — a genuinely new pre-registration would be the
route if narrowing the CI is worth pursuing.

A2 (AC-4 ROW 0) and A3 (re-run D3 emitting slope + SE + p) remain open, still must not
become a round.
