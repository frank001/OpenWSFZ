*Process note: tasks 1–6 are the **Developer session's** (HK-011 — a `src/` + native change is not
QA's to start). Tasks 7–8 are **QA's** (`qa/` tooling, HK-011 does not apply to it). Task 9 is a hard
stop for the **Captain** (HK-010). Tasks 10–11 follow the merge. Design authority is `design.md`;
decision authority is `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`.*

## 1. Native Shim — the suppression rule

- [x] 1.1 Add a thread-local suppression flag beside the existing 12-bit scratch state; reset it with
      the rest of that scratch before each message's text decode, so it can never leak between
      messages (`SUP-B` TRAP 3's own reset bracket).
      **Done, evidence:** `b616b6d` — `tls_h12_suppressed` added (`ft8_shim.c`, beside
      `tls_h12_code`), reset `false` in the same per-message bracket as
      `tls_h12_lookup_performed` (`ft8_shim.c:1636`, comment: "same bracket, so it can never leak
      between messages").
- [x] 1.2 In `cb_lookup_hash`, inside the existing 12-bit branch **only**, set that flag when the
      probe-chain multiplicity is ≥ 2, and return *resolved AND NOT suppressed*. Leave the
      `hash_table_lookup` call and its output buffer exactly as they are — **do not clear the
      buffer** (design D1).
      **Done, evidence:** `b616b6d` — `tls_h12_suppressed = (tls_h12_multiplicity >= 2)` inside the
      `if (t == FTX_CALLSIGN_HASH_12_BITS)` branch's `found` sub-branch; final line changed from
      `return found;` to `return found && !tls_h12_suppressed;`; `cs`/the lookup buffer untouched
      per the adjacent comment.
- [x] 1.3 Confirm by inspection that `hash_table_lookup`, `hash_table_add` and `announce_stamp` are
      untouched (TRAP 1 / TRAP 2), and that the 22-bit and 10-bit paths are untouched (design D2).
      **Done, evidence:** `b616b6d`'s diff touches only `ft8_shim.c`/`.h` — `native/ft8_lib_vendor/`
      diff is empty (independently re-verified by the QA reviewer per the board's 2026-09-01 23:14Z
      entry); `hash_table_lookup`'s call and return path is marked "UNCHANGED return path — TRAP 1"
      in the diff itself.
- [x] 1.4 Add the process-lifetime suppressed counter and its read-only getter
      `ft8_get_h12_suppressed_count`, following the three existing 12-bit getters' pattern.
      **Done, evidence:** `b616b6d` — `static int g_h12_suppressed = 0;` and
      `int ft8_get_h12_suppressed_count(void) { return g_h12_suppressed; }` (`ft8_shim.c`).
- [x] 1.5 🔴 Increment that counter **in the emission block**, beside its three siblings — **never in
      the callback** (design D4: the callback would count decode attempts, not displays).
      **Done, evidence:** `b616b6d` — `if (tls_h12_suppressed) g_h12_suppressed++;` sits in the
      emission block (`ft8_shim.c:1654`) directly beside the `g_h12_displaying`/`g_h12_ambiguous`/
      `g_h12_divergent` increments, not inside `cb_lookup_hash`.
- [x] 1.6 🔴 Verify the existing displaying / ambiguous / divergent counters and the per-code cluster
      table are **byte-for-byte unchanged**, and that the "resolved" thread-local still reflects the
      table's own result rather than the suppression decision (design D3).
      **Done, evidence:** `b616b6d`'s diff leaves `g_h12_displaying++`/`g_h12_ambiguous`/
      `g_h12_divergent` lines and the cluster-table block untouched; `tls_h12_resolved = found` is
      unchanged and the diff's own comment states this explicitly ("unchanged meaning, NOT gated on
      suppression — SUP-B's counters depend on this"). AC-4 (`27d9c6a`, 847 == 847) is the
      behavioural confirmation this held on the full corpus.

## 2. Native Shim — Version Bump

- [x] 2.1 `FT8_SHIM_VERSION` `20260048` → `20260049`, with a changelog entry naming the mechanism and
      stating plainly that — unlike `20260047` and `20260048` — **this bump changes decode output**.
      **Done, evidence:** `b616b6d` — `ft8_shim.h` history block gains the `20260049` entry;
      `win-x64/libft8.version.txt` gains the full narrative including "UNLIKE 20260047/20260048,
      THIS BUMP CHANGES DECODE OUTPUT." `ExpectedShimVersion` bumped to match in
      `Ft8LibInterop.cs`.

## 3. Binary Rebuild

- [x] 3.1 🔴 Add `ft8_get_h12_suppressed_count` to the Windows build's explicit `/EXPORT:` list
      (`native/ft8_lib_build/rebuild_shim.bat`). Omitting it builds and links clean on Linux and
      fails only on Windows, only at runtime (design D5).
      **Done, evidence:** `b616b6d` — `/EXPORT:ft8_get_h12_suppressed_count` added to
      `rebuild_shim.bat`'s link step.
- [x] 3.2 Rebuild Windows x64; record the compiler version and the binary's SHA256.
      **Done, evidence:** `b616b6d` — `win-x64/libft8.version.txt`: MSVC 19.44.35223, SHA256
      `ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e`; re-hashed independently by
      the QA reviewer and matched (board, 2026-09-01 23:14Z entry).
- [x] 3.3 Rebuild Linux x64; record the toolchain and the binary's SHA256.
      **Done, evidence:** `b616b6d` — `win-x64/libft8.version.txt`: GCC 14.2.0 via WSL2 Debian,
      SHA256 `d6aa3d6164d3d9b1f8f01f08a627da66ec6298af30a2bbd4ac17460bfde55eae`; `nm -D` confirmed
      all 21 exported symbols present, only the one new getter added; independently re-hashed by
      the QA reviewer and matched.
- [~] 3.4 macOS ARM64 — **deferred, standing project-wide policy, not a finding.** Not rebuilt
      locally (no Mac available); CI's `macos-latest` leg rebuilds from source and auto-commits on
      the first push that changes native sources, per every prior native change in this project's
      history. `win-x64/libft8.version.txt` records this explicitly for this bump. 🛑 Expected and
      permanent on a Windows box — do not raise as a new finding (standing memory rule).

## 4. Managed Interop

- [x] 4.1 `ExpectedShimVersion` `20260048` → `20260049`.
      **Done, evidence:** `b616b6d` — `Ft8LibInterop.cs:405`.
- [x] 4.2 Add `GetH12SuppressedCount()` to `IFt8NativeInterop`, `Ft8LibInterop` and
      `Ft8NativeInteropAdapter`, mirroring the three existing 12-bit getters.
      **Done, evidence:** `b616b6d` — `IFt8NativeInterop.cs` (interface member),
      `Ft8LibInterop.cs` (`NativeGetH12SuppressedCount` P/Invoke + public wrapper),
      `Ft8NativeInteropAdapter.cs` (`GetH12SuppressedCount() => Ft8LibInterop.GetH12SuppressedCount();`).
- [x] 4.3 Add the suppressed count to `Ft8Decoder`'s existing per-cycle 12-bit hash-path log line.
      **Done, evidence:** `b616b6d` — `Ft8Decoder.cs`: `GetH12SuppressedCount()` public wrapper
      added, and the per-cycle `LogInformation` call extended with `h12Suppressed={H12Suppressed}`.
- [x] 4.4 Add a fixed-zero stub to every other `IFt8NativeInterop` implementer. ⚠️ **Enumerate them
      by search, do not trust a remembered count** — 13 files declared an implementation on
      `main`@`68a014d` (12 in `tests/` plus the production adapter), and the `SUP-B` proposal's
      "11 implementers" is stale.
      **Done, evidence:** `b616b6d` — the diff touches all 12 `tests/OpenWSFZ.Ft8.Tests/*.cs` files
      declaring `IFt8NativeInterop` (`AvContainmentTests.cs`, `CoherentLlrAtTests.cs`,
      `D005MessageTrimTests.cs`, `D009FpFilterTests.cs`,
      `D011NonstandardCallsignFpGuardTests.cs`, `GetLastSnrTermsTests.cs`,
      `H12InstrumentationLoggingTests.cs`, `HashTableRejectCountLoggingTests.cs`,
      `HashedCallsignResolutionTests.cs`, `RefineCandidateTests.cs`, `RegionLookupTests.cs`,
      `SetDecodeParamsTests.cs`, `WorkedBeforeLookupTests.cs`) — 13 files including the production
      adapter, matching the pre-verified count exactly.

## 5. New Tests

- [x] 5.1 Ambiguous chain ⇒ suppressed: seed the table so two **Q-prefix synthetic** callsigns
      (e.g. `Q1ABC`, `Q2XYZ`) collide on one 12-bit code, then assert the decoded text renders
      `<...>` and contains **neither** candidate.
      **Done, evidence:** `b616b6d` —
      `HashedCallsignResolutionTests.AmbiguousH12Chain_SuppressesCallsign_DecodeSurvives`, using
      `FindEmptyColliding12BitPair` and Q-prefix synthetic calls (`Q1H12B0000`/`Q1H12B0001`-shaped).
      Asserts `<...>` present, neither candidate present, suppressed-counter delta == 1.
- [x] 5.2 Unique match ⇒ still resolves: a 12-bit code with exactly one matching entry renders the
      callsign exactly as before this change.
      **Done, evidence:** `b616b6d` —
      `HashedCallsignResolutionTests.UniqueH12Match_StillRendersResolvedCallsign`.
- [x] 5.3 Demonstrate 5.1 is **capable of failing** — temporarily invert or disable the predicate,
      confirm the test goes RED, then revert. A test that has never been seen to fail is not evidence.
      **Done, evidence:** `b616b6d` commit message: "the ambiguous test was demonstrated RED under a
      temporarily-broken predicate before the real fix was restored (task 7.4)" [dev-task's own
      numbering, not this file's].
- [x] 5.4 Pin the per-cycle log line's new field.
      **Done, evidence:** `b616b6d` —
      `H12InstrumentationLoggingTests.cs` extended: `FixedH12CountsInterop` gains a `suppressed`
      parameter, both existing log-line tests assert `h12Suppressed`/`h12Suppressed=0` present
      alongside the three pre-existing fields.
- [x] 5.5 🔒 NFR-021: confirm every fixture, assertion and comment added uses Q-prefix synthetic
      callsigns only.
      **Done, evidence:** `b616b6d` diff uses only `Q1H12A…`/`Q1H12B…`/`Q1H12PROBE` synthetic
      callsigns throughout the new test code. QA review (board, 2026-09-01 23:14Z entry) flagged
      that the scanner tool itself (`nfr021_pre_merge_scan.py`) skips `.cs`/`.h` and so never
      mechanically scanned these files, but manually verified the two `.cs` files carrying the new
      literal callsigns clean — the scanner-coverage gap is a separate, already-raised tooling
      finding (see this branch's own §8), not a defect in this task.

## 6. Build and Test (Developer session)

- [x] 6.1 Full solution build, Release.
      **Done, evidence:** `b616b6d` commit message + board 2026-09-01 23:14Z entry: full
      `dotnet build`/`OpenWSFZ.Ft8.Tests` re-run independently by the QA reviewer.
- [x] 6.2 Full test suite green. Note any pre-existing failures explicitly as pre-existing —
      re-run them on the unmodified base commit before claiming so, rather than asserting it.
      **Done, evidence:** `b616b6d` commit message — 1748/1749 passed; the one failure
      (`CycleArchiveServiceTests.RepeatedCycleLabel_ProducesTwoDistinctFiles`) reproduced
      identically on unmodified `main`@`68a014d` in a worktree, zero file overlap with this diff.
      Board's 2026-09-01 23:14Z QA-review entry independently re-ran the full suite: 321/321 for
      `OpenWSFZ.Ft8.Tests`.
- [x] 6.3 Gate G10 (`check_test_delay_sync.py`) OK; **no new `Task.Delay(...)`** anywhere in the diff.
      **Done, evidence:** board 2026-09-01 23:14Z QA-review entry: "G10 OK".
- [x] 6.4 `openspec validate --strict --all` passes.
      **Done, evidence:** board 2026-09-01 23:14Z QA-review entry: "`openspec validate` 63/0".
- [x] 6.5 NFR-021 scan **post-commit** (the scan misses uncommitted files — commit first, then scan).
      **Done, evidence:** board 2026-09-01 23:14Z QA-review entry, finding (1): scanner run
      post-commit, found to have skipped `.cs`/`.h` (a tool-coverage gap, separately tracked), the
      two `.cs` files with new literal callsigns manually verified clean.
- [x] 6.6 🛑 **STOP.** No push, no merge, no `pre_merge_check.py` (HK-006 — Captain's initiative only).
      **Done, evidence:** `b616b6d` commit message: "Per HK-011/HK-014: builds and tests only, no
      push, no merge, no pre_merge_check.py. Captain review pending before any push." — branch
      remained local and unpushed until the Captain's later ruling (§9).

## 7. QA — replay harness

- [x] 7.1 Pin the new binary's SHA256 into the replay manifest **after** the rebuild, never before.
      **Done, evidence:** `27d9c6a` — `g4_h12_suppression_replay.py` computes and records
      `dll_sha256` from the actual candidate binary at replay time (`P.dll_sha256(args.dll_path)`).
- [x] 7.2 Produce a pre-change baseline run of the `S-17M` corpus at `20260048`, if one is not already
      on disk. ⚠️ Check `qa/ARTEFACT_INVENTORY.md` before generating anything — this corpus has been
      replayed before.
      **Done, evidence:** `27d9c6a` — `g4_h12_suppression_replay.py`'s own header comment: the BASE
      (20260048) leg did not need to be re-run because SUP-B's own ROW 0 Amendment-2 run already
      produced a full S-17M decode set at shim 20260048; reused rather than regenerated (HK-018).
- [x] 7.3 Replay the same corpus at `20260049` and diff the two outputs line by line.
      **Done, evidence:** `27d9c6a` — `g4_h12_suppression_replay.py` (candidate leg, full S-17M
      corpus, 1,856 cycles) + `g4_ac_evaluate.py` (positional per-cycle decode-line diff against
      BASE, bracket-aware tokenizer). Full write-up:
      `qa/rr-study/2026-09-01-2203-qa-to-architect-f001-h12-suppression-ac1-4-result.md`.

## 8. QA — acceptance criteria

- [x] 8.1 **AC-1** decode count identical: zero decodes gained, zero lost. A non-zero delta means
      suppression is killing decodes rather than names ⇒ **STOP**, the change is wrong.
      **PASS, evidence:** `27d9c6a` — 29,696 decodes both legs, zero gained/lost.
- [~] 8.2 **AC-2** the number of differing lines **equals** the ambiguous count read from the same
      run. Any mismatch means the predicate fires somewhere other than where the instrument counted.
      **VOID BY CONSTRUCTION — see `8071391`.** Measured result was FAIL as literally written (250
      differing lines vs 847 ambiguous), but the Architect traced this to source, not a suppression
      defect: `ftx_message_encode_nonstd` (`message.c:256-261`) hard-wires `n12=0`/`iflip=0` for
      every CQ-shaped (`icq!=0`) Type-4 message, so the 12-bit field is padding, not a hash, for
      that population — `decode_nonstd` looks it up unconditionally (the only 12-bit call site) and
      discards it before rendering. AC-2's equality is unsatisfiable by construction for ANY correct
      implementation, provable from source before the run — the legitimate ground for voiding a
      pre-registered gate post-hoc. The Architect's own drafting defect (HK-021(x): gate scoped to
      "ambiguous resolutions", claim ranges over "ambiguous renderings") is recorded in `8071391`
      and self-attributed there. **Never tick `[x]` — this did not pass, it was ruled inapplicable.**
      Residual measurement replacing it: 250 rendered / 597 discarded, discard population measured
      at 925 (597 ≤ 925), rate 64.5%, contamination guard = 0 — see `8071391` and
      `qa/rr-study/architect_ac2_padding_probe.py`.
- [x] 8.3 **AC-3** every differing line differs **only** by one bracketed callsign token becoming
      `<...>`; frequency, DT, SNR and payload byte-identical. A changed numeric field means the change
      has escaped its scope.
      **PASS, evidence:** `27d9c6a` — 250/250 differing lines are clean single-token swaps to
      `<...>`, numeric fields untouched. Independently re-derived by the Architect with a separate
      bracket-aware tokenizer sharing no code with QA's evaluator (`8071391`): same 250/250, 10 line
      shapes, 0 `f`/`dt`/`snr` violations — two independent implementations agree (HK-022).
- [x] 8.4 **AC-4** suppressed count equals ambiguous count exactly.
      **PASS, evidence:** `27d9c6a` — 847 == 847, the wiring invariant design D4 predicted.
- [x] 8.5 Report the result, then **STOP** (HK-011). QA does not merge.
      **Done, evidence:** `27d9c6a` commit message: "Per HK-011/tasks.md 8.5: QA reports and stops
      here; the Captain rules on the merge. No src/ or native/ touched, no push, no
      pre_merge_check.py (HK-006)." Full write-up committed alongside, no push performed by QA.

## 9. Captain

- [x] 9.1 🛑 **HARD STOP.** The Captain reviews the diff together with the task-8 result and rules on
      the merge (HK-010). Green CI is necessary and never sufficient.
      **Done, evidence:** Captain ruled 2026-09-02 (~14:3xZ, per `BOARD.md`): merge on AC-1/AC-3/AC-4
      (Architect's Option A recommendation from `8071391` taken), then a pre-merge check, then a real
      PR through branch protection. Rehearsal `pre_merge_check.py` runs found and fixed two
      structural gates unrelated to this change's own diff (G9b VERSION bump, `cc0f5e3`; WSL Debian
      leg's missing linux-x64 publish step), final rehearsal PASS WITH WARNINGS (standing macOS
      `.dylib` WARN only). Merged via PR #138 → `main`@`47a781c`.

## 10. Spec Sync

- [ ] 10.1 🔴 **Check the archive ordering FIRST.** `f001-sup-b-instrumented-suppression-sizing` has
      **not** been spec-synced — the base `ft8lib-interop` spec still reads `20260046` and the base
      `hashed-callsign-resolution` spec carries none of the 12-bit sizing Requirements. This change's
      deltas are written against `SUP-B`'s deltas as their baseline. **Sync and archive `SUP-B`
      first**, or this change's `MODIFIED` block overwrites version history that was never recorded.
      **Not yet done as of this record correction** — this is exactly the ordering hazard this QA
      spec (`qa/2026-09-02-1521-…`) exists to handle. Covered by that spec's Task C (SUP-B
      spec-sync + archive, first) and Task D (this change's own spec-sync + archive, second).
- [ ] 10.2 Merge this change's `specs/hashed-callsign-resolution/spec.md` delta into
      `openspec/specs/hashed-callsign-resolution/spec.md`.
      **Not yet done** — Task D of `qa/2026-09-02-1521-…`, gated on 10.1/Task C completing first.
- [ ] 10.3 Merge this change's `specs/ft8lib-interop/spec.md` delta into
      `openspec/specs/ft8lib-interop/spec.md`.
      **Not yet done** — Task D of `qa/2026-09-02-1521-…`, gated on 10.1/Task C completing first.
- [ ] 10.4 `openspec validate --strict --all` passes after both merges.
      **Not yet done** — part of Task D / the §6 verification gate of `qa/2026-09-02-1521-…`.

## 11. Housekeeping

- [ ] 11.1 Update `BOARD.md` (and `MEMORY.md`'s one-line index) in the **same edit** as the merge
      result — not later, not in a topic file only (HK-024).
      **Partially done** (the merge itself is recorded on `BOARD.md`); **this task's own
      spec-archival housekeeping is Task I of `qa/2026-09-02-1521-…`**, done in the same pass as
      this record correction.
- [ ] 11.2 Branch hygiene (HK-003): delete merged branches and any worktrees created for this change.
      **Not yet done** — covered by Task H of `qa/2026-09-02-1521-…` (branch/worktree sweep).
- [ ] 11.3 Confirm the archived change validates after `opsx:archive`.
      **Not yet done** — this change has not been archived yet; Task D of
      `qa/2026-09-02-1521-…` performs the archive and its own `openspec validate` gate confirms it.
- [ ] 11.4 Open, separately: whether any downstream consumer (ADIF log, decode-panel filtering, QSO
      answerer) is sensitive to `<...>` becoming **more frequent**. The placeholder already occurs
      today, so the path is exercised — but its frequency changes here and nobody has checked
      (design, Open Questions).
      **Genuinely open** — not discharged by anything on `main`. Left `[ ]` on purpose: this is a
      real follow-up, not a record gap. Carried forward, not this QA spec's to resolve.
