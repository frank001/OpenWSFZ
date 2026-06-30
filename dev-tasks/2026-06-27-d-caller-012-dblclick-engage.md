# Handoff: D-CALLER-012 — Double-Click Decode Row: Abort & Engage

**Date:** 2026-06-27
**Prepared by:** QA engineer
**Status:** Awaiting developer action
**Defect ID:** D-CALLER-012
**Severity:** High — operator has no way to interrupt a QSO in progress and pivot to
a newly decoded station without navigating buttons

---

## 1. Context

Previous work (D-CALLER-006, D-CALLER-009, D-CALLER-010, D-CALLER-011) attempted
incremental fixes to the abort-and-re-engage flow via single/double-click on teal
decode-responder rows. That lineage was on the unmerged `fix/caller-ux-fixes` branch
(D-CALLER-011 deferred). The branch is **abandoned**. Start fresh from `main`.

The Captain's requirement is broader and cleaner:

> **Any row in the decodes panel can be double-clicked at any time. The application
> immediately aborts everything, determines the correct response from the decode, and
> engages the QSO from that point.**

This replaces D-CALLER-006/010 entirely. D-CALLER-008 (WaitAnswer entry sweep) and
D-CALLER-009 (`pendingRearmAfterAbort`) are **not needed** under this design — the
backend handles abort + engage atomically, so the frontend deferred-rearm race does
not exist.

### What D-CALLER-012 requires

Steps on double-click, as specified by the Captain:

1. Full stop — abort, disarm TX, clear partner. No grace, no waiting.
2. Determine the decode from the row selected.
3. Identify the partner callsign from the message.
4. Determine the correct A/B TX window (opposite phase from the decoded message).
5. Determine the correct FT8 response for the message type.
6. Engage the state machine at that response point.
7. Update the GUI to reflect the new state.

---

## 2. Branch

`fix/d-caller-012-dblclick-engage` — **new branch from `main`**.

Pure stack: all changes are in well-isolated locations. No renames, no refactoring.

---

## 3. Actions

### 3.1 — New enum: `EngagePoint`

**New file:** `src/OpenWSFZ.Abstractions/EngagePoint.cs`

```csharp
namespace OpenWSFZ.Abstractions;

/// <summary>
/// The exchange point at which to engage a QSO mid-sequence (D-CALLER-012).
/// Used by <see cref="IQsoController.EngageAtAsync"/>.
/// </summary>
public enum EngagePoint
{
    /// <summary>
    /// Reply to a plain signal report: TX <c>PARTNER OURS R+00</c> → enter WaitRr73.
    /// Used when the decode carries a bare signal report (e.g. <c>PD2FZ W1ABC -07</c>).
    /// </summary>
    SendReport = 1,

    /// <summary>
    /// Confirm a roger-report or RRR: TX <c>PARTNER OURS RR73</c> → QsoComplete.
    /// Used when the decode carries <c>R±NN</c> or <c>RRR</c>
    /// (e.g. <c>PD2FZ W1ABC R-07</c>, <c>PD2FZ W1ABC RRR</c>).
    /// </summary>
    SendRr73 = 2,

    /// <summary>
    /// Send the final 73: TX <c>PARTNER OURS 73</c> → QsoComplete.
    /// Used when the decode carries <c>RR73</c>
    /// (e.g. <c>PD2FZ W1ABC RR73</c>).
    /// </summary>
    Send73 = 3,
}
```

---

### 3.2 — Add `EngageAtAsync` to `IQsoController`

**File:** `src/OpenWSFZ.Abstractions/IQsoController.cs`

Append the following method to the interface (after `SelectResponderAsync`):

```csharp
/// <summary>
/// Arms a mid-exchange jump-in: the service will TX the correct response message
/// at the next FT8 cycle boundary of the <em>opposite</em> phase to
/// <paramref name="theirCycleStart"/> and advance the state machine accordingly.
/// </summary>
/// <param name="partnerCallsign">Callsign of the partner.</param>
/// <param name="frequencyHz">Audio frequency of the decoded message, in Hz.</param>
/// <param name="theirCycleStart">UTC cycle-start of the decode batch.</param>
/// <param name="point">Which exchange message to transmit next.</param>
/// <param name="ct">Cancellation token.</param>
/// <remarks>
/// The service MUST already be in <see cref="QsoState.Idle"/> when this is called.
/// The caller (HTTP layer) is responsible for aborting and waiting for Idle first.
/// <c>QsoCallerService</c> does not implement this — it returns a no-op.
/// </remarks>
Task EngageAtAsync(
    string partnerCallsign,
    double frequencyHz,
    DateTimeOffset theirCycleStart,
    EngagePoint point,
    CancellationToken ct);
```

