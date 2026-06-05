# p19 QA Findings

Defects and observations identified during the p19 review cycle.
Items marked **Deferred** are filed for a future change and do not block this PR.

---

## F-001 — `ws.js`: `connect()` provides no destroy handle (Deferred)

**Severity:** Minor / latent  
**Status:** Deferred — does not affect any current behaviour  
**File:** `web/js/ws.js`

### Observation

`connect()` declares a `destroyed` flag and checks it in `scheduleReconnect()` and `open()`, but nothing ever sets `destroyed = true`. The function returns `void`, so callers have no way to stop the reconnection loop or release the `visibilitychange` listener.

```js
// Current — no way out
export function connect(onEvent) {
  let destroyed = false;   // ← declared but never set externally
  ...
}
```

### Risk

In the current codebase `connect()` is called exactly once, inside a `DOMContentLoaded` listener on the main page. Browser page-unload tears down the JS context, so the loop and listener are cleaned up automatically. There is no observable leak today.

The risk is latent: if `connect()` were ever called conditionally (e.g., to reconnect to a different host, or to tear down and re-establish on settings change), a second call would start a parallel reconnection loop with its own `visibilitychange` listener, doubling the connection traffic without any way to stop the first loop.

### Recommended fix (future change)

Return a `destroy` function from `connect()` and wire it to `beforeunload` or the caller's teardown path:

```js
export function connect(onEvent) {
  let destroyed = false;
  ...
  function destroy() {
    destroyed = true;
    if (reconnectTimer !== null) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    ws?.close();
  }

  open();
  return destroy;
}
```

Callers:

```js
const disconnect = connect(onEvent);
window.addEventListener('pagehide', disconnect, { once: true });
```

---

## F-002 — WebSocket reconnect during shutdown holds up process exit (Fixed in this PR)

**Severity:** High  
**Status:** Fixed — `WebApp.cs` S2 gate (503 response during `ApplicationStopping`)  
**Verification:** Task 10.3

### Root cause

`AbortAll(appScope)` fires on `ApplicationStopping` and aborts all existing WebSocket connections. The browser's `close` event fires and `ws.js` schedules a reconnect after 1 second. Kestrel remains in its drain phase (port still bound) during that window. The browser reconnects before the port is released; the new `HandleAsync` was not alive when `AbortAll` fired and is therefore never aborted — holding up the graceful drain indefinitely.

### Fix applied

`WebApp.cs` — capture `app.Lifetime.ApplicationStopping` as `appStopping` and check `IsCancellationRequested` at the top of the `/api/v1/ws` handler. During shutdown, new upgrade requests receive `503 Service Unavailable`, which causes `ws.js`'s exponential back-off to engage rather than hammering the dying process.

---

## F-003 — `ObjectDisposedException` in `CatPollingService` on daemon exit (Merge blocker)

**Severity:** High — unhandled exception on every clean shutdown; appears in the console and may alarm operators  
**Status:** Fixed — `CatPollingService.DisposeAsync` now uses `Interlocked.Exchange` to atomically take `_cts`; a second call sees `null` and returns immediately  
**Verification:** Task 10.7  
**Files:** `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs`

### Observed error

```
Unhandled exception. System.ObjectDisposedException: The CancellationTokenSource has been disposed.
Object name: 'System.Threading.CancellationTokenSource'.
   at OpenWSFZ.Daemon.Cat.CatPollingService.StopAsync(CancellationToken) line 81
   at OpenWSFZ.Daemon.Cat.CatPollingService.DisposeAsync() line 99
   at Microsoft.Extensions.DependencyInjection.ServiceLookup.ServiceProviderEngineScope.<DisposeAsync>...
   at Microsoft.Extensions.Hosting.Internal.Host.DisposeAsync()
   at Microsoft.Extensions.Hosting.HostingAbstractionsHostExtensions.RunAsync(IHost host, ...)
```

### Root cause

`Program.cs` registers `CatPollingService` in the DI container through two separate service descriptors that both result in the DI root scope tracking the same instance for disposal:

```csharp
// Line 251 — creates and owns the CatPollingService singleton
services.AddSingleton<CatPollingService>();

// Line 253 — factory resolves the same instance; root scope captures it again
services.AddHostedService(sp => sp.GetRequiredService<CatPollingService>());
```

