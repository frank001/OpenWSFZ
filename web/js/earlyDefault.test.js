/**
 * decode-early-batch-panel (FR-083), the default flip of 2026-10-04: the Settings page shows the STORED value of
 * `decoder.earlyDecodeEnabled`, and a station with no stored key sees the checkbox CHECKED (the early decode is ON by
 * default). settings.js touches the DOM at import, so, like decodePanelBatches.test.js, this reads it as text.
 *
 * Run with: node --test web/js/earlyDefault.test.js  (or: node --test web/js/*.test.js)
 */
import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here     = dirname(fileURLToPath(import.meta.url));
const settings = readFileSync(join(here, 'settings.js'), 'utf8');
const html     = readFileSync(join(here, '..', 'settings.html'), 'utf8');

test('the checkbox is pre-filled from the stored value, and no stored key means CHECKED', () => {
  assert.match(settings, /decoderEarlyEnabled\.checked\s*=\s*dec\.earlyDecodeEnabled\s*\?\?\s*true/);
  assert.doesNotMatch(settings, /dec\.earlyDecodeEnabled\s*\?\?\s*false/);
});

test('"Reset to defaults" restores the new default: checked, lead 2', () => {
  const reset = settings.slice(settings.indexOf("decoderReset.addEventListener('click'"));
  const body = reset.slice(0, reset.indexOf('});'));
  assert.match(body, /decoderEarlyEnabled\.checked\s*=\s*true/);
  assert.match(body, /decoderEarlyCut\.value\s*=\s*'2'/);
});

test('the posted object carries the checkbox as it is (so an operator who unticks it posts an explicit false)', () => {
  assert.match(settings, /earlyDecodeEnabled:\s*decoderEarlyEnabled\.checked/);
});

test('the help text says the default is ON and how to turn it off', () => {
  const at = html.indexOf('id="decoder-early-enabled"');
  assert.ok(at > 0, 'the checkbox exists');
  const hint = html.slice(at, at + 1500);
  assert.match(hint, /Default:\s*<strong>on<\/strong>/);
  assert.match(hint, /untick/i);
  assert.doesNotMatch(hint, /Default:\s*off/i);
});
