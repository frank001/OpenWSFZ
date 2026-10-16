/**
 * #212 (gui-state-preservation, FR-086 / FR-087): Playwright acceptance A1-A9 for "the main GUI keeps its
 * state through a window resize and a visit to Settings".
 *
 * Not part of `dotnet test` or CI (HK-007: Playwright is fetched on demand). It drives a real Chromium
 * against a running daemon, so it needs one:
 *
 *   1. Start a daemon on an ISOLATED config and port (never the station's), from a build of this tree
 *      with web/ copied next to the executable:
 *        OpenWSFZ.Daemon.exe --port 18212 --config <scratch>/config.json
 *      with e.g.  { "port": 18212, "decodingEnabled": false }
 *   2. In a scratch directory:  npm install playwright   (1.61; Chromium is cached under ms-playwright)
 *   3. BASE_URL=http://127.0.0.1:18212 SHOTS=<dir for screenshots> node gui-state.playwright.mjs
 *      (run from a directory where `playwright` resolves; NODE_PATH works too)
 *
 * Exit code 0 = every check passed. Each check prints PASS/FAIL. The script CHANGES the daemon's config
 * (callsign, countdown, one frequency) and RESTARTS the daemon (A7), which is why it must be isolated.
 *
 * The WebSocket is proxied (page.routeWebSocket + connectToServer) so spectrum / decode / status frames can be
 * injected deterministically, while a real daemon restart (A7) still produces a real reconnect. No audio
 * device or radio is needed. NFR-021: only Q-prefix synthetic callsigns appear in any injected value.
 *
 * Tests that do not flake (TESTING_STRATEGY.md section 11): every wait is on a positive condition
 * (waitForFunction / poll), never a fixed delay.
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const BASE  = process.env.BASE_URL ?? 'http://127.0.0.1:18212';
const SHOTS = process.env.SHOTS ?? '.';
mkdirSync(SHOTS, { recursive: true });

const STEP_TIMEOUT_MS = 20_000;        // per positive-condition wait
const RESTART_TIMEOUT_MS = 90_000;     // daemon bind-retry budget is 20 s; this is the outer bound

let failures = 0;
function check(name, ok, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  -- ${detail}`}`);
  if (!ok) failures++;
}

// ── Synthetic data (NFR-021: Q-prefix calls only) ──────────────────────────────────────────────────────
const OWN_CALL   = 'Q1OFZ';
const OWN_GRID   = 'AA00';
const NEW_CALL   = 'Q3NEW';
const BIN_COUNT  = 100;
const BG_VALUE   = 30;
const STRIPE_VALUE = 200;
const STRIPE_FROM = 20, STRIPE_TO = 25;     // bins [20, 25): 20 % - 25 % of the width
const LINES      = 300;
const EXTRA_LINES = 20;     // injected while the panel is open (A4)

/** Same gradient as the page's colormap(), re-stated here so the test does not import the code under test. */
function colormap(v) {
  if (v < 64)  return [0, 0, Math.round(v / 64 * 255)];
  if (v < 128) return [0, Math.round((v - 64) / 64 * 255), 255];
  if (v < 192) { const t = (v - 128) / 64; return [Math.round(t * 255), 255, Math.round((1 - t) * 255)]; }
  return [255, 255, Math.round((v - 192) / 63 * 255)];
}
/** Marker for line i (0 = oldest): distinct from its neighbours, so a repaint in the wrong order is visible. */
const markerOf = (i) => (i * 7 + 13) % 200 + 20;
function makeBins(i) {
  const bins = new Array(BIN_COUNT).fill(BG_VALUE);
  for (let b = STRIPE_FROM; b < STRIPE_TO; b++) bins[b] = STRIPE_VALUE;
  bins[0] = markerOf(i);
  return bins;
}

// ── Browser ───────────────────────────────────────────────────────────────────────────────────────────
// The full Chromium build (new headless), not the default headless shell: the shell's canvas readback does not
// reflect an OffscreenCanvas putImageData composite, which the waterfall readbacks (A1-A4, A7) depend on.
const browser = await chromium.launch({ channel: 'chromium' });
const context = await browser.newContext({ viewport: { width: 1400, height: 1300 } });
const page    = await context.newPage();

