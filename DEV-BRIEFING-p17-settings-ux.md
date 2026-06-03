# Developer Briefing — p17: Settings UX & Dial Frequency Improvements

**Date:** 2026-06-03  
**Branch:** `feat/p17-settings-ux`  
**Requirements:** FR-035, FR-036, FR-037, FR-038, FR-039  
**Status:** Ready for implementation

---

## 1. Overview

This change delivers five improvements to the Settings page and the main-page
dial frequency display. They were specified together because they touch the same
files and are tightly coupled at the UI level.

| Req    | Summary                                                    |
|--------|------------------------------------------------------------|
| FR-035 | Settings page reorganised into three tabs                  |
| FR-036 | `#cycle-timer` hides via CSS `visibility` not `hidden`     |
| FR-037 | Dial frequency input locked when CAT polling is on         |
| FR-038 | New `GET /api/v1/serial/ports` + serial port `<select>`    |
| FR-039 | Last polled CAT frequency persisted across restarts        |

---

## 2. Files to Change

### Backend (`src/`)

| File | Change |
|------|--------|
| `src/OpenWSFZ.Abstractions/CatConfig.cs` | Add `LastPolledFrequencyMHz` field |
| `src/OpenWSFZ.Web/WebApp.cs` | Add `GET /api/v1/serial/ports` endpoint; update effective-frequency resolution to three-tier rule |
| `src/OpenWSFZ.Web/AppJsonContext.cs` | Ensure `double?` / `CatConfig` serialisation still compiles after the new field |
| `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs` | Persist `LastPolledFrequencyMHz` on each ≥1 Hz change |

### Frontend (`web/`)

| File | Change |
|------|--------|
| `web/index.html` | Remove `hidden` attribute from `#cycle-timer` |
| `web/settings.html` | Restructure into tabs; replace serial port `<input>` with `<select>`+ refresh |
| `web/js/main.js` | Change `startCycleTimerIfEnabled` to use `visibility` |
| `web/js/settings.js` | Tab switching; CAT-enabled ↔ dial-freq binding; port enumeration |
| `web/js/api.js` | Add `getSerialPorts()` export |
| `web/css/app.css` | Add tab styles; add `#cycle-timer { visibility: hidden; }` default |

### Tests (`tests/`)

| File | Change |
|------|--------|
| `tests/OpenWSFZ.Web.Tests/SerialPortsApiTests.cs` | **New** — tests for `GET /api/v1/serial/ports` |
| `tests/OpenWSFZ.Web.Tests/EffectiveFrequencyTests.cs` | **New** — tests for three-tier resolution rule |
| `tests/OpenWSFZ.Config.Tests/CatConfigTests.cs` | Add test for `LastPolledFrequencyMHz` round-trip |
| `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs` | **New** — tests for persistence behaviour |

---

## 3. Backend Changes

### 3.1 CatConfig — new field (FR-039)

Add one nullable double field to the `CatConfig` record in
`src/OpenWSFZ.Abstractions/CatConfig.cs`:

```csharp
/// <summary>
/// Last successfully-polled VFO-A frequency in MHz, persisted across restarts (FR-039).
/// Written only by <c>CatPollingService</c>; never exposed as an editable UI field.
/// <c>null</c> until at least one successful poll has been persisted.
/// </summary>
public double? LastPolledFrequencyMHz { get; init; } = null;
```

This is the *only* change to `CatConfig`. Existing serialisation round-trips
are unaffected because `null` maps to a JSON `null` and unknown fields are
ignored on deserialisation.

### 3.2 CatPollingService — persist on poll (FR-039)

In `CatPollingService.RunAsync`, after a successful `GetDialFrequencyMhzAsync`
call, compare the new frequency to the currently-stored
`AppConfig.Cat.LastPolledFrequencyMHz`. If they differ by ≥ 1 Hz, save the
updated config asynchronously:

