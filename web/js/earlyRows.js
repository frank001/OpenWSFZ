// @ts-check
/**
 * decode-early-batch-panel (#122 step 4, phase 4a; FR-083, design.md D5): the decode panel's handling of EARLY rows.
 *
 * An early row is a decode of the first part of a window, shown about 2 s before the cycle's final decode. It is
 * marked *early* until the final decode (batch 1) arrives; the batch-1 `decode` frame then says, per early row, whether
 * the final decode confirmed it. A confirmed early row is REPLACED IN PLACE by its final row (one row, not two); an
 * unconfirmed one stays and its mark changes to *unconfirmed*.
 *
 * The mark is TEXT, never colour alone: a visible badge span whose text is "early" or "unconfirmed" (so it is in the
 * accessibility tree and read by a screen reader), plus a `title`. `data-early-state` is the machine-readable twin.
 *
 * This module touches no globals: the document and the table body are injected, so it runs under `node --test` with a
 * tiny fake DOM (see earlyRows.test.js). main.js builds the row cells (it owns the column layout) and hands the row here.
 */

/** The two marks an early row can carry. */
export const EARLY_STATE = Object.freeze({ EARLY: 'early', UNCONFIRMED: 'unconfirmed' });

const BADGE_TEXT = Object.freeze({
  [EARLY_STATE.EARLY]:       'early',
  [EARLY_STATE.UNCONFIRMED]: 'unconfirmed',
});

const BADGE_TITLE = Object.freeze({
  [EARLY_STATE.EARLY]:       'Early decode of a partial window. The full decode has not confirmed it yet.',
  [EARLY_STATE.UNCONFIRMED]: 'Early decode that the full decode did not confirm.',
});

const ROW_CLASS = Object.freeze({
  [EARLY_STATE.EARLY]:       'decode-early',
  [EARLY_STATE.UNCONFIRMED]: 'decode-early-unconfirmed',
});

/**
 * Sets (or changes) the mark on an early row: the row class, `data-early-state`, and the text badge.
 *
 * @param {any} tr    the table row (carries `__earlyBadge` once the tracker has added it)
 * @param {'early'|'unconfirmed'} state
 */
export function markEarlyRow(tr, state) {
  tr.dataset.earlyState = state;
  tr.classList.remove(ROW_CLASS[EARLY_STATE.EARLY], ROW_CLASS[EARLY_STATE.UNCONFIRMED]);
  tr.classList.add(ROW_CLASS[state]);
  const badge = tr.__earlyBadge;
  if (badge) {
    badge.textContent = BADGE_TEXT[state];
    badge.title       = BADGE_TITLE[state];
    badge.className   = `early-badge early-badge-${state}`;
  }
}

/**
 * Tracks the early rows currently on the panel, by their `earlyId`.
 *
 * @param {any} tbody  the decode table body
 * @param {any} doc    the document (injected for tests)
 */
export function createEarlyRowTracker(tbody, doc) {
  /** @type {Map<number, any>} */
  const rows = new Map();

  function prune() {
    for (const [id, tr] of rows) if (!tr.isConnected) rows.delete(id);   // trimmed by the row cap
  }

  return {
    /**
     * Adds an early row: appends the text badge to the message cell, marks it *early* and prepends it to the table.
     *
     * @param {number} earlyId
     * @param {any} tr           the finished row
     * @param {any} messageCell  the cell the badge goes in
     */
    add(earlyId, tr, messageCell) {
      const badge = doc.createElement('span');
      messageCell.appendChild(badge);
      tr.__earlyBadge = badge;
      markEarlyRow(tr, EARLY_STATE.EARLY);
      tbody.prepend(tr);
      prune();
      rows.set(earlyId, tr);
    },

    /**
     * Applies a batch-1 frame's `resolves` list. An unconfirmed early row is marked *unconfirmed* now. A confirmed
     * one is NOT touched here: the caller replaces it in place when it builds the final row at `finalIndex`
     * (so there is no paint between "early row removed" and "final row added").
     *
     * @param {Array<{earlyId:number, outcome:string, finalIndex?:number}>|undefined|null} resolves
     * @returns {Map<number, any>} final-row index to the early row it replaces
     */
    resolve(resolves) {
      /** @type {Map<number, any>} */
      const confirmed = new Map();
      for (const r of resolves ?? []) {
        const tr = rows.get(r.earlyId);
        if (!tr) continue;
        rows.delete(r.earlyId);
        if (r.outcome === 'confirmed' && Number.isInteger(r.finalIndex)) {
          confirmed.set(/** @type {number} */ (r.finalIndex), tr);
        } else {
          markEarlyRow(tr, EARLY_STATE.UNCONFIRMED);
        }
      }
      return confirmed;
    },

    /** The number of early rows still awaiting their cycle's final batch. */
    get pending() {
      prune();
      return rows.size;
    },
  };
}
