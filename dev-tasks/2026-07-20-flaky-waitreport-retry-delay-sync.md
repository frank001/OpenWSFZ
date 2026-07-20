# Handoff: `WaitReport_Retry_BracketsRetransmissionWithTxAnswer` is flaky under CI load

**Date:** 2026-07-20
**Prepared by:** QA engineer (observed during PR #93 CI review)
**Status:** Not started
**Severity:** Low/hygiene — flaky test, not a product defect. Does not block any current PR; this
is a standalone follow-up.

---

## 1. What was observed

PR #93 (`feat/qso-transcript-own-section`, a `web/**`-only CSS/HTML change with zero `.cs` files
touched) failed its `Build & Test (ubuntu-latest)` GitHub Actions job on the `pull_request`-triggered
run, while the identical commit passed the same job on the `push`-triggered run for the same SHA
minutes earlier. Re-running the failed job (`gh run rerun 29762105557 --failed`) came back green with
no code changes. See run `29762105557`, job `88418984418`.

The failing test:

```
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1102
[Fact(DisplayName = "GUI polish 2: WaitReport retry brackets retransmission with TxAnswer / WaitReport")]
public async Task WaitReport_Retry_BracketsRetransmissionWithTxAnswer()
```

Failure was `NSubstitute.Exceptions.CallSequenceNotFoundException` — the test expected four ordered
`eventBus.Publish(...)` calls bracketing a retransmission, but only the first had landed by the time
`Received.InOrder(...)` ran.

Confirmed **not** related to PR #93's content:
- The branch touches only `web/index.html` / `web/css/app.css` — nothing in `OpenWSFZ.Daemon` or the
  answerer/retry path.
- Ran the test standalone, 5/5, on Windows locally — clean every time (~320ms each).
- The same commit passed this exact job on a different CI run.

## 2. Root cause (why it's flaky, not a one-off fluke)

`WaitReport_Retry_BracketsRetransmissionWithTxAnswer` (and its sibling
`WaitRr73_Retry_BracketsRetransmissionWithTxReport` immediately below it, likely the same risk)
synchronizes with the system-under-test using a bare fixed-duration sleep rather than polling for the
actual condition:

```csharp
await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));
await Task.Delay(50); // let the trailing post-retransmit publish settle
```

`Task.Delay(50)` assumes the retransmission's remaining `Publish` calls will have completed within
50ms of the state transition. That assumption only holds when the test host isn't under load. On a
busy shared `ubuntu-latest` runner (this suite runs 500+ tests, several of them in parallel, including
a ~78s `OpenWSFZ.Ft8.Tests` run in the same job), that margin isn't always enough.

This is the same class of bug this file has already hit and fixed once before — see
`WaitForKeyingAsync`'s doc comment at `QsoAnswererServiceTests.cs:123-131`:

> `State` and `Keying` are two independent fields... a single immediate check right after
> `WaitForStateAsync` returns is a genuine race (**observed failing on CI's Linux runner, not
> locally**) rather than a fixed-order guarantee.

That fix replaced a fixed check with a poll loop. This test still uses the fixed-delay pattern
`WaitForKeyingAsync` was written specifically to avoid.

## 3. Suggested fix (not urgent — batch with other test-hygiene work)

Replace `await Task.Delay(50);` before the `Received.InOrder(...)` assertion (and the equivalent in
`WaitRr73_Retry_BracketsRetransmissionWithTxReport`) with a poll that waits for the actual condition —
e.g. a small helper mirroring `WaitForStateAsync`'s shape that polls
`eventBus.ReceivedCalls().Count(...)` (or a similar NSubstitute call-count query) until the expected
number of `Publish` calls for this partner have landed, or the timeout elapses. Keep the existing
`Received.InOrder(...)` as the final assertion — only the synchronization before it needs to change.

Do **not** just increase the delay (e.g. `Task.Delay(200)`) — that raises the odds without eliminating
the race, and slows the suite for everyone in the meantime.

## 4. Scope

- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` — both retry-bracket tests noted above.
  Worth a quick grep for any other `Task.Delay(\d+);\s*//` comments in the same file/suite while in
  there, in case the pattern repears elsewhere (not confirmed, just worth a look given two prior
  instances of this exact species of flake in this codebase: `2026-07-05-f-003-ap-assist-flaky-decode-test.md`,
  `2026-07-18-n8-decodefilterstore-admitnewvalues-set-race-test-flake.md`).

## 5. References

- CI run: https://github.com/frank001/OpenWSFZ/actions/runs/29762105557 (job `88418984418`)
- Prior fix of the same bug class: `WaitForKeyingAsync`, `QsoAnswererServiceTests.cs:123-131`
- Prior flaky-test dev-tasks: `2026-07-05-f-003-ap-assist-flaky-decode-test.md`,
  `2026-07-18-n8-decodefilterstore-admitnewvalues-set-race-test-flake.md`