```csharp
// After: _catState.Update(freq, CatConnectionStatus.Connected);

var storedLast = _configStore.Current.Cat?.LastPolledFrequencyMHz;
if (HasFreqChanged(storedLast, freq))
{
    var updated = _configStore.Current with
    {
        Cat = (_configStore.Current.Cat ?? new CatConfig()) with
        {
            LastPolledFrequencyMHz = freq
        }
    };
    // Fire-and-forget — a failed persist is not fatal.
    _ = _configStore.SaveAsync(updated, CancellationToken.None)
                    .ContinueWith(t => _logger.LogWarning(
                        "CAT: failed to persist last-known frequency: {Msg}",
                        t.Exception?.GetBaseException().Message),
                        TaskContinuationOptions.OnlyOnFaulted);
}
```

Use the existing `HasFreqChanged` helper (already present for the WebSocket
event throttle) — no new logic required.

**Important:** do not await the save on the hot poll path; a sluggish filesystem
must not delay the next poll. The fire-and-forget pattern with an error log is
the correct approach here.

### 3.3 Effective frequency resolution — three-tier rule (FR-039)

The current helper expression used in `WebApp.cs` (`/api/v1/status`,
`/api/v1/decode/start`, `/api/v1/decode/stop`) is:

```csharp
catState?.DialFrequencyMHz ?? store.Current.DecodeLog?.DialFrequencyMHz ?? 0.0
```

Replace every occurrence with a call to a private helper:

```csharp
/// <summary>
/// Resolves the effective dial frequency using the three-tier rule (FR-039):
///   1. Live in-session CAT value (ICatState.DialFrequencyMHz — non-null)
///   2. Persisted last-known CAT value (AppConfig.Cat.LastPolledFrequencyMHz),
///      only when cat.enabled is true
///   3. Operator's manual fallback (AppConfig.DecodeLog.DialFrequencyMHz)
/// </summary>
static double ResolveEffectiveFrequency(ICatState? catState, AppConfig config)
{
    if (catState?.DialFrequencyMHz is { } live)
        return live;

    var cat = config.Cat;
    if (cat is { Enabled: true, LastPolledFrequencyMHz: { } persisted })
        return persisted;

    return config.DecodeLog?.DialFrequencyMHz ?? 0.0;
}
```

Apply this helper in all five places the old inline expression appeared:
`/api/v1/status` GET, `/api/v1/decode/start` POST, `/api/v1/decode/stop` POST,
and the WebSocketHub initial `status` event. Search for the old pattern to find
them all.

### 3.4 New REST endpoint — serial port enumeration (FR-038)

Add the following endpoint in `WebApp.cs` immediately after the
`GET /api/v1/audio/devices` endpoint:

```csharp
app.MapGet("/api/v1/serial/ports", () =>
{
    try
    {
        var ports = System.IO.Ports.SerialPort.GetPortNames();
        return TypedResults.Ok(ports.OrderBy(p => p).ToArray());
    }
    catch
    {
        return TypedResults.Ok(Array.Empty<string>());
    }
});
```

**AOT serialisation note:** `string[]` is already covered by `AppJsonContext`.
Verify the return type compiles under the AOT JSON source-generation
configuration; add `[JsonSerializable(typeof(string[]))]` to
`AppJsonContext.cs` if the build reports a missing type info provider.

---

## 4. Frontend Changes

### 4.1 `web/index.html` — remove hidden attribute (FR-036)

In the `#cycle-timer` span, remove the `hidden` attribute:

```html
<!-- Before -->
<span id="cycle-timer" hidden title="…">

<!-- After -->
<span id="cycle-timer" title="…">
```

CSS (see §4.4) provides the `visibility: hidden` default. No other change to
`index.html`.

### 4.2 `web/css/app.css` — new rules (FR-035, FR-036)

**Cycle timer default visibility:**

```css
/* FR-036: reserves layout space regardless of enabled state */
#cycle-timer {
  visibility: hidden;
}
```

**Tab styles** (add near the settings-specific block at the bottom of the file):

