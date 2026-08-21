# Developer handoff: Route B2 Phase B — origin fix (B1), fusion fix (B2), LDPC-decode diagnostic export (B4, Amendment 1)

**Authored by:** QA (per HK-000/HK-015), following R0/R1/Phase 1's established
convention: the operative artifact is `openspec/changes/r2-coherent-llr-instrument/`
(`proposal.md` + `design.md` + `specs/` + `tasks.md`). A Developer session should run
`opsx:apply` against that change's `tasks.md`, not duplicate its content here. This
document exists only to record HK-000's required handoff fields and to state **exactly
which sections of that `tasks.md` are this session's to do** — the change is phased and
most of it is already done (Phase 0 and Phase 1 both shipped).

🔴 **Per HK-011, this document is a proposal, not approved work in itself.** Only the
Captain opens the Developer session (nothing here does that). The Developer runs
`opsx:apply` (build + tests only — never `pre_merge_check.py`, that is QA's own
review-step gate per HK-006). The Captain reviews the `native/`/`src/` diff before any
push or merge (HK-010/HK-014). QA does not declare "ready for merge."

**Behaviour change: NONE INTENDED to any existing production path.** B1 and B2 correct
an already-diagnostic-only, no-production-call-site export (`ft8_coherent_llr_at`); B4
is a wholly new diagnostic-only export. `ftx_decode_candidate()` and all existing
decode behaviour must remain byte-for-byte unchanged (see the spec's own scenarios for
the mechanical check — "Existing exports and decode paths are unaffected").

---

## 0. Why this session exists — the one-paragraph version

Phase 1 (`ft8_coherent_llr_at`) shipped 2026-08-21, `main` `a420016`, shim `20260043`.
Before its own kill gate could run, a pre-registered validity pre-check (**ROW 0g**)
ran against that binary and **FIRED**: on real audio the coherent path collapsed to
near-chance bit error (median 79/174) despite passing a clean-synthetic-signal check.
Diagnosis traced this to two defects in `ft8_coherent_llr_at`: (**B1**) the raw-PCM
correlation origin is derived from a lattice time-offset with a one-symbol unit-
conversion error; (**B2**) the cross-window LLR-fusion comparison uses raw,
unnormalised magnitude, which structurally favours the longest coherent window
regardless of its actual reliability. Both are fixed in this session. The Captain
separately authorised folding a third, unrelated addition into the same session
(**B4**, Amendment 1): a diagnostic-only export, `ft8_ldpc_decode_llrs`, that lets a
later analysis arm (not this session, not this change) convert an LLR vector into a
CRC-verified decode count instead of a modelled BER-threshold crossing.

## 1. What is already done — do not redo it

`openspec/changes/r2-coherent-llr-instrument/tasks.md` §1-6 are checked off already —
Phase 0 (2026-08-20) built and validated the measurement harness; Phase 1 (2026-08-20/
21) built `ft8_coherent_llr_at`, bumped the shim to `20260043`, and shipped on `main`
(`a420016`). §12 (C1 — the `design.md` cascade-shape pin, Decision D-B2-1) is also
already done — QA applied it directly during this authoring pass; it is docs-only and
needed no Developer session. **None of §1-6 or §12 is this session's to touch.**

## 2. What this handoff covers — `tasks.md` §7, §8, §9, §10

**Branch name:** `feat/r2-coherent-llr-phase-b` (never commit directly to `main`).

**Actions**, in the order `tasks.md` lists them:

1. **§7 — B1, the origin correction.** In `ft8_coherent_llr_at`
   (`native/ft8_lib_vendor/refine/coherent_llr.c`), after the existing lattice snap
   produces `time_offset_s_grid`, apply `correction_symbols = 1/time_osr − freq_osr/2
   − 0.5` (== `-1.0` at `K_TIME_OSR = K_FREQ_OSR = 2`) to `origin_sample_f` (currently
   formed at line 437). **Derive `time_osr`/`freq_osr`/`symbol_period` from
   `mon.wf.time_osr`/`mon.wf.freq_osr`/`mon.symbol_period` (already read at lines
   394-398, captured before `monitor_free(&mon)` at line 413) — do not hardcode the
   resulting constant.** Comment the correction with its rationale (the look-back
   window + window-centre derivation), pointing at the 2026-08-21 14:12Z finding
   document. Cross-check against
   `qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py:227`'s own
   `TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K` — if the derived correction disagrees
   with that empirically-calibrated prototype constant at production OSR, **stop and
   escalate before rebuilding.**
2. **§8 — B2, the fusion normalisation.** Before the cross-`n_syms` comparison at
   `coherent_llr.c:480` (`if (n_syms == 1 || fabsf(candidate) >
   fabsf(out_log174[gb]))`), standardise each window's per-bit LLRs to a common,
   window-size-independent scale before comparing (e.g. divide by that window's own
   `stddev(mag[])`, guarding `scale > 0`). Do **not** fix this by restricting
   `n_syms` — all three window sizes must remain in the comparison. Add the mandatory
   unit test: two windows with equal discriminative information but different
   absolute scale; normalised LLRs agree, pre-normalisation LLRs do not.