---

### 3.3 — Implement `EngageAtAsync` in `QsoAnswererService`

**File:** `src/OpenWSFZ.Daemon/QsoAnswererService.cs`

#### 3.3.1 — New private jump-in fields

Add directly below the existing `_pendingTargetSetAt` field (inside the
`_stateLock`-guarded group). Use the **same** `_stateLock` object — do not
introduce a second lock.

```csharp
// ── Jump-in state (D-CALLER-012 EngageAtAsync) ────────────────────────────
// Set by EngageAtAsync; consumed by HandleIdleAsync before the pending-target block.
// Protected by _stateLock. Cleared by SafeAbortToIdleAsync.
private EngagePoint    _jumpPoint;          // only meaningful when _jumpPartner != null
private string?        _jumpPartner;
private double         _jumpFreqHz;
private bool           _jumpIsAPhase;       // false = B-phase, i.e. opposite of their decode
private DateTimeOffset _jumpSetAt;
```

#### 3.3.2 — Implement `EngageAtAsync`

Add after `SelectResponderAsync` (the existing no-op):

```csharp
/// <inheritdoc/>
public Task EngageAtAsync(
    string         partnerCallsign,
    double         frequencyHz,
    DateTimeOffset theirCycleStart,
    EngagePoint    point,
    CancellationToken ct)
{
    lock (_stateLock)
    {
        // Safety guard: caller (HTTP layer) must have brought us to Idle first.
        if (_state != QsoState.Idle)
            return Task.CompletedTask;

        _jumpPoint    = point;
        _jumpPartner  = partnerCallsign;
        _jumpFreqHz   = frequencyHz;
        _jumpIsAPhase = !IsAPhase(theirCycleStart);  // TX in the opposite slot
        _jumpSetAt    = DateTimeOffset.UtcNow;
    }

    // Push a wakeup so the background loop fires within the current cycle window,
    // matching the pattern used by AnswerCqAsync (_wakeupChannel push).
    var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
    _wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));
    return Task.CompletedTask;
}
```

#### 3.3.3 — Clear jump-in state in `SafeAbortToIdleAsync`

In `SafeAbortToIdleAsync`, locate the existing `lock (_stateLock)` block that
clears `_pendingTargetCallsign`:

```csharp
lock (_stateLock) { _pendingTargetCallsign = null; }
```

Extend it to also clear the jump-in partner:

```csharp
lock (_stateLock)
{
    _pendingTargetCallsign = null;
    _jumpPartner           = null;   // D-CALLER-012: clear any pending jump-in
}
```

#### 3.3.4 — Add jump-in dispatch at the top of `HandleIdleAsync`

In `HandleIdleAsync`, add the following block **immediately before** the existing
`// ── Phase-aware pending-target handling` comment. The jump-in takes priority
over the pending-target (which is the normal CQ-click path):

```csharp
// ── Jump-in handler (D-CALLER-012) ───────────────────────────────────────────
// EngageAtAsync arms this block.  Fires before the pending-target block so
// that a double-click engage takes effect even if a stale pending-target exists.
{
    EngagePoint    jumpPoint;
    string?        jumpPartner;
    double         jumpFreqHz;
    bool           jumpIsAPhase;
    DateTimeOffset jumpSetAt;

    lock (_stateLock)
    {
        jumpPoint    = _jumpPoint;
        jumpPartner  = _jumpPartner;
        jumpFreqHz   = _jumpFreqHz;
        jumpIsAPhase = _jumpIsAPhase;
        jumpSetAt    = _jumpSetAt;
    }

    if (jumpPartner is not null)
    {
        // 60-second expiry guard (stale jump-in after a decode-loop stall).
        if (DateTimeOffset.UtcNow - jumpSetAt > TimeSpan.FromSeconds(60))
        {
            _logger.LogWarning(
                "QsoAnswererService: jump-in target '{Partner}' expired — discarding.",
                jumpPartner);
            lock (_stateLock) { _jumpPartner = null; }
            return;
        }

        // Phase check: same semantics as the pending-target block.
        bool nextCycleIsAPhase = IsAPhase(batch.CycleStart + TimeSpan.FromSeconds(15));
        if (nextCycleIsAPhase != jumpIsAPhase)
            return; // wrong phase — wait for next cycle

        // Correct phase — consume the jump-in and execute.
        lock (_stateLock) { _jumpPartner = null; }

        _logger.LogInformation(
            "QsoAnswererService: jump-in to {Point} with partner {Partner} at {FreqHz} Hz.",
            jumpPoint, jumpPartner, (int)Math.Round(jumpFreqHz));

        await ExecuteJumpInAsync(jumpPartner, jumpFreqHz, jumpPoint, tx, stoppingToken)
            .ConfigureAwait(false);
        return;
    }
}
// ── End jump-in handler ───────────────────────────────────────────────────────
```