`AddHostedService` with a factory delegate calls `ServiceDescriptor.Singleton<IHostedService, CatPollingService>(factory)`. When the host resolves the `IHostedService` registration, the factory is invoked, returns the existing singleton, and the `ServiceProviderEngineScope.CaptureDisposable` path adds that instance to the scope's dispose list a second time — even though it is the same CLR object already tracked via line 251.

At shutdown, `DisposeAsync()` is therefore called twice on the same `CatPollingService` object:

1. **First call** — `StopAsync` cancels `_cts`, awaits the polling task, returns. `_cts?.Dispose()` at line 100 runs — `_cts` is now disposed.
2. **Second call** — `StopAsync` is entered again. Line 79 (`if (_cts is null) return`) is **not** triggered because `_cts` is non-null (the reference was not cleared). Line 81 calls `_cts.CancelAsync()` on a disposed `CancellationTokenSource` → `ObjectDisposedException`.

### Required fix

Two changes are needed — both are small:

**1. Make `DisposeAsync` idempotent (primary fix)**

Use `Interlocked.Exchange` to atomically nullify `_cts` on first disposal, so a second call sees `null` and exits cleanly:

```csharp
// CatPollingService.cs — replace DisposeAsync
public async ValueTask DisposeAsync()
{
    var cts = Interlocked.Exchange(ref _cts, null);
    if (cts is null) return;   // never started, or already disposed

    await StopAsync(CancellationToken.None).ConfigureAwait(false);
    cts.Dispose();
}
```

`_cts` must also be changed from `CancellationTokenSource?` to `volatile CancellationTokenSource?` (or the field left as-is with the understanding that `Interlocked.Exchange` provides the necessary memory barrier).

Note: `StopAsync` reads `_cts` directly; update it to use the local variable, or add a corresponding null guard consistent with the new pattern.

**2. Guard `StopAsync` against operating on a disposed `_cts`**

`StopAsync` is called both by the host (`IHostedService` contract) and by `DisposeAsync`. The existing null guard on line 79 is correct in intent but is currently bypassed by the double-dispose scenario. With the `Interlocked.Exchange` fix above, the guard in `DisposeAsync` handles the double-dispose case before `StopAsync` is reached. No separate change to `StopAsync` is strictly required, but for robustness consider wrapping `_cts.CancelAsync()` in a try/catch for `ObjectDisposedException`.

**Alternative (additional, lower priority):** review whether the DI registration pattern can be simplified to avoid the double-tracking entirely — for example, by registering a pre-constructed instance via `services.AddSingleton<IHostedService>(existingInstance)` rather than a factory, which would avoid the second `CaptureDisposable` call. This is an architectural clean-up and not a prerequisite for the fix above.

---

## F-004 — Frequency dropdown shows only the active frequency (Merge blocker)

**Severity:** High — core feature of FR-044 is non-functional; the dropdown's purpose is to allow the operator to select a different frequency, which requires all available frequencies to be present  
**Status:** Fixed — `renderDialFreqSelect` guard now checks `options.length === cachedFt8Frequencies.length`; `getFrequencies().then()` triggers a rebuild if the select is already visible when the cache resolves  
**Verification:** Task 10.8  
**File:** `web/js/main.js`

### Observed behaviour

When CAT is connected, `#dial-freq` is replaced with a `<select>`. The dropdown contains only a single option — the currently active frequency — rather than all fifteen FT8 entries from `frequencies.json`.

### Root cause

There is a start-up race between `getFrequencies()` (an HTTP fetch) and the WebSocket `status` or `cat_status` event that drives `renderDialFreqSelect()`.

```js
// DOMContentLoaded — both start concurrently
getFrequencies().then(entries => {          // (A) async HTTP fetch
    cachedFt8Frequencies = entries.filter(…);
}).catch(…);

connect((event) => {                        // (B) WebSocket — fires almost immediately
    if (event.type === 'status') {
        updateDialFreq(catStatus, freqMHz); // → renderDialFreqSelect()
    }
});
```

Path (B) wins in practice: the WebSocket connection is established in the same tick as `DOMContentLoaded`, whereas the HTTP fetch requires a full request round-trip. `renderDialFreqSelect()` is therefore called while `cachedFt8Frequencies` is still `[]`.

Inside `renderDialFreqSelect()`, the empty-cache branch runs:

```js
if (cachedFt8Frequencies.length === 0) {
    // fallback — single option showing the current frequency only
    const opt = document.createElement('option');
    opt.value       = String(hz);
    opt.textContent = hz.toFixed(3) + ' MHz';
    select.appendChild(opt);
}
```

