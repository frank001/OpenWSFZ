## Context

R1 built a diagnostic-only per-candidate sync refiner (`ft8_refine_candidate`, shim `20260040`) and
validated it against a synthetic oracle with six mechanical acceptance criteria. AC-1/AC-2/AC-5/AC-6
passed cleanly and are not touched by this change. AC-3 (noise-only null) and AC-4 (SNR
monotonicity) both failed, and the Captain's ruling on R1
(`qa/rr-study/2026-08-14-2028-architect-to-qa-r1-ruling-and-r1b-instrument-scope.md`) found the
failures were in the *gates*, not (necessarily) the refiner:

- AC-4 had a ~99.9% chance of FAILing a flawless refiner at n=400/stratum against a frequency truth
  that is flat *by construction* (the 0.5 Hz search grid floors RMS(Δf) regardless of SNR) — void by
  construction, HK-021(k).
- AC-3's time sub-check rejected a convolution null whose independence assumption (Stage A+B and
  Stage C search independently) is known false, and the rejection is concentrated exactly in the two
  single-path extreme bins where that false assumption does the most damage. What survives any null
  is the raw asymmetry: 102 observed vs. 32.8 expected in the most-negative bin, 6 vs. 32.8 in the
  most-positive.

Neither gate can currently be re-examined properly because `ft8_refine_candidate` exports only the
*sum* of two search stages (`out_delta_time_s = dt_coarse + dt_fine`); the two stage selections
(`best_dt_samp` from the ±60 ms/5 ms coarse search, `best_fine_samp` from the ±10 ms/0.5 ms fine
search) are computed in `sync_refiner.c` but never leave the function. This change is narrowly
scoped to fixing that instrument gap — export the decomposition, replace the two broken gates with
mechanically sound successors, and use data already on disk (the 1,200-trial noise population in
`run_a.json`/`run_b.json`/`run_c.json`) wherever it answers the question without a new run.

This is **not** a decode-path change and **not** a re-tuning of the refiner's search parameters or
correlation method — `sync_refiner.c`'s actual algorithm (downconvert → coherent Costas correlation
→ joint coarse time×frequency search → fine time search) is untouched by this change. This is
instrumentation and gate replacement only.

## Goals / Non-Goals

**Goals:**
- Make the (coarse, fine) time-search decomposition observable (D1), so AC-3's original
  "each stage individually looks uniform" claim — asserted by eye in R1's report, never computed
  over the full population (HK-021 — cannot support a conclusion as stated) — can finally be tested.
- Replace AC-3's time sub-check with a test that survives HK-026 and does not depend on the false
  independence assumption R1's own convolution null relied on (D2).
- Answer, from data already committed, whether the observed asymmetry is localised to a particular
  injected time/frequency position (an edge/boundary artefact) or pervasive across the search space
  (D3) — before spending any budget on D1/D2's implementation.
- Retire the frequency-monotonicity half of AC-4 permanently (it is unidentifiable per R-1) and
  replace the time half with a trend test whose power is derived from the data actually available,
  not from treating six RMS numbers as noiseless (D4).
- Leave a written, explicit design input for R2: the refiner's frequency resolution floor is 0.5 Hz,
  and there is no fine-frequency stage in the code to assume otherwise (D5).

**Non-Goals:**
- Not adding a fine-frequency stage to the refiner. R-1 of the ruling is explicit: whether 0.5 Hz
  is sufficient for R2 or whether a fine-frequency stage is needed is an R2 design question, to be
  answered with its own pre-registration, not silently resolved here.
- Not re-pre-registering any form of frequency monotonicity gate — R-1 established it is
  unidentifiable while the 0.5 Hz grid floors RMS(Δf) flat across the full SNR range tested.
- Not determining which of H-A (argmax tie-break convention), H-B (coarse-filter aliasing near
  Nyquist), or H-C (genuine selection-bias interaction) is the mechanism. All three are DIRECTIONAL
  hypotheses from the Architect, whose own calibration record on DIRECTIONAL predictions is 1.5/3.5
  — the weakest class recorded. This change makes them testable (D1) and offers cheap discriminators
  (below) but explicitly does not let any of them gate an AC.
