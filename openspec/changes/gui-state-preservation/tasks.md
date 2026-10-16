# Tasks: gui-state-preservation (#212)

Owner: Engineer (Eng): this change, the Developer handoff, and the §5 acceptance. Build (`web/`, `tests/`): a
separate Developer session, branch `feat/212-gui-state` off `origin/main` (HK-011 by its principle: `web/` is
product code). Engineer branch: `eng/212-gui-state`. Architect branch: `arch/212-gui-state`.
Source spec: `qa/rr-study/2026-10-16-1705-architect-to-engineer-spec-212-gui-state-preservation.md`
(`arch/212-gui-state` @ `e7b87117`). Test IDs U1–U7 and acceptance rows A1–A9 are the spec's (§4, §5); rows
A5 and A10 here are extended (see §4).
Handoff: `dev-tasks/2026-10-16-eng-to-dev-212-gui-state.md`.

## 0. Preconditions

- [x] 0.1 `origin/main` is `76aa48cd` (2026-10-16). Evidence: `git log -1 origin/main`.
- [x] 0.2 Load-time inventory (spec E1): `design.md` §E1. Ten rows, four re-read on close, no daemon change needed.
- [x] 0.3 The Developer re-reads the line numbers quoted in `design.md` on the tree they branch from.

## 1. Tests first (Developer)

- [x] 1.1 `web/js/waterfallHistory.test.js`: U1–U6 (spec §4). Each must be able to fail (HK-025(k)).
- [x] 1.2 `web/js/cycleTimer.test.js`: U7, with a fake `setInterval`/`clearInterval`.
- [x] 1.3 `tests/web-ui/gui-state.playwright.mjs`: acceptance A1–A10 (spec §5 plus `design.md`), same conventions
      as `settings-archive.playwright.mjs` (isolated daemon and port, never the station's; `routeWebSocket`
      for the frames). Written before the implementation; it SHALL be red on `origin/main` for A1–A5, A9.

## 2. Part A: waterfall (Developer)

- [x] 2.1 `web/js/waterfallHistory.js` (DOM-free): `HISTORY_LINES = 2048`, colormap LUT, `WaterfallHistory`.
- [x] 2.2 `spectrum.js`: `render()` pushes and paints row 0 through the shared row painter; `_resize()` ignores a
      zero size, ignores an unchanged size, otherwise repaints from the ring.
- [x] 2.3 `main.js`: `ResizeObserver` callback coalesced to one `requestAnimationFrame`; a `devicePixelRatio`
      `matchMedia` listener feeds the same path.

## 3. Parts B–E: Settings panel (Developer)

- [x] 3.1 `index.html` + `app.css`: `<dialog id="settings-dialog" aria-label="Settings">`, close button.
- [x] 3.2 `main.js`: link click interception (primary button, no modifier), fresh iframe per open, one
      `requestCloseSettings()`, Escape on the main page via the dialog's `cancel` event, focus in and back.
- [x] 3.3 `settings.js` + `settings.html`: `embedded=1` mode (Close, no navigation), `window.owsfzSettings.requestClose()`,
      Escape forwarded from the iframe, the direct-visit path untouched.
- [x] 3.4 `api.js` `redirectToLogin()`, all twelve sites use it (`api.js` ×10, `main.js`, `ws.js`).
- [x] 3.5 `cycleTimer.js` and the split of `startCycleTimerIfEnabled` into `initConfigDerivedState()` and
      `refreshConfigDerivedState()`; `renderDialFreqSelect` rebuilds on a content difference; refresh on every close
      and on a WebSocket `connected` that follows a disconnect.

## 4. Acceptance (Engineer, mechanical; every row PASS or FAIL)

Rows A1–A9 are the spec's §5, verbatim. **Extended by the Engineer (neither changes a spec bar):**

- **A5 adds a same-length edit:** edit an existing frequency's description (count unchanged), save, close: the
  dropdown shows the edited text. (`design.md` §E1 row 2; it is the case the length test would miss.)
- **A7 adds a late finish:** press Restart in the panel and close the panel at once (before the daemon is back);
  once the WebSocket has reconnected, the config, frequency list, TX status and decode filter are re-read
  (Architect ruling 2026-10-16; mutation m6: remove the on-reconnect refresh, A7 turns red).
- **A10:** `git diff --stat origin/main -- src/ native/` is empty on the Developer's branch.

Plus **T-resize** (descriptive, not a gate): median and maximum of 20 resizes at 2,048 stored lines on the station
PC. Reported to the Architect, who rules if the median is over 16.7 ms.

- [ ] 4.1 A1–A10 run on an isolated daemon and port, with before and after screenshots (HK-005).
- [ ] 4.2 Mutations, each turning a test red: (m1) restore the `canvas.width` wipe in the resize path; (m2) make
      the refresh a no-op; (m3) let one close path skip the dirty guard; (m4, optional) restore the 1×1 clamp;
      (m5, Engineer's addition) restore the length-only rebuild test in `renderDialFreqSelect`.
- [ ] 4.3 Say whether the diff touches the decode-panel code (filtering, rendering, reapply); if it does,
      `live_verify_9_axes.py` is required before merge.

## 5. Documentation and gates (Developer; Engineer verifies)

- [x] 5.1 `REQUIREMENTS.md`: add **FR-086** (waterfall history survives a resize) and **FR-087** (Settings opens over
      the live main page, with its close paths, config refresh and 401 rule); amend **FR-041** (its guard
      now also covers the panel's close paths); add a revision-history row.
- [ ] 5.2 `VERSION` bump (G9b); commit before running `check_version_bump.py` (it reads the proposal from git).
- [x] 5.3 Traceability: follow the precedent for the other web-only FRs (FR-062, FR-083) and report what it was.
- [ ] 5.4 `openspec validate gui-state-preservation --strict`; `node --test web/js/*.test.js` green.

## 6. Out of scope, to note on #212 as follow-ups (not built here)

- A daemon-pushed `configChanged` WebSocket event (covers another tab or client; a protocol change).
- Persisting the waterfall or decode list across a real page reload.
