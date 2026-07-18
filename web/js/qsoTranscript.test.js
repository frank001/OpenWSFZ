/**
 * Unit tests for the qso-transcript-panel (FR-062) DOM-free module — mirrors
 * `decodeFilter.test.js`'s structure and precedent (design.md Decision 7).
 *
 * Run with: node --test web/js/qsoTranscript.test.js  (or: node --test web/js/*.test.js)
 * No dependencies — uses Node's built-in test runner and assert module only.
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import {
  shouldCaptureDecode,
  buildTranscriptEntry,
  pushTranscriptEntry,
  hasEnteredNewActiveTxState,
  TRANSCRIPT_LOG_MAX,
} from './qsoTranscript.js';

// ── shouldCaptureDecode ──────────────────────────────────────────────────

test('matches a message containing the operator\'s own callsign', () => {
  assert.equal(shouldCaptureDecode('Q2XYZ Q1OFZ R+00', 'Q1OFZ', 'Q2XYZ'), true);
});

test('matches a message containing only the active partner callsign', () => {
  assert.equal(shouldCaptureDecode('Q1OFZ Q2XYZ +05', 'Q1OFZ', 'Q2XYZ'), true);
});

test('does not match unrelated traffic naming neither callsign', () => {
  assert.equal(shouldCaptureDecode('Q3ABC Q4DEF JO22', 'Q1OFZ', 'Q2XYZ'), false);
});

test('matches a portable-suffixed operator callsign (e.g. "Q1OFZ/P")', () => {
  assert.equal(shouldCaptureDecode('Q2XYZ Q1OFZ/P R+00', 'Q1OFZ', 'Q2XYZ'), true);
});

test('matches a portable-suffixed partner callsign', () => {
  assert.equal(shouldCaptureDecode('Q1OFZ Q2XYZ/P +05', 'Q1OFZ', 'Q2XYZ'), true);
});

test('does not false-positive on a callsign that merely starts with the same letters', () => {
  // "Q1OFZZ" must not match "Q1OFZ" — exact token or "callsign/" prefix only. Neither the
  // operator's callsign nor the tracked partner appears verbatim anywhere in this message.
  assert.equal(shouldCaptureDecode('Q3ABC Q1OFZZ R+00', 'Q1OFZ', 'Q2XYZ'), false);
});

// ── Idle-state permissive case (design.md Decision 3, last paragraph) ───

test('idle state (currentPartner null): a message matching only the operator callsign still qualifies', () => {
  assert.equal(shouldCaptureDecode('CQ Q1OFZ JO33', 'Q1OFZ', null), true);
});

test('idle state (currentPartner null): unrelated traffic is still rejected', () => {
  assert.equal(shouldCaptureDecode('CQ Q3ABC JO22', 'Q1OFZ', null), false);
});

test('empty message never matches', () => {
  assert.equal(shouldCaptureDecode('', 'Q1OFZ', 'Q2XYZ'), false);
});

// ── buildTranscriptEntry ─────────────────────────────────────────────────

test('buildTranscriptEntry constructs an entry with the given kind/text/partner', () => {
  const entry = buildTranscriptEntry('sent', 'Q2XYZ Q1OFZ R+00', 'Q2XYZ');
  assert.equal(entry.kind, 'sent');
  assert.equal(entry.text, 'Q2XYZ Q1OFZ R+00');
  assert.equal(entry.partner, 'Q2XYZ');
  assert.match(entry.isoTs, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$/);
});

test('buildTranscriptEntry defaults partner to null when omitted', () => {
  const entry = buildTranscriptEntry('abort', 'Timeout waiting for reply');
  assert.equal(entry.partner, null);
});

// ── pushTranscriptEntry ───────────────────────────────────────────────────

test('pushTranscriptEntry unshifts newest entry to the front', () => {
  const log = [{ text: 'older' }];
  pushTranscriptEntry(log, { text: 'newer' }, 100);
  assert.deepEqual(log.map(e => e.text), ['newer', 'older']);
});

test('pushTranscriptEntry truncates the oldest entries once the cap is exceeded', () => {
  const log = [];
  for (let i = 0; i < 5; i++) pushTranscriptEntry(log, { text: `entry${i}` }, 3);
  assert.equal(log.length, 3);
  // Newest (entry4) on top; oldest two (entry0, entry1) dropped.
  assert.deepEqual(log.map(e => e.text), ['entry4', 'entry3', 'entry2']);
});

test('TRANSCRIPT_LOG_MAX is 100 (design.md Decision 5)', () => {
  assert.equal(TRANSCRIPT_LOG_MAX, 100);
});

test('pushTranscriptEntry enforces TRANSCRIPT_LOG_MAX exactly at the boundary', () => {
  const log = [];
  for (let i = 0; i < TRANSCRIPT_LOG_MAX + 1; i++)
    pushTranscriptEntry(log, { text: `entry${i}` }, TRANSCRIPT_LOG_MAX);
  assert.equal(log.length, TRANSCRIPT_LOG_MAX);
  assert.equal(log[0].text, `entry${TRANSCRIPT_LOG_MAX}`);
});

// ── hasEnteredNewActiveTxState ────────────────────────────────────────────

const answererActiveStates = ['TxAnswer', 'TxReport', 'Tx73'];

test('fires when transitioning from Idle into an active state', () => {
  assert.equal(hasEnteredNewActiveTxState('Idle', 'TxAnswer', answererActiveStates), true);
});

test('does not fire on a repeated push of the same state', () => {
  assert.equal(hasEnteredNewActiveTxState('TxAnswer', 'TxAnswer', answererActiveStates), false);
});

test('does not fire when the new state is not a member of activeStates', () => {
  assert.equal(hasEnteredNewActiveTxState('TxAnswer', 'WaitReport', answererActiveStates), false);
});

test('fires again on a retried transmission (re-entering an active state from a different prior state)', () => {
  // TxReport was left for WaitRr73, then timed out back to TxReport — a real retry.
  assert.equal(hasEnteredNewActiveTxState('WaitRr73', 'TxReport', answererActiveStates), true);
});

test('fires for the caller role\'s activeStates set too', () => {
  const callerActiveStates = ['TxCq', 'TxReport', 'TxRr73'];
  assert.equal(hasEnteredNewActiveTxState('Idle', 'TxCq', callerActiveStates), true);
});
