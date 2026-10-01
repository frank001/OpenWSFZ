/**
 * T15 (config-save-preserves-unsent-settings, Part C): Playwright check of the Settings page's
 * "Audio archive" group, plus the dynamic half of T13 (the payload the page REALLY posts).
 *
 * Not part of `dotnet test` or CI: the repo has no browser-automation dependency (HK-007: Playwright
 * is fetched on demand). It drives a real Chromium against a running daemon, so it needs one:
 *
 *   1. Start a daemon on an ISOLATED config and port (never the station's):
 *        OpenWSFZ.Daemon.exe --port 18193 --config <scratch>/config.json
 *      with e.g.  { "port": 18193, "decodingEnabled": false,
 *                   "cycleAudioArchive": { "mode": "noDecodes", "directory": "<scratch>/arch" } }
 *   2. In a scratch directory:  npm install playwright   (Chromium is cached under ms-playwright)
 *   3. BASE_URL=http://127.0.0.1:18193 SHOTS=<dir for screenshots> node settings-archive.playwright.mjs
 *      (run from a directory where `playwright` resolves; NODE_PATH works too)
 *
 * Exit code 0 = every check passed. Each check prints PASS/FAIL. The screenshots are the HK-005 "after"
 * evidence. The script CHANGES the daemon's config (mode -> all), which is why it must be isolated.
 */

import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BASE  = process.env.BASE_URL ?? 'http://127.0.0.1:18193';
const SHOTS = process.env.SHOTS ?? '.';
mkdirSync(SHOTS, { recursive: true });

const here     = dirname(fileURLToPath(import.meta.url));
const expected = JSON.parse(readFileSync(
  join(here, '..', 'OpenWSFZ.Web.Tests', 'settings-payload-shape.json'), 'utf8')).shape;

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

/** Captures the body of every POST /api/v1/config the page makes. */
const posted = [];
page.on('request', (r) => {
  if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/v1/config')
    posted.push(JSON.parse(r.postData() ?? '{}'));
});

async function openLoggingTab() {
  // Register the wait BEFORE navigating: the form is populated when GET /api/v1/config returns, and
  // the HTML's own defaults are non-empty, so "the field has a value" proves nothing.
  const loaded = page.waitForResponse((r) => r.url().endsWith('/api/v1/config') && r.request().method() === 'GET');
  await page.goto(`${BASE}/settings.html`);
  await loaded;
  await page.waitForSelector('#archive-mode', { state: 'attached' });
  await page.click('#tab-btn-logging');
  await page.waitForSelector('#cycle-audio-archive-settings', { state: 'visible' });
  await page.waitForLoadState('networkidle');
}

async function saveAndWait() {
  const resp = page.waitForResponse((r) => r.url().endsWith('/api/v1/config') && r.request().method() === 'POST');
  await page.click('#save-btn');
  return (await resp).status();
}

// ── The stored config (any of the four modes) renders correctly ──────────────────────────────────
const stored = await getConfig(page);
await openLoggingTab();
check('page shows the stored archive mode', (await page.inputValue('#archive-mode')) === stored.cycleAudioArchive.mode,
  `page=${await page.inputValue('#archive-mode')} stored=${stored.cycleAudioArchive.mode}`);
const options = await page.$$eval('#archive-mode option', (os) => os.map((o) => o.value));
check('the mode selector offers all four modes', same(options, ['off', 'all', 'decoded', 'noDecodes']), options.join(','));
check('page shows the stored size cap',
  (await page.inputValue('#archive-max-size-mb')) === String(stored.cycleAudioArchive.maxSizeMb));
check('page shows the stored age cap',
  (await page.inputValue('#archive-max-age-hours')) === String(stored.cycleAudioArchive.maxAgeHours));
await page.screenshot({ path: join(SHOTS, 'after-1-stored-config.png'), fullPage: true });