```css
/* ── Settings tabs (FR-035) ─────────────────────────────────────────────── */
.settings-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 1.5rem;
}

.settings-tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  color: var(--color-muted);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0.5rem 1.2rem;
  transition: color 0.15s, border-color 0.15s;
}

.settings-tab-btn:hover {
  color: var(--color-text);
  background: none;
}

.settings-tab-btn.active {
  border-bottom-color: var(--color-accent);
  color: var(--color-text);
  font-weight: 600;
}

.settings-tab-panel {
  display: none;
}

.settings-tab-panel.active {
  display: block;
}
```

### 4.3 `web/settings.html` — tabbed layout + serial port select (FR-035, FR-038)

Replace the flat `<form>` body with the tabbed structure below. Preserve all
existing element `id` attributes — `settings.js` references them by ID.

```html
<form id="settings-form" novalidate>

  <!-- ── Tab navigation ──────────────────────────────────────────────── -->
  <div class="settings-tabs" role="tablist" aria-label="Settings sections">
    <button type="button" class="settings-tab-btn active"
            role="tab" aria-selected="true"  aria-controls="tab-radio"   id="tab-btn-radio">
      Radio hardware
    </button>
    <button type="button" class="settings-tab-btn"
            role="tab" aria-selected="false" aria-controls="tab-logging" id="tab-btn-logging">
      Logging
    </button>
    <button type="button" class="settings-tab-btn"
            role="tab" aria-selected="false" aria-controls="tab-advanced" id="tab-btn-advanced">
      Advanced
    </button>
  </div>

  <!-- ── Tab 1: Radio hardware ───────────────────────────────────────── -->
  <div id="tab-radio" class="settings-tab-panel active" role="tabpanel" aria-labelledby="tab-btn-radio">

    <div class="field-group">
      <label for="device-select">Audio capture device</label>
      <select id="device-select">
        <option disabled>Loading devices…</option>
      </select>
    </div>

    <fieldset id="cat-settings">
      <legend>CAT rig connection</legend>

      <div class="field-group">
        <label class="checkbox-label">
          <input type="checkbox" id="cat-enabled" />
          Enable CAT frequency polling
        </label>
        <p class="field-hint">
          Polls the rig's VFO-A frequency and displays it live in the status bar.
          Keeps the ALL.TXT log accurate without manual dial-frequency entry.
        </p>
      </div>

      <div class="field-group" id="cat-status-indicator">
        <label>CAT connection status</label>
        <span id="cat-status-value" class="cat-status-badge cat-disabled">Disabled</span>
      </div>

      <div class="field-group">
        <label for="cat-rig-model">Rig transport</label>
        <select id="cat-rig-model">
          <option value="SerialCat">SerialCat — direct serial port</option>
          <option value="RigCtld">RigCtld — TCP to rigctld daemon</option>
        </select>
      </div>

      <!-- Serial CAT fields (shown when RigModel = SerialCat) -->
      <div id="cat-serial-fields">
        <div class="field-group">
          <label for="cat-serial-port">Serial port</label>
          <div class="input-with-action">
            <select id="cat-serial-port">
              <option value="">Loading ports…</option>
            </select>
            <button type="button" id="cat-serial-refresh" title="Refresh port list">↺ Refresh</button>
          </div>
          <p class="field-hint">
            Windows: <code>COM6</code> · Linux: <code>/dev/ttyUSB0</code> · macOS: <code>/dev/cu.usbserial</code>
          </p>
        </div>

        <div class="field-group">
          <label for="cat-baud-rate">Baud rate</label>
          <input type="number" id="cat-baud-rate" min="1200" max="115200" step="100" placeholder="9600" />
        </div>
      </div>

      <!-- rigctld fields (shown when RigModel = RigCtld) -->
      <div id="cat-rigctld-fields" style="display:none">
        <div class="field-group">
          <label for="cat-rigctld-host">rigctld host</label>
          <input type="text" id="cat-rigctld-host" placeholder="127.0.0.1" />
        </div>

        <div class="field-group">
          <label for="cat-rigctld-port">rigctld port</label>
          <input type="number" id="cat-rigctld-port" min="1" max="65535" placeholder="4532" />
        </div>

        <p class="field-hint cat-rigctld-note" id="cat-rigctld-note">
          ⚠ <strong>rigctld must be running before you enable CAT in this mode.</strong>
          Start it with e.g. <code>rigctld -m &lt;model-id&gt; -r COM6 -s 9600</code>.
          The daemon will retry automatically if rigctld is not yet available.
        </p>
      </div>

      <div class="field-group">
        <label for="cat-poll-interval">Poll interval (seconds)</label>
        <input type="number" id="cat-poll-interval" min="1" max="60" placeholder="1" />
        <p class="field-hint">How often to query the rig. Range: 1–60 seconds.</p>
      </div>

    </fieldset>
  </div><!-- /tab-radio -->

  <!-- ── Tab 2: Logging ───────────────────────────────────────────────── -->
  <div id="tab-logging" class="settings-tab-panel" role="tabpanel" aria-labelledby="tab-btn-logging">

    <fieldset id="decode-log-settings">
      <legend>Decode log (ALL.TXT)</legend>

      <div class="field-group">
        <label class="checkbox-label">
          <input type="checkbox" id="decode-log-enabled" />
          Write ALL.TXT decode log
        </label>
        <p class="field-hint">
          Appends one line per decoded FT8 message to the file below in
          WSJT-X compatible format after each 15-second cycle.
        </p>
      </div>

      <div class="field-group" id="decode-log-dependent">
        <label for="decode-log-path">ALL.TXT path</label>
        <input type="text" id="decode-log-path" placeholder="ALL.TXT" />
        <p class="field-hint">
          Relative to the executable, or an absolute path.
        </p>
      </div>

      <div class="field-group">
        <label for="decode-log-dial-freq">Dial frequency (MHz)</label>
        <input
          type="number"
          id="decode-log-dial-freq"
          step="0.001"
          min="0"
          placeholder="e.g. 7.074"
        />
        <p class="field-hint" id="decode-log-dial-freq-hint">
          Your radio's VFO setting — written to each ALL.TXT line.
          Leave at 0.000 if you do not need this column.
        </p>
      </div>

    </fieldset>

    <fieldset id="logging-settings">
      <legend>File logging</legend>

      <div class="field-group">
        <label class="checkbox-label">
          <input type="checkbox" id="logging-file-enabled" />
          Write logs to a file
        </label>
      </div>

      <div class="field-group" id="logging-dependent">
        <label for="logging-directory">Log directory</label>
        <input type="text" id="logging-directory" placeholder="logs" />
        <p class="field-hint">Relative to the executable, or an absolute path.</p>
      </div>

      <div class="field-group" id="logging-level-group">
        <label for="logging-file-log-level">File log level</label>
        <select id="logging-file-log-level">
          <option value="Trace">Trace — all internal loop counters, per-sample values</option>
          <option value="Debug">Debug — framer offsets, Costas scores, LLR magnitudes</option>
          <option value="Information">Information — pipeline events, decode results (default)</option>
          <option value="Warning">Warning — recoverable anomalies only</option>
          <option value="Error">Error — operation failures only</option>
          <option value="Critical">Critical — unrecoverable failures only</option>
        </select>
      </div>

      <div class="field-group">
        <label for="logging-rotation-schedule">Rotation schedule</label>
        <select id="logging-rotation-schedule">
          <option value="session">Session — new file on each start</option>
          <option value="hourly">Hourly — at each UTC hour boundary</option>
          <option value="daily" selected>Daily — at a configured UTC time</option>
          <option value="weekly">Weekly — on a configured day and time</option>
        </select>
      </div>

      <div class="field-group" id="logging-time-group">
        <label for="logging-rotation-time">Rotation time (UTC, HH:MM)</label>
        <input type="time" id="logging-rotation-time" value="00:00" />
      </div>

      <div class="field-group" id="logging-day-group" style="display:none">
        <label for="logging-rotation-day">Day of week</label>
        <select id="logging-rotation-day">
          <option value="Monday">Monday</option>
          <option value="Tuesday">Tuesday</option>
          <option value="Wednesday">Wednesday</option>
          <option value="Thursday">Thursday</option>
          <option value="Friday">Friday</option>
          <option value="Saturday">Saturday</option>
          <option value="Sunday">Sunday</option>
        </select>
      </div>

      <div class="field-group">
        <label for="logging-max-files">Maximum files to keep</label>
        <input type="number" id="logging-max-files" min="1" value="7" />
      </div>

    </fieldset>
  </div><!-- /tab-logging -->

  <!-- ── Tab 3: Advanced ─────────────────────────────────────────────── -->
  <div id="tab-advanced" class="settings-tab-panel" role="tabpanel" aria-labelledby="tab-btn-advanced">

    <div class="field-group">
      <label for="port-input">Web UI port</label>
      <input
        id="port-input"
        type="number"
        min="1"
        max="65535"
        placeholder="8080"
      />
    </div>

    <div class="field-group">
      <label for="log-level-select">Application log level</label>
      <select id="log-level-select">
        <option value="Trace">Trace — all internal loop counters, per-sample values</option>
        <option value="Debug">Debug — framer offsets, Costas scores, sweep positions</option>
        <option value="Information">Information — pipeline events, decode results (default)</option>
        <option value="Warning">Warning — recoverable anomalies (buffer overflow, reconnects)</option>
        <option value="Error">Error — operation failures that do not terminate the app</option>
        <option value="Critical">Critical — unrecoverable failures only</option>
        <option value="None">None — suppress all output</option>
      </select>
      <p class="field-hint">
        Requires an application restart to take effect. Output is written to stderr
        in the format <code>[OpenWSFZ] YYYY-MM-DD HH:MM:SS [LEVEL]  Component — message</code>.
      </p>
    </div>

    <div class="field-group">
      <label class="checkbox-label">
        <input type="checkbox" id="cycle-countdown-toggle" />
        Show cycle countdown
      </label>
      <p class="field-hint">
        <em>(Testing aid)</em> — Displays a countdown in the status bar to the next
        15-second FT8 cycle boundary, followed by an 8-second <strong>GO</strong>
        window — the time during which starting a test recording will capture a
        usable FT8 signal.
      </p>
    </div>

  </div><!-- /tab-advanced -->

  <div class="form-footer">
    <button id="save-btn" type="button" class="primary">Save</button>
    <p id="feedback" aria-live="polite"></p>
  </div>

</form>
```

