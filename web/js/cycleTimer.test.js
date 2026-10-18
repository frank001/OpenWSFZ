/**
 * Unit tests for the cycle-countdown timer wrapper (#212, FR-087, spec R2.7).
 * U7: applying the configuration any number of times leaves at most one
 * interval running, and turning the setting off hides the countdown.
 *
 * Run with: node --test web/js/cycleTimer.test.js  (or: node --test web/js/*.test.js)
 */

import { test } from 'node:test';
import assert    from 'node:assert/strict';
import { createCycleTimer } from './cycleTimer.js';

/** A fake setInterval/clearInterval pair that records what is live. */
function makeFakeTimers() {
  let nextId = 1;
  const live = new Map();
  return {
    live,
    setIntervalFn:   (fn, ms) => { const id = nextId++; live.set(id, { fn, ms }); return id; },
    clearIntervalFn: (id)     => { live.delete(id); },
  };
}

test('U7: apply(true) twice leaves exactly one interval running', () => {
  const fake = makeFakeTimers();
  const timer = createCycleTimer({ tick: () => {}, ...fake });
  assert.equal(timer.apply(true), true);
  assert.equal(timer.apply(true), true);
  assert.equal(fake.live.size, 1);
  assert.equal(timer.intervalCount, 1);
});

test('U7: many applications of true never stack intervals', () => {
  const fake = makeFakeTimers();
  const timer = createCycleTimer({ tick: () => {}, ...fake });
  for (let i = 0; i < 25; i++) timer.apply(true);
  assert.equal(fake.live.size, 1);
});

test('U7: apply(false) hides the countdown and leaves no interval running', () => {
  const fake = makeFakeTimers();
  const timer = createCycleTimer({ tick: () => {}, ...fake });
  timer.apply(true);
  assert.equal(timer.apply(false), false);
  assert.equal(fake.live.size, 0);
  assert.equal(timer.intervalCount, 0);
});

test('U7: true again after false starts one interval, not two', () => {
  const fake = makeFakeTimers();
  const timer = createCycleTimer({ tick: () => {}, ...fake });
  timer.apply(true);
  timer.apply(false);
  timer.apply(true);
  timer.apply(true);
  assert.equal(fake.live.size, 1);
});

test('U7: apply(false) before any start is harmless', () => {
  const fake = makeFakeTimers();
  const timer = createCycleTimer({ tick: () => {}, ...fake });
  assert.equal(timer.apply(false), false);
  assert.equal(fake.live.size, 0);
});

test('the interval runs the supplied tick at a 100 ms cadence', () => {
  const fake = makeFakeTimers();
  let ticks = 0;
  const timer = createCycleTimer({ tick: () => { ticks++; }, ...fake });
  timer.apply(true);
  const [{ fn, ms }] = [...fake.live.values()];
  assert.equal(ms, 100);
  assert.equal(ticks, 1, 'starting paints the countdown once at once');
  fn(); fn();
  assert.equal(ticks, 3);
});
