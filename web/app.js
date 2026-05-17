// SPDX-License-Identifier: MIT
//
// OpenWSFZ web UI bootstrap.
//
// Responsibilities at the skeleton stage:
//   * Fetch /api/health once on load, populate the daemon card.
//   * Open a WebSocket to /ws, send a ping every 5s, update the
//     status pill from pong replies.
//
// The wire envelope is {type, id, ts, payload?} as specified in
// openspec/changes/add-project-skeleton/specs/web-control-api/spec.md.

const el = (id) => document.getElementById(id);
const setText = (id, value) => { const n = el(id); if (n) n.textContent = value; };

function setPill(state, label) {
  const p = el('status-pill');
  p.className = 'pill pill-' + state;
  p.textContent = label;
}

function formatUptime(seconds) {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}h ${m}m ${r}s`;
  if (m > 0) return `${m}m ${r}s`;
  return `${r}s`;
}

async function loadHealth() {
  try {
    const res = await fetch('/api/health', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const j = await res.json();
    setText('version', 'v' + j.version);
    setText('d-status', j.status);
    setText('d-version', j.version);
    setText('d-git', j.git_sha || '—');
    setText('d-uptime', formatUptime(j.uptime_seconds));
  } catch (err) {
    setText('d-status', 'unreachable');
    console.warn('health probe failed:', err);
  }
}

// ---- WebSocket -----------------------------------------------------------

let ws = null;
let pingTimer = null;
let nextId = 1;
const pending = new Map();   // id -> sent timestamp (for round-trip)

function envelope(type, payload) {
  const id = String(nextId++);
  return {
    msg: { type, id, ts: new Date().toISOString(), payload: payload ?? {} },
    id,
  };
}

function sendPing() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const { msg, id } = envelope('ping', { from: 'web-ui' });
  pending.set(id, performance.now());
  ws.send(JSON.stringify(msg));
}

function handleEnvelope(msg) {
  if (!msg || typeof msg !== 'object') return;
  if (msg.type === 'pong') {
    const sent = pending.get(String(msg.id));
    pending.delete(String(msg.id));
    const rtt = sent != null ? (performance.now() - sent).toFixed(1) : '?';
    setText('d-pong', `${msg.ts} (rtt ${rtt} ms)`);
    setPill('ok', 'live');
    // Opportunistically refresh uptime so it ticks visibly.
    loadHealth();
  } else if (msg.type === 'error') {
    console.warn('ws error from daemon:', msg.payload?.message);
  } else if (msg.type === 'echo') {
    // Skeleton-only behaviour; future capabilities will register real types.
    console.debug('echo:', msg);
  }
}

function connect() {
  setPill('pending', 'connecting');
  const url = (location.protocol === 'https:' ? 'wss://' : 'ws://')
            + location.host + '/ws';
  ws = new WebSocket(url);

  ws.addEventListener('open', () => {
    setPill('ok', 'connected');
    sendPing();
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(sendPing, 5000);
  });

  ws.addEventListener('message', (ev) => {
    try { handleEnvelope(JSON.parse(ev.data)); }
    catch (err) { console.warn('ws: non-JSON frame:', ev.data); }
  });

  ws.addEventListener('close', () => {
    setPill('down', 'disconnected');
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
    // Reconnect after a short backoff. Keep it simple for the skeleton.
    setTimeout(connect, 2000);
  });

  ws.addEventListener('error', () => {
    setPill('down', 'error');
  });
}

// ---- boot ----------------------------------------------------------------

loadHealth();
connect();
