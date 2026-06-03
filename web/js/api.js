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
