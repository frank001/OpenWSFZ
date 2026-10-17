/**
 * #219: the highlight classification shared by the final-row and early-row paths (decodeRowClasses.js), and its
 * wiring in main.js (pinned as text: main.js touches the DOM at import). The live behaviour is
 * tests/web-ui/early-row-shade.playwright.mjs.
 *
 * Run with: node --test web/js/decodeRowClasses.test.js
 */
import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { classifyDecodeRow, applyDecodeRowClasses, tokenMatchesCallsign } from './decodeRowClasses.js';

const CALLER_WAIT = { txCallsign: 'Q1OFZ/P', role: 'caller', state: 'WaitAnswer', partnerSelect: 'None' };
const IDLE        = { txCallsign: 'Q1OFZ',   role: 'answerer', state: 'Idle',     partnerSelect: 'None' };

test('CQ: message starting with "CQ " only', () => {
  assert.equal(classifyDecodeRow('CQ Q2AAA AA11', IDLE).cq, true);
  assert.equal(classifyDecodeRow('CQ DX Q2AAA AA11', IDLE).cq, true);
  assert.equal(classifyDecodeRow('Q2AAA CQ AA11', IDLE).cq, false);
  assert.equal(classifyDecodeRow('CQX Q2AAA', IDLE).cq, false);
});

test('partner: any token is our callsign or its portable form; never with no callsign', () => {
  assert.equal(classifyDecodeRow('Q1OFZ Q2DDD -09', IDLE).partner, true);
  assert.equal(classifyDecodeRow('Q2DDD Q1OFZ/P R-03', IDLE).partner, true);
  assert.equal(classifyDecodeRow('Q2DDD Q2EEE -09', IDLE).partner, false);
  assert.equal(classifyDecodeRow('Q1OFZ Q2DDD -09', { ...IDLE, txCallsign: '' }).partner, false);
});

test('responder: only Caller + WaitAnswer + None + first token is us (or the base call)', () => {
  assert.equal(classifyDecodeRow('Q1OFZ/P Q2DDD JO22', CALLER_WAIT).responder, true);
  assert.equal(classifyDecodeRow('Q1OFZ Q2DDD JO22', CALLER_WAIT).responder, true);        // decoder dropped /P
  assert.equal(classifyDecodeRow('Q2DDD Q1OFZ/P -09', CALLER_WAIT).responder, false);      // not first token
  assert.equal(classifyDecodeRow('Q1OFZ Q2DDD', CALLER_WAIT).responder, false);            // fewer than 3 tokens
  assert.equal(classifyDecodeRow('Q1OFZ/P Q2DDD JO22', { ...CALLER_WAIT, state: 'Idle' }).responder, false);
  assert.equal(classifyDecodeRow('Q1OFZ/P Q2DDD JO22', { ...CALLER_WAIT, role: 'answerer' }).responder, false);
  assert.equal(classifyDecodeRow('Q1OFZ/P Q2DDD JO22', { ...CALLER_WAIT, partnerSelect: 'First' }).responder, false);
});

test('tokenMatchesCallsign: exact or "/suffix"', () => {
  assert.equal(tokenMatchesCallsign('Q1OFZ', 'Q1OFZ'), true);
  assert.equal(tokenMatchesCallsign('Q1OFZ/P', 'Q1OFZ'), true);
  assert.equal(tokenMatchesCallsign('Q1OFZX', 'Q1OFZ'), false);
});

test('applyDecodeRowClasses adds exactly the chosen classes', () => {
  const added = [];
  const tr = { classList: { add: (...c) => added.push(...c) } };
  applyDecodeRowClasses(tr, { cq: true, partner: false, responder: true });
  assert.deepEqual(added, ['decode-cq', 'decode-responder']);
});

// ── wiring, pinned as text ────────────────────────────────────────────────────────────────────────────────
const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'main.js'), 'utf8');
function functionBody(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `main.js: function ${name} not found`);
  const next = source.indexOf('\n}\n', start);
  return source.slice(start, next);
}

test('handleEarlyDecodes and handleDecodes both classify through the shared helper', () => {
  for (const fn of ['handleEarlyDecodes', 'handleDecodes']) {
    const body = functionBody(fn);
    assert.match(body, /classifyDecodeRow\(\s*r\.message,\s*decodeRowContext\(\)\s*\)/, fn);
    assert.match(body, /applyDecodeRowClasses\(/, fn);
  }
});

test('handleEarlyDecodes stays display-only: no listener, no pointer cursor', () => {
  const body = functionBody('handleEarlyDecodes');
  assert.doesNotMatch(body, /addEventListener/);
  assert.doesNotMatch(body, /style\.cursor/);
});

test('main.js no longer carries its own copy of the classification', () => {
  assert.doesNotMatch(source, /function tokenMatchesCallsign\(/);
  assert.doesNotMatch(source, /startsWith\('CQ '\)/);
});