const consoleErrors = [];
page.on('console',   (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push(String(e)));

// Count live 100 ms intervals (the cycle countdown) from before any page script runs.
await context.addInitScript(() => {
  const live = new Set();
  const origSet = window.setInterval.bind(window);
  const origClear = window.clearInterval.bind(window);
  window.setInterval = (fn, ms, ...rest) => {
    const id = origSet(fn, ms, ...rest);
    if (ms === 100) live.add(id);
    return id;
  };
  window.clearInterval = (id) => { live.delete(id); return origClear(id); };
  window.__liveCountdownIntervals = () => live.size;
});

// Request log for the refresh checks (A5, A7): endpoint kind per GET.
const REFRESH_PATHS = {
  config:      '/api/v1/config',
  frequencies: '/api/v1/frequencies',
  txStatus:    '/api/v1/tx/status',
  decodeFilter: '/api/v1/decode-filter',
};
const mainGets = { config: 0, frequencies: 0, txStatus: 0, decodeFilter: 0 };
page.on('request', (r) => {
  if (r.method() !== 'GET') return;
  // Only the MAIN frame's requests: the Settings iframe also reads config and frequencies.
  if (r.frame() !== page.mainFrame()) return;
  const p = new URL(r.url()).pathname;
  for (const [k, path] of Object.entries(REFRESH_PATHS)) if (p === path) mainGets[k]++;
});

// Proxy the WebSocket so the test can add frames to what the real daemon sends.
let wsToPage = null;          // the page-facing route of the CURRENT connection
let wsConnections = 0;
let serverConnectedGen = 0;   // bumped on the first frame the REAL daemon sends on each connection
await page.routeWebSocket(/\/api\/v1\/ws/, (ws) => {
  wsConnections++;
  wsToPage = ws;
  const server = ws.connectToServer();
  let first = true;
  server.onMessage((msg) => {           // installing a handler stops the default forwarding: forward by hand
    if (first) { first = false; serverConnectedGen++; }
    ws.send(msg);
  });
  ws.onMessage((msg) => server.send(msg));
  ws.onClose(() => server.close());
  server.onClose(() => ws.close());
});
const inject = (frame) => wsToPage.send(JSON.stringify(frame));

// Dialogs (confirm) raised by the main page or by the Settings iframe.
const dialogLog = [];
let dialogAnswer = true;
page.on('dialog', async (d) => {
  dialogLog.push({ type: d.type(), message: d.message() });
  if (dialogAnswer) await d.accept(); else await d.dismiss();
});

/** Polls a predicate until true (positive condition), failing the named check after the timeout. */
async function expectEventually(pred, name) {
  const deadline = Date.now() + STEP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (pred()) return true;
    await page.waitForTimeout(25);
  }
  check(name, false, 'timed out');
  return false;
}

/** Runs one acceptance block; a crash inside it (e.g. a missing element on the unfixed tree) is one FAIL, not an abort. */
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null;   // e.g. ONLY=A6 while debugging one block
async function section(name, body) {
  if (ONLY && !ONLY.includes(name)) return;
  try { await body(); }
  catch (e) {
    check(`${name} completed`, false, String(e.message ?? e).split('\n')[0]);
    await page.screenshot({ path: join(SHOTS, `crash-${name}.png`) }).catch(() => {});
    try {
      await page.keyboard.press('Escape');
      if (new URL(page.url()).pathname !== '/') {          // the page navigated away: start the next block on a main page
        await page.goto(BASE + '/');
        await waitConnected();
      }
    } catch { /* best effort */ }
  }
}

// ── In-page helpers ───────────────────────────────────────────────────────────────────────────────────
const canvasSize = () => page.evaluate(() => {
  const c = document.getElementById('waterfall');
  return { w: c.width, h: c.height };
});

/** SHA-256 over the first `rows` rows of the visible canvas, plus its size. Byte-for-byte comparison. */
const readbackHash = (rows) => page.evaluate(async (n) => {
  const c = document.getElementById('waterfall');
  const d = c.getContext('2d').getImageData(0, 0, c.width, Math.min(n, c.height)).data;
  const digest = await crypto.subtle.digest('SHA-256', d);
  return { w: c.width, h: c.height,
           hash: Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('') };
}, rows);

/**
 * Checks rows 0..n-1: x = 0 holds the line marker (newest at the top), the stripe sits at its scaled x
 * (+-1 px at both edges), and the background is the background colour. Returns the failing row count and
 * the first failure.
 */