// Precondition for T15, so the script can be re-run: start from mode=off. (A partial POST is a
// one-liner now that POST /api/v1/config is an overlay.)
await page.request.post(`${BASE}/api/v1/config`, { data: { cycleAudioArchive: { mode: 'off' } } });
await openLoggingTab();

// ── T15: set mode All in the UI, save, reload ─────────────────────────────────────────────────────
await page.selectOption('#archive-mode', 'all');
check('changing the mode marks the form dirty (Unsaved changes badge)', await page.isVisible('#unsaved-badge'));
posted.length = 0;
const status1 = await saveAndWait();
check('save with mode=all returns 200', status1 === 200, String(status1));
check('the daemon now stores mode=all', (await getConfig(page)).cycleAudioArchive.mode === 'all');

// T13 dynamic half: the body the page really posted has exactly the fixture's key set.
const body = posted.at(-1) ?? {};
check('posted top-level keys equal the shared fixture', same(Object.keys(body), Object.keys(expected)),
  Object.keys(body).join(','));
for (const [section, keys] of Object.entries(expected)) {
  if (keys === null) continue;
  check(`posted '${section}' keys equal the shared fixture`, same(Object.keys(body[section] ?? {}), keys),
    Object.keys(body[section] ?? {}).join(','));
}

await openLoggingTab();
check('after reload the page shows All', (await page.inputValue('#archive-mode')) === 'all');
await page.screenshot({ path: join(SHOTS, 'after-2-mode-all-after-reload.png'), fullPage: true });

// ── T15: an unrelated save keeps All ─────────────────────────────────────────────────────────────
await page.click('#tab-btn-advanced');
await page.click('#cycle-countdown-toggle');
const status2 = await saveAndWait();
check('an unrelated save returns 200', status2 === 200, String(status2));
check('the unrelated save keeps mode=all', (await getConfig(page)).cycleAudioArchive.mode === 'all');
await openLoggingTab();
check('after the second reload the page still shows All', (await page.inputValue('#archive-mode')) === 'all');

// ── every one of the four modes round-trips through the UI ───────────────────────────────────────
for (const mode of ['off', 'decoded', 'noDecodes', 'all']) {
  await openLoggingTab();
  await page.selectOption('#archive-mode', mode);
  const s = await saveAndWait();
  await openLoggingTab();
  check(`mode '${mode}' saves and reloads`, s === 200 && (await page.inputValue('#archive-mode')) === mode
    && (await getConfig(page)).cycleAudioArchive.mode === mode, `status=${s}`);
}

// ── a blank directory is sent as null ────────────────────────────────────────────────────────────
await openLoggingTab();
await page.fill('#archive-directory', '');
posted.length = 0;
await saveAndWait();
check('a blank directory is posted as null', posted.at(-1)?.cycleAudioArchive?.directory === null,
  JSON.stringify(posted.at(-1)?.cycleAudioArchive));
check('a blank directory is stored as null', (await getConfig(page)).cycleAudioArchive.directory === null);

// ── client-side bounds: a bad value is refused before any request is made ────────────────────────
await openLoggingTab();
await page.fill('#archive-max-size-mb', '0');
posted.length = 0;
await page.click('#save-btn');
await page.waitForTimeout(400);
check('maxSizeMb=0 is refused client-side (no POST)', posted.length === 0, `posts=${posted.length}`);
check('an error message is shown', ((await page.textContent('#feedback')) ?? '').includes('maximum size'));
await page.screenshot({ path: join(SHOTS, 'after-3-validation-error.png'), fullPage: true });

await page.fill('#archive-max-size-mb', '2048');
await page.fill('#archive-max-age-hours', '87601');
posted.length = 0;
await page.click('#save-btn');
await page.waitForTimeout(400);
check('maxAgeHours=87601 is refused client-side (no POST)', posted.length === 0, `posts=${posted.length}`);

check('no console errors or page errors', consoleErrors.length === 0, consoleErrors.join(' | '));

await browser.close();
if (consoleErrors.length) console.log('console errors:', consoleErrors);
console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
