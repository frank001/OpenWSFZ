# Developer handoff: Route B2 Amendment 2 (corrected by Amendment 3) — `ft8_get_last_snr_terms` diagnostic export + LDPC-decode guard widening

**Authored by:** QA (per HK-000/HK-015), following R0/R1/Phase 1/Phase B's established
convention: the operative artifact is `openspec/changes/r2-coherent-llr-instrument/`
(`proposal.md` + `design.md` + `specs/` + `tasks.md`). A Developer session should run
`opsx:apply` against that change's `tasks.md`, not duplicate its content here. This
document exists only to record HK-000's required handoff fields and to state **exactly
which sections of that `tasks.md` are this session's to do** — most of the change is
already shipped (Phase 0, Phase 1, and Phase B all landed; Phase B is `main`-bound
branch `feat/r2-coherent-llr-phase-b`, commit `7ed8b0c`).

🔴 **Per HK-011, this document is a proposal, not approved work in itself.** Only the
Captain opens the Developer session (nothing here does that). The Developer runs
`opsx:apply` (build + tests only — never `pre_merge_check.py`, that is QA's own
review-step gate per HK-006). The Captain reviews the `native/`/`src/` diff before any
push or merge (HK-010/HK-014). QA does not declare "ready for merge."

**Behaviour change: NONE INTENDED to any existing production path.** The new export is
diagnostic-only, read-only, and reachable only from test code and QA harnesses. The
guard widening only tightens an already-inert export's own input validation and does
not change any value on any input that previously passed. `ftx_decode_candidate()` and
all existing decode behaviour must remain byte-for-byte unchanged (see the spec's own
"Existing exports and decode paths are unaffected" scenario).

---

## 0. Why this session exists — the one-paragraph version

