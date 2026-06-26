# Handoff: D-CALLER-003 — CallerPartnerSelect=None immediately retransmits CQ

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action

---

## 1. Context

Live session `openswfz-20260626T131847Z.log` confirmed that when the operator
sets `CallerPartnerSelect = None` (pileup-mode checkbox unchecked) the QSO
never starts. Every `POST /api/v1/tx/select-responder` click returns **409
Conflict** because the service has already left `WaitAnswer` and re-entered
`TxCq` before the operator can click.

The defect is a single missing guard in `QsoCallerService.HandleWaitAnswerAsync`.

---

## 2. Branch

`feat/qso-caller` (existing) — add one commit directly to this branch.

---

## 3. Root cause

`HandleWaitAnswerAsync` contains this comment followed by code that contradicts it:

```csharp
// None mode with no pending responder: stay in WaitAnswer, no TX.

// No matching message — retry or abort.
if (_skipNextRetry) { _skipNextRetry = false; return; }
await RetryOrAbortAsync(tx, stoppingToken);   // ← fires unconditionally in None mode
```

`RetryOrAbortAsync` in `WaitAnswer` state transitions the service to `TxCq` and
calls `TransmitAsync` within ~80 ms of the batch being processed. The HTTP
endpoint guard at `WebApp.cs:734`:

```csharp
if (qsoController.State != QsoState.WaitReport)
    return Results.Conflict();
```

then fires for every operator click that arrives after that transition. The
operator cannot click fast enough — the window is measured in milliseconds.

The `TryParseResponder` scan (which knows whether any decoded message addressed
our callsign) runs only inside the `if (CallerPartnerSelect == First)` block.
`None` mode never checks the batch content; it treats every cycle without a
`_pendingResponderCallsign` as a missed CQ response.

---

## 4. Actions

### 4.1 — Add the None-mode responder-hold guard

**File:** `src/OpenWSFZ.Daemon/QsoCallerService.cs`

**Location:** `HandleWaitAnswerAsync`, immediately before the line
`if (_skipNextRetry) { _skipNextRetry = false; return; }`.

**Current code (abbreviated):**

```csharp
        // None mode with no pending responder: stay in WaitAnswer, no TX.

        // No matching message — retry or abort.
        // A-01: first empty cycle after entering WaitAnswer = our own TX window; skip it.
        if (_skipNextRetry) { _skipNextRetry = false; return; }
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
```

**Replace with:**

```csharp
        // None mode with no pending responder: stay in WaitAnswer if this batch
        // contains at least one response to our CQ — the operator must click a
        // highlighted row.  Only proceed to retry when the batch is genuinely empty
        // of responses.
        if (tx.CallerPartnerSelect == CallerPartnerSelectMode.None)
        {
            foreach (var r in batch.Results)
            {
                if (TryParseResponder(r.Message, ours, out _, out _, _logger))
                    return; // responses present — hold in WaitAnswer
            }
        }

        // No matching message — retry or abort.
        // A-01: first empty cycle after entering WaitAnswer = our own TX window; skip it.
        if (_skipNextRetry) { _skipNextRetry = false; return; }
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
```

**No other files require changes.**

---

### 4.2 — Unit tests

Add to the existing caller test file (or a new
`QsoCallerService_NoneModeTests.cs`):

1. **`HandleWaitAnswer_NoneMode_HoldsWhenResponderPresent`**
   — Configure `CallerPartnerSelect = None`.  Feed a batch containing a message
   addressed to our callsign (e.g. `"PD2FZ QTEST JO33"`).  Assert:
   - State remains `WaitAnswer` after the batch is processed.
   - No TX was fired (mock `IPttController.KeyDownAsync` was not called).

2. **`HandleWaitAnswer_NoneMode_RetriesWhenNoBatchResponder`**
   — Configure `CallerPartnerSelect = None`, `_skipNextRetry = false`.
   Feed an empty batch (or one whose messages do not match our callsign).
   Assert:
   - Service retransmits CQ (`KeyDownAsync` called once).
   - State transitions to `TxCq` then back to `WaitAnswer`.

3. **`HandleWaitAnswer_NoneMode_FiresTxAfterOperatorClick`**
   — Configure `CallerPartnerSelect = None`.
   Feed a batch with a responder → service holds.
   Call `SelectResponderAsync` with that callsign.
   Feed a wakeup batch.
   Assert:
   - State advances past `WaitAnswer` to `TxReport`.
   - `_partner` is set to the clicked callsign.

---

## 5. Acceptance criteria

QA will verify the following before approving merge to `main`:

1. **Hold on responder:** When `CallerPartnerSelect = None` and a decoded cycle
   contains a message addressed to our callsign, the service remains in
   `WaitAnswer` — no CQ retransmission.

2. **Retry on empty cycle:** When `CallerPartnerSelect = None` and no decoded
   message addresses our callsign, the service retransmits the CQ (same
   behaviour as before this fix, but now conditional on batch content).

3. **Operator click accepted:** A `POST /api/v1/tx/select-responder` call
   issued after the service has held in `WaitAnswer` returns **200**, not 409.

4. **QSO completes:** After a successful row-click the QSO advances through
   `TxReport → WaitRr73 → TxRr73 → QsoComplete` in the normal way.

5. **First mode unaffected:** `CallerPartnerSelect = First` behaviour is
   unchanged — still auto-engages the first responder.

6. **Existing tests green:** `dotnet test OpenWSFZ.slnx -c Release` — zero
   failures.

7. **Zero build warnings:** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors,
   0 warnings.

---

## 6. References

- Session log: `logs/openswfz-20260626T131847Z.log`
- Defect confirmed at lines 875, 902, 969, 1028, 1079 (successive 409 cluster
  timestamps: 15:20:32, 15:21:02, 15:21:34, 15:22:01, 15:22:02)
- Broken code: `src/OpenWSFZ.Daemon/QsoCallerService.cs`
  `HandleWaitAnswerAsync` — the six lines before `RetryOrAbortAsync`
- `TryParseResponder` (already correct): same file, line ~918
- `WebApp.cs:734` — the 409 guard that was correctly exposing the bug
- FR-PILEUP-001 implementation: `dev-tasks/2026-06-26-caller-highlighting-fix-and-pileup-mode.md`
