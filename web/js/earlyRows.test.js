/**
 * decode-early-batch-panel (FR-083, task 6.3): the decode panel's handling of EARLY rows.
 *
 * `earlyRows.js` touches no globals (the document and the table body are injected), so these tests drive it with a tiny
 * fake DOM that implements exactly what the module and the panel use: createElement, appendChild, prepend, replaceWith,
 * remove, isConnected, dataset, classList, textContent, title, className. main.js touches the DOM at import, so its
 * wiring is pinned as TEXT, the same way decodePanelBatches.test.js pins handleDecodes. The real browser behaviour
 * (the mark in the accessibility tree, one row after a confirmation) is QA's Playwright row A5.
 *
 * Run with: node --test web/js/earlyRows.test.js  (or: node --test web/js/*.test.js)
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createEarlyRowTracker, markEarlyRow, EARLY_STATE } from './earlyRows.js';

// ── A fake DOM that is just big enough ────────────────────────────────────────

class FakeClassList {
  constructor() { this.set = new Set(); }
  add(...c)    { for (const x of c) this.set.add(x); }
  remove(...c) { for (const x of c) this.set.delete(x); }
  contains(c)  { return this.set.has(c); }
}

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.parent = null;
    this.children = [];
    this.dataset = {};
    this.classList = new FakeClassList();
    this.textContent = '';
    this.title = '';
    this.className = '';
    this.hidden = false;
  }
  get isConnected() { let n = this; while (n.parent) n = n.parent; return n.tag === 'tbody'; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  prepend(c)     { c.parent = this; this.children.unshift(c); }
  replaceWith(n) {
    const i = this.parent.children.indexOf(this);
    n.parent = this.parent;
    this.parent.children[i] = n;
    this.parent = null;
  }
  remove() {
    const i = this.parent?.children.indexOf(this) ?? -1;
    if (i >= 0) this.parent.children.splice(i, 1);
    this.parent = null;
  }
}

const doc = { createElement: (tag) => new FakeNode(tag) };

function makeTbody() { return new FakeNode('tbody'); }

/** A finished row as main.js builds it: a tr whose message cell is a td. */
function makeRow(message) {
  const tr = new FakeNode('tr');
  const cell = new FakeNode('td');
  cell.textContent = message;
  tr.appendChild(cell);
  tr.__decode = { message };
  return { tr, cell };
}

const badgeOf = (tr) => tr.__earlyBadge;

// ── the mark ──────────────────────────────────────────────────────────────────

test('an early row carries a TEXT mark "early" (never colour alone), the state attribute and the row class', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const { tr, cell } = makeRow('CQ Q1ABC JO33');

  tracker.add(7, tr, cell);

  assert.equal(badgeOf(tr).textContent, 'early');
  assert.ok(badgeOf(tr).title.length > 0, 'the badge explains itself');
  assert.equal(tr.dataset.earlyState, EARLY_STATE.EARLY);
  assert.ok(tr.classList.contains('decode-early'));
  assert.ok(cell.children.includes(badgeOf(tr)), 'the badge text sits inside the message cell, so it is in the accessibility tree');
  assert.equal(tbody.children[0], tr, 'prepended like any decode row');
});

// ── a confirming final row replaces its early row: one row, in place ──────────

test('a confirmed early row is replaced IN PLACE by its final row: one row, same position', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const older = new FakeNode('tr'); tbody.prepend(older);
  const a = makeRow('CQ Q1ABC JO33'); tracker.add(1, a.tr, a.cell);
  const b = makeRow('Q1AAA Q1BBB -01'); tracker.add(2, b.tr, b.cell);
  // tbody (newest first): b, a, older

  const confirmed = tracker.resolve([
    { earlyId: 1, outcome: 'confirmed', finalIndex: 0 },
    { earlyId: 2, outcome: 'unconfirmed' },
  ]);

  assert.equal(confirmed.size, 1);
  assert.equal(confirmed.get(0), a.tr, 'the caller gets the early row to replace at final index 0');
  assert.equal(b.tr.dataset.earlyState, EARLY_STATE.UNCONFIRMED, 'an unconfirmed row is marked now');

  // What main.js does for final index 0:
  const finalRow = new FakeNode('tr');
  const early = confirmed.get(0);
  assert.ok(early.isConnected);
  early.replaceWith(finalRow);

  assert.deepEqual(tbody.children, [b.tr, finalRow, older], 'the final row sits exactly where the early row was');
  assert.equal(tbody.children.filter((r) => r === a.tr).length, 0, 'the early row is gone: one row, not two');
});

test('an unconfirmed early row KEEPS its row and changes its mark to "unconfirmed"', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const { tr, cell } = makeRow('CQ Q1ABC JO33');
  tracker.add(3, tr, cell);

  const confirmed = tracker.resolve([{ earlyId: 3, outcome: 'unconfirmed' }]);

  assert.equal(confirmed.size, 0);
  assert.ok(tr.isConnected, 'the row stays on the panel');
  assert.equal(badgeOf(tr).textContent, 'unconfirmed');
  assert.equal(tr.dataset.earlyState, EARLY_STATE.UNCONFIRMED);
  assert.ok(tr.classList.contains('decode-early-unconfirmed'));
  assert.ok(!tr.classList.contains('decode-early'));
});

