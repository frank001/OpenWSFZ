# Developer handoff: retire the "settle" delays and the weak `WaitForBatchDrainedAsync` in the QSO Caller/Answerer tests

**Date:** 2026-10-01. **From:** QA. **To:** Developer. **Priority:** medium-high. These are flaky tests waiting to be discovered; D-015 was the first one to surface, and it surfaced as a red mechanical gate on the SUB-FEAS merge branch.

## 1. Context

The standing rule is Gate G10 (`tools/check_test_delay_sync.py`, `test-delay-debt.md`): a test waits for a **positive condition** via `OpenWSFZ.TestSupport` `Poll.*`, never for a fixed delay. QA's read-only audit of 2026-10-01 (on `merge/sub-feas-local`) found that the rule is being met in letter but not in effect, in two ways.

**Finding A: 8 "settle" delays that G10 tolerates by a debt-file justification.** Each is `drain _wakeupChannel` followed by `await Task.Delay(50)`, after which the test acts on service state. Lines are current on `merge/sub-feas-local`; match by test name, since lines drift.

| File | Line | Test |
|---|---|---|
| `QsoCallerServiceTests.cs` | 540 | `SelectResponderAsync_PhaseSemanticsCorrect` |
| `QsoCallerServiceTests.cs` | 1400 | `HandleWaitAnswer_NoneMode_FiresTxAfterOperatorClick` |
| `QsoCallerServiceTests.cs` | 1727 | `SelectResponderAsync_NoneMode_CapturesPartnerGridIntoQsoRecord` (**the D-015 test; its fix `ada7b488` left this delay in place**) |
| `QsoCallerServiceTests.cs` | 1866 | `SelectResponderAsync_NoneMode_UsesRealMeasuredSnr` (same shape as 1727) |
| `QsoAnswererServiceTests.cs` | 2591, 2621, 2700, 2733 | four tests that arm a pending target (`AnswerCqAsync`/`EngageAtAsync`), drain the wakeup, then delay 50 ms |

The debt file justifies them as a "wall-clock stray-wakeup settle ... no externally observable condition to poll for". That justification is doubtful: the D-015 fix found an observable condition (`_recentResponderDecodes`) for a neighbouring case.

**Finding B: `WaitForBatchDrainedAsync` does not prove what its callers need.** It polls `channel.Reader.Count == 0`, which is true the moment the service *reads* a batch, **before** `ProcessBatchAsync` has run. That was the real D-015 cause (see the comment in `ada7b488`). The helper is unchanged and is called **29 times in `QsoCallerServiceTests.cs` and 27 times in `QsoAnswererServiceTests.cs`**. Callers that are followed by a `State` assertion, a mock-call assertion (`ptt.Received(...)`) or a `SelectResponderAsync`/`AnswerCqAsync` are exposed to the same read-versus-processed gap. G10 cannot see this, because there is no delay literal.

## 2. Branch

Cut **`fix/qso-test-sync-settle-and-drain`** from `origin/main`. First check whether `fix/qso-caller-d015-flake` (`ada7b488`) is already on `origin/main`; if not, cut from `origin/main` and take that commit's helper (`WaitForResponderRecordedAsync`) as your starting point rather than reimplementing it. Never commit to `main`. **Test-only.** If the right fix needs a product seam (Action 2, option B), **stop and tell QA** with the evidence (HK-011); do not touch `src/`.

## 3. Actions

