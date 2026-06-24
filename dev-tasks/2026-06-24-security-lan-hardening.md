# Security Hardening — LAN Mode (SEC-001, SEC-002, SEC-003)

**Date:** 2026-06-24
**Raised by:** QA engineer (security review 2026-06-24)
**Branch:** `fix/security-lan-hardening`
**Priority:** Medium — all three findings are confined to LAN remote-access mode (`RemoteAccess.Enabled = true`), which is off by default. The default loopback-only configuration is unaffected. Address before LAN mode is documented or promoted to users.

---

## Context

A security review of the public repository identified three confirmed vulnerabilities, all exploitable only when LAN remote access is enabled. They are grouped into a single branch because they share the same threat model and the fixes are small and self-contained.

| ID | Finding | Severity | Confidence |
|---|---|---|---|
| SEC-001 | Open LAN access when passphrase is unconfigured (`NullAuthPolicy`) | MEDIUM | 9/10 |
| SEC-002 | Passphrase exposed in URL query parameter + non-constant-time comparison | MEDIUM | 9/10 |
| SEC-003 | Stored XSS via `innerHTML` in frequency table rows (`settings.js`) | MEDIUM | 8/10 |

---

## SEC-001 — Startup guard: require passphrase when LAN mode is enabled

**File:** `src/OpenWSFZ.Daemon/Program.cs` (around line 255)
**File:** `src/OpenWSFZ.Web/NullAuthPolicy.cs`

When `RemoteAccess.Enabled = true` and `RemoteAccess.Passphrase` is null or empty, `NullAuthPolicy` is registered and unconditionally authorises every request. Any device on the network can reach all REST endpoints — including TX control, rig tuning, and full config read/write — with no authentication.

### Actions

1. In `Program.cs`, before the DI container is built, add a startup validation:

```csharp
if (config.RemoteAccess.Enabled &&
    string.IsNullOrWhiteSpace(config.RemoteAccess.Passphrase))
{
    logger.LogCritical(
        "LAN remote access is enabled but no passphrase is configured. " +
        "Set RemoteAccess.Passphrase in config.json before enabling LAN mode. " +
        "Refusing to start.");
    return 1;
}
```

2. The existing `NullAuthPolicy` class may remain for the loopback-only code path (where it is appropriate — the daemon only binds to 127.0.0.1 in that mode). No change to `NullAuthPolicy` itself is required; the guard above prevents it from ever being reached in LAN mode without a passphrase.

3. Update the config schema documentation / any in-code XML doc comment on `RemoteAccessConfig.Passphrase` to state that a non-empty passphrase is mandatory when `Enabled = true`.

---

## SEC-002 — Timing-safe passphrase comparison + remove passphrase from URL

### Part A — Constant-time comparison

**File:** `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs` (around lines 29–47)

The current comparison uses `==` on strings, which is not constant-time. Replace with:

```csharp
using System.Security.Cryptography;
using System.Text;

// Replace the == comparison with:
bool authorised = CryptographicOperations.FixedTimeEquals(
    Encoding.UTF8.GetBytes(suppliedPassphrase),
    Encoding.UTF8.GetBytes(configuredPassphrase));
```

`CryptographicOperations.FixedTimeEquals` requires both spans to be the same length to be meaningful; if lengths differ, return false immediately (length itself is not secret):

```csharp
var supplied   = Encoding.UTF8.GetBytes(suppliedPassphrase);
var configured = Encoding.UTF8.GetBytes(configuredPassphrase);
if (supplied.Length != configured.Length) return false;
return CryptographicOperations.FixedTimeEquals(supplied, configured);
```

### Part B — Remove passphrase from login redirect URL

**File:** `web/login.html` (around lines 159–164)
**File:** `web/js/ws.js` (around lines 31–33)

The login page currently navigates to `returnPath?key=<passphrase>`, causing the credential to appear in server access logs, proxy logs, and browser history. The WebSocket URL also includes `?key=<passphrase>` permanently.

REST calls already correctly use the `X-Api-Key` header — extend this pattern:

1. **`login.html`:** After storing the key in `sessionStorage`, navigate to `returnPath` only (no `?key=` appended). The receiving page reads the key from `sessionStorage` via the existing `api.js` pattern.

2. **`ws.js`:** Remove the `?key=` query parameter from the WebSocket URL. Instead, immediately after the socket `open` event, send a JSON auth frame:

```js
socket.addEventListener('open', () => {
    const key = sessionStorage.getItem('owsfz-api-key');
    if (key) {
        socket.send(JSON.stringify({ type: 'auth', key }));
    }
});
```

