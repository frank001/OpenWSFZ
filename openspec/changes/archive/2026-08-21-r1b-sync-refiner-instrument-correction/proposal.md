**User-facing:** no

## Why

R1 (`feat/r1-sync-refiner-instrument-validation`, `af2f466`) was accepted by the Captain
2026-08-14 20:28Z with the AC-3 time-dimension null-test FAIL carried forward as an open
**instrument** question, not a decode-path defect (`qa/rr-study/2026-08-14-2028-architect-to-qa-
r1-ruling-and-r1b-instrument-scope.md`). The ruling found two things wrong with R1's own gates,
not with the refiner: AC-4 (SNR monotonicity) was **void by construction** — at n=400/stratum the
gate had a ~99.9% chance of FAILing a flawless refiner (HK-021(k), the Architect's own admission);
and AC-3's time sub-check FAILed against a null whose one load-bearing assumption (Stage A+B and
Stage C search independently) is known false, concentrated in exactly the two single-path extreme
bins that drive the χ². The FAIL's one part that survives any null — a 102:6 imbalance between
mirror-image extreme bins — cannot currently be investigated further because `ft8_refine_candidate`
exports only the *sum* `Δt = dt_coarse + dt_fine`; the two stage selections
(`best_dt_samp`, `best_fine_samp`) that the entire hypothesis is stated in terms of are not
recoverable from any committed artefact. R2 (wiring refinement into the decode path) stays blocked
on this gap, per R-4 of the ruling — not on a defect, but because a null result from R2 would be
uninterpretable while the instrument that would validate the refiner first cannot itself be tested.

This change fixes the instrument: export the missing decomposition, replace the two broken gates
with mechanically sound successors, and answer the question with data already sitting on disk.

## What Changes

- **D1 — export the (coarse, fine) time decomposition.** `ft8_refine_candidate` gains two new
  out-parameters (`best_dt_samp` at the Stage A+B coarse rate, `best_fine_samp` at the Stage C fine
  rate); `best_df` is already exported via `out_delta_freq_hz` and needs no new parameter. Shim
  bump to **20260041**. Diagnostic-only, exactly as R1 — no production call site.
- **D2 — replace AC-3's time sub-check** with a shape-free reflection-symmetry test (the observed
  `Δt` distribution against its own negation — no grid model, no independence assumption, no
  HK-026 exposure) plus mechanically computed per-stage marginals (`best_dt_samp` and
  `best_fine_samp` each tested for uniformity against their own, now-separately-identifiable,
  discrete null) over the full `n = 1,200` noise population.
- **D3 — stratify the existing noise population** by `coarse_time_offset_s` and `coarse_freq_hz`
  (both already recorded in `run_a.json`/`run_b.json`/`run_c.json` — **no new capture run**). Done
  first, ahead of D1/D2/D4, because it reshapes what those need to check. See Impact for the
  preliminary result already obtained from committed data.
- **D4 — retire AC-4 and replace it, time-dimension only.** Per R-1 of the ruling, the frequency
  dimension is floored by the 0.5 Hz search grid and cannot show a monotone trend in principle
  (unidentifiable, HK-021) — a frequency monotonicity gate is **not** re-pre-registered in any form.
  The time dimension does carry genuine SNR response (1.515 ms at −20 dB → 1.109 ms at +5 dB,
  saturating near −10 dB) and gets a new ordered-alternative trend test with a tolerance derived
  from the stratum sample size, replacing the old any-single-step-fails rule.
- **D5 — carry the frequency-floor finding into R2's design inputs.** No new artefact; recorded as
  a design constraint (design.md) for whoever proposes R2: the refiner has no sub-0.5 Hz frequency
  capability, full stop, and R2 must not assume one.
