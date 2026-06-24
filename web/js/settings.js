/**
 * Settings page logic.
 * - Loads audio devices and current config from the API on page load.
 * - Populates the device selector, port field, and logging controls.
 * - Handles Save: POSTs updated config and shows success/error feedback.
 *
 * @module settings
 */

import { getConfig, getDevices, getOutputDevices, postConfig, getStatus, getSerialPorts, getFrequencies, postFrequencies, postCatRetry, getApiKey } from './api.js';

const deviceSelect          = /** @type {HTMLSelectElement} */ (document.getElementById('device-select'));
const outputDeviceSelect    = /** @type {HTMLSelectElement} */ (document.getElementById('output-device-select'));
const portInput             = /** @type {HTMLInputElement}  */ (document.getElementById('port-input'));
const cycleCountdownToggle  = /** @type {HTMLInputElement}  */ (document.getElementById('cycle-countdown-toggle'));
const logLevelSelect        = /** @type {HTMLSelectElement} */ (document.getElementById('log-level-select'));
const saveBtn               = /** @type {HTMLButtonElement} */ (document.getElementById('save-btn'));
const feedback              = /** @type {HTMLElement}       */ (document.getElementById('feedback'));
const unsavedBadge          = /** @type {HTMLElement}       */ (document.getElementById('unsaved-badge'));
const backLink              = /** @type {HTMLAnchorElement} */ (document.getElementById('back-link'));

// Decode log controls (p9)
const decodeLogEnabled      = /** @type {HTMLInputElement}  */ (document.getElementById('decode-log-enabled'));
const decodeLogPath         = /** @type {HTMLInputElement}  */ (document.getElementById('decode-log-path'));
const decodeLogDialFreq     = /** @type {HTMLInputElement}  */ (document.getElementById('decode-log-dial-freq'));
const decodeLogDependent    = /** @type {HTMLElement}       */ (document.getElementById('decode-log-dependent'));
const decodeLogDialFreqHint = /** @type {HTMLElement}       */ (document.getElementById('decode-log-dial-freq-hint'));

// CAT controls (p16)
const catEnabled         = /** @type {HTMLInputElement}  */ (document.getElementById('cat-enabled'));
const catRigModel        = /** @type {HTMLSelectElement} */ (document.getElementById('cat-rig-model'));
const catSerialPort      = /** @type {HTMLSelectElement} */ (document.getElementById('cat-serial-port'));
const catSerialRefreshBtn = /** @type {HTMLButtonElement} */ (document.getElementById('cat-serial-refresh'));
const catBaudRate        = /** @type {HTMLInputElement}  */ (document.getElementById('cat-baud-rate'));
const catRigctldHost     = /** @type {HTMLInputElement}  */ (document.getElementById('cat-rigctld-host'));
const catRigctldPort     = /** @type {HTMLInputElement}  */ (document.getElementById('cat-rigctld-port'));
const catPollInterval    = /** @type {HTMLInputElement}  */ (document.getElementById('cat-poll-interval'));
const catSerialFields    = /** @type {HTMLElement}       */ (document.getElementById('cat-serial-fields'));
const catRigctldFields   = /** @type {HTMLElement}       */ (document.getElementById('cat-rigctld-fields'));
const catStatusValue     = /** @type {HTMLElement}       */ (document.getElementById('cat-status-value'));
const catRetryBtn        = /** @type {HTMLButtonElement} */ (document.getElementById('cat-retry-btn'));

// General tab controls (callsign, grid, watchdog, retry moved from TX fieldset)
const txCallsign        = /** @type {HTMLInputElement} */ (document.getElementById('general-callsign'));
const txGrid            = /** @type {HTMLInputElement} */ (document.getElementById('general-grid'));
const txWatchdogMinutes = /** @type {HTMLInputElement} */ (document.getElementById('general-watchdog-minutes'));
const txRetryCount      = /** @type {HTMLInputElement} */ (document.getElementById('general-retry-count'));

// TX auto-answer control (remains on Radio tab)
const txAutoAnswer      = /** @type {HTMLInputElement} */ (document.getElementById('tx-auto-answer'));

