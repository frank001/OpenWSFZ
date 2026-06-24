# QA Review R1 — fix/security-lan-hardening required fixes

**Date:** 2026-06-24
**Raised by:** QA engineer (review R1)
**Branch:** `fix/security-lan-hardening` (continue on same branch — do NOT open a new branch)
**Verdict:** RETURNED — two blocking defects, three non-blocking observations.

---

## Context

The security implementation is largely correct. SEC-001 (startup guard), SEC-002A
(constant-time comparison), and SEC-003 (DOM construction XSS fix) are all sound and
well-tested. The two blocking defects are both in the middleware wiring for SEC-002B
(WebSocket auth-frame protocol).

---

## BLOCKING — F1: `Upgrade: websocket` header bypasses auth for all REST endpoints

**File:** `src/OpenWSFZ.Web/WebApp.cs` ~line 163

The `isWebSocketUpgrade` bypass fires before the credential check and is path-agnostic.
Any LAN client that sends any REST request with `Upgrade: websocket` in the header
reaches the route handler unauthenticated:

```bash
curl -H "Upgrade: websocket" http://192.168.1.x:8080/api/v1/config
# → 200 OK — full config including passphrase, callsign, serial port
```

`AuthenticateViaFrameAsync` is only wired into the `/api/v1/ws` handler. Every other
endpoint (config, status, TX control, frequencies) has no independent auth gate. ASP.NET
Core does not block a non-WS request from reaching a REST handler just because it carries
an `Upgrade` header.

### Required fix

Add a path scope to the bypass condition:

```csharp
bool isWebSocketUpgrade =
    ctx.Request.Path.StartsWithSegments("/api/v1/ws") &&
    ctx.Request.Headers.TryGetValue("Upgrade", out var upgradeValues) &&
    upgradeValues.ToString().Equals("websocket", StringComparison.OrdinalIgnoreCase);
```

### Acceptance criteria

- [ ] `GET /api/v1/config` with header `Upgrade: websocket` from a non-loopback origin
  returns 401, not 200. (Verify by unit test or integration test.)
- [ ] `GET /api/v1/ws` upgrade from a non-loopback origin still proceeds to the WS
  handler (existing tests 8.10a/b/c continue to pass).

---

## BLOCKING — F2: `?key=` query-parameter path is unreachable for non-loopback WS clients

**Files:** `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs` ~line 47,
`src/OpenWSFZ.Web/WebSocketHub.cs` ~line 146

`PassphraseAuthPolicy.cs` line 47 says:
> "`?key=` is kept for non-browser clients that cannot set an initial auth frame."

This is incorrect. The path is dead:

1. The middleware bypass (`isWebSocketUpgrade → next(ctx)`) fires before `keyQueryParam`
   is extracted from the request — `IsAuthorized` is never called with the query param.
2. `AuthenticateViaFrameAsync` calls
   `IsAuthorized(remoteIp: null, apiKeyHeader: frame.Key, keyQueryParam: null)` —
   `keyQueryParam` is hardcoded `null`.
3. `ConstantTimeEquals(null, _passphrase)` returns `false` immediately.

A non-browser WS client using `ws://host/api/v1/ws?key=correct` waits 5 seconds and
receives close 4001 — no auth frame was sent.

### Required fix (choose one — developer's discretion)

**Option A — Remove the false claim (simpler):**
- Delete or correct the comment on `PassphraseAuthPolicy.cs` line 47. Replace with a note
  that non-browser WS clients must use the JSON auth-frame protocol
  (`{"type":"auth","key":"..."}`) as their first message.
- No functional code change required.

**Option B — Restore backward compatibility (preserves the original intent):**
- In `AuthenticateViaFrameAsync`, accept a valid `?key=` query-parameter as an
  alternative to the auth frame. The HTTP context (or the query string) must be passed
  into the method so it can extract `ctx.Request.Query["key"]`.
- Both paths (frame key and query-param key) must be validated with
  `authPolicy.IsAuthorized`.

Option A is strongly preferred given that LAN mode is new and there are no known
non-browser WS clients to break.

### Acceptance criteria

- [ ] (Option A) The comment on `PassphraseAuthPolicy.cs` accurately describes the
  actual behaviour: `?key=` works for REST calls via the HTTP auth middleware; WS
  connections from non-loopback origins must use the auth-frame protocol.
- [ ] (Option B) A non-browser WS client connecting with `?key=correct` in the URL
  is authenticated successfully from a non-loopback origin. Add a test.

---

## Non-blocking — F3: `null RemoteIpAddress` silently skips WS frame auth

**File:** `src/OpenWSFZ.Web/WebApp.cs` ~line 758

```csharp
if (remoteIp is not null && !IPAddress.IsLoopback(remoteIp))
```

When `RemoteIpAddress` is `null`, this condition is `false` and the auth frame gate is
skipped. Under current direct-Kestrel deployment this is unreachable in production, so
this is non-blocking. Consider flipping the null treatment to require auth:
`if (remoteIp is null || !IPAddress.IsLoopback(remoteIp))`, or add a comment explaining
the intentional trust decision. Defer to a future change if preferred.

---

## Non-blocking — F4: Auth frame rejected for fragmented WebSocket messages

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs` ~line 89

`ReceiveAsync` is called once with a 512-byte buffer; `result.EndOfMessage` is not
checked. A client whose TCP stack fragments the auth JSON across two frames has its first
fragment deserialised — the `JsonException` closes the socket with 4001. Unlikely in
practice for small auth payloads, but inconsistent with the `HandleAsync` loop pattern
elsewhere in `WebSocketHub`. Defer to a future change if preferred.

---

## Non-blocking — F5: REQUIREMENTS.md version history out of order

**File:** `REQUIREMENTS.md` changelog table

Row `1.25` (2026-06-24) is inserted before row `1.24` (2026-06-14). The table reads
`…1.23, 1.25, 1.24`. Please move row `1.25` to after `1.24`.

---

## References

- Security review: 2026-06-24 (this conversation)
- Handoff for original implementation: `dev-tasks/2026-06-24-security-lan-hardening.md`
- Acceptance criteria for SEC-001/002/003: `dev-tasks/2026-06-24-security-lan-hardening.md`