#### 3.3.5 — New private method `ExecuteJumpInAsync`

Add after `ExecuteTxAnswerAsync`:

```csharp
// ── ExecuteJumpInAsync — mid-exchange jump-in (D-CALLER-012) ─────────────────

/// <summary>
/// Executes a mid-exchange jump-in requested by <see cref="EngageAtAsync"/>.
/// Sets partner/frequency, transmits the correct response message for
/// <paramref name="point"/>, and advances the state machine accordingly.
/// </summary>
private async Task ExecuteJumpInAsync(
    string        partner,
    double        freqHz,
    EngagePoint   point,
    TxConfig      tx,
    CancellationToken stoppingToken)
{
    if (string.IsNullOrWhiteSpace(tx.Callsign) || string.IsNullOrWhiteSpace(tx.Grid))
    {
        _logger.LogWarning(
            "QsoAnswererService: jump-in suppressed — callsign or grid not configured.");
        return;
    }

    // Initialise per-session state (mirrors ExecuteTxAnswerAsync).
    _partner      = partner;
    _partnerGrid  = null;        // not available in mid-exchange jump-in
    _retryCount   = 0;
    _rstRcvd      = "+00";
    _qsoStartUtc  = DateTime.UtcNow;
    _lastTxFreqHz = tx.HoldTxFreq
        ? (int)Math.Round(tx.TxAudioOffsetHz ?? freqHz)
        : (int)Math.Round(freqHz);

    // Push audioOffset event if HoldTxFreq is false (matches ExecuteTxAnswerAsync behaviour).
    if (!tx.HoldTxFreq)
    {
        try
        {
            await _configStore.SaveAsync(
                _configStore.Current with
                {
                    Tx = (_configStore.Current.Tx ?? new TxConfig()) with
                    {
                        TxAudioOffsetHz = _lastTxFreqHz,
                    },
                }, stoppingToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "QsoAnswererService: jump-in failed to update TxAudioOffsetHz.");
        }
        _audioOffsetEventBus.Publish(new AudioOffsetPayload(_lastTxFreqHz));
    }

    StartWatchdog(tx);
    ApplyApConstraints(tx.Callsign, partner);

    switch (point)
    {
        case EngagePoint.SendReport:
        {
            // They sent us a plain SNR → we reply R+00 → enter WaitRr73.
            var msg = $"{partner} {tx.Callsign} R+00";
            _lastTxMessage = msg;
            SetStateAndNotify(QsoState.TxReport);
            await TransmitAsync(msg, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
            ResetWatchdog(tx);
            _skipNextRetry = true;   // A-01: our TX window immediately follows
            SetStateAndNotify(QsoState.WaitRr73);
            break;
        }

        case EngagePoint.SendRr73:
        {
            // They sent RRR or R±NN → we reply RR73 → QsoComplete (no ADIF — partial QSO).
            var msg = $"{partner} {tx.Callsign} RR73";
            _lastTxMessage = msg;
            SetStateAndNotify(QsoState.Tx73);    // nearest proxy; UI shows as final TX
            await TransmitAsync(msg, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
            await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
            break;
        }

        case EngagePoint.Send73:
        {
            // They sent RR73 → we reply 73 → QsoComplete (ADIF written via ExecuteTx73Async).
            await ExecuteTx73Async(tx, stoppingToken).ConfigureAwait(false);
            break;
        }
    }
}
```

