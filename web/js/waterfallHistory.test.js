/**
 * Unit tests for the waterfall history ring buffer (#212, FR-086, spec R1).
 * DOM-free: inputs are lines, a width and a height; output is RGBA bytes.
 *
 * Run with: node --test web/js/waterfallHistory.test.js  (or: node --test web/js/*.test.js)
 * No dependencies — Node's built-in test runner and assert module only.
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import {
  HISTORY_LINES,
  colormap,
  createColormapLut,
  WaterfallHistory,
} from './waterfallHistory.js';

/** Deterministic synthetic line of `len` bins: values depend on (seed, index). */
function makeLine(seed, len) {
  const bins = new Array(len);
  for (let i = 0; i < len; i++) bins[i] = (seed * 37 + i * 11) % 256;
  return bins;
}

/** The colour the spec requires at column x of row i: the line's own bin->x map. */
function expectedPixel(bins, x, w) {
  const idx = Math.min(Math.floor(x * bins.length / w), bins.length - 1);
  const [r, g, b] = colormap(bins[idx]);
  return [r, g, b, 255];
}

function pixelAt(rgba, w, x, row) {
  const o = (row * w + x) * 4;
  return [rgba[o], rgba[o + 1], rgba[o + 2], rgba[o + 3]];
}

/** Asserts rows [0, n) of `rgba` equal the paint of `lines` (newest = last in `lines`) at width w. */
function assertRowsMatchLines(rgba, w, lines, n) {
  for (let row = 0; row < n; row++) {
    const bins = lines[lines.length - 1 - row];
    for (let x = 0; x < w; x++) {
      assert.deepEqual(pixelAt(rgba, w, x, row), expectedPixel(bins, x, w),
        `row ${row} x ${x} (w=${w})`);
    }
  }
}

test('colormap LUT agrees with colormap() for every intensity', () => {
  const lut = createColormapLut();
  for (let v = 0; v < 256; v++) {
    const [r, g, b] = colormap(v);
    assert.deepEqual([lut[v * 3], lut[v * 3 + 1], lut[v * 3 + 2]], [r, g, b], `v=${v}`);
  }
});

// U1
test('U1: row i of paint(w, h) is line i (newest first) mapped by its own length', () => {
  const hist = new WaterfallHistory();
  const lines = [];
  for (let i = 0; i < 40; i++) { const l = makeLine(i, 100); lines.push(l); hist.push(l); }
  const w = 77, h = 50;
  const rgba = hist.paint(w, h);
  assert.equal(rgba.length, w * h * 4);
  assertRowsMatchLines(rgba, w, lines, 40);
  // Rows below the stored lines are black, fully opaque.
  for (let row = 40; row < h; row++)
    for (let x = 0; x < w; x++)
      assert.deepEqual(pixelAt(rgba, w, x, row), [0, 0, 0, 255], `blank row ${row}`);
});

// U2
test('U2: repainting at a different width maps the same lines at the new width', () => {
  const hist = new WaterfallHistory();
  const lines = [];
  for (let i = 0; i < 30; i++) { const l = makeLine(i, 100); lines.push(l); hist.push(l); }
  for (const w of [77, 150, 31]) {
    assertRowsMatchLines(hist.paint(w, 30), w, lines, 30);
  }
});

// U3
test('U3: shrinking the height to 10 and growing back restores every row', () => {
  const hist = new WaterfallHistory();
  const lines = [];
  for (let i = 0; i < 60; i++) { const l = makeLine(i, 64); lines.push(l); hist.push(l); }
  const w = 40, h1 = 60;
  const before = hist.paint(w, h1);
  const small = hist.paint(w, 10);
  assertRowsMatchLines(small, w, lines, 10);
  const after = hist.paint(w, h1);
  assert.deepEqual(Array.from(after), Array.from(before));
  assertRowsMatchLines(after, w, lines, 60);
});

// U4
test('U4: a zero-size paint changes nothing and returns no buffer', () => {
  const hist = new WaterfallHistory();
  const lines = [];
  for (let i = 0; i < 20; i++) { const l = makeLine(i, 50); lines.push(l); hist.push(l); }
  const before = Array.from(hist.paint(30, 20));
  assert.equal(hist.paint(0, 20).length, 0);
  assert.equal(hist.paint(30, 0).length, 0);
  assert.equal(hist.paint(0, 0).length, 0);
  assert.equal(hist.length, 20, 'a zero-size paint must not drop stored lines');
  assert.deepEqual(Array.from(hist.paint(30, 20)), before);
});

// U5
test('U5: HISTORY_LINES + k pushes keep the newest HISTORY_LINES lines, in order', () => {
  assert.equal(HISTORY_LINES, 2048);
  const k = 37;
  const hist = new WaterfallHistory();
  const lines = [];
  // Short lines keep this fast; the identity of a line is its seed in bin 0.
  for (let i = 0; i < HISTORY_LINES + k; i++) {
    const l = [i % 256, Math.floor(i / 256)];
    lines.push(l);
    hist.push(l);
  }
  assert.equal(hist.length, HISTORY_LINES);
  const w = 2, h = HISTORY_LINES + 10;
  const rgba = hist.paint(w, h);
  for (let row = 0; row < HISTORY_LINES; row++) {
    const line = lines[lines.length - 1 - row];
    assert.deepEqual(pixelAt(rgba, w, 0, row), expectedPixel(line, 0, w), `row ${row}`);
    assert.deepEqual(pixelAt(rgba, w, 1, row), expectedPixel(line, 1, w), `row ${row}`);
  }
  // Rows past the stored history are black.
  assert.deepEqual(pixelAt(rgba, w, 0, HISTORY_LINES + 5), [0, 0, 0, 255]);
});

// U6
test('U6: lines of different lengths repaint each by its own length', () => {
  const hist = new WaterfallHistory();
  const lines = [makeLine(1, 100), makeLine(2, 40), makeLine(3, 250), makeLine(4, 100)];
  for (const l of lines) hist.push(l);
  assertRowsMatchLines(hist.paint(90, 4), 90, lines, 4);
});

test('push stores a copy: mutating the caller\'s array afterwards changes nothing', () => {
  const hist = new WaterfallHistory();
  const line = [10, 200, 90, 30];
  hist.push(line);
  const before = Array.from(hist.paint(4, 1));
  line.fill(255);
  assert.deepEqual(Array.from(hist.paint(4, 1)), before);
});