// Logging controls
const loggingFileEnabled    = /** @type {HTMLInputElement}  */ (document.getElementById('logging-file-enabled'));
const loggingDirectory      = /** @type {HTMLInputElement}  */ (document.getElementById('logging-directory'));
const loggingFileLogLevel   = /** @type {HTMLSelectElement} */ (document.getElementById('logging-file-log-level'));
const loggingSchedule       = /** @type {HTMLSelectElement} */ (document.getElementById('logging-rotation-schedule'));
const loggingTime           = /** @type {HTMLInputElement}  */ (document.getElementById('logging-rotation-time'));
const loggingDay            = /** @type {HTMLSelectElement} */ (document.getElementById('logging-rotation-day'));
const loggingMaxFiles       = /** @type {HTMLInputElement}  */ (document.getElementById('logging-max-files'));
const loggingDependent      = /** @type {HTMLElement}       */ (document.getElementById('logging-dependent'));
const loggingTimeGroup      = /** @type {HTMLElement}       */ (document.getElementById('logging-time-group'));
const loggingDayGroup       = /** @type {HTMLElement}       */ (document.getElementById('logging-day-group'));

// Frequencies tab controls (FR-043)
const freqTbody  = /** @type {HTMLTableSectionElement} */ (document.getElementById('freq-tbody'));
const addFreqBtn = /** @type {HTMLButtonElement}       */ (document.getElementById('add-freq-btn'));

// Remote access controls (lan-remote-access)
const remoteAccessEnabled         = /** @type {HTMLInputElement}  */ (document.getElementById('remote-access-enabled'));
const remoteAccessPassphrase      = /** @type {HTMLInputElement}  */ (document.getElementById('remote-access-passphrase'));
const remoteAccessPassphraseGroup = /** @type {HTMLElement}       */ (document.getElementById('remote-access-passphrase-group'));
const remoteAccessPassToggle      = /** @type {HTMLButtonElement} */ (document.getElementById('remote-access-passphrase-toggle'));
const remoteAccessRestartWarning  = /** @type {HTMLElement}       */ (document.getElementById('remote-access-restart-warning'));
const remoteAccessDisclaimer      = /** @type {HTMLElement}       */ (document.getElementById('remote-access-disclaimer'));

// D-LAN-005: update the back-link to carry the API key so navigating back to the
// main page does not trigger an auth redirect.
// `backLink` is already captured at module scope above.
(function () {
  const key = getApiKey();
  if (key && backLink) {
    backLink.href = '/?key=' + encodeURIComponent(key);
  }
})();

// ── Tab switching (FR-035) ────────────────────────────────────────────────

const TAB_STORAGE_KEY = 'settings-tab';
const tabBtns   = /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll('.settings-tab-btn'));
const tabPanels = /** @type {NodeListOf<HTMLElement>}       */ (document.querySelectorAll('.settings-tab-panel'));

function activateTab(panelId) {
  tabBtns.forEach(btn => {
    const isActive = btn.getAttribute('aria-controls') === panelId;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', String(isActive));
  });
  tabPanels.forEach(panel => {
    panel.classList.toggle('active', panel.id === panelId);
  });
  sessionStorage.setItem(TAB_STORAGE_KEY, panelId);
}

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const panelId = btn.getAttribute('aria-controls');
    if (panelId) activateTab(panelId);
  });
});

// Restore last active tab on load.
const savedTab = sessionStorage.getItem(TAB_STORAGE_KEY);
if (savedTab && document.getElementById(savedTab)) {
  activateTab(savedTab);
}

// ── Serial port enumeration (FR-038) ─────────────────────────────────────

let portsLoaded = false;

async function loadSerialPorts() {
  try {
    const ports      = await getSerialPorts();
    const configured = catSerialPort.value;

    catSerialPort.innerHTML = '';
    if (ports.length === 0) {
      const opt = document.createElement('option');
      opt.value       = configured || '';
      opt.textContent = configured ? configured : '(no ports found)';
      catSerialPort.appendChild(opt);
    } else {
      // If the configured value is not in the list, prepend it.
      const allPorts = ports.includes(configured) || !configured
        ? ports
        : [configured, ...ports];

      for (const p of allPorts) {
        const opt = document.createElement('option');
        opt.value       = p;
        opt.textContent = p;
        catSerialPort.appendChild(opt);
      }
      catSerialPort.value = configured || ports[0] || '';
    }
    portsLoaded = true;
  } catch {
    // Best-effort; leave the select with its current content.
  }
}

