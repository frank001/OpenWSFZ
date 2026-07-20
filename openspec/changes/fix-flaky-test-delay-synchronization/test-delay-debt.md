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


### `tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs` (8)

tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:28: Task.Delay(2000)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:33: Task.Delay(20)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:54: Task.Delay(30)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:58: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:81: Task.Delay(2000)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:94: Task.Delay(20)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:105: Task.Delay(2000)
tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs:108: Task.Delay(600)

### `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` (58)

tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:117: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:139: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:158: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:166: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:181: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:230: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:273: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:379: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:440: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:513: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:523: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:525: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:527: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:529: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:546: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:548: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:550: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:552: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:554: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:571: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:588: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:592: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:611: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:631: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:635: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:651: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:655: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:659: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:668: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:685: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:689: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:693: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:701: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:732: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1095: Task.Delay(10, feedCts.Token)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1148: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1201: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1396: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1467: Task.Delay(400)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1529: Task.Delay(400)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1656: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1852: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1856: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:1915: Task.Delay(10, feedCts.Token)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2528: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2558: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2598: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2635: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2668: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2704: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2831: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2837: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2874: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2886: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2914: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2926: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:3423: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:3516: Task.Delay(300)

### `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` (45)

tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:131: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:152: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:380: Task.Delay(10)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:505: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:508: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:550: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:556: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:613: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:875: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:879: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:994: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1003: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1005: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1007: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1009: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1056: Task.Delay(120)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1110: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1118: Task.Delay(100)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1122: Task.Delay(100)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1235: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1239: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1280: Task.Delay(100, (CancellationToken)c.Args()[0])
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1305: Task.Delay(250)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1350: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1354: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1365: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1659: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1670: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1802: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1809: Task.Delay(50)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1856: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1860: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1955: Task.Delay(150)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1957: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2246: Task.Delay(100)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2282: Task.Delay(100)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2353: Task.Delay(300)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2472: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2478: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2519: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2561: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2567: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2606: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2611: Task.Delay(200)
tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:2650: Task.Delay(300)


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
