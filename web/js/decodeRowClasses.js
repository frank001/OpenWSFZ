// @ts-check
/**
 * Decode-row highlight classification, shared by the final-row path (`handleDecodes`) and the early-row path
 * (`handleEarlyDecodes`) in main.js so the two cannot drift (#219: early rows were built without these classes, so
 * the early-row colours never showed on a live page).
 *
 * DOM-free: it only decides WHICH highlights apply; the callers add the classes. Click handlers and the pointer
 * cursor stay with the final-row path (an early row is display-only, FR-083).
 */

/**
 * Returns true if `token` matches `callsign` exactly or as a portable suffix
 * (e.g. "PD2FZ/P" matches callsign "PD2FZ").
 *
 * @param {string} token
 * @param {string} callsign
 * @returns {boolean}
 */
export function tokenMatchesCallsign(token, callsign) {
  return token === callsign || token.startsWith(callsign + '/');
}

/**
 * @typedef {object} DecodeRowContext
 * @property {string} txCallsign       the operator's callsign ('' when unset)
 * @property {string} role             current TX role ('caller' | 'answerer' | ...)
 * @property {string} state            current TX state ('WaitAnswer', ...)
 * @property {string} partnerSelect    the caller's partner-select mode ('None', ...)
 */

/**
 * Decides which highlight classes a decoded message gets.
 *
 * - `cq`: the message starts with `CQ ` (TX-D01).
 * - `partner`: any space-delimited token matches the operator's callsign.
 * - `responder`: Caller role, WaitAnswer, partner-select None, three or more tokens, and the first token is our
 *   callsign or its base callsign (the decoder may drop a `/P` suffix).
 *
 * @param {string} message
 * @param {DecodeRowContext} ctx
 * @returns {{cq: boolean, partner: boolean, responder: boolean}}
 */
export function classifyDecodeRow(message, ctx) {
  const tokens = message.split(' ');
  const call = ctx.txCallsign;
  const base = call ? call.split('/')[0] : '';
  return {
    cq: message.startsWith('CQ '),
    partner: Boolean(call) && tokens.some(t => tokenMatchesCallsign(t, call)),
    responder: ctx.role === 'caller'
      && ctx.state === 'WaitAnswer'
      && ctx.partnerSelect === 'None'
      && tokens.length >= 3
      && Boolean(call)
      && (tokens[0] === call || tokens[0] === base),
  };
}

/**
 * Adds the highlight classes `classifyDecodeRow` chose to a row.
 *
 * @param {{classList: {add: (...c: string[]) => void}}} tr
 * @param {{cq: boolean, partner: boolean, responder: boolean}} cls
 */
export function applyDecodeRowClasses(tr, cls) {
  if (cls.cq)        tr.classList.add('decode-cq');
  if (cls.partner)   tr.classList.add('decode-partner');
  if (cls.responder) tr.classList.add('decode-responder');
}