catRigModel.addEventListener('change', () => {
  updateCatVisibility();
  if (catRigModel.value === 'SerialCat' && !portsLoaded) {
    loadSerialPorts();
  }
});

catSerialRefreshBtn.addEventListener('click', () => {
  portsLoaded = false;
  loadSerialPorts();
});

// ── Dial frequency lock (FR-037) ──────────────────────────────────────────

function updateDialFreqLock() {
  const locked = catEnabled.checked;
  decodeLogDialFreq.disabled = locked;
  if (locked) {
    decodeLogDialFreqHint.textContent =
      'Overridden by CAT — the live rig frequency is used while polling is active.';
  } else {
    decodeLogDialFreqHint.textContent =
      'Your radio\'s VFO setting — written to each ALL.TXT line. ' +
      'Leave at 0.000 if you do not need this column.';
  }
}

catEnabled.addEventListener('change', updateDialFreqLock);

// ── Opaque server-managed fields (FR-039) ────────────────────────────────
// Fields the UI does not expose as editable must be carried forward unchanged
// when saving, to prevent the POST from resetting them to null.

let catOpaqueFields = {};

// ── Dirty-state snapshot (FR-040) ────────────────────────────────────────

/** JSON string of form values captured immediately after a successful page load.
 *  Compared against the current form state to determine the dirty flag.
 *  @type {string}
 */
let _cleanSnapshot = '';

/**
 * Serialise all editable form fields into the same shape as the postConfig
 * payload.  Used for dirty-state detection; NOT used for the actual save
 * (the save handler remains the authoritative source to avoid duplication).
 *
 * @returns {string}  JSON string of the current form values.
 */
function snapshotForm() {
  return JSON.stringify({
    audioDeviceId:        deviceSelect.value.trim() || null,
    audioOutputDeviceId:  outputDeviceSelect.value.trim() || null,
    port:                 portInput.value,
    showCycleCountdown:   cycleCountdownToggle.checked,
    logLevel:             logLevelSelect.value,
    decodeLog: {
      enabled:            decodeLogEnabled.checked,
      path:               decodeLogPath.value.trim(),
      dialFrequencyMHz:   decodeLogDialFreq.value,
    },
    logging: {
      fileEnabled:        loggingFileEnabled.checked,
      directory:          loggingDirectory.value.trim(),
      fileLogLevel:       loggingFileLogLevel.value,
      rotationSchedule:   loggingSchedule.value,
      rotationTime:       loggingTime.value,
      rotationDayOfWeek:  loggingDay.value,
      maxFiles:           loggingMaxFiles.value,
    },
    cat: {
      enabled:            catEnabled.checked,
      rigModel:           catRigModel.value,
      serialPort:         catSerialPort.value.trim(),
      baudRate:           catBaudRate.value,
      rigctldHost:        catRigctldHost.value.trim(),
      rigctldPort:        catRigctldPort.value,
      pollIntervalSeconds: catPollInterval.value,
    },
    tx: {
      autoAnswer:      txAutoAnswer.checked,
      callsign:        txCallsign.value.trim(),
      grid:            txGrid.value.trim().toUpperCase(),
      watchdogMinutes: txWatchdogMinutes.value,
      retryCount:      txRetryCount.value,
    },
    // FR-043: include frequency table in dirty-state comparison (FR-040).
    _frequencies:         snapshotFrequencies(),
    // lan-remote-access: include remote access controls in dirty-state snapshot (task 5.6).
    remoteAccess: {
      enabled:    remoteAccessEnabled.checked,
      passphrase: remoteAccessPassphrase.value,
    },
  });
}

// ── Dirty-state tracking (FR-040) ────────────────────────────────────────

