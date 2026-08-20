# Developer handoff: Route B2 Phase 1 — `ft8_coherent_llr_at()`, diagnostic-only

**Authored by:** QA (per HK-000/HK-015), following R0/R1's established convention: the
operative artifact is `openspec/changes/r2-coherent-llr-instrument/` (`proposal.md` +
`design.md` + `specs/` + `tasks.md`). A Developer session should run `opsx:apply`
against that change's `tasks.md`, not duplicate its content here. This document exists
only to record HK-000's required handoff fields and to state **exactly which sections
of that `tasks.md` are this session's to do** — the change is phased and most of it is
already done.

🔴 **Per HK-011, this document is a proposal, not approved work in itself.** Only the
Captain opens the Developer session (nothing here does that). The Developer runs
`opsx:apply` (build + tests only — never `pre_merge_check.py`, that is QA's own
review-step gate per HK-006). The Captain reviews the `native/`/`src/` diff before any
push or merge (HK-010/HK-014). QA does not declare "ready for merge."

**Behaviour change: NONE INTENDED to any existing production path.** This is a new
diagnostic-only export, reachable only from test code and a validation harness —
`ftx_decode_candidate()` and all existing decode behaviour must remain byte-for-byte
unchanged (see the spec's own scenarios for the mechanical check).

---

## 1. What is already done — do not redo it

`openspec/changes/r2-coherent-llr-instrument/tasks.md` §3, §4, and §6 are **checked off
already** — QA's Phase 0 (2026-08-20, this session): the measurement harness
(`qa/rr-study/r2-coherent-llr-instrument/`), the P-LIVE population re-derivation, and
two validity checks (ROW 0c sign unit test, ROW 0d `ber_grid` reproduction of Stage 2's
own 31.03% median) all PASS against the current build. No `src/` or `native/` file was
touched to do this; the DLL in production use (SHA256
`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`, shim `20260042`)
was not rebuilt. Full account: `qa/rr-study/2026-08-20-1707-qa-to-architect-b2-phase0-results.md`.

## 2. What this handoff covers — `tasks.md` §1, §2, §5

**Branch name:** `feat/r2-coherent-llr-phase1` (never commit directly to `main`).

**Actions**, in the order `tasks.md` lists them:

1. **§1 — Build `ft8_coherent_llr_at()`** in `native/ft8_lib_vendor/` (design.md Open
   Question 1 suggests `refine/`, alongside `sync_refiner.c`, since it reuses that
   file's downconversion — record the actual placement chosen). Implement per
   design.md D1 (grid position only, **never calls `ft8_refine_candidate`**) and the
   coherent-correlation method in the spec's own Requirement text
   (`specs/ft8-coherent-llr/spec.md`). Add the export, confirm `ftx_decode_candidate()`
   is byte-for-byte unchanged (diff against the pre-change vendored/patched source).
2. **§2 — Managed binding.** `Ft8LibInterop.CoherentLlrAt` + `IFt8NativeInterop`
   method + `FakeInterop` stub, matching the existing `RefineCandidate`/`ExtractLlrsAt`
   pattern exactly (`specs/ft8lib-interop/spec.md`'s ADDED requirement has the full
   scenario list). Grep-confirm zero production call sites.
3. **§5 — Shim version and cross-platform build.** 🔴 **Before touching this task,
   snapshot `D:\Projects\claude` and diff it again immediately after** — two prior
   occurrences of a stray `OpenWSFZ<icon>` folder (`memory/operational-note-stray-
   nonascii-openwsfz-folder.md`) both coincided with exactly this kind of native
   Linux rebuild / shim-version-bump step, and the Captain wants this specific step
   watched:
   ```powershell
   $watch = "C:\Users\Frank\.claude\projects\D--Projects-claude-OpenWSFZ\memory\check-stray-folders.ps1"
   powershell -File $watch -Save   # BEFORE build_linux.sh
   # ... run this task ...
   powershell -File $watch          # AFTER — report the output
   ```
   (Script + baseline live in the Claude Code project **memory** directory above, not
   in this repo — there is no `memory/` folder under `D:\Projects\claude\OpenWSFZ`.)
   Report both outputs in the QA hand-back regardless of result (a clean diff is a
   real negative, not a skipped step). If a stray folder DOES appear, do not delete it
   — preserve it and the surrounding tool-call/shell transcript for the operational
   note, then continue.
   Advance `FT8_SHIM_VERSION`/
   `ExpectedShimVersion` **past `20260042`** — do not reuse or collide with any of the
   five unmerged `d001-*` branches' own claimed integers (the spec's own §6 risk note:
   "the allocation record is already behind reality"). Rebuild all three platform
   binaries you have toolchain access to; record each SHA256 honestly (R0's own
   standard for an unavailable platform — state it, don't skip silently). Re-run a
   production-decode-equality replay (R0/R1's own AC-1/AC-2-style pattern, ≥200
   contiguous cycles) between the pre-change and new binaries: zero decode-output
   differences, mechanically diffed. `dotnet build`: 0 warnings. `dotnet test`: full
   suite green plus the new `CoherentLlrAtTests`.

**Acceptance criteria** (what QA checks on review):

- `ft8_coherent_llr_at` exists, is diagnostic-only, and `ftx_decode_candidate()`/
  `DecodeAll` are provably byte-for-byte unchanged (mechanical diff, not eyeballed).
- No call to `ft8_refine_candidate`/`RefineCandidate` anywhere inside the new export's
  implementation (design.md D1 — this is the whole point of Phase 1's design).
- Shim version bumped, does not collide with any other branch's claimed integer, SHA256
  of every rebuilt binary recorded.
- `dotnet build`/`dotnet test` green; `CoherentLlrAtTests` covers fake delegation and a
  real-binary smoke test (mirrors R1's `RefineCandidateTests` 2.1a/b/c pattern).
- **QA then runs `openspec/changes/r2-coherent-llr-instrument/tasks.md` §4.3 — the
  `f_net`/`C_ber` gate itself** (extends this session's own `r2_ber_grid.py` with the
  second extraction call) and reports one of ROW 1/2/3/4. That run is QA's, not the
  Developer's, and is not part of this handoff's Definition of Done.

**References:**

- `openspec/changes/r2-coherent-llr-instrument/` — proposal.md, design.md,
  specs/ft8-coherent-llr/spec.md, specs/ft8lib-interop/spec.md, tasks.md (the operative
  artifact — implement from this, not from this file).
- `qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-phase1-coherent-llr-kill-gate.md`
  — the Architect's original Phase 1 spec (method description, gate arithmetic,
  licence discipline).
- `qa/rr-study/2026-08-20-1707-qa-to-architect-b2-phase0-results.md` — this session's
  Phase 0 results (harness validated, ROW 0c/0d PASS).
- `native/ft8_lib_vendor/refine/sync_refiner.c` — the downconversion this export reuses.
- Licence discipline, binding and unchanged: WSJT-X source may be read for method only;
  no line copied, transliterated, or ported (Captain's ruling, 2026-08-11).