const stripeReport = (n, newestIndex) => page.evaluate(({ n, newestIndex, markerColours, stripe, bg, from, to, bins }) => {
  const c = document.getElementById('waterfall');
  const w = c.width;
  const img = c.getContext('2d').getImageData(0, 0, w, Math.min(n, c.height));
  const px = (x, r) => Array.from(img.data.slice((r * w + x) * 4, (r * w + x) * 4 + 3));
  const eq = (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
  const left  = Math.ceil(from * w / bins);     // first stripe column
  const right = Math.ceil(to   * w / bins);     // first column after the stripe
  let bad = 0, first = null;
  const rows = Math.min(n, c.height);
  for (let r = 0; r < rows; r++) {
    const problems = [];
    if (!eq(px(0, r), markerColours[newestIndex - r])) problems.push('marker');
    if (!eq(px(left + 1, r), stripe))  problems.push('stripe-left+1');
    if (!eq(px(right - 2, r), stripe)) problems.push('stripe-right-2');
    if (!eq(px(left - 2, r), bg))      problems.push('bg-left-2');
    if (!eq(px(right + 1, r), bg))     problems.push('bg-right+1');
    if (problems.length) { bad++; if (!first) first = { row: r, problems }; }
  }
  return { rows, bad, first, w, left, right };
}, { n, newestIndex,
     markerColours: Array.from({ length: LINES + EXTRA_LINES }, (_, i) => colormap(markerOf(i))),
     stripe: colormap(STRIPE_VALUE), bg: colormap(BG_VALUE), from: STRIPE_FROM, to: STRIPE_TO, bins: BIN_COUNT });

/** Injects spectrum lines one at a time; waits (on a positive condition) until each one is painted at row 0. */
async function injectSpectrum(fromIndex, count) {
  for (let i = fromIndex; i < fromIndex + count; i++) {
    inject({ type: 'spectrum', payload: makeBins(i) });
    const [r, g, b] = colormap(markerOf(i));
    await page.waitForFunction(([r, g, b]) => {
      const c = document.getElementById('waterfall');
      const d = c.getContext('2d').getImageData(0, 0, 1, 1).data;
      return d[0] === r && d[1] === g && d[2] === b;
    }, [r, g, b], { timeout: STEP_TIMEOUT_MS, polling: 'raf' });
  }
}

const decodeRowTexts = () => page.$$eval('#decodes-body tr', (rows) => rows.map((r) => r.innerText.replace(/\s+/g, ' ').trim()));
const transcriptTexts = () => page.$$eval('#tx-transcript-log li', (li) => li.map((e) => e.innerText.replace(/\s+/g, ' ').trim()));
const msgRowsText = () => page.$$eval('.tx-msg-text', (els) => els.map((e) => e.textContent));
const sentinel = () => page.evaluate(() => window.__ows212);

let decodeSerial = 0;
function makeDecode(message) {
  decodeSerial++;
  const hh = String(Math.floor(decodeSerial / 60) % 24).padStart(2, '0');
  const mm = String(decodeSerial % 60).padStart(2, '0');
  return { time: `${hh}${mm}00`, band: '40m', snr: -5, dt: 0.1, freqHz: 1000 + decodeSerial, message,
           region: { entity: 'Test', synthetic: true, continent: null } };
}
async function injectDecodes(messages, expectRows) {
  inject({ type: 'decode', payload: messages.map(makeDecode) });
  await page.waitForFunction((n) => document.querySelectorAll('#decodes-body tr').length === n,
    expectRows, { timeout: STEP_TIMEOUT_MS });
}

async function waitConnected() {
  await page.waitForFunction(() => document.getElementById('ws-state')?.textContent === 'Connected',
    null, { timeout: RESTART_TIMEOUT_MS });
}

const api = async (method, path, data) => {
  const r = await page.request.fetch(`${BASE}${path}`, { method, data });
  return r;
};

// ── Fixture: a known isolated config ──────────────────────────────────────────────────────────────────
await api('POST', '/api/v1/config', { tx: { callsign: OWN_CALL, grid: OWN_GRID }, showCycleCountdown: false });

// Frequency list: record the original so A5 can restore nothing it did not add (the daemon is isolated anyway).
const freqsBefore = await (await api('GET', '/api/v1/frequencies')).json();

// ── Load the main page ────────────────────────────────────────────────────────────────────────────────
await page.goto(BASE + '/');
await waitConnected();
await page.waitForFunction(() => document.querySelector('.tx-msg-text')?.textContent.includes('Q1OFZ'),
  null, { timeout: STEP_TIMEOUT_MS });
// CAT "connected" so the dial control is the frequency dropdown (A5 checks it).
inject({ type: 'status', payload: { audioDevice: 'test', audioActive: true, decodingEnabled: false,
  catConnectionStatus: 'Connected', dialFrequencyMHz: 7.074, rxAudioOffsetHz: 1500, txAudioOffsetHz: 1500, holdTxFreq: false } });
await page.waitForFunction(() => document.getElementById('dial-freq')?.tagName === 'SELECT',
  null, { timeout: STEP_TIMEOUT_MS });

// ── Build up state worth keeping ──────────────────────────────────────────────────────────────────────
await injectSpectrum(0, LINES);
await injectDecodes(['CQ Q2AAA AA11', 'CQ Q2BBB BB22', 'Q2CCC Q2DDD -05'], 3);
await injectDecodes([`${OWN_CALL} Q2EEE -07`, `Q2EEE ${OWN_CALL} R-03`], 5);        // own call: transcript entries
await injectDecodes([`${OWN_CALL} Q2FFF 73`], 6);
await page.waitForFunction(() => document.querySelectorAll('#tx-transcript-log li').length >= 3,
  null, { timeout: STEP_TIMEOUT_MS });

const baselineRowsAll = await decodeRowTexts();
const baselineTranscript = await transcriptTexts();
check('precondition: >= 5 decode rows and >= 3 transcript entries',
  baselineRowsAll.length >= 5 && baselineTranscript.length >= 3,
  `rows=${baselineRowsAll.length} transcript=${baselineTranscript.length}`);
await page.screenshot({ path: join(SHOTS, 'before-0-main-with-state.png') });

// ── A1: a resize keeps the waterfall history ──────────────────────────────────────────────────────────
const size0 = await canvasSize();
const rep0 = await stripeReport(LINES, LINES - 1);
check('A1 precondition: the stripe and markers are on the canvas before any resize', rep0.bad === 0,
  JSON.stringify(rep0.first));
const hash0 = await readbackHash(LINES);

async function resizeTo(width) {
  await page.setViewportSize({ width, height: 1300 });
  // Positive condition: the canvas has taken the new width.
  await page.waitForFunction((prev) => {
    const c = document.getElementById('waterfall');
    const rect = c.getBoundingClientRect();
    return c.width === Math.round(rect.width * devicePixelRatio) && c.width !== prev;
  }, null, { timeout: STEP_TIMEOUT_MS }).catch(() => {});
  // The waterfall's repaint is coalesced onto an animation frame; wait two frames for it to land.
  await page.evaluate(() => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))));
}

