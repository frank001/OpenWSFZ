## Context

The FT8 pipeline starts unconditionally on application launch whenever `AppConfig.AudioDeviceId` is set. There is no mechanism for the operator to pause decoding. FR-017 requires a toggle control in the UI, persistence of the stopped/running state across sessions, and that the pipeline respects the state at startup.

The existing config-change handler in `Program.cs` already restarts the pipeline when the device changes (lines 258–276). This is the natural extension point for responding to `DecodingEnabled` changes. The `POST /api/v1/config` endpoint already persists arbitrary config fields — the new `DecodingEnabled` field will flow through it automatically. Two dedicated toggle endpoints (`/decode/start`, `/decode/stop`) provide an explicit, discoverable API surface without requiring the caller to know or preserve the full config document.

## Goals / Non-Goals

**Goals:**

- `AppConfig.DecodingEnabled` persisted to the config file; defaults to `true` (no behaviour change on first run)
- Startup gate: `Program.cs` only calls `StartPipeline()` when `DecodingEnabled && AudioDeviceId != null`
- Config-change handler reacts to `DecodingEnabled` transitions: `false → true` starts; `true → false` stops
- `POST /api/v1/decode/start` and `POST /api/v1/decode/stop` set the flag, persist it, and trigger the pipeline transition; both return the updated `DaemonStatus`
- `DaemonStatus` carries `bool DecodingEnabled` so the UI has a reliable source of truth
- WebSocket `status` event includes `DecodingEnabled` in its initial payload
- `index.html`: start/stop toggle button + decoding-state badge in the status bar
- `main.js`: button wired to the API; badge updated from `status`/heartbeat events

**Non-Goals:**

- Pause/resume mid-cycle (decoding is always a full cycle or not at all)
- Per-frequency or per-device enable/disable
- WebSocket push notification when `DecodingEnabled` changes (polling via heartbeat is sufficient for v1)

## Decisions

### D1 — Dedicated `/decode/start` and `/decode/stop` endpoints rather than a raw config POST

**Decision:** Add `POST /api/v1/decode/start` and `POST /api/v1/decode/stop` in addition to the existing `POST /api/v1/config`.

**Rationale:** The UI needs a simple, intent-revealing call. A raw `POST /api/v1/config` requires the caller to read the current config, mutate `DecodingEnabled`, and POST the full object — fragile if the config shape evolves. Dedicated endpoints are one-shot with no request body. They still persist by calling `store.SaveAsync` internally, so the config file stays authoritative.

**Alternative rejected:** Expose only the raw config POST and let the UI construct the full payload. Acceptable but adds coupling between the UI and the config schema.

---

### D2 — `DecodingEnabled` lives in `AppConfig`, not as volatile daemon state

**Decision:** The decode state is part of `AppConfig` and is persisted to the config file on every change.

**Rationale:** FR-017 explicitly requires that "a session explicitly stopped by the operator does not auto-resume on the next application launch." This mandates persistence. Using `AppConfig` as the single source of truth avoids a second state store and keeps the startup logic simple: read config, check flag, decide whether to start.

**Alternative rejected:** A separate in-memory flag set by the API but not persisted. This would not satisfy the FR-017 requirement about persisted state.

---

### D3 — Config-change handler in `Program.cs` reacts to `DecodingEnabled` transitions

**Decision:** Extend the existing `store.OnSaved` callback (which already handles device-change pipeline restarts) to also handle `DecodingEnabled` transitions.

**Rationale:** The callback already has access to `StartPipeline` and `RestartPipelineAsync`. Adding `DecodingEnabled` handling here keeps all pipeline lifecycle logic in one place and avoids duplicating it in the new API endpoints.

**Implementation note:** The endpoints call `store.SaveAsync` first, then the `OnSaved` callback fires and performs the pipeline transition. This keeps the endpoints thin: they set state, they do not directly call `StartPipeline`/`StopFramerAsync`.

---

### D4 — `DaemonStatus.DecodingEnabled` reflects the persisted config value

**Decision:** `DecodingEnabled` in `DaemonStatus` is read from `store.Current.DecodingEnabled`.

**Rationale:** The config is the authoritative source; there is no separate runtime flag to keep in sync. A client connecting via WebSocket receives the current config state in the `status` push, and all subsequent heartbeats carry `DecodingEnabled` via the updated `DaemonStatus` shape. No additional push event is required.

---

### D5 — UI toggle is a `<button>` in the status bar, not a checkbox

**Decision:** A single `<button id="decode-toggle">` element that reads "Stop" when decoding is active and "Start" when stopped. A `<span id="decode-badge">` shows "Decoding" or "Stopped" as an adjacent state badge.

**Rationale:** A button has clear affordance for a side-effect action (start/stop a live process). A checkbox implies a preference setting, which belongs on the Settings page. The badge provides persistent visual state without requiring the button label alone to convey it.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Race: operator clicks Stop while a decode cycle is mid-flight | `StopFramerAsync` drains the framer output channel before stopping capture; an in-flight `DecodeAsync` will complete naturally. No partial-result risk. |
| `DecodingEnabled = true` but `AudioDeviceId = null` | The startup gate already guards `AudioDeviceId != null`. The `/decode/start` endpoint must check the same condition and return `400 Bad Request` with a clear message if no device is configured. |
| `OnSaved` fires for non-DecodingEnabled config changes (e.g. device name edit) | The handler already checks `newDevice != runningDevice`; add an analogous `newEnabled != runningEnabled` check as a separate conditional, not nested, to avoid interfering with device-change logic. |
| `SetDllImportResolver` note: unrelated to this change | n/a |

## Migration Plan

1. Add `DecodingEnabled = true` to `AppConfig` — existing config files without the field deserialise to `true`, preserving current behaviour.
2. Update `DaemonStatus`, `WebApp.cs`, `Program.cs` — no breaking changes to existing API contracts (only additive).
3. Update `web/index.html` and `web/js/main.js` — purely additive UI changes.
4. No database migration; no deploy coordination required.

## Open Questions

*(none)*