function isDirty() {
  return snapshotForm() !== _cleanSnapshot;
}

function onBeforeUnload(event) {
  event.preventDefault();
  // event.returnValue must be set for legacy Chromium compatibility.
  event.returnValue = '';
}

function syncDirtyUI() {
  const dirty = isDirty();
  unsavedBadge.hidden = !dirty;

  // Guard: add/remove beforeunload only as needed to avoid stale listeners.
  if (dirty) {
    window.addEventListener('beforeunload', onBeforeUnload);
  } else {
    window.removeEventListener('beforeunload', onBeforeUnload);
  }
}

// Register form-level event delegation so every field edit is caught.
document.getElementById('settings-form').addEventListener('input',  syncDirtyUI);
document.getElementById('settings-form').addEventListener('change', syncDirtyUI);

// ── Breadcrumb navigation guard (FR-041) ─────────────────────────────────

backLink.addEventListener('click', event => {
  if (isDirty()) {
    const confirmed = window.confirm(
      'You have unsaved changes. Leave without saving?'
    );
    if (confirmed) {
      // Stand down the beforeunload guard — the operator has already confirmed
      // intent to discard. Without this, the browser fires beforeunload as part
      // of the navigation and produces a second, redundant prompt.
      window.removeEventListener('beforeunload', onBeforeUnload);
    } else {
      event.preventDefault();
    }
  }
});

// ── Frequencies tab (FR-043) ─────────────────────────────────────────────

/**
 * Read the current frequency table rows as an array of entry objects.
 * @returns {Array<{protocol: string, frequencyMHz: number, description: string}>}
 */
function collectFrequencies() {
  const rows = /** @type {NodeListOf<HTMLTableRowElement>} */ (
    freqTbody.querySelectorAll('tr[data-freq-row]')
  );
  return Array.from(rows).map(row => ({
    protocol:     /** @type {HTMLInputElement} */ (row.querySelector('.freq-protocol')).value.trim() || 'FT8',
    frequencyMHz: parseFloat(/** @type {HTMLInputElement} */ (row.querySelector('.freq-mhz')).value) || 0,
    description:  /** @type {HTMLInputElement} */ (row.querySelector('.freq-desc')).value.trim(),
  }));
}

/**
 * Serialise the frequency table contents for the dirty-state snapshot.
 * @returns {string}
 */
function snapshotFrequencies() {
  return JSON.stringify(collectFrequencies());
}

/**
 * Build and append a single frequency table row.
 * @param {string}  protocol
 * @param {number}  frequencyMHz
 * @param {string}  description
 */
function appendFreqRow(protocol, frequencyMHz, description) {
  const tr = document.createElement('tr');
  tr.setAttribute('data-freq-row', '');

  tr.innerHTML = `
    <td><input type="text"   class="freq-protocol" value="${escAttr(protocol)}" /></td>
    <td><input type="number" class="freq-mhz"      step="0.001" min="0" value="${escAttr(String(frequencyMHz.toFixed(3)))}" /></td>
    <td><input type="text"   class="freq-desc"     value="${escAttr(description)}" /></td>
    <td><button type="button" class="freq-delete-btn" aria-label="Delete row">✕</button></td>
  `;

  tr.querySelector('.freq-delete-btn').addEventListener('click', () => {
    tr.remove();
    syncDirtyUI();  // FR-040: deleting a row marks the form dirty
  });

  freqTbody.appendChild(tr);
}

/** Simple HTML attribute escape. */
function escAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}

/**
 * Render the full frequency table from an array of entries.
 * Clears any existing rows (including the placeholder).
 * @param {Array<{protocol: string, frequencyMHz: number, description: string}>} entries
 */
function renderFreqTable(entries) {
  freqTbody.innerHTML = '';

  if (entries.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="4" class="freq-placeholder"><em>No frequencies configured — click Add to begin</em></td>';
    freqTbody.appendChild(tr);
    return;
  }

  for (const e of entries) {
    appendFreqRow(e.protocol, e.frequencyMHz, e.description ?? '');
  }
}

