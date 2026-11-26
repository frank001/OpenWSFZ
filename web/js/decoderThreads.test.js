/**
 * Operator threads setting (FR-108): the Settings page's controls for decoder.threads (1 to 16 explicit; 0 or absent = automatic = min(logical processors, 16)),
 * decoder.engine (classic | lean) and decoder.effort (normal | fast). The pure helpers (decoderThreads.js) are imported; settings.js touches the DOM at import,
 * so, like coherentFallbackDefault.test.js, it is read as text for the wiring checks (payload, pre-fill, dirty snapshot, reset).
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
  decoderThreadsLoaded, decoderThreadsAutoHint, decoderChoicePayload, autoThreadsValue,
  DEFAULT_ENGINE, DEFAULT_EFFORT, AUTO_THREADS, FALLBACK_SHOWN_THREADS, MIN_THREADS, MAX_THREADS,
} from './decoderThreads.js';

const here     = dirname(fileURLToPath(import.meta.url));
const settings = readFileSync(join(here, 'settings.js'), 'utf8');
const html     = readFileSync(join(here, '..', 'settings.html'), 'utf8');

test('the defaults are the code defaults: lean, normal, automatic threads (0), range 1 to 16, fallback display 2', () => {
  assert.equal(DEFAULT_ENGINE, 'lean');
  assert.equal(DEFAULT_EFFORT, 'normal');
  assert.equal(AUTO_THREADS, 0);
  assert.equal(FALLBACK_SHOWN_THREADS, 2);
  assert.equal(MIN_THREADS, 1);
  assert.equal(MAX_THREADS, 16);
});

test('an absent key shows the defaults; a stored value is shown as stored', () => {
  assert.equal(decoderEngineShown(undefined), 'lean', 'DR-3: lean is the default');
  assert.equal(decoderEngineShown(null), 'lean');
  assert.equal(decoderEngineShown('lean'), 'lean');
  assert.equal(decoderEngineShown('classic'), 'classic');
  assert.equal(decoderEffortShown(undefined), 'normal');
  assert.equal(decoderEffortShown('fast'), 'fast');
  assert.equal(decoderEffortShown('normal'), 'normal');
});

test('an unknown stored word shows the default (the daemon reads it as the default too); case and white space are ignored as the daemon ignores them', () => {
  assert.equal(decoderEngineShown('turbo'), 'lean');
  assert.equal(decoderEngineShown(''), 'lean');
  assert.equal(decoderEngineShown(' LEAN '), 'lean');
  assert.equal(decoderEngineShown(' Classic '), 'classic');
  assert.equal(decoderEngineShown('classical'), 'lean');
  assert.equal(decoderEffortShown('warp'), 'normal');
  assert.equal(decoderEffortShown(' Fast '), 'fast');
  assert.equal(decoderEffortShown(42), 'normal');
});

test('an automatic field posts 0 whatever it shows; a touched field posts its integer clamped to 1 to 16; an empty or non-numeric entry is automatic', () => {
  assert.equal(decoderThreadsPayload('16', true), 0, 'untouched: the shown auto value is not posted');
  assert.equal(decoderThreadsPayload('2', true), 0);
  assert.equal(decoderThreadsPayload('16', false), 16, 'touched to the number that equals the auto value: explicit');
  assert.equal(decoderThreadsPayload('6', false), 6);
  assert.equal(decoderThreadsPayload('1', false), 1);
  assert.equal(decoderThreadsPayload('0', false), MIN_THREADS);
  assert.equal(decoderThreadsPayload('-4', false), MIN_THREADS);
  assert.equal(decoderThreadsPayload('17', false), MAX_THREADS);
  assert.equal(decoderThreadsPayload('300', false), MAX_THREADS);
  assert.equal(decoderThreadsPayload('3.9', false), 3);
  assert.equal(decoderThreadsPayload('', false), 0);
  assert.equal(decoderThreadsPayload('abc', false), 0);
});

test('a stored explicit value is shown and saved as stored; a stored 0 or an absent key shows the auto value and is automatic', () => {
  const six = decoderThreadsLoaded(6, 16);
  assert.deepEqual(six, { auto: false, value: 6 });
  assert.equal(decoderThreadsPayload(String(six.value), six.auto), 6, 'a stored 6 is saved as 6');
  assert.deepEqual(decoderThreadsLoaded(2, 16), { auto: false, value: 2 }, 'a stored 2 (written by an earlier save) stays explicit');
  assert.deepEqual(decoderThreadsLoaded(0, 12), { auto: true, value: 12 });
  assert.deepEqual(decoderThreadsLoaded(undefined, 12), { auto: true, value: 12 });
  assert.deepEqual(decoderThreadsLoaded(null, 64), { auto: true, value: 16 }, 'the auto value is capped at 16');
  assert.deepEqual(decoderThreadsLoaded(20, 64), { auto: false, value: 16 }, 'an oversize stored value is shown as the daemon clamps it, never as auto');
  assert.deepEqual(decoderThreadsLoaded(-3, 64), { auto: false, value: 1 });
  const untouched = decoderThreadsLoaded(undefined, 12);
  assert.equal(decoderThreadsPayload(String(untouched.value), untouched.auto), 0, 'an untouched save writes no number');
});

test('a missing processor count falls back to showing 2 without error, and says nothing else', () => {
  assert.deepEqual(decoderThreadsLoaded(undefined, undefined), { auto: true, value: 2 });
  assert.deepEqual(decoderThreadsLoaded(0, null), { auto: true, value: 2 });
  assert.deepEqual(decoderThreadsLoaded(0, 0), { auto: true, value: 2 });
  assert.equal(autoThreadsValue(undefined), null);
  assert.equal(decoderThreadsAutoHint(undefined), '');
});

test('the Automatic hint names the logical processors, the thread count and the maximum', () => {
  assert.equal(decoderThreadsAutoHint(8), 'Automatic: this PC has 8 logical processors, so 8 threads (maximum 16).');
  assert.equal(decoderThreadsAutoHint(64), 'Automatic: this PC has 64 logical processors, so 16 threads (maximum 16).');
});

test('engine and effort: a changed select posts its choice; an unchanged one posts the stored word, or nothing when none was stored', () => {
  assert.equal(decoderChoicePayload('classic', 'lean', null), 'classic', 'a changed select posts its choice');
  assert.equal(decoderChoicePayload('lean', 'lean', null), undefined, 'never stored: an untouched save posts no engine');
  assert.equal(decoderChoicePayload('classic', 'classic', 'classic'), 'classic', 'stored: sent back as stored');
  assert.equal(decoderChoicePayload('lean', 'lean', 'Bogus'), 'Bogus', 'an unknown stored word is kept');
  assert.equal(JSON.stringify({ engine: undefined, effort: undefined, threads: 0 }), '{"threads":0}', 'undefined is dropped from the body');
});

test('the three controls exist in the Advanced Decoder Settings block, with the 1 to 16 range on the number input', () => {
  const block = html.slice(html.indexOf('id="advanced-decoder-settings"'));
  assert.match(block, /<select id="decoder-engine"/);
  assert.match(block, /<select id="decoder-effort"/);
  assert.match(block, /<input[^>]*id="decoder-threads"[^>]*min="1"[^>]*max="16"[^>]*step="1"/s);
  assert.match(block, /id="decoder-threads-auto"/, 'the Automatic hint');
  assert.ok(block.indexOf('id="decoder-threads"') < block.indexOf('id="decoder-reset"'), 'they sit above the reset button');
});

test('the payload carries engine, effort and threads, and so does the dirty-state snapshot', () => {
  assert.match(settings, /threads:\s*decoderThreadsPayload\(decoderThreads\.value, _decoderThreadsAuto\)/, 'the save payload');
  assert.match(settings, /engine:\s*decoderChoicePayload\(decoderEngine\.value, _decoderEngineShown, _decoderEngineLoadedRaw\)/, 'the save payload: engine');
  assert.match(settings, /effort:\s*decoderChoicePayload\(decoderEffort\.value, _decoderEffortShown, _decoderEffortLoadedRaw\)/, 'the save payload: effort');
  assert.match(settings, /threads:\s*\(_decoderThreadsAuto \? 'auto:' : 'set:'\) \+ decoderThreads\.value,/, 'the snapshot: threads (a change of mode alone makes the page dirty)');
  assert.match(settings, /engine:\s+decoderEngine\.value,/, 'the snapshot: engine');
  assert.match(settings, /effort:\s+decoderEffort\.value,/, 'the snapshot: effort');
});

test('the pre-fill resolves the stored value (never replacing it with a default via ||) and the engine and effort words', () => {
  assert.match(settings, /decoderThreadsLoaded\(dec\.threads, _hostProcessorCount\)/);
  assert.match(settings, /decoderThreads\.value\s*=\s*String\(threadsLoaded\.value\)/);
  assert.doesNotMatch(settings, /dec\.threads\s*\|\|/);
  assert.match(settings, /decoderEngineShown\(_decoderEngineLoadedRaw\)/);
  assert.match(settings, /decoderEffortShown\(_decoderEffortLoadedRaw\)/);
});

test('touched vs loaded: only an input event on the field clears the automatic flag; a load and a reset set it (a programmatic .value assignment fires no input event)', () => {
  assert.match(settings, /decoderThreads\.addEventListener\('input',\s*\(\) => \{\s*_decoderThreadsAuto = false;/);
  assert.match(settings, /_decoderThreadsAuto = threadsLoaded\.auto;/);
});

test('"Reset to defaults" restores lean, normal and automatic threads (not 2)', () => {
  const reset = settings.slice(settings.indexOf("decoderReset.addEventListener('click'"));
  const body = reset.slice(0, reset.indexOf('});'));
  assert.match(body, /decoderEngine\.value\s*=\s*'lean'/);
  assert.match(body, /decoderEffort\.value\s*=\s*'normal'/);
  assert.match(body, /_decoderThreadsAuto = true;/);
  assert.doesNotMatch(body, /decoderThreads\.value\s*=\s*'2'/);
  assert.match(body, /syncDirtyUI\(\)/, 'a reset makes the page dirty');
});

test('the host processor count comes from the daemon status (not the browser) and is shown in the help text', () => {
  assert.match(settings, /status\?\.processorCount/);
  assert.doesNotMatch(settings, /hardwareConcurrency/, 'the browser may be on another machine');
  assert.match(settings, /This PC has \$\{status\.processorCount\} logical processors\./);
  assert.match(html, /id="decoder-threads-host"/);
});

test('the help text says what more threads do, gives the measurement once with its limits, the memory cost, automatic, lean-only, the maximum and the default', () => {
  const at = html.indexOf('id="decoder-threads"');
  const hint = html.slice(at, at + 2800);
  assert.match(hint, /sooner/i);
  assert.match(hint, /more CPU in total/i);
  assert.match(hint, /gentler/i);
  assert.match(hint, /16-processor test PC/);
  assert.match(hint, /2 threads, last results about 7\.6 s/);
  assert.match(hint, /4 threads, 4\.4 s/);
  assert.match(hint, /8 threads, 2\.7 s/);
  assert.match(hint, /10 % each time the count doubles/);
  assert.match(hint, /Your PC will differ/);
  assert.match(hint, /32 MB/);
  assert.match(hint, /0\.5 GB/);
  assert.match(hint, /Automatic uses every logical processor up to 16\. Lower it if this PC also runs other programs\./);
  assert.match(hint, /only when the lean engine is selected/i);
  assert.match(hint, /maximum is 16/i);
  assert.match(hint, /Default:\s*automatic/);
  assert.equal((html.match(/16-processor test PC/g) ?? []).length, 1, 'the measurement is given once');
});

test('the engine and effort help say what they are, that lean is the default, and that effort applies to lean only', () => {
  const eng = html.slice(html.indexOf('id="decoder-engine"'), html.indexOf('id="decoder-effort"'));
  assert.match(eng, /classic/);
  assert.match(eng, /lean/);
  assert.doesNotMatch(eng, /off by default/i, 'DR-3: lean is no longer off by default');
  assert.match(eng, /Default:\s*lean/);
  const eff = html.slice(html.indexOf('id="decoder-effort"'), html.indexOf('id="decoder-threads"'));
  assert.match(eff, /only when the lean engine is selected/i);
  assert.match(eff, /fast/);
  assert.match(eff, /Default:\s*normal/);
});
