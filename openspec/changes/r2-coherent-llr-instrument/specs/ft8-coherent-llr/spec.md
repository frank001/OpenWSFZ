## ADDED Requirements

### Requirement: Per-candidate coherent multi-symbol LLR formation, diagnostic-only (Phase 1 — not yet implemented)

The native shim SHALL expose a diagnostic entry point (e.g. `ft8_coherent_llr_at`) that, given the cycle's retained PCM (12 kHz, 180 000 samples) and a candidate's *existing, unrefined* grid `(freq_idx, time_idx)` from `ftx_find_candidates()`, returns 174 coherent per-bit LLRs, computed by (1) downconverting the PCM to complex baseband at the candidate's grid frequency with phase retained, reusing `sync_refiner.c`'s existing downconversion rather than reimplementing it; (2) for each of the 58 data symbols, correlating coherently against each of the 8 tone hypotheses — complex accumulation across the symbol, magnitude taken last; (3) forming 1-, 2- and 3-symbol coherent metrics and combining them into per-bit LLRs via max-log over the tone hypotheses consistent with each bit; and (4) normalising to the same scale `ftx_normalize_logl` expects, so the output is drop-in comparable with the existing magnitude-only `log174`. This entry point SHALL NOT call `ft8_refine_candidate` anywhere in its implementation — the candidate position it is given SHALL be used as-is, never refined internally. It SHALL be reachable only from a diagnostic/validation harness — no production decode call site SHALL invoke it, and `ftx_decode_candidate()` SHALL remain byte-for-byte unchanged by this change.

#### Scenario: Coherent LLR export is callable as a standalone diagnostic, at the grid position it is given

- **WHEN** the validation harness calls `ft8_coherent_llr_at` with a cycle's PCM and a candidate's existing grid `(freq_idx, time_idx)`
- **THEN** the function SHALL return 174 coherent LLRs without internally calling `ft8_refine_candidate` or any other position-search routine

#### Scenario: Production decode path is unchanged

- **WHEN** `Ft8LibInterop.DecodeAll` is called on any of the three reference platforms after Phase 1 ships
- **THEN** the returned decode results SHALL be byte-for-byte identical to the pre-change baseline for the same input PCM

---

### Requirement: The pre-registered kill gate on `f_net`, strict order, mutually exclusive rows (Phase 1 — not yet implemented)

Over the P-LIVE Stage 2 population (reference decoded, we did not, candidate present), paired per cluster: `n_in` = clusters with `n_err_grid > 19` and `n_err_coh ≤ 19`; `n_out` = clusters with `n_err_grid ≤ 19` and `n_err_coh > 19`; `f_net = (n_in − n_out) / n_clusters`, cluster-bootstrapped 95% CI by `ts`. The gate SHALL evaluate, in this strict order, first match wins: **ROW 1 (STRONG)** if `CI_lo(f_net) > 15%` ⇒ Phase 2 authorised, expected recall gain ≈ `f_net × 37pp` quoted as an estimate only; **ROW 2 (MATERIAL, NOT SUFFICIENT)** if `CI_lo(f_net) > 5%` and not ROW 1 ⇒ Phase 2 authorised as a product improvement, with an explicit Captain re-decision that the project's stated purpose is not met by this outcome; **ROW 3 (KILL)** if `CI_hi(f_net) < 5%` ⇒ Route B2 is dead in full, no re-read with a better metric; **ROW 4 (residue)** otherwise ⇒ no verdict, report the interval, escalate. A companion secondary statistic `C_ber` (median BER_coh − median BER_grid, signed, cluster-bootstrapped) SHALL be reported alongside `f_net` always, gating nothing, so a null on `f_net` can be distinguished from "coherent LLRs did nothing at all."

#### Scenario: Rows are provably exclusive

- **WHEN** any measured `(CI_lo, CI_hi)` pair for `f_net` is evaluated against the four rows in the stated order
- **THEN** exactly one row SHALL fire — ROW 1 is a subset of ROW 2's own condition and is checked first; ROW 2 requires `CI_lo > 5%` and ROW 3 requires `CI_hi < 5%`, and `CI_lo ≤ CI_hi` makes both firing simultaneously impossible; ROW 4 is the complement of the other three

#### Scenario: ROW 3 fires — Route B2 is dead, no re-read

- **WHEN** `CI_hi(f_net) < 5%`
- **THEN** the report SHALL state Route B2 is dead in full (limb 1 already dead, limb 2 now also dead) and SHALL NOT be re-evaluated later against a different metric or threshold (standing prohibition)

