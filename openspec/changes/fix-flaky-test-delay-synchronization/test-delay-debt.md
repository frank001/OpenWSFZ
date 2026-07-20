# Test-Delay Synchronization Debt

Entries here are bare `Task.Delay(<numeric literal>)` synchronization-barrier call sites,
explicitly acknowledged as pending migration onto the shared `OpenWSFZ.TestSupport` polling library
(`Poll.UntilAsync` and its typed wrappers — see design.md Decision 1). They are excluded from Gate
**G10**'s (`tools/check_test_delay_sync.py`) untracked-bare-delay check until the phase that covers
them lands.

**Format:** `path:line: matched-text` — one entry per currently-known site, seeded via
`python3 tools/check_test_delay_sync.py --list` (guaranteeing the initial inventory matches exactly
what the gate script itself will scan for). Matching is by **(file, matched-text)**, not by line
number — see that script's module docstring for why this tolerates ordinary line drift from
unrelated edits between phases without needing every entry's line number kept perfectly in sync.

**Rule:** a migration PR removes its own entries as bare delays are replaced with shared-library
polling helpers (see `tasks.md`). An entry that's still here once its phase's migration PR has
landed is a stale debt entry — remove it as part of that same PR, per the standard convention this
file follows from `traceability-debt.md` (G3).


## Phase 1 — Live flake fix + the two dominant files (Answerer/Caller)

`PttWatchdogTests.cs` (includes the live flake `Disarm_BeforeTimeout_CallbackNeverInvoked`),
`QsoAnswererServiceTests.cs`, `QsoCallerServiceTests.cs` — the latter two also have their
own hand-duplicated `WaitForStateAsync`/`WaitForKeyingAsync`/`WaitForKeyDownAsync`/
`WaitForPublishCountAsync` private helpers deleted in this phase (design.md Decision 5),
which is why entries below include those helpers' own internal poll-loop delay lines
(e.g. the `await Task.Delay(10);` inside each helper's `while` loop) — an already-correct
pattern, not itself risky, but still a currently-matching site that must be tracked until
the whole helper method it lives in is deleted.


### `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` — MIGRATED, 6 permanent justified exceptions remain

52 of the original 58 sites migrated onto `Poll`/`WaitForBatchDrainedAsync` (a private per-file
helper polling `_channel.Reader.Count == 0`, since the decode channel is specific to this test
class, not something the shared `OpenWSFZ.TestSupport` library should know about). Full local
regression: 5/5 consecutive clean runs of the whole file, all 106 tests, after migration.

**Design correction found during migration:** the two `WaitReport_SilenceAfterRetry_IsSkipped` /
`WaitRr73_SilenceAfterRetry_IsSkipped` tests initially failed (2/106) when migrated to
`WaitForBatchDrainedAsync` alone — `Channel<T>.Reader.Count == 0` proves a batch was *dequeued* by
`QsoAnswererService.ExecuteAsync`'s loop, not that `ProcessBatchAsync` (including any retry-TX
transmit work) has *finished* acting on it; the next cycle's batch could race ahead of the current
one's still-in-flight retry, corrupting the skip/retry cycle count. Fixed by waiting for the
specific, precise signal each cycle actually produces instead: `Poll.WaitForCallCountAsync` on
`KeyUpAsync`'s count for cycles expected to fire a retry (TransmitAsync's `finally` always calls
`KeyUpAsync` immediately after `KeyDownAsync` on normal completion — the strongest available proof
a transmit-and-release sequence is fully done), and `WaitForBatchDrainedAsync` only for genuine
skip cycles (which have no observable side effect to poll for at all).

The 6 remaining sites are two distinct, deliberately **not** migrated shapes — no polling helper
fits either, and forcing one would be worse than the fixed delay it replaces:

- **Background feeder throttle** (2 sites, `Task.Delay(10, feedCts.Token)`, lines ~1065 and 1891):
  a `Task.Run` loop continuously feeding synthetic noise decodes every 10ms until cancelled, to
  keep retries cycling without pause while a watchdog-timeout race is proven. The 10ms *is* the
  feed rate — a deliberate test-load parameter, not a guess at how long something takes.
