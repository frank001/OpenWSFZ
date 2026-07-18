## 1. Branch

- [x] 1.1 Create and check out branch `fix/jump-in-rr73-adif-capture` from `main`.

## 2. Thread the raw decoded payload through EngageAtAsync

- [x] 2.1 Add a new trailing `string rawPayload` parameter to
  `IQsoController.EngageAtAsync` (`src/OpenWSFZ.Abstractions/IQsoController.cs:125-130`).
- [x] 2.2 Update `QsoControllerRouter.EngageAtAsync` (`QsoControllerRouter.cs:125-143`) to accept
  and pass through the new parameter unchanged to `_answerer.EngageAtAsync(...)`.
- [x] 2.3 Update `QsoAnswererService.EngageAtAsync` (`QsoAnswererService.cs:229-...`) to accept
  the new parameter and store it in a new `_jumpRawPayload` field alongside the existing
  `_jumpPoint`/`_jumpPartner`/`_jumpFreqHz`/`_jumpIsAPhase`/`_jumpSetAt` jump-in state fields
  (declared ~`:110-118`), following the same `_stateLock` discipline as the existing fields.
- [x] 2.4 Update `QsoAnswererService.TestSetJumpTarget` (`:457-468`) to also accept/set
  `_jumpRawPayload`, so test setup stays consistent with the real path.
- [x] 2.5 Update `QsoAnswererService`'s jump-in consumption block (`:618-...`, where
  `jumpPoint`/`jumpPartner`/etc. are read out of `_stateLock` before calling
  `ExecuteJumpInAsync`) to also read `_jumpRawPayload` and pass it through to
  `ExecuteJumpInAsync`.
- [x] 2.6 Update `QsoAnswererService.ExecuteJumpInAsync`'s signature (`:892-897`) to accept the
  new `string rawPayload` parameter.
- [x] 2.7 Update `QsoCallerService.EngageAtAsync` (`QsoCallerService.cs:397-...`) — the existing
  documented no-op stub — to accept the new parameter for signature parity only; no behavior
  change (still returns without acting, per its `<remarks>` comment).
- [x] 2.8 Update `WebApp.cs`'s `POST /api/v1/tx/engage-decode` handler (`:1485-1517`) to pass its
  local `info` variable (the exact matched payload text) as the new `rawPayload` argument at all
  three `EngageAtAsync` call sites (`SendRr73` at `:1493-1495` needs the real value; the
  `Send73`/`SendReport` call sites at `:1487-1489`, `:1499-1501`, `:1507-1509` can pass `info`
  too for consistency, though only `SendRr73` currently consumes it).

## 3. Derive a real RstRcvd instead of a hardcoded placeholder

- [x] 3.1 In `ExecuteJumpInAsync`, remove the unconditional `_rstRcvd = "+00";` at `:910` for the
  `SendRr73` case specifically — `SendReport` and `Send73` don't consume `_rstRcvd` at jump-in
  entry the way `SendRr73` will, so confirm via the existing tests (task 6.4) that only the
  `SendRr73` path's behavior changes.
- [x] 3.2 In the `EngagePoint.SendRr73` case (`:961-970`), before transmitting, set `_rstRcvd`
  using the same normalization `QsoCallerService.IsRogerReport` already implements
  (`QsoCallerService.cs:1327-1334`, and its call site at `:847-851`): if
  `QsoCallerService.IsRogerReport(rawPayload)`, strip the leading `R`
  (`rawPayload[1..]`); otherwise use `rawPayload` as-is (covers a bare `"RRR"`). `IsRogerReport`
  is `internal static` in the same assembly — call it directly, no relocation needed.

## 4. Write ADIF for the SendRr73 jump-in