**CSS addition for the Refresh button layout:**

```css
/* Input with an adjacent action button (e.g., serial port refresh) */
.input-with-action {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.input-with-action select,
.input-with-action input {
  flex: 1;
}
.input-with-action button {
  flex-shrink: 0;
  white-space: nowrap;
}
```

### 4.4 `web/js/api.js` — new export (FR-038)

Add one function after `getDevices`:

```js
/**
 * GET /api/v1/serial/ports
 * @returns {Promise<string[]>}
 */
export function getSerialPorts() {
  return fetchJson('/api/v1/serial/ports');
}
```

### 4.5 `web/js/main.js` — visibility-based cycle timer (FR-036)

Replace `startCycleTimerIfEnabled` entirely:

```js
/**
 * Fetch config. If ShowCycleCountdown is true, make the timer visible and
 * start the 100 ms tick. The hidden attribute is never used — see FR-036.
 */
async function startCycleTimerIfEnabled() {
  // Remove the HTML hidden attribute unconditionally — CSS provides the default
  // visibility: hidden state.  This prevents a FOUC if the attribute is left on
  // the element at parse time.
  cycleTimerEl.removeAttribute('hidden');

  try {
    const config = await getConfig();
    if (config.showCycleCountdown) {
      cycleTimerEl.style.visibility = 'visible';
      tickCycleTimer();
      setInterval(tickCycleTimer, 100);
    }
    // If false, CSS default (visibility: hidden) applies — no explicit set needed.
  } catch {
    // Config fetch failed — timer stays hidden (fail-safe).
  }
}
```