- **Wall-clock stray-wakeup settle** (4 sites, `Task.Delay(50)`, lines ~2504, 2534, 2613, 2646,
  each already preceded by `sut._wakeupChannel.Reader.TryRead(out _)`): `AnswerCqAsync`/
  `EngageAtAsync`'s wakeup push is computed from real `DateTimeOffset.UtcNow`, not the test's
  injected `FakeTimeProvider`, so it races the background loop's own concurrent read of the same
  internal channel. There is no externally observable condition to poll for this internal race
  (see each site's own inline comment); this is a deliberate, documented wall-clock margin, not a
  synchronization-barrier guess about production behavior — same rationale already accepted at the
  precedent this file itself cites (`QsoCallerServiceTests`).

tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1065: Task.Delay(10, feedCts.Token)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1891: Task.Delay(10, feedCts.Token)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2504: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2534: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2613: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2646: Task.Delay(50)

### `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` — MIGRATED, 5 permanent justified exceptions remain

40 of the original 45 sites migrated onto `Poll`/a per-file `WaitForBatchDrainedAsync(Channel<DecodeBatch>,
TimeSpan?)` helper (this file has no class-level `_channel` field — every SUT is built per-test via
`BuildIsolatedSut`/inline construction — so the helper takes the channel explicitly rather than
defaulting to an instance field the way `QsoAnswererServiceTests`' sibling helper does). Full local
regression: 8/8 consecutive clean runs of the whole file, all 64 tests, after migration — deliberately
run more than Answerer's 5x given this file shares the exact same skip/retry cycle-sequencing shape
that broke once during the Answerer migration (see that file's debt-file note); no repeat of that
failure surfaced here, but the extra runs were worth the few seconds given the precedent.

The 5 remaining sites are the same two categories already established and justified in
`QsoAnswererServiceTests.cs` above — no polling helper fits either:

- **Wall-clock stray-wakeup settle** (4 sites, `Task.Delay(50)`, lines ~524, 1338, 1643, 1782, each
  already preceded by `sut._wakeupChannel.Reader.TryRead(out _)`): identical rationale to
  `QsoAnswererServiceTests`' equivalent sites — `SelectResponderAsync`'s wakeup push is computed
  from real wall-clock time, racing the background loop's own concurrent read of the same internal
  channel, with no externally observable condition to poll for.
- **Simulated KeyDownAsync latency** (1 site, line ~1253, `.Returns(c => Task.Delay(100,
  (CancellationToken)c.Args()[0]))`): a mock configuration, not a test synchronization wait — see
  `HandleWaitAnswer_NoneMode_RetriesWhenNoBatchResponder`'s own XML doc comment: without this,
  `KeyDownAsync` returns instantly and the `TxCq`/`TxAnswer` state window is too narrow for any
  poller (shared library or otherwise) to ever observe.

tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:524: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1253: Task.Delay(100, (CancellationToken)c.Args()[0])
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1338: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1643: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1782: Task.Delay(50)


## Phase 2 — External reporting and CAT polling/PTT files


### `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs` (3)

tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs:46: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs:86: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs:124: Task.Delay(400)

### `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs` (14)

tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:43: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:74: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:108: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:113: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:162: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:174: Task.Delay(20)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:217: Task.Delay(250)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:224: Task.Delay(0, cancelledCt)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:226: Task.Delay(600)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:284: Task.Delay(20)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:312: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:320: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:337: Task.Delay(20)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:344: Task.Delay(300)

### `tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs` (4)

tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs:149: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs:199: Task.Delay(20)
tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs:233: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs:241: Task.Delay(100)

### `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs` (18)

tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:294: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:311: Task.Delay(500)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:367: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:535: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:881: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:886: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:897: Task.Delay(500)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:933: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:938: Task.Delay(500)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:983: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:988: Task.Delay(500)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1020: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1025: Task.Delay(500)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1079: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1092: Task.Delay(500)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1125: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1129: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:1134: Task.Delay(500)


## Phase 3 — Remaining files across all four affected test projects

`CaptureManagerTests.cs` (`Task.WhenAny(Task.Delay(10), deadline)` shape) is reviewed
case-by-case per design.md's Open Questions — its entries stay tracked here until task 4.4
resolves whether it needs migration or is a materially different, already-safe pattern.


### `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs` (5)

tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs:28: Task.Delay(10, ct)
tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs:139: Task.Delay(10)
tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs:164: Task.Delay(10)
tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs:215: Task.Delay(10)
tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs:243: Task.Delay(10)

### `tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs` (2)

tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs:79: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs:134: Task.Delay(250)

### `tests/OpenWSFZ.Daemon.Tests/GracefulStopDelegationTests.cs` (2)

tests/OpenWSFZ.Daemon.Tests/GracefulStopDelegationTests.cs:114: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/GracefulStopDelegationTests.cs:123: Task.Delay(10)

### `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs` (2)

tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs:127: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs:130: Task.Delay(10)

### `tests/OpenWSFZ.Daemon.Tests/SerialRtsDtrPttControllerTests.cs` (3)

tests/OpenWSFZ.Daemon.Tests/SerialRtsDtrPttControllerTests.cs:188: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/SerialRtsDtrPttControllerTests.cs:262: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/SerialRtsDtrPttControllerTests.cs:270: Task.Delay(100)

### `tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs` (3)

tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs:141: Task.Delay(20)
tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs:180: Task.Delay(20)
tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs:357: Task.Delay(20)

### `tests/OpenWSFZ.Web.Tests/AuthMiddlewareTests.cs` (1)

tests/OpenWSFZ.Web.Tests/AuthMiddlewareTests.cs:384: Task.Delay(500)

### `tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs` (4)

tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs:150: Task.Delay(700)
tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs:171: Task.Delay(700)
tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs:227: Task.Delay(700)
tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs:242: Task.Delay(700)


## Permanent exemption — `Poll.UntilAsync`'s own test fixtures

`tests/OpenWSFZ.TestSupport.Tests/PollTests.cs` is explicitly allowed small literal
delays by construction (design.md Decision 3): it simulates a background action
completing after a short delay, to prove the polling primitive itself observes it —
the delay is not a synchronization barrier substituting for a poll, `Poll.UntilAsync`
is the thing under test. `tests/OpenWSFZ.TestSupport/**` (the library's own
implementation) is excluded from Gate G10's scan entirely and needs no debt-file
entries at all; this project is a sibling folder, not covered by that exclusion, so its
entries are tracked here instead and are not expected to ever be removed.


### `tests/OpenWSFZ.TestSupport.Tests/PollTests.cs` (3)

tests/OpenWSFZ.TestSupport.Tests/PollTests.cs:72: Task.Delay(30)
tests/OpenWSFZ.TestSupport.Tests/PollTests.cs:107: Task.Delay(30)
tests/OpenWSFZ.TestSupport.Tests/PollTests.cs:134: Task.Delay(20)