**Important notes on `ExecuteJumpInAsync`:**

- `SendReport` enters `WaitRr73` and the normal `HandleWaitRr73Async` loop then handles
  the partner's RR73 → TX 73 → ADIF write. Full QSO record is captured.
- `SendRr73` bypasses `ExecuteTx73Async` (no ADIF write) because the QSO was interrupted
  mid-exchange; the operator chose to confirm an exchange they didn't start cleanly. Acceptable loss.
- `Send73` calls `ExecuteTx73Async` which writes a partial ADIF record (`RstRcvd = "+00"`,
  `PartnerGrid = null`). Also acceptable.
- The `HoldTxFreq` path (lines 12–29 of `ExecuteJumpInAsync`) mirrors the logic in
  `ExecuteTxAnswerAsync` — copy the same pattern verbatim to remain consistent. If
  `HoldTxFreq = true`, use the configured `TxAudioOffsetHz`; if false, use the decoded
  `freqHz` and update the config + push an `audioOffset` WS event.

---

### 3.4 — Stub `EngageAtAsync` in `QsoCallerService`

**File:** `src/OpenWSFZ.Daemon/QsoCallerService.cs`

Add the stub after the existing `SelectResponderAsync` implementation:

```csharp
/// <inheritdoc/>
/// <remarks>
/// Not implemented: <see cref="QsoControllerRouter"/> always delegates
/// <c>EngageAtAsync</c> to <see cref="QsoAnswererService"/> (D-CALLER-012).
/// </remarks>
public Task EngageAtAsync(
    string partnerCallsign,
    double frequencyHz,
    DateTimeOffset theirCycleStart,
    EngagePoint point,
    CancellationToken ct)
    => Task.CompletedTask;
```

---

### 3.5 — Implement `EngageAtAsync` in `QsoControllerRouter`

**File:** `src/OpenWSFZ.Daemon/QsoControllerRouter.cs`

Add after the existing `SelectResponderAsync` delegation:

```csharp
/// <inheritdoc/>
/// <remarks>
/// D-CALLER-012: mid-exchange jump-in always uses the answerer service.
/// If the active role is Caller, the router switches to Answerer here so that
/// <see cref="QsoAnswererService.HandleIdleAsync"/> fires with <c>IsActive = true</c>.
/// Phase 1 supports answerer-configured roles; for caller-configured roles the
/// switch may race with the <c>OnBecameIdle</c> revert — document as untested.
/// </remarks>
public Task EngageAtAsync(
    string partnerCallsign,
    double frequencyHz,
    DateTimeOffset theirCycleStart,
    EngagePoint point,
    CancellationToken ct)
{
    // Switch to answerer if currently active as caller.
    if (_activeRole != QsoRole.Answerer)
    {
        _logger.LogInformation(
            "QsoControllerRouter: switching to Answerer for mid-exchange jump-in (D-CALLER-012).");
        _caller.IsActive   = false;
        _answerer.IsActive = true;
        _activeRole        = QsoRole.Answerer;
    }

    return _answerer.EngageAtAsync(partnerCallsign, frequencyHz, theirCycleStart, point, ct);
}
```

---

### 3.6 — New request type and JSON registration

**File:** `src/OpenWSFZ.Web/AppJsonContext.cs`

#### 3.6.1 — Add `[JsonSerializable]` attribute

Append immediately after `[JsonSerializable(typeof(SelectResponderRequest))]`:

```csharp
[JsonSerializable(typeof(EngageDecodeRequest))]
```

#### 3.6.2 — Add request record definition

Append after the `SelectResponderRequest` record definition (wherever that is in the file):

```csharp
/// <summary>
/// Request body for <c>POST /api/v1/tx/engage-decode</c> (D-CALLER-012).
/// Wire format: <c>{"message":"PD2FZ W1ABC -07","frequencyHz":1234.0,"cycleStartUtc":"2026-06-27T10:00:15Z"}</c>
/// </summary>
internal sealed record EngageDecodeRequest(
    string Message,
    double FrequencyHz,
    string CycleStartUtc);
```

---

### 3.7 — New endpoint: `POST /api/v1/tx/engage-decode`

**File:** `src/OpenWSFZ.Web/WebApp.cs`

Add after the `POST /api/v1/tx/select-responder` block (around line 820):