No other change to `main.js`.

### 4.6 `web/js/settings.js` — tabs, dial freq lock, serial port enum (FR-035, FR-037, FR-038)

The changes to `settings.js` are substantial. Below is a description rather than
a full rewrite, to guide the developer. The existing element references can all
be kept; only new references and new logic need adding.

**New element references (add near the top with the other declarations):**

```js
const catSerialRefreshBtn  = /** @type {HTMLButtonElement} */ (document.getElementById('cat-serial-refresh'));
const decodeLogDialFreqHint = /** @type {HTMLElement}       */ (document.getElementById('decode-log-dial-freq-hint'));
```

**Tab switching logic (add before `DOMContentLoaded`):**

```js
// ── Tab switching (FR-035) ────────────────────────────────────────────────

const TAB_STORAGE_KEY = 'settings-tab';
const tabBtns   = /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll('.settings-tab-btn'));
const tabPanels = /** @type {NodeListOf<HTMLElement>}       */ (document.querySelectorAll('.settings-tab-panel'));

function activateTab(panelId) {
  tabBtns.forEach(btn => {
    const isActive = btn.getAttribute('aria-controls') === panelId;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', String(isActive));
  });
  tabPanels.forEach(panel => {
    panel.classList.toggle('active', panel.id === panelId);
  });
  sessionStorage.setItem(TAB_STORAGE_KEY, panelId);
}

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const panelId = btn.getAttribute('aria-controls');
    if (panelId) activateTab(panelId);
  });
});

// Restore last active tab on load.
const savedTab = sessionStorage.getItem(TAB_STORAGE_KEY);
if (savedTab && document.getElementById(savedTab)) {
  activateTab(savedTab);
}
```

