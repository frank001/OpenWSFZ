/**
 * Standalone full-log page logic (log-viewer).
 * Fetches GET /api/v1/logs/full exactly once on page load and renders it as plain text.
 * Deliberately does NOT poll or auto-refresh — new log content is only shown after the
 * operator manually reloads the browser page (Captain's explicit choice, design.md
 * Decision 4).
 *
 * @module logs
 */

import { getLogsFull, getApiKey } from './api.js';

const outputEl = /** @type {HTMLElement} */ (document.getElementById('logs-full-output'));
const backLink = /** @type {HTMLAnchorElement} */ (document.getElementById('back-link'));

// D-LAN-005 pattern: carry the API key forward so navigating back to the main page
// does not trigger an auth redirect on a non-loopback session.
(function () {
  const key = getApiKey();
  if (key && backLink) {
    backLink.href = '/?key=' + encodeURIComponent(key);
  }
})();

document.addEventListener('DOMContentLoaded', async () => {
  if (!outputEl) return;

  try {
    const text = await getLogsFull();
    outputEl.textContent = (text && text.length > 0)
      ? text
      : '(no log content — file logging may be disabled, or no log file exists yet)';
  } catch (err) {
    outputEl.textContent = `Failed to load log: ${err.message}`;
  }
});