- Not touching AC-1, AC-2, AC-5, or AC-6 — all four passed and are accepted by the ruling without
  qualification.
- Not archiving R1 — that is a separate, Captain-level action; see Open Questions for the
  sequencing dependency this creates.

## Decisions

**D1 — `ft8_refine_candidate` gains two new out-parameters; the existing signature's meaning is
unchanged.**

```c
int ft8_refine_candidate(
    const float* pcm, int pcm_len,
    int coarse_freq_hz, float coarse_time_offset_s,
    float* out_delta_freq_hz,
    float* out_delta_time_s,
    float* out_sync_score,
    int*   out_coarse_dt_samp,   /* NEW: best_dt_samp, Stage A+B, @200 Hz, range [-12, 12] */
    int*   out_fine_dt_samp);    /* NEW: best_fine_samp, Stage C, @2000 Hz, range [-20, 20] */
```

`out_delta_freq_hz` continues to carry `best_df` unchanged (already the full Stage A+B frequency
selection — no second frequency parameter is needed, since there is no fine-frequency stage, D5).
`out_delta_time_s` continues to carry the sum, so every existing AC-1/AC-2/AC-5/AC-6 evaluator code
path is unaffected by this change — those two new pointers are additive, not a replacement.
Alternative considered: a struct return instead of two more scalar out-params, matching the existing
five-scalar convention more closely for consistency with the rest of this shim's ABI (`ft8_shim.h`
uses flat structs like `FT8Result`, not nested ones, for exactly this reason) but the two new values
are `int`, not `float`, and appending two more scalar pointers keeps the change to a pure signature
extension rather than a new type. Existing callers that don't pass the two new pointers would need
updating regardless — there is no NULL-tolerant variant, matching how the existing five parameters
are already treated as mandatory (`if (!pcm || !out_delta_freq_hz || ...) return -1;`), extended to
require the two new pointers too. Shim bump to **20260041**. Diagnostic-only, no production call
site — identical boundary to R1 (Impact, proposal.md).

**D2 — AC-3's time sub-check becomes three reflection-symmetry tests: combined, coarse-stage-only,
fine-stage-only.**

The reflection-symmetry test (ruling §4.3): compare an observed sample against its own negation via
a two-sample Kolmogorov–Smirnov test. This needs no grid model and no independence assumption
between search stages — it only requires that the search grid itself is symmetric about zero, which
is true by inspection of `sync_refiner.c` for both stages (`REFINE_COARSE_TIME_HALF_SAMPLES = 12`
searched `[-12, 12]` inclusive; `REFINE_FINE_TIME_HALF_MS = 10.0`, step `0.5`, giving `[-20, 20]`
inclusive at the fine rate — both ranges are exactly symmetric with a centre point at zero, verified
directly against the constants, not assumed).

Drafted as the evaluating code first, per HK-021:

```python
def reflection_symmetry_test(x: np.ndarray, alpha: float) -> dict:
    """x: the per-trial values for ONE dimension (combined dt, coarse-only, or fine-only)."""
    if np.std(x) == 0:
        return {"pass": None, "instrument_failure": "degenerate: zero variance, cannot test"}
    stat, p = stats.ks_2samp(x, -x)
    return {"pass": bool(p >= alpha), "ks_statistic": float(stat), "p_value": float(p)}
```

Applied three times over the `n = 1,200` noise population — `Δt` combined (already recorded),
`best_dt_samp` (Stage A+B, newly exported by D1), `best_fine_samp` (Stage C, newly exported by D1)
— with a Bonferroni-corrected per-test `α = 0.01 / 3 ≈ 0.00333` so the family-wise false-positive
rate across the three sub-tests stays at the pre-registered `0.01` (matching AC-3's original
significance level; AC-3's already-accepted frequency sub-check at `α = 0.01` is untouched by this
change). **ROW 0**: if any sub-population is degenerate (zero variance — cannot happen at this `n`
for a healthy instrument, but must be named), that sub-test reports `instrument_failure`, not a
silent PASS. **Overall verdict**: PASS only if all three sub-tests PASS; a FAIL names which
stage(s) — the report becomes directly informative about whether the asymmetry lives in Stage A+B,
Stage C, or both, which none of R1's AC-3 evidence could show.

