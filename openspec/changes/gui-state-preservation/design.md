# Design: gui-state-preservation (#212)

Base `origin/main` `76aa48cd`, read 2026-10-16. Line numbers are as of that tree; the Developer re-reads them on the branch they cut.

## E1. Inventory of every load-time read in `web/js/main.js`

Method: every `get…()` call from `api.js`, every `config.` / `status.` read, and every module-level value
derived from the daemon, on the `DOMContentLoaded` path and the functions it calls (`grep` of
`await get|get[A-Z]…\(|config\.|cachedFt8|setInterval|ResizeObserver|location.href`, then each hit read in
context). **Refresh set: 1, 3, 4 and 5 are re-read on every panel close.** All four are idempotent GETs.

| # | Where | What is read | Derived state | Kept current by | Refreshed on close? | Why |
|---|---|---|---|---|---|---|
| 1 | `startCycleTimerIfEnabled` ~L1126, `getConfig()` | `showCycleCountdown` | `cycleTimerEl` visibility; the 100 ms `setInterval(tickCycleTimer)` | nothing | **YES** | Settings edits it. The interval is started inside this function, so it must be split (below). |
| 1 | same | `tx.callsign`, `tx.grid` | `txCallsign`, `txGrid`, the template text of the message rows | nothing | **YES** | Settings edits them; `renderMessageRows` must be called again. Rows already in the decode table keep the callsign they were rendered with; only later rows and the message rows change. |
| 1 | same | `tx.callerPartnerSelect` | `currentCallerPartnerSelect`, the `#pileup-auto-select` checkbox | the checkbox's own POST, the `getTxStatus` response | **YES** | Settings has the same control (FR for CallerPartnerSelect). |
| 2 | `getFrequencies()` ~L1649 | the whole frequency list | `cachedFt8Frequencies` (filtered to `activeProtocol`), the `#dial-freq` `<select>` | nothing | **YES** | Settings edits it (`postFrequencies`). 🔴 `renderDialFreqSelect` ~L1214 re-uses the existing `<select>` when `options.length === cachedFt8Frequencies.length`, so a same-length edit (a description or a value changed, or one entry removed and one added) would NOT show. The rebuild test must compare content, not length. (Found by the Engineer; not in the spec.) |
| 3 | `getTxStatus()` ~L1511 | `state`, `partner`, `autoAnswerEnabled`, `role`, `keying`, `lastTxMessage`, `callerPartnerSelect` | the TX panel | `txState` WS events | **YES (differs from the Architect's "probably no")** | Between close and the next `txState` event it is stale in exactly one case that matters here: **Restart Daemon from the panel** (A7) rebuilds the daemon's QSO state, and a role change only takes effect after that restart. `txState` is pushed on a transition, not on connect, and `ws.js` reconnect re-seeds only the `status` frame. One GET on close covers it at no cost. |
| 4 | `initDecodeFilter` → `getDecodeFilter()` ~L698 | the filter state | `currentDecodeFilter`, row visibility (`reapplyDecodeFilterToRenderedRows`) | `decodeFilterChanged` WS event | **YES (same reason as 3)** | Normally current. After a daemon restart from the panel the daemon's filter state is rebuilt and no event announces it. The re-read is idempotent (`reapply…` is what the page already does on every change). Settings itself never edits the filter. |
| 5 | WS `status` frame (on every connect) | `audioDevice`, `audioActive`, `decodingEnabled`, `catConnectionStatus`, `dialFrequencyMHz`, `rxAudioOffsetHz`, `txAudioOffsetHz`, `holdTxFreq` | status bar, dial display, cursors, hold-TX box | the WS `status`, `cat_status`, `heartbeat`, `audioOffset` events | **No** | Already re-seeded by the first `status` frame after any reconnect. A Settings save that changes the audio device or CAT shows up through the next `status`/`cat_status` frame, as it does today without a reload. |
| 6 | `getPropModes()` ~L1413 | prop-mode list | the QSO-log dialog's dropdown | read each time the dialog opens | **No (not a load-time read)** | Fetched per dialog open. |
| 7 | `getRegionDataLookup`, `getRegionDataStatus` (region column) | per-callsign lookups | decode-table cells | read per row | **No (not a load-time read)** | On demand. |
| 8 | module constants: `activeProtocol = 'FT8'` (L28) | none | n/a | n/a | **No** | A constant, not config. |
| 9 | `bootstrapApiKeyFromUrl()` at module load, `getApiKey()` ~L1929 | the API key (`?key=` → `sessionStorage`) | the Settings link's `href` | n/a | **No** | `sessionStorage` is shared with a same-origin iframe, so the panel authenticates with it. The link's `href` is built once; the key does not change while the page is alive (a 401 redirects to login). |
| 10 | `localStorage`/`sessionStorage` use in `main.js` | none besides the key | n/a | n/a | **No** | |

The 12 redirects to `/login.html` (R2.8) are in `api.js` (10), `main.js` (the decode-toggle handler) and
`ws.js` (the auth-failure close).

No row needs a daemon change, so the spec's §7 first stop condition does not fire.

## D1. Waterfall history (Part A)

**Keep the lines, not the pixels** (the Architect's recommendation, adopted). A pixel-rescale of the old
buffer loses whatever a shrink cropped and blurs on every resize, so a drag through a small size and back
degrades the history. Repainting from raw lines is exact at every size, so shrink-then-grow restores it
(test U3).

- New DOM-free module `web/js/waterfallHistory.js` (as `qsoTranscript.js` was): `HISTORY_LINES = 2048`,
  `createColormapLut()` (256 entries, the existing `colormap()` made a table), and a
  `WaterfallHistory` class with `push(bins)` (copies into a `Uint8Array` slot of a preallocated ring),
  `paint(width, height)` returning `Uint8ClampedArray` RGBA (alpha 255, black below the stored rows) and
  `paintRow(bins, width, out, rowOffset)` shared with the incremental path so the two cannot drift.
- `spectrum.js`: `render(bins)` pushes the line, scrolls with `copyWithin`, paints row 0 with `paintRow`.
  `_resize()` recomputes `(w, h)`; **if either is 0, return without touching anything (R1.4)**; if `(w, h)`
  is unchanged, return; else assign the canvas size, rebuild the buffer from `paint(w, h)`, allocate the
  `OffscreenCanvas`, call `_flushToCanvas()`.
- **Coalescing (R1.5):** the `ResizeObserver` callback sets a flag and schedules one
  `requestAnimationFrame`; the frame runs `renderer.resize()` once. A `devicePixelRatio` change is
  watched with a `matchMedia('(resolution: …dppx)')` listener, re-armed after each change, feeding the
  same coalesced path.
- Memory: 2,048 lines × the bin count in bytes (about 2 MB at 1,000 bins), accepted by the Architect.
- `HISTORY_LINES` is a design constant that covers a canvas up to 2,048 physical pixels tall; it is not a
  pass bar (spec R1.3, HK-038: its number comes from the layout, not from a population).
- **Test seam note:** the axis and cursor overlays are drawn over the pixel rows in `_flushToCanvas`, so a
  canvas readback in A1 compares rows below the axis strip, or compares the history module's `paint()` output
  against the readback with the axis rows masked. Which one is a test-design choice for the Developer; the
  mechanical row condition is in `tasks.md` §4.

## D2. Settings panel (Part B and C)

- `index.html`: a `<dialog id="settings-dialog" aria-label="Settings">` holding a header with a close
  button and an empty container. `main.js` creates the `<iframe>` (`title="Settings"`, `src =
  /settings.html?embedded=1&key=…`) on open and removes it on close (spec R2.4).
- Click interception: on the Settings link, handle `click` only when `button === 0` and none of
  `ctrlKey`, `metaKey`, `shiftKey`, `altKey` is set; `preventDefault()` and open. Anything else falls
  through to the real `href`.
- **One close function** `requestCloseSettings()` in `main.js`. The four paths: the Close link inside the
  iframe (a `postMessage` to the parent, see "Transport as built" below), the dialog's own close button, a
  `keydown` Escape listener on the iframe's document, and the `<dialog>`'s `cancel` event (Escape on the
  main page, with `preventDefault()` so the browser's native close does not bypass the guard).
- **Dirty guard transport: direct same-origin call, not `postMessage`** (the Developer may choose
  otherwise and record it here). `settings.js` exposes `window.owsfzSettings = { requestClose() }`, which
  runs the existing FR-041 `confirm()` when `isDirty()`, removes the `beforeunload` listener on confirm,
  and returns `true`/`false` synchronously. The parent calls
  `iframe.contentWindow.owsfzSettings.requestClose()`. Reason: Settings is same-origin; a synchronous return
  value makes "Cancel leaves the panel open" trivially testable; `postMessage` would need a reply protocol.
  If the iframe has not finished loading, `owsfzSettings` is absent and the parent closes without a prompt
  (nothing can be dirty before the form exists).
- **Transport as built (Developer, 2026-10-16).** Parent to iframe is the direct same-origin call above
  (`iframe.contentWindow.owsfzSettings.requestClose()`, synchronous boolean). Iframe to parent is a
  **`postMessage`** `{ type: 'owsfz.settings.close' }` to `location.origin`, accepted by `main.js` only when
  `event.origin === location.origin` and `event.source === iframe.contentWindow`. It is used by the Close link
  AND by Escape inside the iframe, and `settings.js` owns both listeners (`isEmbedded` only). Reason: no global
  on the main page for the iframe to reach into, the Escape listener lives with the page it belongs to (nothing
  to re-attach if the iframe navigates), and there is no reply to wait for. Every way the dialog ends, including
  a native close the browser forces, lands on the dialog's `close` event, which is the single place that removes
  the iframe, returns focus and starts the refresh (so a native close cannot skip the cleanup).
- **Embedded mode** is read once from `new URLSearchParams(location.search).get('embedded') === '1'` in
  `settings.js`. Embedded: the back link's text becomes Close, its click calls the parent's close function
  and is prevented. Not embedded: the code is untouched (R2.10).
- Modal and focus: `dialog.showModal()` makes the rest of the page inert and gives Escape; on `iframe`
  `load`, focus the active tab button inside it; on close, `dialog.close()` and focus the link.
- `logs.html` via `window.open` is unchanged (R2.11).

## D3. Config refresh on close (Part D)

- New DOM-free module `web/js/cycleTimer.js`: `createCycleTimer({ tick, setIntervalFn, clearIntervalFn })`
  returning `{ apply(showCountdown) → boolean visible, intervalCount }`. `apply(true)` starts the interval
  at most once; `apply(false)` clears it (the Developer may keep it running and only hide the element; what
  is fixed is **at most one interval ever**, and that the element is hidden when the setting is off). Tested
  with a fake `setInterval` (U7). `cycleTimerEl.removeAttribute('hidden')` stays in the one-time start
  (FR-036).
- `startCycleTimerIfEnabled` becomes `initConfigDerivedState()` (called once from `DOMContentLoaded`) plus
  `refreshConfigDerivedState()` (called on every close): both call `getConfig()` →
  `applyConfig(config)`, `getFrequencies()` → `applyFrequencies(entries)`, `getTxStatus()` →
  `applyTxStatus(status)` (the existing seed code, extracted), `getDecodeFilter()` →
  `applyDecodeFilter(state)` (extracted). The four calls are independent: one failing leaves the others
  applied (as each `catch` does today).
- **Also refresh on reconnect (Architect ruling, 2026-10-16):** `WebSocketHub` sends only `status` on connect and
  `txState` only on a transition, and a restart can finish after the panel has closed (the close-time GETs
  then read the old daemon or fail). So `refreshConfigDerivedState()` also runs when the `__state`
  `connected` event follows a disconnect (not on the first connect, which `initConfigDerivedState()` covers).
  Client-only, `web/` only. Acceptance A7 closes the panel straight after pressing Restart.
- `renderDialFreqSelect` rebuilds when the existing `<select>`'s `(value, text)` sequence differs from the
  cache, not when only the length differs.
- `pileupAutoSelectEl.checked` is set from the refreshed value; an in-flight optimistic toggle is not
  protected (a close happens through a human, never during a toggle's round trip).

## D4. Auth in the panel (Part E)

`api.js` gains `export function redirectToLogin()`: clears the `sessionStorage` key, then sets
`(isEmbedded() ? window.top : window).location.href = '/login.html'`. `isEmbedded()` is the same
`embedded=1` test as D2. All twelve sites call it (`ws.js` and `main.js` import it). The helper returns
`new Promise(() => {})` where a site already does, so callers do not see a thrown error mid-navigation.

## D5. Why ADDED and not MODIFIED

The two existing scenarios the Architect named ("Settings navigation affordance is present": a link that
navigates to `/settings.html`; "Settings page has navigation back to main page") are **still true** under
this design: the link keeps a real `href`, and a direct visit keeps its back link. A MODIFIED block would
require copying the whole 60-line "Main page layout" and "Settings page" requirements to change nothing in
them. The new behaviour is stated as ADDED requirements instead; `REQUIREMENTS.md` FR-041 is the one
statement whose text needs amending (its path (1) names only the back link; it now also covers the panel's
close paths), and that is done in `tasks.md` §5.

## Risks carried

- Stale config after save: the main one, covered by D3 and acceptance A5.
- A stacked countdown interval: U7.
- A nested main GUI on a 401: D4, A9.
- Repaint cost on slow hardware: T-resize is reported descriptively (no bar), and R1.5 bounds the rate.
