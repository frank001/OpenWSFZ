## Context

Full derivation: `qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-phase1-coherent-
llr-kill-gate.md` ("the Phase 1 spec"). Summary of what changed the shape of this work
during drafting (Phase 1 spec §0): the `C:\Temp` build blocker that made Route B2 look
un-sizeable is gone (R0 vendored the tree); half of Route B2 (`sync_refiner.c`, limb 1)
was already built and has no production call site; and that built half is the half
that has since failed three times (`M4`, `N1`, P-LIVE Stage 2 — see proposal.md Why).
**Route B2's remaining value rests entirely on limb 2** (coherent multi-symbol LLR
formation), which has never been measured. Phase 1 tests limb 2 alone, formed at the
*existing* grid position so that limb 1's death cannot contaminate the result.

This change is itself phased (proposal.md's own distinction): **Phase 0 (this session,
QA, no native code) builds and validates the measurement harness against the current
build; Phase 1 (native, a future Developer session) builds `ft8_coherent_llr_at()` and
runs the gate below.** The two are one OpenSpec change because they specify one
capability end-to-end, matching R1's own precedent (build-with-acceptance-criteria);
they are not one *session* of work.

## Goals / Non-Goals

**Goals (Phase 0, this session):**
- Re-derive the exact population Phase 1's gate will run on
  (`plive_population.build_p_live_population(PRIMARY_CORPUS)`, the P-LIVE Stage 2
  population — reference decoded, we did not), reporting CLUSTER counts, not row
  counts, and confirming no population helper truncates via a `limit=` argument
  (HK-021(i)).
- Build the `ber_grid` half of the harness Phase 1 will extend with a second
  (`ber_coh`) extraction call, using only the *existing* `ft8_extract_llrs_at` export.
- Pass a mandatory two-sided sign unit test (ROW 0c) proving the bit-error-counting
  convention this harness reuses is correct in both directions.
- Reproduce Stage 2's own already-published median `ber_grid` (31.03%) within 1.0pp on
  a fresh re-derivation (ROW 0d), certifying the harness before Phase 1 is proposed.

**Goals (Phase 1, future, native — specified here, not built here):**
- Build `ft8_coherent_llr_at()`: coherent per-candidate LLR formation *at the existing
  grid position*, reusing `sync_refiner.c`'s already-reviewed downconversion.
- Run the pre-registered gate (§ below) on the P-LIVE Stage 2 population and report
  one of ROW 1/2/3/4.

**Non-Goals (either phase):**
- Not wiring `ft8_coherent_llr_at` into `ftx_decode_candidate()` or any production
  decode call — that is Phase 2's scope entirely, gated on Phase 1's ROW 1/ROW 2.
- Not calling `ft8_refine_candidate` from anywhere in this change, diagnostically or
  otherwise (Decision D1). Limb 1 is dead three times over; Phase 1 must not import
  that dependency even for a "coarse position."
- Not re-deriving the `+0.65s` anchor-offset correction — it is REUSED verbatim from
  Stage 2's own Part A (`r2_population.STAGE2_ANCHOR_OFFSET_S`), not re-swept here.
- Not re-measuring `B50` = 11.3% (the July-corpus correction threshold) — reused as-is
  from N1/N5's own citation, flagged as a real but accepted risk (Phase 1 spec §6.2).
- Not the S3b synthetic sweep — HELD, released only on this change's Phase 1 ROW 1/2
  outcome, and not this change's own concern (2026-08-20-1613 ordering doc §3).

## Decisions

**D1 — Phase 1 forms coherent LLRs at the EXISTING grid position; no dependence on
`ft8_refine_candidate()`'s position estimate.**
Alternative considered: refine first, then form coherent LLRs at the refined position
(the naive "improve limb 1, then add limb 2" order). Rejected — limb 1 is dead three
times over (`M4` ROW 2, `N1` ROW 2, P-LIVE Stage 2 ROW 3/HARM); stacking limb 2 on a
dead limb 1 would make a limb-2 null result ambiguous between "coherent LLRs don't
help" and "the position they were formed at was already wrong," exactly the
interpretability hazard R1 was built to remove for the refiner itself. Forming coherent
LLRs at the grid position makes the two limbs' fates independent by construction.