*HK-025 self-check (classification, per the ruling's explicit instruction to run this on every gate
in this document, including this one):* does a FAIL here happen only when the refiner is genuinely
asymmetric (an estimate of what the gate names), or would it fire regardless of the world state? The
search grids for both stages are exactly symmetric about zero by construction (verified above) —
under a correctly functioning, unbiased correlator, `Δt` (and each stage's own selection) has no
principled reason to prefer one sign over the other on pure noise, so a symmetric null is a real,
achievable state, not one the instrument forecloses the way the 0.5 Hz grid forecloses a flat
frequency response regardless of correlator quality. This is a VALIDITY check: it distinguishes two
real states of the world (a fair selection process vs. a biased one) rather than returning the same
row in both. **Passes HK-025; not refused.**

**D3 — stratify the existing noise population by `coarse_time_offset_s` and `coarse_freq_hz`; report
only, no gate.**

Both fields are already recorded per noise trial (verified directly against `run_a.json`'s
`noise_results[*]` keys — ruling §1). This requires no new capture run, which is why the ruling asks
for it first: it can reshape the rest of the plan before any implementation budget is spent. QA ran
this informally against `run_a.json` while drafting this proposal (see proposal.md Impact for the
full numbers): the mean `Δt` is negative in every decile of `coarse_time_offset_s`'s position within
its 5 ms coarse cell (range −1.96 ms to −14.06 ms), with negligible correlation to either
`coarse_time_offset_s` (`r = −0.067` for cell-position, `r = −0.033` for the raw offset) or
`coarse_freq_hz` (`r = −0.007`). **This rules out a position-dependent cause** (an edge/boundary
artefact tied to a specific injected offset — already independently refuted in the ruling §1 by a
direct read of `downconvert_decimate`'s zero-padding and the coarse FIR's ~5 ms half-width) and is
consistent with a pervasive, position-independent mechanism — which is what both surviving
hypotheses (H-A, H-B) predict, and inconsistent with nothing currently on the table. Because this
already ran on committed data, D3's remaining scope is narrow: promote the informal analysis above
into a mechanically reported, reproducible artefact — a `stratify_noise.py` script under
`qa/rr-study/r1-sync-refiner/` that computes the same correlations and decile table from any results
file (not hand-run in a scratch shell), committed alongside its output for `run_a.json` specifically,
so the number in this proposal is independently reproducible rather than asserted from a session
transcript (HK-018/HK-022).

**D4 — AC-4 retired for frequency (permanently, per R-1); replaced for time with a Spearman
rank-correlation trend test over the full per-trial population, not the six collapsed RMS numbers.**

R1's AC-4 computed one RMS number per SNR stratum (n=400 each) and failed if any adjacent pair
increased — a rule with essentially no tolerance for the sampling noise inherent in collapsing 400
observations to one summary statistic per stratum (ruling §3: relative SE ≈ 3.5% at that n, and the
observed spread was ±3%, i.e. inside noise). The successor uses every trial directly instead of
collapsing first:

```python
def snr_trend_test(snr_db: np.ndarray, abs_time_error_s: np.ndarray, alpha: float) -> dict:
    """One row per trial across ALL six strata pooled (n ~= 2,400), not one row per stratum."""
    rho, p = stats.spearmanr(snr_db, abs_time_error_s)
    # one-sided: SNR increasing should correlate with error decreasing => rho < 0
    p_one_sided = p / 2 if rho < 0 else 1.0 - p / 2
    return {"pass": bool(rho < 0 and p_one_sided < alpha), "rho": float(rho), "p_value": float(p_one_sided)}
```

Pre-registered `α = 0.01` (matching AC-3's convention). **ROW 0**: any SNR stratum with `n < 200`
(the standing power floor, spec's pre-existing "Validation population" requirement, untouched by
this change) is named as underpowered and excluded from the pooled test rather than silently diluting
it. Frequency is not tested at all under this requirement — R-1 established `RMS(Δf)` is flat by
construction, so a "does error improve with SNR" question is unidentifiable for that dimension; it
continues to be *reported* per stratum (unchanged from R1, informational only) but is not part of
this pass/fail decision, and no successor frequency-monotonicity gate is registered under any name.

*HK-025 self-check:* does a FAIL happen only when the time dimension genuinely fails to improve with
SNR? Unlike frequency, time is only *partly* floored — R1's own measurement shows real SNR-dependent
shrinkage (1.515 ms at −20 dB → 1.109 ms at +5 dB, saturating near −10 dB), i.e. the two branches
(genuine improvement vs. none) are both physically realisable and were in fact already observed to
differ in R1's data. This is evaluating a real matched-filter-theory prediction (error should shrink
as SNR rises, for a coherent correlator that is actually exploiting phase), not an artefact of a
fixed grid — **passes HK-025; not refused.** One honest caveat, recorded rather than hidden: with
saturation setting in by −10 dB, the *high-SNR half* of the ladder is closer to its own floor and a
real, correctly-functioning refiner could show a weaker trend there than at the low-SNR end — the
pooled Spearman test is sensitive to the whole ladder's average trend, not each adjacent pair, which
is precisely why it replaces the old any-single-step rule rather than tightening it.

**D5 — no new artefact; the frequency-floor finding is recorded here as an explicit R2 design
input.**

**The refiner has no sub-0.5 Hz frequency capability.** `REFINE_FREQ_STEP_HZ = 0.5f` and there is no
fine-frequency stage anywhere in `sync_refiner.c` — `best_df` is assigned only in the Stage A+B
joint grid search and passed straight through to `out_delta_freq_hz`; Stage C searches time only.
0.5 Hz is 6.25× finer than the 3.125 Hz waterfall lattice R2 would replace and may well be
sufficient for D-001 — but that is now an explicit open design question for whoever proposes R2, not
an established property to inherit silently. This change adds nothing to the code to address it;
it is scope boundary information only.

**Non-gating diagnostic hypotheses (carried from the ruling §5, unchanged, offered as cheap
discriminators to run manually after D1 lands — not part of this change's own task list, and not
gating any AC in this change or any future one under this name):**
- **H-A — argmax tie/plateau convention.** Both `costas_coherent_sum` search loops use strict `>`
  scanning from the most-negative index (verified directly: `sync_refiner.c` lines computing
  `best_score_ab`/`best_score_c`, both `if (mag > best_score) { ... }` inside loops starting at
  `-REFINE_COARSE_TIME_HALF_SAMPLES`/`-fine_half_samp`). *Discriminator:* flip to `>=` and see
  whether the pile-up moves to the opposite extreme bin.
- **H-B — coarse-filter aliasing.** `REFINE_LP_CUTOFF_COARSE_HZ = 90.0f` against a 100 Hz Nyquist at
  the 200 Hz coarse rate. *Discriminator:* lower the cutoff toward ~60 Hz (still above the 50 Hz tone
  span) and/or raise the tap count; if the asymmetry shrinks, it is the filter.
- **H-C — genuine selection-bias interaction**, as R1's report concluded. Reach this only after H-A
  and H-B are excluded.

## Risks / Trade-offs

- **[Risk] R1 is not yet archived** (still `openspec/changes/r1-sync-refiner-instrument-validation/`,
  implemented on `feat/r1-sync-refiner-instrument-validation`, not merged to `main`) — so the
  `ft8-sync-refiner` and modified `ft8lib-interop` requirements this change's spec deltas are written
  against do not yet exist in `openspec/specs/`. → **Mitigation:** documented explicitly in
  proposal.md Impact and Open Questions below; this change's `MODIFIED` deltas are written against
  R1's requirement text as committed (`openspec/changes/r1-sync-refiner-instrument-validation/specs/
  ft8-sync-refiner/spec.md`), which the Captain's ruling accepted as-is with no revision — the text
  should match whatever R1's own archive eventually produces. Recommended sequencing: archive R1
  before archiving this change.
- **[Risk] Multiple-comparisons inflation from running three reflection-symmetry sub-tests (D2)** →
  **Mitigation:** Bonferroni correction applied explicitly (`α = 0.01/3` per sub-test), stated as
  code, not asserted in prose.
- **[Risk] D4's trend test, like AC-4 before it, could still be underpowered if collapsed to too few
  effective points** (the exact failure mode that made the original AC-4 unreliable at
  n=400/stratum) → **Mitigation:** D4 pools all ~2,400 per-trial observations instead of six
  stratum-level summaries, and the underpowered-stratum floor (`n ≥ 200`) is checked before pooling,
  not after.
- **[Risk] D4's pooled test can be significant with a small effect** if `n` is large — a real concern
  in principle, but the effect this test targets (0.4 ms difference in RMS between the extreme SNR
  strata, already measured in R1) is not small relative to typical `Δt` noise, so this is recorded as
  a known trade-off of any large-`n` significance test, not treated as invalidating the choice.
- **[Risk] D1's two new out-parameters are a breaking ABI change to a function only ever called by
  test code and the validation harness** (no external consumers) → low actual risk, but every caller
  site must be updated in the same change: `Ft8LibInterop.RefineCandidate`, `IFt8NativeInterop`, all
  8 existing test-double implementations, `refiner_ctypes.py`, `run_harness.py`. Named explicitly in
  tasks.md so none is missed (R1's own task 2.1 already establishes the "8 existing implementations"
  count to check against).
- **[Trade-off] This change may not resolve D-001's mechanism.** If D2's per-stage marginals come
  back symmetric individually but the combined sum is not (or vice versa), that is still useful
  localisation, but the non-gating H-A/H-B/H-C hypotheses would then need their own follow-up
  session — explicitly out of this change's scope (Non-Goals) and not committed to as a deliverable
  here.

## Migration Plan

No runtime migration — D1's new export remains diagnostic-only with no production call site, same
as R1. Deployment: merge to `main` after R1; `FT8_SHIM_VERSION`/`ExpectedShimVersion` advances to
`20260041`; all three platform binaries rebuilt (macOS remains stale pending toolchain access, named
in proposal.md Impact — CI rebuilds from source regardless, so this is non-blocking exactly as it was
for R0 and R1). Rollback is a plain `git revert` of this change's commit(s); R1's `20260040` binary
and any already-published result stay pinned to their own SHA regardless. D2/D4's evaluator changes
are QA-tooling only (`qa/rr-study/r1-sync-refiner/evaluate_acs.py` and new `stratify_noise.py`) —
reverting them has zero effect on any shipped binary.

## Open Questions

1. **Sequencing against R1's own archive.** This change's spec deltas are written against R1's
   requirement text as it exists on `feat/r1-sync-refiner-instrument-validation` today, since R1 has
   not merged/archived. Left to the Captain: archive R1 first (recommended — keeps the
   `openspec/specs/` baseline this change's `MODIFIED` deltas assume actually true at archive time),
   or archive both together. Not resolved here; flagged so it is not lost.
2. **Whether D2's per-stage marginals should also be plotted/tabulated by SNR-adjacent structure**
   (i.e. does the noise population's `coarse_freq_hz`/`coarse_time_offset_s` spread interact with
   which stage shows the asymmetry) — D3 already checks this for the combined `Δt`; whether it's
   worth re-running per-stage once D1 lands is left to whoever implements this change, informed by
   what D2's marginals actually show.
3. **`stratify_noise.py`'s placement and whether it becomes a permanent harness component** (run
   routinely alongside `evaluate_acs.py`) or a one-off analysis script — left to the Developer
   session; no behavioural requirement depends on the answer.
