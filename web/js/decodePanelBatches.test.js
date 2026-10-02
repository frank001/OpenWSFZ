/**
 * S3 (d), sub-feas-speed-redesign two-stage publish (design.md D9): the decode panel must APPEND a second batch of
 * the same cycle, never replace the first. `handleDecodes` (web/js/main.js) is the only writer of `#decodes-body`
 * rows. main.js touches the DOM at import, so this reads it as TEXT and asserts the two properties two-stage publish
 * relies on, which QA verified by reading and which this pins so a later edit cannot silently break it:
 *   1. every result becomes a row that is PREPENDED (`decodesBody.prepend(tr)`);
 *   2. the function never clears the table (no innerHTML/textContent/replaceChildren assignment on it, no
 *      row-removal loop over it) other than dropping the one "no data" placeholder row.
 *
 * Run with: node --test web/js/decodePanelBatches.test.js  (or: node --test web/js/*.test.js)
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

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

const body = functionBody('handleDecodes');

test('handleDecodes prepends each result as a new row', () => {
  assert.match(body, /decodesBody\.prepend\(\s*tr\s*\)/);
});

test('handleDecodes never clears the decode table (a second batch of the same cycle cannot replace the first)', () => {
  assert.doesNotMatch(body, /decodesBody\.innerHTML\s*=/);
  assert.doesNotMatch(body, /decodesBody\.textContent\s*=/);
  assert.doesNotMatch(body, /decodesBody\.replaceChildren\(/);
  assert.doesNotMatch(body, /decodesBody\.(?:removeChild|firstChild|lastChild)/);
});

test('the only rows handleDecodes removes are the "no data" placeholder and the OLDEST rows beyond MAX_DECODE_ROWS', () => {
  const removals = body.match(/\.remove\(\)/g) ?? [];
  assert.equal(removals.length, 2);
  assert.match(body, /placeholder[\s\S]{0,60}\.remove\(\)/);
  // The cap starts counting from row index MAX_DECODE_ROWS (the bottom of the newest-first table), so a
  // freshly prepended batch is never the part that gets trimmed.
  assert.match(body, /for\s*\(\s*let i = MAX_DECODE_ROWS;\s*i < rows\.length;\s*i\+\+\s*\)\s*\{\s*rows\[i\]\.remove\(\)/);
});

test('a row keeps its cycle-start stamp from the decode time, so both batches of a cycle share one', () => {
  assert.match(body, /dataset\.cqCycleStartUtc\s*=\s*parseFt8CycleStartUtc\(\s*r\.time\s*\)/);
});
