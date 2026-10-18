/**
 * #219: early decode rows show the CQ / addressed-to-operator colours on the REAL page.
 *
 * Not part of `dotnet test` or CI (HK-007: Playwright is fetched on demand). It drives a real Chromium against a
 * running daemon, and feeds `decode-early` / `decode` frames through the page's own WebSocket handler
 * (handleEarlyDecodes / handleDecodes), so the classes come from main.js and not from hand-written markup.
 *
 *   1. Start a daemon on an ISOLATED config and port (never the station's), from a build of this tree:
 *        OpenWSFZ.Daemon.exe --port 18219 --config <scratch>/config.json     { "port": 18219, "decodingEnabled": false }
 *   2. In a scratch directory:  npm install playwright
 *   3. BASE_URL=http://127.0.0.1:18219 SHOTS=<dir> node early-row-shade.playwright.mjs
 *
 * Exit code 0 = every check passed. NFR-021: only Q-prefix synthetic callsigns. The operator callsign is read from
 * the daemon's config (default Q1OFZ), not set here.
 * Every wait is on a positive condition (waitForFunction), never a fixed delay (TESTING_STRATEGY.md section 11).
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const BASE  = process.env.BASE_URL ?? 'http://127.0.0.1:18219';
const SHOTS = process.env.SHOTS ?? '';
const STEP_TIMEOUT_MS = 10000;
const OWN_CALL = 'Q1OFZ';

let failures = 0;
function check(name, ok, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  -- ${detail}`}`);
  if (!ok) failures++;
}
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

let wsToPage = null;
await page.routeWebSocket(/\/api\/v1\/ws/, (ws) => {
  wsToPage = ws;
  const server = ws.connectToServer();
  server.onMessage((msg) => ws.send(msg));
  ws.onMessage((msg) => server.send(msg));
  ws.onClose(() => server.close());
  server.onClose(() => ws.close());
});
const inject = (frame) => wsToPage.send(JSON.stringify(frame));

await page.goto(BASE + '/');
await page.waitForFunction(() => document.getElementById('ws-state')?.textContent === 'Connected',
  null, { timeout: STEP_TIMEOUT_MS });
await page.waitForFunction((c) => document.querySelector('.tx-msg-text')?.textContent.includes(c),
  OWN_CALL, { timeout: STEP_TIMEOUT_MS });

let serial = 0;
const decode = (message) => {
  serial++;
  return { time: `19${String(40 + serial).padStart(2, '0')}00`, band: '40m', snr: -5, dt: 0.1,
           freqHz: 1000 + serial, message, region: { entity: 'Test', synthetic: true, continent: null } };
};
const rowCount = () => page.evaluate(() => document.querySelectorAll('#decodes-body tr').length);
async function waitRows(n) {
  await page.waitForFunction((k) => document.querySelectorAll('#decodes-body tr').length === k, n,
    { timeout: STEP_TIMEOUT_MS });
}
/** Look up a row by its message text; read the classes and the message cell's computed style. */
const rowInfo = (text) => page.evaluate((t) => {
  const tr = [...document.querySelectorAll('#decodes-body tr')].find((r) => r.cells[5]?.textContent.startsWith(t));
  if (!tr) return null;
  const cs = getComputedStyle(tr.cells[5]);
  return { classes: [...tr.classList].sort(), bg: cs.backgroundColor, weight: cs.fontWeight, opacity: cs.opacity,
           color: cs.color, cursorInline: tr.style.cursor };
}, text);
const hasAll = (info, ...c) => info && c.every((x) => info.classes.includes(x));

// ── Early rows through handleEarlyDecodes ─────────────────────────────────────────────────────────────
const CQ_MSG = 'CQ Q2AAA AA11', TO_ME_MSG = `${OWN_CALL} Q2DDD -09`, PLAIN_MSG = 'Q2BBB Q2CCC -05', CQ2_MSG = 'CQ Q2EEE BB22';
inject({ type: 'decode-early', payload: [
  { earlyId: 1, decode: decode(CQ_MSG) },
  { earlyId: 2, decode: decode(TO_ME_MSG) },
  { earlyId: 3, decode: decode(PLAIN_MSG) },
  { earlyId: 4, decode: decode(CQ2_MSG) },
] });
await waitRows(4);

