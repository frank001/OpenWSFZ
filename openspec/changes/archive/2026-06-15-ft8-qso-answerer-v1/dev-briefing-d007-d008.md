# Developer Briefing — D-007 & D-008 (QsoAnswererService abort defects)

**Date:** 2026-06-15
**Issued by:** QA
**Branch:** `fix/d007-d008-abort-race-watchdog`
**Scope:** Two defects in `QsoAnswererService` found during UAT of tasks 8.5 and 8.6

---

## Background

Tasks 8.5 (operator abort) and 8.6 (watchdog abort) of the `ft8-qso-answerer-v1` change
were tested on 2026-06-15 (UAT session `artefacts/ft8-qso-answerer-v1_items/202606152213`).
Two defects were found. Both are confined to `QsoAnswererService.cs`; no other files require
modification except the test file.

**GitHub issues:** #18 (D-007) and #19 (D-008).

---

## D-007 — Abort race: state machine advances despite active abort

### Defect summary

When `POST /api/v1/tx/abort` is issued while TX audio is playing, the state machine
advances to the next state (and eventually writes an ADIF record) rather than aborting
to Idle. The abort call is processed correctly by `AbortAsync`; the bug is in
`TransmitAsync`, which does not inspect the cancellation token after `KeyDownAsync` returns.

### Evidence (log `202606152213/openswfz-20260615T185524Z.log`)

```
[157] TX abort requested (HTTP) — cancelling active session (partner: PD2FZ, state: "TxReport")
[158] TX KeyUp — stopping playback
[164] TX KeyDown — playback completed          ← returns normally after KeyUp stopped audio
[165] QsoAnswererService: TX complete for "PD2FZ PD2FZ/P R+00"  ← continues despite abort
[167] state → "WaitRr73"                       ← state advanced despite abort
[206] FR-051: ADIF QSO logged                  ← ADIF written despite abort (NFR violation)
```

### Root cause

`TransmitAsync` links `stoppingToken` and `_txCts.Token` into a combined token and
passes it to `KeyDownAsync`. When `AbortAsync` is called:

1. `_txCts.Cancel()` sets the linked token as cancelled.
2. `KeyUpAsync` stops WASAPI audio output.
3. Stopping the audio causes `KeyDownAsync` to return **normally** (not by throwing).
4. The combined token is cancelled, but `TransmitAsync` never checks it — it just logs
   "TX complete" and returns, as if the transmission had finished successfully.
5. The caller (e.g. `HandleWaitReportAsync`) receives a normal return and advances state.

### File and line

`src/OpenWSFZ.Daemon/QsoAnswererService.cs`, `TransmitAsync` method, lines 481–497:

```csharp
// BEFORE (lines 492–496):
using var linked = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken, _txCts.Token);
await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);

_logger.LogDebug("QsoAnswererService: TX complete for \"{Message}\".", message);
```

### Fix — C1

Add one line immediately after the `KeyDownAsync` await, before the debug log:

```csharp
// AFTER:
using var linked = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken, _txCts.Token);
await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);
linked.Token.ThrowIfCancellationRequested();   // ← ADD THIS LINE

_logger.LogDebug("QsoAnswererService: TX complete for \"{Message}\".", message);
```

**Why this works:**
- If `_txCts` was cancelled (operator abort or watchdog) the linked token is cancelled.
- `ThrowIfCancellationRequested()` throws `OperationCanceledException` before the debug
  log fires. The exception propagates up through `TransmitAsync` and all callers.
- `ExecuteAsync` catches it at line 149:
  ```csharp
  catch (OperationCanceledException)
  {
      // Watchdog or abort fired during a TX operation.
      await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
  }
  ```
  This correctly aborts to Idle.
- If only `stoppingToken` was cancelled (clean shutdown), the first catch
  `when (stoppingToken.IsCancellationRequested)` takes priority → clean `break`.