for (const [label, width] of [['+1 px', 1401], ['-400 px', 1000]]) {
  const before = await canvasSize();
  await resizeTo(width);
  const after = await canvasSize();
  check(`A1 ${label}: the canvas width really changed`, after.w !== before.w, `${before.w} -> ${after.w}`);
  const rep = await stripeReport(LINES, LINES - 1);
  check(`A1 ${label}: rows 0-${LINES - 1} still show every line (marker, stripe at its scaled x)`, rep.bad === 0,
    `${rep.bad} bad rows, first ${JSON.stringify(rep.first)}`);
}
await page.screenshot({ path: join(SHOTS, 'after-1-resized-narrow.png') });
await resizeTo(1400);
const sizeBack = await canvasSize();
const hashBack = await readbackHash(LINES);
check('A1 back at the original size: width restored', sizeBack.w === size0.w, `${size0.w} vs ${sizeBack.w}`);
check('A1 back at the original size: rows 0-299 are byte-identical to before the first resize',
  hashBack.hash === hash0.hash, `before ${hash0.hash.slice(0, 12)} after ${hashBack.hash.slice(0, 12)}`);

// ── A2: collapsing the panel to zero height and restoring it ──────────────────────────────────────────
await page.addStyleTag({ content: '#waterfall-panel { flex: 0 0 0 !important; min-height: 0 !important; height: 0 !important; }' })
  .then(async (tag) => {
    await page.evaluate(() => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))));
    await tag.evaluate((el) => el.remove());
  });
await page.waitForFunction((h) => document.getElementById('waterfall').height === h, size0.h, { timeout: STEP_TIMEOUT_MS })
  .catch(() => {});
await page.evaluate(() => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))));
const hashA2 = await readbackHash(LINES);
check('A2 collapse to height 0 and restore: rows 0-299 byte-identical to before', hashA2.hash === hash0.hash,
  `size ${hashA2.w}x${hashA2.h} vs ${size0.w}x${size0.h}`);