const cq = await rowInfo(CQ_MSG), toMe = await rowInfo(TO_ME_MSG), plain = await rowInfo(PLAIN_MSG);
check('E1 early CQ row has decode-cq + decode-early', hasAll(cq, 'decode-cq', 'decode-early'), JSON.stringify(cq));
check('E2 early CQ row background is #04140a (rgb(4, 20, 10))', cq?.bg === 'rgb(4, 20, 10)', cq?.bg);
check('E3 early CQ row: full opacity, weight 800', cq?.opacity === '1' && cq?.weight === '800', JSON.stringify(cq));
check('E4 early addressed-to-operator row has decode-partner + decode-early', hasAll(toMe, 'decode-partner', 'decode-early'), JSON.stringify(toMe));
check('E5 early addressed-to-operator background is #1c0709 (rgb(28, 7, 9))', toMe?.bg === 'rgb(28, 7, 9)', toMe?.bg);
check('E6 early plain row has no highlight class', plain && !plain.classes.some((c) => /^decode-(cq|partner|responder)$/.test(c)), JSON.stringify(plain));
check('E7 early rows stay display-only: no inline pointer cursor', cq?.cursorInline === '' && toMe?.cursorInline === '', JSON.stringify([cq?.cursorInline, toMe?.cursorInline]));

// Hover keeps the early colour (not the final row's bright hover) and the default cursor.
await page.locator('#decodes-body tr', { hasText: CQ_MSG }).locator('td').nth(5).hover();
const hov = await page.evaluate((t) => {
  const tr = [...document.querySelectorAll('#decodes-body tr')].find((r) => r.cells[5]?.textContent.startsWith(t));
  return { bg: getComputedStyle(tr.cells[5]).backgroundColor, cursor: getComputedStyle(tr).cursor };
}, CQ_MSG);
check('E8 hovered early CQ row: early hover colour #0b2d14, default cursor', hov.bg === 'rgb(11, 45, 20)' && hov.cursor === 'default', JSON.stringify(hov));

await page.mouse.move(0, 0);   // off the table: later colour checks read the resting state, not :hover
if (SHOTS) await page.screenshot({ path: join(SHOTS, 'live-early.png') });

// ── The tracker keeps the classes when a row is marked unconfirmed or replaced by its final row ───────
// early 4 (CQ2) becomes unconfirmed; early 1 (CQ) is confirmed by a final row at index 0; 2 and 3 are unconfirmed.
inject({ type: 'decode', payload: [decode(CQ_MSG)], resolves: [
  { earlyId: 1, outcome: 'confirmed', finalIndex: 0 },
  { earlyId: 2, outcome: 'unconfirmed' },
  { earlyId: 3, outcome: 'unconfirmed' },
  { earlyId: 4, outcome: 'unconfirmed' },
] });
await page.waitForFunction(() => document.querySelectorAll('#decodes-body tr.decode-early-unconfirmed').length === 3,
  null, { timeout: STEP_TIMEOUT_MS });
const cq2 = await rowInfo(CQ2_MSG), toMe2 = await rowInfo(TO_ME_MSG);
check('U1 unconfirmed CQ row keeps decode-cq and the dark background',
  hasAll(cq2, 'decode-cq', 'decode-early-unconfirmed') && cq2.bg === 'rgb(4, 20, 10)', JSON.stringify(cq2));
check('U2 unconfirmed addressed-to-operator row keeps decode-partner and its background',
  hasAll(toMe2, 'decode-partner', 'decode-early-unconfirmed') && toMe2.bg === 'rgb(28, 7, 9)', JSON.stringify(toMe2));
const finalCq = await page.evaluate((t) => {
  const trs = [...document.querySelectorAll('#decodes-body tr')].filter((r) => r.cells[5]?.textContent.startsWith(t));
  return trs.map((tr) => ({ classes: [...tr.classList], bg: getComputedStyle(tr).backgroundColor,   // a final row's colour is on the tr
    weight: getComputedStyle(tr.cells[5]).fontWeight, cursor: tr.style.cursor }));
}, CQ_MSG);
check('F1 the confirmed early CQ row was replaced by ONE final row, unchanged look (#103115, normal weight, pointer)',
  finalCq.length === 1 && finalCq[0].classes.includes('decode-cq') && !finalCq[0].classes.includes('decode-early')
  && finalCq[0].bg === 'rgb(16, 49, 21)' && finalCq[0].weight === '400' && finalCq[0].cursor === 'pointer',
  JSON.stringify(finalCq));

if (SHOTS) await page.screenshot({ path: join(SHOTS, 'live-resolved.png') });

await browser.close();
console.log(failures === 0 ? 'ALL PASS' : `${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
