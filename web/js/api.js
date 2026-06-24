/**
 * REST API client — thin fetch wrappers around the OpenWSFZ REST endpoints.
 * All functions return parsed JSON or throw on non-2xx responses.
 *
 * @module api
 */

// ── Remote access passphrase (lan-remote-access) ──────────────────────────
const API_KEY_SESSION_KEY = 'owsfz-api-key';

/**
 * Returns the stored API passphrase, or null if none is present
 * (loopback access or no passphrase configured).
 * @returns {string|null}
 */
export function getApiKey() {
  return sessionStorage.getItem(API_KEY_SESSION_KEY);
}

/**
 * Stores the passphrase extracted from the URL's ?key= parameter into
 * sessionStorage, then removes the parameter from the browser history so
 * the passphrase is not visible in the URL bar or the back-button history.
 * Called once at module load time.
 */
function bootstrapApiKeyFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const key    = params.get('key');
  if (key) {
    sessionStorage.setItem(API_KEY_SESSION_KEY, key);
    params.delete('key');
    const clean = params.toString()
      ? `${window.location.pathname}?${params}`
      : window.location.pathname;
    history.replaceState(null, '', clean);
  }
}

bootstrapApiKeyFromUrl();

/**
 * Fetches a URL and returns the parsed JSON body.
 * Injects the stored API passphrase as an X-Api-Key header when present.
 * Redirects to /login.html on 401.
 * Throws an Error with the HTTP status text if the response is not 2xx.
 * @param {string} url
 * @param {RequestInit} [init]
 * @returns {Promise<unknown>}
 */
async function fetchJson(url, init) {
  const key = getApiKey();
  const extraHeaders = key ? { 'X-Api-Key': key } : {};
  const mergedInit = {
    ...init,
    headers: { ...(init?.headers ?? {}), ...extraHeaders },
  };

  const res = await fetch(url, mergedInit);

  if (res.status === 401) {
    // Passphrase rejected or session expired — return to login.
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    // Return a never-resolving promise so callers don't see a thrown error
    // while the navigation is in progress.
    return new Promise(() => {});
  }

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — ${url}`);
  }
  return res.json();
}

/**
 * GET /api/v1/status
 * @returns {Promise<{state: string, version: string, audioDevice: string|null}>}
 */
export function getStatus() {
  return fetchJson('/api/v1/status');
}

/**
 * GET /api/v1/audio/devices
 * @returns {Promise<Array<{id: string, name: string}>>}
 */
export function getDevices() {
  return fetchJson('/api/v1/audio/devices');
}

/**
 * GET /api/v1/audio/output-devices
 * @returns {Promise<Array<{id: string, name: string}>>}
 */
export function getOutputDevices() {
  return fetchJson('/api/v1/audio/output-devices');
}

/**
 * GET /api/v1/config
 * @returns {Promise<{audioDeviceName: string|null, port: number}>}
 */
export function getConfig() {
  return fetchJson('/api/v1/config');
}

/**
 * POST /api/v1/config
 * @param {{audioDeviceName: string|null, port: number}} config
 * @returns {Promise<{audioDeviceName: string|null, port: number}>}
 */
export function postConfig(config) {
  return fetchJson('/api/v1/config', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(config),
  });
}

/**
 * GET /api/v1/serial/ports
 * @returns {Promise<string[]>}
 */
export function getSerialPorts() {
  return fetchJson('/api/v1/serial/ports');
}

/**
 * GET /api/v1/frequencies
 * @returns {Promise<Array<{protocol: string, frequencyMHz: number, description: string}>>}
 */
export function getFrequencies() {
  return fetchJson('/api/v1/frequencies');
}

/**
 * POST /api/v1/frequencies
 * @param {Array<{protocol: string, frequencyMHz: number, description: string}>} entries
 * @returns {Promise<Array<{protocol: string, frequencyMHz: number, description: string}>>}
 */
export function postFrequencies(entries) {
  return fetchJson('/api/v1/frequencies', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(entries),
  });
}

/**
 * POST /api/v1/tune
 * @param {number} frequencyMHz
 * @returns {Promise<{effectiveFrequencyMHz: number}>}
 */
export function postTune(frequencyMHz) {
  return fetchJson('/api/v1/tune', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ frequencyMHz }),
  });
}

/**
 * POST /api/v1/cat/retry
 * Signals the CAT polling service to clear its failure suspension and attempt
 * an immediate reconnect.  Returns void — the server responds with 204 No Content.
 * @returns {Promise<void>}
 */
export async function postCatRetry() {
  const key = getApiKey();
  const res = await fetch('/api/v1/cat/retry', {
    method:  'POST',
    headers: key ? { 'X-Api-Key': key } : {},
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return;
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/cat/retry`);
  }
  // 204 No Content — no body to parse.
}

/**
 * GET /api/v1/tx/status
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean}>}
 */
export function getTxStatus() {
  return fetchJson('/api/v1/tx/status');
}

/**
 * POST /api/v1/tx/enable
 * Sets tx.autoAnswer = true and returns the current TX status.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean}>}
 */
export function postTxEnable() {
  return fetchJson('/api/v1/tx/enable', { method: 'POST' });
}

/**
 * POST /api/v1/tx/disable
 * Sets tx.autoAnswer = false and returns the current TX status.
 * Does NOT abort any in-progress QSO.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean}>}
 */
export function postTxDisable() {
  return fetchJson('/api/v1/tx/disable', { method: 'POST' });
}

/**
 * POST /api/v1/tx/abort
 * Aborts any in-progress QSO and disarms TX (sets autoAnswer = false).
 * Returns the updated TX status.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean}>}
 */
export function postTxAbort() {
  return fetchJson('/api/v1/tx/abort', { method: 'POST' });
}

/**
 * POST /api/v1/tx/answer-cq
 * Arms a phase-aware pending TX to answer a specific CQ call (TX-D01).
 * Returns the updated TX status with autoAnswerEnabled = true.
 * Throws an Error with `.status = 409` if the controller is not Idle.
 * @param {string} callsign         Callsign of the CQ station.
 * @param {number} frequencyHz      Audio frequency of the CQ decode, in Hz.
 * @param {string} cqCycleStartUtc  ISO 8601 UTC cycle-start, e.g. "2026-06-22T17:29:15Z".
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean}>}
 */
export async function postTxAnswerCq(callsign, frequencyHz, cqCycleStartUtc) {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/answer-cq', {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Api-Key': key } : {}),
    },
    body:    JSON.stringify({ callsign, frequencyHz, cqCycleStartUtc }),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/tx/answer-cq`);
    /** @type {any} */ (err).status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * POST /api/v1/audio-offset
 * Updates the RX/TX audio frequency cursor positions and Hold TX Freq state.
 * @param {number}  rxHz        RX cursor frequency in Hz (0–3000).
 * @param {number}  txHz        TX cursor frequency in Hz (0–3000).
 * @param {boolean} holdTxFreq  Whether the answerer should lock TX to txHz.
 * @returns {Promise<{rxHz: number, txHz: number, holdTxFreq: boolean}>}
 */
export function postAudioOffset(rxHz, txHz, holdTxFreq) {
  return fetchJson('/api/v1/audio-offset', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ rxHz, txHz, holdTxFreq }),
  });
}
