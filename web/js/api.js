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
 * POST /api/v1/ptt/test (cat-tx-ptt, task 17.3/17.6, FR-057)
 * Fires a brief, silent PTT pulse against the currently-running IPttController.
 * Unlike the generic fetchJson-based helpers above, this reads the JSON body on a 409
 * response too (rather than discarding it and throwing a generic "HTTP 409" error) so the
 * caller can show the operator the actual reason ("a QSO is currently transmitting" /
 * "PTT method is AudioVox…") rather than a bare status code.
 * @returns {Promise<{result: 'pass'|'error', message: string|null}>}
 */
export async function postPttTest() {
  const key = getApiKey();
  const res = await fetch('/api/v1/ptt/test', {
    method:  'POST',
    headers: key ? { 'X-Api-Key': key } : {},
  });

  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }

  if (res.status === 409) {
    let message = 'PTT test unavailable.';
    try {
      const problem = await res.json();
      message = problem?.detail || problem?.title || message;
    } catch {
      // Malformed/absent ProblemDetails body — fall back to the generic message above.
    }
    return { result: 'error', message };
  }

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/ptt/test`);
  }

  return res.json();
}

/**
 * POST /api/v1/system/restart (remote-daemon-restart)
 * Restarts the daemon process in place: spawns a fresh instance of itself, then gracefully
 * stops the current one. Refuses with 409 while a real QSO is transmitting. Like
 * {@link postPttTest}, reads the JSON body on a 409 response too (rather than throwing a
 * generic "HTTP 409" error) so the caller can show the operator the actual reason.
 * @returns {Promise<{status: 'restarting'|'refused', message: string|null}>}
 */
export async function postSystemRestart() {
  const key = getApiKey();
  const res = await fetch('/api/v1/system/restart', {
    method:  'POST',
    headers: key ? { 'X-Api-Key': key } : {},
  });

  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }

  if (res.status === 409) {
    let message = 'Restart unavailable.';
    try {
      const problem = await res.json();
      message = problem?.detail || problem?.title || message;
    } catch {
      // Malformed/absent ProblemDetails body — fall back to the generic message above.
    }
    return { status: 'refused', message };
  }

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/system/restart`);
  }

  const body = await res.json();
  return { status: body?.status ?? 'restarting', message: null };
}

/**
 * GET /api/v1/tx/status
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, keying: boolean}>}
 */
export function getTxStatus() {
  return fetchJson('/api/v1/tx/status');
}

/**
 * POST /api/v1/tx/enable
 * Sets tx.autoAnswer = true and returns the current TX status.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, keying: boolean}>}
 */
export function postTxEnable() {
  return fetchJson('/api/v1/tx/enable', { method: 'POST' });
}

/**
 * POST /api/v1/tx/disable
 * Sets tx.autoAnswer = false and returns the current TX status.
 * Does NOT abort any in-progress QSO.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, keying: boolean}>}
 */
export function postTxDisable() {
  return fetchJson('/api/v1/tx/disable', { method: 'POST' });
}

/**
 * POST /api/v1/tx/abort
 * Aborts any in-progress QSO and disarms TX (sets autoAnswer = false).
 * Returns the updated TX status.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, keying: boolean}>}
 */
export function postTxAbort() {
  return fetchJson('/api/v1/tx/abort', { method: 'POST' });
}

/**
 * POST /api/v1/tx/engage-decode
 * Atomically aborts any in-progress QSO and engages a new one based on the
 * double-clicked decode.  The backend parses the message, determines the correct
 * response, and primes the state machine.
 *
 * Returns HTTP 422 Unprocessable Entity if the message is not actionable
 * (not addressed to us, or unknown format).  In that case the abort has still
 * been performed; the caller should refresh TX status.
 *
 * Returns HTTP 409 Conflict (engagement-target-validation) if the target callsign is
 * rejected by the region-anchored grammar check and `confirm` was not set — the thrown
 * error carries `.reason` and `.requiresConfirmation` so the caller can prompt the
 * operator and, on acceptance, retry with `confirm: true`.
 *
 * @param {string} message       Full FT8 message text (e.g. "PD2FZ W1ABC -07").
 * @param {number} frequencyHz   Audio frequency of the decode, in Hz.
 * @param {string} cycleStartUtc ISO 8601 UTC cycle-start (e.g. "2026-06-27T10:00:15Z").
 * @param {boolean} [confirm]    Operator has already confirmed a prior engagement-target
 *                               rejection for this same target — proceed regardless.
 * @param {number} [snr]         Real measured SNR of the double-clicked decode row (TX-D04) —
 *                               used only when the jump-in resolves to a SendReport response, so
 *                               the transmitted report reflects the real signal quality instead of
 *                               a fixed placeholder.
 * @returns {Promise<{state:string, partner:string|null, autoAnswerEnabled:boolean, role:string}>}
 */
