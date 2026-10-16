## ADDED Requirements

### Requirement: Waterfall history survives a resize

The waterfall renderer SHALL keep the spectrum lines it has received, not only the pixels it has drawn, so that a change of the canvas size or of `devicePixelRatio` does not discard history. It SHALL keep the last `HISTORY_LINES` = 2,048 lines, each exactly as received (a copy of the `bins` array), in a ring buffer. `render()` SHALL stay incremental (push the line, scroll the pixel buffer by one row, paint row 0). On a resize the renderer SHALL rebuild the pixel buffer at the new size and repaint `min(height, stored lines)` rows from the ring buffer, newest at the top, mapping each line to x by its own length. Rows below the stored history SHALL be black, as at start-up. One stored line is one physical pixel row, so the time scale is unchanged.

The history and repaint logic SHALL be in a module that does not touch the DOM (inputs: lines, a width and a height; output: RGBA bytes), so it can be tested without a browser.

#### Scenario: A resize keeps the history

- **WHEN** at least 300 spectrum lines have been rendered and the viewport is resized by 1 px, by −400 px, and back to the original size
- **THEN** after each resize the canvas SHALL show the history (the same lines, newest at the top, at the new width), and after the return to the original size rows 0 to 299 SHALL equal the pre-resize readback byte for byte

#### Scenario: A shrink followed by a grow brings the history back

- **WHEN** the canvas height is reduced to 10 rows and then restored to its original height
- **THEN** all of the original rows SHALL be repainted from the stored lines

#### Scenario: A zero-size panel is ignored

- **WHEN** the waterfall panel collapses to zero width or zero height and is later restored
- **THEN** the renderer SHALL keep its buffers while collapsed (no clamp to 1×1) and the history SHALL be visible again at the restored size

#### Scenario: The ring buffer keeps the newest lines

- **WHEN** `HISTORY_LINES` + k lines have been pushed
- **THEN** the renderer SHALL hold the newest `HISTORY_LINES` lines, in order

#### Scenario: Lines of different lengths repaint correctly

- **WHEN** the bin count changes between two lines in the stored history and a resize repaints them
- **THEN** each line SHALL be mapped to x by its own length

#### Scenario: Resize repaints are coalesced

- **WHEN** `ResizeObserver` fires many times within one animation frame
- **THEN** at most one repaint SHALL be performed for that frame, and the axis and cursor overlays SHALL be redrawn afterwards as they are today

---

### Requirement: Settings opens over the live main page

A plain left-click (no modifier key) on the main page's Settings link SHALL open Settings in an overlay panel that contains an `<iframe>`, with the main page left running behind it. Nothing on the main page SHALL be torn down: not the WebSocket, the waterfall rendering, the decode table, the QSO transcript, the timers or any open dialog. The link SHALL keep a real `href` of `/settings.html?key=…` so that middle-click, Ctrl-click, Shift-click and "open in new tab" open Settings as a normal page. The iframe SHALL be created fresh on every open and removed on close, so Settings always shows the daemon's current configuration and no second set of Settings timers runs while the panel is closed.

#### Scenario: A plain click opens the panel without navigating

- **WHEN** the operator plain-clicks the Settings link on the main page
- **THEN** a panel containing an iframe whose `src` carries `embedded=1` SHALL open, the main page SHALL NOT navigate (a page-memory sentinel set before the click SHALL still be set after), and the WebSocket SHALL stay connected

#### Scenario: The main page keeps running behind the panel

- **WHEN** the panel is open and the daemon sends `decode` and `spectrum` frames
- **THEN** the decode table SHALL gain those rows and the waterfall SHALL gain those lines

#### Scenario: A modified click opens a normal page

- **WHEN** the operator Ctrl-clicks, Shift-clicks or middle-clicks the Settings link
- **THEN** the browser SHALL handle the link as an ordinary link and no panel SHALL open

---

### Requirement: Settings embedded mode

The Settings page SHALL treat the query parameter `embedded=1` as the signal that it is shown inside the main page's panel. It SHALL NOT infer embedding from `window.top !== window.self`. In embedded mode the "← Back to main" link SHALL read **Close** and SHALL ask the main page to close the panel instead of navigating. A direct visit to `/settings.html` (no `embedded` parameter) SHALL behave exactly as before, back link included: the existing requirement "Settings page" and its scenario "Settings page has navigation back to main page" cover a direct visit, and in embedded mode that link becomes Close instead of navigating to `/`.

#### Scenario: Embedded mode shows Close

- **WHEN** `/settings.html?embedded=1` is loaded
- **THEN** the header link SHALL read Close, and activating it SHALL close the panel through the single close function and SHALL NOT navigate the iframe

#### Scenario: A direct visit is unchanged

- **WHEN** `/settings.html` is loaded without `embedded`
- **THEN** the link SHALL read "← Back to main" and SHALL navigate to `/` (carrying `?key=` as today), and the FR-041 guard SHALL work as before

