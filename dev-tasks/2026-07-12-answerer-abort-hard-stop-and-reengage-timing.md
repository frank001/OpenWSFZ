# Handoff: D-CALLER-018/016/019 — Abort must be a hard stop; re-engagement is needlessly delayed 30 s

**Date:** 2026-07-12
**Prepared by:** QA engineer (analysis of `logs/openswfz-20260712T211150Z.log`, Captain report)
**Status:** Awaiting developer action
**Defect IDs:** D-CALLER-018 (critical), D-CALLER-016 (high), D-CALLER-019 (medium, cleanup)
**Severity:** Critical — the operator's Abort action does not reliably stop the transmitter, and once
that happens there is currently **no recourse**: the armed engagement fires regardless of how many
times Abort is clicked. This is a repeat of the abort-race family first seen in D-CALLER-009/010; this
occurrence is a new root cause, not a regression of the earlier fix.

---

## 0. Captain's stated requirement (authoritative — design to this)

> Abort just means stop all and everything, bring the application to an idle state. Do not engage TX
> again unless the operator decides otherwise. When double-clicking a QSO already engaged it should
> switch to resume the QSO. When double-clicking a new CQ it should engage on the new one. And, not to
> forget, when a CQ is double-clicked it should engage immediately at the very first opportunity instead
> of waiting 30 seconds before engaging.

Three separate defects below implement this. Read D-CALLER-018 first — it is the one that actually
explains the reported "it engages after an abort" behaviour.

---

## 1. Context

### 1.1 What the log shows

Across `logs/openswfz-20260712T211150Z.log`, the Answerer engaged CX1RL three times in a row, ~29–30 s
apart, despite the operator aborting every single time:

```
23:18:30.754  pending CQ target 'CX1RL' — answering at A phase
23:18:30.766  KeyDown — PTT asserted
23:18:31.779  TX abort requested (HTTP) — cancelling active session (partner: CX1RL, state: TxAnswer)
23:18:31.861  KeyUp — PTT released
23:18:31.878  aborted to Idle (was: TxAnswer, partner: CX1RL)
23:18:31.892  pending target 'CX1RL' — late start (1.9 s into window); deferring to next occurrence  ← re-armed, same request
23:18:36.599–23:18:38.427  FOURTEEN POST /api/v1/tx/abort calls, all 200 OK, all no-ops (state already Idle)
23:19:00.776  pending CQ target 'CX1RL' — answering at A phase   ← fires anyway, 29 s later
23:19:00.778  KeyDown — PTT asserted
```

The same pattern repeats for LU1DA (23:13:30→23:14:00) and ZL4TT (23:17:30). This is not one glitch; it
is the system working exactly as coded, which is the problem.

### 1.2 Root cause chain

- `POST /api/v1/tx/engage-decode` (D-CALLER-012, `WebApp.cs` line 1251) is a **double-click** gesture:
  abort whatever is running, then dispatch the clicked row (`AnswerCqAsync` for a `CQ ...` row,
  `EngageAtAsync` for a directed report/RR73/73 row). This is legitimate, explicit operator intent —
  double-clicking a row is asking to engage it — and per the Captain's requirement above, it is correct
  for it to arm a fresh target immediately, including re-answering the same partner if they're still
  calling CQ.
- The problem is that the **dedicated Abort button** (`POST /api/v1/tx/abort` → `QsoAnswererService.AbortAsync`,
  line 257) cannot cancel that armed target once `_state` has returned to `Idle`:

  ```csharp
  public async Task AbortAsync(CancellationToken ct = default)
  {
      if (_state == QsoState.Idle) return;   // ← everything below is skipped, INCLUDING clearing
                                               //   _pendingTargetCallsign / _jumpPartner
      ...
  }
  ```

  `_pendingTargetCallsign` (armed by `AnswerCqAsync`/`ArmPendingTarget`, line 387) and `_jumpPartner`
  (armed by `EngageAtAsync`, line 229) are **independent of `_state`** — they are consulted at the top of
  `HandleIdleAsync` (lines 564 and 632) specifically so they can fire *while* Idle. Only
  `SafeAbortToIdleAsync` (line 1263) clears them, and that method only runs as part of a state
  transition *out of* an active session — never when the service is already sitting Idle with a pending
  target quietly waiting for its window.

  Net effect: once a target is armed, the Abort button is a no-op for the remainder of that ~60 s
  window (the 14 clicks at 23:18:36–38 prove this) and the engagement **will** fire. There is currently
  no operator action that can prevent it. This directly contradicts "do not engage TX again unless the
  operator decides otherwise."