3. **§9 — B4, the LDPC-decode diagnostic export.** Add `ft8_ldpc_decode_llrs` to
   `native/ft8_lib_build/patched/ft8/decode.c` (forced placement —
   `ftx_normalize_logl`/`osd_decode` are `static` there), thin wrapper in
   `ft8_shim.c`. Signature and exact 7-step sequence (memcpy → degenerate guard →
   mandatory `ftx_normalize_logl` → save for OSD → `bp_decode` → CRC check → OSD
   fallback iff CRC failed and `osd_depth >= 0`) are given in full in `tasks.md` §9.1-
   9.2 and in `specs/ft8lib-interop/spec.md`'s new "Diagnostic LDPC-decode-from-LLRs
   native export" Requirement — implement from those, not from this summary. **No
   `Ft8LibInterop`/`IFt8NativeInterop` C# binding is needed or wanted** (design.md
   D10) — native/Python smoke tests only, covering all five acceptance checks (B4-a
   through B4-e, `tasks.md` §9.4). **B4-e (agreement with the production decoder on
   real audio, ≥90%) is the one check with known ground truth and is a stop condition
   if it fails — report it regardless, but do not let a B4-e failure block §10 or the
   handback; it only blocks a later, separate C2 arm this session does not run.**
4. **§10 — Version, pin, cross-platform build.** Bump `FT8_SHIM_VERSION`/
   `ExpectedShimVersion` from `20260043` to `20260044` — **assert mechanically that
   `20260044` is unused across all branches first** (the board records two prior
   collisions across five unmerged `d001-*` branches; do not infer freedom from the
   number being the next integer). Rebuild all three platform binaries you have
   toolchain access to; record each SHA256 honestly. Re-run a production-decode-
   equality replay (≥200 contiguous cycles, `qa/cycleframer-alignment-replay/
   r0_ac1_ac2_replay.py` + `r0_ac1_ac2_diff.py`) between the pre-Phase-B and new
   binaries — zero decode-output differences, mechanically diffed. **Re-pin
   `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py`'s
   `CURRENT_DLL_SHA256`/`CURRENT_SHIM_VERSION`** (four QA harnesses import this one
   file — read the rebuilt DLL's actual SHA256 from disk, don't copy it from a
   report). Verify mechanically whether `.github/workflows/ci.yml`'s build recipe
   needs an edit for the new exported symbol (no new source *file*, but a new
   *symbol* — re-check, don't inherit Phase 1's "no edit needed" answer). `dotnet
   build`: 0 warnings. `dotnet test`: full suite green (regression check only — this
   session adds no C# code).

**Acceptance criteria** (what QA checks on review):

- `ft8_coherent_llr_at`'s origin correction is derived from `mon.wf.*` at runtime, not
  hardcoded, and agrees with the N2 Python prototype's empirical constant at
  production OSR.
- The fusion comparison at `coherent_llr.c:480` compares normalised, not raw, LLRs
  across windows; the mandatory unit test (design.md D9) passes.
- `ft8_ldpc_decode_llrs` exists, is diagnostic-only, mirrors `decode.c:641-713`
  exactly (no duplicated arithmetic, nothing un-`static`'d, `osd_decode` not moved),
  and all five acceptance checks (B4-a through B4-e) are run and reported — B4-a
  through B4-d passing is mandatory; B4-e's result (≥90% floor) is reported either way.
- `decode.c`'s existing functions are provably byte-for-byte unchanged (mechanical
  diff, not eyeballed); no production call site anywhere calls
  `ft8_ldpc_decode_llrs` or the corrected `ft8_coherent_llr_at` outside test code and
  QA harnesses.
- Shim version bumped to `20260044`, asserted unused across all branches first, SHA256
  of every rebuilt binary recorded, `coherent_llr_ctypes.py`'s pin updated from the
  actual rebuilt SHA256.
- `dotnet build`/`dotnet test` green.
- **QA then runs `tasks.md` §11 — the acceptance ordering (B-orig-A re-run, the B2
  unit test, then ROW 0g AS PRE-REGISTERED) — and, only if all three pass, `tasks.md`
  §4.3 (the `f_net`/`C_ber` kill gate).** Those runs are QA's, not the Developer's,
  and are not part of this handoff's Definition of Done.

**References:**

- `openspec/changes/r2-coherent-llr-instrument/` — proposal.md, design.md (Decisions
  D8/D9/D10/D-B2-1), specs/ft8-coherent-llr/spec.md, specs/ft8lib-interop/spec.md,
  tasks.md §7-10 (the operative artifact — implement from this, not from this file).
- `qa/rr-study/2026-08-21-1525-architect-to-qa-spec-phase-b-origin-and-fusion-fix-and-
  row0g-rerun.md` — the Architect's B1/B2 spec (method description, exact formulas,
  licence discipline).
- `qa/rr-study/2026-08-21-1644-architect-to-qa-phase-b-amendment-1-ldpc-decode-llrs-
  export-and-cascade-pin.md` — the Architect's B4 amendment (exact signature, exact
  7-step sequence, the five acceptance checks).
- `qa/rr-study/2026-08-21-1412-architect-to-qa-origin-convention-finding-and-spec-b-
  orig-a.md` — the B1 root-cause finding and derivation.
- `native/ft8_lib_vendor/refine/coherent_llr.c` — the file B1 and B2 both edit.
- `native/ft8_lib_build/patched/ft8/decode.c` — the file B4 adds to.
- Licence discipline, binding and unchanged: WSJT-X source may be read for method only;
  no line copied, transliterated, or ported (Captain's ruling, 2026-08-11).