- **ADIF side-effect resolved:** `ExecuteTx73Async` calls `TransmitAsync` before writing
  the ADIF record. With the fix, the throw happens before reaching `_adifLog.AppendQsoAsync`,
  so no ADIF record is written on abort. No further change to `ExecuteTx73Async` is required.

---

## D-008 — Watchdog timer reset on every retry, preventing expiry

### Defect summary

The watchdog timer is reset after every retry retransmission, including retransmissions
that do not change the state variable. The spec requires the timer to reset only on
"every successful state transition." With `watchdogMinutes=1` and `retryCount` ≥ 2,
each 30-second FT8 cycle resets the watchdog before it can expire. The watchdog can never
fire as long as retries keep occurring.

### Evidence (log `202606152213/openswfz-20260615T185524Z.log`)

```
[449] TX KeyDown — playback completed
[450] watchdog reset for 1 minutes             ← reset after retry TX (not a state transition)
[462] retry count 1 exceeded 1 — aborting QSO  ← retry counter terminated; watchdog never fired
```

The test was conducted with `watchdogMinutes=1` and `retryCount=1`. The watchdog was
reset at line 450 (after the retry TX), which means it had a full minute to run from that
point. The retry counter expired first at line 462, demonstrating the watchdog cannot
overtake the retry mechanism — the opposite of its intended role as a safety net.

### Root cause

`ResetWatchdog(tx)` is called inside `RetryOrAbortAsync` (line 470), which runs on every
retry including those that remain in `WaitReport` or `WaitRr73`. It should be called only
at genuine forward state transitions.

Comparing existing `ResetWatchdog` call sites:

| Call site | Transitioning from → to | Correct? |
|---|---|---|
| `HandleIdleAsync` line 291 | `TxAnswer` → `WaitReport` | ✓ Genuine transition |
| `HandleWaitReportAsync` line 343 | `WaitReport` → `TxReport` | ✓ Genuine transition |
| `HandleWaitReportAsync` line 347 | `TxReport` → `WaitRr73` | ✓ Genuine transition |
| `ExecuteTx73Async` line 419 | `WaitRr73/WaitReport` → `Tx73` | ✓ Genuine transition |
| **`RetryOrAbortAsync` line 470** | **Stays in same state** | **✗ Spurious reset** |

### File and line

`src/OpenWSFZ.Daemon/QsoAnswererService.cs`, `RetryOrAbortAsync` method, line 470:

```csharp
// BEFORE (lines 467–471):
    // Retransmit the last TX message.
    await TransmitAsync(_lastTxMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
    _skipNextRetry = true; // A-01: retry TX window also needs its silence cycle skipped
    ResetWatchdog(tx);     // ← BUG: resets watchdog on every retry
    // Stay in current state (WaitReport or WaitRr73).
}
```

### Fix — C2

Remove the `ResetWatchdog(tx)` call from `RetryOrAbortAsync`:

```csharp
// AFTER:
    // Retransmit the last TX message.
    await TransmitAsync(_lastTxMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
    _skipNextRetry = true; // A-01: retry TX window also needs its silence cycle skipped
    // Stay in current state (WaitReport or WaitRr73).
    // NOTE: watchdog is NOT reset here — retries are not state transitions.
}
```

**Why this works:**
- The watchdog CTS (`_txCts`) is started with `CancelAfter` in `StartWatchdog` when the
  service first leaves Idle. With the spurious `ResetWatchdog` removed, the timer runs
  uninterrupted across retry cycles.
- Genuine transitions (lines 291, 343, 347, 419) still call `ResetWatchdog`, giving the
  watchdog a full `watchdogMinutes` from the point of each real advance.
- If the partner goes silent and the retry budget is not exhausted, the watchdog fires,
  cancels `_txCts`, and `ExecuteAsync` catches the `OperationCanceledException` → aborts
  to Idle.

---

## Regression test requirements — C3

Add the following two tests to
`tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`.

### Prerequisite: inject watchdog duration for testing

