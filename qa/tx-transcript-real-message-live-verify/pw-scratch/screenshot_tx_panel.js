// One-shot Playwright screenshot check for fix-tx-transcript-real-message (TX-D05).
// Starts a real, isolated OpenWSFZ.Daemon (Release build), drives the same
// EngagePoint.SendReport jump-in as live_verify_tx_transcript.py via a real HTTP POST, opens the
// real index.html/main.js in a real Chromium tab connected over the real WebSocket, and screenshots
// the TX panel + QSO Transcript so the fix can be visually compared against the Captain's original
// bug report (which showed "+00" on every "sent report" line).
//
// Run from repo root: node qa/tx-transcript-real-message-live-verify/pw-scratch/screenshot_tx_panel.js

const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const PORT = 18769;
const BASE = `http://127.0.0.1:${PORT}`;
const OUR_CALLSIGN = 'Q1OFZ';
const OUR_GRID = 'JO33';
const PARTNER_CALLSIGN = 'Q9AAA';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function httpGet(urlPath) {
  const res = await fetch(BASE + urlPath);
  return res.json();
}
async function httpPost(urlPath, body) {
  const res = await fetch(BASE + urlPath, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  let json = null;
  try { json = await res.json(); } catch { /* ignore */ }
  return { status: res.status, body: json };
}

async function waitForReady(timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try { return await httpGet('/api/v1/status'); } catch { await sleep(300); }
  }
  throw new Error('daemon not ready');
}

function floorTo15s(date) {
  const s = Math.floor(date.getTime() / 1000);
  return new Date((s - (s % 15)) * 1000);
}

async function main() {
  const exe = process.platform === 'win32' ? 'OpenWSFZ.Daemon.exe' : 'OpenWSFZ.Daemon';
  const binary = path.join(REPO_ROOT, 'src', 'OpenWSFZ.Daemon', 'bin', 'Release', 'net10.0', exe);
  if (!fs.existsSync(binary)) {
    console.error('ENVIRONMENT UNAVAILABLE: Release daemon binary not found at', binary);
    process.exit(2);
  }

  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'owsfz-txd05-shot-'));
  const configPath = path.join(scratch, 'config.json');
  const logsDir = path.join(scratch, 'logs');
  fs.mkdirSync(logsDir, { recursive: true });
  const daemonLogPath = path.join(scratch, 'daemon.log');

  // Phase 0: throwaway start to enumerate audio devices.
  fs.writeFileSync(configPath, '{}');
  let proc = spawn(binary, ['--port', String(PORT), '--config', configPath],
    { cwd: REPO_ROOT, stdio: ['ignore', fs.openSync(daemonLogPath, 'w'), 'pipe'] });
  await waitForReady();
  const inputDevices = await httpGet('/api/v1/audio/devices');
  const outputDevices = await httpGet('/api/v1/audio/output-devices');
  const inputDev = inputDevices.find(d => /cable output|voicemeeter out/i.test(d.name)) || inputDevices[0];
  const outputDev = outputDevices.find(d => /cable input|voicemeeter in|speakers/i.test(d.name)) || outputDevices[0];
  proc.kill();
  await sleep(500);

  // Phase 1: final config — Answerer role, armed.
  const config = {
    audioDeviceId: inputDev ? inputDev.id : null,
    audioOutputDeviceId: outputDev ? outputDev.id : null,
    port: PORT,
    decodingEnabled: true,
    logLevel: 'Information',
    decodeLog: { enabled: true, path: path.join(logsDir, 'ALL.TXT').replace(/\\/g, '/'), dialFrequencyMHz: 7.074 },
    tx: {
      autoAnswer: true, callsign: OUR_CALLSIGN, grid: OUR_GRID, retryCount: 0,
      watchdogMinutes: 4, rxAudioOffsetHz: 1500, txAudioOffsetHz: 1500, holdTxFreq: false,
      role: 'Answerer', callerPartnerSelect: 'First', qsoConfirmation: false,
    },
  };
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

  proc = spawn(binary, ['--port', String(PORT), '--config', configPath],
    { cwd: REPO_ROOT, stdio: ['ignore', fs.openSync(daemonLogPath, 'a'), 'pipe'] });
  await waitForReady();

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
    await page.goto(BASE + '/', { waitUntil: 'load' });

    // Let the initial GET /tx/status + WS connection settle.
    await sleep(1000);

    // Trigger the EngagePoint.SendReport jump-in — same scenario as
    // live_verify_tx_transcript.py's Scenario A, driven here from the real browser tab's own
    // WebSocket connection observing the resulting txState push.
    const cycleStart = floorTo15s(new Date()).toISOString();
    const snr = -7;
    const formatSnr = n => (n >= 0 ? '+' : '-') + String(Math.abs(n)).padStart(2, '0');
    const engageResult = await httpPost('/api/v1/tx/engage-decode', {
      message: `${OUR_CALLSIGN} ${PARTNER_CALLSIGN} ${formatSnr(snr)}`,
      frequencyHz: 900.0,
      cycleStartUtc: cycleStart,
      confirm: false,
      snr: snr,
    });
    console.log('engage-decode POST result:', engageResult.status, JSON.stringify(engageResult.body));

    // Wait for the TX panel's row 2 text to show the real report (not "+00"/"R+00").
    const deadline = Date.now() + 40000;
    let sawReal = false;
    while (Date.now() < deadline) {
      const row2Text = await page.locator('#tx-msg-2 .tx-msg-text').textContent().catch(() => null);
      if (row2Text && /R-07|R\+07/.test(row2Text)) { sawReal = true; break; }
      await sleep(300);
    }

    const outDir = path.join(REPO_ROOT, 'qa', 'tx-transcript-real-message-live-verify', 'live-reports');
    fs.mkdirSync(outDir, { recursive: true });
    const shotPath = path.join(outDir, 'tx-panel-real-report-screenshot.png');
    // Scroll the TX panel into view before capturing so both the message rows and the
    // QSO Transcript are visible in one shot, mirroring the Captain's original bug screenshot.
    const panel = page.locator('#tx-transcript-section').first();
    if (await panel.count() > 0) {
      await panel.scrollIntoViewIfNeeded().catch(() => {});
    }
    await page.screenshot({ path: shotPath, fullPage: true });

    console.log('Row 2 shows real report text:', sawReal);
    console.log('Screenshot written to:', shotPath);

    if (!sawReal) {
      const logText = fs.readFileSync(daemonLogPath, 'utf-8');
      console.log('--- daemon log tail ---');
      console.log(logText.split('\n').slice(-60).join('\n'));
    }

    process.exitCode = sawReal ? 0 : 1;
  } finally {
    await browser.close();
    proc.kill();
    await sleep(300);
    fs.rmSync(scratch, { recursive: true, force: true });
  }
}

main().catch(err => { console.error(err); process.exit(1); });