addFreqBtn.addEventListener('click', () => {
  // Remove the placeholder row if present.
  const placeholder = freqTbody.querySelector('.freq-placeholder');
  if (placeholder) placeholder.closest('tr').remove();

  appendFreqRow('FT8', 0.000, '');
  syncDirtyUI();  // FR-040: adding a row marks the form dirty
});

// ── Load config and devices ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [config, devices, outputDevices, status, frequencies] = await Promise.all([
      getConfig(), getDevices(), getOutputDevices(), getStatus(), getFrequencies(),
    ]);

    // Populate device selector.
    deviceSelect.innerHTML = '';
    const noneOpt = document.createElement('option');
    noneOpt.value       = '';
    noneOpt.textContent = '(none)';
    deviceSelect.appendChild(noneOpt);

    if (devices.length === 0) {
      const noDevOpt = document.createElement('option');
      noDevOpt.disabled     = true;
      noDevOpt.textContent  = 'No devices found';
      deviceSelect.appendChild(noDevOpt);
    } else {
      for (const dev of devices) {
        const opt = document.createElement('option');
        opt.value       = dev.id;
        opt.textContent = dev.name;
        deviceSelect.appendChild(opt);
      }
    }

    // Pre-select the configured device (p7: use audioDeviceId, not audioDeviceName).
    deviceSelect.value = config.audioDeviceId ?? '';

    // Populate output device selector.
    outputDeviceSelect.innerHTML = '';
    const noOutputOpt = document.createElement('option');
    noOutputOpt.value       = '';
    noOutputOpt.textContent = '— No device —';
    outputDeviceSelect.appendChild(noOutputOpt);

    for (const dev of outputDevices) {
      const opt = document.createElement('option');
      opt.value       = dev.id;
      opt.textContent = dev.name;
      outputDeviceSelect.appendChild(opt);
    }

    // Pre-select configured output device; fall back to placeholder if null or not found.
    outputDeviceSelect.value = config.audioOutputDeviceId ?? '';
    if (outputDeviceSelect.value !== (config.audioOutputDeviceId ?? '')) {
      // Device no longer present — select the placeholder.
      outputDeviceSelect.value = '';
    }

    // Pre-fill port.
    portInput.value = String(config.port);

    // Pre-check cycle countdown.
    cycleCountdownToggle.checked = config.showCycleCountdown ?? false;

    // Pre-select console log level.
    logLevelSelect.value = config.logLevel ?? 'Information';

    // Pre-fill decode log controls (p9).
    const dl = config.decodeLog ?? {};
    decodeLogEnabled.checked  = dl.enabled          ?? false;
    decodeLogPath.value       = dl.path             ?? 'ALL.TXT';
    decodeLogDialFreq.value   = String(dl.dialFrequencyMHz ?? 0.0);
    updateDecodeLogVisibility();

    // Pre-fill logging controls (p6).
    const lg = config.logging ?? {};
    loggingFileEnabled.checked  = lg.fileEnabled       ?? false;
    loggingDirectory.value      = lg.directory         ?? 'logs';
    // Normalise legacy Serilog names (Verbose → Trace, Fatal → Critical) that may
    // appear in config files written before the UI adopted MEL terminology.
    loggingFileLogLevel.value   = normaliseMelLevel(lg.fileLogLevel);
    loggingSchedule.value       = lg.rotationSchedule  ?? 'daily';
    loggingTime.value           = lg.rotationTime      ?? '00:00';
    loggingDay.value            = lg.rotationDayOfWeek ?? 'Monday';
    loggingMaxFiles.value       = String(lg.maxFiles   ?? 7);

    updateLoggingVisibility();

    // Pre-fill CAT controls (p16).
    const cat = config.cat ?? {};
    catEnabled.checked      = cat.enabled          ?? false;
    catRigModel.value       = cat.rigModel         ?? 'SerialCat';
    catBaudRate.value       = String(cat.baudRate   ?? 9600);
    catRigctldHost.value    = cat.rigctldHost       ?? '127.0.0.1';
    catRigctldPort.value    = String(cat.rigctldPort ?? 4532);
    catPollInterval.value   = String(cat.pollIntervalSeconds ?? 1);
    updateCatVisibility();

    // Pre-populate the serial port select with the configured value so the Save
    // handler can read it before loadSerialPorts() completes.
    const configuredPort = cat.serialPort ?? '';
    catSerialPort.innerHTML = '';
    const initialOpt = document.createElement('option');
    initialOpt.value       = configuredPort;
    initialOpt.textContent = configuredPort || 'Loading ports…';
    catSerialPort.appendChild(initialOpt);
    catSerialPort.value = configuredPort;

    // Show live CAT status from the daemon status endpoint.
    updateCatStatusBadge(status?.catConnectionStatus ?? null);

    // FR-039: carry forward server-managed fields that the UI does not edit.
    catOpaqueFields = {
      lastPolledFrequencyMHz: cat.lastPolledFrequencyMHz ?? null,
    };

    // FR-037: update dial frequency lock state based on loaded CAT enabled flag.
    updateDialFreqLock();

    // FR-038: populate the serial port list if SerialCat is the active transport.
    // Awaited here (§8.1) so the baseline snapshot is captured after the select
    // is populated, preventing a spurious dirty state from the programmatic DOM
    // update that loadSerialPorts() performs.
    if (catRigModel.value === 'SerialCat') {
      await loadSerialPorts();
    }

    // TX auto-answer (ft8-qso-answerer-v1).
    const tx = config.tx ?? {};
    txCallsign.value          = tx.callsign        ?? 'Q1OFZ';
    txGrid.value              = tx.grid            ?? 'JO33';
    txAutoAnswer.checked      = tx.autoAnswer      ?? false;
    // A-02: pre-populate numeric TX fields so Save does not submit browser default (0).
    txWatchdogMinutes.value   = String(tx.watchdogMinutes ?? 4);
    txRetryCount.value        = String(tx.retryCount      ?? 3);

    // FR-043: populate the frequencies table.
    renderFreqTable(Array.isArray(frequencies) ? frequencies : []);

    // Pre-fill remote access controls (task 5.2).
    const ra = config.remoteAccess ?? {};
    remoteAccessEnabled.checked    = ra.enabled    ?? false;
    remoteAccessPassphrase.value   = ra.passphrase ?? '';
    updateRemoteAccessVisibility();

    // Capture the clean baseline after all fields are fully populated (FR-040).
    _cleanSnapshot = snapshotForm();

  } catch (err) {
    showFeedback(`Failed to load settings: ${err.message}`, 'error');
  }
});

