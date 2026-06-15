# QA Review — `fix/d007-d008-abort-race-watchdog`

**Date:** 2026-06-15  
**Reviewed by:** QA  
**Branch:** `fix/d007-d008-abort-race-watchdog`  
**Commit reviewed:** `6e1bed5`  
**Verdict:** ❌ Not approved — 3 required changes before merge

---

## Summary

The D-008 fix (removing `ResetWatchdog` from `RetryOrAbortAsync`) is correct and requires no further work.

The D-007 fix (`linked.Token.ThrowIfCancellationRequested()`) is correct in the **TxAnswer** path but leaves the race open in the **TxReport** and **Tx73** paths, because `ResetWatchdog` is called *before* `TransmitAsync` in those two paths, silently discarding any abort that arrived in the intervening window.

Both new regression tests have assertion defects that prevent them from serving as genuine guards against the bugs they claim to cover.

---

## Required changes

### R-1 — D-007 fix incomplete: CTS swap race in TxReport and Tx73 paths

**Severity: High.** The current fix works for TxAnswer but not for TxReport or Tx73.

**Root cause:** `ResetWatchdog` *replaces* `_txCts` with a brand-new
`CancellationTokenSource`. It is called **before** `TransmitAsync` in two places:

```csharp
// HandleWaitReportAsync — signal-report branch:
ResetWatchdog(tx);            // ← creates NEW _txCts (CTS_new)
SetStateAndNotify(QsoState.TxReport);
await TransmitAsync(...);     // linked = CreateLinkedTokenSource(stoppingToken, CTS_new.Token)

// ExecuteTx73Async:
ResetWatchdog(tx);            // ← creates NEW _txCts (CTS_new)
SetStateAndNotify(QsoState.Tx73);
await TransmitAsync(...);     // linked = CreateLinkedTokenSource(stoppingToken, CTS_new.Token)
```

If `AbortAsync` runs on the HTTP thread between the batch read returning and the
`ResetWatchdog` call — a genuine preemption window — it reads and cancels the *old*
`_txCts`. `ResetWatchdog` then installs a fresh, uncancelled CTS. `TransmitAsync` builds
its `linked` token from the new CTS, which is not cancelled. `ThrowIfCancellationRequested`
does not fire. The abort is silently lost and:

- In the TxReport path: state advances to WaitRr73 despite the abort.
- In the Tx73 path: state advances to QsoComplete *and* `AppendQsoAsync` writes an ADIF
  record for an operator-aborted QSO — a direct violation of the adif-log spec (§3).

**Why TxAnswer is safe:** `HandleIdleAsync` calls `StartWatchdog`, which uses `CancelAfter`
on the *existing* `_txCts` rather than replacing it. The CTS is the same object throughout
TxAnswer, so `AbortAsync` always cancels the right token.

**Fix:** move the pre-TX `ResetWatchdog` call to *after* `TransmitAsync` returns, following
the same Start → TX → Reset pattern that `HandleIdleAsync` already uses.

#### HandleWaitReportAsync — signal-report branch

```csharp
// BEFORE:
ResetWatchdog(tx);
SetStateAndNotify(QsoState.TxReport);
await TransmitAsync(reportMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
ResetWatchdog(tx);
_skipNextRetry = true;
SetStateAndNotify(QsoState.WaitRr73);

// AFTER:
SetStateAndNotify(QsoState.TxReport);
await TransmitAsync(reportMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
// D-007: reset watchdog AFTER TX so AbortAsync cannot cancel a pre-swap CTS that
// TransmitAsync never sees. The first ResetWatchdog (pre-TX) is removed; the
// post-TX reset (now the only one) is sufficient and safe.
ResetWatchdog(tx);
_skipNextRetry = true;
SetStateAndNotify(QsoState.WaitRr73);
```

#### ExecuteTx73Async

```csharp
// BEFORE:
ResetWatchdog(tx);
SetStateAndNotify(QsoState.Tx73);
await TransmitAsync(msg73, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

// QSO complete.
SetStateAndNotify(QsoState.QsoComplete);
...
await _adifLog.AppendQsoAsync(record).ConfigureAwait(false);

// AFTER:
SetStateAndNotify(QsoState.Tx73);
await TransmitAsync(msg73, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
// D-007: reset watchdog after TX for the same reason as HandleWaitReportAsync.
ResetWatchdog(tx);

// QSO complete.
SetStateAndNotify(QsoState.QsoComplete);
...
await _adifLog.AppendQsoAsync(record).ConfigureAwait(false);
```

After this change: if an abort arrives before either `SetStateAndNotify(TxReport/Tx73)`,
the old `_txCts` is still current when `TransmitAsync` builds its `linked` token.
`ThrowIfCancellationRequested` fires correctly. The `ResetWatchdog` after `TransmitAsync`
is never reached, which is the correct outcome for an aborted TX.

---

### R-2 — D-008 test: `keyDownCalls < 10` assertion cannot catch a regression

**Severity: Medium.** The test passes whether or not D-008 is fixed.