export async function postTxEngageDecode(message, frequencyHz, cycleStartUtc, confirm = false, snr = 0) {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/engage-decode', {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Api-Key': key } : {}),
    },
    body: JSON.stringify({ message, frequencyHz, cycleStartUtc, confirm, snr }),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    throw new Error('Unauthorized');
  }
  const err = new Error(`engage-decode: ${res.status}`);
  /** @type {any} */ (err).status = res.status;
  if (res.status === 409) {
    // engagement-target-validation: body is { reason, requiresConfirmation }.
    try {
      const body = await res.json();
      /** @type {any} */ (err).reason               = body?.reason ?? null;
      /** @type {any} */ (err).requiresConfirmation  = body?.requiresConfirmation ?? true;
    } catch { /* malformed/empty body — leave reason unset */ }
  }
  if (!res.ok) throw err;
  return res.json();
}

/**
 * POST /api/v1/tx/answer-cq
 * Arms a phase-aware pending TX to answer a specific CQ call (TX-D01).
 * Returns the updated TX status with autoAnswerEnabled = true.
 * Throws an Error with `.status = 409` if the controller is not Idle.
 * @param {string} callsign         Callsign of the CQ station.
 * @param {number} frequencyHz      Audio frequency of the CQ decode, in Hz.
 * @param {string} cqCycleStartUtc  ISO 8601 UTC cycle-start, e.g. "2026-06-22T17:29:15Z".
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, keying: boolean}>}
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
 * POST /api/v1/tx/select-responder
 * Arms a phase-aware pending TX to call a specific station that responded to our CQ.
 * Only valid when the QSO controller is in Caller role and WaitAnswer state.
 * Returns the updated TX status.
 * Throws an Error with `.status = 405` if the controller is Answerer role.
 * Throws an Error with `.status = 409` if the controller is not in WaitAnswer state.
 * @param {string} callsign               Callsign of the responding station.
 * @param {number} frequencyHz            Audio frequency of the response decode, in Hz.
 * @param {string} responseCycleStartUtc  ISO 8601 UTC cycle-start of the response, e.g. "2026-06-25T14:29:15Z".
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, role: string, keying: boolean}>}
 */
export async function postTxSelectResponder(callsign, frequencyHz, responseCycleStartUtc) {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/select-responder', {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Api-Key': key } : {}),
    },
    body:    JSON.stringify({ callsign, frequencyHz, responseCycleStartUtc }),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/tx/select-responder`);
    /** @type {any} */ (err).status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * POST /api/v1/tx/call-cq
 * Switches to Caller role (if not already) and arms AutoAnswer so the daemon
 * transmits CQ on the next FT8 cycle.  Works regardless of the configured role:
 * if the daemon was started in Answerer mode, the active role switches at runtime
 * and reverts automatically after the CQ QSO completes or is aborted.
 * Returns HTTP 409 (Conflict) if a QSO is already in progress.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, role: string, keying: boolean}>}
 */
export async function postTxCallCq() {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/call-cq', {
    method:  'POST',
    headers: key ? { 'X-Api-Key': key } : {},
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/tx/call-cq`);
    /** @type {any} */ (err).status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * GET /api/v1/logs/tail?lines=N
 * Returns the last N lines of the daemon's currently active log file, oldest first.
 * Returns an empty array (not an error) when file logging is disabled or no active
 * log file exists yet.
 * @param {number} [lines=150]
 * @returns {Promise<{lines: string[]}>}
 */
export function getLogsTail(lines = 150) {
  return fetchJson(`/api/v1/logs/tail?lines=${encodeURIComponent(lines)}`);
}

/**
 * GET /api/v1/logs/full
 * Fetches the complete current contents of the daemon's currently active log file as
 * plain text. Returns an empty string when no active log file exists.
 * @returns {Promise<string>}
 */
