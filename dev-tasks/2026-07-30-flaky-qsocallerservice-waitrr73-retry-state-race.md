# Flaky test — `QsoCallerServiceTests` WaitRr73-retry state assertion (TX-D04)

**Date surfaced:** 2026-07-30, CI on `integration/2026-07-29-live-run-40m-20m`
(run `30576716097`, job `90986698530`, `ubuntu-latest` only — `macos-latest` and
`windows-latest` both passed clean in the same run), triggered by a push that only touched
`qa/endurance/` artefacts — nothing in `src/` or this test file.
**Test:** `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1806`
`QsoCallerServiceTests.RetryOrAbortAsync_WaitRr73Retry_ResendsSamePersistedReportValue`
(`TX-D04: a WaitRr73 retry resends the same report value chosen at TxReport time, and the
final ADIF record still reflects it`).
**Owner area:** `OpenWSFZ.Daemon`'s `QsoCallerService` retry/state-machine path — production
code, not the test double or harness.

## Symptom

```
Expected sut.State to be QsoState.WaitRr73 {value: 4} because one retry must not exhaust the
retry budget, but found QsoState.TxReport {value: 3}.
   at OpenWSFZ.Daemon.Tests.QsoCallerServiceTests.RetryOrAbortAsync_WaitRr73Retry_ResendsSamePersistedReportValue()
   in QsoCallerServiceTests.cs:line 1844
```

1 failed, 568 passed in `OpenWSFZ.Daemon.Tests.dll` on that run. First flake on this specific
test per `git log --all --grep` / `dev-tasks/` search — no prior tracking entry exists for it.

## Why this is not the pushed content's fault

The push that triggered this CI run added `qa/endurance/anova_common.py`,
`endurance_anova_jt9.py`, `endurance_anova_wsjtx.py`, `tools/gather_live_run_artefacts.py`'s
band-split feature, and a `qa/endurance/2026-07-29-5016363/CONTAMINATION-NOTE.md` — nothing
that touches `QsoCallerService`, its tests, or anything in the TX/QSO call path. Re-running
the full suite locally (both native Windows and WSL Debian, via `pre_merge_check.py`) against
the *original, unfixed* test code passed clean both times (601/601 and 569/569 respectively) —
consistent with a genuine, low-probability race rather than a reliable repro, and with the
push's actual content being unrelated.

## Root cause, read from the code (not just inferred from symptoms)

The test's failing assertion sequence (pre-fix):

```csharp
Send(channel, Make("Q2NOISE Q3NOISE -10"));
await Poll.WaitForCallCountAsync(() => ptt.ReceivedCalls(), nameof(IPttController.KeyUpAsync), 3,
    timeout: TimeSpan.FromSeconds(3));
await ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>()); // retry fired
sut.State.Should().Be(QsoState.WaitRr73, "one retry must not exhaust the retry budget");
```

It polls until `KeyUpAsync` has been called 3 times, then asserts `sut.State` **synchronously**,
with no poll on the state itself. `KeyUpAsync` firing does not happen-before the state
machine's own transition into `WaitRr73` — the PTT release and the state assignment are two
separate steps in the retry path, and nothing guarantees the second has completed by the
instant the third `KeyUpAsync` call is observed. On an idle machine the gap is too small to
ever hit; under real CI scheduling load (this run was `ubuntu-latest`, sharing the runner with
everything else in the matrix) the assertion can land in the gap and observe the prior
`TxReport` state instead — exactly what the failure shows (`TxReport {value: 3}` where
`WaitRr73` is `{value: 4}`, i.e. one state transition short).

**This exact race was already known and documented, just not fixed**: the sibling test
`LastTxMessage_ReflectsRetransmittedValue_AfterWaitRr73Retry` (line ~1911) has an identical
`KeyUpAsync`-count-then-synchronous-assert pattern, with a comment directly above it reading
*"...draining proves the batch was dequeued but not that the retransmit + WaitRr73 transition
has landed, which races on ubuntu-latest scheduling."* Someone had already spotted the gap and
left a warning rather than closing it — a genuine miss, since every other state check in this
same file (lines 1827, 1830, 1900, 1930) already uses `Poll.WaitForEqualAsync` for exactly this
kind of wait, so the fix was already the file's own established convention.

This is the same *class* of defect TESTING_STRATEGY.md §11 calls out under "Threading / async
waits" — a fixed-duration or otherwise-unguarded synchronization barrier substituting for a
poll on the actual condition — just manifesting as a bare post-poll assertion rather than a
literal `Task.Delay`, so Gate G10 (which only scans for `Task.Delay`/`Thread.Sleep` literals)
would never have caught it.

## Disposition

**Status: FIXED in this session**, per the Captain's steer that documentation and tests are QA
territory (unlike a `src/` behavior fix, which would need a separate Developer session per
HK-011). Both sites replaced the bare assertion with
`await Poll.WaitForEqualAsync(() => sut.State, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3), what: "...")`,
matching this file's own established pattern. The now-stale "races on ubuntu-latest scheduling"
comment on the sibling test was reworded to reflect that the transition is now polled rather
than merely flagged as risky.

Per TESTING_STRATEGY.md §11.2, the first flake still gets filed here regardless of same-session
fix, so the occurrence is on record if the pattern resurfaces elsewhere in this file or a
sibling one.

## Cross-reference

- `TESTING_STRATEGY.md` §11 (Flaky Test Policy) — the policy this document exists to satisfy;
  worth a future note that "poll the wrong thing then assert synchronously" is a variant of the
  bare-delay anti-pattern that Gate G10's regex-based scan structurally cannot detect.
- `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` — both fixed sites
  (`RetryOrAbortAsync_WaitRr73Retry_ResendsSamePersistedReportValue`,
  `LastTxMessage_ReflectsRetransmittedValue_AfterWaitRr73Retry`).
- CI run `30576716097` / job `90986698530` — the observed failure.
