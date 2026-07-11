/**
 * Unit tests for `resolveUnknownCheckboxDisplay` (decode-noise-suppression capability, task 6.4).
 *
 * Run with: node --test web/js/decodeNoiseSuppression.test.js  (or: node --test web/js/*.test.js)
 * No dependencies — uses Node's built-in test runner and assert module only.
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { resolveUnknownCheckboxDisplay } from './decodeNoiseSuppression.js';

test('raw null, effective false -> displays unchecked (no region data yet)', () => {
  assert.equal(resolveUnknownCheckboxDisplay(null, false), false);
});

test('raw null, effective true -> displays checked (region data now present)', () => {
  assert.equal(resolveUnknownCheckboxDisplay(null, true), true);
});

test('raw explicit false -> always displays unchecked, regardless of effective value', () => {
  assert.equal(resolveUnknownCheckboxDisplay(false, true), false);
  assert.equal(resolveUnknownCheckboxDisplay(false, false), false);
});

test('raw explicit true -> always displays checked, regardless of effective value', () => {
  assert.equal(resolveUnknownCheckboxDisplay(true, false), true);
  assert.equal(resolveUnknownCheckboxDisplay(true, true), true);
});
