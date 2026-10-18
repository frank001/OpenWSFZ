**User-facing:** yes

## Why

GitHub issue **#212** (filed by QA 2026-10-05 from the Captain's report): the main GUI loses its state in
two ordinary operator actions.

1. **Resizing the browser window blanks the waterfall.** `WaterfallRenderer._resize()` assigns
   `canvas.width`/`canvas.height` (which clears the canvas) and allocates a fresh black `ImageData`; nothing
   is copied across. The waterfall's only memory is that pixel buffer, so any size change, even 1 px, loses
   the history. A zero-size panel (a layout change, a hidden ancestor) is clamped to 1×1 and wipes it too.
2. **Opening Settings and coming back discards the whole page.** `index.html` links to `/settings.html` with
   a full navigation, and Settings links back with another. Everything the main page holds only in memory is
   gone on return: the waterfall, the decode-table rows, the QSO transcript, the decode-filter "seen" sets and
   the cached real TX row text. None of it can be rebuilt from the daemon.

Source spec: `qa/rr-study/2026-10-16-1705-architect-to-engineer-spec-212-gui-state-preservation.md`
(Architect, on `arch/212-gui-state` @ `e7b87117`; Captain, 2026-10-16: "lets spend some time on gh issue
#212. spec it for the engineer"). Base `origin/main` @ `76aa48cd`.

🔴 **A finding that is in neither the issue nor the symptom, and it decides the design.** Today **the page
reload is what makes a saved setting appear on the main page**: the main page reads config only at page
load (`startCycleTimerIfEnabled`, `getFrequencies`, `getTxStatus`, `getDecodeFilter`) and no WebSocket
event reports a config change. Keeping the page alive therefore turns "stale until you reload" into a new
defect unless the page re-reads its config-derived state when Settings closes. `design.md` carries the
inventory of every load-time read (E1) and the decision for each.

## What Changes

- **Part A, waterfall history survives a resize.** The renderer keeps a ring buffer of the last 2,048
  spectrum lines exactly as received and repaints from it on resize. A zero size is ignored. Repaints are
  coalesced to one per animation frame. The history and repaint logic lives in a DOM-free module.
- **Part B, Settings opens over the live main page.** An unmodified left-click on the Settings link opens
  `/settings.html?embedded=1&key=…` in a modal `<dialog>` holding a fresh `<iframe>`, and the main page
  keeps running behind it. Middle-click, Ctrl-click and a direct visit are unchanged.
- **Part C, one close path with the unsaved-changes guard.** The Close link, the panel's close button and
  Escape (inside the iframe or on the main page) all go through one function that applies the FR-041 prompt.
- **Part D, the main page re-reads its config-derived state on close.** `startCycleTimerIfEnabled` is split
  into a one-time timer start and an idempotent `applyConfig(config)`; the frequency list, TX status and
  decode filter are re-read too. The dial dropdown is rebuilt when the list's content changes, not only
  its length.
- **Part E, authentication inside the panel.** A 401 in embedded mode redirects the **top** window to
  `/login.html`. All twelve redirect sites go through one helper.

## Impact

- Code: `web/js/spectrum.js`, a new DOM-free `web/js/waterfallHistory.js`, a new DOM-free
  `web/js/cycleTimer.js`, `web/js/main.js`, `web/js/api.js`, `web/js/ws.js`, `web/js/settings.js`,
  `web/index.html`, `web/settings.html`, `web/css/app.css`, new `web/js/*.test.js`, new
  `tests/web-ui/gui-state.playwright.mjs`. **No `src/`, no `native/`, no daemon API or WebSocket change**
  (`git diff --stat origin/main -- src/ native/` SHALL be empty).
- Behaviour a caller can see: the waterfall survives a resize; Settings is a panel, not a page.
- Out of scope, noted on #212 as a possible follow-up: a daemon-pushed `configChanged` WebSocket event (it
  would also cover a change made from another tab or client; it is a protocol change). No persistence of
  the waterfall or decode list across a real reload.
- Docs: `REQUIREMENTS.md` gains FR-086 (waterfall history) and FR-087 (Settings panel), and FR-041 is
  amended; `VERSION` bumped (G9b).
- No data era: the change touches no decode path.
