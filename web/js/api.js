/**
 * REST API client — thin fetch wrappers around the OpenWSFZ REST endpoints.
 * All functions return parsed JSON or throw on non-2xx responses.
 *
 * @module api
 */

/**
 * Fetches a URL and returns the parsed JSON body.
 * Throws an Error with the HTTP status text if the response is not 2xx.
 * @param {string} url
 * @param {RequestInit} [init]
 * @returns {Promise<unknown>}
 */
async function fetchJson(url, init) {
  const res = await fetch(url, init);
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
  const res = await fetch('/api/v1/cat/retry', { method: 'POST' });
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
 * Requests an immediate abort of any in-progress QSO exchange.
 * State update arrives via the txState WebSocket event.
 * @returns {Promise<void>}
 */
export async function postTxAbort() {
  const res = await fetch('/api/v1/tx/abort', { method: 'POST' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/tx/abort`);
  }
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