When `getFrequencies()` eventually resolves and `cat_status` events subsequently call `renderDialFreqSelect()` again, the early-return guard prevents re-population:

```js
// If it's already a select, just update the selected option.
if (old.tagName === 'SELECT') {
    updateSelectValue(old, hz);
    return;                  // ← options are never rebuilt
}
```

The dropdown therefore remains permanently stuck at one option for the lifetime of the page.

### Required fix

Two targeted changes in `main.js`:

**1. After `getFrequencies()` resolves, rebuild the dropdown if it is already visible**

```js
getFrequencies().then(entries => {
    if (!Array.isArray(entries)) return;
    cachedFt8Frequencies = entries.filter(e => e.protocol === activeProtocol);

    // If the dropdown was already rendered before the cache was ready,
    // rebuild it now so all frequency options are present.
    const existing = document.getElementById('dial-freq');
    if (existing?.tagName === 'SELECT') {
        // Force a full rebuild by replacing the element.
        existing.replaceWith(existing); // ← not quite right; use the approach below
    }
}).catch(…);
```

The cleanest approach is to factor the "force rebuild" out of the existing-select early-return. One way: clear and repopulate options in `renderDialFreqSelect` when `cachedFt8Frequencies` has grown since the select was built. A simpler approach is to store the option count on the element as a data attribute and compare on re-entry:

```js
function renderDialFreqSelect(freqMHz) {
    const hz  = typeof freqMHz === 'number' ? freqMHz : 0;
    const old = document.getElementById('dial-freq');
    if (!old) return;

    // Re-use existing select only if options are already fully populated.
    if (old.tagName === 'SELECT' && old.options.length === cachedFt8Frequencies.length && cachedFt8Frequencies.length > 0) {
        updateSelectValue(/** @type {HTMLSelectElement} */ (old), hz);
        return;
    }

    // … remainder of function (build fresh select) …
}
```

Then in the `getFrequencies()` callback:

```js
getFrequencies().then(entries => {
    if (!Array.isArray(entries)) return;
    cachedFt8Frequencies = entries.filter(e => e.protocol === activeProtocol);

    // If the dropdown is already showing, trigger a rebuild now that the cache is warm.
    const existing = document.getElementById('dial-freq');
    if (existing?.tagName === 'SELECT') {
        const currentVal = parseFloat(/** @type {HTMLSelectElement} */ (existing).value);
        renderDialFreqSelect(isFinite(currentVal) ? currentVal : 0);
    }
}).catch(…);
```

This ensures the dropdown is fully populated regardless of which side of the race resolves first.

---

## F-006 — Tune command does not cause rig to change frequency; no error reported on failure (Merge blocker)

**Severity:** High — core feature FR-045 (CAT remote tuning) is non-functional; the radio ignores the tune command and the application provides no feedback  
**Status:** Open — three distinct code defects identified; all require fixing before merge  
**Files:** `src/OpenWSFZ.Rig/RigctldConnection.cs`, `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs`

### Observed behaviour

When the operator selects a frequency from the `#dial-freq` dropdown while CAT is `Connected`, the GUI updates to show the new frequency but the rig remains on its current frequency. No errors appear in the operator log or the browser console.

---

### Root cause A — `RigctldConnection`: `\set_freq` acknowledgement (`RPRT 0`) is never consumed

**File:** `src/OpenWSFZ.Rig/RigctldConnection.cs`, `SetDialFrequencyMhzAsync`

The `rigctld` protocol requires every command to be acknowledged. After sending `\set_freq <hz>\n`, `rigctld` writes back `RPRT 0\n` (success) or `RPRT -N\n` (error). The current implementation discards the response:

```csharp
public async Task SetDialFrequencyMhzAsync(double frequencyMHz, CancellationToken ct)
{
    var hz      = (long)Math.Round(frequencyMHz * 1_000_000.0);
    var command = $@"\set_freq {hz}" + "\n";
    await _tcp.SendAsync(command, ct).ConfigureAwait(false);
    // ← RPRT 0\n is now sitting unread in the TCP receive buffer
}
```

The TCP stream is ordered. The unread `RPRT 0\n` line is then read by the *next* call to `GetDialFrequencyMhzAsync`, which attempts to parse it as a frequency:

```csharp
var line = (await _tcp.ReceiveLineAsync(ct)).Trim();   // ← reads "RPRT 0"
if (line.StartsWith("RPRT", ...))
    throw new InvalidOperationException(...);           // ← fires
```

This causes the next poll to throw `InvalidOperationException`, which the polling loop logs at `Warning` and treats as a connection error. CAT enters the `Error` state, `_activeConnection` is nulled, and the connection is re-established on the next retry cycle.

The rig may well have tuned correctly — `rigctld` likely executed `\set_freq` and returned `RPRT 0` — but the operator sees the error badge flash and the effective frequency revert, with no indication that the tune command itself succeeded.

**Required fix:**

Read and validate the acknowledgement line inside `SetDialFrequencyMhzAsync`:

```csharp
public async Task SetDialFrequencyMhzAsync(double frequencyMHz, CancellationToken ct)
{
    var hz      = (long)Math.Round(frequencyMHz * 1_000_000.0);
    var command = $@"\set_freq {hz}" + "\n";
    await _tcp.SendAsync(command, ct).ConfigureAwait(false);

    // rigctld acknowledges every command. Consume the response line to keep
    // the receive buffer clean. RPRT 0 = success; any other RPRT = error.
    var ack = (await _tcp.ReceiveLineAsync(ct).ConfigureAwait(false)).Trim();
    if (!ack.Equals("RPRT 0", StringComparison.OrdinalIgnoreCase))
        throw new InvalidOperationException(
            $"rigctld returned error for \\set_freq {hz}: '{ack}'");
}
```

---

### Root cause B — No mutual exclusion between the poll loop and `SetDialFrequencyAsync`

**File:** `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs`

`CatPollingService.RunAsync` runs on the thread pool and calls `GetDialFrequencyMhzAsync` on `_activeConnection` in a loop. `SetDialFrequencyAsync` is called from ASP.NET Core's HTTP request pipeline on a separate thread. Both access `_activeConnection` concurrently with no lock.

**For `SerialCatConnection` (serial port):**

`GetDialFrequencyMhzAsync` executes a three-step sequence:

```
DiscardInBuffer() → Write("FA;") → ReadTo(";")
```

If `SetDialFrequencyAsync` calls `Write("FA<hz>;")` while the poll loop is between `Write("FA;")` and `ReadTo(";")`, the TX buffer delivers both writes in rapid succession. Most Kenwood/Yaesu radios parse CAT commands from a sequential byte stream; receiving `FA;FA<hz>;` in one burst can confuse the radio's command parser, causing it to silently ignore the set command.

Conversely, if `DiscardInBuffer()` executes immediately after `Write("FA<hz>;")` (a real scheduling possibility), it discards any transient data in the RX buffer, including potentially a `?;` error acknowledgement from the radio, leaving the failure entirely invisible.

**For `RigctldConnection` (TCP):**

The same issue arises on the TCP path. `SendAsync("\get_freq\n")` and `SendAsync("\set_freq <hz>\n")` can be issued concurrently, and the responses can arrive interleaved. Without a lock, the pairing of `SendAsync` to `ReceiveLineAsync` is not guaranteed.

**Required fix:**

Add a `SemaphoreSlim(1, 1)` to `CatPollingService` and hold it across the entire query-or-set I/O operation:

```csharp
private readonly SemaphoreSlim _connectionLock = new(1, 1);

// In RunAsync — wrap the poll I/O:
await _connectionLock.WaitAsync(ct).ConfigureAwait(false);
try
{
    var freq = await connection.GetDialFrequencyMhzAsync(ct).ConfigureAwait(false);
    ...
}
finally { _connectionLock.Release(); }

// In SetDialFrequencyAsync:
await _connectionLock.WaitAsync(cancellationToken).ConfigureAwait(false);
try
{
    await conn.SetDialFrequencyMhzAsync(frequencyMHz, cancellationToken).ConfigureAwait(false);
}
finally { _connectionLock.Release(); }
```

The lock scope must cover the full read cycle (write command + read response) so that a concurrent `SetDialFrequencyAsync` cannot inject bytes between the poll's `Write("FA;")` and its `ReadTo(";")`.

---

### Root cause C — Silent failure: no corrective WebSocket event when the rig ignores the tune command

**File:** `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs`

The `POST /api/v1/tune` response returns `TuneResponse(freq)` — the **requested** frequency — before confirming that the rig actually tuned:

```csharp
await catTuner.SetDialFrequencyAsync(freq, ct);   // fire-and-forget at the transport level
...
return TypedResults.Ok(new TuneResponse(freq));    // ← always the requested freq, not confirmed
```

The browser immediately calls `renderDialFreqSelect(result.effectiveFrequencyMHz)` and displays the requested frequency. The optimistic display is intentional and acceptable *provided* the polling loop corrects it if the rig did not tune.

However, the correction mechanism is broken. `EmitIfChanged` compares the newly-polled frequency against `lastEmittedFreq` (a local variable in `RunAsync`). If the rig does not tune, the next poll returns the same frequency as the last emitted value, so `HasFreqChanged` returns `false` and no `cat_status` event is published:

```csharp
// lastEmittedFreq = 14.074 (last value pushed to browser)
// Rig did NOT tune; poll returns 14.074
var freqChanged = HasFreqChanged(lastFreq: 14.074, newFreq: 14.074);   // false
// → no event published → browser permanently shows 7.074 (the requested freq)
```

The GUI is left permanently displaying the wrong frequency. The operator has no indication that the tune failed, short of looking at the physical radio.

**Required fix:**

Make the poll loop aware that a tune command has been issued. The cleanest approach is to promote `lastEmittedFreq` from a `RunAsync`-local variable to a `CatPollingService` field, and have `SetDialFrequencyAsync` update it to the optimistic (requested) frequency *after* publishing the event to connected clients:

```csharp
// New field:
private volatile double? _lastBroadcastFreq;

// SetDialFrequencyAsync — publish the optimistic value immediately:
await conn.SetDialFrequencyMhzAsync(frequencyMHz, cancellationToken).ConfigureAwait(false);
_catState.Update(frequencyMHz, _catState.Status);
_catEventBus.Publish(_catState.Status, frequencyMHz);
_lastBroadcastFreq = frequencyMHz;   // poll loop now uses this as the comparison baseline

// EmitIfChanged — compare against the shared field instead of the local:
private void EmitIfChanged(double? newFreq, CatConnectionStatus newStatus)
{
    var freqChanged   = HasFreqChanged(_lastBroadcastFreq, newFreq);
    var statusChanged = _lastBroadcastStatus != newStatus;
    if (!freqChanged && !statusChanged) return;
    _lastBroadcastFreq   = newFreq;
    _lastBroadcastStatus = newStatus;
    _catEventBus.Publish(newStatus, newFreq);
}
```

With this fix:
- **Rig tunes successfully:** next poll returns the new frequency. `HasFreqChanged(optimistic, confirmed)` = false (same value). No redundant event. ✓
- **Rig ignores the command:** next poll returns the old frequency. `HasFreqChanged(optimistic=7.074, confirmed=14.074)` = true. Correction event published. Browser display reverts to actual rig frequency. ✓

The `ref double?` parameter signature of the current `EmitIfChanged` will need to change accordingly; the above sketch outlines the intent rather than the verbatim implementation.

---

### Root cause D (Documentation) — Stale class-level summary in both rig connection classes

**Files:** `src/OpenWSFZ.Rig/SerialCatConnection.cs` (line 22), `src/OpenWSFZ.Rig/RigctldConnection.cs` (line 27)

Both class-level `<summary>` blocks still contain the pre-p19 statement:

> *"Only the read-only `FA;` command is ever sent — no frequency-set, mode-set, or PTT commands are issued by this class."*

This was correct before FR-045 was implemented. It is now factually wrong and will mislead any developer reading the class for the first time.

**Required fix:** Update both summaries to accurately describe the current command repertoire.

---

### Diagnostic steps (to be run before fixing)

1. Enable `Debug` log level on the daemon.
2. Add a `_logger.LogDebug("CAT SET: {Command}", command)` line inside both `SetDialFrequencyMhzAsync` implementations, immediately before the write call. This confirms whether the command is being issued at all and what it looks like on the wire.
3. For RigCtld: log the acknowledgement line read back.
4. For SerialCat: confirm the radio model responds to `FA<hz>;` (SET) in addition to `FA;` (query) — some inexpensive CAT interfaces only implement the read side.

---

## F-005 — Frequency selector dropdown is too wide in the status bar (Merge blocker)

