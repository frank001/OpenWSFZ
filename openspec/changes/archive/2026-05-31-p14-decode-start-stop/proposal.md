## Why

FR-017 (decode start/stop control) was added to REQUIREMENTS.md in v1.2 and has never been implemented. The FT8 pipeline starts unconditionally on launch whenever an audio device is configured — there is no way for the operator to pause decoding without clearing the device selection or restarting the process. This violates a Must Have requirement and must be addressed before further UI or pipeline work proceeds.

## What Changes

- **`AppConfig`** — Add `bool DecodingEnabled` (default: `true`) persisted to the config file.
- **`Program.cs`** — On startup, only call `StartPipeline()` if `DecodingEnabled` is `true`; extend the config-change handler to start or stop the pipeline when `DecodingEnabled` changes.
- **New API endpoints** — `POST /api/v1/decode/start` and `POST /api/v1/decode/stop` set `DecodingEnabled` and trigger the pipeline transition, returning the updated `DaemonStatus`.
- **`DaemonStatus`** — Add `bool DecodingEnabled` so the UI and API consumers can reflect the authoritative state.
- **WebSocket `status` event** — Include `DecodingEnabled` in the initial status payload pushed to each connecting client.
- **`index.html`** — Add a start/stop button in the status bar and a decoding-state badge (e.g. "Decoding" / "Stopped") in the status area.
- **`main.js`** — Handle `DecodingEnabled` from the `status` event; wire the button to call the appropriate API endpoint and update the badge optimistically.

## Capabilities

### New Capabilities

- `decode-control`: Operator-facing pipeline start/stop control — API endpoints, `AppConfig.DecodingEnabled` field, startup gate, and config-change handler reaction.

### Modified Capabilities

- `web-frontend`: New start/stop toggle button and decoding-state badge in the status bar (UI visibility rule: visible because the backend is implemented in this same change).

## Impact

- `src/OpenWSFZ.Abstractions/AppConfig.cs` — new `DecodingEnabled` field
- `src/OpenWSFZ.Web/DaemonStatus.cs` — new `DecodingEnabled` field
- `src/OpenWSFZ.Web/WebApp.cs` — two new API endpoints; `DaemonStatus` construction updated
- `src/OpenWSFZ.Daemon/Program.cs` — startup gate; config-change handler extended
- `web/index.html` — start/stop button + badge
- `web/js/main.js` — event handling and button wiring