The current constructor does not support sub-minute watchdog timeouts, which would require
tests to wait 60+ seconds. Before writing the tests, add an `internal` constructor
parameter `TimeSpan? watchdogDurationOverride = null` and pass it through to
`StartWatchdog` / `ResetWatchdog`.

Add to `QsoAnswererService.cs`:

```csharp
// At class level, alongside the other private fields:
private readonly TimeSpan? _watchdogDurationOverride; // non-null in tests only

// Add a second constructor for testing:
/// <summary>
/// Test constructor — allows watchdog duration override to avoid 1-minute waits in unit tests.
/// </summary>
internal QsoAnswererService(
    ChannelReader<IReadOnlyList<DecodeResult>> decodeChannel,
    IConfigStore                               configStore,
    IPttController                             pttController,
    TxEventBus                                 txEventBus,
    AdifLogWriter                              adifLog,
    ILogger<QsoAnswererService>                logger,
    TimeSpan                                   watchdogDurationOverride)
    : this(decodeChannel, configStore, pttController, txEventBus, adifLog, logger)
{
    _watchdogDurationOverride = watchdogDurationOverride;
}
```

In `StartWatchdog` and `ResetWatchdog`, replace `TimeSpan.FromMinutes(minutes)` with:

```csharp
var timeout = _watchdogDurationOverride ?? TimeSpan.FromMinutes(minutes);
```

### Test T-D007 — Abort during TX resolves to Idle without ADIF

```csharp
[Fact(DisplayName = "D-007: AbortAsync during TX stops state machine at Idle; no ADIF written")]
public async Task Abort_DuringTx_ResolvesToIdleWithoutAdif()
{
    // Arrange: PTT whose KeyDownAsync completes normally even when cancelled,
    // simulating the race where KeyUp stops audio but KeyDown returns non-exceptionally.
    var racyPtt = Substitute.For<IPttController>();
    racyPtt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
    racyPtt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

    var store = Substitute.For<IConfigStore>();
    store.Current.Returns(new AppConfig() with
    {
        Tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 4,
        }
    });

    using var adifDir  = new TempDirectory();
    var adifStore      = Substitute.For<IConfigStore>();
    adifStore.Current.Returns(store.Current with
    {
        DecodeLog = new DecodeLogConfig { Path = System.IO.Path.Combine(adifDir.Path, "ALL.TXT") }
    });
    var adifLog  = new AdifLogWriter(adifStore, NullLogger<AdifLogWriter>.Instance);
    var channel  = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();
    var sut      = new QsoAnswererService(channel.Reader, store, racyPtt, new TxEventBus(),
                       adifLog, NullLogger<QsoAnswererService>.Instance);

    using var stopCts = new CancellationTokenSource();
    await sut.StartAsync(stopCts.Token);

    // Act: trigger a QSO and abort immediately once TX starts.
    channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]);
    await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

    // Advance to TxReport so we can abort mid-TX.
    channel.Writer.TryWrite([new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]);
    // Abort as soon as TxReport starts (state transitions through TxReport quickly in mocks).
    await sut.AbortAsync();

    // Assert: service returns to Idle.
    await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));
    sut.State.Should().Be(QsoState.Idle, "abort must win the race against TX completion");
    sut.Partner.Should().BeNull("partner must be cleared on abort");

    // Assert: no ADIF record written.
    var adifPath = System.IO.Path.Combine(adifDir.Path, "ADIF.log");
    System.IO.File.Exists(adifPath).Should().BeFalse(
        "no ADIF record shall be written when a QSO is aborted (adif-log spec §3)");

    await stopCts.CancelAsync();
    await sut.StopAsync(CancellationToken.None);
    await racyPtt.DisposeAsync();
}
```

### Test T-D008 — Watchdog fires before retry exhaustion

