# Developer Handoff — TX UX Improvements

**Date:** 2026-06-24  
**QA reference:** 2026-06-24 live-run analysis + log review (`openswfz-20260624T174827Z.log`)  
**Branch:** `feat/tx-ux-improvements`  
**Related defects / features:** D-TX-002, FR-UX-001 (deferred), FR-UX-002

---

## 1. Context

A supervised live-run session on 2026-06-24 (log: `logs/openswfz-20260624T174827Z.log`) surfaced
the following issues:

| ID | Type | Description |
|---|---|---|
| **D-TX-002** | Bug | Absurdly large config values crash the daemon (`WatchdogMinutes=480000` → `ArgumentOutOfRangeException` in `CancellationTokenSource.CancelAfter`; `RetryCount=50000000` mapped to 1 by `Math.Max(1,…)`, breaking the intended `0 = unlimited` semantic). |
| **UI-001** | Cleanup | The "Enable auto-answer" checkbox in Settings → Radio is obsolete. The supervised single-QSO model arms auto-answer on CQ click and disarms on every return to Idle; no persistent toggle is meaningful. |
| **FR-UX-002** | Feature | TX abort reasons are logged to the server file but never surfaced in the UI. When operating remotely, the operator cannot tell whether a session ended because of a watchdog timeout, partner misbehaviour, or retry exhaustion. A scrolling TX history list below the TX panel is required. |
| **FR-UX-001** | Feature | Clicking a CQ while already in a QSO currently returns HTTP 409 and is silently ignored. The operator expects the current QSO to be aborted and the new CQ answered. **This item is DEFERRED** — it requires a more invasive state-machine change and a separate branch; see Section 6. |

D-TX-003 (watchdog reset to 1 min) was closed as unconfirmed: the log shows the watchdog
consistently at 5 minutes throughout the session.

---

## 2. Branch name

```
feat/tx-ux-improvements
```

Branch from current `main` HEAD (`aee8263`). **Never commit directly to `main`.**

---

## 3. Actions

Work through the tasks in order; they share several files.

### Task A — D-TX-002: Config value bounds + unlimited retry

**A-1. `web/settings.html`**

1. Add `max="60"` to the watchdog input (line 74). Change `min="1"` to `min="1"`:
   ```html
   <input type="number" id="general-watchdog-minutes" min="1" max="60" placeholder="4" />
   ```
2. Add `min="0" max="200"` to the retry-count input (line 83); change `min="1"` to `min="0"` to
   express that 0 is the unlimited sentinel:
   ```html
   <input type="number" id="general-retry-count" min="0" max="200" placeholder="3" />
   ```
3. Update the watchdog hint text (line 75–78) to say:  
   `Maximum 60 minutes. Resets on each successful state transition.`
4. Update the retry-count hint text (line 84–87) to say:  
   `0 = unlimited (watchdog is the backstop). Maximum 200.`

**A-2. `web/js/settings.js`**

In the save handler (around line 737), replace the current falsy-fallback lines:
```js
watchdogMinutes: parseInt(txWatchdogMinutes.value, 10) || 4,
retryCount:      parseInt(txRetryCount.value, 10)      || 3,
```
with explicit-bounds versions that allow `retryCount = 0` (unlimited):
```js
watchdogMinutes: Math.min(60,  Math.max(1,   parseInt(txWatchdogMinutes.value, 10) || 4)),
retryCount:      Math.min(200, Math.max(0,   parseInt(txRetryCount.value,      10) || 3)),
```

**A-3. `src/OpenWSFZ.Web/WebApp.cs` — POST `/api/v1/config` validation**

In the server-side validation block (currently lines 311–334), add upper-bound clamps **after**
the existing lower-bound clamps:

```csharp
// Existing:
if (body.Tx is { } tx)
{
    if (tx.WatchdogMinutes < 1) tx = tx with { WatchdogMinutes = 1 };
    if (tx.RetryCount     < 1) tx = tx with { RetryCount     = 1 };
    // NEW — upper bounds:
    if (tx.WatchdogMinutes > 60)  tx = tx with { WatchdogMinutes = 60  };
    if (tx.RetryCount      > 200) tx = tx with { RetryCount      = 200 };
    body = body with { Tx = tx };
}
```

Also update the lower-bound RetryCount clamp: change `< 1` to `< 0` so that `RetryCount = 0`
(unlimited) passes validation:
```csharp
if (tx.RetryCount < 0) tx = tx with { RetryCount = 0 };
```

**A-4. `src/OpenWSFZ.Config/JsonConfigStore.cs` — `Load()` method**

In the clamping block (lines 126–145), add upper-bound clamps and update the lower-bound comment.
Change the existing block to:
```csharp
if (config.Tx is { } tx)
{
    bool clamped = false;
    if (tx.RetryCount < 0)
    {
        Console.Error.WriteLine(
            $"[OpenWSFZ] WARNING: tx.retryCount = {tx.RetryCount} is invalid (minimum 0); clamped to 0.");
        tx      = tx with { RetryCount = 0 };
        clamped = true;
    }
    if (tx.RetryCount > 200)
    {
        Console.Error.WriteLine(
            $"[OpenWSFZ] WARNING: tx.retryCount = {tx.RetryCount} exceeds maximum (200); clamped to 200.");
        tx      = tx with { RetryCount = 200 };
        clamped = true;
    }
    if (tx.WatchdogMinutes < 1)
    {
        Console.Error.WriteLine(
            $"[OpenWSFZ] WARNING: tx.watchdogMinutes = {tx.WatchdogMinutes} is below minimum (1); clamped to 1.");
        tx      = tx with { WatchdogMinutes = 1 };
        clamped = true;
    }
    if (tx.WatchdogMinutes > 60)
    {
        Console.Error.WriteLine(
            $"[OpenWSFZ] WARNING: tx.watchdogMinutes = {tx.WatchdogMinutes} exceeds maximum (60); clamped to 60.");
        tx      = tx with { WatchdogMinutes = 60 };
        clamped = true;
    }
    if (clamped)
        config = config with { Tx = tx };
}
```

**A-5. `src/OpenWSFZ.Abstractions/TxConfig.cs`**

Update the XML doc comments on `RetryCount` and `WatchdogMinutes` to reflect the new constraints:
- `RetryCount`: `"0 = unlimited (watchdog is the backstop). Clamped to [0, 200] at load time."`
- `WatchdogMinutes`: `"Clamped to [1, 60] at load time."`

**A-6. `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `StartWatchdog` and `ResetWatchdog`**

In both `StartWatchdog` (line 882) and `ResetWatchdog` (line 896), add an upper clamp and
promote the log from `LogDebug` to `LogInformation`:

```csharp
// OLD (both methods):
var minutes = Math.Max(1, tx.WatchdogMinutes);
...
_logger.LogDebug("QsoAnswererService: watchdog armed for {Minutes} minutes.", minutes);

// NEW (StartWatchdog):
var minutes = Math.Clamp(tx.WatchdogMinutes, 1, 60);
...
_logger.LogInformation("QsoAnswererService: watchdog armed for {Minutes} minutes.", minutes);

// NEW (ResetWatchdog):
var minutes = Math.Clamp(tx.WatchdogMinutes, 1, 60);
...
_logger.LogInformation("QsoAnswererService: watchdog reset for {Minutes} minutes.", minutes);
```

Also update the defensive comments in both methods to reference the new [1, 60] range.

**A-7. `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `RetryOrAbortAsync`**

Replace the current retry logic (line 702) to implement `RetryCount = 0` as unlimited:

```csharp
// OLD:
var maxRetries = Math.Max(1, tx.RetryCount);
_retryCount++;
if (_retryCount > maxRetries)

// NEW:
_retryCount++;
var maxRetries = tx.RetryCount; // 0 = unlimited; watchdog is the backstop
if (maxRetries > 0 && _retryCount > maxRetries)
```

