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

**Phase 0 (2026-08-20) and Phase 1 (2026-08-21) have both shipped**: the measurement
harness, population re-derivation, and validity checks (ROW 0c/0d) all passed against
the pre-Phase-1 build (Phase 0); `ft8_coherent_llr_at` was then built and merged (Phase
1, `main` `a420016`, shim `20260043`). Before the kill gate itself could be evaluated, a
pre-registered instrument-gain validity pre-check (**ROW 0g**) ran against the merged
binary and **FIRED**: on real audio the coherent path collapsed to near-chance bit
error (median 79/174) despite passing a clean-synthetic-signal check
(`qa/rr-study/2026-08-21-1100-…-row0g-fires-phase1-gate-void.md`). Diagnosis
(`qa/rr-study/2026-08-21-1201-…-triage-and-phase-a-deconfounding.md`,
`…-1330-…-b-pos-a-…`, `…-1412-…-origin-convention-finding-…`) traced this to two native
defects in `ft8_coherent_llr_at`, confirmed against known ground truth
(`…-1500-…-b-orig-a-results.md`, ROW 1 CONFIRMED): a raw-PCM correlation-origin
unit-conversion error, and a cross-window LLR-fusion comparison that is indefensible on
arithmetic grounds. **This change now also ships Phase B** (`qa/rr-study/2026-08-21-
1525-…-phase-b-origin-and-fusion-fix-and-row0g-rerun.md`, amended by `…-1644-…-phase-
b-amendment-1-…`): **B1** fixes the origin conversion, **B2** fixes the fusion
comparison, and **B4** (Amendment 1, authorised by the Captain to fold a planned
follow-on analysis arm's front end into this same Developer session) adds
`ft8_ldpc_decode_llrs`, a diagnostic-only export that decodes a caller-supplied LLR
vector through production's own decode sequence — inert, no production call site,
existing so a later, separately-pre-registered analysis arm can report CRC-verified
decode counts instead of modelled BER-threshold crossings. **C1** additionally pins, in
`design.md` (Decision D-B2-1), the shape any eventual production integration of the
coherent path must take (a fallback leg behind the grid path, never a replacement) — a
documentation-only edit, no code, no Developer session.

Phase B (B1, B2, B4) is `tasks.md` §7-10, and has since landed (`feat/r2-coherent-llr-
phase-b`, commit `7ed8b0c`). C1 was applied directly in `design.md` by that authoring
pass — no run, no session. `tasks.md` §11 (QA, after the Developer session — B-orig-A
unchanged, the B2 unit test, ROW 0g AS PRE-REGISTERED, before `tasks.md` §4.3's kill
gate can be attempted again) remains unrun as of this update; a separate arm,
**B-dt-A**, ran against the committed Phase B binary first (`qa/rr-study/2026-08-22-
1218-…-b-dt-a-results.md`), independent of §11's own acceptance ordering.

**This change now also ships Amendment 2, corrected in full by Amendment 3**
(`qa/rr-study/2026-08-21-2311-…-phase-b-amendment-2-snr-terms-getter.md`,
`qa/rr-study/2026-08-21-2334-…-phase-b-amendment-3-snr-terms-correction.md`). Amendment
2 found that the per-signal SNR formula's two terms (`signal_db`, `local_noise_db`)
have been unobservable since the noise-floor estimator that feeds them changed
(`FT8_SHIM_VERSION 20260012`), against a measured, large, conditional error: reported
SNR reads `+1.0..+1.2 dB` off true on single-signal scenarios but `-11.9..-14.6 dB` off
on others, while WSJT-X stays stable (`+0.5..+1.0 dB`) on the identical audio — so the
estimator, not the audio or truth labels, is responsible. **Amendment 3 retracted
Amendment 2's own framing of that split** (single- vs multi-signal / "crowding") after
re-deriving the same dataset: the true split is `true_dt == 0` vs `true_dt > 0` — every
multi-signal scenario in the corpus happens to be synthesised at DT 0.0, which made
crowding look causal when DT was the actual variable (HK-018 — the mechanism was
identifiable from data already on disk; Amendment 2's claim that it "cannot be
identified from outside the shim" was wrong). Amendment 3 made Amendment 2
**conditional on arm B-dt-A reaching ROW 2** (the Phase B origin fix, B1, does NOT
already resolve the collapse) rather than ROW 1 (it does, and the getter would be
deferred). **B-dt-A ran and ROW 2 fired** — `M0` (mean reported-minus-true SNR at
`true_dt == 0`) moved `+0.229 dB` from pre-B1 to post-B1, sub-quantum, i.e. no
measurable effect — so this Amendment proceeds. It adds `ft8_get_last_snr_terms`, a
diagnostic-only, per-decode, index-aligned parallel-array export exposing both SNR
terms, and bundles in the same rebuild a one-line widening of `ft8_ldpc_decode_llrs`'s
degenerate-variance guard (a hardening fix flagged in the 2026-08-21 22:09Z QA code
review). Unlike B4, this export DOES get a managed `Ft8LibInterop`/`IFt8NativeInterop`
P/Invoke binding (the amendment's own §4), matching the pattern the project's other
`ft8_get_last_*` diagnostic getters already use.

Amendment 2/3 is `tasks.md` §14-16, left unchecked, and requires a separate
Captain-opened Developer session (HK-011) from the one that built Phase B. §17 (QA,
after that session) runs AC-N1 through AC-N5 in the corrected order Amendment 3 §3-5
specify, culminating in AC-N5 — a REPORTED, not gated, DT-stratified measurement of
which term carries the collapse. This Amendment does not depend on `tasks.md` §11
having run, and does not itself resolve §11 or `tasks.md` §4.3 — independent forks off
the same Phase B binary.

## What Changes

- **(Phase 1, shipped — `main` `a420016`, shim `20260043`)** Added a new native,
  diagnostic-only export `ft8_coherent_llr_at(pcm, num_samples, cand_freq_idx,
  cand_time_idx, out_log174, out_diag)` that, given a candidate's *existing,
  unrefined* grid position, downconverts to complex baseband (reusing
  `sync_refiner.c`'s existing, already-reviewed downconversion — not
  reimplementing it), coherently correlates against each of the 8 tone hypotheses per
  data symbol (complex accumulation across the symbol, magnitude last), forms 1-, 2-
  and 3-symbol coherent metrics, and produces 174 per-bit LLRs normalised to the same
  scale `ftx_normalize_logl` expects — drop-in comparable with the existing
  magnitude-only `log174`. `ftx_decode_candidate()` and all production decode
  behaviour remain byte-for-byte unchanged — **BREAKING: none**. The pre-registered
  ROW 0g validity pre-check subsequently FIRED against this binary (see Phase B below).
- **(Phase 0, shipped)** Added the validation harness
  (`qa/rr-study/r2-coherent-llr-instrument/`) that re-derives the P-LIVE Stage 2
  population (`plive_population.build_p_live_population`, reused verbatim — HK-018),
  measures `ber_grid`/`n_err_grid` for every row using the *existing*
  `ft8_extract_llrs_at` export at Stage 2's own corrected anchor (`+0.65s`), and
  passes two validity checks: a mandatory sign unit test (ROW 0c) and a reproduction
  of Stage 2's own already-published median `ber_grid` = 31.03% within 1.0pp (ROW 0d).
  This harness is the one Phase 1 extends — once ROW 0g passes, the same per-row loop
  gains a second extraction call and computes `f_net`/`C_ber` per the §3 gate below.
- **(Phase 1, shipped)** Advanced `FT8_SHIM_VERSION` / `Ft8LibInterop.ExpectedShimVersion`
  to `20260043` and added the corresponding P/Invoke binding
  (`Ft8LibInterop.CoherentLlrAt`), matching the existing `RefineCandidate`/
  `ExtractLlrsAt` diagnostic-export pattern.
- **(Phase B, B1 — shipped, `feat/r2-coherent-llr-phase-b` commit `7ed8b0c`)** Fix
  `ft8_coherent_llr_at`'s raw-PCM correlation origin: it currently converts a lattice
  time-offset to seconds and uses that value directly as the correlation origin, one
  symbol period short of the analysis window's true centre (the look-back buffer +
  multi-symbol span the window spans). Corrected in place, derived at runtime from
  `mon.wf.time_osr`/`mon.wf.freq_osr`/`mon.symbol_period` — no hardcoded literal
  (design.md D8). No signature change, no new export, no production call site.
  **BREAKING: none.**
- **(Phase B, B2 — shipped, same commit)** Fix
  `ft8_coherent_llr_at`'s cross-window LLR-fusion comparison (`coherent_llr.c:480`):
  currently a raw `fabsf` magnitude comparison across the 1-, 2- and 3-symbol windows,
  which is a near-constant structural preference for the longest window rather than a
  reliability comparison, since a coherent sum's magnitude scales with window length.
  Corrected to compare each window's LLRs after standardising to a common,
  window-size-independent scale (design.md D9). No signature change. **BREAKING: none.**
- **(Phase B, B4 — Amendment 1, shipped, same commit)** Add a
  new native, diagnostic-only export `ft8_ldpc_decode_llrs(llr174, max_iters,
  osd_depth, out_a91, out_ldpc_errors, out_path, out_crc_ok)` in `decode.c` (forced
  placement — `ftx_normalize_logl`/`osd_decode` are `static` there) that decodes a
  caller-supplied 174-LLR vector through production's own `ftx_normalize_logl` →
  `bp_decode` → OSD (conditional) → CRC-14 sequence, mirroring `decode.c:641-713`
  exactly, duplicating no arithmetic. Inert — no production call site — and gets no
  `Ft8LibInterop` C# binding (design.md D10, following `n1-extract-llrs-at-position`'s
  own precedent). Exists so a later, separately-pre-registered analysis arm (C2, not
  this change) can report CRC-verified decode counts on rows already measured, in
  place of modelled BER-threshold crossings. `ftx_decode_candidate()` and all existing
  `decode.c` functions remain byte-for-byte unchanged. **BREAKING: none.**
- **(Phase B, all three — shipped, same commit)** Advanced `FT8_SHIM_VERSION` /
  `Ft8LibInterop.ExpectedShimVersion` from `20260043` to `20260044` (asserted
  mechanically unused across all branches first), rebuilt Windows and Linux platform
  binaries (macOS: no local toolchain, same limitation every prior native change in
  this project has recorded), and re-pinned
  `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py`'s
  `CURRENT_DLL_SHA256`/`CURRENT_SHIM_VERSION` (the single source four harnesses import).
- **(Phase B, C1 — applied by this authoring pass, docs only, no Developer session)**
  Pinned, in `design.md` (Decision D-B2-1), that any eventual production integration of
  the coherent path is a fallback leg behind the grid path (grid decodes first; the
  coherent leg runs only where the grid decode's CRC-14 fails), never a replacement —
  settling whether `f_break` is a recall cost (it is not, under this shape) before any
  integration work begins. No code change.
- **(Amendment 2, corrected by Amendment 3 — not yet implemented, blocked on a
  separate Developer session, HK-011; conditional on arm B-dt-A's ROW 2, which fired)**
  Widen `ftx_ldpc_decode_llrs`'s degenerate-variance guard (`decode.c:940`,
  `variance == 0.0f` → `!(variance > 0.0f)`, matching its sibling `coh_window_scale`'s
  own guard added by B2 in the same diff — a hardening fix, no value changes on any
  input that previously passed) and add a new native, diagnostic-only export
  `ft8_get_last_snr_terms(out_signal_db, out_local_noise_db, capacity)` exposing the
  two per-decode, index-aligned terms of `snr = signal_db - local_noise_db - 26.5f`
  (design.md D11/D12) — a quantity that has been unobservable since the local noise
  floor that feeds it changed (`FT8_SHIM_VERSION 20260012`) and is the only remaining
  way to localise a measured, conditional SNR-reporting collapse (`true_dt == 0`:
  `-11.9..-14.6 dB` off true; `true_dt > 0`: `+1.0..+1.2 dB`) to one of its two terms.
  Unlike B4, this export DOES get a managed `Ft8LibInterop.GetLastSnrTerms` P/Invoke
  binding and `IFt8NativeInterop` surface, matching the project's other
  `ft8_get_last_*` diagnostic getters (design.md D11 — the amendment's own §4).
  `ftx_decode_candidate()` and all existing decode-path values remain byte-for-byte
  unchanged. **BREAKING: none.**
- **(Amendment 2/3, all — not yet implemented, same Developer session)** Advance
  `FT8_SHIM_VERSION` / `Ft8LibInterop.ExpectedShimVersion` from `20260044` to
  `20260045` (asserted mechanically unused across all branches first), rebuild all
  three platform binaries, re-pin `coherent_llr_ctypes.py`'s
  `CURRENT_DLL_SHA256`/`CURRENT_SHIM_VERSION` again, then (QA, `tasks.md` §17) run
  AC-N1 through AC-N4 (all gating) and AC-N5 (reported, not gated — the DT-stratified
  `signal_db`/`local_noise_db` measurement on S3 + S8 that this export exists for).

## Capabilities

### New Capabilities
- `ft8-coherent-llr`: the per-candidate coherent multi-symbol LLR-formation stage
  (Phase 1, native, diagnostic-only, **shipped**) and the pre-registered kill gate
  (`f_net`, `C_ber`) that decides whether it is worth wiring into production (Phase
  2+), still blocked on the ROW 0g validity pre-check passing (`tasks.md` §11,
  unrun). Phase 0 (shipped) covers the gate's measurement harness and two validity
  checks against the *existing* extraction; Phase B (shipped) corrected two native
  defects ROW 0g surfaced in the already-shipped native stage. Amendment 2/3 (this
  update, not yet implemented) is an unrelated diagnostic export riding the same
  capability's native surface — it does not touch `ft8_coherent_llr_at` or the kill
  gate.

### Modified Capabilities
- `ft8lib-interop`: **(Phase 1, shipped)** the ABI self-test's expected shim constant
  advanced from `20260042` to `20260043`; the diagnostic P/Invoke entry point
  `ft8_coherent_llr_at` was added alongside the existing `RefineCandidate`/
  `ExtractLlrsAt` diagnostic surface, with no change to `DecodeAll`,
  `GetLastPassCounts`, or `SetDecodeParams`. **(Phase B, shipped)** the expected shim
  constant advanced again, `20260043` → `20260044`; a second new diagnostic native
  export, `ft8_ldpc_decode_llrs`, was added (native-only, no P/Invoke binding —
  design.md D10); `CoherentLlrAt`'s own P/Invoke signature and `IFt8NativeInterop`
  surface were unchanged, only the native values it returns changed (B1/B2's
  corrections to `ft8_coherent_llr_at` itself). **(Amendment 2/3, not yet
  implemented)** the expected shim constant advances a third time, `20260044` →
  `20260045`; a third new diagnostic native export, `ft8_get_last_snr_terms`, is
  added, and — unlike `ft8_ldpc_decode_llrs` — DOES get a P/Invoke binding
  (`Ft8LibInterop.GetLastSnrTerms`) and an `IFt8NativeInterop` surface, matching the
  project's other `ft8_get_last_*` diagnostic getters (design.md D11). `DecodeAll`,
  `CoherentLlrAt`, and every other existing entry point are unchanged.

## Impact

- **Affected code (Phase 1, shipped):** `native/ft8_lib_vendor/refine/coherent_llr.c`
  (new sibling file, the coherent-LLR export's C source, reusing
  `refine/sync_refiner.c`'s existing downconversion); `src/OpenWSFZ.Ft8/Native/
  ft8_shim.c`/`ft8_shim.h` (the new export); `src/OpenWSFZ.Ft8/Interop/` (the
  corresponding P/Invoke binding); all three platform binaries rebuilt.
- **Affected code (Phase B, shipped, commit `7ed8b0c`):** `coherent_llr.c` (B1's
  origin-correction edit near `origin_sample_f`, B2's fusion-comparison edit at the
  `fabsf(candidate)` comparison); `native/ft8_lib_build/patched/ft8/decode.c` (B4's new
  `ft8_ldpc_decode_llrs` function, additive only — zero diff on every existing
  function); `ft8_shim.c`/`ft8_shim.h` (B4's thin wrapper + export declaration, and the
  `FT8_SHIM_VERSION` bump to `20260044`); no `src/OpenWSFZ.Ft8/Interop/` change (B4
  got no C# binding); Windows/Linux platform binaries rebuilt again (macOS: not
  rebuilt locally, no toolchain available).
- **Affected code (Amendment 2/3, not yet touched):**
  `native/ft8_lib_build/patched/ft8/decode.c` (the one-line degenerate-variance guard
  widening at `ftx_ldpc_decode_llrs`, `:940`); `ft8_shim.c`/`ft8_shim.h` (the new
  `ft8_get_last_snr_terms` TLS storage, implementation, and export declaration, and
  the `FT8_SHIM_VERSION` bump to `20260045`); `native/ft8_lib_build/rebuild_shim.bat`
  (the new `/EXPORT:ft8_get_last_snr_terms` line, Windows only);
  `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`/`IFt8NativeInterop.cs` (the new
  `GetLastSnrTerms` P/Invoke binding and interface method, plus a stub in every
  existing `IFt8NativeInterop` test-fake implementer); all three platform binaries
  rebuilt a third time.
- **Affected tooling (Phase 0, shipped):** `qa/rr-study/r2-coherent-llr-instrument/`
  (population re-derivation, ROW 0c/0d, the gate harness, ROW 0g). Depends on, and
  reuses without modification, `qa/rr-study/p-live-population/plive_population.py`,
  `qa/rr-study/n1-extract-llrs-at-position/extract_llrs_ctypes.py`, and
  `qa/rr-study/p-live-population/run_stage1.py`'s `WavCache`/DLL-pin constants
  (HK-018 — none of this is reimplemented).
- **Affected tooling (Phase B, QA, still unrun — `tasks.md` §11 — independent of
  Amendment 2/3):** re-run `b_orig_a_origin_convention.py` unchanged (B1's own
  acceptance test), the B2 unit test, then `row0g_instrument_gain_check.py` AS
  PRE-REGISTERED — all four harnesses in `coherent_llr_ctypes.py`'s import chain
  re-pinned to the Phase B SHA256/shim version first. A separate arm, B-dt-A, already
  ran against the committed Phase B binary and is what authorised Amendment 2/3 to
  proceed (see the Why section) — it does not substitute for §11.
- **Affected tooling (Amendment 2/3, QA, after that Developer session —
  `tasks.md` §17):** re-pin `coherent_llr_ctypes.py`'s `CURRENT_DLL_SHA256`/
  `CURRENT_SHIM_VERSION` to the `20260045` build, then run AC-N1 (inertness, against
  the archived pre-Amendment-2 binary or the equivalent committed `7ed8b0c` binary —
  they must agree), AC-N2 (identifiability), AC-N3 (count contract), AC-N4 (capacity),
  and AC-N5 (the DT-stratified `signal_db`/`local_noise_db` measurement on S3 + S8,
  reported not gated).
- **Not affected:** `ftx_decode_candidate()`, the production decode path, every
  existing `ft8-decoder`/`ft8lib-interop` scenario, and (this change's own scope)
  every `ft8-sync-refiner` scenario from R1 — no phase, including B and Amendment 2/3,
  calls `ft8_refine_candidate` (design.md D1: limb 2 must not inherit limb 1's
  three-times-dead position search). B3 (`out_diag`, the fusion-selection-share
  diagnostic) stays HELD — neither Phase B nor Amendment 2/3 builds it. The SNR
  formula itself, suppression, and `K_SOFT_SUPP_SNR_*` are untouched — Amendment 2/3
  is an instrument, not a fix (design.md Goals, Amendment 2/3; does not reopen H5).
- **Licence:** WSJT-X source may be read for understanding of the method; **no line
  of WSJT-X code may be copied, transliterated, or ported** (Captain's ruling,
  2026-08-11 — MIT/BSD-2/BSD-3/ISC only; WSJT-X is GPLv3 and out of bounds
  regardless of this project's own AGPL-3.0 licence).
- **Downstream:** this change's Phase 1, now built, unblocks Phase 2 (production
  wiring behind a runtime flag) only on a ROW 1 or ROW 2 gate outcome (§3 of the
  design) — itself now blocked on Phase B's ROW 0g re-run passing. A ROW 3 (kill)
  outcome means Route B2 is dead in full — limb 1 was already dead, and D-001 would
  then have no remaining identified route (Architect's own stated consequence,
  2026-08-19-1850 doc §3). Releasing the currently-HELD S3b full sweep is also gated on
  this Phase's ROW 1/ROW 2 outcome (2026-08-20-1613 ordering doc §3), not on anything
  in this change directly. Once Phase B's binary is merged and its SHA256 pinned, B4
  unblocks a separately-pre-registered analysis arm (C2, not this change, not to be run
  against an unmerged build) that re-reads Stage 1RE's already-delivered rows through
  B4 to report CRC-verified counts in place of B50-threshold crossings. **Amendment
  2/3 is an independent fork off the same Phase B binary** (design.md Migration Plan):
  it does not gate on, and is not gated by, `tasks.md` §11/§4.3, ROW 0g, Route B2, or
  Phase 2 — its own downstream is AC-N5's report of which SNR term carries the
  `true_dt == 0` collapse, which a later, separately-pre-registered arm would need
  before proposing a fix to `DEFECT-snr-reported-gain-error.md` §4.