**D2 — Phase 0's harness reuses `plive_population.build_p_live_population` and
`extract_llrs_ctypes.ExtractLLRs`/`hard_decision_ber` verbatim; it does not
reimplement population construction or bit-error counting.**
HK-018: both are already built, already validated across Stage 1/1R/2, and a second,
divergent implementation of either would risk two different definitions of "the
population" or "an error" existing in the same codebase for the same capability.
`r2_ber_grid.py` is a genuinely new module (it drops the refiner call Stage 2's own
`measure_stage2_row` made — D1 above — so it cannot be a call-for-call reuse of that
function), but every primitive it calls is reused, not rewritten.

**D3 — ROW 0c (sign unit test)'s SIGNAL sub-check uses real P-HIT rows at Stage 2's own
corrected anchor, not a synthetic signal at its own encoder-specified position.**
The first construction of this check used `qa/rr-study/synth/encoder.encode_message`
at a clean high SNR, extracted at the exact `(freq_hz, dt_s)` passed to the encoder,
expecting `n_err ≈ 0`. **It failed**: mean `n_err ≈ 70/174`, far from clean. A
fine-grained noiseless `dt` sweep isolated the cause: the synth encoder's `dt_s`
parameter and `ft8_extract_llrs_at`'s own `time_offset_s` convention are offset from
each other by roughly +0.1–0.2s — a real, repeatable gap, but a *different* one from
the already-known `+0.65s` live-capture-chain offset (`AO1`/`D1`/Stage 2), with no
prior measurement anywhere in this project. Chasing that gap to a precise constant is
its own investigation (a synth-harness question, not a Phase 0 or Phase 1 question) and
is explicitly out of scope here — flagged to the Architect in the QA report, not solved
in this change. The construction actually shipped sidesteps the question entirely:
real P-HIT rows (a cycle both decoders decoded, so ground truth is real, off-air audio)
at the anchor+offset convention Stage 2's own sign test already validated. See
`r2_sign_test.py`'s module docstring for the full account, kept in the code per
HK-022 rather than only in this document.

**D4 — ROW 0c's SIGNAL sub-check gates on the MEDIAN of `n_err`, not the mean.**
A first pass gated on the mean and FAILED (22.78, bar 15) on the same 18-trial sample
whose median was 12.5 (PASS). The distribution is right-skewed by construction: most
P-HIT rows extract near-clean at the corrected anchor, a minority sit near chance
(rows where the WSJT-X-reported anchor itself carries more slop than the single global
`+0.65s` correction absorbs — the same phenomenon Stage 2's own Part A found and
reported as a *median*, never a mean, throughout this project's history for this exact
population). Both statistics are computed and reported in the harness output (HK-022 —
report what was measured, don't silently pick whichever passes); only the median gates.

**D5 — Mechanical definitions for Phase 1's gate, fixed now (HK-021(o), reused
verbatim from the Phase 1 spec §3 rather than re-derived):**
- A codeword is 174 bits ⇒ the BER quantum is `1/174 = 0.575pp`. The correction
  threshold `B50 = 11.3%` does not land on a quantum, so **correctable ⇔ `n_err ≤ 19`**
  (10.92%, the conservative side of 11.3%) — an integer bit-count comparison, never a
  float comparison against `0.113`. `r2_ber_grid.py` reports `n_err_grid` as an int for
  exactly this reason.
- `f_net`'s quantum on the 3,916-cluster P-LIVE population is `1/3,916 = 0.0255%`.
- Resolvable distance (HK-021(m), stated while drafting, unchanged from the Phase 1
  spec): at `f_net ≈ 10%`, cluster-level SE ≈ 0.48%, CI half-width ≈ 0.94% — the 5%
  and 15% gate bars sit ~10 half-widths apart. If the delivered cluster count at Phase
  1 time is below 1,500, STOP and escalate rather than running (the bars stop
  separating well before that floor, but 1,500 is the pre-registered trigger).
- HK-021(l): `f_net` is signed (nets the reverse crossings); never gate on `n_in` alone.

**D6 — ROW ordering for Phase 1's gate is unchanged from the Phase 1 spec §3, restated
here for one-document completeness (not re-derived):** ROW 1 (`CI_lo(f_net) > 15%`) →
ROW 2 (`CI_lo(f_net) > 5%`, not ROW 1) → ROW 3 (`CI_hi(f_net) < 5%`) → ROW 4 (residue).
Exclusivity: ROW 1 ⊂ ROW 2's condition, evaluated first; ROW 2 requires `CI_lo > 5%`,
ROW 3 requires `CI_hi < 5%`, and `CI_lo ≤ CI_hi` ⇒ they cannot both hold; ROW 4 is the
complement.

