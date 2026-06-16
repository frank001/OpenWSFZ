## Why

The callsign, grid locator, watchdog timer, and retry count currently live in the "FT8 auto-answer (TX)" fieldset on the Radio tab. These are station-identity and behaviour settings that will apply to every future TX mode (caller role, manual CQ, etc.) — not just the auto-answerer. Burying them in a radio-hardware tab alongside audio device selectors and CAT port settings makes them hard to find and implies a scope they do not have. A dedicated General tab gives operator-identity settings a permanent, logical home that will not need to move again as TX capabilities expand.

## What Changes

- **New tab** — A "General" tab is added to `settings.html` as the first tab, containing: callsign, Maidenhead grid, watchdog timer (minutes), and retry count.
- **TX fieldset reduced** — The "FT8 auto-answer (TX)" fieldset on the Radio tab retains only the auto-answer enable/disable checkbox. The four fields listed above are removed from it.
- **No backend changes** — The `AppConfig`/`TxConfig` schema, REST API, and all daemon code are unchanged. This is a pure UI restructuring.

## Capabilities

### New Capabilities

- None. No new spec file is created.

### Modified Capabilities

- `web-frontend`: The Settings page gains a General tab; the TX fieldset on the Radio tab is reduced to the auto-answer toggle only. Spec updated to document the General tab and its fields.

## Impact

- **`web/settings.html`** — New tab button and panel for General; TX fieldset stripped back.
- **`web/js/settings.js`** — `loadConfig()` and `saveConfig()` updated to read/write callsign, grid, watchdog, and retry count from their new element IDs on the General tab; dirty-state snapshot updated accordingly.
- **`openspec/specs/web-frontend/spec.md`** — New requirement block for the General tab; TX fieldset requirement amended.
- No changes to any `.cs` files, tests, or configuration schema.
