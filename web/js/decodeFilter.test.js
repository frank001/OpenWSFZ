/**
 * Unit tests for `isDecodeVisible` (decode-panel-filtering capability, task 5.1) — the JS twin
 * of `DecodeFilterEvaluatorTests.cs`. Cases are mirrored 1:1 with the C# suite wherever the
 * scenario translates directly, per design.md Decision 2's drift-risk mitigation ("mirrored
 * unit tests on both sides against the same set of representative (decode, filterState) →
 * visible cases").
 *
 * Run with: node --test web/js/decodeFilter.test.js  (or: node --test web/js/*.test.js)
 * No dependencies — uses Node's built-in test runner and assert module only.
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { isDecodeVisible, UNFILTERED_DECODE_FILTER } from './decodeFilter.js';

/** @param {object} [overrides] */
function makeDecode(overrides = {}) {
  return {
    time: '12:00:00', snr: 0, dt: 0.0, freqHz: 1000, message: 'CQ Q1TST JO22',
    region: null, workedBefore: null,
    ...overrides,
  };
}

const monacoEu = { continent: 'EU', entity: 'Monaco', synthetic: false, cqZone: 14, ituZone: 27 };

const workedBeforeNone = { contact: 'never', country: 'never', continent: 'never', cqZone: 'never', ituZone: 'never' };

// ── Unfiltered default ───────────────────────────────────────────────────

test('Unfiltered passes everything including null region and workedBefore', () => {
  assert.equal(isDecodeVisible(makeDecode(), UNFILTERED_DECODE_FILTER), true);
});

test('Unfiltered passes a fully resolved decode', () => {
  const decode = makeDecode({ region: monacoEu, workedBefore: workedBeforeNone });
  assert.equal(isDecodeVisible(decode, UNFILTERED_DECODE_FILTER), true);
});

// ── Attribute allow-list axes — independently ────────────────────────────

test('allowedEntities excludes a resolved entity not in the set', () => {
  const decode = makeDecode({ region: monacoEu });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedEntities: ['Germany'] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

test('allowedEntities passes a resolved entity in the set', () => {
  const decode = makeDecode({ region: monacoEu });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedEntities: ['Monaco'] };
  assert.equal(isDecodeVisible(decode, filter), true);
});

test('allowedContinents excludes a resolved continent not in the set', () => {
  const decode = makeDecode({ region: monacoEu });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedContinents: ['NA'] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

test('allowedCqZones excludes a resolved zone not in the set', () => {
  const decode = makeDecode({ region: monacoEu });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedCqZones: [5] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

test('allowedItuZones excludes a resolved zone not in the set', () => {
  const decode = makeDecode({ region: monacoEu });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedItuZones: [1] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

test('an explicit empty allow-list filters everything on that axis', () => {
  const decode = makeDecode({ region: monacoEu });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedEntities: [] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

// ── Fail-open on unresolved attribute values ─────────────────────────────

test('null region is never excluded by an active entity allow-list', () => {
  const decode = makeDecode({ region: null });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedEntities: ['Germany'] };
  assert.equal(isDecodeVisible(decode, filter), true);
});

test('null continent on a resolved region is never excluded by an active continent allow-list', () => {
  const decode = makeDecode({ region: { continent: null, entity: 'Synthetic (R&R Study)', synthetic: true } });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedContinents: ['EU'] };
  assert.equal(isDecodeVisible(decode, filter), true);
});

test('null cqZone on a resolved region is never excluded by an active cqZone allow-list', () => {
  const decode = makeDecode({ region: { continent: 'EU', entity: 'Monaco', synthetic: false, cqZone: null, ituZone: 27 } });
  const filter = { ...UNFILTERED_DECODE_FILTER, allowedCqZones: [5] };
  assert.equal(isDecodeVisible(decode, filter), true);
});

// ── Worked-before tri-state axes ─────────────────────────────────────────

test('contactStates excludes a resolved state not in the set', () => {
  const decode = makeDecode({ workedBefore: { ...workedBeforeNone, contact: 'thisBand' } });
  const filter = { ...UNFILTERED_DECODE_FILTER, contactStates: ['never', 'differentBand'] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

test('contactStates passes a resolved state in the set', () => {
  const decode = makeDecode({ workedBefore: { ...workedBeforeNone, contact: 'thisBand' } });
  const filter = { ...UNFILTERED_DECODE_FILTER, contactStates: ['thisBand'] };
  assert.equal(isDecodeVisible(decode, filter), true);
});

test('absent workedBefore is treated as Never and filtered when Never is excluded', () => {
  const decode = makeDecode({ workedBefore: null });
  const filter = { ...UNFILTERED_DECODE_FILTER, contactStates: ['differentBand', 'thisBand'] };
  assert.equal(isDecodeVisible(decode, filter), false);
});

test('absent workedBefore passes when Never is included in an active filter', () => {
  const decode = makeDecode({ workedBefore: null });
  const filter = { ...UNFILTERED_DECODE_FILTER, contactStates: ['never'] };
  assert.equal(isDecodeVisible(decode, filter), true);
});

for (const axis of ['countryStates', 'continentStates', 'cqZoneStates', 'ituZoneStates']) {
  test(`every worked-before axis independently excludes Never when active (${axis})`, () => {
    const decode = makeDecode({ workedBefore: workedBeforeNone }); // all 'never'
    const filter = { ...UNFILTERED_DECODE_FILTER, [axis]: ['thisBand'] };
    assert.equal(isDecodeVisible(decode, filter), false);
  });
}

// ── Combinations ──────────────────────────────────────────────────────────

test('a decode passing all active axes is visible', () => {
  const decode = makeDecode({
    region:       monacoEu,
    workedBefore: { ...workedBeforeNone, contact: 'differentBand' },
  });
  const filter = {
    allowedEntities:   ['Monaco', 'Germany'],
    allowedContinents: ['EU'],
    allowedCqZones:    [14],
    allowedItuZones:   [27],
    contactStates:     ['never', 'differentBand'],
    countryStates:     null,
    continentStates:   null,
    cqZoneStates:      null,
    ituZoneStates:     null,
  };
  assert.equal(isDecodeVisible(decode, filter), true);
});

test('a decode failing any single active axis among several is not visible', () => {
  const decode = makeDecode({
    region:       monacoEu,
    workedBefore: { ...workedBeforeNone, contact: 'thisBand' },
  });
  // Every axis passes except contactStates, which excludes thisBand.
  const filter = {
    allowedEntities:   ['Monaco'],
    allowedContinents: ['EU'],
    allowedCqZones:    [14],
    allowedItuZones:   [27],
    contactStates:     ['never', 'differentBand'],
    countryStates:     null,
    continentStates:   null,
    cqZoneStates:      null,
    ituZoneStates:     null,
  };
  assert.equal(isDecodeVisible(decode, filter), false);
});
