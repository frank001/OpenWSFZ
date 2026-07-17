## 1. Branch

- [x] 1.1 Create and check out branch `fix/adif-partner-grid-capture` from `main`.

## 2. TryParseResponder — surface the grid it already parses

- [x] 2.1 Extend `QsoCallerService.TryParseResponder`'s signature
  (`QsoCallerService.cs:1187-1228`) with a new `out string? grid` parameter, set as
  `grid = isGrid ? thirdToken : null;` right where `isGrid` is already computed — no new
  parsing logic.
- [x] 2.2 Update the `None`-mode auto-track call site (`QsoCallerService.cs:695`, which only
  records into `_recentResponderDecodes` and doesn't need the grid) to pass `out _` for the new
  parameter, matching the existing pattern for `freqHz`.

## 3. Thread the grid through the `First`-mode auto-engage path

- [x] 3.1 At the `CallerPartnerSelectMode.First` call site (`QsoCallerService.cs:666-680`),
  capture the new `grid` out-param and pass it through to `ExecuteTxReportAsync`.

## 4. Thread the grid through the `None`-mode manual-select path

- [x] 4.1 Add a new `_pendingResponderGrid` field alongside the existing
  `_pendingResponderCallsign`/`_pendingResponderFrequencyHz`/`_pendingResponderIsAPhase` fields.
- [x] 4.2 In `SelectResponderAsync` (`QsoCallerService.cs:274-306`), after looking up
  `_recentResponderDecodes.TryGetValue(callsign, out var recentDecode)`, re-run
  `TryParseResponder` (or a small shared token-3-is-a-grid helper, to avoid re-validating the
  callsign match) against `recentDecode.Message` to recover the grid, and store it in
  `_pendingResponderGrid` (set at `QsoCallerService.cs:295-298`).
- [x] 4.3 Update `TestSetPendingResponder` (`QsoCallerService.cs:377-387`) to also accept/set
  `_pendingResponderGrid`, so test setup stays consistent with the real path.
- [x] 4.4 Thread `_pendingResponderGrid` into the pending-responder-fire call to
  `ExecuteTxReportAsync` (`QsoCallerService.cs:649`).

## 5. Capture and emit the grid on the final QsoRecord

- [x] 5.1 Add a `string? partnerGrid` parameter to `ExecuteTxReportAsync`
  (`QsoCallerService.cs:713-766`) and set `_partnerGrid = partnerGrid;` alongside the existing
  `_partner = partner;` assignment.
- [x] 5.2 At `QsoCallerService.cs:833`, change `PartnerGrid = null, // caller does not capture
  partner's grid in WaitRr73` to `PartnerGrid = _partnerGrid,` and remove the now-inaccurate
  comment (optionally replace with a short note that `null` here is normal/expected when the
  responder's first message was a bare signal report, not a gap).

## 6. Tests

- [x] 6.1 `QsoCallerServiceTests.cs`: add a case confirming a CQ-answer message containing a
  grid (e.g. `"Q1OFZ Q2NOISE IO91"`) results in the final `QsoRecord.PartnerGrid` being
  populated with that grid once the QSO completes, for the `CallerPartnerSelectMode.First` path.
- [x] 6.2 `QsoCallerServiceTests.cs`: add a second case for the `None`-mode manual-select path
  (`SelectResponderAsync` / `TestSetPendingResponder`) proving the same grid capture works there
  too.
- [x] 6.3 `QsoCallerServiceTests.cs`: add a case confirming a CQ-answer message that skips the
  grid and goes straight to a signal report (e.g. `"Q1OFZ Q2NOISE -05"`) still correctly yields
  `PartnerGrid = null` — the fix must not invent a grid where none was sent.
- [x] 6.4 Re-run `QsoAnswererServiceTests.cs`'s existing jump-in coverage unmodified — confirm no
  assertion there changes (Part 2 of the original defect analysis is explicitly out of scope).
- [x] 6.5 Re-run `AdifLogWriterTests.cs` unmodified — confirm no change expected
  (`AdifLogWriter.BuildAdifRecord` already correctly conditions `GRIDSQUARE` on `PartnerGrid`).

## 7. Verification

- [x] 7.1 `dotnet build` — clean build, no new warnings. (Daemon project and test project both
  built clean, 0 warnings/0 errors.)
- [x] 7.2 `dotnet test` — full suite green; unchanged pass counts plus the new grid-capture
  tests from Section 6. (1246 tests across all assemblies passed; one unrelated
  `JsonConfigStoreTests.SaveAsync_ConcurrentCallers_DoNotThrow_AndFileEndsUpValid` failure under
  full-solution parallel load — confirmed pre-existing Windows file-lock flake, passes in
  isolation, same class of flake already documented in `cat-tx-ptt`'s tasks.md §18.6; not caused
  by this change.)
- [x] 7.3 `openspec validate --strict --all` — 56/56, unchanged from before the delta spec was
  added (the new `qso-caller` requirement validates cleanly; no other spec text changed).
- [x] 7.4 `python3 tools/pre_merge_check.py` — **PASS WITH WARNINGS**. G9a, Release build, full
  test suite, Gate G3 traceability, and Gate G8 (`openspec validate --strict --all`) all PASS.
  AOT publish WARN: local machine is missing the MSVC native-linker toolchain (`vswhere.exe`
  not on PATH) — a local-environment gap unrelated to this change (touches only
  `QsoCallerService.cs` and its test file; no AOT/native-interop surface). CI's Windows runner
  has the full toolchain and is expected to pass this gate normally.
- [ ] 7.5 Manual/hardware (optional but recommended): complete one more real QSO where the
  partner answers our CQ with a grid included, and confirm `ADIF.log`'s new record includes a
  populated `GRIDSQUARE` tag matching the grid visible in `ALL.TXT`. **Deferred** — no hardware
  session available in this session; left for the Captain to run opportunistically, not
  blocking merge (severity is Minor per the dev-task doc, and full unit coverage already proves
  the fix).

## 8. Housekeeping

- [x] 8.1 Commit all changes with a clear message (e.g. `fix(qso-caller): capture partner grid
  for ADIF logging on caller-initiated QSOs`). (`08b3046`)
- [x] 8.2 Push and confirm CI green on all platforms. Pushed to `origin/fix/adif-partner-grid-capture`;
  PR #80 checks all green (`Build & Test` on ubuntu-latest/windows-latest/macos-latest, `Gate G9`),
  and post-merge push to `main` (run `29526215957`, commit `b098b2e`) also completed green.
- [x] 8.3 Open PR to `main`; request QA gate review. `PR #80`:
  https://github.com/frank001/OpenWSFZ/pull/80
- [x] 8.4 After merge, run `/opsx:archive` for this change (sync `qso-caller`'s delta spec into
  `openspec/specs/qso-caller/spec.md`, confirm `openspec validate --strict --all` before/after).
  Synced the "Partner grid capture for ADIF logging" requirement (3 scenarios) into
  `openspec/specs/qso-caller/spec.md` after `TxRr73`, before `Repeat-CQ retry logic`.
  `openspec validate --strict --all`: 57/57 before sync, 57/57 after sync+before archive-move,
  56/56 after archive-move (expected drop — one fewer active change's delta spec to validate).
- [x] 8.5 Update `dev-tasks/2026-07-12-adif-partner-grid-not-captured.md` status to Closed,
  referencing the merged PR, or remove it if the project convention is to delete closed
  dev-tasks rather than mark them closed in place. **Captain's call: left the file untouched.**
  Checked git history — no prior dev-task doc has ever been edited-in-place after merge (all
  "Awaiting developer action" headers stay as originally written); resolution is tracked in
  MEMORY.md instead, consistent with that established convention.
