**User-facing:** no

## Why

D-001 (weak-signal recovery deficit against WSJT-X) has converged on an architectural
diagnosis: our extraction reads symbols non-coherently, magnitude-only, at a single
grid position (`3.125 Hz / 0.08 s`), while WSJT-X forms per-candidate coherent
multi-symbol bit metrics from a phase-retaining complex-baseband front end. Route B2
(per-candidate complex-baseband front end) was authorised by the Product Owner
2026-08-19 as the project's one active route, with the explicit stakes that without
D-001 closed "this project is dead... a nice exercise in coding/testing/statistics, but
nothing more."

Route B2 has two limbs, and the evidence on each is asymmetric. **Limb 1 (candidate
position refinement, `ft8_refine_candidate`) is dead three times over**: `M4` found it
does not locate real signals (`rho_conc` = −0.0241); `N1` found refining the extraction
position does not move BER across the correction threshold (limb 1 DEAD); P-LIVE Stage
2 found refinement *harms* the miss population at scale (`d_ber` = −3.45pp, CI95
[−3.45, −2.87]pp, p = 0.0000, 3,916 clusters). **Limb 2 (coherent multi-symbol LLR
formation) is not built and has never been measured** — Route B2's entire remaining
value rests on it.

Building limb 2's production integration (weeks of native work, a runtime flag, an A/B
corpus replay, a false-positive gate) before knowing whether coherent LLRs move the
needle at all would risk the same mistake R1 was designed to avoid for the refiner: an
unvalidated, expensive change whose null result is uninterpretable. **This change is
Phase 1 of a phased plan** (`qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-
phase1-coherent-llr-kill-gate.md`): a single new diagnostic-only native export,
`ft8_coherent_llr_at()`, that forms coherent LLRs **at the existing grid position** (no
dependence on the dead-three-times refiner), gated against a pre-registered kill gate
(`f_net`) on the P-LIVE Stage 2 population before any production wiring is proposed.

**This change currently ships Phase 0 only** (QA's own item per the 2026-08-20 16:13Z
ordering ruling): the OpenSpec artefacts, the measurement harness, population
re-derivation, and two validity checks (ROW 0c/0d) run against the *current* build —
`ft8_coherent_llr_at` does not exist yet and nothing here builds it. Phase 1 (the
native export itself, run against the §3 gate below) requires a Captain-opened
Developer session (HK-011) and is `tasks.md` §1-2/§4, left unchecked.

## What Changes

- **(Phase 1, not yet implemented — blocked on a Developer session, HK-011)** Add a
  new native, diagnostic-only export `ft8_coherent_llr_at(pcm, num_samples,
  cand_freq_idx, cand_time_idx, out_log174, out_diag)` that, given a candidate's
  *existing, unrefined* grid position, downconverts to complex baseband (reusing
  `sync_refiner.c`'s existing, already-reviewed downconversion — not
  reimplementing it), coherently correlates against each of the 8 tone hypotheses per
  data symbol (complex accumulation across the symbol, magnitude last), forms 1-, 2-
  and 3-symbol coherent metrics, and produces 174 per-bit LLRs normalised to the same
  scale `ftx_normalize_logl` expects — drop-in comparable with the existing
  magnitude-only `log174`. `ftx_decode_candidate()` and all production decode
  behaviour remain byte-for-byte unchanged — **BREAKING: none**.
- **(Phase 0, shipped this change)** Add the validation harness
  (`qa/rr-study/r2-coherent-llr-instrument/`) that re-derives the P-LIVE Stage 2
  population (`plive_population.build_p_live_population`, reused verbatim — HK-018),
  measures `ber_grid`/`n_err_grid` for every row using the *existing*
  `ft8_extract_llrs_at` export at Stage 2's own corrected anchor (`+0.65s`), and
  passes two validity checks: a mandatory sign unit test (ROW 0c) and a reproduction
  of Stage 2's own already-published median `ber_grid` = 31.03% within 1.0pp (ROW 0d).
  This harness is the one Phase 1 extends — once `ft8_coherent_llr_at` exists, the
  same per-row loop gains a second extraction call and computes `f_net`/`C_ber`
  per the §3 gate below.
