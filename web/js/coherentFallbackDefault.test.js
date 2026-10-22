/**
 * COH-FALLBACK default ON (2026-10-22): the Settings page shows the STORED value of `decoder.coherentFallbackEnabled`, and a
 * station with no stored key sees the checkbox CHECKED (same precedent as the early decode, FR-083). settings.js touches the DOM at
 * import, so, like earlyDefault.test.js, this reads it as text.
 *
 * Run with: node --test web/js/coherentFallbackDefault.test.js  (or: node --test web/js/*.test.js)
 */
import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here     = dirname(fileURLToPath(import.meta.url));
const settings = readFileSync(join(here, 'settings.js'), 'utf8');
const html     = readFileSync(join(here, '..', 'settings.html'), 'utf8');

test('the checkbox exists in the decoder section, next to the early-decode controls', () => {
  const early = html.indexOf('id="decoder-early-enabled"');
  const coh   = html.indexOf('id="decoder-coherent-fallback"');
  const cut   = html.indexOf('id="decoder-early-cut"');
  assert.ok(coh > 0, 'the checkbox exists');
  assert.ok(early > 0 && coh > early && coh < cut, 'it sits between the early-decode checkbox and the early-decode lead');
});

test('the checkbox is pre-filled from the stored value, and no stored key means CHECKED', () => {
  assert.match(settings, /decoderCoherentFallback\.checked\s*=\s*dec\.coherentFallbackEnabled\s*\?\?\s*true/);
  assert.doesNotMatch(settings, /dec\.coherentFallbackEnabled\s*\?\?\s*false/);
});

test('a stored false is shown unchecked: the pre-fill uses ?? (nullish), not ||', () => {
  assert.doesNotMatch(settings, /dec\.coherentFallbackEnabled\s*\|\|/);
});

test('the posted object carries the checkbox as it is (an operator who unticks it posts an explicit false)', () => {
  assert.match(settings, /coherentFallbackEnabled:\s*decoderCoherentFallback\.checked/);
  // both the dirty-state snapshot and the save payload carry it
  assert.equal((settings.match(/coherentFallbackEnabled:\s*decoderCoherentFallback\.checked/g) ?? []).length, 2);
});

test('"Reset to defaults" restores the default: checked', () => {
  const reset = settings.slice(settings.indexOf("decoderReset.addEventListener('click'"));
  const body = reset.slice(0, reset.indexOf('});'));
  assert.match(body, /decoderCoherentFallback\.checked\s*=\s*true/);
});

test('the help text says what it does, that it needs subtraction, that the default is ON and how to turn it off', () => {
  const at = html.indexOf('id="decoder-coherent-fallback"');
  const hint = html.slice(at, at + 1500);
  assert.match(hint, /weak signals/i);
  assert.match(hint, /extra batch/i);
  assert.match(hint, /subtraction/i);
  assert.match(hint, /next decode cycle/i);
  assert.match(hint, /Default:\s*<strong>on<\/strong>/);
  assert.match(hint, /untick/i);
  assert.doesNotMatch(hint, /Default:\s*off/i);
});