// ── CAT visibility helpers (p16) ─────────────────────────────────────────

function updateCatVisibility() {
  const model = catRigModel.value;
  catSerialFields.style.display  = (model === 'SerialCat') ? '' : 'none';
  catRigctldFields.style.display = (model === 'RigCtld')   ? '' : 'none';
}

/**
 * Update the read-only CAT status badge and retry button visibility.
 * @param {string|null} status  'Connected', 'Connecting', 'Error', 'Disabled', or null
 */
function updateCatStatusBadge(status) {
  const s = (status ?? 'Disabled').toLowerCase();
  catStatusValue.textContent = status ?? 'Disabled';
  catStatusValue.className   = `cat-status-badge cat-${s}`;

  // Retry button is only useful when polling has been suspended after a failure.
  // The backend sets status to 'Error' exactly in that state.
  catRetryBtn.hidden = (status !== 'Error');
}

// ── CAT retry (FR-034) ───────────────────────────────────────────────────

catRetryBtn.addEventListener('click', async () => {
  catRetryBtn.disabled    = true;
  catRetryBtn.textContent = '↻ Retrying…';
  clearFeedback();

  try {
    await postCatRetry();

    // Give the backend time to complete the settle delay and first poll:
    // suspend-loop tick (≤200 ms) + settle delay (150 ms) + serial I/O (≤500 ms).
    await new Promise(r => setTimeout(r, 1500));

    // Re-fetch live status and refresh the badge.
    const status       = await getStatus();
    const newCatStatus = status?.catConnectionStatus ?? null;
    updateCatStatusBadge(newCatStatus);

    if (newCatStatus === 'Connected') {
      showFeedback('CAT connected ✓', 'success');
    } else {
      showFeedback('CAT still unavailable — verify radio and CAT cable.', 'error');
    }
  } catch (err) {
    showFeedback(`Retry failed — ${err.message}`, 'error');
    catRetryBtn.hidden = false;   // restore button so the operator can try again
  } finally {
    catRetryBtn.textContent = '↺ Retry';
    catRetryBtn.disabled    = false;
  }
});