// ── From here on: the sentinel proves no navigation happened ─────────────────────────────────────────
const SENTINEL = Math.random().toString(36).slice(2);
await page.evaluate((s) => { window.__ows212 = s; }, SENTINEL);

const settingsLink = page.locator('nav a[href^="/settings.html"]');
const dialogEl     = page.locator('#settings-dialog');
const settingsFrame = () => page.frames().find((f) => f.url().includes('/settings.html'));
const panelIsOpen  = () => page.evaluate(() => !!document.getElementById('settings-dialog')?.open);

async function openSettings() {
  await settingsLink.click();                                  // a plain primary-button click
  await page.waitForFunction(() => document.getElementById('settings-dialog')?.open === true,
    null, { timeout: STEP_TIMEOUT_MS });
  // Positive condition: the form is populated (Settings has read /api/v1/config).
  await page.waitForFunction(() => {
    const f = document.querySelector('#settings-dialog iframe');
    const d = f?.contentDocument;
    return !!d && d.readyState === 'complete' && !!d.getElementById('general-callsign')?.value;
  }, null, { timeout: STEP_TIMEOUT_MS });
}
async function waitPanelClosed() {
  await page.waitForFunction(() => !document.getElementById('settings-dialog')?.open
    && !document.querySelector('#settings-dialog iframe'), null, { timeout: STEP_TIMEOUT_MS });
}
const frameLocator = () => page.frameLocator('#settings-dialog iframe');

/** Index of the frequency-table row whose MHz field reads `mhz` (input VALUES are properties, not attributes). */
async function freqRowIndex(fr, mhz) {
  const values = await fr.locator('#freq-tbody .freq-mhz').evaluateAll((els) => els.map((e) => e.value));
  const i = values.indexOf(mhz);
  if (i < 0) throw new Error(`no frequency row for ${mhz}: ${values.join(',')}`);
  return i;
}
/** Clicks Save and waits for the positive condition that the whole save finished (the form is clean again). */
async function saveAndWaitClean(fr) {
  const posted = page.waitForResponse((r) => r.url().endsWith('/api/v1/config') && r.request().method() === 'POST');
  await fr.locator('#save-btn').click();
  const status = (await posted).status();
  await fr.locator('#unsaved-badge').waitFor({ state: 'hidden', timeout: STEP_TIMEOUT_MS });
  return status;
}

const closePaths = {
  'Close link':            async () => { await frameLocator().locator('#back-link').click(); },
  'panel close button':    async () => { await page.locator('#settings-dialog-close').click(); },
  'Escape in the iframe':  async () => { await frameLocator().locator('#general-callsign').focus(); await page.keyboard.press('Escape'); },
  'Escape on the main page': async () => {
    // Focus a control of the main document (the panel's own close button) so the key goes to it, not the iframe.
    await page.locator('#settings-dialog-close').focus();
    await page.keyboard.press('Escape');
  },
};

// ── A3: open and close by every path, nothing is lost ─────────────────────────────────────────────────
await section('A3', async () => {
const hashBeforeSettings = await readbackHash(LINES);
for (const [name, doClose] of Object.entries(closePaths)) {
  dialogLog.length = 0;
  await openSettings();
  check(`A3 [${name}] a plain click opened the panel without navigating`, (await sentinel()) === SENTINEL);
  const src = await page.$eval('#settings-dialog iframe', (f) => f.getAttribute('src'));
  check(`A3 [${name}] the iframe src carries embedded=1`, /[?&]embedded=1/.test(src), src);
  await doClose();
  await waitPanelClosed();
  check(`A3 [${name}] a clean form closed with no prompt`, dialogLog.length === 0, JSON.stringify(dialogLog));
  check(`A3 [${name}] page-memory sentinel unchanged`, (await sentinel()) === SENTINEL);
  check(`A3 [${name}] decode rows and texts equal`,
    JSON.stringify(await decodeRowTexts()) === JSON.stringify(baselineRowsAll));
  check(`A3 [${name}] transcript entries equal`,
    JSON.stringify(await transcriptTexts()) === JSON.stringify(baselineTranscript));
  check(`A3 [${name}] waterfall readback byte-identical`, (await readbackHash(LINES)).hash === hashBeforeSettings.hash);
  check(`A3 [${name}] focus is back on the Settings link`,
    await page.evaluate(() => document.activeElement === document.querySelector('nav a[href^="/settings.html"]')));
}
});