**D7 — Phase 0 ships no native code and touches no `src/` file.** `ft8_coherent_llr_at`
does not exist in the current binary (confirmed: `ft8_shim.h` grepped, no such symbol;
DLL SHA256 re-verified at `6890d84c...`, shim `20260042`, matching the pin already in
production use — no rebuild happened). HK-011 is not engaged by this change's Phase 0
scope; it is engaged the moment Phase 1's native tasks begin, and that requires a
Captain-opened Developer session this change does not authorise.

## Risks / Trade-offs

- **[Risk, named in the Phase 1 spec, restated] The shared-machinery risk.** Limb 2
  reuses `sync_refiner.c`'s existing downconversion. Decision D1 stops a bad *position
  estimate* from propagating (coherent LLRs are formed at the grid position, not a
  refined one), but if the downconversion itself is defective on real signals rather
  than merely on its search, limb 2 inherits that. Mitigation: Phase 1's own ROW 0c
  (ft8_coherent_llr_at's sign test, not this change's Phase 0 sign test) is the guard,
  and per the Phase 1 spec it must be two-sided for exactly this reason.
- **[Risk, discovered this session] The synth encoder/extractor position-convention
  gap (D3).** Unresolved and out of scope. If a future change needs a *synthetic*
  known-good signal at a precisely-known extraction position (Phase 1's own harness
  extension might want this for a cleaner AC-style sign test on the coherent limb),
  this gap will need to be chased down first. Flagged, not blocking Phase 0's own ROW
  0c (which sidesteps it via D3's real-data construction).
- **[Trade-off] `B50 = 11.3%` is a July-corpus figure (n = 126 measured), reused
  without re-measurement.** Carried forward from the Phase 1 spec (§6.2) rather than
  re-litigated here; it is doing real work in `n_err ≤ 19`. A re-measurement is a
  defensible ask and would cost a re-run, not a rebuild, if the Captain wants it first.
- **[Trade-off] The 8.9% no-candidate misses are outside Phase 1's addressable
  population by construction** (RC1's decomposition — 3.1% out-of-band, 8.9%
  no-candidate, 87.9% candidate-present-and-failed). The ~37pp ceiling this implies for
  Route B2's maximum possible recall gain is a Phase 1 spec quantity (§2), not
  recomputed in this change; do not let it be dropped when a Phase 1 result is quoted.

## Migration Plan

No runtime migration in Phase 0 — nothing production-facing exists yet. Phase 1,
when built, is diagnostic-only (same discipline as R1's `ft8_refine_candidate` and the
existing `ft8_extract_llrs_at`): `FT8_SHIM_VERSION`/`ExpectedShimVersion` advances,
all three platform binaries rebuild, and no production call site is added. Rollback of
Phase 1 is a plain `git revert` of the new-export + gate-harness-extension commit; this
change's own Phase 0 harness remains valid regardless (it depends only on the
already-shipped `ft8_extract_llrs_at`). Phase 2 (production wiring) does not start
until Phase 1 reports ROW 1 or ROW 2 and the Captain has made the explicit re-decision
the Phase 1 spec names for a ROW 2 outcome (§3: "the project's stated purpose is not
met by this outcome and he should hear that in those words").

## Open Questions

1. **Exact placement of `ft8_coherent_llr_at`'s C source** — `native/ft8_lib_vendor/
   refine/` (alongside `sync_refiner.c`, since it reuses that file's downconversion) is
   the likely answer, left to the Developer session to decide and record, same
   discipline R1's own Open Question 1 used.
2. **Whether `r2_ber_grid.py` gains the `ber_coh`/second-extraction-call limb as an
   edit to this same module, or a new sibling module**, once `ft8_coherent_llr_at`
   exists — a QA-tooling placement choice with no bearing on the gate itself, left to
   whoever runs Phase 1's measurement (QA, per the Phase 1 spec §5).
3. **Whether the synth encoder/extractor position-convention gap (D3/Risks) is ever
   chased down**, and if so whether it belongs to this change, a `synth/` defect report,
   or a standalone QA note — not decided here; flagged in the QA report for the
   Architect.