- [x] 4.1 Extract a shared `BuildAndWriteQsoRecordAsync(TxConfig tx, string partner,
  CancellationToken ct)` helper from `ExecuteTx73Async`'s existing record-build +
  confirmation-gated publish/write block (`QsoAnswererService.cs:1112-1152`), preserving its
  exact behavior: build the `QsoRecord` (`PartnerCallsign`, `PartnerGrid = _partnerGrid`,
  `RstSent = "R+00"`, `RstRcvd = _rstRcvd`, `QsoStartUtc`, `QsoEndUtc` via
  `Ft8TimeHelper.DeriveFt8CycleStartUtc`, `OperatorCallsign`, `OperatorGrid`,
  `DialFrequencyMHz` via `WebApp.ResolveEffectiveFrequency`), then branch on
  `tx.QsoConfirmation` exactly as today (publish via `_txEventBus.PublishQsoReview` if enabled;
  otherwise `_adifLog.AppendQsoAsync` directly — never both).
- [x] 4.2 Update `ExecuteTx73Async` to call the new helper in place of its inlined block, with no
  behavior change (pure refactor — same fields, same branch, same ordering relative to
  `SetStateAndNotify(QsoState.QsoComplete)` and the completion log line). → **Correction
  (post-implementation QA review):** the record-build-and-write call moved to *after*
  `TransmitAsync`/`SetStateAndNotify(QsoState.QsoComplete)` instead of before, for the
  `tx.QsoConfirmation=true` branch specifically — see design.md's Risks/Trade-offs section for
  the detail. Not a regression (no test or client-side code depended on the old ordering), but
  this task's "no behavior change" framing was inaccurate.
- [x] 4.3 In the `EngagePoint.SendRr73` jump-in case (`:961-970`), after `TransmitAsync`
  completes, call the new helper, then move the "QSO with {Partner} complete!" log line and
  `SetStateAndNotify(QsoState.QsoComplete)` in ahead of `SafeAbortToIdleAsync`, matching
  `ExecuteTx73Async`'s ordering. Update the stale `// (no ADIF — partial QSO)` comment above the
  `case EngagePoint.SendRr73:` line to reflect the new behavior.

## 5. Tests

- [x] 5.1 `QsoAnswererServiceTests.cs`: new test asserting that after a `SendRr73` jump-in fires
  (via `TestSetJumpTarget` + a decode cycle, or directly exercising `EngageAtAsync` per the
  existing jump-in test pattern around D-CALLER-018/021, lines ~2558-2857) with
  `rawPayload = "R-05"`, `IAdifLogWriter.AppendQsoAsync` is called exactly once with a
  `QsoRecord` where `PartnerCallsign` matches and `RstRcvd == "-05"`.
- [x] 5.2 Companion test with `rawPayload = "RRR"` asserting `RstRcvd == "RRR"` (not a fabricated
  numeric value).
- [x] 5.3 Companion test confirming `PartnerGrid` is still correctly `null` on this path (guards
  against regressing the "Aside" from the source dev-task — this is deliberate, not a gap to
  fix).
- [x] 5.4 A `tx.QsoConfirmation = true` variant asserting `PublishQsoReview` fires instead of a
  direct `AppendQsoAsync` call, matching `ExecuteTx73Async`'s existing coverage for that gate.
- [x] 5.5 `EngageDecodeEndpointTests.cs` (`tests/OpenWSFZ.Web.Tests/`): confirm the
  `RRR`/`R±NN` dispatch branch (`WebApp.cs:1491-1496`) now forwards the matched payload text into
  `EngageAtAsync`'s new `rawPayload` parameter.
- [x] 5.6 Re-run existing jump-in coverage (`QsoAnswererServiceTests.cs` D-CALLER-018/021 lines
  ~2558-2857) unmodified — this fix only changes what happens *after* the TX completes for
  `SendRr73`, not the phase-arming/expiry logic those tests cover.
- [x] 5.7 Re-run the full existing `ExecuteTx73Async`-covering test suite unmodified — confirms
  the record-build/write extraction (task 4.1-4.2) is a behavior-preserving refactor.

## 6. Verification

- [x] 6.1 `dotnet build` — clean build, no new warnings.
- [x] 6.2 `dotnet test` — full suite green; unchanged pass counts plus the new tests from
  Section 5.