- Three **non-gating** diagnostic hypotheses (argmax tie-break convention, coarse-filter aliasing,
  genuine selection bias) are named as candidate discriminators to run *after* D1 lands, explicitly
  barred from gating any AC per the Architect's own DIRECTIONAL calibration (1.5/3.5, the weakest
  class) — see design.md.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ft8-sync-refiner`: the AC-3 (noise-only null) and AC-4 (SNR monotonicity) requirements are
  replaced; a new requirement is added for the D1 decomposition export and a new requirement for
  the D3 stratification report. **Sequencing note** (see Impact): this capability does not yet
  exist in `openspec/specs/` — it was only ever `ADDED` by R1
  (`openspec/changes/r1-sync-refiner-instrument-validation/`), which is implemented and
  Captain-accepted but not yet merged/archived. This change's delta is written against R1's
  requirement text as committed on `feat/r1-sync-refiner-instrument-validation`, not against an
  archived baseline — R1 should archive before this change does (see design.md Open Questions).
- `ft8lib-interop`: the ABI self-test's expected shim constant advances from R1's `20260040` to
  `20260041`; the diagnostic `RefineCandidate`/`ft8_refine_candidate` requirement is modified to add
  the two new out-parameters.

## Impact

- **Affected code**: `native/ft8_lib_vendor/refine/sync_refiner.c` (two new out-parameters on
  `ft8_refine_candidate`, no change to the search/correlation logic itself — this change instruments
  the existing algorithm, it does not alter it); `ft8_shim.h`/`ft8_shim.c` (export signature);
  `src/OpenWSFZ.Ft8/Interop/` (P/Invoke + `IFt8NativeInterop` + all 8 test-double implementations,
  same pattern R1 already established); `qa/rr-study/r1-sync-refiner/` (harness gains the two new
  fields in its results schema plus D2's symmetry/marginal evaluators and D3's stratification
  report; D4's evaluator replaces the AC-4 function).
- **Preliminary D3 result, from committed data, no new run** (QA, this session, against
  `qa/rr-study/r1-sync-refiner/results/2026-08-14/run_a.json`'s 1,200 noise trials — informal,
  not a gated finding, recorded per HK-018 because it reshapes D2's design): the mean `Δt` is
  **−5.42 ms**, median **−5.00 ms** (suspiciously close to exactly one 5 ms coarse-grid step); a
  sign test on non-zero trials rejects symmetry (637 negative vs. 555 positive, `p = 0.019`); a
  two-sample KS test of the sample against its own negation — the literal statistic D2 formalises —
  rejects symmetry at `p = 4.9×10⁻⁷`. Stratifying by decile of `coarse_time_offset_s`'s position
  within its 5 ms coarse cell shows the mean `Δt` **negative in every decile** (range −1.96 ms to
  −14.06 ms) with negligible linear correlation to cell position (`r = −0.067`) or to
  `coarse_freq_hz` (`r = −0.007`). **Reading**: the bias is not localised to a particular injected
  time or frequency position — it is pervasive across the search space, which weighs against a
  boundary/edge artefact (already independently refuted in the ruling §1) and is consistent with
  either of the two leading non-gating hypotheses (argmax tie-break, coarse-filter aliasing), not
  with a position-dependent cause. This is exploratory, run informally on data already on disk, and
  does not substitute for D1's proper per-stage export or D2's mechanically pre-registered test.
- **Not affected**: `ftx_decode_candidate()`, the production decode path, and every existing
  `ft8-decoder` scenario — this change touches only the diagnostic export and its validation
  harness, same boundary R1 established.
- **Licence**: no new algorithmic code — D1 is instrumentation of the existing, already
  clean-room-written `sync_refiner.c`. Standing licence policy (Captain's ruling 2026-08-11)
  continues to apply unchanged.
- ⚠️ **macOS `osx-arm64/libft8.dylib` is now stale across three consecutive shim versions**
  (unrebuilt through R0's `20260039`, R1's `20260040`, and this change's `20260041`) — non-blocking,
  CI rebuilds from source, but named explicitly per the ruling's own instruction not to inherit the
  gap silently a third time.
- **Downstream**: R2 remains blocked until D2's symmetry test and per-stage marginals report a
  result. A clean symmetry test closes R1b quickly; an asymmetric one with per-stage marginals in
  hand localises the mechanism to a specific stage instead of an unobservable interaction — either
  way, R2 gets a testable instrument it does not have today.