export async function getLogsFull() {
  const key = getApiKey();
  const res = await fetch('/api/v1/logs/full', {
    headers: key ? { 'X-Api-Key': key } : {},
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — /api/v1/logs/full`);
  }
  return res.text();
}

/**
 * POST /api/v1/tx/stop-cq
 * Requests a graceful stop of the current CQ caller session: any TX sample already in
 * flight completes normally, then the service returns to Idle. Unlike postTxAbort(),
 * this does not immediately kill audio. The caller should not re-render the TX panel
 * from this response directly — wait for the subsequent txState WebSocket event
 * (state: 'Idle') instead, consistent with how Abort TX is already handled.
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean, role: string, keying: boolean}>}
 */
export function postTxStopCq() {
  return fetchJson('/api/v1/tx/stop-cq', { method: 'POST' });
}

/**
 * POST /api/v1/tx/caller-partner-select
 * Persists the caller partner-select mode to config (FR-PILEUP-001).
 * @param {'First'|'None'} mode
 * @returns {Promise<{state: string, partner: string|null, autoAnswerEnabled: boolean,
 *                    role: string, callerPartnerSelect: string, keying: boolean}>}
 */
export async function postTxCallerPartnerSelect(mode) {
  const key = getApiKey();
  const res = await fetch('/api/v1/tx/caller-partner-select', {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Api-Key': key } : {}),
    },
    body: JSON.stringify({ mode }),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    return new Promise(() => {});
  }
  if (!res.ok) {
    const err = new Error(
      `HTTP ${res.status} ${res.statusText} — /api/v1/tx/caller-partner-select`);
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

/**
 * GET /api/v1/prop-modes
 * Returns the operator's propagation mode list.
 * @returns {Promise<Array<{protocol: string, value: string, description: string}>>}
 */
export function getPropModes() {
  return fetchJson('/api/v1/prop-modes');
}

/**
 * GET /api/v1/region-data/status
 * Returns the active region table's entry count and this daemon session's refresh history
 * (region-lookup-data-refresh operator status view). `lastRefreshUtc`/`lastRefreshSucceeded`/
 * `lastReleaseVersion`/`lastErrorMessage` are all `null` until a refresh has been triggered at
 * least once this session.
 * `effectiveSuppressUnknownRegion` (decode-noise-suppression) is the live-resolved effective
 * value of the Unknown-region suppression setting — the persisted value once the operator has
 * made an explicit choice, otherwise computed from `entryCount > 0`.
 * @returns {Promise<{
 *   entryCount: number,
 *   hasRefreshedThisSession: boolean,
 *   lastRefreshUtc: string|null,
 *   lastRefreshSucceeded: boolean|null,
 *   lastReleaseVersion: string|null,
 *   lastErrorMessage: string|null,
 *   effectiveSuppressUnknownRegion: boolean
 * }>}
 */
export function getRegionDataStatus() {
  return fetchJson('/api/v1/region-data/status');
}

/**
 * POST /api/v1/region-data/refresh
 * Fetches the current country-files.com release, converts it, and installs it as the daemon's
 * active region table (region-lookup-data-refresh). On failure the existing region data is left
 * untouched — the thrown Error carries the server's detail message.
 * @returns {Promise<{success: boolean, entryCount: number, releaseVersion: string|null}>}
 */
export function postRegionDataRefresh() {
  return fetchJson('/api/v1/region-data/refresh', { method: 'POST' });
}

/**
 * GET /api/v1/region-data/lookup?callsign={token}
 * Resolves a callsign against the active region table using the same longest-prefix-match logic
 * the decode pipeline uses — a read-only diagnostic, not a live decode
 * (region-lookup-data-refresh). `matched: false` means no entry covers the given prefix (the
 * diagnostic equivalent of the decode pipeline's "Unknown").
 * @param {string} callsign
 * @returns {Promise<{
 *   matched: boolean,
 *   entity: string|null,
 *   continent: string|null,
 *   cqZone: number|null,
 *   ituZone: number|null,
 *   synthetic: boolean
 * }>}
 */
export function getRegionDataLookup(callsign) {
  return fetchJson(`/api/v1/region-data/lookup?callsign=${encodeURIComponent(callsign)}`);
}

/**
 * GET /api/v1/decode-filter
 * Returns the daemon's current decode-panel filter state (decode-panel-filtering capability).
 * Every axis is `null` (no restriction) on a freshly-started daemon.
 * @returns {Promise<{
 *   allowedEntities: string[]|null, allowedContinents: string[]|null,
 *   allowedCqZones: number[]|null, allowedItuZones: number[]|null,
 *   contactStates: string[]|null, countryStates: string[]|null,
 *   continentStates: string[]|null, cqZoneStates: string[]|null, ituZoneStates: string[]|null
 * }>}
 */
export function getDecodeFilter() {
  return fetchJson('/api/v1/decode-filter');
}

/**
 * POST /api/v1/decode-filter
 * Whole-object replace of the daemon's decode-panel filter state (decode-panel-filtering
 * capability). Daemon-owned, ephemeral, and shared across all connected clients — the response
 * (and the resulting `decodeFilterChanged` WebSocket broadcast) is authoritative for every
 * connected tab and for both QSO controller services.
 * @param {object} state  Same shape as {@link getDecodeFilter}'s return value.
 * @returns {Promise<object>}
 */
export function postDecodeFilter(state) {
  return fetchJson('/api/v1/decode-filter', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(state),
  });
}

/**
 * POST /api/v1/tx/log-qso
 * Writes a completed QSO to the ADIF log (qso-log-dialog).
 * @param {{
 *   callsign: string,
 *   grid: string|null,
 *   rstSent: string,
 *   rstRcvd: string,
 *   startUtc: string,
 *   endUtc: string,
 *   freqMHz: number,
 *   operatorCallsign: string,
 *   name: string|null,
 *   txPower: string|null,
 *   comment: string|null,
 *   propMode: string|null,
 *   exchSent: string|null,
 *   exchRcvd: string|null,
 *   retainTxPower: boolean,
 *   retainComment: boolean,
 *   retainPropMode: boolean
 * }} data
 * @returns {Promise<{logged: boolean}>}
 */
export async function postLogQso(data) {
  return fetchJson('/api/v1/tx/log-qso', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(data),
  });
}