Update the comment above from  
`"Clamp defensively: RetryCount < 1 would cause abort on the very first no-response cycle."`  
to  
`"RetryCount = 0 means unlimited; the watchdog timer acts as the backstop."`

---

### Task B — FR-UX-002: TX abort reason history in the UI

This adds a structured reason string to every `txState Idle` WebSocket event that results from
an abnormal termination, and renders those reasons in a list below the TX panel.

**B-1. `src/OpenWSFZ.Web/AppJsonContext.cs` — extend `WsTxStateMessage`**

Add an optional `AbortReason` property (null for normal QSO completion and routine Idle state;
non-null only when the termination is an abort):

```csharp
// OLD (line 83):
internal sealed record WsTxStateMessage(string Type, string State, string? Partner, bool AutoAnswerEnabled);

// NEW:
/// <summary>
/// Envelope for <c>txState</c> WebSocket text frames (FR-047).
/// <para>
/// Wire format: <c>{"type":"txState","state":"TxAnswer","partner":"Q1TST",
/// "autoAnswerEnabled":true,"abortReason":null}</c>
/// </para>
/// <para>
/// <c>abortReason</c> is non-null only when transitioning to Idle due to an abnormal
/// termination (watchdog, operator abort, retry exhaustion, partner misbehaviour).
/// It is null on normal QSO completion and on routine Idle state pushes.
/// </para>
/// </summary>
internal sealed record WsTxStateMessage(
    string  Type,
    string  State,
    string? Partner,
    bool    AutoAnswerEnabled,
    string? AbortReason = null);
```

The `[JsonSerializable(typeof(WsTxStateMessage))]` registration at line 35 requires no change;
STJ source-gen picks up the new property automatically.

**B-2. `src/OpenWSFZ.Web/WebSocketHub.cs` — `BroadcastTxState`**

Add `string? abortReason = null` to the method signature and pass it to the record constructor:

```csharp
// OLD:
internal static void BroadcastTxState(QsoState state, string? partner, bool autoAnswerEnabled)
{
    ...
    var msg = new WsTxStateMessage(Type: "txState", State: state.ToString(),
                                   Partner: partner, AutoAnswerEnabled: autoAnswerEnabled);

// NEW:
internal static void BroadcastTxState(
    QsoState state, string? partner, bool autoAnswerEnabled, string? abortReason = null)
{
    ...
    var msg = new WsTxStateMessage(Type: "txState", State: state.ToString(),
                                   Partner: partner, AutoAnswerEnabled: autoAnswerEnabled,
                                   AbortReason: abortReason);
```

**B-3. `src/OpenWSFZ.Web/TxEventBus.cs` — `Publish`**

Add `string? abortReason = null` to the `Publish` signature and thread it through:

```csharp
// OLD:
public void Publish(QsoState state, string? partner, bool autoAnswerEnabled)
    => WebSocketHub.BroadcastTxState(state, partner, autoAnswerEnabled);

// NEW:
public void Publish(
    QsoState state, string? partner, bool autoAnswerEnabled, string? abortReason = null)
    => WebSocketHub.BroadcastTxState(state, partner, autoAnswerEnabled, abortReason);
```

