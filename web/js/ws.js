/**
 * WebSocket client for the OpenWSFZ daemon.
 * Connects to /api/v1/ws, dispatches parsed JSON events to a callback,
 * and automatically reconnects with exponential back-off.
 *
 * @module ws
 */

const WS_URL_PATH   = '/api/v1/ws';
const DELAY_INITIAL = 1_000;   // ms
const DELAY_MAX     = 30_000;  // ms
const DELAY_FACTOR  = 2;

/**
 * Connect to the daemon WebSocket and call `onEvent` for each received frame.
 *
 * `onEvent` receives objects of the form `{ type: string, payload: unknown }`.
 * Additionally the synthetic event `{ type: '__state', payload: 'connected' |
 * 'disconnected' }` is emitted when the connection state changes.
 *
 * @param {function({type: string, payload: unknown}): void} onEvent
 */
export function connect(onEvent) {
  let delay       = DELAY_INITIAL;
  let reconnectTimer = null;
  let ws          = null;
  let destroyed   = false;

  function wsUrl() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const key      = sessionStorage.getItem('owsfz-api-key');
    const keyParam = key ? `?key=${encodeURIComponent(key)}` : '';
    return `${protocol}//${location.host}${WS_URL_PATH}${keyParam}`;
  }

  function scheduleReconnect() {
    if (destroyed) return;

    // If the page is hidden, wait until it becomes visible.
    if (document.visibilityState === 'hidden') return;

    reconnectTimer = setTimeout(open, delay);
    delay = Math.min(delay * DELAY_FACTOR, DELAY_MAX);
  }

  function open() {
    if (destroyed) return;
    reconnectTimer = null;

    let everOpened = false;

    ws = new WebSocket(wsUrl());

    ws.addEventListener('open', () => {
      everOpened = true;
      delay = DELAY_INITIAL; // reset back-off on successful connect
      onEvent({ type: '__state', payload: 'connected' });
    });

    ws.addEventListener('message', (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        onEvent(msg);
      } catch {
        // Malformed frame — ignore silently.
      }
    });

    ws.addEventListener('close', () => {
      ws = null;  // must be cleared so the visibilitychange guard (!ws) works correctly
      onEvent({ type: '__state', payload: 'disconnected' });

      // If the connection closed before ever opening AND we have a stored key,
      // assume auth failure (server returned 401 on the WS upgrade).
      // Clear the key and redirect to the login page.
      if (!everOpened && sessionStorage.getItem('owsfz-api-key')) {
        sessionStorage.removeItem('owsfz-api-key');
        window.location.href = '/login.html';
        return;
      }

      scheduleReconnect();
    });

    ws.addEventListener('error', () => {
      // 'close' fires immediately after 'error', so reconnect is handled there.
    });
  }

  // Defer reconnect when the tab is hidden; fire immediately when visible again.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && !ws && reconnectTimer === null && !destroyed) {
      scheduleReconnect();
    }
  });

  open();
}
