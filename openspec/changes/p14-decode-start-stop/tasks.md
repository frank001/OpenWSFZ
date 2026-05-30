## 1. AppConfig and DaemonStatus

- [x] 1.1 Open `src/OpenWSFZ.Abstractions/AppConfig.cs`. Add `bool DecodingEnabled = true` as a named parameter to the `AppConfig` record, after `ShowCycleCountdown`. The default of `true` ensures existing config files without the field deserialise correctly (System.Text.Json uses the default value for missing properties).
- [x] 1.2 Open `src/OpenWSFZ.Web/DaemonStatus.cs`. Add `bool DecodingEnabled = false` as a named parameter to the `DaemonStatus` record.
- [x] 1.3 Verify `dotnet build -c Release` — 0 errors, 0 warnings. Fix any callers of `DaemonStatus` that now require the new field.

## 2. API Endpoints — WebApp.cs

- [x] 2.1 Open `src/OpenWSFZ.Web/WebApp.cs`. Locate `GET /api/v1/status` (around line 131). Add `DecodingEnabled: store.Current.DecodingEnabled` to the `DaemonStatus(…)` constructor call.
- [x] 2.2 Add `POST /api/v1/decode/start` endpoint in `WebApp.cs`. The endpoint SHALL:
      - Check `store.Current.AudioDeviceId`; if null, return `Results.BadRequest("No audio device configured. Select a device in Settings before starting decoding.")`
      - Set `DecodingEnabled = true`: call `await store.SaveAsync(store.Current with { DecodingEnabled = true }, ct)`
      - Return `TypedResults.Ok(new DaemonStatus(…))` reflecting the updated state (the `OnSaved` callback in `Program.cs` will trigger the pipeline start)
- [x] 2.3 Add `POST /api/v1/decode/stop` endpoint in `WebApp.cs`. The endpoint SHALL:
      - Call `await store.SaveAsync(store.Current with { DecodingEnabled = false }, ct)`
      - Return `TypedResults.Ok(new DaemonStatus(…))` reflecting the updated state
- [x] 2.4 `dotnet build -c Release` — 0 errors, 0 warnings.

## 3. Program.cs — Startup Gate and Config-Change Handler

- [x] 3.1 Open `src/OpenWSFZ.Daemon/Program.cs`. Locate the `ApplicationStarted` callback (around line 220). Change the pipeline start condition from `if (deviceName is not null)` to `if (deviceName is not null && configStore.Current.DecodingEnabled)`.
- [x] 3.2 Locate the `store.OnSaved` / config-change callback (around line 258). After the existing `newDevice != runningDevice` block, add a `DecodingEnabled` transition block:
      - Introduce a `bool runningEnabled` variable (initialised from `configStore.Current.DecodingEnabled` at the start, alongside `runningDevice`)
      - If `newConfig.DecodingEnabled && !runningEnabled && newDevice is not null`: call `StartPipeline(newDevice)` and set `runningEnabled = true`
      - If `!newConfig.DecodingEnabled && runningEnabled`: call `await StopFramerAsync(); await captureManager.StopAsync()` and set `runningEnabled = false`
      - Update `runningEnabled = newConfig.DecodingEnabled` at the end of the handler
- [x] 3.3 `dotnet build -c Release` — 0 errors, 0 warnings.
- [ ] 3.4 Manual smoke-test: launch the daemon, confirm it starts normally. Call `POST /api/v1/decode/stop`, confirm `IsCapturing` goes false. Call `POST /api/v1/decode/start`, confirm pipeline resumes.

## 4. Web Frontend — index.html

- [x] 4.1 Open `web/index.html`. In `<header id="status-bar">`, add the following two elements after the `#audio-indicator` span and before `#cycle-timer`:

      ```html
      <span id="decode-badge" class="decoding-active" title="FT8 decode pipeline state">Decoding</span>

      <button id="decode-toggle" type="button" title="Start or stop the FT8 decode pipeline">Stop Decoding</button>
      ```