**B-4. `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — abort reason plumbing**

Make four targeted changes:

**(i) Add a volatile field for operator-abort intent** (near the other `_txCts` field):
```csharp
private volatile bool _operatorAbortRequested;
```

**(ii) Set the flag in `AbortAsync` (line 157), immediately before `_txCts.Cancel()`:**
```csharp
_operatorAbortRequested = true;   // NEW — distinguishes operator abort from watchdog timeout
_txCts.Cancel();
```

**(iii) Change the signature of `SafeAbortToIdleAsync` (line 770) to accept an optional reason,**
and use `_operatorAbortRequested` as a fallback when no explicit reason is provided.
Replace the method opening:
```csharp
// OLD:
private async Task SafeAbortToIdleAsync(CancellationToken stoppingToken)
{

// NEW:
private async Task SafeAbortToIdleAsync(CancellationToken stoppingToken, string? abortReason = null)
{
    // Resolve the effective abort reason.
    // An explicit caller reason takes precedence; otherwise check the operator-abort flag.
    // Normal QSO completion callers pass null and clear the flag cleanly.
    var effectiveReason = abortReason
        ?? (_operatorAbortRequested ? "Operator abort" : (string?)null);
    _operatorAbortRequested = false;
```

Replace the final `_txEventBus.Publish` call inside `SafeAbortToIdleAsync` (line 837):
```csharp
// OLD:
_txEventBus.Publish(QsoState.Idle, null, autoAnswerEnabled: false);

// NEW:
_txEventBus.Publish(QsoState.Idle, null, autoAnswerEnabled: false, abortReason: effectiveReason);
```

**(iv) Update all `SafeAbortToIdleAsync` call sites** with explicit reason strings where the
reason is known at the call site. Callers that do not pass a reason will fall through to the
`_operatorAbortRequested` flag check (covering the two `OperationCanceledException` catch blocks):

| Line (approx.) | Caller context | New call |
|---|---|---|
| ~231 | `OperationCanceledException` while waiting (catch block in `ExecuteAsync`) | `await SafeAbortToIdleAsync(stoppingToken, _operatorAbortRequested ? "Operator abort" : "Watchdog timeout").ConfigureAwait(false);` |
| ~247 | `OperationCanceledException` during TX (catch block in `ExecuteAsync`) | `await SafeAbortToIdleAsync(stoppingToken, _operatorAbortRequested ? "Operator abort" : "Watchdog timeout").ConfigureAwait(false);` — also clear flag here before calling: `_operatorAbortRequested = false;` **before** the call is NOT needed here; the method clears it internally. |
| ~254 | `Exception` (unexpected error catch in `ExecuteAsync`) | `await SafeAbortToIdleAsync(stoppingToken, $"Internal error: {ex.GetType().Name}").ConfigureAwait(false);` |
| ~605 | Partner working another station (`HandleWaitReportAsync`) | `await SafeAbortToIdleAsync(stoppingToken, $"Partner {partner} is working another station").ConfigureAwait(false);` |
| ~694 | Normal QSO completion (`ExecuteTx73Async`) | No change — pass no reason (null = no abort log entry). |
| ~709 | Retry count exhausted (`RetryOrAbortAsync`) | `await SafeAbortToIdleAsync(stoppingToken, $"No response from {_partner} after {maxRetries} retries").ConfigureAwait(false);` |

> **Note on the two `OperationCanceledException` catch blocks:** By the time the catch block
> executes, `_operatorAbortRequested` has already been set (if it was an operator abort) or is
> still false (if it was the watchdog). Passing the ternary inline and letting the method clear
> the flag is correct, but slightly redundant with the method's own internal check. This is
> intentional — it prevents the field-read from racing with a concurrent `AbortAsync` call
> during a subsequent session. For safety, derive the local string **before** the async call:
> ```csharp
> var reason = _operatorAbortRequested ? "Operator abort" : "Watchdog timeout";
> _operatorAbortRequested = false;
> await SafeAbortToIdleAsync(stoppingToken, reason).ConfigureAwait(false);
> ```
> Apply this pattern to both catch blocks (~231, ~247). The method's own flag-clearing then
> becomes a no-op harmless double-clear.

**B-5. `web/index.html` — abort reason log section**

Add the following block **inside `<section id="tx-panel">`**, immediately after the closing
`</div>` of `tx-msg-3` (line 113) and before the closing `</section>` (line 115):

```html
        <!-- TX abort reason history (FR-UX-002) — populated by JS; hidden until first entry -->
        <div id="tx-abort-log-section" hidden>
          <p class="tx-abort-log-title">TX History</p>
          <ol id="tx-abort-log" class="tx-abort-log-list"></ol>
        </div>
```

**B-6. `web/js/main.js` — render abort log**

**(i)** After the existing `const` declarations for TX panel elements (around line 55), add:
```js
const txAbortLogSection = /** @type {HTMLElement} */ (document.getElementById('tx-abort-log-section'));
const txAbortLogEl      = /** @type {HTMLOListElement} */ (document.getElementById('tx-abort-log'));

/** @type {Array<{isoTs: string, reason: string, partner: string|null}>} */
const txAbortLog = [];
const TX_ABORT_LOG_MAX = 10;

/**
 * Appends an entry to the TX abort log (newest on top) and refreshes the DOM list.
 * Capped at TX_ABORT_LOG_MAX entries; oldest entries are dropped.
 * @param {string}      reason   - Human-readable abort reason.
 * @param {string|null} partner  - Partner callsign at time of abort, or null.
 */
function appendTxAbortLog(reason, partner) {
  const isoTs = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  txAbortLog.unshift({ isoTs, reason, partner });
  if (txAbortLog.length > TX_ABORT_LOG_MAX)
    txAbortLog.length = TX_ABORT_LOG_MAX;

  if (txAbortLogEl) {
    txAbortLogEl.innerHTML = txAbortLog
      .map(e => `<li><span class="tx-abort-ts">${e.isoTs}</span> — ${e.reason}</li>`)
      .join('');
  }
  if (txAbortLogSection) txAbortLogSection.hidden = false;
}
```

**(ii)** In the `txState` WebSocket event handler (around line 833–838), add an `abortReason`
check immediately after the `renderTxPanel` call:

```js
if (event.type === 'txState') {
  renderTxPanel(
    event.state             ?? 'Idle',
    event.partner           ?? null,
    event.autoAnswerEnabled ?? currentAutoAnswerEnabled);

  // FR-UX-002: append to abort log when the daemon reports an abort reason.
  if (event.abortReason) {
    appendTxAbortLog(event.abortReason, event.partner ?? null);
  }
  return;
}
```

**B-7. CSS (optional but recommended)**

Add minimal styling for the abort log to `web/css/app.css`. A compact monospace list is
sufficient; exact design is developer discretion. Suggested classes:

```css
/* TX abort reason history (FR-UX-002) */
.tx-abort-log-title { font-size: 0.78rem; font-weight: 600; margin: 8px 0 2px; opacity: 0.8; }
.tx-abort-log-list  { font-size: 0.75rem; font-family: monospace; margin: 0; padding-left: 1.4em; }
.tx-abort-log-list li { margin-bottom: 2px; }
.tx-abort-ts        { opacity: 0.65; }
```

---

### Task C — UI-001: Remove obsolete "Enable Auto Answer" checkbox

**C-1. `web/settings.html`**

Remove the entire `<fieldset id="tx-settings">` block (lines 187–201 inclusive).
After removal, line 203 (`<!-- ── Advanced Decoder Settings … -->`) follows directly
after the closing `</div>` of the preceding `general-retry-count` field-group.

The removed block is:
```html
        <fieldset id="tx-settings">
          <legend>FT8 TX</legend>

          <div class="field-group">
            <label class="checkbox-label">
              <input type="checkbox" id="tx-auto-answer" />
              Enable auto-answer
            </label>
            <p class="field-hint">
              When enabled, OpenWSFZ will automatically answer the first decoded CQ call
              and drive a full FT8 QSO exchange.
            </p>
          </div>

        </fieldset>
```

**C-2. `web/js/settings.js`**

Remove all four references to `txAutoAnswer`:

1. **Line 49–50** — remove the comment and constant declaration:
   ```js
   // TX auto-answer control (remains on Radio tab)
   const txAutoAnswer      = /** @type {HTMLInputElement} */ (document.getElementById('tx-auto-answer'));
   ```

2. **Line 239** (`snapshotForm`) — remove the `autoAnswer` line from the `tx:` object:
   ```js
   autoAnswer:      txAutoAnswer.checked,   // ← remove this line
   ```

3. **Line 517** (`populateForm`) — remove the assignment:
   ```js
   txAutoAnswer.checked      = tx.autoAnswer      ?? false;   // ← remove this line
   ```

4. **Line 736** (save handler) — remove the `autoAnswer` line from the `tx:` object:
   ```js
   autoAnswer:      txAutoAnswer.checked,   // ← remove this line
   ```

The `autoAnswer` key will no longer be sent in the config `PUT` payload from the settings page.
`QsoAnswererService` manages `AutoAnswer` in-process; the API does not need this field from the
settings form.

---

### Task D — Tests

Add or update tests as follows.

**D-1. New unit tests for D-TX-002 in `tests/Daemon.Tests/`** (or whichever test project covers
`QsoAnswererService`):

- `RetryOrAbortAsync_RetryCount0_NeverAborts`: confirm that after `N > 3` silent cycles, the
  service retransmits each time (watchdog ultimately fires). Use `Q1TST` as partner callsign.
- `RetryOrAbortAsync_RetryCount200_AbortsAfter200`: confirm that after 200 retries the service
  calls `SafeAbortToIdleAsync` (captured via the `TxEventBus` mock emitting `Idle`).

**D-2. New unit tests for abort reason plumbing in `tests/Daemon.Tests/`:**

- `SafeAbortToIdleAsync_WatchdogTimeout_EmitsAbortReason`: trigger a watchdog-cancel (set
  `_watchdogDurationOverride` to 1 ms); capture the `TxEventBus.Publish` call; assert
  `abortReason == "Watchdog timeout"`.
- `SafeAbortToIdleAsync_OperatorAbort_EmitsAbortReason`: call `AbortAsync()`, which sets
  `_operatorAbortRequested`; assert `abortReason == "Operator abort"` on the next Idle event.
- `SafeAbortToIdleAsync_NormalCompletion_NoAbortReason`: let a complete `Q1TST → 73` QSO run
  through; assert `abortReason == null` on the final Idle event.

**D-3. Update existing tests** that assert on the `WsTxStateMessage` wire format or on
`BroadcastTxState` / `TxEventBus.Publish` call signatures — the new optional `AbortReason`
parameter must not break existing assertions. Verify that tests asserting `state == "Idle"` do
not fail due to the new nullable property being present (it defaults to null, so it may or may
not appear in serialised JSON depending on STJ null-handling settings — verify the existing
`JsonIgnoreCondition` policy in `AppJsonContext` and set `[JsonIgnore(Condition = WhenWritingNull)]`
on `AbortReason` if the wire-format doc comment specifies omission rather than explicit null).

**D-4. Confirm `RetryCount = 0` does not regress existing retry tests.** Any test that sets
`RetryCount = 0` and previously got clamped to 1 (aborting after one retry) now gets unlimited
retries. Update such tests to use `RetryCount = 1` if they intend single-retry behaviour.

---

## 4. Acceptance criteria

The QA engineer will verify the following before approving the merge.

### D-TX-002 bounds

- [ ] Setting `WatchdogMinutes = 480000` via the settings page submits `60` to the API (clamped
  in the JS save handler; confirmed via browser DevTools → Network tab).
- [ ] Setting `RetryCount = 50000000` via the settings page submits `200` to the API.
- [ ] A `config.json` with `"watchdogMinutes": 480000` loads without crash; daemon logs
  `WARNING: … clamped to 60`.
- [ ] A `config.json` with `"retryCount": 0` loads without warning; daemon uses unlimited retries.
- [ ] `dotnet test` → 0 failures, ≥ 2 new retry-related test cases pass.
- [ ] `StartWatchdog` and `ResetWatchdog` emit `[INF]` (not `[DBG]`) with `LogLevel = Information`.

### FR-UX-002 abort log

- [ ] After a watchdog timeout, the TX panel abort log shows an entry with text containing
  "Watchdog timeout".
- [ ] After an operator abort (Abort TX button), the entry shows "Operator abort".
- [ ] After retry exhaustion, the entry shows "No response from … after … retries".
- [ ] After a normal 73 QSO completion, no new entry appears in the abort log.
- [ ] The list is newest-on-top; the second abort appends above the first.
- [ ] After 11 consecutive aborts, only 10 entries are retained (oldest dropped).
- [ ] The log section is hidden on page load and becomes visible on the first abort.

### UI-001 removal

- [ ] Settings → Radio tab no longer shows "Enable auto-answer" checkbox.
- [ ] Page loads without JS console errors (no `null.checked` TypeError on `txAutoAnswer`).
- [ ] The settings form `snapshotForm()` does not include `autoAnswer` in the `tx` object.
- [ ] Saving settings does not send `autoAnswer` in the request body (DevTools → Network).

### Regression

- [ ] `dotnet build OpenWSFZ.slnx -c Release` → 0 errors, 0 warnings.
- [ ] `dotnet test OpenWSFZ.slnx -c Release` → 0 failures (all existing tests pass).
- [ ] G3 traceability gate passes.

---

## 5. References

- **Log evidence:** `logs/openswfz-20260624T174827Z.log`
  - Line 616: `[DBG] watchdog armed for 5 minutes` — confirms log currently at Debug level.
  - Line 859: `[INF] TX session cancelled while waiting (state: "WaitRr73")` — watchdog abort,
    no UI feedback.
  - Line 945: `[INF] PD2FZ is working CQ — aborting` — partner abort, no UI feedback.
- **Root cause of D-TX-002:** `TimeSpan.FromMinutes(480000)` = 28.8 × 10⁹ ms > `int.MaxValue`
  (≈ 2.1 × 10⁹ ms) → `ArgumentOutOfRangeException` in `CancellationTokenSource.CancelAfter`.
- **`RetryCount = 0` regression risk:** Lesson #6 in MEMORY.md (STJ source-gen and init
  defaults) — `TxConfig.RetryCount` has `= 3` as its property initialiser, but the
  `[JsonConstructor]` defaults are what STJ uses. Confirm the constructor default for
  `RetryCount` remains `3` after this change; do not inadvertently set it to `0`.
- **Retry test contamination:** Any existing test that creates a `TxConfig` with omitted
  `RetryCount` relies on the constructor default (currently 3). The new 0 = unlimited semantic
  does not affect the default; only explicit `RetryCount = 0` callers are affected.
- **STJ null emission for `AbortReason`:** Check whether `AppJsonContext` uses
  `JsonSerializerOptions` with `DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull`.
  If so, `"abortReason"` will be absent from the wire frame when null (the JS `event.abortReason`
  will be `undefined`, which is falsy — the abort-log check `if (event.abortReason)` works
  correctly either way).

---

## 6. Deferred item — FR-UX-001 (CQ click while in QSO)

**Not in scope for this branch.**

Clicking a CQ while the state machine is in any non-Idle state currently returns HTTP 409, which
`main.js` silently swallows with a `console.warn`. The desired behaviour is:

1. Abort the current QSO immediately.
2. Arm auto-answer for the new CQ target.

This requires:
- Removing the `if (qsoController.State != QsoState.Idle) return Results.Conflict();` guard in
  `WebApp.cs` `POST /api/v1/tx/answer-cq`.
- Calling `await qsoController.AbortAsync()` followed by `await qsoController.AnswerCqAsync(…)`
  in the endpoint handler, with appropriate locking.
- A race guard: the abort + re-arm must be atomic from the state machine's perspective to
  prevent the loop from entering a new session between the two calls.
- Updating `main.js` to remove the 409-path `console.warn` branch.

The QA engineer will produce a separate handoff document when this is scheduled.

---

*Prepared by QA, 2026-06-24. All test callsigns use Q-prefix per NFR-021.*