```csharp
[Fact(DisplayName = "D-008: Watchdog fires before retry count is exhausted when partner goes silent")]
public async Task Watchdog_FiresBeforeRetryExhaustion_WhenPartnerSilent()
{
    // Arrange: very short watchdog so the test does not wait 60 s.
    // RetryCount=10 means the retry path would take 10+ cycles (>5 minutes) to exhaust.
    // If D-008 is fixed the watchdog fires after ~300 ms; if broken, retries keep resetting it.
    var watchdogDuration = TimeSpan.FromMilliseconds(300);

    var ptt = Substitute.For<IPttController>();
    ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
    ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

    var store = Substitute.For<IConfigStore>();
    store.Current.Returns(new AppConfig() with
    {
        Tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 10,    // large — watchdog must fire first
            WatchdogMinutes = 4,     // value is overridden by watchdogDuration below
        }
    });

    var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
    var channel = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();

    // Use the internal test constructor that accepts a watchdog duration override.
    var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                  adifLog, NullLogger<QsoAnswererService>.Instance,
                  watchdogDurationOverride: watchdogDuration);

    using var stopCts = new CancellationTokenSource();
    await sut.StartAsync(stopCts.Token);

    // Trigger CQ answer → WaitReport.
    channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]);
    await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

    // Send silence cycles — partner is not responding.
    // Feed enough cycles that the retry path would reset the watchdog (if the bug is present).
    for (var i = 0; i < 5; i++)
    {
        channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "CQ Q2NOISE IO91")]);
        await Task.Delay(50);
    }

    // Assert: watchdog fires and aborts to Idle well before retry exhaustion.
    await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));
    sut.State.Should().Be(QsoState.Idle,
        "watchdog must abort the session independently of the retry counter");

    // Retry counter did not reach 10 — watchdog fired first.
    await ptt.Received(Arg.Is<int>(n => n < 10)).KeyDownAsync(Arg.Any<CancellationToken>());

    await stopCts.CancelAsync();
    await sut.StopAsync(CancellationToken.None);
    await ptt.DisposeAsync();
}
```

> **Note on `TempDirectory`:** this helper is already used in `JsonConfigStoreTests.cs`.
> If it is not visible from `OpenWSFZ.Daemon.Tests`, either replicate the pattern inline
> or move the helper to a shared test utilities project.

---

## Change map

| # | File | Change |
|---|---|---|
| C1 | `src/OpenWSFZ.Daemon/QsoAnswererService.cs` | Add `linked.Token.ThrowIfCancellationRequested()` after `KeyDownAsync` in `TransmitAsync` |
| C2 | `src/OpenWSFZ.Daemon/QsoAnswererService.cs` | Remove `ResetWatchdog(tx)` from `RetryOrAbortAsync` |
| C3a | `src/OpenWSFZ.Daemon/QsoAnswererService.cs` | Add internal `watchdogDurationOverride` constructor and wire `_watchdogDurationOverride` into `StartWatchdog`/`ResetWatchdog` |
| C3b | `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` | Add tests T-D007 and T-D008 |

No other files require modification. No database migrations. No config schema changes.

---

## Verification

```
dotnet build -c Release        # 0 errors, 0 warnings
dotnet test  -c Release        # all existing 442 tests green + 2 new tests pass
```

After the fix is merged, QA will re-run the manual tests for tasks 8.5 and 8.6:

**Task 8.5 re-test:** Start a QSO, issue `POST /api/v1/tx/abort` during TX. Confirm:
- State returns to Idle immediately.
- No ADIF record in `ADIF.log`.
- HTTP 200 returned.

**Task 8.6 re-test:** Set `watchdogMinutes=1`, `retryCount=5`. Start a QSO. At
`WaitReport`, silence WSJT-X (prevent it from decoding). After 1 minute, confirm:
- Service aborts to Idle with a Warning log entry naming the partner callsign.
- Retry counter did not reach 5.
- No ADIF record written.

QA will tick tasks 8.5 and 8.6 in `openspec/changes/ft8-qso-answerer-v1/tasks.md`
upon successful re-verification and archive the change.
