# DEV TASK — R5-SEC-F4: WebSocket auth — loop ReceiveAsync until EndOfMessage

**Date:** 2026-07-02
**QA defect ID:** R5-SEC-F4
**Severity:** Low — safe failure mode (fragmented frame is rejected, not accepted)
**OpenSpec change:** `lan-remote-access`

---

## 1. Context

`WebSocketHub.AuthenticateViaFrameAsync` (`src/OpenWSFZ.Web/WebSocketHub.cs`, line 77)
handles the non-loopback WebSocket authentication handshake introduced by SEC-002B.
A non-loopback client must send a JSON auth frame as its first WebSocket message:
`{"type":"auth","key":"<passphrase>"}`.

The current implementation calls `ws.ReceiveAsync` exactly once and then checks
`result.EndOfMessage` only in the sense of reading `result.Count` bytes from the buffer.
If a WebSocket client fragments the auth message across two or more frames
(`EndOfMessage = false` on the first frame), the current code:

1. Reads the first fragment (partial JSON) into `buffer`.
2. Attempts to deserialise `buffer[0..result.Count]` — which is incomplete JSON.
3. `JsonSerializer.Deserialize` returns `null` (or throws `JsonException`).
4. `frame is null` → closes the socket with code 4001 ("Authentication required").

**This is a safe failure mode** — the connection is rejected, not granted. However, the
error message ("Authentication required") is misleading; the client sent a structurally
valid auth frame, just fragmented. Real-world WebSocket clients that the product is
tested with do not fragment short frames, so this is currently theoretical.

The fix is to loop `ReceiveAsync` until `result.EndOfMessage == true`, accumulating
bytes in a `MemoryStream`, then deserialise from the accumulated buffer. The existing
`Task.WhenAny`-based timeout must be preserved across all loop iterations (cancelling
`ReceiveAsync` via a `CancellationToken` causes `ManagedWebSocket` to call `Abort()`,
dropping the TCP connection without a clean WS close frame — the client cannot inspect
close code 4001).

---

## 2. Branch name

