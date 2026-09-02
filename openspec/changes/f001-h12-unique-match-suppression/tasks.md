*Process note: tasks 1–6 are the **Developer session's** (HK-011 — a `src/` + native change is not
QA's to start). Tasks 7–8 are **QA's** (`qa/` tooling, HK-011 does not apply to it). Task 9 is a hard
stop for the **Captain** (HK-010). Tasks 10–11 follow the merge. Design authority is `design.md`;
decision authority is `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`.*

## 1. Native Shim — the suppression rule

- [ ] 1.1 Add a thread-local suppression flag beside the existing 12-bit scratch state; reset it with
      the rest of that scratch before each message's text decode, so it can never leak between
      messages (`SUP-B` TRAP 3's own reset bracket).
- [ ] 1.2 In `cb_lookup_hash`, inside the existing 12-bit branch **only**, set that flag when the
      probe-chain multiplicity is ≥ 2, and return *resolved AND NOT suppressed*. Leave the
      `hash_table_lookup` call and its output buffer exactly as they are — **do not clear the
      buffer** (design D1).
- [ ] 1.3 Confirm by inspection that `hash_table_lookup`, `hash_table_add` and `announce_stamp` are
      untouched (TRAP 1 / TRAP 2), and that the 22-bit and 10-bit paths are untouched (design D2).
- [ ] 1.4 Add the process-lifetime suppressed counter and its read-only getter
      `ft8_get_h12_suppressed_count`, following the three existing 12-bit getters' pattern.
- [ ] 1.5 🔴 Increment that counter **in the emission block**, beside its three siblings — **never in
      the callback** (design D4: the callback would count decode attempts, not displays).
- [ ] 1.6 🔴 Verify the existing displaying / ambiguous / divergent counters and the per-code cluster
      table are **byte-for-byte unchanged**, and that the "resolved" thread-local still reflects the
      table's own result rather than the suppression decision (design D3).

## 2. Native Shim — Version Bump

- [ ] 2.1 `FT8_SHIM_VERSION` `20260048` → `20260049`, with a changelog entry naming the mechanism and
      stating plainly that — unlike `20260047` and `20260048` — **this bump changes decode output**.

## 3. Binary Rebuild

- [ ] 3.1 🔴 Add `ft8_get_h12_suppressed_count` to the Windows build's explicit `/EXPORT:` list
      (`native/ft8_lib_build/rebuild_shim.bat`). Omitting it builds and links clean on Linux and
      fails only on Windows, only at runtime (design D5).
- [ ] 3.2 Rebuild Windows x64; record the compiler version and the binary's SHA256.
- [ ] 3.3 Rebuild Linux x64; record the toolchain and the binary's SHA256.
- [ ] 3.4 macOS ARM64 — not rebuilt locally (no Mac available); CI's `macos-latest` leg owns it, as on
      every prior native change. The local pre-merge warning about this is expected, not a finding.

## 4. Managed Interop

- [ ] 4.1 `ExpectedShimVersion` `20260048` → `20260049`.
- [ ] 4.2 Add `GetH12SuppressedCount()` to `IFt8NativeInterop`, `Ft8LibInterop` and
      `Ft8NativeInteropAdapter`, mirroring the three existing 12-bit getters.
- [ ] 4.3 Add the suppressed count to `Ft8Decoder`'s existing per-cycle 12-bit hash-path log line.
- [ ] 4.4 Add a fixed-zero stub to every other `IFt8NativeInterop` implementer. ⚠️ **Enumerate them
      by search, do not trust a remembered count** — 13 files declared an implementation on
      `main`@`68a014d` (12 in `tests/` plus the production adapter), and the `SUP-B` proposal's
      "11 implementers" is stale.

## 5. New Tests

- [ ] 5.1 Ambiguous chain ⇒ suppressed: seed the table so two **Q-prefix synthetic** callsigns
      (e.g. `Q1ABC`, `Q2XYZ`) collide on one 12-bit code, then assert the decoded text renders
      `<...>` and contains **neither** candidate.
- [ ] 5.2 Unique match ⇒ still resolves: a 12-bit code with exactly one matching entry renders the
      callsign exactly as before this change.
- [ ] 5.3 Demonstrate 5.1 is **capable of failing** — temporarily invert or disable the predicate,
      confirm the test goes RED, then revert. A test that has never been seen to fail is not evidence.
- [ ] 5.4 Pin the per-cycle log line's new field.
- [ ] 5.5 🔒 NFR-021: confirm every fixture, assertion and comment added uses Q-prefix synthetic
      callsigns only.

## 6. Build and Test (Developer session)

- [ ] 6.1 Full solution build, Release.
- [ ] 6.2 Full test suite green. Note any pre-existing failures explicitly as pre-existing —
      re-run them on the unmodified base commit before claiming so, rather than asserting it.
- [ ] 6.3 Gate G10 (`check_test_delay_sync.py`) OK; **no new `Task.Delay(...)`** anywhere in the diff.
- [ ] 6.4 `openspec validate --strict --all` passes.
- [ ] 6.5 NFR-021 scan **post-commit** (the scan misses uncommitted files — commit first, then scan).
- [ ] 6.6 🛑 **STOP.** No push, no merge, no `pre_merge_check.py` (HK-006 — Captain's initiative only).

## 7. QA — replay harness

- [ ] 7.1 Pin the new binary's SHA256 into the replay manifest **after** the rebuild, never before.
- [ ] 7.2 Produce a pre-change baseline run of the `S-17M` corpus at `20260048`, if one is not already
      on disk. ⚠️ Check `qa/ARTEFACT_INVENTORY.md` before generating anything — this corpus has been
      replayed before.
- [ ] 7.3 Replay the same corpus at `20260049` and diff the two outputs line by line.

## 8. QA — acceptance criteria

- [ ] 8.1 **AC-1** decode count identical: zero decodes gained, zero lost. A non-zero delta means
      suppression is killing decodes rather than names ⇒ **STOP**, the change is wrong.
- [ ] 8.2 **AC-2** the number of differing lines **equals** the ambiguous count read from the same
      run. Any mismatch means the predicate fires somewhere other than where the instrument counted.
- [ ] 8.3 **AC-3** every differing line differs **only** by one bracketed callsign token becoming
      `<...>`; frequency, DT, SNR and payload byte-identical. A changed numeric field means the change
      has escaped its scope.
- [ ] 8.4 **AC-4** suppressed count equals ambiguous count exactly.
- [ ] 8.5 Report the result, then **STOP** (HK-011). QA does not merge.

## 9. Captain

- [ ] 9.1 🛑 **HARD STOP.** The Captain reviews the diff together with the task-8 result and rules on
      the merge (HK-010). Green CI is necessary and never sufficient.

## 10. Spec Sync

- [ ] 10.1 🔴 **Check the archive ordering FIRST.** `f001-sup-b-instrumented-suppression-sizing` has
      **not** been spec-synced — the base `ft8lib-interop` spec still reads `20260046` and the base
      `hashed-callsign-resolution` spec carries none of the 12-bit sizing Requirements. This change's
      deltas are written against `SUP-B`'s deltas as their baseline. **Sync and archive `SUP-B`
      first**, or this change's `MODIFIED` block overwrites version history that was never recorded.
- [ ] 10.2 Merge this change's `specs/hashed-callsign-resolution/spec.md` delta into
      `openspec/specs/hashed-callsign-resolution/spec.md`.
- [ ] 10.3 Merge this change's `specs/ft8lib-interop/spec.md` delta into
      `openspec/specs/ft8lib-interop/spec.md`.
- [ ] 10.4 `openspec validate --strict --all` passes after both merges.

## 11. Housekeeping

- [ ] 11.1 Update `BOARD.md` (and `MEMORY.md`'s one-line index) in the **same edit** as the merge
      result — not later, not in a topic file only (HK-024).
- [ ] 11.2 Branch hygiene (HK-003): delete merged branches and any worktrees created for this change.
- [ ] 11.3 Confirm the archived change validates after `opsx:archive`.
- [ ] 11.4 Open, separately: whether any downstream consumer (ADIF log, decode-panel filtering, QSO
      answerer) is sensitive to `<...>` becoming **more frequent**. The placeholder already occurs
      today, so the path is exercised — but its frequency changes here and nobody has checked
      (design, Open Questions).
