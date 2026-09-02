## Phase 1 — three unique-match sizing counters (shipped, shim `20260047`)

*Retrofit note: Phase 1 was implemented and verified before this OpenSpec change existed, via
`dev-tasks/2026-08-30-sup-b-h12-instrumentation.md`. Tasks below are checked against that record,
not re-run.*

### 1. Native Shim

- [x] 1.1 Add `uint32_t announce_stamp` to `callsign_entry_t`; zeroed by the existing
      `hash_table_init` memset, no further change needed there.
- [x] 1.2 Stamp `announce_stamp` in `hash_table_add` only — both the already-known re-announcement
      branch and the genuinely-new-insert branch — never in `hash_table_lookup` (design.md D2).
- [x] 1.3 Add `hash_table_count_h12_multiplicity`, a wholly separate, read-only function replaying
      `hash_table_lookup`'s own probe derivation to count matches and locate the
      most-recently-announced one (design.md D1). Confirmed by inspection and by ROW 0b's
      empirical result that `hash_table_lookup` itself is byte-for-byte unchanged in behaviour.
- [x] 1.4 Wire the count into `cb_lookup_hash`'s existing 12-bit branch, into per-message
      thread-local scratch reset before `ftx_message_decode` and read only once the message is
      unconditionally headed for `results[]` (design.md D3, TRAP 3).
- [x] 1.5 Add the three process-global counters and their getters
      (`ft8_get_h12_displaying_count`/`_ambiguous_count`/`_divergent_count`).

### 2. Native Shim — Version Bump

- [x] 2.1 `FT8_SHIM_VERSION` `20260046` → `20260047`, with a changelog entry naming the mechanism
      and its MEASURE-ONLY guarantee.

### 3. Binary Rebuild

- [x] 3.1 Windows x64 (MSVC 19.44.35223): SHA256
      `37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26`.
- [x] 3.2 Linux x64 (GCC 14.2.0, WSL2 Debian): SHA256
      `4970ec5fcc37e0ab291b4d3442b1f91b0fab5f982cc4703f19bc8764cf58384e`.
- [~] 3.3 macOS ARM64 — standing CI-owned deferral, not a finding. NOT rebuilt locally (no Mac
      available), same limitation every prior native change in this project has recorded. CI's
      `macos-latest` leg rebuilds from source and auto-commits on the eventual push.
- [x] 3.4 `libft8.version.txt` updated with both SHA256 values, mechanism summary, and the
      dumpbin/nm export-count confirmation (nineteen exports, sixteen pre-existing + three new).

### 4. Managed Interop

- [x] 4.1 `IFt8NativeInterop.cs`: three new members
      (`GetH12DisplayingCount`/`GetH12AmbiguousCount`/`GetH12DivergentCount`).
- [x] 4.2 `Ft8LibInterop.cs`: three `DllImport`s + public wrappers + `ExpectedShimVersion` →
      `20260047` + changelog comment.
- [x] 4.3 `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`: pass-through wrappers.
- [x] 4.4 All 11 `IFt8NativeInterop` implementers under `tests/OpenWSFZ.Ft8.Tests/`: fixed-zero
      stubs for the three new members (compile-breaking change otherwise).
- [x] 4.5 Per-cycle log line added, cumulative not delta, explicit even when all-zero, matching
      `hashTableRejectCount`'s existing logging convention.

### 5. New Test

- [x] 5.1 `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs` added, mirroring
      `HashTableRejectCountLoggingTests.cs`: one test for the log line appearing with all three
      values, one test for all-zero counts logged explicitly.

### 6. Build and Test

- [x] 6.1 Local Windows build: 0 errors.
- [x] 6.2 `dotnet test` full suite: `OpenWSFZ.Ft8.Tests` 319/319 green (four independent
      confirmations across the session — Developer, cross-check, dirty-tree, post-commit
      clean-tree).
- [x] 6.3 `git diff --stat` against `main`: touches only the files in sections 1-5, plus the
      hand-built binaries — 24 files total, cross-checked and approved before commit.

### 7. QA ROW 0 (Amendment 1's pre-merge reordering, then the full seven-row gate)