3. **`WebSocketHub.cs`:** Add server-side handling for the initial auth frame. Before accepting any other messages on a LAN-mode connection, expect a `{"type":"auth","key":"..."}` message and validate it against `PassphraseAuthPolicy`. Close the connection with code 4001 if the auth frame is absent or invalid.

> **Note:** The WebSocket upgrade request already carries the `X-Api-Key` header for initial HTTP-level auth (ASP.NET Core processes this before the upgrade). Part B is defence-in-depth to eliminate the credential from the URL — verify whether the upgrade-time header check alone is sufficient before deciding how much of the WebSocket auth frame work is required. If the key is validated at upgrade time via the header, the URL query-string removal alone may be sufficient.

---

## SEC-003 — Replace `innerHTML` with DOM construction in frequency table

**File:** `web/js/settings.js` (around lines 307–312)

`appendFreqRow` sets `tr.innerHTML` from a template literal. The `escAttr()` helper escapes only `&` and `"` — it does not escape `<` or `>`. Frequency entry values ultimately derive from `POST /api/v1/frequencies`; a malicious `description` value such as `<img src=x onerror=…>` will execute when the Frequencies tab is opened.

The decode table in `main.js` already uses the correct pattern with `textContent` and `createElement`. Mirror that approach:

```js
function appendFreqRow(protocol, frequencyMhz, description) {
    const tr = freqTableBody.insertRow();
    tr.setAttribute('data-freq-row', '');

    const makeInputCell = (type, cls, val) => {
        const td = tr.insertCell();
        const inp = document.createElement('input');
        inp.type      = type;
        inp.className = cls;
        inp.value     = val;
        td.appendChild(inp);
    };

    makeInputCell('text',   'freq-protocol',    protocol);
    makeInputCell('number', 'freq-mhz',         frequencyMhz);
    makeInputCell('text',   'freq-description', description);

    const tdDel = tr.insertCell();
    const btn   = document.createElement('button');
    btn.type      = 'button';
    btn.className = 'freq-delete-btn';
    btn.textContent = '✕';
    tdDel.appendChild(btn);
}
```

Adjust property names and class names to match whatever the existing template uses — the structure above is illustrative. The key constraint is: **no user-derived value may be assigned to `innerHTML`**.

Also audit the rest of `settings.js` for any other `innerHTML` assignments that incorporate server-returned data and apply the same treatment.

---

## Acceptance Criteria

QA will verify the following before approving merge to `main`:

### SEC-001
- [ ] Starting the daemon with `RemoteAccess.Enabled = true` and no passphrase configured exits with a non-zero return code and logs a `Critical`-level message naming the missing field.
- [ ] Starting the daemon with `RemoteAccess.Enabled = true` and a non-empty passphrase proceeds normally.
- [ ] Starting the daemon with `RemoteAccess.Enabled = false` (default) proceeds normally regardless of passphrase value.
- [ ] Unit test added: `DaemonStartup_LanModeWithoutPassphrase_RefusesToStart`.

### SEC-002
- [ ] After a successful login, the browser URL bar shows `returnPath` with no `?key=` parameter.
- [ ] Browser history contains no URL with `key=` in it after a login/navigate cycle (verified manually in DevTools → Application → History, or by inspecting the redirect chain in Network tab).
- [ ] The WebSocket URL in DevTools → Network → WS shows no `?key=` query parameter.
- [ ] `PassphraseAuthPolicy` uses `CryptographicOperations.FixedTimeEquals` — confirmed by code inspection.
- [ ] Unit test added or updated for `PassphraseAuthPolicy` covering the constant-time comparison path.

### SEC-003
- [ ] No call to `innerHTML` in `settings.js` receives a value derived from server data (confirmed by code inspection and grep).
- [ ] Opening Settings → Frequencies with a description containing `<img src=x onerror=alert(1)>` stored in the frequency list does **not** trigger the alert — the literal text is displayed as plain text in the input field.
- [ ] Existing frequency CRUD functionality (add, edit, delete) is unaffected.

---

## References

- Security review: 2026-06-24 (this conversation)
- Related LAN auth work: `dev-tasks/2026-06-23-lan-browser-auth.md`, `dev-tasks/2026-06-24-d-lan-004-static-asset-auth.md`
- `PassphraseAuthPolicy.cs`, `NullAuthPolicy.cs`, `Program.cs` (DI registration block)
- `web/js/settings.js` (`appendFreqRow` function)
- `web/login.html`, `web/js/ws.js`, `web/js/api.js`
