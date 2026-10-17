/**
 * Cycle-countdown timer wrapper (#212, FR-087, spec R2.7).
 *
 * The main page re-applies its configuration every time the Settings panel
 * closes, so the 100 ms countdown interval must be started AT MOST ONCE however
 * often the configuration is applied. DOM-free so the interval bookkeeping can
 * be tested with fake timers.
 *
 * @module cycleTimer
 */

/** Countdown refresh period in milliseconds. */
export const CYCLE_TICK_MS = 100;

/**
 * @param {object}   deps
 * @param {function(): void} deps.tick              Runs the countdown update.
 * @param {function(Function, number): any} [deps.setIntervalFn]    Defaults to setInterval.
 * @param {function(any): void}             [deps.clearIntervalFn]  Defaults to clearInterval.
 * @returns {{ apply(showCountdown: boolean): boolean, readonly intervalCount: number }}
 */
export function createCycleTimer({
  tick,
  setIntervalFn   = (fn, ms) => setInterval(fn, ms),
  clearIntervalFn = (id)     => clearInterval(id),
}) {
  let handle = null;

  return {
    /**
     * Applies the `showCycleCountdown` setting. Idempotent.
     * @param {boolean} showCountdown
     * @returns {boolean} whether the countdown is visible after the call
     */
    apply(showCountdown) {
      if (showCountdown) {
        if (handle === null) {
          tick();
          handle = setIntervalFn(tick, CYCLE_TICK_MS);
        }
        return true;
      }
      if (handle !== null) {
        clearIntervalFn(handle);
        handle = null;
      }
      return false;
    },

    /** Intervals currently running: 0 or 1, never more. */
    get intervalCount() { return handle === null ? 0 : 1; },
  };
}
