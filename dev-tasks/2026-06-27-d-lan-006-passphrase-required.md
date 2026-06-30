# DEV TASK — D-LAN-006: Enforce passphrase requirement on remote-access save

**Date:** 2026-06-27
**QA defect ID:** D-LAN-006
**Severity:** Blocker

---

## 1. Context

SEC-001 (`LanModeValidator`) causes the daemon to refuse to start when
`RemoteAccess.Enabled = true` and `Passphrase` is null/whitespace. However:

- The Settings UI (`settings.html`) shows a passphrase placeholder of
  *"Leave empty for open LAN access"* and a hint of
  *"Leave empty to allow unauthenticated LAN access"* — both actively
  inviting the operator to omit it.
- The `POST /api/v1/config` API endpoint accepts and persists the
  contradictory configuration without complaint.
- The result: the daemon becomes unlaunchable, recoverable only by
  manually editing `app.json`.

This task closes the gap on all three layers: API validation, UI
validation, and UI text corrections. A fourth item corrects a stale doc
comment in `RemoteAccessConfig.cs`.

---

## 2. Branch name

```
fix/d-lan-006-passphrase-required
```

---

## 3. Actions

### 3.1 — API validation (`src/OpenWSFZ.Web/WebApp.cs`)

In the `POST /api/v1/config` handler, **after** the existing TX config
validation block (around line 381, before the `await store.SaveAsync`
call), add:

```csharp
// ── Remote access config validation (SEC-001 / D-LAN-006) ──────────────
// The daemon refuses to start when Enabled = true and Passphrase is absent.
// Reject the save here so the operator cannot commit an unlaunchable config.
if (config.RemoteAccess is { Enabled: true } &&
    string.IsNullOrWhiteSpace(config.RemoteAccess.Passphrase))
{
    return Results.BadRequest(
        "A passphrase is required when remote access is enabled. " +
        "Enter a passphrase before saving.");
}
```

No new using directives are needed. `Results.BadRequest` is already used
in this handler.

### 3.2 — UI validation (`web/js/settings.js`)

In the `saveBtn` click handler, **after** the port validation block
(lines 756–760) and **before** the `try {` that begins the remote-access
/ decoder collection, add:

```javascript
// D-LAN-006: passphrase is mandatory when remote access is enabled.
if (remoteAccessEnabled.checked && !remoteAccessPassphrase.value.trim()) {
  showFeedback(
    'A passphrase is required when remote access is enabled.',
    'error'
  );
  saveBtn.disabled = false;
  return;
}
```

### 3.3 — UI text corrections (`web/settings.html`)

**Change 1** — passphrase `<input>` placeholder (line 455):

```html
<!-- BEFORE -->
placeholder="Leave empty for open LAN access"

<!-- AFTER -->
placeholder="Required when remote access is enabled"
```

**Change 2** — field hint `<p>` (lines 458–463): replace the entire
paragraph content:

```html
<!-- BEFORE -->
<p class="field-hint">
  Non-loopback clients must supply this passphrase via the
  <code>X-Api-Key</code> header (REST) or <code>?key=</code> query
  parameter (WebSocket). Leave empty to allow unauthenticated LAN access.
  Stored as plaintext in <code>app.json</code>.
</p>

<!-- AFTER -->
<p class="field-hint">
  Required. Non-loopback clients must supply this passphrase via the
  <code>X-Api-Key</code> header (REST) or as the first WebSocket message
  frame. Stored as plaintext in <code>app.json</code>.
</p>
```

### 3.4 — Doc comment correction (`src/OpenWSFZ.Abstractions/RemoteAccessConfig.cs`)

The `Passphrase` property XML comment (lines 44–49) describes the
pre-SEC-001 design. Replace:

```csharp
/// <summary>
/// Shared passphrase for non-loopback access.
/// <c>null</c> or empty means no authentication is required (open LAN access).
/// Stored as plaintext in <c>app.json</c>; acceptable for a home LAN threat model.
/// Default: <c>null</c>.
/// </summary>
```

With:

```csharp
/// <summary>
/// Shared passphrase for non-loopback access.
/// <para>
/// <strong>Required</strong> when <see cref="Enabled"/> is <c>true</c>.
/// The daemon refuses to start (<c>LanModeValidator</c>, SEC-001) and
/// <c>POST /api/v1/config</c> returns 400 when this is null or whitespace
/// with <see cref="Enabled"/> set.
/// </para>
/// Stored as plaintext in <c>app.json</c>; acceptable for a home LAN threat model.
/// Default: <c>null</c> (safe only when <see cref="Enabled"/> is <c>false</c>).
/// </summary>
```

### 3.5 — Tests (`tests/OpenWSFZ.Web.Tests/`)

Add three test cases in the existing config-API test class (or a new
`RemoteAccessConfigValidationTests.cs` if that is tidier):

| Scenario | `enabled` | `passphrase` | Expected status |
|---|---|---|---|
| Enabled, no passphrase | `true` | `null` | `400 Bad Request` |
| Enabled, whitespace passphrase | `true` | `"   "` | `400 Bad Request` |
| Enabled, valid passphrase | `true` | `"hunter2"` | `200 OK` |
| Disabled, no passphrase | `false` | `null` | `200 OK` |

Use the same `WebApplicationFactory` / `WebApp.Create` test fixture
pattern that the existing Web.Tests use. The response body of the 400
cases should contain the phrase `"passphrase is required"`.

---

## 4. Acceptance criteria

The QA engineer will verify the following before approving merge:

- [ ] **AC-1** Saving with Remote Access enabled and an empty passphrase
  shows an inline error message in the UI and does NOT call `POST
  /api/v1/config`.
- [ ] **AC-2** `POST /api/v1/config` with `remoteAccess: { enabled: true,
  passphrase: null }` returns `400 Bad Request` with a body containing
  `"passphrase is required"`.
- [ ] **AC-3** `POST /api/v1/config` with `remoteAccess: { enabled: true,
  passphrase: "secret" }` returns `200 OK`.
- [ ] **AC-4** `POST /api/v1/config` with `remoteAccess: { enabled: false,
  passphrase: null }` returns `200 OK` (disabled remote access needs no
  passphrase).
- [ ] **AC-5** The passphrase field placeholder no longer says "Leave
  empty for open LAN access".
- [ ] **AC-6** The passphrase field hint no longer says "Leave empty to
  allow unauthenticated LAN access".
- [ ] **AC-7** All 4 new tests pass. Existing 712-test suite remains
  green. Build: 0 errors, 0 warnings.
- [ ] **AC-8** `LanModeValidator` remains unchanged — it is the
  daemon-startup backstop and must not be weakened.

---

## 5. References

- `LanModeValidator.cs` (SEC-001) — `src/OpenWSFZ.Daemon/LanModeValidator.cs`
- `RemoteAccessConfig.cs` — `src/OpenWSFZ.Abstractions/RemoteAccessConfig.cs`
- `WebApp.cs` POST /api/v1/config handler — `src/OpenWSFZ.Web/WebApp.cs` lines 291–424
- `settings.js` save handler — `web/js/settings.js` lines 734–862
- `settings.html` remote access fieldset — `web/settings.html` lines 432–503
- Security hardening change: `openspec/changes/archive/2026-06-24-security-lan-hardening/`