- [x] 4.2 Open `web/css/app.css`. Add styles for:
      - `#decode-badge.decoding-active` — visually distinct (e.g. green or accent colour, matching the existing audio-active style pattern)
      - `#decode-badge.decoding-stopped` — muted/neutral style
      - `#decode-toggle` — consistent with the existing status-bar element sizing; no heavy styling required

## 5. Web Frontend — main.js

- [x] 5.1 Open `web/js/main.js`. Add a module-level variable `let decodingEnabled = true;` near the other state variables.
- [x] 5.2 Add element references near the top of the main function (after existing `document.getElementById` calls):
      ```js
      const decodeBadgeEl  = document.getElementById('decode-badge');
      const decodeToggleEl = document.getElementById('decode-toggle');
      ```
- [x] 5.3 Implement `setDecodingState(enabled, hasDevice)`:
      - Updates `decodingEnabled`
      - Sets `decodeBadgeEl.textContent` and `className` (`decoding-active` / `decoding-stopped`)
      - Sets `decodeToggleEl.textContent` (`"Stop Decoding"` / `"Start Decoding"` / `"No device"`)
      - Sets `decodeToggleEl.disabled` (`true` when `!hasDevice`)
- [x] 5.4 In the `status` event handler (the block that reads `audioDevice` and `audioActive`), extract `decodingEnabled` from the payload and call `setDecodingState(payload.decodingEnabled ?? true, !!payload.audioDevice)`.
- [x] 5.5 Wire `decodeToggleEl` click handler:
      - Determine the target endpoint: `/api/v1/decode/stop` if `decodingEnabled`, else `/api/v1/decode/start`
      - Disable the button during the fetch (prevent double-click)
      - On `fetch(endpoint, { method: 'POST' })` success (HTTP 200): parse the `DaemonStatus` JSON; call `setDecodingState(data.decodingEnabled, !!data.audioDevice)`
      - On error (non-200 or network failure): re-enable the button; optionally log to console
- [x] 5.6 `dotnet build -c Release` — 0 errors, 0 warnings (confirms the web files are copied and referenced correctly).

## 6. Tests

- [x] 6.1 Open `tests/OpenWSFZ.Web.Tests/`. Add a test class `DecodeControlEndpointTests` with the following tests (use existing `WebApplicationFactory` / `AppFactory` patterns from the existing test files):
      - `PostDecodeStop_ReturnsOk_AndSetsDecodingEnabledFalse` — POST `/api/v1/decode/stop`, assert 200, assert `DaemonStatus.DecodingEnabled == false`
      - `PostDecodeStart_WithNoDevice_ReturnsBadRequest` — POST `/api/v1/decode/start` with `AudioDeviceId = null` in config, assert 400
      - `PostDecodeStart_WithDevice_ReturnsOk_AndSetsDecodingEnabledTrue` — set config with a device ID + `DecodingEnabled = false`, POST `/api/v1/decode/start`, assert 200, assert `DaemonStatus.DecodingEnabled == true`
      - `GetStatus_ReflectsDecodingEnabled` — save config with `DecodingEnabled = false`, GET `/api/v1/status`, assert `DecodingEnabled == false` in response
- [x] 6.2 `dotnet test tests/OpenWSFZ.Web.Tests -c Release` — all new tests pass, no regressions.
- [x] 6.3 `dotnet test -c Release` (full suite) — 0 failures.

## 7. Traceability and Gates

- [x] 7.1 `dotnet run --project tools/TraceabilityCheck` — G3 green. If FR-017 appears as unmapped, add a `FR-017: DecodeControlEndpointTests` mapping comment to the new test class.
- [x] 7.2 `dotnet run --project tools/LicenseInventoryCheck` — G5 green.
- [x] 7.3 Commit all changes on branch `feat/p14-decode-start-stop`. Open PR to `main`. Confirm CI green on all three matrix legs.
- [ ] 7.4 CAPTAIN: review and approve.
- [ ] 7.5 Merge PR; archive this change (`opsx:archive p14-decode-start-stop`).