**Serial port enumeration (FR-038):**

```js
// ── Serial port enumeration (FR-038) ─────────────────────────────────────

let portsLoaded = false;

async function loadSerialPorts() {
  try {
    const ports = await getSerialPorts();
    const configured = catSerialPort.value;

    catSerialPort.innerHTML = '';
    if (ports.length === 0) {
      const opt = document.createElement('option');
      opt.value       = configured || '';
      opt.textContent = configured ? configured : '(no ports found)';
      catSerialPort.appendChild(opt);
    } else {
      // If the configured value is not in the list, prepend it.
      const allPorts = ports.includes(configured) || !configured
        ? ports
        : [configured, ...ports];

      for (const p of allPorts) {
        const opt = document.createElement('option');
        opt.value       = p;
        opt.textContent = p;
        catSerialPort.appendChild(opt);
      }
      catSerialPort.value = configured || ports[0] || '';
    }
    portsLoaded = true;
  } catch {
    // Best-effort; leave the select with its current content.
  }
}

catRigModel.addEventListener('change', () => {
  updateCatVisibility();
  if (catRigModel.value === 'SerialCat' && !portsLoaded) {
    loadSerialPorts();
  }
});

catSerialRefreshBtn.addEventListener('click', () => {
  portsLoaded = false;
  loadSerialPorts();
});
```

Update `getSerialPorts` import at the top of the file:
```js
import { getConfig, getDevices, postConfig, getStatus, getSerialPorts } from './api.js';
```

**Dial frequency lock (FR-037):**

```js
// ── Dial frequency lock (FR-037) ──────────────────────────────────────────

function updateDialFreqLock() {
  const locked = catEnabled.checked;
  decodeLogDialFreq.disabled = locked;
  if (locked) {
    decodeLogDialFreqHint.textContent =
      'Overridden by CAT — the live rig frequency is used while polling is active.';
  } else {
    decodeLogDialFreqHint.textContent =
      'Your radio\'s VFO setting — written to each ALL.TXT line. ' +
      'Leave at 0.000 if you do not need this column.';
  }
}

catEnabled.addEventListener('change', updateDialFreqLock);
```