```
fix/r5-sec-f4-ws-frame-loop
```

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Web/WebSocketHub.cs`

Replace the body of `AuthenticateViaFrameAsync` from the `var buffer` declaration
through the `result = await receiveTask;` block (lines 89–128) with the looping
implementation below. The code from line 117 onwards (MessageType check, JSON
deserialise, auth policy call) is replaced wholesale; the simplest approach is to
replace the entire method body.

**Complete replacement for the method body** (preserve the existing method signature
and XML-doc comment unchanged):

```csharp
internal static async Task<bool> AuthenticateViaFrameAsync(
    WebSocket ws, IAuthPolicy authPolicy, CancellationToken ct)
{
    const WebSocketCloseStatus InvalidAuth    = (WebSocketCloseStatus)4001;
    const int  AuthTimeoutMs                 = 5_000;
    const int  MaxAuthFrameBytes             = 4_096; // guard against oversized frames

    // timeoutTask is created once and reused across all loop iterations so that the
    // 5-second budget is shared, not reset per fragment.
    var timeoutTask = Task.Delay(AuthTimeoutMs, ct);

    // Use Task.WhenAny rather than a linked CancellationToken for the timeout.
    // Cancelling a ReceiveAsync via CT causes ManagedWebSocket to call Abort(),
    // dropping the TCP connection without a WS close frame.  Keeping the socket
    // Open while the delay fires lets us call CloseAsync(4001, …) cleanly.
    var buffer = new byte[512];
    using var ms = new System.IO.MemoryStream(capacity: 128);
    bool firstFragment = true;

    WebSocketReceiveResult result;
    do
    {
        var receiveTask = ws.ReceiveAsync(new ArraySegment<byte>(buffer), ct);

        if (await Task.WhenAny(receiveTask, timeoutTask) == timeoutTask)
        {
            await TryCloseAsync(ws, InvalidAuth, "Authentication timeout", ct);
            return false;
        }

        try
        {
            result = await receiveTask;
        }
        catch (WebSocketException)
        {
            // Connection dropped before auth frame arrived.
            return false;
        }
        catch (OperationCanceledException)
        {
            // Server shutdown.
            return false;
        }

        // Only the first fragment carries the message type (subsequent fragments
        // arrive with MessageType.Continuation).
        if (firstFragment && result.MessageType != WebSocketMessageType.Text)
        {
            await TryCloseAsync(ws, InvalidAuth, "Authentication required", ct);
            return false;
        }
        firstFragment = false;

        // Size guard: reject oversized frames before accumulating bytes.
        if (ms.Length + result.Count > MaxAuthFrameBytes)
        {
            await TryCloseAsync(ws, InvalidAuth, "Authentication required", ct);
            return false;
        }

        ms.Write(buffer, 0, result.Count);
    } while (!result.EndOfMessage);

    WsAuthFrame? frame;
    try
    {
        frame = JsonSerializer.Deserialize(
            ms.ToArray().AsSpan(),
            AppJsonContext.Default.WsAuthFrame);
    }
    catch (JsonException)
    {
        frame = null;
    }

    if (frame is null ||
        !string.Equals(frame.Type, "auth", StringComparison.Ordinal) ||
        string.IsNullOrEmpty(frame.Key))
    {
        await TryCloseAsync(ws, InvalidAuth, "Authentication required", ct);
        return false;
    }

    // Validate the key using the active auth policy.
    // Pass remoteIp = null so the loopback bypass is not triggered —
    // the call site already confirmed the connection is non-loopback.
    if (!authPolicy.IsAuthorized(remoteIp: null, apiKeyHeader: frame.Key, keyQueryParam: null))
    {
        await TryCloseAsync(ws, InvalidAuth, "Authentication failed", ct);
        return false;
    }

    return true;
}
```

No other production files need to change.

### 3.2 — `tests/OpenWSFZ.Web.Tests/` — add fragmentation test

Add a new test class `WebSocketHubAuthTests.cs` (or add to an existing auth test file if
one exists). `WebSocketHub.AuthenticateViaFrameAsync` is `internal static` and
`InternalsVisibleTo` is already configured for `OpenWSFZ.Web.Tests`.

Use a `FakeWebSocket` — a test double that extends `System.Net.WebSockets.WebSocket`
(abstract) and replays a pre-configured sequence of `WebSocketReceiveResult` values.

**Required test cases:**

| Test name | Scenario | Expected result |
|---|---|---|
| `Auth_SingleFrame_ValidKey_ReturnsTrue` | Single frame, `EndOfMessage=true`, valid JSON key | `true` |
| `Auth_Fragmented_TwoFrames_ValidKey_ReturnsTrue` | Two frames split at mid-JSON, `EndOfMessage=false` then `true`, reassembled JSON is valid | `true` |
| `Auth_Fragmented_TwoFrames_WrongKey_ReturnsFalse` | Two frames, reassembled key is wrong | `false`, socket closed with 4001 |
| `Auth_SingleFrame_OversizedFrame_ReturnsFalse` | Single frame with `Count` > 4096 bytes | `false`, socket closed with 4001 |
| `Auth_SingleFrame_InvalidJson_ReturnsFalse` | Single frame, `EndOfMessage=true`, malformed JSON | `false`, socket closed with 4001 |
| `Auth_BinaryFrame_ReturnsFalse` | Single frame with `MessageType = Binary` | `false`, socket closed with 4001 |

For the `FakeWebSocket`, implement only `ReceiveAsync` and `CloseAsync`; throw
`NotImplementedException` for all other abstract members. Track the close code and
description in fields so assertions can verify them.

Use `NullAuthPolicy` for the `true`-expected cases and `PassphraseAuthPolicy("secret")`
with `frame.Key = "secret"` for the key-match case. The `ct` parameter can be
`CancellationToken.None` for all unit tests.

---

## 4. Acceptance criteria

The QA engineer will verify the following before approving merge:

- [ ] **AC-1** All six new tests pass (`dotnet test OpenWSFZ.slnx -c Release`).
- [ ] **AC-2** A fragmented two-frame auth message where the reassembled JSON is
  `{"type":"auth","key":"secret"}` authenticates successfully (test
  `Auth_Fragmented_TwoFrames_ValidKey_ReturnsTrue`).
- [ ] **AC-3** A single well-formed auth frame continues to authenticate successfully
  (non-regression).
- [ ] **AC-4** An oversized frame (> 4 096 bytes) is rejected with close code 4001.
- [ ] **AC-5** The existing integration tests for `PassphraseAuthPolicy` (8.2, 8.3,
  8.4 in `lan-remote-access/tasks.md`) remain green — non-loopback WS auth via
  `?key=<passphrase>` is NOT affected by this change (that code path uses the query
  parameter, not the auth frame; confirm by re-running the full suite).
- [ ] **AC-6** Build: 0 errors, 0 warnings.
- [ ] **AC-7** `using var ms` is used to ensure the `MemoryStream` is disposed even
  on early-return paths.

---

## 5. References

- `src/OpenWSFZ.Web/WebSocketHub.cs` lines 77–153 — `AuthenticateViaFrameAsync` full body
- `src/OpenWSFZ.Web/OpenWSFZ.Web.csproj` line 28 — `InternalsVisibleTo`
  (`OpenWSFZ.Web.Tests` already configured)
- `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs` line 50 — cross-reference to auth-frame
  comment (update to mention EndOfMessage loop if the comment references the old design)
- OpenSpec change: `openspec/changes/lan-remote-access/`
- R5-SEC review finding F4 in MEMORY.md
