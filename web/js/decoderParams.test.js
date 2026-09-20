/**
 * Unit tests for the read-only decoder-parameter page's data shaping (decoder-param-readout,
 * shim 20260054, FR-070). Only the pure, exported functions are exercised here; the DOM rendering
 * is verified with Playwright against a running daemon (tasks.md 7.2), because this project has no
 * DOM library.
 *
 * Run with: node --test web/js/decoderParams.test.js  (or: node --test web/js/*.test.js)
 * No dependencies — uses Node's built-in test runner and assert module only.
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import {
  KIND_RUNTIME, KIND_COMPILE_TIME,
  groupEntries, formatValue, differsFromDefault, rowModel,
} from './decoderParams.js';

const runtimeNhard = { name: 'osd_nhard_max',     kind: 'runtime',      value: 40,  default: 60 };
const runtimeCorr  = { name: 'osd_corr_threshold', kind: 'runtime',     value: 0.1, default: 0.1 };
const compilePass  = { name: 'K_MAX_PASSES',      kind: 'compile-time', value: 2,   default: 2 };
const compileCands = { name: 'K_MAX_CANDIDATES',  kind: 'compile-time', value: 140, default: 140 };

test('FR-070: the kind constants are the API\'s wire values', () => {
  assert.equal(KIND_RUNTIME, 'runtime');
  assert.equal(KIND_COMPILE_TIME, 'compile-time');
});

test('FR-070: groupEntries splits into the two groups and keeps the native order within each', () => {
  const { runtime, compileTime } = groupEntries([runtimeNhard, compilePass, runtimeCorr, compileCands]);
  assert.deepEqual(runtime.map(e => e.name),     ['osd_nhard_max', 'osd_corr_threshold']);
  assert.deepEqual(compileTime.map(e => e.name), ['K_MAX_PASSES', 'K_MAX_CANDIDATES']);
});

test('FR-070: groupEntries loses no entry (every input lands in exactly one group)', () => {
  const all = [runtimeNhard, compilePass, runtimeCorr, compileCands];
  const { runtime, compileTime } = groupEntries(all);
  assert.equal(runtime.length + compileTime.length, all.length);
});

test('FR-070: groupEntries throws on an empty or missing table rather than showing nothing', () => {
  assert.throws(() => groupEntries([]),        /no parameters/);
  assert.throws(() => groupEntries(undefined), /no parameters/);
  assert.throws(() => groupEntries(null),      /no parameters/);
});

test('FR-070: groupEntries throws on an unknown kind rather than silently dropping the row', () => {
  const stray = { name: 'mystery', kind: 'wat', value: 1, default: 1 };
  assert.throws(() => groupEntries([runtimeNhard, stray]), /Unknown parameter kind 'wat' for 'mystery'/);
});

test('FR-070: formatValue shows the API\'s number verbatim, with no rounding or re-formatting', () => {
  assert.equal(formatValue(40),     '40');
  assert.equal(formatValue(0.1),    '0.1');
  assert.equal(formatValue(-5),     '-5');
  assert.equal(formatValue(3075),   '3075');
  assert.equal(formatValue(26.5),   '26.5');
  assert.equal(formatValue(0.15),   '0.15');
  // The page's text must round-trip to the API's value, so a comparison by number is exact.
  for (const v of [40, 0.1, -5, 3075, 26.5, 0.15, 1e-7, 140, 2]) {
    assert.equal(Number(formatValue(v)), v);
  }
});

test('FR-070: differsFromDefault is true only when the value is not the compiled default', () => {
  assert.equal(differsFromDefault(runtimeNhard), true);    // 40 vs 60 — the split this page exists to show
  assert.equal(differsFromDefault(runtimeCorr),  false);
  assert.equal(differsFromDefault(compilePass),  false);
});

test('FR-070: rowModel carries name, value, default and the differs flag as text/plain data', () => {
  assert.deepEqual(rowModel(runtimeNhard), { name: 'osd_nhard_max', value: '40', default: '60', differs: true });
  assert.deepEqual(rowModel(compileCands), { name: 'K_MAX_CANDIDATES', value: '140', default: '140', differs: false });
});

test('FR-070: a name that looks like markup is carried as data, never interpreted (rows are built with textContent)', () => {
  // The renderer never uses innerHTML; here we only assert the model does not transform the text.
  const hostile = { name: '<img src=x onerror=alert(1)>', kind: 'runtime', value: 1, default: 1 };
  assert.equal(rowModel(hostile).name, '<img src=x onerror=alert(1)>');
});