Call `updateDialFreqLock()` at the end of the `DOMContentLoaded` block, after the
existing `updateCatVisibility()` call. Also call `loadSerialPorts()` there if
`catRigModel.value === 'SerialCat'`:

```js
// Inside DOMContentLoaded, after existing init calls:
updateDialFreqLock();
if (catRigModel.value === 'SerialCat') {
  loadSerialPorts();
}
```

**Save — read serial port value correctly:**

The existing save logic reads `catSerialPort.value.trim() || 'COM6'`. This
still works for `<select>` elements, so no change is needed in the `saveBtn`
handler.

---

## 5. Testing Requirements

### 5.1 Backend — `GET /api/v1/serial/ports` (FR-038)

File: `tests/OpenWSFZ.Web.Tests/SerialPortsApiTests.cs`

- `GET /api/v1/serial/ports` returns HTTP 200 with `Content-Type: application/json`.
- Returns a JSON array of strings (may be empty on the CI runner — that is valid).
- The endpoint does not throw even if `SerialPort.GetPortNames()` would throw on
  the test host (consider injecting a delegate override or accepting the empty-array fallback path in tests).

### 5.2 Backend — three-tier frequency resolution (FR-039)

File: `tests/OpenWSFZ.Web.Tests/EffectiveFrequencyTests.cs`  
Use parameterised theory tests (xUnit `[Theory, InlineData]`):

| Scenario | `ICatState.DialFreq` | `Cat.Enabled` | `Cat.LastPolled` | `DecodeLog.Dial` | Expected |
|----------|----------------------|---------------|-----------------|-----------------|---------|
| Live CAT active | 14.074 | true | 7.074 | 3.573 | **14.074** |
| Session restart, CAT enabled | null | true | 7.074 | 3.573 | **7.074** |
| CAT disabled, persisted ignored | null | false | 7.074 | 3.573 | **3.573** |
| No CAT, manual only | null | false | null | 7.074 | **7.074** |
| All null / zero | null | false | null | 0.0 | **0.0** |

### 5.3 Backend — frequency persistence on poll (FR-039)

File: `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceFreqPersistTests.cs`

- After a successful poll that differs from `LastPolledFrequencyMHz` by ≥ 1 Hz,
  `IConfigStore.SaveAsync` is called with the updated frequency.
- After a successful poll within 1 Hz of the stored value, `SaveAsync` is NOT
  called a second time (no churn).
- A `SaveAsync` failure is logged at Warning and does NOT stop the poll loop.

### 5.4 Frontend (manual verification checklist)

These are not automated in this change; the developer SHALL verify manually
before raising the PR:

- [ ] Settings page opens on **Radio hardware** tab by default.
- [ ] Switching to **Logging** and then navigating away and back restores **Logging**.
- [ ] All fields in all three tabs are submitted when Save is clicked.
- [ ] With `cat.enabled = true`, the dial frequency field is visually greyed out
      on page load and the hint text reflects CAT control.
- [ ] Toggling the CAT enabled checkbox enables/disables the dial freq field live.
- [ ] When **SerialCat** is selected, the serial port dropdown is populated.
- [ ] Clicking **Refresh** clears and repopulates the dropdown.
- [ ] If the configured port is not in the enumerated list, it appears as the
      first option (selected).
- [ ] On the main page, `#cycle-timer` is always present in the DOM with no
      layout shift regardless of whether it is visible.