1. **Reproduce first.** In WSL Debian, Release, run the whole `OpenWSFZ.Daemon.Tests` project unfiltered under the same load used for D-015 (32 busy loops), at least 20 runs, on the **branch base**. Record which tests fail and how often. A fix that is not shown against a reproduction is not a fix (if Findings A/B do not reproduce in 20 runs, say so and give the rate; the mechanism is still real, but report honestly).
2. **Fix Finding B at the helper, not at 56 call sites.** Give both copies of `WaitForBatchDrainedAsync` (`QsoCallerServiceTests.cs`, `QsoAnswererServiceTests.cs`) a condition that proves the batch was **processed**, not just dequeued. Options, in order of preference; state which you chose and why:
   - **A. Test-side only.** Write a sentinel batch after the real batch and poll until the sentinel has been observed processed (for example via an observable the service already exposes, or a no-op decode whose recording you can poll). This is only valid if the service processes batches strictly in order; verify that from the code.
   - **B. A product seam** (for example a processed-cycle counter on the service). This is an `src/` change: **propose it to QA and stop**, do not implement.
   Keep the helper's name/signature if practical so call sites stay untouched; if some call sites genuinely need a different condition (for example "the decode is recorded" as in `ada7b488`), migrate those individually and list them.
3. **Fix Finding A.** Replace each of the 8 settle delays with a positive-condition `Poll.*`. Establish, **from the code**, what the "stray wakeup" actually is: `SelectResponderAsync`/`AnswerCqAsync` push a wakeup computed from real `DateTimeOffset.UtcNow`, which races the service loop's read of `_wakeupChannel`. Candidate positive conditions to check (do not assume): the wakeup channel observed empty **and** the service's loop observed to have passed one full iteration; the pending target/responder state having been consumed or confirmed stable. If a site truly has no observable condition, **keep it, say why with evidence**, and leave its debt entry; otherwise remove the debt entry in the same commit.
4. **Update `test-delay-debt.md`** in the same branch: remove migrated entries, and reword the "no externally observable condition" justification where an observable was found. `python tools/check_test_delay_sync.py` must pass.
5. **List, do not fix**, any other test that mixes the real clock with fixed 2026-06-25/06-27 stamps, or that asserts exact counts against state a background loop also changes. QA will triage.
6. **Do not touch** the sites QA cleared as legitimate (absence proofs, mock latency, feeders, `PollTests`): `ConsoleDetacher:64`, `DecodePump:270`, `ExternalReporting:1470`, `LoggingRotation:128`, `Caller:1315`, `CatPolling:326/334`, `CaptureManager:29`, `Answerer:1152/1978`, `PollTests`, `DaemonStartup:79/134`.

## 4. Acceptance criteria (what QA checks)

1. Your report gives the reproduction on the branch base (runs, failures, load) and the failure rate after the fix, **at least as many runs, same load, 0 failures**.
2. The mechanism for Finding A (what the stray wakeup is, and what condition you poll instead) is stated with evidence from the code, not a guess. Any site you keep is justified individually.
3. No test is weakened or removed; every assertion survives. **No new bare `Task.Delay`/`Thread.Sleep`.** `check_test_delay_sync.py` passes, with a smaller debt file than today (23 sites).
4. Unfiltered pass counts for **Windows** and **WSL Debian** `OpenWSFZ.Daemon.Tests` quoted, with the exact command (a filtered-out run is not a result, HK-022).
5. `git diff --stat -- src/ native/` is empty (or contains only a change QA approved in advance).
6. The helper change is described in the commit message so the next reviewer can see Finding B was fixed at the source.

## 5. References

- Tests: `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` (helper near line 158; D-015 helper `WaitForResponderRecordedAsync` from `ada7b488`), `QsoAnswererServiceTests.cs` (helper near line 159).
- Service: `src/OpenWSFZ.Daemon/QsoCallerService.cs` (`_stateLock`, `_recentResponderDecodes`, `_wakeupChannel`), `QsoAnswererService.cs`.
- Gate and library: `tools/check_test_delay_sync.py`, `test-delay-debt.md`, `OpenWSFZ.TestSupport` `Poll.*`.
- Sibling handoffs: `2026-10-01-d015-qsocaller-partnergrid-flake.md`, `2026-10-01-capture-autostart-coordinator-load-flake.md`.
- QA's audit was read-only; QA did not trace each of the 56 `WaitForBatchDrainedAsync` call sites. Part of your job is to classify them (by what follows the call) in your report.