```csharp
// ── POST /api/v1/tx/engage-decode (D-CALLER-012) ─────────────────────────────
//
// Atomically aborts any in-progress QSO and engages a new one based on the
// double-clicked decode row.  Dispatches by message type:
//
//   CQ ...                 → AnswerCqAsync   (same as clicking a CQ row)
//   OURS PARTNER -NN/+NN   → EngageAtAsync(SendReport)   → TxReport
//   OURS PARTNER R±NN/RRR  → EngageAtAsync(SendRr73)     → Tx73/QsoComplete
//   OURS PARTNER RR73      → EngageAtAsync(Send73)        → Tx73/QsoComplete
//   OURS PARTNER 73        → abort only (QSO already done)
//   Any other pattern      → 422 Unprocessable Entity

app.MapPost("/api/v1/tx/engage-decode", async (
    HttpRequest   request,
    IConfigStore  store,
    CancellationToken ct) =>
{
    if (qsoController is null)
        return Results.Problem("TX controller not available.", statusCode: 503);

    EngageDecodeRequest? req;
    try
    {
        req = await request.ReadFromJsonAsync(
            AppJsonContext.Default.EngageDecodeRequest, ct);
    }
    catch (JsonException)
    {
        return Results.BadRequest("Malformed JSON.");
    }

    if (req is null)
        return Results.BadRequest("Missing or empty request body.");

    if (!DateTimeOffset.TryParse(
            req.CycleStartUtc,
            null,
            System.Globalization.DateTimeStyles.RoundtripKind,
            out var cycleStart))
    {
        return Results.BadRequest("cycleStartUtc is not a valid ISO 8601 date-time.");
    }

    // ── Step 1: Abort if not Idle ─────────────────────────────────────────────
    if (qsoController.State != QsoState.Idle)
    {
        await qsoController.AbortAsync(ct).ConfigureAwait(false);

        // SafeAbortToIdleAsync runs on the background service thread; poll until
        // the state propagates.  2-second deadline is generous: in practice
        // KeyUpAsync completes in <100 ms.
        var deadline = DateTimeOffset.UtcNow.AddSeconds(2);
        while (qsoController.State != QsoState.Idle
               && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(10, ct).ConfigureAwait(false);
        }

        if (qsoController.State != QsoState.Idle)
        {
            return Results.Problem(
                "QSO did not abort in time; please retry.",
                statusCode: 503);
        }
    }

    // ── Step 2: Parse message and dispatch ────────────────────────────────────

    var txConfig     = store.Current.Tx ?? new TxConfig();
    var ourCallsign  = txConfig.Callsign ?? string.Empty;
    var ourBase      = ourCallsign.Split('/')[0];    // strip /P, /M suffixes

    var tokens = req.Message.Trim().Split(
        ' ', StringSplitOptions.RemoveEmptyEntries);

    if (tokens.Length < 2)
        return Results.UnprocessableEntity();

    // ── Case A: CQ row ────────────────────────────────────────────────────────
    if (tokens[0].Equals("CQ", StringComparison.OrdinalIgnoreCase))
    {
        // CQ PARTNER GRID  →  partner = tokens[1]
        // CQ DX PARTNER    →  partner = tokens[2]
        // CQ modifier PARTNER [GRID]  →  partner = tokens[2]
        var partnerCallsign = tokens.Length >= 4 ? tokens[2] : tokens[1];

        await qsoController.AnswerCqAsync(
            partnerCallsign, req.FrequencyHz, cycleStart, ct).ConfigureAwait(false);
    }

    // ── Case B: Directed message TO us ────────────────────────────────────────
    else if (tokens.Length >= 3
             && (tokens[0].Equals(ourCallsign, StringComparison.OrdinalIgnoreCase)
                 || tokens[0].Equals(ourBase,   StringComparison.OrdinalIgnoreCase)))
    {
        var partner = tokens[1];
        var info    = tokens[2];

        static bool IsPlainSnr(string s) =>
            s.Length == 3
            && (s[0] == '+' || s[0] == '-')
            && char.IsDigit(s[1])
            && char.IsDigit(s[2]);

        static bool IsRReport(string s) =>
            s.Length >= 4
            && s[0] == 'R'
            && IsPlainSnr(s[1..]);

        if (info.Equals("73", StringComparison.OrdinalIgnoreCase))
        {
            // QSO already complete — abort only (already done above).  Return Idle.
        }
        else if (info.Equals("RR73", StringComparison.OrdinalIgnoreCase))
        {
            await qsoController.EngageAtAsync(
                partner, req.FrequencyHz, cycleStart, EngagePoint.Send73, ct)
                .ConfigureAwait(false);
        }
        else if (info.Equals("RRR", StringComparison.OrdinalIgnoreCase) || IsRReport(info))
        {
            await qsoController.EngageAtAsync(
                partner, req.FrequencyHz, cycleStart, EngagePoint.SendRr73, ct)
                .ConfigureAwait(false);
        }
        else if (IsPlainSnr(info))
        {
            await qsoController.EngageAtAsync(
                partner, req.FrequencyHz, cycleStart, EngagePoint.SendReport, ct)
                .ConfigureAwait(false);
        }
        else
        {
            // Unrecognised payload (e.g. CQ or free-text bleed-through).
            return Results.UnprocessableEntity();
        }
    }

    // ── Case C: Message not addressed to us ───────────────────────────────────
    else
    {
        // Abort already done.  Return 422 so the JS can show a console note.
        return Results.UnprocessableEntity();
    }

    // ── Step 3: Return new state ──────────────────────────────────────────────
    var state               = qsoController.State;
    var partner_out         = qsoController.Partner;
    var role                = qsoController.Role.ToString().ToLowerInvariant();
    var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
    var autoAnswer          = store.Current.Tx?.AutoAnswer ?? false;

    return TypedResults.Ok(new TxStatusResponse(
        state.ToString(),
        partner_out,
        AutoAnswerEnabled: autoAnswer,
        Role:              role,
        CallerPartnerSelect: callerPartnerSelect));
});
```