// ── Remote access visibility (lan-remote-access) ─────────────────────────

/**
 * Show or hide the passphrase input, restart warning, and legal disclaimer
 * based on the current state of the enable toggle (task 5.3).
 */
function updateRemoteAccessVisibility() {
  const enabled = remoteAccessEnabled.checked;
  remoteAccessPassphraseGroup.style.display = enabled ? '' : 'none';
  remoteAccessRestartWarning.style.display  = enabled ? '' : 'none';
  remoteAccessDisclaimer.style.display      = enabled ? '' : 'none';
}

remoteAccessEnabled.addEventListener('change', updateRemoteAccessVisibility);

// Passphrase show/hide toggle (task 5.4).
remoteAccessPassToggle.addEventListener('click', () => {
  const isPassword = remoteAccessPassphrase.type === 'password';
  remoteAccessPassphrase.type = isPassword ? 'text' : 'password';
});

// ── Visibility helpers (p9) ──────────────────────────────────────────────

function updateDecodeLogVisibility() {
  const enabled = decodeLogEnabled.checked;
  decodeLogDependent.querySelectorAll('input').forEach(el => {
    /** @type {HTMLInputElement} */ (el).disabled = !enabled;
  });
}

decodeLogEnabled.addEventListener('change', updateDecodeLogVisibility);

// ── Visibility helpers (p6) ───────────────────────────────────────────────

function updateLoggingVisibility() {
  const enabled  = loggingFileEnabled.checked;
  const schedule = loggingSchedule.value;

  // Grey out all dependent controls when file logging is disabled.
  loggingDependent.querySelectorAll('input, select').forEach(el => {
    /** @type {HTMLInputElement|HTMLSelectElement} */ (el).disabled = !enabled;
  });
  loggingFileLogLevel.disabled     = !enabled;
  loggingSchedule.disabled         = !enabled;
  loggingTime.disabled             = !enabled;
  loggingDay.disabled              = !enabled;
  loggingMaxFiles.disabled         = !enabled;

  // Show/hide time and day based on schedule.
  loggingTimeGroup.style.display = (enabled && (schedule === 'daily' || schedule === 'weekly'))
      ? '' : 'none';
  loggingDayGroup.style.display  = (enabled && schedule === 'weekly')
      ? '' : 'none';
}

loggingFileEnabled.addEventListener('change', updateLoggingVisibility);
loggingSchedule.addEventListener('change',    updateLoggingVisibility);

// ── Save ──────────────────────────────────────────────────────────────────

