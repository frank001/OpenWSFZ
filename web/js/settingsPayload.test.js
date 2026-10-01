/**
 * T13 (config-save-preserves-unsent-settings): payload contract for web/js/settings.js.
 *
 * `POST /api/v1/config` applies the body as an overlay, so a key the Settings page stops sending
 * is silently kept rather than reset — which is safe, but means a payload change can pass unnoticed.
 * This test pins the exact key set the page posts: the object passed to `postConfig({...})` and each
 * nested object literal built for it, read straight from settings.js. It compares that with
 * tests/OpenWSFZ.Web.Tests/settings-payload-shape.json, the same file the C# fixture
 * (ConfigSaveOverlayTests / SettingsPayload) loads. A payload change without a fixture change fails.
 *
 * Run with: node --test web/js/settingsPayload.test.js  (or: node --test web/js/*.test.js)
 * No dependencies — Node's built-in test runner only. settings.js is read as TEXT, not imported: it
 * touches the DOM at module load. Playwright test T15 (tests/web-ui/) captures the payload the page
 * really posts, as the dynamic cross-check of this static reading.
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here     = dirname(fileURLToPath(import.meta.url));
const source   = readFileSync(join(here, 'settings.js'), 'utf8');
const expected = JSON.parse(
  readFileSync(join(here, '..', '..', 'tests', 'OpenWSFZ.Web.Tests', 'settings-payload-shape.json'), 'utf8')
).shape;

/**
 * Returns the text between the `{` at `openIndex` and its matching `}`, skipping string literals,
 * template literals and comments so a brace or comma inside one cannot confuse the count.
 */
function braceBody(text, openIndex) {
  assert.equal(text[openIndex], '{');
  let depth = 0;
  for (let i = openIndex; i < text.length; i++) {
    const c = text[i];
    if (c === '/' && text[i + 1] === '/') { i = text.indexOf('\n', i); if (i < 0) break; continue; }
    if (c === '/' && text[i + 1] === '*') { i = text.indexOf('*/', i) + 1; continue; }
    if (c === '\'' || c === '"' || c === '`') {
      const q = c;
      for (i++; i < text.length && text[i] !== q; i++) if (text[i] === '\\') i++;
      continue;
    }
    if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return text.slice(openIndex + 1, i);
  }
  throw new Error('unbalanced braces');
}

/**
 * The keys at depth 0 of an object-literal body. Handles `key: value`, shorthand `key`, quoted keys
 * and `...spread` (returned as `...name` so the caller can resolve it).
 */
function topLevelKeys(body) {
  const keys = [];
  let depth = 0, start = 0;
  const flush = (end) => {
    const part = body.slice(start, end).replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').trim();
    start = end + 1;
    if (!part) return;
    const spread = /^\.\.\.\s*([A-Za-z_$][\w$]*)/.exec(part);
    if (spread) { keys.push('...' + spread[1]); return; }
    const m = /^(?:['"]([^'"]+)['"]|([A-Za-z_$][\w$]*))\s*(?::|$)/.exec(part);
    assert.ok(m, `cannot read a key from: ${part.slice(0, 60)}`);
    keys.push(m[1] ?? m[2]);
  };
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c === '/' && body[i + 1] === '/') { i = body.indexOf('\n', i); if (i < 0) break; continue; }
    if (c === '/' && body[i + 1] === '*') { i = body.indexOf('*/', i) + 1; continue; }
    if (c === '\'' || c === '"' || c === '`') {
      const q = c;
      for (i++; i < body.length && body[i] !== q; i++) if (body[i] === '\\') i++;
      continue;
    }
    if (c === '{' || c === '[' || c === '(') depth++;
    else if (c === '}' || c === ']' || c === ')') depth--;
    else if (c === ',' && depth === 0) flush(i);
  }
  flush(body.length);
  return keys;
}

// The save handler is the only place the payload is built.
const saveStart   = source.indexOf("saveBtn.addEventListener('click'");
assert.ok(saveStart > 0, "settings.js: save handler not found");
const saveHandler = source.slice(saveStart);

/** Key set of `const <name> = { ... }` inside the save handler (spreads resolved). */
function sectionKeys(name) {
  const m = new RegExp(`const\\s+${name}\\s*=\\s*\\{`).exec(saveHandler);
  assert.ok(m, `settings.js: 'const ${name} = {' not found in the save handler`);
  const body = braceBody(saveHandler, m.index + m[0].length - 1);
  return topLevelKeys(body).flatMap((k) => (k.startsWith('...') ? spreadKeys(k.slice(3)) : [k]));
}

/** Keys carried by a `...spread` of a module-level object (only catOpaqueFields exists today). */
function spreadKeys(name) {
  const keys = new Set();
  const re = new RegExp(`${name}\\s*=\\s*\\{`, 'g');
  let m;
  while ((m = re.exec(source)) !== null) {
    topLevelKeys(braceBody(source, m.index + m[0].length - 1)).forEach((k) => keys.add(k));
  }
  assert.ok(keys.size > 0, `settings.js: no object literal assigned to '${name}'`);
  return [...keys];
}

// Top-level keys: the literal passed to postConfig({...}).
const postCall = /postConfig\(\s*\{/.exec(saveHandler);
assert.ok(postCall, 'settings.js: postConfig({...}) call not found');
const postedKeys = topLevelKeys(braceBody(saveHandler, postCall.index + postCall[0].length - 1));

const sorted = (a) => [...a].sort();

test('the top-level key set posted by settings.js equals the shared fixture', () => {
  assert.deepEqual(sorted(postedKeys), sorted(Object.keys(expected)),
    'settings.js posts a different set of top-level keys than tests/OpenWSFZ.Web.Tests/settings-payload-shape.json. ' +
    'Update both together (and check ConfigSaveOverlayTests).');
});

for (const [section, keys] of Object.entries(expected)) {
  if (keys === null) continue; // scalar leaf: covered by the top-level test
  test(`the '${section}' object posted by settings.js has exactly the fixture's keys`, () => {
    assert.deepEqual(sorted(sectionKeys(section)), sorted(keys));
  });
}

test('the fixture describes the Part C archive group in full (all five fields)', () => {
  assert.deepEqual(sorted(expected.cycleAudioArchive),
    ['directory', 'maxAgeHours', 'maxSizeMb', 'mode', 'writeManifest']);
});