// ── A4: the page keeps running behind the panel ──────────────────────────────────────────────────────
await section('A4', async () => {
await openSettings();
const rowsBeforeA4 = (await decodeRowTexts()).length;
inject({ type: 'decode', payload: [makeDecode('CQ Q2GGG CC33'), makeDecode('CQ Q2HHH DD44')] });
await page.screenshot({ path: join(SHOTS, 'after-2-settings-panel-open.png') });
await injectSpectrum(LINES, EXTRA_LINES);
await closePaths['Close link']();
await waitPanelClosed();
await page.waitForFunction((n) => document.querySelectorAll('#decodes-body tr').length === n, rowsBeforeA4 + 2,
  { timeout: STEP_TIMEOUT_MS });
check('A4 exactly 2 more decode rows after frames arrived behind the panel',
  (await decodeRowTexts()).length === rowsBeforeA4 + 2);
const repA4 = await stripeReport(LINES + EXTRA_LINES, LINES + EXTRA_LINES - 1);
check('A4 exactly 20 more waterfall lines (rows 0-319 are the newest 320 lines)', repA4.bad === 0,
  `${repA4.bad} bad rows, first ${JSON.stringify(repA4.first)}`);
});

// ── A5: saved config shows up without a reload ───────────────────────────────────────────────────────
await section('A5', async () => {
const timerBefore = await page.evaluate(() => window.__liveCountdownIntervals());
check('A5 precondition: countdown is off and no interval is running', timerBefore === 0, `live=${timerBefore}`);
await openSettings();
const fr = frameLocator();
await fr.locator('#general-callsign').fill(NEW_CALL);
await fr.locator('#tab-btn-advanced').click();
await fr.locator('#cycle-countdown-toggle').check();
await fr.locator('#tab-btn-frequencies').click();
// Same-length edit first would hide in a count-only test: change the description of the 40 m entry.
await fr.locator('#freq-tbody .freq-desc').nth(await freqRowIndex(fr, '7.074')).fill('40m EDITED');
await fr.locator('#add-freq-btn').click();
const newRow = fr.locator('#freq-tbody tr[data-freq-row]').last();
await newRow.locator('.freq-protocol').fill('FT8');
await newRow.locator('.freq-mhz').fill('50.313');
await newRow.locator('.freq-desc').fill('6m ADDED');
check('A5 save returns 200', (await saveAndWaitClean(fr)) === 200);
await closePaths['Close link']();
await waitPanelClosed();
check('A5 no reload (sentinel unchanged)', (await sentinel()) === SENTINEL);
await page.waitForFunction((call) => [...document.querySelectorAll('.tx-msg-text')].some((e) => e.textContent.includes(call)),
  NEW_CALL, { timeout: STEP_TIMEOUT_MS }).catch(() => {});
const msgs = await msgRowsText();
check('A5 the TX message rows show the new callsign', msgs.every((t) => t.includes(NEW_CALL)), JSON.stringify(msgs));
await page.waitForFunction(() => getComputedStyle(document.getElementById('cycle-timer')).visibility === 'visible',
  null, { timeout: STEP_TIMEOUT_MS }).catch(() => {});
check('A5 the countdown became visible',
  await page.evaluate(() => getComputedStyle(document.getElementById('cycle-timer')).visibility === 'visible'));
check('A5 exactly one countdown interval is running', (await page.evaluate(() => window.__liveCountdownIntervals())) === 1,
  `live=${await page.evaluate(() => window.__liveCountdownIntervals())}`);
await page.waitForFunction(() => [...document.querySelectorAll('#dial-freq option')].some((o) => o.textContent.includes('6m ADDED')),
  null, { timeout: STEP_TIMEOUT_MS }).catch(() => {});
const dialOptions = await page.$$eval('#dial-freq option', (os) => os.map((o) => o.textContent));
check('A5 the dial dropdown lists the added frequency', dialOptions.some((t) => t.includes('50.313') && t.includes('6m ADDED')),
  JSON.stringify(dialOptions));
check('A5 same-length edit: the dropdown shows the edited description of the existing entry',
  dialOptions.some((t) => t.includes('7.074') && t.includes('40m EDITED')), JSON.stringify(dialOptions));

// Same-length edit proper: change a description and NOTHING else, so the entry count stays equal.
await openSettings();
await fr.locator('#tab-btn-frequencies').click();
await fr.locator('#freq-tbody .freq-desc').nth(await freqRowIndex(fr, '50.313')).fill('6m RENAMED');
const countBefore = await page.$$eval('#dial-freq option', (os) => os.length);
await saveAndWaitClean(fr);
await closePaths['Close link']();
await waitPanelClosed();
await page.waitForFunction(() => [...document.querySelectorAll('#dial-freq option')].some((o) => o.textContent.includes('6m RENAMED')),
  null, { timeout: STEP_TIMEOUT_MS }).catch(() => {});
const dialOptions2 = await page.$$eval('#dial-freq option', (os) => os.map((o) => o.textContent));
check('A5 same-length edit (count unchanged): the dropdown shows the renamed entry',
  dialOptions2.length === countBefore && dialOptions2.some((t) => t.includes('6m RENAMED')),
  `count ${countBefore} -> ${dialOptions2.length}: ${JSON.stringify(dialOptions2)}`);

// Turning the countdown off again hides it and leaves no interval.
await openSettings();
await fr.locator('#tab-btn-advanced').click();
await fr.locator('#cycle-countdown-toggle').uncheck();
await saveAndWaitClean(fr);
await closePaths['Close link']();
await waitPanelClosed();
await page.waitForFunction(() => getComputedStyle(document.getElementById('cycle-timer')).visibility === 'hidden',
  null, { timeout: STEP_TIMEOUT_MS }).catch(() => {});
check('A5 countdown turned off: hidden again',
  await page.evaluate(() => getComputedStyle(document.getElementById('cycle-timer')).visibility === 'hidden'));
check('A5 countdown turned off: no interval left', (await page.evaluate(() => window.__liveCountdownIntervals())) === 0);
await page.screenshot({ path: join(SHOTS, 'after-3-config-refreshed.png') });
});

