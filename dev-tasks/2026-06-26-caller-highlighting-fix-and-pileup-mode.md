# Handoff: Caller highlighting ID bug + pileup-mode control on main page

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action

---

## 1. Context

Two independent items arising from live testing of `feat/qso-caller` after commit
`8f642f1` (D-CALLER-001 + D-CALLER-002 fix).

- **D-CALLER-002A** — The retroactive partner-highlight scan introduced in `8f642f1`
  is silently broken: it queries `#decodes-tbody` but the actual DOM element in
  `index.html` has ID `decodes-body`.  `querySelectorAll` returns an empty NodeList;
  no rows are ever retroactively highlighted.

- **FR-PILEUP-001** — The `callerPartnerSelect` setting (First / None) controls whether
  the service auto-engages the first responder or waits for the operator to click a
  highlighted row.  The setting exists in `settings.html` but is (a) buried behind a
  navigation away from the main page, and (b) only revealed when TX Mode is already set
  to Caller in that page's own dropdown.  Operators cannot change the mode mid-session
  without leaving the operating page.  The Captain requires this control on the main
  page, persistent across sessions.

---

## 2. Branch

`feat/qso-caller` (existing) — add one or more commits directly to this branch.

---

## 3. Actions

### 3.1 — Fix the retroactive scan element ID (D-CALLER-002A)

**File:** `web/js/main.js`
**Location:** `renderTxPanel`, inside the `if (partner !== previousPartner)` block (~line 212)

**Current (broken):**
```javascript
document.querySelectorAll('#decodes-tbody tr').forEach(row => {
```

**Correct:**
```javascript
document.querySelectorAll('#decodes-body tr').forEach(row => {
```

The HTML element in `index.html` (line 78) has `id="decodes-body"`.  The dev-task
spec used `#decodes-tbody`; the implementation copied the spec verbatim rather than
checking the actual DOM.

**No other changes required for this item.**

---

### 3.2 — Add `POST /api/v1/tx/caller-partner-select` endpoint (backend)

Pattern mirrors the existing `POST /api/v1/tx/enable` / `disable` endpoints:
accept a tiny payload, update one config field, save, return the updated status.

**File:** `src/OpenWSFZ.Web/WebApp.cs`

```csharp
// ── POST /api/v1/tx/caller-partner-select ────────────────────────────────

app.MapPost("/api/v1/tx/caller-partner-select", async (
    HttpRequest       request,
    CancellationToken ct) =>
{
    // Body: {"mode":"First"} or {"mode":"None"}
    var body = await request.ReadFromJsonAsync<CallerPartnerSelectRequest>(
        AppJsonContext.Default.CallerPartnerSelectRequest, ct);
    if (body is null ||
        (body.Mode != "First" && body.Mode != "None"))
    {
        return Results.BadRequest("mode must be \"First\" or \"None\"");
    }

    var cfg    = configStore.Load();
    var newTx  = cfg.Tx with { CallerPartnerSelect =
                     body.Mode == "First"
                         ? CallerPartnerSelectMode.First
                         : CallerPartnerSelectMode.None };
    var newCfg = cfg with { Tx = newTx };
    await configStore.SaveAsync(newCfg, ct);

    var txStatus = router.GetCurrentStatus();          // or equivalent getter
    return Results.Ok(new TxStatusResponse(
        txStatus.State.ToString(),
        txStatus.Partner,
        AutoAnswerEnabled: cfg.Tx.AutoAnswer,
        Role: txStatus.Role.ToString().ToLowerInvariant(),
        CallerPartnerSelect: body.Mode));
}).WithAuth();
```

Add the request DTO near the other inner DTOs in `AppJsonContext.cs`:
```csharp
internal sealed record CallerPartnerSelectRequest(string Mode);
// + [JsonSerializable(typeof(CallerPartnerSelectRequest))] in the context
```

**Extend `TxStatusResponse`** to include `CallerPartnerSelect` so the main page can
initialise the control from `GET /api/v1/tx/status` rather than needing a separate
config fetch:

```csharp
// Before:
public sealed record TxStatusResponse(
    string State, string? Partner, bool AutoAnswerEnabled, string Role = "answerer");

// After:
public sealed record TxStatusResponse(
    string State, string? Partner, bool AutoAnswerEnabled,
    string Role = "answerer",
    string CallerPartnerSelect = "First");
```

Update all construction sites (enable, disable, status, call-cq, select-responder,
caller-partner-select) to pass `CallerPartnerSelect: cfg.Tx.CallerPartnerSelect.ToString()`.

> **Note:** adding a new field with a default value to a record does not break
> existing tests that don't supply it — no mechanical test changes required,
> but verify no tests assert the full serialised JSON string.

---

### 3.3 — Add `postTxCallerPartnerSelect` to `api.js`

**File:** `web/js/api.js`

```javascript
/**
 * POST /api/v1/tx/caller-partner-select
 * Persists the caller partner-select mode to config.
 * @param {'First'|'None'} mode
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean,
 *                    role: string, callerPartnerSelect: string}>}
 */
export async function postTxCallerPartnerSelect(mode) {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/caller-partner-select', {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Api-Key': key } : {}),
    },
    body: JSON.stringify({ mode }),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }
  if (!res.ok) {
    const err = new Error(
      `HTTP ${res.status} ${res.statusText} — /api/v1/tx/caller-partner-select`);
    throw err;
  }
  return res.json();
}
```

Add `postTxCallerPartnerSelect` to the import in `main.js`.

---

### 3.4 — Add pileup-mode toggle to `index.html`

Place the control in the TX panel, below the button row and above the state display,
wrapped in a `<div>` that is conditionally shown only when `currentTxRole === 'caller'`
(visibility managed by JS, not CSS `hidden`, so it can animate if desired):

```html
<!-- Pileup mode toggle (caller role only) — shown/hidden by JS -->
<div id="pileup-mode-row" class="tx-pileup-row" hidden>
  <label class="checkbox-label">
    <input type="checkbox" id="pileup-auto-select">
    Auto-answer first responder
  </label>
</div>
```

Insert between the `.tx-controls-row` `<div>` (buttons) and the `.tx-state-row` `<div>`.

---

### 3.5 — Wire the toggle in `main.js`

**Additions needed in `main.js`:**

```javascript
// ── Pileup-mode toggle (FR-PILEUP-001) ───────────────────────────────────
const pileupModeRowEl      = document.getElementById('pileup-mode-row');
const pileupAutoSelectEl   =
  /** @type {HTMLInputElement} */ (document.getElementById('pileup-auto-select'));
```

**On `renderTxPanel` call** (or a new `renderPileupToggle(role, mode)` helper):
```javascript
// Show the pileup-mode row only in caller role.
if (pileupModeRowEl) {
  pileupModeRowEl.hidden = (effectiveRole !== 'caller');
}
// Sync checkbox state.
if (pileupAutoSelectEl) {
  pileupAutoSelectEl.checked = (currentCallerPartnerSelect === 'First');
}
```

**Change handler (register once at module level):**
```javascript
if (pileupAutoSelectEl) {
  pileupAutoSelectEl.addEventListener('change', async () => {
    const newMode = pileupAutoSelectEl.checked ? 'First' : 'None';
    // Optimistic local update.
    currentCallerPartnerSelect = newMode;

    try {
      await postTxCallerPartnerSelect(newMode);
    } catch (err) {
      // Revert on error.
      currentCallerPartnerSelect = newMode === 'First' ? 'None' : 'First';
      pileupAutoSelectEl.checked  = (currentCallerPartnerSelect === 'First');
      console.error('Failed to save pileup mode:', err);
    }
  });
}
```