- [ ] After saving `showCycleCountdown = false`, the status bar layout is stable
      (no content jumps to fill the timer's space).

---

## 6. Constraints & Edge Cases

### 6.1 `sessionStorage` for tab state

`sessionStorage` is cleared when the browser tab is closed, which is the correct
behaviour — the operator should start fresh each session. Do not use
`localStorage` (that would persist across sessions, which could be confusing if
the operator bookmarks the settings page).

### 6.2 Serial port select + typed fallback

`System.IO.Ports.SerialPort.GetPortNames()` is reliable on Windows. On Linux
and macOS it typically works but may return an empty list in some configurations.
The UI requirement is simply that the configured value is always preserved; the
empty-list fallback (pre-populating the `<select>` with the configured value)
handles this correctly. There is no requirement to fall back to a plain
`<input type="text">`.

### 6.3 `LastPolledFrequencyMHz` not in Settings UI

This field is written only by `CatPollingService`. The Settings page must not
expose it as an editable field; the `POST /api/v1/config` handler already
persists whatever it receives, so if the JS inadvertently omits the field from
the save payload, the value will be reset to null. The developer should verify
that the save payload construction in `settings.js` passes the `cat` object with
all existing fields intact — the existing code already does `cat: { enabled, rigModel, serialPort, baudRate, ... }` which omits `lastPolledFrequencyMHz` from the
save payload. This will reset the field to null on every save.

**Fix required:** In `settings.js`, when building the `cat` object for `postConfig`,
spread or carry forward the `cat.lastPolledFrequencyMHz` from the loaded config:

```js
// At DOMContentLoaded time, store the opaque fields the UI doesn't edit:
let catOpaqueFields = {};

// Inside DOMContentLoaded, after reading config:
catOpaqueFields = {
  lastPolledFrequencyMHz: config.cat?.lastPolledFrequencyMHz ?? null,
};

// Inside saveBtn click handler, when building cat:
const cat = {
  ...catOpaqueFields,          // ← carry forward server-managed fields
  enabled:             catEnabled.checked,
  rigModel:            catRigModel.value,
  serialPort:          catSerialPort.value.trim() || 'COM6',
  baudRate:            parseInt(catBaudRate.value, 10) || 9600,
  rigctldHost:         catRigctldHost.value.trim()  || '127.0.0.1',
  rigctldPort:         parseInt(catRigctldPort.value, 10) || 4532,
  pollIntervalSeconds: Math.max(1, Math.min(60, parseInt(catPollInterval.value, 10) || 1)),
};
```

### 6.4 AOT / JSON serialisation

`CatConfig` is serialised via `AppJsonContext`. After adding
`LastPolledFrequencyMHz`, confirm that `dotnet build -c Release -r win-x64`
still succeeds — the AOT JSON source generator will regenerate automatically, but
if there is a nullable double in a place that was not previously declared as
`JsonSerializable`, you may need to add `[JsonSerializable(typeof(double?))]` to
the context.

---

## 7. Suggested Implementation Order

1. **Backend first:**
   - `CatConfig.cs` — add `LastPolledFrequencyMHz` field.
   - `WebApp.cs` — add `ResolveEffectiveFrequency` helper; update all call sites;
     add `GET /api/v1/serial/ports`.
   - `CatPollingService.cs` — persist on poll.
   - Build + existing tests green.
2. **Backend tests:**
   - `EffectiveFrequencyTests.cs` (five theory cases).
   - `SerialPortsApiTests.cs`.
   - `CatPollingServiceFreqPersistTests.cs`.
3. **Frontend:**
   - `app.css` — add tab styles and `#cycle-timer` visibility rule.
   - `index.html` — remove `hidden` attribute.
   - `api.js` — add `getSerialPorts`.
   - `settings.html` — restructure into tabs with new serial port `<select>`.
   - `settings.js` — tab switching, dial freq lock, serial port enum, opaque fields carry-forward.
   - `main.js` — update `startCycleTimerIfEnabled`.
4. **Manual verification checklist** (§5.4).
5. **Raise PR** against `feat/p17-settings-ux` → `main`.

---

*This briefing supersedes no prior documents. All new requirements are formally
recorded in `REQUIREMENTS.md` as FR-035 through FR-039.*