---

### Requirement: Candidate identity between the grid and coherent extractions (Phase 1 — not yet implemented)

For every row in the gate's population, the grid-position LLRs and the coherent LLRs SHALL be computed at the identical `(freq_idx, time_idx)` — asserted per row, not merely assumed. A candidate-position mismatch between the two extractions would inflate BER toward 50% for one side and could fake a null result.

#### Scenario: Candidate identity holds for every measured row

- **WHEN** the gate harness measures a row's `ber_grid` and `ber_coh`
- **THEN** both extractions SHALL have been called with the same `(freq_idx, time_idx)` for that row, and this SHALL be asserted (not merely assumed) at 100% of measured rows

---

### Requirement: Population re-derivation reports cluster counts (Phase 0 — shipped this change)

The measurement harness SHALL re-derive the P-LIVE Stage 2 population (reference decoded, we did not, same `ts`) using the existing `plive_population.build_p_live_population` builder, without reimplementing population construction, and SHALL report cluster counts (distinct `ts`) alongside row counts at every population-size checkpoint — never row counts alone. The harness SHALL NOT use any population helper's `limit=`-style truncation argument, since at least one such helper in this codebase's history (`compute_matched_hit_control(cycles, limit=N)`) truncates in file order rather than sampling.

#### Scenario: Dry count is reported with clusters, before any DLL call

- **WHEN** the harness re-derives the P-LIVE population for `PRIMARY_CORPUS`
- **THEN** it SHALL report both `n_rows` and `n_clusters` before making any extraction call, and this dry count SHALL match the already-published Stage 2 figure (`n_rows=18012`, `n_clusters=4113`) exactly

---

### Requirement: Mandatory two-sided sign unit test before any BER is trusted (Phase 0 — shipped this change)

Before the harness's `ber_grid`/`n_err_grid` output is used for any downstream measurement, a two-sided sign unit test SHALL be run and SHALL PASS on both of its sub-checks: a SIGNAL sub-check (a known-good codeword's extraction SHALL report a bit-error count far below chance) and a NOISE sub-check (pure-noise extraction against an arbitrary fixed truth SHALL report a bit-error count statistically consistent with chance, `~87/174`). Both sub-checks are required because neither alone certifies the sign convention: the NOISE sub-check alone cannot distinguish a correct hard-decision rule from a uniformly sign-inverted one (both average to chance on true noise), and the SIGNAL sub-check alone cannot distinguish "correct" from "always reports errors" without the chance-level reference the NOISE sub-check provides. A FAIL on either sub-check SHALL stop the harness before any ROW 0d or downstream measurement runs (HK-025).

#### Scenario: Both sub-checks pass

- **WHEN** the sign unit test is run against the current build
- **THEN** the SIGNAL sub-check's gating statistic SHALL fall at or below its pre-registered bar and the NOISE sub-check's mean and every per-trial value SHALL fall within their pre-registered two-sided bands, and the harness SHALL proceed to ROW 0d only if both hold

#### Scenario: Either sub-check fails

- **WHEN** the SIGNAL sub-check's gating statistic exceeds its bar, or the NOISE sub-check's mean or any per-trial value falls outside its band
- **THEN** the harness SHALL report FAIL, SHALL NOT proceed to ROW 0d, and SHALL NOT report any `ber_grid` number as trustworthy until resolved

---

### Requirement: `ber_grid` reproduces the already-published reference measurement (Phase 0 — shipped this change)

A fresh, independent re-derivation of the P-LIVE Stage 2 population's median `ber_grid`, measured at the same corrected anchor offset Stage 2 used, SHALL reproduce Stage 2's own already-published median `ber_grid` (31.03%) within 1.0 percentage point. This SHALL be evaluated only after the sign unit test above has passed, and SHALL run against the full re-derived population (not a sample), since Stage 2's own full-population runtime (~9-10 minutes) is well within any reasonable session budget.

#### Scenario: Reproduction passes

- **WHEN** the harness measures the full P-LIVE population's median `ber_grid` at the corrected anchor
- **THEN** the absolute difference from Stage 2's own published median SHALL be at or below 1.0 percentage point, and both the fresh and the cited value SHALL be reported (not only the delta)

#### Scenario: Reproduction fails

- **WHEN** the absolute difference exceeds 1.0 percentage point
- **THEN** the harness SHALL report FAIL, SHALL NOT be treated as validated, and this change SHALL NOT proceed to propose Phase 1 native work on top of an unreproduced harness
