# Developer handoff: intermittent failure of D-015 `SelectResponderAsync_NoneMode_CapturesPartnerGridIntoQsoRecord` under the full suite on Linux

**Date:** 2026-10-01. **From:** QA. **To:** Developer. **Priority:** blocks a clean gate on the SUB-FEAS merge branch (one red WSL gate), but it is **not** in SUB-FEAS code.

## 1. Context

QA's second mechanical gate run on `merge/sub-feas-local` (local, @`2c687768` plus the fix-branch merge) failed one gate: **WSL Debian compile + test**, one test in `OpenWSFZ.Daemon.Tests` (632 of 633 passed):

```
D-015: None-mode manual select (SelectResponderAsync) captures partner grid into QsoRecord.PartnerGrid [FAIL]
Expected to receive exactly 1 call matching:
    AppendQsoAsync(r => r.PartnerCallsign == "Q1TST" && r.PartnerGrid == "JO22")
Actually received no matching calls.
Received 1 non-matching call:
    AppendQsoAsync(QsoRecord { PartnerCallsign = Q1TST, PartnerGrid = <empty>, RstSent = +00, RstRcvd = +07,
        QsoStartUtc = 10/1/2026 15:28:06, QsoEndUtc = 10/1/2026 15:28:00, ... })
   at QsoCallerServiceTests.SelectResponderAsync_NoneMode_CapturesPartnerGridIntoQsoRecord() in QsoCallerServiceTests.cs:line 1720
```

Why QA calls it a flake and not a SUB-FEAS regression:
- `QsoCallerService.cs` and `QsoCallerServiceTests.cs` are **not touched** by this branch (`git diff origin/main HEAD` on `src/OpenWSFZ.Daemon` shows only `DecodePump.cs` and `Program.cs`; tests only `DecodePumpTests`, `ExternalReportingServiceTests`, `TwoStageEngageCharacterisationTests`).
- The same test **passed** in the previous full WSL run on the same code, and passed **8 of 8** run alone in WSL Debian.
- It fails only inside the full parallel suite; Windows full run green both times.

Two oddities in the failing record are the best clues: the recorded `QsoEndUtc` (15:28:00) is **earlier** than `QsoStartUtc` (15:28:06), and `PartnerGrid` is empty although the test feeds the responder's grid (`JO22`) into the service before selecting.

## 2. Branch

Cut **`fix/qso-caller-d015-flake`** from **`origin/main`**. First reproduce it there (Action 1) so we learn whether the flake pre-exists SUB-FEAS; QA merges the result into the merge branch either way. Never commit to `main`. Test-only unless Action 3 finds a product cause (then stop and tell QA, HK-011).

## 3. Actions

1. **Reproduce.** In WSL Debian, run the whole `OpenWSFZ.Daemon.Tests` project repeatedly (at least 10 times, Release, unfiltered) on `origin/main`, and record how often D-015 fails and whether other tests fail with it. Alone it does not fail, so the load matters (the suite runs test classes in parallel). If it reproduces rarely, add CPU load in WSL (a parallel busy loop, or a parallel run of another test project) to make it frequent. Report the failure rate before and after your fix. **A fix that is not shown against a reproduction is not a fix.**
2. **Establish the mechanism, from the code, not from the clues above.** Read the path: the None-mode auto-track records the responder's decode into `_recentResponderDecodes`; `SelectResponderAsync` re-parses it to recover the grid (test comment at the top of the failing block). Candidate mechanisms for an empty grid, to **check, not assume**:
   - a time window or ordering in `_recentResponderDecodes` (entries expiring or evicted by wall-clock or by the injected cycle times: the test mixes `Make(...)` batches stamped with the real clock and `SendAt`/`bPhaseResponse` stamped **2026-06-25 14:29**, while the clock today is 2026-10-01);
   - the `await Task.Delay(50)` and the `_wakeupChannel` drain loops in the test racing the service loop (a wakeup consumed or dropped before the grid is captured);
   - a second `Make("CQ Q2NOISE JO00")` batch (the phase trigger) overwriting or clearing the stored grid on a slower scheduling pass.
   The `QsoEndUtc < QsoStartUtc` ordering is a symptom to explain too, not to ignore.
3. **Fix the cause.** If the test races the service, synchronise it on a **positive condition** with `Poll.*` (never a new bare delay; Gate G10 would reject it) and, if the `Task.Delay(50)` there is a G10 debt entry, remove it as part of the fix. If the cause is in `QsoCallerService` (a real race that could lose a grid in production), **stop and report to QA with the evidence**; do not fix product code without QA's pre-approval (HK-011).
4. If other tests in the same file show the same pattern (mixing the real clock with fixed 2026-06-25 stamps, or a bare 50 ms wait before a state assertion), list them in your report; do not change them in this branch unless the same fix applies without extra risk.

## 4. Acceptance criteria (what QA checks)

1. Your report gives the reproduction on `origin/main` (runs, failures, the load used) and the failure rate after the fix over **at least as many runs**, under the same load, with **0 failures**.
2. The established mechanism is stated in your report with evidence (a trace, an ordering, or a failing interleaving), not a guess.
3. The test still asserts what it asserts today (`PartnerCallsign` and `PartnerGrid` of the appended QSO record, the state sequence); nothing is weakened or removed. No new bare `Task.Delay`/`Thread.Sleep`.
4. Unfiltered runs quoted for **Windows** `OpenWSFZ.Daemon.Tests` and **WSL Debian** `OpenWSFZ.Daemon.Tests` (pass counts; a filtered-out run is not a result, HK-022).
5. `git diff --stat -- src/ native/` for your branch is empty (or contains only a change QA has approved in advance).

## 5. References

- Test: `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` around lines 1670 to 1730; service: `src/OpenWSFZ.Daemon/QsoCallerService.cs` (`PartnerGrid` set around line 995, `_recentResponderDecodes`).
- Polling library and Gate G10: `OpenWSFZ.TestSupport` `Poll.*`, `tools/check_test_delay_sync.py`, `test-delay-debt.md`.
- Gate failure context: `merge/sub-feas-local`, local only.