**On page load** (in `startCycleTimerIfEnabled`, after reading `callerPartnerSelect`
from config, or from the `getTxStatus()` response if `TxStatusResponse` now includes
the field):
```javascript
if (config.tx?.callerPartnerSelect != null) {
  currentCallerPartnerSelect = config.tx.callerPartnerSelect;
}
// Sync initial checkbox state (no event fired):
if (pileupAutoSelectEl) {
  pileupAutoSelectEl.checked = (currentCallerPartnerSelect === 'First');
}
```

---

### 3.6 — CSS for the new row

**File:** `web/css/app.css`

Add a simple style consistent with the existing `.waterfall-hold-label` checkbox row:

```css
/* ── Pileup-mode toggle row ─────────────────────────────────────────────── */
.tx-pileup-row {
  padding: 0.3rem 0;
  font-size: 0.875rem;
}
```

---

### 3.7 — Unit tests for the new backend endpoint

Add to the appropriate test file (or a new `QsoCallerPartnerSelectTests.cs`):

1. **`PostCallerPartnerSelect_None_UpdatesConfigAndReturns200`**
   — POST `{"mode":"None"}` → 200, response `callerPartnerSelect === "None"`,
   config store confirms `CallerPartnerSelectMode.None` was saved.

2. **`PostCallerPartnerSelect_First_UpdatesConfigAndReturns200`**
   — POST `{"mode":"First"}` → 200, `callerPartnerSelect === "First"`.

3. **`PostCallerPartnerSelect_InvalidMode_Returns400`**
   — POST `{"mode":"Banana"}` → 400.

---

## 4. Acceptance criteria

QA will verify the following before approving merge to `main`:

1. **Retroactive highlighting works (D-CALLER-002A):** After "Call CQ" and a response
   decode arrives in the same batch that identifies the partner, the response row gains
   `decode-partner` styling within one event-loop tick.  Verify in DevTools → Elements.

2. **73-confirmation highlighting still works (D-CALLER-002 gap 2):** After QSO
   completion, the partner's 73 row (next cycle) is highlighted; highlight clears ~16 s
   later.

3. **Pileup-mode toggle visible in caller role:** After clicking "Call CQ", the
   "Auto-answer first responder" checkbox appears in the TX panel.

4. **Pileup-mode toggle invisible in answerer role:** When no CQ session is active
   (Idle) the checkbox row is hidden.

5. **Checkbox reflects persisted value on page load:** If config has
   `callerPartnerSelect = "None"`, the checkbox is unchecked on a fresh page load.

6. **Checkbox change persists:** Toggling the checkbox → reload the page → the
   checkbox still reflects the changed value (config was saved).

7. **Revert on API failure:** If the API call fails (simulate by blocking the endpoint),
   the checkbox reverts to the previous state.

8. **Backend endpoint validation:** POST `{"mode":"Banana"}` returns 400.

9. **Existing tests green:** `dotnet test OpenWSFZ.slnx -c Release` — zero failures.

10. **Zero build warnings:** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors,
    0 warnings.

11. **Answerer unaffected:** `QsoAnswererService` behaviour is unchanged.

---

## 5. References

- D-CALLER-002 original dev task: `dev-tasks/2026-06-26-caller-response-detection-and-highlighting.md`
- Implementing commit: `8f642f1` — introduces the retroactive scan with the wrong ID
- Bug location: `web/js/main.js` ~line 212, selector `#decodes-tbody` (should be
  `#decodes-body` per `web/index.html` line 78)
- Existing pattern for single-field config persistence: `POST /api/v1/tx/enable` /
  `disable` in `src/OpenWSFZ.Web/WebApp.cs`
- `CallerPartnerSelectMode` enum: `src/OpenWSFZ.Abstractions/CallerPartnerSelectMode.cs`
- `TxConfig.CallerPartnerSelect` field: `src/OpenWSFZ.Abstractions/TxConfig.cs` line 131
- `currentCallerPartnerSelect` JS variable: `web/js/main.js` line 63
- UI visibility rule (MEMORY.md): controls appear once backend is implemented end-to-end.
  The backend already exists for the `None` / `First` behaviour; this item adds the
  persistence endpoint and the main-page toggle only.