// ── A6: unsaved edits are guarded on every close path ─────────────────────────────────────────────────
await section('A6', async () => {
for (const [name, doClose] of Object.entries(closePaths)) {
  await openSettings();
  // Settings remembers its last tab, so select General explicitly before editing the callsign.
  await frameLocator().locator('#tab-btn-general').click();
  await frameLocator().locator('#general-callsign').fill('Q9DIRTY');
  const rowsBefore = JSON.stringify(await decodeRowTexts());

  dialogLog.length = 0;
  dialogAnswer = false;                                 // Cancel
  await doClose();
  // Positive condition: the confirmation was raised.
  await expectEventually(() => dialogLog.length >= 1, `A6 [${name}] confirmation raised`);
  check(`A6 [${name}] the confirmation text is the FR-041 text`,
    dialogLog[0]?.message === 'You have unsaved changes. Leave without saving?', JSON.stringify(dialogLog));
  check(`A6 [${name}] Cancel keeps the panel open`, await panelIsOpen());
  check(`A6 [${name}] Cancel keeps the edit`,
    (await frameLocator().locator('#general-callsign').inputValue()) === 'Q9DIRTY');

  dialogLog.length = 0;
  dialogAnswer = true;                                  // OK
  await doClose();
  await waitPanelClosed();
  check(`A6 [${name}] OK closes the panel`, !(await panelIsOpen()));
  check(`A6 [${name}] OK leaves the main page unchanged`, JSON.stringify(await decodeRowTexts()) === rowsBefore
    && (await sentinel()) === SENTINEL);
}
dialogAnswer = true;
});

// ── A8: a direct visit, and a modified click, behave as before ───────────────────────────────────────
await section('A8', async () => {
{
  const direct = await context.newPage();
  await direct.goto(`${BASE}/settings.html`);
  await direct.waitForFunction(() => !!document.getElementById('general-callsign')?.value);
  check('A8 direct visit: the back link reads "← Back to main"',
    (await direct.locator('#back-link').innerText()).trim() === '← Back to main');
  await direct.locator('#general-callsign').fill('Q9DIRTY');
  let promptText = null, accept = false;
  direct.on('dialog', async (d) => { promptText = d.message(); if (accept) await d.accept(); else await d.dismiss(); });
  await direct.locator('#back-link').click();
  await expectEventually(() => promptText !== null, 'A8 direct visit: FR-041 guard raised');
  check('A8 direct visit: the FR-041 guard still prompts', promptText === 'You have unsaved changes. Leave without saving?');
  check('A8 direct visit: Cancel stays on /settings.html', new URL(direct.url()).pathname === '/settings.html');
  accept = true;
  await Promise.all([direct.waitForURL((u) => u.pathname === '/'), direct.locator('#back-link').click()]);
  check('A8 direct visit: OK navigates to the main page', new URL(direct.url()).pathname === '/');
  await direct.close();

  const popupP = context.waitForEvent('page', { timeout: STEP_TIMEOUT_MS });
  popupP.catch(() => {});                // a failure is reported by the await below, not as an unhandled rejection
  await settingsLink.click({ modifiers: ['Control'] });
  const popup = await popupP;
  await popup.waitForLoadState('domcontentloaded');
  check('A8 Ctrl-click opens Settings as a normal page', new URL(popup.url()).pathname === '/settings.html', popup.url());
  check('A8 Ctrl-click: that page has the direct-visit back link',
    (await popup.locator('#back-link').innerText()).trim() === '← Back to main');
  await popup.close();
  check('A8 Ctrl-click opened no panel and did not navigate the main page', !(await panelIsOpen()) && (await sentinel()) === SENTINEL);
}
});