---

### 3.8 — `web/js/api.js`: Add `postTxEngageDecode`

Add the following export after `postTxAbort`:

```javascript
/**
 * POST /api/v1/tx/engage-decode
 * Atomically aborts any in-progress QSO and engages a new one based on the
 * double-clicked decode.  The backend parses the message, determines the correct
 * response, and primes the state machine.
 *
 * Returns HTTP 422 Unprocessable Entity if the message is not actionable
 * (not addressed to us, or unknown format).  In that case the abort has still
 * been performed; the caller should refresh TX status.
 *
 * @param {string} message       Full FT8 message text (e.g. "PD2FZ W1ABC -07").
 * @param {number} frequencyHz   Audio frequency of the decode, in Hz.
 * @param {string} cycleStartUtc ISO 8601 UTC cycle-start (e.g. "2026-06-27T10:00:15Z").
 * @returns {Promise<{state:string, partner:string|null, autoAnswerEnabled:boolean, role:string}>}
 */
export async function postTxEngageDecode(message, frequencyHz, cycleStartUtc) {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/engage-decode', {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Api-Key': key } : {}),
    },
    body: JSON.stringify({ message, frequencyHz, cycleStartUtc }),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    throw new Error('Unauthorized');
  }
  const err = new Error(`engage-decode: ${res.status}`);
  /** @type {any} */ (err).status = res.status;
  if (!res.ok) throw err;
  return res.json();
}
```

---

### 3.9 — `web/js/main.js`: Import and dblclick handler

#### 3.9.1 — Update import statement (line 10–14)

Add `postTxEngageDecode` to the api.js import:

```javascript
import { getConfig, getFrequencies, postTune, postAudioOffset,
         getTxStatus, postTxEnable, postTxDisable, postTxAbort,
         postTxAnswerCq, postTxSelectResponder, postTxCallCq,
         postTxCallerPartnerSelect, getApiKey,
         getPropModes, postLogQso,
         postTxEngageDecode }                                              from './api.js';
```

#### 3.9.2 — Add `dblclick` handler to every decode row

In `handleDecodes`, locate the line `decodesBody.prepend(tr);` (currently around
line 433). Insert the following block **immediately before** that line, after all
existing event-handler attachment:

```javascript
    // ── D-CALLER-012: Double-click any decode row to abort + engage ───────────
    // The first click of a double-click fires the existing single-click handlers
    // (CQ answer or responder select) which fail gracefully with 409 if not idle.
    // The dblclick then calls engage-decode which performs the abort + re-engage
    // atomically on the server.
    let engageInFlight = false;
    tr.addEventListener('dblclick', async () => {
      if (engageInFlight) return;
      engageInFlight = true;

      try {
        const status = await postTxEngageDecode(
          r.message,
          r.freqHz,
          tr.dataset.cqCycleStartUtc);

        renderTxPanel(
          status.state             ?? 'Idle',
          status.partner           ?? null,
          status.autoAnswerEnabled ?? false,
          status.role              ?? currentTxRole);

      } catch (err) {
        const code = /** @type {any} */ (err)?.status;

        if (code === 422) {
          // Message not actionable (73, or not addressed to us) — abort already
          // happened.  Refresh state from the server so the UI reflects Idle.
          console.info('D-CALLER-012: engage-decode not actionable for:', r.message);
          try {
            const s = await getTxStatus();
            renderTxPanel(s.state, s.partner, s.autoAnswerEnabled, s.role);
          } catch { /* ignore secondary error */ }

        } else if (code === 503) {
          console.warn('D-CALLER-012: engage-decode — abort timed out (503).');

        } else {
          console.error('D-CALLER-012: engage-decode error:', err);
        }

      } finally {
        engageInFlight = false;
      }
    });
    // ── End D-CALLER-012 ─────────────────────────────────────────────────────
```

#### 3.9.3 — Add `prevState` capture and D-CALLER-008 entry sweep in `renderTxPanel`

In `renderTxPanel` (currently line 190):

**Before** `currentTxState = state;`, capture the previous state:

```javascript
function renderTxPanel(state, partner, autoAnswerEnabled, role) {
  // Capture previous state before overwriting — used below for D-CALLER-008 sweep.
  const prevState = currentTxState;

  // Persist for subsequent partial updates ...
  currentTxState           = state;
  // ... rest of function unchanged until the renderMessageRows call ...
```

**After** the `renderMessageRows(...)` call (currently the last line of `renderTxPanel`),
add the D-CALLER-008 WaitAnswer entry sweep:

```javascript
  // D-CALLER-008: Sweep stale decode-responder rows when WaitAnswer begins.
  // Rows from prior WaitAnswer sessions carry the decode-responder class but
  // have stale responseCycleStartUtc values.  Clearing them here ensures only
  // rows created in the new WaitAnswer window are teal and single-click-selectable.
  // Note: rows are NOT cleared on WaitAnswer exit so the operator can still
  // double-click them (D-CALLER-012) to abort and re-engage.
  if (prevState !== 'WaitAnswer' && state === 'WaitAnswer') {
    decodesBody.querySelectorAll('tr.decode-responder').forEach(row => {
      row.classList.remove('decode-responder');
      row.style.cursor        = '';
      row.style.pointerEvents = 'none';
    });
  }
```

---

## 4. Acceptance criteria

### AC-1 — Double-click on a CQ row when TX is active

1. While in any active TX state (TxAnswer, WaitReport, TxReport, WaitRr73), double-click
   a CQ row.
2. Network tab shows `POST /api/v1/tx/engage-decode` → 200.
3. Daemon log shows: `abort requested`, then `pending CQ target` (or jump-in log line)
   → state transitions to TxAnswer.
4. TX panel shows "Working {partner}" with the CQ station.
5. No `POST /api/v1/tx/abort` fires separately — the engage-decode endpoint handles it.

### AC-2 — Double-click `PD2FZ PARTNER -07` row (signal report addressed to us)

While in WaitReport (mid-QSO), double-click a row that contains our callsign as the
first token and a plain SNR as the third token:

1. `POST /api/v1/tx/engage-decode` → 200, `state: "Idle"` in response (jump-in primed
   but not yet fired; state is Idle until the TX window).
2. TX panel shows armed state (autoAnswerEnabled = true in autoAnswer config, or the
   response shows the new partner via the WS event).
3. At the next B-phase (or A-phase) cycle, daemon log shows `jump-in to SendReport
   with partner {PARTNER}`.
4. RF: TX fires `{PARTNER} {US} R+00`.
5. State transitions to WaitRr73. Normal WaitRr73 handling kicks in for the rest of
   the QSO.

### AC-3 — Double-click `PD2FZ PARTNER RR73` row

While in any state, double-click a row carrying `RR73` from the partner:

1. `POST /api/v1/tx/engage-decode` → 200.
2. At the next TX window, daemon log shows `jump-in to Send73`.
3. RF: TX fires `{PARTNER} {US} 73`.
4. ADIF record written (QSO complete via `ExecuteTx73Async`).
5. State returns to Idle.

### AC-4 — Double-click `PD2FZ PARTNER RRR` row

Same as AC-3 but for `RRR`. Daemon log shows `jump-in to SendRr73`.
RF: TX fires `{PARTNER} {US} RR73`.
No ADIF write (partial QSO — expected).
State returns to Idle.

### AC-5 — Double-click `PD2FZ PARTNER 73` row (QSO already done)

Double-click a row carrying `73` (QSO already ended). The abort fires but no
engagement follows. Response: `state: "Idle"`, `autoAnswerEnabled: false`. TX panel
shows Idle. Console: `engage-decode not actionable` logged.

### AC-6 — Double-click row not addressed to us

Double-click a row addressed to a different station (first token ≠ our callsign,
not a CQ). Response: 422. JS falls back to `getTxStatus()` to refresh the panel.
Abort has fired; system is Idle.

### AC-7 — Single-click decode-responder row in WaitAnswer still works

In WaitAnswer (None mode), single-click a teal row. Confirm: one
`POST /api/v1/tx/select-responder` fires and the service advances to TxReport.
D-CALLER-012 does not break the existing single-click path.

### AC-8 — D-CALLER-008: stale rows cleared on WaitAnswer entry

Complete one full CQ QSO (TxReport → WaitRr73 → TxRr73/Tx73 → Idle → new CQ →
new WaitAnswer). In DevTools Elements, confirm all decode-responder rows from the
prior WaitAnswer are deactivated (class removed, `pointer-events: none`) when the
new WaitAnswer begins.

### AC-9 — Build and tests

```
dotnet build OpenWSFZ.slnx -c Release   # 0 errors, 0 warnings
dotnet test                              # 0 failures
```

No C# tests are expected to break (pure additions). New unit tests for
`QsoAnswererService.EngageAtAsync` are **optional** in this PR and may be tracked
as a follow-up.

---

## 5. Known limitations (Phase 1)

- **Caller-configured role**: if the daemon is configured with `TxRole.Caller`, the
  `OnBecameIdle` revert callback races with the `EngageAtAsync` role switch in the
  router (3.5 above). The jump-in may silently fail to fire. Workaround: double-click
  again. Phase 2 should address this with proper synchronisation.

- **ADIF quality for `SendReport` and `SendRr73` jump-ins**: `PartnerGrid` is `null`
  (not available in mid-exchange decodes). `RstSent` is always `"R+00"` regardless of
  actual propagation. Acceptable for Phase 1.

- **`dblclick` → `click` event ordering**: a browser double-click always fires two
  `click` events before `dblclick`. The first click on a CQ row or decode-responder
  row fires the single-click handler; if the system is Idle it may briefly enter
  TxAnswer before the dblclick aborts it. This is a cosmetic artifact only — the net
  result is correct.

---

## 6. References

- `src/OpenWSFZ.Abstractions/IQsoController.cs` — add `EngageAtAsync`
- `src/OpenWSFZ.Abstractions/EngagePoint.cs` — new file
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — jump-in fields, `EngageAtAsync`,
  `ExecuteJumpInAsync`, `SafeAbortToIdleAsync` clear, `HandleIdleAsync` dispatch
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — stub `EngageAtAsync`
- `src/OpenWSFZ.Daemon/QsoControllerRouter.cs` — router `EngageAtAsync`
- `src/OpenWSFZ.Web/AppJsonContext.cs` — `EngageDecodeRequest` type + attribute
- `src/OpenWSFZ.Web/WebApp.cs` — new endpoint (after select-responder block, ~line 820)
- `web/js/api.js` — `postTxEngageDecode`
- `web/js/main.js` — import, dblclick handler, `prevState`, D-CALLER-008 sweep
- D-CALLER-010 handoff (`dev-tasks/2026-06-27-d-caller-010-dblclick-abort.md`) — superseded
- D-CALLER-011 record (`dev-tasks/2026-06-27-d-caller-011-abort-recq-deferred.md`) — resolved
- `dev-tasks/2026-06-26-d-caller-008-entry-sweep.md` — AC-8 here implements this
