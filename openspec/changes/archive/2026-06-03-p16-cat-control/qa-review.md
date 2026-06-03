# QA Review — p16-cat-control (PR #20)

**Reviewer:** QA  
**Date:** 2026-06-03  
**Branch:** `feat/p16-cat-control`  
**PR:** https://github.com/frank001/OpenWSFZ/pull/20  
**Verdict:** ❌ Return for changes — three blocking issues; all fixes already in working tree

---

## What Was Reviewed

The full diff from `main` to `HEAD` on `feat/p16-cat-control`, plus the six uncommitted working-tree
changes detected via `git diff HEAD`. The working tree contains the fixes for all three blocking
issues but they have not been committed or pushed.

---

## Blocking Issues — Must Fix Before Merge

### B1 — `SerialCatConnection.CatCommand` sends `\r` and corrupts subsequent polls

**File:** `src/OpenWSFZ.Rig/SerialCatConnection.cs`

**Committed state (wrong):**
```csharp
private const string CatCommand = "FA;\r";
```

**Required state:**
```csharp
private const string CatCommand = "FA;";
```

**Why it matters:** The trailing carriage return is interpreted by some rig families as a second,
separate command. The rig replies to the `\r` with a `?;` error frame, which sits in the receive
buffer and is read as the response to the *next* `FA;` poll. The result is an alternating
success/failure pattern on every other poll cycle.

**Fix already in working tree:** Yes — `SerialCatConnection.cs` is modified in the working tree
to use `"FA;"`. The associated regression tests (`NineDigitResponse`,
`SendsCommandWithoutCarriageReturn`, `RigCommandError`) are also present in the working tree.

**Action:** Stage and commit the working-tree changes to `SerialCatConnection.cs` and
`SerialCatConnectionTests.cs`.

---

### B2 — `DaemonStatus` missing `CatConnectionStatus` field; all status responses omit CAT state

**Files:** `src/OpenWSFZ.Web/DaemonStatus.cs`, `src/OpenWSFZ.Web/WebApp.cs`,
`src/OpenWSFZ.Web/WebSocketHub.cs`

**Committed state (wrong) — `DaemonStatus.cs` ends at:**
```csharp
double DialFrequencyMHz = 0.0);   // record closes here — CatConnectionStatus absent
```

**Required state:**
```csharp
double  DialFrequencyMHz       = 0.0,
string  CatConnectionStatus    = "Disabled");
```

**Why it matters:** The `/api/v1/status` response, the initial WebSocket `status` event on
connect, and the `/api/v1/decode/start|stop` responses all use `DaemonStatus`. Without the
field, a browser client loading the page has no CAT indicator until a `cat_status` event
happens to be emitted — which requires a state *change* after load. FR-033 requires the
status bar to reflect live CAT state; a client loading after CAT has already settled to
`Connected` will never see that state.

**Fix already in working tree:** Yes — `DaemonStatus.cs` is modified to add the field, and
`WebApp.cs` and `WebSocketHub.cs` are both modified to pass `CatConnectionStatus:` at the
six `DaemonStatus(...)` constructor call sites.

**Action:** Stage and commit all three working-tree changes.

---

### B3 — Connect failure logged at `LogError`; FR-034 specifies Warning

**File:** `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs`

**Committed state (wrong):**
```csharp
_logger.LogError(ex,
    "CAT: failed to connect via {RigModel} — {Message}. Retrying in {Delay} s.", ...);
```

**Required state:**
```csharp
_logger.LogWarning(ex,
    "CAT: failed to connect via {RigModel} — {Message}. Retrying in {Delay} s.", ...);
```

**Why it matters:** FR-034 is explicit: *"shall log a Warning with the port/host and exception
message."* `LogError` signals a software defect or unrecoverable failure and triggers operator
alarm in production log-aggregation tooling. A serial port being held by another application is
an expected operational state, not an application error.

**Fix already in working tree:** Yes — the level is already changed to `LogWarning`.

**Action:** Stage and commit the working-tree change to `CatPollingService.cs`. See also the
minor note M1 below before committing.

---

## Minor Issues — Fix Alongside the Blocking Commits

### M1 — Working-tree change drops period from two log messages (regression)

**File:** `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs`

The working-tree fix for B3 also removes the `.` separating `{Message}` from `Retrying`:

```
// Working tree (wrong — period removed)
"CAT: failed to connect via {RigModel} — {Message} Retrying in {Delay} s."
"CAT: frequency poll failed via {RigModel} — {Message} Retrying in {Delay} s."

// Required (original period preserved)
"CAT: failed to connect via {RigModel} — {Message}. Retrying in {Delay} s."
"CAT: frequency poll failed via {RigModel} — {Message}. Retrying in {Delay} s."
```

Restore the period in both strings before committing `CatPollingService.cs`.

---

### M2 — `REQUIREMENTS.md` version history out of order; 1.12 absent

**File:** `REQUIREMENTS.md`

The change-log table at the end of the document currently reads:

```
| 1.11 | 2026-05-31 | ...
| 1.14 | 2026-06-02 | NFR-019 (brand neutrality)
| 1.13 | 2026-06-02 | NFR-017 + NFR-018
```

Problems:
- 1.12 is skipped entirely.
- 1.14 appears before 1.13 in the table (reverse chronological order).
- The document header correctly declares version 1.15.

Please swap rows 1.13 and 1.14 so the table reads chronologically, and insert a 1.12 entry
(the secrets-scan / `.gitignore` hardening change from this PR).

---

### M3 — `RigctldConnection._connected` is a non-volatile plain `bool`

**File:** `src/OpenWSFZ.Rig/RigctldConnection.cs`

```csharp
private bool _connected;   // should be volatile
```

`IsConnected` is part of the `IRadioConnection` public interface and is readable from any
thread. While `CatPollingService` sequences all writes in practice, the field is technically
observable stale without a memory barrier. `volatile` costs nothing and is consistent with the
`_status` field in `CatState`.

---

### M4 — `CatState.Update()` XML doc overstates atomicity

**File:** `src/OpenWSFZ.Daemon/Cat/CatState.cs`

The Interlocked exchange on `_dialFreqBits` and the volatile write to `_status` are two separate
instructions. The doc comment `Atomically updates frequency and connection status` is inaccurate.
Amend to: *"Updates frequency and connection status. Each field is individually atomic; the
two-field compound update is not."*

---

## Positive Observations

These are noted so the developer knows what is working well and need not be touched.

- `NaN`-as-null sentinel for `DialFrequencyMHz` via `Interlocked.Exchange` on the bit
  representation is the correct approach for a lock-free nullable double.
- `HasFreqChanged` handles all three null/non-null combinations correctly.
- `ISerialPort` / `ITcpConnection` internal interfaces expose exactly what the implementations
  require. `InternalsVisibleTo` for both the test project and `DynamicProxyGenAssembly2` is
  the correct NSubstitute incantation.
- `SafeDisconnectAsync` with `finally { (connection as IDisposable)?.Dispose(); }` is clean
  and will not leak port handles on failure paths.
- `CatEventBus` correctly insulates `OpenWSFZ.Daemon` from `OpenWSFZ.Web` internals.
- The D5 change-detection rule (`|Δfreq| ≥ 1 Hz || status changed`) is correctly implemented.
- `CatConfig` being a `record` means the `lastConfig != config` hot-reload detection in
  `CatPollingService` works correctly via structural equality.

---

## Summary Checklist for Developer

Before requesting a re-review, please confirm each item:

- [ ] `SerialCatConnection.CatCommand` changed to `"FA;"` (no `\r`)
- [ ] Regression tests for `\r` removal and 9-digit response committed
- [ ] `DaemonStatus` record has `CatConnectionStatus` field
- [ ] All six `DaemonStatus(...)` call sites in `WebApp.cs` and `WebSocketHub.cs` pass `CatConnectionStatus:`
- [ ] `CatPollingService` connect failure uses `LogWarning` (not `LogError`)
- [ ] Period restored in both warning log message strings (`{Message}. Retrying`)
- [ ] `REQUIREMENTS.md` version history rows swapped (1.13 before 1.14); 1.12 row added
- [ ] (Optional) `RigctldConnection._connected` marked `volatile`
- [ ] (Optional) `CatState.Update()` doc comment corrected

Items marked Optional are advisory; they do not block merge.

Manual acceptance gates (tasks 15 and 16 — hardware required) remain outstanding as expected
and are not blocking automated merge readiness.