- [x] 7.1 Committed the 24-file diff (`3b9f960`) at the Captain's explicit authorisation, per
      Amendment 1's precondition that ROW 0 needs an empty `git diff --stat` at run start.
- [x] 7.2 Pinned the `INST` SHA256 (`37cbb4ac...`) into the ROW 0 manifest; `BASE` stayed
      `bc8efcf1...` (`fix-negative-time-offset-snr-collapse`'s own pin, unchanged).
- [x] 7.3 Ran ROW 0a-0f (binary identity, both independent non-perturbation comparators,
      counter-arithmetic identity, denominator/emission-site bounds, static increment-site
      verification, determinism across two INST replays, NFR-021) on `S-17M` (1,856 cycles).
      **ALL SEVEN ROWS PASS**, 2026-08-30 15:39Z
      (`qa/rr-study/2026-08-30-1735-qa-to-architect-f001-sup-b-row0-result.md`).
- [x] 7.4 **Result superseded, not falsified, by Phase 2 (see design.md's Migration Plan):** a new
      shim version voids `0a`/`0b` by construction; Phase 2's own ROW 0 must re-run in full before
      any reading leg may run. Recorded here so this task list does not read as though Phase 1's
      pass licenses skipping Phase 2's re-run.

## Phase 2 — per-code cluster table (Amendment 2, spec'd, dev-task authored, NOT YET BUILT)

*Dev-task: `dev-tasks/2026-08-30-sup-b-amendment2-h12-cluster-table.md`, authored from the
execution pack's Sec.C2. Blocked on a Captain-opened Developer session (HK-011) — not started as of
this document.*

### 8. Native Shim

- [x] 8.1 Add the fixed 4,096×3 static table (`g_h12_by_code_displaying`/`_ambiguous`/`_divergent`)
      and the `g_h12_code_out_of_range` counter, beside the three existing scalars.
- [x] 8.2 Add `tls_h12_code`, set unconditionally inside `cb_lookup_hash`'s existing 12-bit branch
      (dev-task §1.2).
- [x] 8.3 Add the table increments inside the existing, UNCHANGED emission-site guard, masking
      defensively (`c = code & 0xFFF`) and counting any out-of-range violation rather than silently
      absorbing it (design.md D4).
- [x] 8.4 Add `ft8_get_h12_by_code`, returning `4096` on success or `-1` on any bad argument
      (capacity or NULL pointer, `out_of_range` included).

### 9. Native Shim — Version Bump

- [x] 9.1 `FT8_SHIM_VERSION` `20260047` → `20260048`, with a changelog entry naming the mechanism
      and confirming no C# binding exists for the new export.

### 10. Binary Rebuild

- [x] 10.1 Windows x64 rebuild; record SHA256. `e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626
      fe6a8799fa84e33e` (MSVC 19.44.35223, matches the 20260047 pass's own compiler exactly).
- [x] 10.2 Linux x64 rebuild (WSL2 Debian); record SHA256. `4686a4f7eec31d2190c545586d39d95cab6e10e
      0758fbb59f7fab44e77498b62` (GCC 14.2.0, matches the 20260047 pass's own compiler exactly).
- [~] 10.3 macOS ARM64 — standing CI-owned deferral, not a finding. Same "not rebuilt locally"
      deferral as every prior native change; CI rebuilds it on the eventual push.
- [x] 10.4 `libft8.version.txt` (`win-x64/`, the actual on-disk location — dev-task §0 corrects the
      execution pack's own cited path) updated with both SHA256 values and the dumpbin/nm
      twenty-export confirmation.

### 11. Managed Interop — ONE constant, nothing else

- [x] 11.1 `Ft8LibInterop.cs` line 385, `ExpectedShimVersion` → `20260048`, plus its changelog
      comment. **Confirm via `git diff --stat` that no other line in this file changed, and that
      `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`, and all 11 implementers
      do not appear in the diff at all** — this is the acceptance criterion for the "ft8lib-interop"
      spec delta's own "No managed binding exists for the export" scenario. Confirmed: `git diff`
      on this file shows only the one `ExpectedShimVersion` line plus its new `<remarks>` block;
      none of the four named files appear anywhere in `git status --short`.

### 12. Native Build — Export List

- [x] 12.1 `rebuild_shim.bat`: one new `/EXPORT:ft8_get_h12_by_code` line (twenty exports total).
- [x] 12.2 `BUILD.md`: the matching one-line addition only — do NOT backfill its pre-existing,
      unrelated `ft8_get_last_snr_terms` omission as part of this diff (design.md Risks).

### 13. Build and Test

- [x] 13.1 Local build (Windows at minimum) succeeds with no unresolved P/Invoke entry points.
      `dotnet build OpenWSFZ.slnx -c Release`: 0 Warning(s), 0 Error(s).
- [x] 13.2 `dotnet test` full suite — `OpenWSFZ.Ft8.Tests` 319/319, unchanged from the 20260047
      pass (no test file added or edited by Phase 2). Two pre-existing, already-tracked flakes
      recurred in `OpenWSFZ.Daemon.Tests` (FR-064 `ExternalReportingServiceTests` and
      `CycleArchiveServiceTests`'s manifest timing test) — confirmed zero file overlap with this
      diff (native shim, interop constant, build scripts, binaries only) before treating them as
      unrelated, per this task's own instruction. All other projects green (Rig 41/41, Audio
      19/19, Config 100/100, Web 276/276, E2E 7/7, TestSupport 9/9, TraceabilityCheck 34/34,
      LicenseInventoryCheck 24/24). Full detail in `libft8.version.txt`'s new entry.
- [x] 13.3 `git diff --stat` against the branch HEAD at Phase 2's start (`5c01d60`) touches only the
      eight files the execution pack Sec.C2 and this change's `ft8lib-interop` spec delta name —
      nothing else.
- [x] 13.4 Commit on `qa/sup-b-2026-08-30`. Does not push, does not merge, does not run
      `pre_merge_check.py` (HK-006/HK-011/HK-014).

### 14. QA — extend the harness and evaluator (qa-tooling, HK-011 does not apply)

- [~] 14.1 Bind `ft8_get_h12_by_code` in `g3_h12_replay.py`'s `build_decoder()`, conditional on
      `shim_version >= 20260048` (BASE has none of these exports) — no bare `try/except` around the
      bind (execution pack Sec.C3.2).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
- [~] 14.2 Read the table ONCE, at end of run — never per cycle (execution pack Sec.C3.2, the
      ~90 MB-per-leg cost of doing otherwise).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
- [~] 14.3 Extend `row0_evaluate_s17m.py` with `0c-ii` (code-width invariant, evaluated FIRST —
      design.md D4) and `0c-iii` (table↔scalar reconciliation, three exact equalities), and widen
      `0e` to diff the full table between two INST replays (execution pack Sec.C4).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
- [~] 14.4 Pin the bootstrap exactly as specified (execution pack Sec.C5): `default_rng(20260830)`,
      10,000 draws, percentile method, point estimate = the lookup-weighted `S`/`D`, not the mean of
      the draws; assert no degenerate draw is possible; run the bootstrap twice and byte-compare the
      bounds.
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.

### 15. QA — pin the manifest and re-run ROW 0 in full

- [~] 15.1 Pin the new `INST` SHA256 into the ROW 0 manifest (Sec.4); confirm `git diff --stat` is
      empty at run start (the same precondition that cost this arm a session once already).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
- [~] 15.2 Run ROW 0a through 0f, in the amended strict order (`0a, 0b, 0c, 0c-ii, 0c-iii, 0d-i,
      0d-ii, 0e, 0f`), on `S-17M` — BASE ×1, INST ×2. A FAIL at any row stops the run; no partial
      evaluation (HK-021/HK-025).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
- [~] 15.3 **HARD STOP.** Captain reviews the diff and the ROW 0 result together and rules on the
      merge (HK-010). No push, no merge, no `pre_merge_check.py` before this review.
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands. (The Captain's actual merge
      review for the shipped mechanism happened under `f001-h12-unique-match-suppression`
      §9.1, not here — that change carries the real HK-010 sign-off.)

### 16. QA — reading legs (blocked on task 15's Captain review)

- [~] 16.1 Evaluate ROW 0g (`N >= 30` distinct participating codes) per band, BEFORE that band's
      interval — a band that fails gets no verdict, not a wider or caveated one, and may not be
      pooled with another band to reach 30.
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
- [~] 16.2 Run the `S-80M` and `S-20M` reading legs; compute `S-17M`'s reading from the ROW 0 INST
      run itself (no fourth leg needed — execution pack Sec.C6).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands. **These legs did not run; this
      is not a measurement claim.**
- [~] 16.3 Apply Sec.6.4's verdict table per band, `MARGINAL` evaluated first and governing,
      escalating to the Product Owner rather than auto-triggering any narrower rule. Report all
      three bands as independent verdicts — never pooled (Sec.6.3).
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — per-band sizing has no
      consequence once suppression is unconditional on all bands. The PO's actual ruling *is*
      the disposition of the step-7 MARGINALs: Option A, unconditional on all bands, escalation
      closed (see `78713b8`, `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`).
- [~] 16.4 Decide, at the Product Owner's ruling (not QA's), whether `S-17M` counts as this
      programme's third independent reading band, per design.md's Open Question 1.
      SUPERSEDED by PO Option A ruling 2026-09-01 (`78713b8`) — moot once per-band reading legs
      themselves are superseded; no third-band question remains to decide.

## 17. Spec Sync

- [x] 17.1 Once Phase 2 lands and this change is ready to archive, merge this change's
      `specs/hashed-callsign-resolution/spec.md` delta into
      `openspec/specs/hashed-callsign-resolution/spec.md` (both Phase 1 and Phase 2 Requirements —
      Phase 1's is already true today and may be merged independently of Phase 2 landing, at QA's
      discretion, to stop understating the tracked spec surface in the meantime).
      **Done, evidence:** merged 2026-09-02 under `qa/2026-09-02-1521-…` Task C.2 — both Phase 1
      ("Observable 12-bit hash-path unique-match sizing") and Phase 2 ("Observable 12-bit hash-path
      per-code cluster identity") Requirements appended to
      `openspec/specs/hashed-callsign-resolution/spec.md`.
- [x] 17.2 Merge this change's `specs/ft8lib-interop/spec.md` delta into
      `openspec/specs/ft8lib-interop/spec.md`, confirming the merged ABI self-test history reads
      `20260046` → `20260047` → `20260048` in order, matching the base file's existing convention
      (established by the `fix-negative-time-offset-snr-collapse`/`r2-coherent-llr-instrument`
      merges) of keeping intermediate version history present, not just the final entry.
      **Done, evidence:** merged 2026-09-02 under `qa/2026-09-02-1521-…` Task C.2 — ABI self-test
      Requirement's expected constant advanced to `20260048`, history prose extended (not
      rewritten) to record `20260047`/`20260048`, new "Previous library (20260047)"/"Previous
      library (20260046)" scenarios added alongside the existing older ones; both Phase 1/Phase 2
      diagnostic-getter Requirements appended. `grep -c 20260047`/`20260048` on the merged file both
      `>= 1` (§6 gate of the same QA spec).
- [x] 17.3 `openspec validate --strict --all` passes after both merges.
      **Done, evidence:** `openspec validate --strict --all` → 62 passed, 0 failed, immediately
      after both merges, before archiving this change.

## 18. Housekeeping

- [x] 18.1 Update `MEMORY.md`/`BOARD.md` to record this change's opening (the retrofit itself,
      Captain-directed) and, once Phase 2 lands, its own result — distinct from Phase 1's already-
      recorded 15:39Z result, which this change's task 7.4 marks superseded rather than wrong.
      **Done** — as part of `qa/2026-09-02-1521-…` Task I (BOARD.md/MEMORY.md updated in the same
      pass as this archive).
- [x] 18.2 Once this change is fully landed and archived (`opsx:archive`), confirm the archived
      `openspec/changes/archive/<date>-f001-sup-b-instrumented-suppression-sizing/` entry is the
      canonical record — no `openspec/changes/` gap remains for either phase's native ABI surface.
      **Done, evidence:** archived to
      `openspec/changes/archive/2026-09-02-f001-sup-b-instrumented-suppression-sizing/`;
      `openspec validate --strict --all` passes with this change no longer listed under
      `openspec/changes/` (only `f001-h12-unique-match-suppression` remains, archived next in the
      same QA spec's Task D).