- **(Phase 1, not yet implemented)** Advance `FT8_SHIM_VERSION` /
  `Ft8LibInterop.ExpectedShimVersion` and add the corresponding P/Invoke binding
  (`Ft8LibInterop.CoherentLlrAt`), matching the existing `RefineCandidate`/
  `ExtractLlrsAt` diagnostic-export pattern.

## Capabilities

### New Capabilities
- `ft8-coherent-llr`: the per-candidate coherent multi-symbol LLR-formation stage
  (Phase 1, native, diagnostic-only) and the pre-registered kill gate (`f_net`,
  `C_ber`) that decides whether it is worth wiring into production (Phase 2+). This
  change's own scope (Phase 0) covers only the gate's measurement harness and two
  validity checks against the *existing* extraction; the native stage itself is
  specified here but not yet built.

### Modified Capabilities
- `ft8lib-interop`: **(Phase 1, not yet implemented)** the ABI self-test's expected
  shim constant will advance from `20260042`; a new diagnostic P/Invoke entry point
  (`ft8_coherent_llr_at`) will be added alongside the existing `RefineCandidate`/
  `ExtractLlrsAt` diagnostic surface, with no change to `DecodeAll`,
  `GetLastPassCounts`, or `SetDecodeParams`. Not touched by this change's Phase 0
  scope — the harness shipped now calls only the pre-existing `ft8_extract_llrs_at`.

## Impact

- **Affected code (Phase 1 only, not yet touched):** `native/ft8_lib_vendor/` gains
  the coherent-LLR export's C source, reusing `refine/sync_refiner.c`'s existing
  downconversion; `ft8_shim.c`/`ft8_shim.h` gain the new export; `src/OpenWSFZ.Ft8/
  Interop/` gains the corresponding P/Invoke binding; all three platform binaries
  are rebuilt.
- **Affected tooling (this change, Phase 0):** new directory
  `qa/rr-study/r2-coherent-llr-instrument/` (population re-derivation, ROW 0c/0d,
  the future gate harness). Depends on, and reuses without modification,
  `qa/rr-study/p-live-population/plive_population.py`,
  `qa/rr-study/n1-extract-llrs-at-position/extract_llrs_ctypes.py`, and
  `qa/rr-study/p-live-population/run_stage1.py`'s `WavCache`/DLL-pin constants
  (HK-018 — none of this is reimplemented).
- **Not affected:** `ftx_decode_candidate()`, the production decode path, every
  existing `ft8-decoder`/`ft8lib-interop` scenario, and (this change's own scope)
  every `ft8-sync-refiner` scenario from R1 — Phase 1 explicitly does not call
  `ft8_refine_candidate` (design.md D1: limb 2 must not inherit limb 1's
  three-times-dead position search).
- **Licence:** WSJT-X source may be read for understanding of the method; **no line
  of WSJT-X code may be copied, transliterated, or ported** (Captain's ruling,
  2026-08-11 — MIT/BSD-2/BSD-3/ISC only; WSJT-X is GPLv3 and out of bounds
  regardless of this project's own AGPL-3.0 licence).
- **Downstream:** this change's Phase 1, once built, unblocks Phase 2 (production
  wiring behind a runtime flag) only on a ROW 1 or ROW 2 gate outcome (§3 of the
  design). A ROW 3 (kill) outcome means Route B2 is dead in full — limb 1 was
  already dead, and D-001 would then have no remaining identified route (Architect's
  own stated consequence, 2026-08-19-1850 doc §3). Releasing the currently-HELD S3b
  full sweep is also gated on this Phase's ROW 1/ROW 2 outcome (2026-08-20-1613
  ordering doc §3), not on anything in this change directly.