### 1.3 Secondary finding: needless 30 s delay

`MaxLateStartSeconds = 1.5` (`QsoAnswererService.cs` line 139, added by D-CALLER-013) leaves very little
room: an FT8 tone is 12.64 s in a 15 s window, so the true physical ceiling is `15 − 12.64 = 2.36 s`.
Decode processing alone consumes 0.4–0.7 s in this log before a click is even possible. Every
manually-armed engagement in this session — both the original clicks and the abort-triggered
re-engagements — landed at 1.9 s or 3.7 s into its window, both past the 1.5 s cutoff, and both were
deferred a full 30 s (phase alternates every 15 s, so the next *matching-phase* window is always two
cycles away, never one). This is the "always skips two cycles" / "waiting 30 seconds" complaint.

### 1.4 Tertiary finding: duplicate double-click handlers (noise, not the root cause)

Every CQ row in `web/js/main.js` carries **two** independent `dblclick` listeners:

- Line 733 (TX-D01, pre-dates D-CALLER-012): calls `postTxAnswerCq(...)` directly.
- Line 847 (D-CALLER-012): calls `postTxEngageDecode(...)` — abort, then dispatch, and its own
  `Case A` (WebApp.cs line 1318) already reproduces exactly what the line-733 handler does.

A single double-click fires both. The line-733 call always loses the race and returns 409 (log lines
894/910, 360/376, etc.) — harmless, but it is dead code doubling every double-click's network traffic
and cluttering the log with a guaranteed spurious 409 on every single engagement. Worth removing while
in this code, but it is not what caused the reported behaviour — D-CALLER-012's own Step 1 abort is
what's logged as "TX abort requested (HTTP)" in every instance above, not a separate Abort-button click.

---

## 2. Branch

Create a new branch off `main`: `fix/d-caller-018-abort-hard-stop`. No branch of this name currently
exists (verified 2026-07-12) and this is not an amendment to any in-flight work — start clean from `main`.

---

## 3. Actions

### 3.1 — D-CALLER-018: `AbortAsync` must unconditionally clear armed targets (Critical)

**File:** `src/OpenWSFZ.Daemon/QsoAnswererService.cs`, `AbortAsync` (currently lines 257–280).

Move the pending-target/jump-in clear (the same fields `SafeAbortToIdleAsync` clears at lines
1274–1278) **above** the `Idle` guard, so it always runs regardless of `_state`:

```csharp
public async Task AbortAsync(CancellationToken ct = default)
{
    // D-CALLER-018: unconditionally clear any armed-but-not-yet-fired pending target or
    // jump-in, regardless of current _state. A target armed by AnswerCqAsync / EngageAtAsync /
    // TryEngageExternal fires independently of _state (it is specifically checked while Idle —
    // see HandleIdleAsync). Previously this method returned immediately whenever _state was
    // already Idle, which meant an armed target could NOT be cancelled by the operator once the
    // service returned to Idle — it fired regardless, up to ~30 s later, no matter how many times
    // Abort was clicked. Abort must be an unconditional hard stop: nothing may re-engage after it
    // until the operator explicitly requests it again. See
    // dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md.
    lock (_stateLock)
    {
        _pendingTargetCallsign    = null;
        _pendingTargetFrequencyHz = 0.0;
        _pendingTargetIsAPhase    = false;
        _pendingTargetSetAt       = default;
        _jumpPartner              = null;
    }

    if (_state == QsoState.Idle) return;

    _logger.LogInformation(
        "TX abort requested (HTTP) — cancelling active session (partner: {Partner}, state: {State}).",
        _partner, _state);

    _operatorAbortRequested = true;
    _txCts.Cancel();

    try
    {
        await _pttController.KeyUpAsync(ct).ConfigureAwait(false);
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "KeyUpAsync threw during abort — ignoring.");
    }
}
```

No change needed to `SafeAbortToIdleAsync` — its own clear is now redundant in the pure-Abort path but
still correct/necessary for the watchdog-timeout and retry-exhaustion paths that don't go through
`AbortAsync` at all.