- [x] 6.3 `openspec validate --strict --all` — expect a clean pass with the new `qso-answerer`
  delta requirement validating.
- [x] 6.4 `python3 tools/pre_merge_check.py` — run before declaring this ready for merge (per
  HK-006). If the E2E gate fails due to a port conflict with an already-running local daemon
  (a known environmental hazard, not a code issue — confirm by checking for a process already
  bound to the configured port before assuming a regression), note that explicitly rather than
  treating it as a defect.
- [x] 6.5 Manual/hardware (recommended, given the source defect was found via a real QSO):
  recreate the shape of the original incident — let a caller-side session's retry/watchdog cycle
  expire mid-QSO, then double-click the partner's subsequent `RRR`/`R±NN` reply in the decode
  panel — and confirm `ADIF.log` gains a well-formed record with a real (non-placeholder)
  `RST_RCVD`. → DONE, live hardware-in-the-loop, real Release daemon + real audio output device:
  `qa/jump-in-rr73-adif-capture-live-verify/live_verify_jumpin_rr73_adif.py` — **PASS**. Phase 1
  recreated the precondition faithfully (real Caller CQ session, real 1-minute watchdog expiry,
  caller-side abort with `abortReason: "Watchdog timeout"`, router auto-reverted to
  Answerer/Idle). Phase 2a repeated the *exact* payload shape from the original incident (a
  bare `"RRR"`, matching `dev-tasks/2026-07-16-jump-in-sendrr73-no-adif-record.md`'s evidence log)
  via `POST /api/v1/tx/engage-decode`: real RR73 transmitted, real ADIF write —
  `<CALL:5>Q7GHK<RST_SENT:4>R+00<RST_RCVD:3>RRR...<EOR>`, no fabricated `+00`, no `GRIDSQUARE`.
  Phase 2b repeated with a numeric roger report (`"R-05"`) confirming `RST_RCVD:-05` (leading `R`
  stripped). Report: `qa/jump-in-rr73-adif-capture-live-verify/live-reports/2026-07-18T001228Z-bb18cb3.md`.

## 7. Housekeeping

- [x] 7.1 Commit all changes with a clear message (e.g. `fix(qso-answerer): write ADIF record
  and derive real RstRcvd for SendRr73 jump-ins`).
- [x] 7.2 Push and confirm CI green on all platforms. → Pushed; PR #82 opened
  (https://github.com/frank001/OpenWSFZ/pull/82). CI status to be confirmed once checks run.
- [x] 7.3 Open PR to `main`; request QA gate review. → PR #82:
  https://github.com/frank001/OpenWSFZ/pull/82. QA review found and fixed three issues before
  approval: a Gate G9b violation inherited from an unpushed `main` commit (`b2cef04`'s archived
  `fix-adif-partner-grid-capture` proposal was missing its `**User-facing:**` declaration — fixed
  directly on `main`, commit `312849e`), a real third-party callsign (`G7LHK`) in this change's own
  `proposal.md`/`tasks.md` and in the pre-existing `dev-tasks/2026-07-16-jump-in-sendrr73-no-adif-
  record.md` (NFR-021 — redacted to the synthetic `Q7GHK` stand-in, commits `6e6e22e`/`312849e`),
  and an inaccurate "zero behavior change" claim about the `BuildAndWriteQsoRecordAsync` extraction
  (corrected inline in `design.md`/this file's task 4.2 — see there for detail). Merged as
  `dc32a3f`.
- [x] 7.4 After merge, run `/opsx:archive` for this change (sync the `qso-answerer` delta spec
  into `openspec/specs/qso-answerer/spec.md`, confirm `openspec validate --strict --all`
  before/after).
- [x] 7.5 Update `dev-tasks/2026-07-16-jump-in-sendrr73-no-adif-record.md`'s status to reflect
  the merged fix, consistent with this project's established convention of leaving dev-task docs
  as originally written and tracking resolution in `MEMORY.md` instead (see prior precedent:
  `fix-adif-partner-grid-capture` task 8.5). Resolution tracked in `MEMORY.md`.