**Severity:** Medium — layout defect; the status bar is distorted, degrading usability for all users regardless of CAT state  
**Status:** Fixed — `select#dial-freq` rule now sets `width: auto` to override the global `select { width: 100% }` reset  
**Verification:** Task 10.8 (visual, same smoke run as F-004)  
**File:** `web/css/app.css`

### Observed behaviour

When `#dial-freq` becomes a `<select>`, it expands to fill the full width of the status bar flex container, pushing other status-bar elements out of their expected positions.

### Root cause

The global reset rule at line 68–77 of `app.css` applies `width: 100%` to every `select` element on the page:

```css
input, select {
    …
    width: 100%;   /* ← applies to #dial-freq select */
}
```

The `select#dial-freq` block (lines 554–562) does not override this. The status bar uses a flex layout; `width: 100%` inside a flex item causes the item to claim all remaining space.

### Required fix

Add `width: auto` to the `select#dial-freq` rule so the element sizes itself to its content (the longest option text) rather than filling its container:

```css
/* ── Dial frequency select (FR-044) ─────────────────────────────────────── */
#dial-freq {
  display: inline-block;
}
select#dial-freq {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  padding: 0.15rem 0.375rem;
  border-radius: 4px;
  font-size: inherit;
  cursor: pointer;
  width: auto;   /* ← override global select { width: 100% } */
}
```

`width: auto` on a `<select>` causes the browser to size the element to accommodate the longest `<option>` text, which is the desired behaviour.

---

## F-007 — `FrequencyStore` does not sort entries on save (Fixed in this PR)

**Severity:** Low — cosmetic ordering defect; new rows added via the Settings tab appeared at the bottom regardless of frequency value  
**Status:** Fixed — `SaveAsync` now sorts by `FrequencyMHz` ascending before persisting; `LoadAsync` applies the same sort in-memory so pre-existing unsorted files are presented correctly  
**Files:** `src/OpenWSFZ.Daemon/FrequencyStore.cs`

### Observed behaviour

Rows added via the Frequencies tab were appended at the end of the table in insertion order rather than being presented in ascending frequency order. After a page reload (which re-fetches from disk), the newly added entries appeared out of order relative to the default entries.

### Root cause

`SaveAsync` persisted the entry list in the order supplied by the caller. No sort was applied either at save or at load time.

### Fix applied

`SaveAsync` calls `entries.OrderBy(e => e.FrequencyMHz)` before constructing the DTO and writing to disk. `LoadAsync` applies the same `.OrderBy` after deserialising so that even pre-existing files written before the sort invariant was introduced are presented in the correct order in memory (without overwriting the file).

---

## F-008 — `SerialCatConnection.SetDialFrequencyMhzAsync` hard-coded 11 Hz digits; Yaesu FT-991A requires 9 (Fixed in this PR)

**Severity:** High — FR-045 (CAT frequency set) was silently non-functional for the FT-991A; every tune command was rejected by the rig with no error visible to the operator  
**Status:** Fixed — digit count is derived dynamically from the length of the frequency string returned by the preceding `FA;` GET query  
**Files:** `src/OpenWSFZ.Rig/SerialCatConnection.cs`

### Observed behaviour

Selecting a frequency from the `#dial-freq` dropdown while connected via serial CAT to a Yaesu FT-991A had no effect. The rig remained on its original frequency. No error was logged.

### Root cause

The original task spec (task 4.2) stated: *"zero-pad to 11 digits, write `FA<11-digit-Hz>;`"*. The Kenwood CAT standard uses 11 Hz digits for the `FA` command. However, the Yaesu FT-991A's implementation of the `FA` command uses **9 Hz digits** — e.g., `FA007074000;` (9 digits) rather than `FA00007074000;` (11 digits).

When the daemon sent `FA00007074000;`, the FT-991A's CAT parser did not recognise the command and silently discarded it. Because `SetDialFrequencyMhzAsync` performed no read-back, the failure was invisible.

### Fix applied

Rather than hard-coding the digit count, `SetDialFrequencyMhzAsync` first issues the `FA;` query (GET) and measures the length of the numeric portion of the response. The SET command then zero-pads to the same length. This makes the implementation adaptive to any rig that uses the Kenwood-style `FA` command with a non-standard digit count, without requiring per-model configuration.

### Regression test added

`SerialCatConnectionTests` — `FR-045: SetDialFrequencyMhzAsync uses digit count derived from GET response` verifies that when the mock serial port returns a 9-digit `FA` response, the SET command sent to the port is also 9 digits.