**Do not** add any additional "latch" or cool-down flag. `engage-decode`'s Step 1 also calls
`AbortAsync`, then Step 2 deliberately re-arms a fresh target — that re-arm is a *new*, explicit operator
gesture (the double-click itself) and must keep working exactly as today. The fix above only guarantees
that a *separate, later* Abort-button click always wins and leaves nothing armed — it does not prevent
`engage-decode`'s own Step 2 from arming within the same request.

### 3.2 — D-CALLER-016: raise the late-start threshold (High)

**File:** `src/OpenWSFZ.Daemon/QsoAnswererService.cs`, line 139.

```csharp
/// <summary>
/// Maximum number of seconds into a 15-second FT8 window that TX may still be started.
/// An FT8 signal is 12.64 s; the true physical ceiling is 15 - 12.64 = 2.36 s — starting any
/// later overruns into the next window and can prevent the far station from decoding cleanly.
/// D-CALLER-013 originally set this to 1.5 s, leaving only ~0.8-1.0 s of realistic click budget
/// after decode processing (0.4-0.7 s observed) — in practice this meant almost every manual
/// click (openswfz-20260712T211150Z.log: 1.9 s and 3.7 s observed) missed its window and was
/// deferred a full 30 s (phase alternates every 15 s, so the next matching-phase window is
/// always two cycles away, never one — see D-CALLER-016). 2.0 s leaves a 0.36 s hard safety
/// margin against overrun, comfortably covering the ~50-90 ms KeyDown/device-open jitter observed
/// in production logs, while catching realistic decode-to-click latency instead of nearly always
/// missing it.
/// </summary>
private const double MaxLateStartSeconds = 2.0;
```

Be honest in the PR description and with the Captain: this reduces *how often* the 30 s deferral is hit,
it does not eliminate it. A click that lands beyond ~2.3 s into its window genuinely cannot start a
12.64 s FT8 transmission in that window without overrunning — that remaining wait is FT8 protocol
physics (alternating 15 s slots), not a bug, and no threshold tuning removes it. Update the existing
D-CALLER-013 tests (`QsoAnswererServiceTests.cs` lines ~2351–2521) that assert the exact
`MaxLateStartSeconds` boundary — they currently use 1.5 s and 5 s/0.5 s/0.2 s fixtures; adjust the
"late" fixtures to land clearly past 2.0 s (e.g. keep 5 s) and the "timely" fixtures to land clearly
under it (e.g. keep 0.5 s, 0.2 s — both still pass) so the tests remain meaningful rather than just
re-encoding whatever the new constant is.

### 3.3 — D-CALLER-019: remove the redundant legacy dblclick handler (Medium, cleanup)

**File:** `web/js/main.js`, lines 727–776 (the TX-D01 `.decode-cq` dblclick handler that calls
`postTxAnswerCq` directly).

Remove this block entirely. `D-CALLER-012`'s handler (line 841 onward) already reproduces it exactly:
its `Case A` dispatch (`WebApp.cs` line 1318) parses a `CQ ...` message and calls the identical
`AnswerCqAsync`, and additionally handles the abort-first step this old handler never did. Keeping both
means every CQ-row double-click fires two competing HTTP requests, one of which is guaranteed to lose
and return 409 — pure noise that made this session's log harder to diagnose. Confirm no other code
depends on the `inFlight` guard or `cqCycleStartUtc` dataset attribute this block referenced (the D-CALLER-012
handler reads `tr.dataset.cqCycleStartUtc` independently at line 855, so it is unaffected by the removal).

`postTxAnswerCq` itself (`web/js/api.js`) should remain — it is still the function `engage-decode`'s
front-end awaits indirectly is not — check whether anything else in `main.js` calls `postTxAnswerCq`
directly before deleting its import; if nothing else does, remove the now-unused import too.

---

## 4. Acceptance criteria

**AC-1 (D-CALLER-018).** With a pending target armed (e.g. via `engage-decode`) and the service already
back at `Idle`, clicking Abort clears the pending target. Confirm: advance time/inject the next
matching-phase batch and assert `IPttController.KeyDownAsync` is **not** called. Add this as an explicit
unit test in `QsoAnswererServiceTests.cs` — arm via `AnswerCqAsync` with a late-start time so it doesn't
fire immediately, call `AbortAsync`, then push the correct-phase batch and assert no TX.