With 5 noise batches at 50 ms intervals, the channel empties after ~250 ms. The A-01
skip-guard means only 2–3 retry TXs fire (≤ 3 `KeyDownAsync` calls total) before the
channel is dry. Once empty, the service blocks in `ReadNextBatchAsync`; the 300 ms watchdog
fires — and this happens identically with or without the D-008 fix, because the critical
distinction (watchdog resets on retry vs. doesn't) only manifests when retries are
*continuously cycling*. The assertion `< 10` passes in both cases.

**Verification:** restore `ResetWatchdog(tx)` in `RetryOrAbortAsync` (re-introduce D-008).
The test still passes. It is not a regression guard.

**Fix:** tighten the bound to match what actually happens with the fix in place.

```csharp
// BEFORE:
keyDownCalls.Should().BeLessThan(10,
    "watchdog must fire before retry count reaches 10");

// AFTER:
// With the D-008 fix: TxAnswer (1) + at most 2 retry TXs before channel empties = 3 total.
// If D-008 regresses and watchdog resets on every retry, the watchdog still fires eventually,
// but only AFTER more retries cycle — with continuous feeding the count could reach 10.
// A bound of 4 is tight enough to catch the regression while tolerating scheduler jitter.
keyDownCalls.Should().BeLessThan(4,
    "watchdog must abort the QSO with no more than one retry TX cycle (TxAnswer + 1 retry)");
```

Alternatively, restructure the test to feed batches continuously in a background loop while
the service runs, which would let the retry cycle accumulate and make the distinction
observable. The tight-bound approach above is simpler and adequate given the 300 ms watchdog.

---

### R-3 — D-007 test: ADIF `File.Exists` assertion is vacuous

**Severity: Medium.** The assertion can never fail, regardless of whether the D-007 fix
is present or absent.

`AppendQsoAsync` is called in exactly one place in the service: inside `ExecuteTx73Async`,
which is only reached when an RR73 or RRR message arrives. The D-007 test never injects
such a message. No ADIF write can occur in this test scenario. The assertion
`File.Exists(adifPath).Should().BeFalse(...)` is therefore always true — it tests nothing.

If the D-007 fix is absent (no `ThrowIfCancellationRequested`) and the abort fails, the
service advances to `WaitRr73` and blocks waiting for an RR73. The `WaitForStateAsync`
call at line 664 times out and throws `TimeoutException` before the ADIF assertion is ever
reached. The ADIF check is dead code in the failure path.

**Fix:** remove the ADIF assertion from this test. The meaningful assertions are the state
and partner checks on lines 665–666, which correctly capture the D-007 contract.

```csharp
// REMOVE these lines entirely — they test nothing in this scenario:
var adifPath = System.IO.Path.Combine(adifDir.Path, "ADIF.log");
System.IO.File.Exists(adifPath).Should().BeFalse(
    "no ADIF record shall be written when a QSO is aborted (adif-log spec §3)");
```

If ADIF-on-abort coverage is desired, it belongs in a separate test that drives the service
all the way to Tx73 (by injecting the RR73 message), then aborts during that TX and
confirms no ADIF file is created. Note that after R-1 is applied, an abort during Tx73 TX
will now correctly propagate, so that test would become meaningful.

---

## Discretionary observations (no action required before merge)

### D-1 — `TempDirectory` helper duplicated across three test files

`tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` lines 33–46 add a fourth copy of
the same private `TempDirectory` class. The same body (modulo the prefix string) already
exists in `JsonConfigStoreTests.cs`, `TxConfigTests.cs`, and `OpenWSFZ.Config.Tests`. A
shared `TestHelpers/TempDirectory.cs` in each test project would prevent further copies.
Not a correctness issue; noted for the next housekeeping pass.

### D-2 — `_watchdogDurationOverride` is a test-only field on a production class

`src/OpenWSFZ.Daemon/QsoAnswererService.cs` lines 71–72, 96–107. The field and the internal
7-argument constructor survive into the production binary. The idiomatic .NET 8 alternative
is to inject `TimeProvider` into the public constructor and use `FakeTimeProvider` in tests,
which eliminates both the bespoke field and the `??` guards in `StartWatchdog`/`ResetWatchdog`.
The current approach is pragmatic and introduces no correctness defect. Flagged for
consideration on a future refactor.

---

## Change map (required items only)

| # | File | Change |
|---|---|---|
| R-1a | `src/OpenWSFZ.Daemon/QsoAnswererService.cs` | Remove pre-TX `ResetWatchdog` in signal-report branch of `HandleWaitReportAsync`; keep post-TX call |
| R-1b | `src/OpenWSFZ.Daemon/QsoAnswererService.cs` | Move `ResetWatchdog` to after `TransmitAsync` in `ExecuteTx73Async` |
| R-2  | `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` | Tighten `keyDownCalls` bound from `< 10` to `< 4` |
| R-3  | `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` | Remove vacuous `File.Exists(adifPath)` assertion |

No other files require modification. No new constructors. No schema changes.

---

## Verification checklist (after changes)

```
dotnet build OpenWSFZ.slnx -c Release    # 0 errors, 0 warnings
dotnet test  OpenWSFZ.slnx -c Release    # ≥ 444 passed, 0 failures
```

Re-submit the branch for review once all three required items are addressed.