---

### Requirement: Every close path honours the unsaved-changes guard

The panel SHALL close through one function, reached from the Close link, the panel's close button, Escape pressed with focus inside the iframe, and Escape pressed with focus on the main page. When the Settings form is dirty (FR-040) that function SHALL present the same confirmation as FR-041 ("You have unsaved changes. Leave without saving?"). Cancelling SHALL leave the panel open with the operator's edits intact. Confirming SHALL close the panel and discard the edits.

#### Scenario: A dirty form prompts on every close path

- **WHEN** a Settings field has been edited and not saved, and the operator uses any of the four close paths
- **THEN** the confirmation SHALL appear; Cancel SHALL keep the panel open with the edit intact; OK SHALL close the panel and leave the main page unchanged

#### Scenario: A clean form closes without a prompt

- **WHEN** the form is not dirty and the operator uses any of the four close paths
- **THEN** the panel SHALL close with no prompt

---

### Requirement: Main page refreshes its config-derived state when Settings closes

Because the main page reads configuration only at page load and no WebSocket event reports a configuration change, the main page SHALL re-read its config-derived state each time the panel closes, without reloading. It SHALL re-read `GET /api/v1/config` and apply `showCycleCountdown`, `tx.callsign`, `tx.grid` and `tx.callerPartnerSelect` and re-render the message rows; re-read the frequency list and rebuild the dial dropdown when the list's content (not only its length) differs; and re-read the TX status and the decode filter. The same refresh SHALL also run when the WebSocket reports `connected` after a disconnect, because a daemon restart can finish after the panel has closed, when the close-time reads saw the old daemon or failed while it was down. The one-time start of the 100 ms countdown interval SHALL be separated from the idempotent application of the configuration, so that applying it any number of times leaves at most one interval running and hides the countdown again when the setting is turned off.

#### Scenario: A saved callsign, countdown setting and frequency appear without a reload

- **WHEN** the operator changes `tx.callsign` to a synthetic Q-prefix call, turns `showCycleCountdown` on or off, and adds a frequency in Settings, saves, and closes the panel
- **THEN** with no reload the TX message rows SHALL show the new callsign, the countdown's visibility SHALL follow the setting, the dial dropdown SHALL list the new frequency, and exactly one countdown interval SHALL be running

#### Scenario: An edited frequency list of the same length is shown

- **WHEN** the operator edits a frequency's description or value without changing the number of entries, saves, and closes the panel
- **THEN** the dial dropdown SHALL show the edited entry

#### Scenario: A restart that finishes after the panel closed is re-read on reconnect

- **WHEN** the operator confirms Restart Daemon, closes the panel at once, and the WebSocket later reconnects
- **THEN** the config, frequency list, TX status and decode filter SHALL be re-read once the `connected` event follows the disconnect, and the page SHALL show the new daemon's values without a reload

#### Scenario: Applying the configuration twice starts one interval

- **WHEN** the configuration is applied twice with `showCycleCountdown` true
- **THEN** one interval SHALL be running; applying it again with `showCycleCountdown` false SHALL hide the countdown

---

### Requirement: An authentication failure inside the panel redirects the top window

In embedded mode a 401 from any request SHALL redirect the **top** window to `/login.html`, never the iframe, so that the login page and a second main GUI are not loaded inside the panel. All redirects to `/login.html` SHALL go through one helper that chooses the window.

#### Scenario: A 401 in the panel lands the top window on the login page

- **WHEN** a request made from the embedded Settings page receives HTTP 401
- **THEN** the top window SHALL navigate to `/login.html` and no main GUI SHALL be loaded inside the iframe

---

### Requirement: The Settings panel is modal and accessible

While the panel is open the main page behind it SHALL be inert (a modal `<dialog>` opened with `showModal()`, or the `inert` attribute). On open, focus SHALL move into the iframe, to its first tab or the active tab button. On close, focus SHALL return to the Settings link. The panel SHALL have the accessible name "Settings".

#### Scenario: Focus moves in and returns

- **WHEN** the panel opens and later closes
- **THEN** focus SHALL be inside the iframe while open and on the Settings link after close, and the dialog SHALL be exposed with the name "Settings"

---

### Requirement: Settings actions that leave the page work from the panel

Links that open a new window from Settings (the log viewer, via `window.open`) SHALL keep working from the panel. After a "Restart Daemon" confirmed from the panel, the main page SHALL reconnect by itself and its decode table, QSO transcript and waterfall history SHALL still be present afterwards.

#### Scenario: Restart Daemon from the panel

- **WHEN** the operator confirms Restart Daemon from the panel and the daemon comes back
- **THEN** the main page's WebSocket SHALL reconnect without a reload and the decode rows, transcript entries and waterfall history present before the restart SHALL still be present
