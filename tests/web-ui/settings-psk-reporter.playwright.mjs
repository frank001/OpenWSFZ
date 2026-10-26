/**
 * FR-094..FR-096 (psk-reporter-upload, issue #262): Playwright acceptance of the Settings page's PSK Reporter control: placement at
 * the top of External Programs (1.23), the 6-character locator field, and the status line against a stubbed endpoint.
 *
 * Not part of `dotnet test` or CI (HK-007: Playwright is fetched on demand). It drives a real Chromium against a running
 * daemon, so it needs one, on an ISOLATED config and port (never the station's):
 *
 *   1. OpenWSFZ.Daemon.exe --port 18262 --config <scratch>/config.json
 *      with e.g.  { "port": 18262, "decodingEnabled": false,
 *                   "pskReporter": { "host": "pskreporter.invalid", "port": 14739 } }
 *      (the host is unresolvable on purpose, and `enabled` starts false: this script ticks the box, but the daemon then only
 *      holds a socket; the identity is the placeholder Q1OFZ, so it sends nothing anyway.)
 *   2. In a scratch directory:  npm install playwright
 *   3. BASE_URL=http://127.0.0.1:18262 SHOTS=<dir> node settings-psk-reporter.playwright.mjs
 *
 * Exit code 0 = every check passed. Each check prints PASS/FAIL. The script CHANGES the daemon's config.
 */

import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BASE  = process.env.BASE_URL ?? 'http://127.0.0.1:18262';
const SHOTS = process.env.SHOTS ?? '.';
mkdirSync(SHOTS, { recursive: true });

const here     = dirname(fileURLToPath(import.meta.url));
const expected = JSON.parse(readFileSync(
  join(here, '..', 'OpenWSFZ.Web.Tests', 'settings-payload-shape.json'), 'utf8')).shape;

const OPT_IN_TEXT = 'Sends the calls and locators of stations you receive, with your call and locator, to the public PSK Reporter service.';

let failures = 0;
function check(name, ok, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  -- ${detail}`}`);
  if (!ok) failures++;
}
const same = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
const getConfig = async (page) => (await page.request.get(`${BASE}/api/v1/config`)).json();