**AC-2 (D-CALLER-018).** Same as AC-1 but for a jump-in target (`EngageAtAsync`) instead of a pending
CQ target.

**AC-3 (D-CALLER-018).** Regression: `AbortAsync` while genuinely mid-TX still cancels the active
transmission exactly as before (existing `AbortAsync` tests must continue to pass unmodified).

**AC-4 (D-CALLER-016).** A click landing ≤2.0 s into the correct-phase window fires TX in that same
window. A click landing >2.0 s is deferred to the next matching-phase window (~30 s later) — update
existing D-CALLER-013 tests per §3.2 rather than duplicating them.

**AC-5 (D-CALLER-019).** Double-clicking a CQ row produces exactly one outbound POST
(`/api/v1/tx/engage-decode`), not two. Confirm in the Network tab or via a front-end test that
`postTxAnswerCq` is no longer wired to CQ-row `dblclick`.

**AC-6 (end-to-end, matches the Captain's stated requirement — verify with the `verify` skill against a
real session, not just unit tests).**
- Abort while mid-QSO with any partner → service reaches Idle and stays there; no TX fires afterward
  regardless of what CQs continue to be decoded, until the operator takes a new explicit action.
- Double-clicking the CQ row of the station currently engaged → resumes/re-engages that same partner
  (no behavioural change required here beyond AC-4's timing fix — `engage-decode`'s existing dispatch
  already does this correctly once 3.1/3.2 land).
- Double-clicking a different station's CQ row while mid-QSO → aborts the current session and engages
  the new one (existing D-CALLER-012 behaviour, unchanged).
- None of the above engagements take the needless extra 15 s cycle that 3.2 fixes.

**AC-7.** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

**AC-8.** Full test suite — 0 failures (current baseline ≥948 passed per project state notes; new/updated
tests add to the count).

---

## 5. Live verification requirement

This defect was only caught by reading a real operating log, not by unit tests — the existing D-CALLER-013
unit tests all passed while this was broken, because none of them exercised "Abort while a target is
armed but the service is already Idle." Before merge, run a real loopback session (VB-CABLE or equivalent,
per the D-CALLER-013/014 annex notes on audio isolation) reproducing the exact sequence from
§1.1 — engage, abort mid-TX, then hammer the Abort button — and attach the resulting log excerpt to the
PR showing no re-engagement occurs. Unit tests alone are not sufficient sign-off for this class of defect.

---

## 6. References

- Evidence log: `logs/openswfz-20260712T211150Z.log` — lines 887–1115 (CX1RL sequence, most complete),
  296–392 (LU1DA), 683–733 (ZL4TT)
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs`:
  - `AbortAsync` — lines 257–280 (fix target, §3.1)
  - `MaxLateStartSeconds` — line 139 (fix target, §3.2)
  - `SafeAbortToIdleAsync` pending/jump clear — lines 1271–1279 (pattern to replicate in §3.1)
  - `ArmPendingTarget` — lines 387–412
  - Pending-target consumption — lines 632–712
  - Jump-in consumption — lines 564–629
- `src/OpenWSFZ.Web/WebApp.cs`:
  - `POST /api/v1/tx/abort` — lines 1101–1117
  - `POST /api/v1/tx/engage-decode` — lines 1251–1408 (Step 1 abort-and-poll at 1282–1303, Step 2
    dispatch at 1305–1396)
- `web/js/main.js`:
  - TX-D01 legacy CQ-row dblclick handler — lines 727–776 (removal target, §3.3)
  - D-CALLER-012 dblclick handler — lines 841–887
  - Dedicated Abort button handler — lines 1366–1385 (unaffected; the bug was server-side)
- `dev-tasks/2026-06-27-d-caller-013-late-tx-guard.md` — original `MaxLateStartSeconds` rationale
  (1.5 s chosen without production click-latency data; this task supersedes that value)
- `dev-tasks/2026-06-26-d-caller-009-rearm-race.md`, `dev-tasks/2026-06-27-d-caller-010-dblclick-abort.md`
  — prior occurrences of the same abort-race defect family, on the Caller side; different root cause,
  same category of mistake (assuming an abort-adjacent action has fully settled when it hasn't, or that
  "Idle" implies "nothing pending")
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` lines 2351–2521 — existing D-CALLER-013
  late-start tests to extend (§3.1 new tests) and adjust (§3.2)