// ── A7: Restart Daemon from the panel (real restart of the isolated daemon) ──────────────────────────
await section('A7', async () => {
{
  await openSettings();
  const hashA7 = await readbackHash(LINES);
  const rowsA7 = JSON.stringify(await decodeRowTexts());
  const transcriptA7 = JSON.stringify(await transcriptTexts());
  const genBefore = serverConnectedGen;
  const base = { ...mainGets };

  await frameLocator().locator('#tab-btn-advanced').click();
  await frameLocator().locator('#restart-daemon-btn').click();      // the test's dialog handler accepts the confirm
  // Wait on the positive condition that the restart is really under way, THEN close the panel at once
  // (before the new daemon is back): the close-time GETs read the old daemon or fail.
  await frameLocator().locator('#restart-daemon-status').waitFor({ state: 'visible', timeout: STEP_TIMEOUT_MS });
  await closePaths['panel close button']();
  await waitPanelClosed();

  // The page reconnects by itself (a new proxied WebSocket connection), without a reload.
  const reconnectDeadline = Date.now() + RESTART_TIMEOUT_MS;
  while (serverConnectedGen === genBefore && Date.now() < reconnectDeadline) await page.waitForTimeout(100);
  await waitConnected();
  check('A7 the WebSocket reconnected to the restarted daemon (a new connection, first frame received)',
    serverConnectedGen > genBefore);
  check('A7 no reload (sentinel unchanged)', (await sentinel()) === SENTINEL);

  // Close refresh = 1 GET per endpoint; the on-reconnect refresh must make it at least 2.
  let ok = true, detail = '';
  const deadline = Date.now() + STEP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    ok = Object.keys(REFRESH_PATHS).every((k) => mainGets[k] - base[k] >= 2);
    if (ok) break;
    await page.waitForTimeout(100);
  }
  detail = JSON.stringify(Object.fromEntries(Object.keys(base).map((k) => [k, mainGets[k] - base[k]])));
  check('A7 config, frequencies, TX status and decode filter were re-read on close AND on reconnect (>= 2 GETs each)', ok, detail);
  check('A7 decode rows are still there', JSON.stringify(await decodeRowTexts()) === rowsA7);
  check('A7 transcript entries are still there', JSON.stringify(await transcriptTexts()) === transcriptA7);
  check('A7 waterfall history is still there', (await readbackHash(LINES)).hash === hashA7.hash);
}
});

// ── A9: a 401 inside the panel sends the TOP window to the login page ────────────────────────────────
await section('A9', async () => {
{
  await page.route(/\/api\/v1\/config(\?.*)?$/, async (route) => {
    const frame = route.request().frame();
    if (route.request().method() === 'GET' && frame !== page.mainFrame() && frame.url().includes('/settings.html'))
      await route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized"}' });
    else await route.continue();
  });
  await settingsLink.click();
  await page.waitForURL((u) => u.pathname === '/login.html', { timeout: STEP_TIMEOUT_MS }).catch(() => {});
  check('A9 the top window landed on /login.html', new URL(page.url()).pathname === '/login.html', page.url());
  const nestedGui = await page.evaluate(() => document.querySelectorAll('iframe').length);
  check('A9 no iframe (no second GUI) is left on the login page', nestedGui === 0, `iframes=${nestedGui}`);
  await page.unroute(/\/api\/v1\/config(\?.*)?$/);
}
});

// ── Wrap up ───────────────────────────────────────────────────────────────────────────────────────────
const real = consoleErrors.filter((e) => !/401|Failed to load resource/.test(e));
check('no unexpected console errors', real.length === 0, real.join(' | ').slice(0, 400));
await browser.close();
console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
