/**
 * Operator threads setting (FR-108): the Settings page's controls for decoder.threads (1 to 16, default 2), decoder.engine (classic | lean) and decoder.effort
 * (normal | fast). The pure helpers (decoderThreads.js) are imported; settings.js touches the DOM at import, so, like coherentFallbackDefault.test.js, it is
 * read as text for the wiring checks (payload, pre-fill, dirty snapshot, reset).
 *
 * Run with: node --test web/js/decoderThreads.test.js  (or: node --test web/js/*.test.js)
 */
import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  decoderEngineShown, decoderEffortShown, decoderThreadsPayload,
  DEFAULT_ENGINE, DEFAULT_EFFORT, DEFAULT_THREADS, MIN_THREADS, MAX_THREADS,
} from './decoderThreads.js';

const here     = dirname(fileURLToPath(import.meta.url));
const settings = readFileSync(join(here, 'settings.js'), 'utf8');
const html     = readFileSync(join(here, '..', 'settings.html'), 'utf8');

test('the defaults are the code defaults: classic, normal, 2 threads, range 1 to 16', () => {
  assert.equal(DEFAULT_ENGINE, 'classic');
  assert.equal(DEFAULT_EFFORT, 'normal');
  assert.equal(DEFAULT_THREADS, 2);
  assert.equal(MIN_THREADS, 1);
  assert.equal(MAX_THREADS, 16);
});

test('an absent key shows the defaults; a stored value is shown as stored', () => {
  assert.equal(decoderEngineShown(undefined), 'classic');
  assert.equal(decoderEngineShown(null), 'classic');
  assert.equal(decoderEngineShown('lean'), 'lean');
  assert.equal(decoderEngineShown('classic'), 'classic');
  assert.equal(decoderEffortShown(undefined), 'normal');
  assert.equal(decoderEffortShown('fast'), 'fast');
  assert.equal(decoderEffortShown('normal'), 'normal');
});

test('an unknown stored word shows the default (the daemon reads it as the default too); case and white space are ignored as the daemon ignores them', () => {
  assert.equal(decoderEngineShown('turbo'), 'classic');
  assert.equal(decoderEngineShown(''), 'classic');
  assert.equal(decoderEngineShown(' LEAN '), 'lean');
  assert.equal(decoderEngineShown('leanest'), 'classic');
  assert.equal(decoderEffortShown('warp'), 'normal');
  assert.equal(decoderEffortShown(' Fast '), 'fast');
  assert.equal(decoderEffortShown(42), 'normal');
});

test('the posted thread count is an integer clamped to 1 to 16; an empty or non-numeric entry posts the default', () => {
  assert.equal(decoderThreadsPayload('4'), 4);
  assert.equal(decoderThreadsPayload('1'), 1);
  assert.equal(decoderThreadsPayload('8'), 8);
  assert.equal(decoderThreadsPayload('16'), 16);
  assert.equal(decoderThreadsPayload('0'), 1);
  assert.equal(decoderThreadsPayload('-2'), 1);
  assert.equal(decoderThreadsPayload('9'), 9);
  assert.equal(decoderThreadsPayload('17'), 16);
  assert.equal(decoderThreadsPayload('300'), 16);
  assert.equal(decoderThreadsPayload('3.9'), 3);
  assert.equal(decoderThreadsPayload(''), 2);
  assert.equal(decoderThreadsPayload('abc'), 2);
});

test('the three controls exist in the Advanced Decoder Settings block, with the 1 to 16 range on the number input', () => {
  const block = html.slice(html.indexOf('id="advanced-decoder-settings"'));
  assert.match(block, /<select id="decoder-engine"/);
  assert.match(block, /<select id="decoder-effort"/);
  assert.match(block, /<input[^>]*id="decoder-threads"[^>]*min="1"[^>]*max="16"[^>]*step="1"/s);
  assert.ok(block.indexOf('id="decoder-threads"') < block.indexOf('id="decoder-reset"'), 'they sit above the reset button');
});

