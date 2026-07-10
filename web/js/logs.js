/**
 * Standalone full-log page logic (log-viewer).
 * Fetches GET /api/v1/logs/full exactly once on page load and renders it as plain text.
 * Deliberately does NOT poll or auto-refresh — new log content is only shown after the
 * operator manually reloads the browser page (Captain's explicit choice, design.md
 * Decision 4).
 *
 * @module logs
 */

import { getLogsFull } from './api.js';

const outputEl = /** @type {HTMLElement} */ (document.getElementById('logs-full-output'));

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