const browser = await chromium.launch();
const page    = await browser.newPage({ viewport: { width: 1100, height: 1300 } });
const consoleErrors = [];
page.on('console',   (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push(String(e)));

const posted = [];
page.on('request', (r) => {
  if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/v1/config')
    posted.push(JSON.parse(r.postData() ?? '{}'));
});

async function openTab() {
  const loaded = page.waitForResponse((r) => r.url().endsWith('/api/v1/config') && r.request().method() === 'GET');
  await page.goto(`${BASE}/settings.html`);
  await loaded;
  await page.waitForSelector('#psk-reporter-enabled', { state: 'attached' });
  await page.click('#tab-btn-external-programs');
  await page.waitForSelector('#psk-reporter-fieldset', { state: 'visible' });
  await page.waitForLoadState('networkidle');
}

async function saveAndWait() {
  const resp = page.waitForResponse((r) => r.url().endsWith('/api/v1/config') && r.request().method() === 'POST');
  await page.click('#save-btn');
  return (await resp).status();
}

// Precondition so the script can be re-run: opted out, no antenna text, a known host and port.
await page.request.post(`${BASE}/api/v1/config`,
  { data: { pskReporter: { enabled: false, antennaInformation: '', locator: '', host: 'pskreporter.invalid', port: 14739 } } });

// ── the control exists, carries the stated text, and shows the stored (opted-out) state ───────────
await openTab();
check('the opt-in checkbox exists and is unticked for the default (inert) configuration', (await page.isChecked('#psk-reporter-enabled')) === false);
check('the antenna field exists and is empty', (await page.inputValue('#psk-reporter-antenna')) === '');
// 1.23: the box is the FIRST box on the External Programs tab, above the GridTracker enable checkbox and its table.
const order = await page.evaluate(() => {
  const tab = document.getElementById('tab-external-programs');
  const box = document.getElementById('psk-reporter-fieldset');
  const ext = document.getElementById('ext-rep-enabled');
  const tbl = document.getElementById('ext-rep-table');
  const before = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
  return {
    firstFieldset: tab.querySelector('fieldset') === box,
    aboveCheckbox: before(box, ext),
    aboveTable:    before(box, tbl),
    boxTop:        box.getBoundingClientRect().top,
    extTop:        ext.getBoundingClientRect().top,
  };
});
check('the PSK Reporter box is the first fieldset on External Programs', order.firstFieldset, JSON.stringify(order));
check('it is above the GridTracker enable checkbox and its target table (document order and on screen)',
  order.aboveCheckbox && order.aboveTable && order.boxTop < order.extTop, JSON.stringify(order));
check('the locator field is labelled "Locator for PSK Reporter (6 characters, optional)"',
  ((await page.textContent('label[for="psk-reporter-locator"]')) ?? '').trim() === 'Locator for PSK Reporter (6 characters, optional)');
check('the locator field is empty for the default configuration', (await page.inputValue('#psk-reporter-locator')) === '');
const fieldsetText = await page.textContent('#psk-reporter-fieldset');
check('the fieldset carries the stated opt-in text', (fieldsetText ?? '').replace(/\s+/g, ' ').includes(OPT_IN_TEXT));
check('host and port are NOT on the page', (await page.$('#psk-reporter-host')) === null && (await page.$('#psk-reporter-port')) === null
  && !/report\.pskreporter\.info|4739|14739/.test(fieldsetText ?? ''));
await page.screenshot({ path: join(SHOTS, 'psk-1-default.png'), fullPage: true });

// ── tick, type, save: enabled true + the antenna text, host and port untouched ───────────────────
await page.check('#psk-reporter-enabled');
await page.fill('#psk-reporter-antenna', 'Q1 test dipole');
check('ticking the box and typing marks the form dirty', await page.isVisible('#unsaved-badge'));
posted.length = 0;
const status = await saveAndWait();
check('save returns 200', status === 200, String(status));

const body = posted.at(-1) ?? {};
check('the posted pskReporter has exactly enabled, antennaInformation and locator (no host, no port)',
  same(Object.keys(body.pskReporter ?? {}), ['enabled', 'antennaInformation', 'locator']), Object.keys(body.pskReporter ?? {}).join(','));
check('posted top-level keys equal the shared fixture', same(Object.keys(body), Object.keys(expected)), Object.keys(body).join(','));

const stored = (await getConfig(page)).pskReporter;
check('the daemon stores enabled true', stored.enabled === true, JSON.stringify(stored));
check('the daemon stores the antenna text', stored.antennaInformation === 'Q1 test dipole', JSON.stringify(stored));
check('host is unchanged', stored.host === 'pskreporter.invalid', JSON.stringify(stored));
check('port is unchanged', stored.port === 14739, JSON.stringify(stored));

// ── the locator: an invalid value is refused in the page (message, nothing posted); a valid one is stored as typed ──
for (const bad of ['JO33E', 'JO33ZZ', '1O33ab']) {
  await page.fill('#psk-reporter-locator', bad);
  posted.length = 0;
  await page.click('#save-btn');
  await page.waitForSelector('#psk-reporter-locator-error', { state: 'visible' });
  check(`an invalid locator "${bad}" is refused in the page with a message`, ((await page.textContent('#psk-reporter-locator-error')) ?? '').length > 0);
  check(`nothing is posted for "${bad}"`, posted.length === 0, JSON.stringify(posted));
}
await page.fill('#psk-reporter-locator', 'jo33ED');
posted.length = 0;
check('a valid locator saves with 200', (await saveAndWait()) === 200);
check('the posted locator is the typed text', posted.at(-1)?.pskReporter?.locator === 'jo33ED', JSON.stringify(posted.at(-1)?.pskReporter));
check('the daemon stores the locator as typed and still keeps host and port',
  (await getConfig(page)).pskReporter.locator === 'jo33ED' && (await getConfig(page)).pskReporter.host === 'pskreporter.invalid');
const rejected = await page.request.post(`${BASE}/api/v1/config`, { data: { pskReporter: { locator: 'JO33E' } } });
check('the server answers 400 for an invalid locator', rejected.status() === 400, String(rejected.status()));
check('and leaves the stored locator alone', (await getConfig(page)).pskReporter.locator === 'jo33ED');

// ── the status line shows each of its four states against a stubbed endpoint ─────────────────────
const zero = { seen: 0, reported: 0, region: 0, noDial: 0, identity: 0, hashed: 0, ownCall: 0, dedup: 0 };
const states = [
  [{ state: 'off',     lastDatagramUtc: null, lastDatagramRecords: 0, reason: null, window: zero }, 'off'],
  [{ state: 'waiting', lastDatagramUtc: null, lastDatagramRecords: 0, reason: null, window: zero }, 'on, waiting for the first datagram'],
  [{ state: 'sending', lastDatagramUtc: '2026-10-26T12:34:56Z', lastDatagramRecords: 40, reason: null, window: zero }, 'on, last datagram at 12:34:56Z with 40 records'],
  [{ state: 'refused', lastDatagramUtc: null, lastDatagramRecords: 0, reason: 'identity', window: zero }, 'on but nothing is being reported: the receiver call or grid is a placeholder'],
  [{ state: 'refused', lastDatagramUtc: null, lastDatagramRecords: 0, reason: 'no-dial', window: zero }, 'on but nothing is being reported: no dial frequency'],
  [{ state: 'refused', lastDatagramUtc: null, lastDatagramRecords: 0, reason: 'region', window: zero }, 'on but nothing is being reported: unknown region'],
];
for (const [stub, text] of states) {
  await page.route('**/api/v1/psk-reporter/status', (route) => route.fulfill({ json: stub }));
  await openTab();
  await page.waitForFunction((t) => document.getElementById('psk-reporter-status').textContent === `Status: ${t}`, text, { timeout: 5000 })
    .catch(() => {});
  const shown = (await page.textContent('#psk-reporter-status')) ?? '';
  check(`the status line shows "${text}"`, shown === `Status: ${text}`, shown);
  await page.unroute('**/api/v1/psk-reporter/status');
}
await page.screenshot({ path: join(SHOTS, 'psk-3-status.png'), fullPage: true });

// ── reload shows the stored state; an unrelated save keeps it ────────────────────────────────────
await openTab();
check('after reload the box is ticked', await page.isChecked('#psk-reporter-enabled'));
check('after reload the antenna text is shown', (await page.inputValue('#psk-reporter-antenna')) === 'Q1 test dipole');
check('after reload the locator is shown', (await page.inputValue('#psk-reporter-locator')) === 'jo33ED');
await page.screenshot({ path: join(SHOTS, 'psk-2-opted-in.png'), fullPage: true });

await page.click('#tab-btn-advanced');
await page.click('#cycle-countdown-toggle');
check('an unrelated save returns 200', (await saveAndWait()) === 200);
const after = (await getConfig(page)).pskReporter;
check('an unrelated save keeps enabled, antenna, host and port',
  after.enabled === true && after.antennaInformation === 'Q1 test dipole' && after.host === 'pskreporter.invalid' && after.port === 14739, JSON.stringify(after));

// ── untick and save: back to inert ───────────────────────────────────────────────────────────────
await openTab();
await page.uncheck('#psk-reporter-enabled');
await saveAndWait();
check('unticking and saving stores enabled false', (await getConfig(page)).pskReporter.enabled === false);

check('no console errors', consoleErrors.length === 0, consoleErrors.join(' | '));
await browser.close();
console.log(failures === 0 ? 'ALL CHECKS PASSED' : `${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
