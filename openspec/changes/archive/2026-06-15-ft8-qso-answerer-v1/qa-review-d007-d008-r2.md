# QA Review (Round 2) — `fix/d007-d008-abort-race-watchdog`

**Date:** 2026-06-15  
**Reviewed by:** QA  
**Verdict:** ❌ Not approved — 1 required change before merge

R-1 (CTS swap race) and R-3 (vacuous ADIF assertion) are approved.  
R-2 (D-008 test) is not — the fix applied was correct but the underlying recommendation
in `qa-review-d007-d008.md` was wrong. This document supersedes R-2 from that document.

---

## Required change

### R-2 (revised) — D-008 test must use a continuous feeder, not a fixed 5-batch loop

**The problem with the current implementation:** changing the bound from `< 10` to `< 4`
does not make the test a genuine regression guard. With only 5 noise batches at 50 ms
intervals, the channel empties at approximately t = 200 ms. Once empty, the service blocks
in `ReadNextBatchAsync` and the watchdog fires eventually — regardless of whether the bug
is present. Both paths yield exactly 3 `KeyDownAsync` calls. `< 4` passes in both cases.

| Condition | KeyDown count | Idle reached | `< 4` passes? |
|---|---|---|---|
| Fix present | 3 | ~300 ms | ✅ — correct |
| Bug restored | 3 | ~450 ms | ✅ — **false pass** |

**Why the bug requires a continuous feeder to detect:** D-008's symptom is that retries
keep the watchdog perpetually reset *while cycling*. When the channel drains, cycling
stops, and the watchdog fires regardless. A continuous feeder prevents the channel from
ever draining, which is the only condition under which the bug prevents the watchdog from
firing.

**Replace the entire `Watchdog_FiresBeforeRetryExhaustion_WhenPartnerSilent` test body
with the following:**

```csharp
[Fact(DisplayName = "D-008: Watchdog fires before retry count is exhausted when partner goes silent")]
public async Task Watchdog_FiresBeforeRetryExhaustion_WhenPartnerSilent()
{
    // Arrange: very short watchdog so the test does not wait 60 s.
    // RetryCount=100 — if D-008 is present, retries reset the watchdog on every cycle
    // and Idle is never reached as long as the channel keeps being fed.
    // If D-008 is fixed, the watchdog fires independently at ~300 ms.
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
            RetryCount      = 100,   // enormous — watchdog must fire long before this
            WatchdogMinutes = 4,     // overridden by watchdogDuration below
        }
    });

    var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
    var channel = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();

    var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                  adifLog, NullLogger<QsoAnswererService>.Instance,
                  watchdogDurationOverride: watchdogDuration);

    using var stopCts = new CancellationTokenSource();
    await sut.StartAsync(stopCts.Token);

    // Trigger CQ answer → WaitReport.
    channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz,
        $"CQ {PartnerCall} {PartnerGrid}")]);
    await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

    // Feed noise continuously so retries keep cycling without pause.
    // With the D-008 fix:  watchdog fires ~300 ms after WaitReport → Idle by ~400 ms.
    // With the D-008 bug:  every retry resets the watchdog to 300 ms; the channel never
    //                      empties; Idle is never reached → WaitForStateAsync times out.
    using var feedCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
    var feedTask = Task.Run(async () =>
    {
        while (!feedCts.IsCancellationRequested)
        {
            channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz,
                "CQ Q2NOISE IO91")]);
            try   { await Task.Delay(10, feedCts.Token); }
            catch (OperationCanceledException) { break; }
        }
    });

    // Tight deadline distinguishes the two paths.
    // Fixed: Idle in ~300 ms. Buggy: never reaches Idle within 600 ms → TimeoutException.
    await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromMilliseconds(600));
    feedCts.Cancel();
    await feedTask;

    sut.State.Should().Be(QsoState.Idle,
        "watchdog must abort the session independently of the retry counter");

    await stopCts.CancelAsync();
    await sut.StopAsync(CancellationToken.None);
    await ptt.DisposeAsync();
}
```

**Verify this catches the regression:** restore `ResetWatchdog(tx)` in `RetryOrAbortAsync`
and confirm the test throws `TimeoutException` at the `WaitForStateAsync` call. Then revert
and confirm the test passes.

---

## Discretionary observations (no action required before merge)

**D-1 — `adifDir` / `adifStore` in the D-007 test are now dead setup**

After R-3 removed the `File.Exists` assertion, `TempDirectory` and the second mock
`IConfigStore` serve no purpose. The `AdifLogWriter` can be constructed from `store`
directly, as the D-008 test already does. Clean up on a housekeeping pass.

**D-2 — `ResetWatchdog` after Tx73 TX is a no-op**

`SafeAbortToIdleAsync` (called immediately after) replaces `_txCts` with a fresh
no-timeout CTS, discarding the one just created by `ResetWatchdog`. The call is harmless
but serves no purpose. Remove on a housekeeping pass.

---

## Verification checklist

```
dotnet build OpenWSFZ.slnx -c Release    # 0 errors, 0 warnings
dotnet test  OpenWSFZ.slnx -c Release    # ≥ 444 passed, 0 failures
```

Re-submit for review once R-2 is addressed.