test('an empty batch 1 with resolves still marks every early row unconfirmed', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const rows = [makeRow('A'), makeRow('B')];
  rows.forEach((r, i) => tracker.add(10 + i, r.tr, r.cell));

  tracker.resolve([{ earlyId: 10, outcome: 'unconfirmed' }, { earlyId: 11, outcome: 'unconfirmed' }]);

  for (const r of rows) assert.equal(badgeOf(r.tr).textContent, 'unconfirmed');
  assert.equal(tracker.pending, 0, 'nothing is left waiting');
});

test('a resolution for an unknown or already-resolved early id changes nothing and does not throw', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const { tr, cell } = makeRow('X');
  tracker.add(5, tr, cell);

  assert.doesNotThrow(() => tracker.resolve([{ earlyId: 999, outcome: 'confirmed', finalIndex: 0 }]));
  assert.equal(tr.dataset.earlyState, EARLY_STATE.EARLY);

  tracker.resolve([{ earlyId: 5, outcome: 'unconfirmed' }]);
  assert.doesNotThrow(() => tracker.resolve([{ earlyId: 5, outcome: 'confirmed', finalIndex: 0 }]));
  assert.equal(tr.dataset.earlyState, EARLY_STATE.UNCONFIRMED, 'a second resolution of the same id is ignored');
});

test('a "confirmed" resolution without a usable finalIndex is treated as unconfirmed, never left marked early', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const { tr, cell } = makeRow('X');
  tracker.add(6, tr, cell);

  const confirmed = tracker.resolve([{ earlyId: 6, outcome: 'confirmed' }]);

  assert.equal(confirmed.size, 0);
  assert.equal(tr.dataset.earlyState, EARLY_STATE.UNCONFIRMED);
});

test('early rows trimmed by the row cap are forgotten, so pending counts only rows still on the panel', () => {
  const tbody = makeTbody();
  const tracker = createEarlyRowTracker(tbody, doc);
  const a = makeRow('A'); tracker.add(1, a.tr, a.cell);
  const b = makeRow('B'); tracker.add(2, b.tr, b.cell);
  assert.equal(tracker.pending, 2);

  a.tr.remove();                       // the cap dropped the oldest row

  assert.equal(tracker.pending, 1);
  assert.doesNotThrow(() => tracker.resolve([{ earlyId: 1, outcome: 'confirmed', finalIndex: 0 }]));
});

test('markEarlyRow switches the mark both ways', () => {
  const { tr, cell } = makeRow('X');
  const tracker = createEarlyRowTracker(makeTbody(), doc);
  tracker.add(1, tr, cell);

  markEarlyRow(tr, EARLY_STATE.UNCONFIRMED);
  assert.equal(badgeOf(tr).textContent, 'unconfirmed');
  markEarlyRow(tr, EARLY_STATE.EARLY);
  assert.equal(badgeOf(tr).textContent, 'early');
  assert.ok(tr.classList.contains('decode-early') && !tr.classList.contains('decode-early-unconfirmed'));
});

// ── main.js wiring, pinned as text (main.js touches the DOM at import) ─────────

const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'main.js'), 'utf8');

function functionBody(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `main.js: function ${name} not found`);
  const open = source.indexOf('{', source.indexOf(')', start));
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    const c = source[i];
    if (c === '\'' || c === '"' || c === '`') {
      const q = c;
      for (i++; i < source.length && source[i] !== q; i++) if (source[i] === '\\') i++;
      continue;
    }
    if (c === '/' && source[i + 1] === '/') { i = source.indexOf('\n', i); continue; }
    if (c === '/' && source[i + 1] === '*') { i = source.indexOf('*/', i) + 1; continue; }
    if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return source.slice(open + 1, i);
  }
  throw new Error('unbalanced braces in ' + name);
}

test('main.js routes decode-early frames to handleEarlyDecodes and passes resolves to handleDecodes', () => {
  assert.match(source, /event\.type === 'decode-early'[\s\S]{0,80}handleEarlyDecodes\(\s*event\.payload\s*\)/);
  assert.match(source, /event\.type === 'decode'[\s\S]{0,80}handleDecodes\(\s*event\.payload,\s*event\.resolves\s*\)/);
});

test('handleDecodes resolves the early rows BEFORE it builds rows, replaces a confirmed one in place, and still prepends the rest', () => {
  const body = functionBody('handleDecodes');
  assert.match(body, /earlyRowTracker\.resolve\(/);
  assert.match(body, /confirmedEarlyRow\.replaceWith\(\s*tr\s*\)/);
  assert.match(body, /decodesBody\.prepend\(\s*tr\s*\)/);
  assert.ok(body.indexOf('earlyRowTracker.resolve(') < body.indexOf('for (const r of results)'));
});

test('handleDecodes does not return early on an EMPTY batch 1 that carries resolves', () => {
  const body = functionBody('handleDecodes');
  assert.match(body, /\(!results \|\| results\.length === 0\) && !hasResolves/);
});

test('early rows are display-only: handleEarlyDecodes attaches no click, dblclick or engage handler, and feeds no transcript', () => {
  const body = functionBody('handleEarlyDecodes');
  assert.doesNotMatch(body, /addEventListener/);
  assert.doesNotMatch(body, /postTxEngageDecode|postTxSelectResponder|postTxAnswerCq/);
  assert.doesNotMatch(body, /appendTranscriptEntry/);
  assert.match(body, /isDecodeVisible\(\s*r,\s*currentDecodeFilter\s*\)/, 'the active decode filter applies to early rows');
  assert.match(body, /earlyRowTracker\.add\(/);
});