saveBtn.addEventListener('click', async () => {
  saveBtn.disabled = true;
  clearFeedback();

  // p7: capture both device ID (for WASAPI) and friendly name (for display).
  const audioDeviceId           = deviceSelect.value.trim() || null;
  const selectedOption          = deviceSelect.options[deviceSelect.selectedIndex];
  const audioDeviceFriendlyName = audioDeviceId
      ? (selectedOption?.textContent?.trim() || null)
      : null;

  // Audio output device (TX pipeline routing).
  const audioOutputDeviceId       = outputDeviceSelect.value.trim() || null;
  const selectedOutputOption      = outputDeviceSelect.options[outputDeviceSelect.selectedIndex];
  const audioOutputFriendlyName   = audioOutputDeviceId
      ? (selectedOutputOption?.textContent?.trim() || null)
      : null;

  const port               = parseInt(portInput.value, 10);
  const showCycleCountdown = cycleCountdownToggle.checked;
  const logLevel           = logLevelSelect.value;

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    showFeedback('Port must be a number between 1 and 65535.', 'error');
    saveBtn.disabled = false;
    return;
  }

  // p16: collect CAT config — carry forward opaque server-managed fields (FR-039).
  const cat = {
    ...catOpaqueFields,          // ← carry forward server-managed fields
    enabled:             catEnabled.checked,
    rigModel:            catRigModel.value,
    serialPort:          catSerialPort.value.trim() || 'COM6',
    baudRate:            parseInt(catBaudRate.value, 10)    || 9600,
    rigctldHost:         catRigctldHost.value.trim()  || '127.0.0.1',
    rigctldPort:         parseInt(catRigctldPort.value, 10) || 4532,
    pollIntervalSeconds: Math.max(1, Math.min(60, parseInt(catPollInterval.value, 10) || 1)),
  };

  // p9: collect decode log config.
  const decodeLog = {
    enabled:          decodeLogEnabled.checked,
    path:             decodeLogPath.value.trim() || 'ALL.TXT',
    dialFrequencyMHz: parseFloat(decodeLogDialFreq.value) || 0.0,
  };

  // p6: collect logging config.
  const logging = {
    fileEnabled:       loggingFileEnabled.checked,
    directory:         loggingDirectory.value.trim() || 'logs',
    fileLogLevel:      loggingFileLogLevel.value,
    rotationSchedule:  loggingSchedule.value,
    rotationTime:      loggingTime.value || '00:00',
    rotationDayOfWeek: loggingDay.value,
    maxFiles:          parseInt(loggingMaxFiles.value, 10) || 7,
  };

  // TX auto-answer config (ft8-qso-answerer-v1).
  // callsign and grid are normalised to upper-case; fall back to placeholder
  // defaults so the server never receives null/empty strings.
  // A-02: watchdogMinutes and retryCount are pre-populated on load; fall back
  //       to defaults so the server never receives 0 and triggers a WRN clamp.
  const tx = {
    callsign:        txCallsign.value.trim().toUpperCase()     || 'Q1OFZ',
    grid:            txGrid.value.trim().toUpperCase()          || 'JO33',
    autoAnswer:      txAutoAnswer.checked,
    watchdogMinutes: parseInt(txWatchdogMinutes.value, 10)     || 4,
    retryCount:      parseInt(txRetryCount.value, 10)          || 3,
  };

  // FR-043: collect current frequency table entries for parallel POST.
  const freqEntries = collectFrequencies();

  try {
    // Collect remote access config (task 5.5).
    // Post null for passphrase when the input is empty so the server receives a
    // clean null rather than an empty string.
    const remoteAccess = {
      enabled:    remoteAccessEnabled.checked,
      passphrase: remoteAccessPassphrase.value.trim() || null,
    };

    // POST config and frequencies in parallel (FR-043 / FR-007).
    await Promise.all([
      postConfig({
        audioDeviceId,
        audioDeviceFriendlyName,
        audioOutputDeviceId,
        audioOutputFriendlyName,
        port,
        showCycleCountdown,
        logLevel,
        decodeLog,
        logging,
        cat,
        tx,
        remoteAccess,
      }),
      postFrequencies(freqEntries),
    ]);
    showFeedback('Saved ✓', 'success');
    _cleanSnapshot = snapshotForm();
    syncDirtyUI();          // clears the badge and removes the beforeunload guard
    setTimeout(() => { saveBtn.disabled = false; }, 2000);
  } catch (err) {
    showFeedback(`Save failed — ${err.message}`, 'error');
    saveBtn.disabled = false;
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────

/**
 * Normalise a file log-level string to MEL terminology.
 * Config files written by older versions of the UI used Serilog names
 * (Verbose, Fatal); the current UI uses MEL names (Trace, Critical).
 * Unknown values are passed through and will fall back to the select's
 * default when assigned.
 *
 * @param {string|undefined} level
 * @returns {string}
 */
function normaliseMelLevel(level) {
  if (level === 'Verbose') return 'Trace';
  if (level === 'Fatal')   return 'Critical';
  return level ?? 'Information';
}

function showFeedback(message, type) {
  feedback.textContent = message;
  feedback.className   = type;
}

function clearFeedback() {
  feedback.textContent = '';
  feedback.className   = '';
}
