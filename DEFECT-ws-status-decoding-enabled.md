# Defect: WebSocket `status` Event Omits `DecodingEnabled` — GUI Misreports State on Restart

**Raised by:** QA  
**Severity:** High — GUI systematically lies about application state after restart  
**Requirement violated:** FR-017 — *"The GUI must reflect the actual pipeline state at all times."*  
**Affects:** `src/OpenWSFZ.Web/WebSocketHub.cs`, `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs`

---

## What is Wrong

When the application is stopped while decoding is active (`DecodingEnabled = true` is persisted in config), and then restarted, two contradictory things happen simultaneously:

1. **The backend pipeline starts correctly.** `Program.cs` lines 247–249 read `configStore.Current.DecodingEnabled` and call `StartPipeline(deviceName)` when it is `true`. The pipeline is running.

2. **The GUI shows STOPPED.** The WebSocket `status` event — the mechanism by which the frontend learns the initial application state — is constructed in `WebSocketHub.HandleAsync` **without the `DecodingEnabled` field**. Because `DaemonStatus` declares `DecodingEnabled = false` as a default parameter, the serialised payload always contains `"decodingEnabled": false` regardless of what is persisted.

The frontend (`main.js` line 264) reads this field and calls `setDecodingState(false, ...)`, which renders the badge as "Stopped" and the button as "Start Decoding" — while the backend is actively decoding.

---

## Location of the Defect

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`  
**Method:** `HandleAsync` (the initial status event construction block)

The faulty construction is approximately lines 136–147:

```csharp
var status = new DaemonStatus(
    State:               "Running",
    Version:             AssemblyVersion.Get(),
    AudioDevice:         configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
    CaptureActive:       captureManager?.IsCapturing ?? false,
    AudioActive:         captureManager?.IsCapturing ?? false,
    DialFrequencyMHz:    effectiveFreq,
    CatConnectionStatus: catState?.Status.ToString() ?? "Disabled");
//  ^^^ DecodingEnabled is absent — defaults to false
```

**Compare with** `WebApp.cs` — the `GET /api/v1/status` REST endpoint, which correctly reads the persisted value:

```csharp
return TypedResults.Ok(new DaemonStatus(
    ...
    DecodingEnabled: store.Current.DecodingEnabled,   // ← present and correct
    ...));
```

The WebSocket initial status path was simply never given the same treatment.

---

## Required Fix

### 1 — `src/OpenWSFZ.Web/WebSocketHub.cs`

Add `DecodingEnabled: configStore.Current.DecodingEnabled` to the `DaemonStatus` constructor inside `HandleAsync`.

The corrected construction should be:

```csharp
var status = new DaemonStatus(
    State:               "Running",
    Version:             AssemblyVersion.Get(),
    AudioDevice:         configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
    CaptureActive:       captureManager?.IsCapturing ?? false,
    AudioActive:         captureManager?.IsCapturing ?? false,
    DecodingEnabled:     configStore.Current.DecodingEnabled,   // ← add this line
    DialFrequencyMHz:    effectiveFreq,
    CatConnectionStatus: catState?.Status.ToString() ?? "Disabled");
```

### 2 — `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs`

Add a regression test to the `AudioConfigIntegrationTests` class (which already has access to the controllable `TestConfigStore` via `AudioConfigFixture`). The test must:

1. Save an `AppConfig` with `DecodingEnabled = true` to `_fixture.ConfigStore` before connecting.
2. Connect a `ClientWebSocket` to `/api/v1/ws`.
3. Read the initial `status` frame.
4. Assert that `payload.decodingEnabled` is `true`.

The test covers the exact regression path: a persisted `DecodingEnabled = true` must be visible in the WebSocket `status` event, not silently masked by the record default.

A suggested display name: `"FR-017: WebSocket status event reflects DecodingEnabled = true from config store"`.

---

## Why This Was Not Caught

No existing test exercises the `decodingEnabled` field of the WebSocket `status` payload. The existing `WebSocketTests` verify `state`, `version`, and `audioActive` in the initial status frame, but not `decodingEnabled`. The `DecodeControlEndpointTests` verify the REST endpoints (`GET /api/v1/status`, `POST /api/v1/decode/start`, `POST /api/v1/decode/stop`) — none of which exercise the WebSocket path.

The regression test in item 2 above closes this gap directly.

---

## Acceptance Criteria

- [ ] `WebSocketHub.HandleAsync` includes `DecodingEnabled: configStore.Current.DecodingEnabled` in the initial status payload.
- [ ] A regression test is added that connects via WebSocket with `DecodingEnabled = true` pre-seeded in the config store and asserts the status event carries `decodingEnabled: true`.
- [ ] All existing tests remain green.
- [ ] Manual verification: start the daemon with `DecodingEnabled = true` in the persisted config; open the UI; the badge must show "Decoding" and the button must show "Stop Decoding" on first connect, without any user interaction.