Since the noise-floor estimator `fix-d004-local-noise-floor` (`FT8_SHIM_VERSION
20260012`) replaced the global noise floor with a local one, the per-signal SNR
formula's two terms — `signal_db` and `local_noise_db` — have had no getter. A large,
conditional error is measured against them: OpenWSFZ's reported SNR reads
`+1.0..+1.2 dB` off true on single-signal scenarios but `-11.9..-14.6 dB` off on
others, while WSJT-X stays stable (`+0.5..+1.0 dB`) on the identical audio, so the
estimator (not the audio or truth labels) is responsible. The Architect first framed
this as a single- vs multi-signal ("crowding") split (Amendment 2), then retracted that
framing after re-deriving the same dataset (Amendment 3): the real split is
`true_dt == 0` vs `true_dt > 0` — every multi-signal scenario in the corpus happens to
be synthesised at DT 0.0, which made crowding look causal when DT was the actual
variable. Amendment 3 made the getter's construction **conditional on arm B-dt-A
reaching ROW 2** (the Phase B origin fix, B1, does NOT already resolve the collapse).
**B-dt-A ran 2026-08-22 and ROW 2 fired** — `M0` (mean reported-minus-true SNR at
`true_dt == 0`) moved `+0.229 dB` from pre-B1 to post-B1, sub-quantum, i.e. no
measurable effect (`qa/rr-study/2026-08-22-1218-qa-to-architect-b-dt-a-results.md`).
This session builds the getter needed to localise the collapse to one of its two
terms, and bundles in the same rebuild an unrelated one-line hardening fix (widening
`ft8_ldpc_decode_llrs`'s degenerate-variance guard) flagged in an earlier code review,
per the Architect's own "one rebuild, not two" instruction.

## 1. What is already done — do not redo it

`openspec/changes/r2-coherent-llr-instrument/tasks.md` §1-10, §12 are checked off and
shipped (Phase 0, Phase 1, Phase B — B1/B2/B4/C1 — all landed, `feat/r2-coherent-llr-
phase-b` commit `7ed8b0c`). §11 (QA's post-Phase-B acceptance ordering: B-orig-A
re-run, B2 unit-test confirmation, ROW 0g re-run AS PRE-REGISTERED) and §13 (Phase B
reporting) remain **unrun** as of this handoff — that is a separate, still-open QA
task, independent of this session and not part of it. A different arm, **B-dt-A**, ran
against the committed Phase B binary and is what authorised this session to proceed;
it does not substitute for §11. **None of §1-13 is this session's to touch.**

## 2. What this handoff covers — `tasks.md` §14, §15, §16

**Branch name:** a new branch off `main` (Phase B is already merged into `main`'s
lineage via `feat/r2-coherent-llr-phase-b` — confirm with the Captain which branch to
start from before naming this session's own branch; never commit directly to `main`).

**Actions**, in the order `tasks.md` lists them:

1. **§14.1 — the guard widening.** In `native/ft8_lib_build/patched/ft8/decode.c:940`
   (inside `ftx_ldpc_decode_llrs`, added by Phase B's B4), change the degenerate-
   variance guard from `variance == 0.0f` to `!(variance > 0.0f)` — matching its
   sibling `coh_window_scale`'s own guard (also added in Phase B, `coherent_llr.c`).
   This also catches a float-cancellation NEGATIVE variance the exact-equality check
   would miss. Re-run B4-d (`tasks.md` §9.4) afterwards: still negative `rc`, still no
   crash, no NaN, on the same all-`3.5f` zero-variance input.
2. **§14.2 — the `ft8_get_last_snr_terms` export.** Two new `_Thread_local` float
   arrays sized `K_MAX_DECODED` (`ft8_shim.c:552`) — `tls_signal_db`/
   `tls_local_noise_db` — plus a count, declared alongside the existing TLS diagnostic
   state (`ft8_shim.c:577-583`). Reset the count to `0` at the same point
   `tls_pass_counts`/`tls_candidate_counts` are reset per `ft8_decode_all` call
   (`ft8_shim.c:1274-1275`). At the point `FT8Result* r = &results[num_decoded++];`
   is formed (`ft8_shim.c:1476`, inside the per-candidate loop that already computes
   `signal_db` at lines 1450-1471 and `local_noise_db` at line 1473), write
   `tls_signal_db[num_decoded]`/`tls_local_noise_db[num_decoded]` at the SAME
   pre-increment index `results[]` uses for this decode — this is the whole
   index-alignment contract (AC-N3). Immediately before `return num_decoded;`
   (`ft8_shim.c:1504`), set the new count variable to `num_decoded`. **Read-only: must
   not alter control flow, ordering, or any decode-path value** — no existing local
   (`signal_db`, `local_noise_db`, `snr`) is renamed, moved, or recomputed. Exact
   signature, NULL/negative-capacity contract, and doc comment are given in full in
   `tasks.md` §14.2 and in `specs/ft8lib-interop/spec.md`'s new "Diagnostic SNR-terms
   native export and P/Invoke entry point" Requirement — implement from those, not
   from this summary.
3. **§14.3 — build changes.** Windows: add `/EXPORT:ft8_get_last_snr_terms ^` to
   `native/ft8_lib_build/rebuild_shim.bat`'s explicit export list (currently 15 lines,
   `:139-153`; this is the 16th). Linux: no change (`gcc -shared`, default
   visibility). Verify the export is present in the built DLL mechanically
   (`dumpbin /exports`), not inferred from the build succeeding.
4. **§15 — managed binding.** Add `Ft8LibInterop.GetLastSnrTerms` (P/Invoke to
   `ft8_get_last_snr_terms`), matching the existing `GetLastCandidateCounts`/
   `GetLastLlrStats` pattern (`Ft8LibInterop.cs:640-696`) — **unlike B4, this export
   DOES get a C# binding** (design.md D10 does not apply here; Amendment 2 §4 calls
   for one explicitly). Public signature:
   `(float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)`. Add the
   corresponding `IFt8NativeInterop.GetLastSnrTerms(int maxDecoded)` method and update
   all ten `IFt8NativeInterop` implementers with a stub (`Ft8NativeInteropAdapter` +
   the nine test fakes — the same file list `CoherentLlrAt` updated in Phase 1 task
   2.1). Add a smoke test mirroring the existing `GetLastLlrStats`/
   `GetLastCandidateCounts` coverage.
5. **§16 — version, pin, cross-platform build.** Bump `FT8_SHIM_VERSION`/
   `ExpectedShimVersion` from `20260044` to `20260045` — **assert mechanically that
   `20260045` is unused across all branches first** (the board records two prior
   collisions across five unmerged `d001-*` branches; do not infer freedom from the
   number being the next integer). Rebuild all three platform binaries you have
   toolchain access to; record each SHA256 honestly. Re-run a production-decode-
   equality replay (≥200 contiguous cycles, `qa/cycleframer-alignment-replay/
   r0_ac1_ac2_replay.py` + `r0_ac1_ac2_diff.py`) between the new binary and the
   archived pre-Amendment-2 Phase B binary (`a3d32b78...` win / `13d9799d...` linux —
   which, as of commit `7ed8b0c`, is also the committed `main`-lineage binary; verify
   both agree) — zero decode-output differences, mechanically diffed. This is AC-N1,
   and it GATES: any non-zero difference means STOP and escalate. **Re-pin
   `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py`'s
   `CURRENT_DLL_SHA256`/`CURRENT_SHIM_VERSION`** (four QA harnesses import this one
   file — read the rebuilt DLL's actual SHA256 from disk, don't copy it from a
   report). Verify mechanically whether `.github/workflows/ci.yml`'s build recipe
   needs an edit for the new exported symbol. `dotnet build`: 0 warnings. `dotnet
   test`: full suite green plus the new `GetLastSnrTerms` coverage — bump the C#
   `ExpectedShimVersion` constant in the SAME pass as the native bump, not a later one
   (task 10.6's own self-caught defect from the Phase B session is the standing
   cautionary example: a stale C# pin against a rebuilt DLL fails the whole daemon
   test suite with `InvalidOperationException` at `LoadAndVerify`, not a subtle bug).

**Acceptance criteria** (what QA checks on review — AC-N1 above is the only one this
session itself must clear; AC-N2 through AC-N5 are QA's own follow-on, `tasks.md`
§17, not part of this handoff's Definition of Done):

- The guard at `decode.c:940` reads `!(variance > 0.0f)`, matching `coh_window_scale`'s
  own guard exactly; B4-d re-run still passes.
- `ft8_get_last_snr_terms` exists, is index-aligned with `results[]`/`FT8Result[]`
  from the same `ft8_decode_all` call, is read-only (no control-flow, ordering, or
  value change to any existing decode-path computation), handles NULL/both-NULL/
  negative-capacity per the corrected contract, and is declared in `ft8_shim.h`
  alongside the other `ft8_get_last_*` getters.
- `decode.c`'s existing functions (beyond the one-line guard edit) and `ft8_shim.c`'s
  existing decode-path logic (beyond the two-line TLS write) are provably byte-for-
  byte unchanged (mechanical diff, not eyeballed); no production call site anywhere
  calls `ft8_get_last_snr_terms`.
- `Ft8LibInterop.GetLastSnrTerms` and `IFt8NativeInterop.GetLastSnrTerms` exist, all
  ten implementers updated, a smoke test added.
- Shim version bumped to `20260045`, asserted unused across all branches first, SHA256
  of every rebuilt binary recorded, `coherent_llr_ctypes.py`'s pin updated from the
  actual rebuilt SHA256.
- AC-N1 (the replay diff against the archived/committed pre-Amendment-2 binary) run
  and PASSING (zero differences) — this is the one acceptance check this session
  itself must clear before handing back; a non-zero diff is a STOP condition, not
  something to report and move past.
- `dotnet build`/`dotnet test` green.
- **QA then runs `tasks.md` §17 — AC-N2 (identifiability), AC-N3 (count contract),
  AC-N4 (capacity, including the both-NULL and negative-capacity cases), and AC-N5
  (the DT-stratified `signal_db`/`local_noise_db` measurement on S3 + S8, reported not
  gated).** Those runs are QA's, not the Developer's, and are not part of this
  handoff's Definition of Done.

**References:**

- `openspec/changes/r2-coherent-llr-instrument/` — proposal.md, design.md (Decisions
  D11/D12), specs/ft8lib-interop/spec.md ("Diagnostic SNR-terms native export and
  P/Invoke entry point" Requirement), tasks.md §14-16 (the operative artifact —
  implement from this, not from this file).
- `qa/rr-study/2026-08-21-2311-architect-to-qa-spec-phase-b-amendment-2-snr-terms-
  getter.md` — the Architect's original spec (symbol design, rationale for the
  parallel-array/per-decode/both-terms decisions, version/build discussion).
- `qa/rr-study/2026-08-21-2334-architect-to-qa-phase-b-amendment-3-snr-terms-
  correction.md` — **supersedes Amendment 2 wherever they conflict.** Corrected AC-N1
  (precondition on the archived binary), AC-N2 (`+1e-3` tolerance), AC-N4 (degenerate-
  capacity case), the both-NULL contract, and AC-N5 (the DT-stratified measurement,
  replacing the retracted crowding framing entirely).
- `qa/rr-study/2026-08-22-1218-qa-to-architect-b-dt-a-results.md` — the run that
  authorised this session to proceed (ROW 2 fired).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — the file §14 edits (TLS storage, the write at
  line 1476, the count set before line 1504's return).
- `native/ft8_lib_build/patched/ft8/decode.c` — the file §14.1's guard edit touches
  (line 940, inside `ftx_ldpc_decode_llrs`, itself added by Phase B/B4).
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` (around `GetLastCandidateCounts`/
  `GetLastLlrStats`, `:640-696`) and `IFt8NativeInterop.cs` — the files §15 edits.
- Licence discipline, binding and unchanged: WSJT-X source may be read for method only;
  no line copied, transliterated, or ported (Captain's ruling, 2026-08-11).