test('the payload carries engine, effort and threads, and so does the dirty-state snapshot', () => {
  assert.match(settings, /threads:\s*decoderThreadsPayload\(decoderThreads\.value\)/, 'the save payload');
  assert.match(settings, /engine:\s*decoderEngine\.value === _decoderEngineShown/, 'the save payload: engine');
  assert.match(settings, /effort:\s*decoderEffort\.value === _decoderEffortShown/, 'the save payload: effort');
  assert.match(settings, /threads:\s*decoderThreads\.value,/, 'the snapshot: threads');
  assert.match(settings, /engine:\s+decoderEngine\.value,/, 'the snapshot: engine');
  assert.match(settings, /effort:\s+decoderEffort\.value,/, 'the snapshot: effort');
});

test('the pre-fill uses the code defaults for an absent key, and uses ?? (nullish) so a stored value is never replaced by the default', () => {
  assert.match(settings, /decoderThreads\.value\s*=\s*String\(dec\.threads\s*\?\?\s*2\)/);
  assert.doesNotMatch(settings, /dec\.threads\s*\|\|/);
  assert.match(settings, /decoderEngineShown\(_decoderEngineLoadedRaw\)/);
  assert.match(settings, /decoderEffortShown\(_decoderEffortLoadedRaw\)/);
});

test('an unchanged select posts the stored word back (an unknown word is kept until the operator changes the select)', () => {
  assert.match(settings, /\(_decoderEngineLoadedRaw \?\? _decoderEngineShown\)/);
  assert.match(settings, /\(_decoderEffortLoadedRaw \?\? _decoderEffortShown\)/);
});

test('"Reset to defaults" restores classic, normal and 2', () => {
  const reset = settings.slice(settings.indexOf("decoderReset.addEventListener('click'"));
  const body = reset.slice(0, reset.indexOf('});'));
  assert.match(body, /decoderEngine\.value\s*=\s*'classic'/);
  assert.match(body, /decoderEffort\.value\s*=\s*'normal'/);
  assert.match(body, /decoderThreads\.value\s*=\s*'2'/);
  assert.match(body, /syncDirtyUI\(\)/, 'a reset makes the page dirty');
});

test('the host processor count comes from the daemon status (not the browser) and is shown in the help text', () => {
  assert.match(settings, /status\?\.processorCount/);
  assert.doesNotMatch(settings, /hardwareConcurrency/, 'the browser may be on another machine');
  assert.match(settings, /This PC has \$\{status\.processorCount\} logical processors\./);
  assert.match(html, /id="decoder-threads-host"/);
});

test('the help text says what more threads do, gives the measurement once with its limits, says it applies only to the lean engine, and states the maximum and the default', () => {
  const at = html.indexOf('id="decoder-threads"');
  const hint = html.slice(at, at + 2200);
  assert.match(hint, /sooner/i);
  assert.match(hint, /more CPU in total/i);
  assert.match(hint, /gentler/i);
  assert.match(hint, /16-processor test PC/);
  assert.match(hint, /2 threads/);
  assert.match(hint, /7\.6 s/);
  assert.match(hint, /8 threads/);
  assert.match(hint, /2\.7 s/);
  assert.match(hint, /24 % more CPU/);
  assert.match(hint, /Your PC will differ/);
  assert.match(hint, /only when the lean engine is selected/i);
  assert.match(hint, /maximum is 16/i);
  assert.match(hint, /Default:\s*2/);
  assert.equal((html.match(/16-processor test PC/g) ?? []).length, 1, 'the measurement is given once');
});

test('the engine and effort help say what they are, that lean is off by default, and that effort applies to lean only', () => {
  const eng = html.slice(html.indexOf('id="decoder-engine"'), html.indexOf('id="decoder-effort"'));
  assert.match(eng, /classic/);
  assert.match(eng, /lean/);
  assert.match(eng, /off by default/i);
  assert.match(eng, /Default:\s*classic/);
  const eff = html.slice(html.indexOf('id="decoder-effort"'), html.indexOf('id="decoder-threads"'));
  assert.match(eff, /only when the lean engine is selected/i);
  assert.match(eff, /fast/);
  assert.match(eff, /Default:\s*normal/);
});
