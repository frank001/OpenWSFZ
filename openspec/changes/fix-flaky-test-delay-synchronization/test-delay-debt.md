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

All four files migrated onto `Poll`/`WaitForInboundBoundAsync` (a per-file helper in
`ExternalReportingServiceTests` polling the service's bound `_inboundClient`). Full local
regression: 5/5 consecutive clean runs of the four affected classes (46 tests) after migration.


### `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs` — MIGRATED, no exceptions

All 3 sites migrated: the ≥ 1 Hz persist waits on `SpyConfigStore.SaveCount`; the within-1 Hz
no-save case waits on `CatState.Status == Connected` (a completed poll proves the save branch was
evaluated — the within-threshold change means no save signal ever appears to poll for); the
failing-save case waits on the spy logger's `WarningCount`.

### `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs` — MIGRATED, 2 permanent justified exceptions remain

12 of the 14 sites migrated onto `Poll.WaitForEqualAsync`/`WaitForCallCountAsync`/`UntilAsync`
(status transitions; failure-suspension holds proven via poll-and-expect-timeout; reconnect and
PTT paths). The comment-text false-positive at the old line 224 (`Task.Delay(0, cancelledCt)`,
inside a code comment, never real code) was reworded away.

The 2 remaining sites are **simulated connection I/O latency** inside the mock `IRadioConnection`
in `SetPttAsync_ConcurrentWithPoll_NeverInterleaves` — the same "simulated-mock-latency" category
already justified in `QsoCallerServiceTests.cs` (line ~1253). Each `await Task.Delay(50)` makes a
mocked `GetDialFrequencyMhzAsync`/`SetPttAsync` call take measurable time so the re-entrancy guard
has a window in which to observe any overlap; without them both calls return instantly and the
test can never detect a serialisation violation. This is mock-input simulation, not a
test-synchronization barrier, so no polling helper applies.

tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:326: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs:334: Task.Delay(50)

### `tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs` — MIGRATED, no exceptions

All 4 sites migrated: the PTT-assert barrier waits on `SetPttAsync` being called; the two existing
hand-written poll loops became `Poll.WaitForCallCountAsync`/`UntilAsync`; the concurrency
"caller #2 stays blocked" negative wait became a poll-and-expect-timeout on `callCount == 2`.

### `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs` — MIGRATED, no exceptions

All 18 sites migrated: "let Reconcile bind" delays became `WaitForInboundBoundAsync` (polls the
bound `_inboundClient` — sending an inbound datagram before the socket is bound silently drops
it); "wait then assert AbortAsync/TryEngageAsync/LastFreeText" delays became
`Poll.WaitForCallAsync`/`WaitForEqualAsync`; the opted-out reply negative became a
poll-and-expect-timeout; the two between-sends pacing delays were removed (FIFO delivery on the
single inbound socket already orders them, and the trailing barrier proves processing); and the
StopAsync-Clear/Close test now waits for the initial Heartbeat+Status burst to actually be
received before stopping.


## Phase 3 — Remaining files across all four affected test projects

All remaining files migrated onto `Poll`. `OpenWSFZ.TestSupport` `ProjectReference`s were added to
`OpenWSFZ.Web.Tests`, `OpenWSFZ.Ft8.Tests`, and `OpenWSFZ.Audio.Tests`. Full local regression:
10/10 consecutive clean runs across all four affected test projects after migration.

Fully migrated, no exceptions:
- `GracefulStopDelegationTests.cs` (2) — router state → `Poll.WaitForEqualAsync`.
- `QsoAnswererServiceExternalReplyTests.cs` (2) — the `SeedCqBatchAsync` helper now polls the
  service's own volatile `_lastIdleDecodeBatch` (the exact field `TryEngageExternal` consults) via
  reflection, instead of a State-poll-plus-fixed-settle.
- `SerialRtsDtrPttControllerTests.cs` (3) — line-assert barrier, callCount poll, and a
  poll-and-expect-timeout negative (mirrors `CatPttControllerTests`).
- `LoggingPipelineTests.cs` (3) — file-content `do/while` polls → `Poll.UntilAsync` with the
  original assertion text carried into `timeoutMessage`.
- `SystemRestartEndpointTests.cs` (4) — fire-and-forget relaunch waits → `Poll.UntilAsync`; the
  refused-restart negative → poll-and-expect-timeout.
- `AuthMiddlewareTests.cs` (1) — "WS stays open" → poll-and-expect-timeout on the socket state.
- `CaptureManagerTests.cs`: the four `Task.WhenAny(Task.Delay(10), deadline)` hand-rolled
  `IsCapturing` polls (resolving design.md's Open Question — they are the same poll shape the shared
  library exists to replace, not a materially different pattern) → `Poll.UntilAsync(() =>
  !cm.IsCapturing, …)`. Sound because `CaptureManager` writes its termination log **before** the
  `finally` clears `_isCapturing`, so `IsCapturing == false` guarantees the asserted log is present.

### `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs` — MIGRATED, 1 permanent justified exception

The one remaining site is **simulated audio-capture chunk rate** inside the `InfiniteAudioSource`
test double (`await Task.Delay(10, ct)` between yielded chunks) — the double's data-production
cadence, not a test-synchronization barrier. Same "simulated feed rate" category as
`QsoAnswererServiceTests`' background-feeder throttle.

tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs:29: Task.Delay(10, ct)

### `tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs` — MIGRATED, 2 permanent justified exceptions

Both remaining sites are a **simulated delayed port release** inside a `Task.Run` background task
(`await Task.Delay(300)` / `await Task.Delay(250)` before `blocker.Stop()`) that defines the test
scenario "the old daemon instance releases the port after N ms." The retry loop under test has a
multi-second budget, so this is a deliberate scenario-timeline parameter well inside that budget —
not a synchronization-barrier guess about how long an async operation takes.

tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs:79: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs:134: Task.Delay(250)


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
