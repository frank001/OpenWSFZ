## Why

The backend is fully operational — the daemon serves static files from `web/`, exposes REST endpoints for audio device enumeration and config persistence, and pushes live status over WebSocket. What the operator actually sees in their browser is still a bare placeholder. P3 replaces that placeholder with a real, usable UI that satisfies all remaining frontend requirements (FR-008–FR-016) and makes OpenWSFZ feel like a genuine application.

## What Changes

- Create the `web/` top-level directory with conventional `css/`, `js/` subfolders and a root `index.html`.
- Implement a **main page** (`index.html`) with:
  - Dark default theme (CSS custom properties for easy theming).
  - A waterfall/spectrogram panel area — Phase 3 renders a placeholder canvas; real audio data arrives in Phase 5 (FT8 decoder).
  - A decoded-messages list panel — Phase 3 renders an empty list with correct structure; messages arrive in Phase 5.
  - A status bar showing connection state and the active audio device name.
  - Navigation affordance to the Settings page.
- Implement a **Settings page** (`settings.html`) with:
  - Audio device selector populated live from `GET /api/v1/audio/devices`.
  - Port number field pre-filled from `GET /api/v1/config`.
  - Save button that `POST`s to `/api/v1/config` and shows success/error feedback.
  - Navigation back to the main page.
- Implement a **WebSocket client** (`js/ws.js`) that connects to `/api/v1/ws`, handles `status` and `heartbeat` events, and updates the status bar in real time.
- All frontend files are plain files on disk — no bundler, no build step, vanilla HTML/CSS/JS only.
- Strict UI visibility rule (FR-016) is observed throughout: every control shown is backed by a working endpoint.

## Capabilities

### New Capabilities

- `web-frontend`: Vanilla HTML/CSS/JS frontend — page layout, dark theme, waterfall placeholder, decoded-messages list, Settings page with audio device selector and Save action, WebSocket status client.

### Modified Capabilities

*(none — the web-server spec already requires serving static files from `web/`; no server-side behaviour changes in this phase)*

## Impact

- New top-level `web/` directory and all its files (served as-is by the existing static-file middleware).
- No C# source changes expected; the daemon's static-file wiring is already in place from P1.
- Integration tests in `OpenWSFZ.Web.Tests` may be extended to verify real page assets load (HTTP 200 for `index.html`, `settings.html`, CSS, JS).
- No new NuGet dependencies.
