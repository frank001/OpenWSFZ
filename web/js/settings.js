/**
 * Settings page logic.
 * - Loads audio devices and current config from the API on page load.
 * - Populates the device selector, port field, and logging controls.
 * - Handles Save: POSTs updated config and shows success/error feedback.
 *
 * @module settings
 */

import { getConfig, getDevices, postConfig, getStatus } from './api.js';

const deviceSelect          = /** @type {HTMLSelectElement} */ (document.getElementById('device-select'));
const portInput             = /** @type {HTMLInputElement}  */ (document.getElementById('port-input'));
const cycleCountdownToggle  = /** @type {HTMLInputElement}  */ (document.getElementById('cycle-countdown-toggle'));
const logLevelSelect        = /** @type {HTMLSelectElement} */ (document.getElementById('log-level-select'));
const saveBtn               = /** @type {HTMLButtonElement} */ (document.getElementById('save-btn'));
const feedback              = /** @type {HTMLElement}       */ (document.getElementById('feedback'));

// Decode log controls (p9)
const decodeLogEnabled      = /** @type {HTMLInputElement}  */ (document.getElementById('decode-log-enabled'));
const decodeLogPath         = /** @type {HTMLInputElement}  */ (document.getElementById('decode-log-path'));
const decodeLogDialFreq     = /** @type {HTMLInputElement}  */ (document.getElementById('decode-log-dial-freq'));
const decodeLogDependent    = /** @type {HTMLElement}       */ (document.getElementById('decode-log-dependent'));

// CAT controls (p16)
const catEnabled         = /** @type {HTMLInputElement}  */ (document.getElementById('cat-enabled'));
const catRigModel        = /** @type {HTMLSelectElement} */ (document.getElementById('cat-rig-model'));
const catSerialPort      = /** @type {HTMLInputElement}  */ (document.getElementById('cat-serial-port'));
const catBaudRate        = /** @type {HTMLInputElement}  */ (document.getElementById('cat-baud-rate'));
const catRigctldHost     = /** @type {HTMLInputElement}  */ (document.getElementById('cat-rigctld-host'));
const catRigctldPort     = /** @type {HTMLInputElement}  */ (document.getElementById('cat-rigctld-port'));
const catPollInterval    = /** @type {HTMLInputElement}  */ (document.getElementById('cat-poll-interval'));
const catSerialFields    = /** @type {HTMLElement}       */ (document.getElementById('cat-serial-fields'));
const catRigctldFields   = /** @type {HTMLElement}       */ (document.getElementById('cat-rigctld-fields'));
const catStatusValue     = /** @type {HTMLElement}       */ (document.getElementById('cat-status-value'));

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

// ── Load config and devices ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [config, devices, status] = await Promise.all([getConfig(), getDevices(), getStatus()]);

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
    catSerialPort.value     = cat.serialPort        ?? '';
    catBaudRate.value       = String(cat.baudRate   ?? 9600);
    catRigctldHost.value    = cat.rigctldHost       ?? '127.0.0.1';
    catRigctldPort.value    = String(cat.rigctldPort ?? 4532);
    catPollInterval.value   = String(cat.pollIntervalSeconds ?? 1);
    updateCatVisibility();

    // Show live CAT status from the daemon status endpoint.
    updateCatStatusBadge(status?.catConnectionStatus ?? null);

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
 * Update the read-only CAT status badge.
 * @param {string|null} status  'Connected', 'Connecting', 'Error', 'Disabled', or null
 */
function updateCatStatusBadge(status) {
  const s = (status ?? 'Disabled').toLowerCase();
  catStatusValue.textContent = status ?? 'Disabled';
  catStatusValue.className   = `cat-status-badge cat-${s}`;
}

catRigModel.addEventListener('change', updateCatVisibility);

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

  const port               = parseInt(portInput.value, 10);
  const showCycleCountdown = cycleCountdownToggle.checked;
  const logLevel           = logLevelSelect.value;

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    showFeedback('Port must be a number between 1 and 65535.', 'error');
    saveBtn.disabled = false;
    return;
  }

  // p16: collect CAT config.
  const cat = {
    enabled:             catEnabled.checked,
    rigModel:            catRigModel.value,
    serialPort:          catSerialPort.value.trim()   || 'COM6',
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

  try {
    await postConfig({
      audioDeviceId,
      audioDeviceFriendlyName,
      port,
      showCycleCountdown,
      logLevel,
      decodeLog,
      logging,
      cat,
    });
    showFeedback('Saved ✓', 'success');
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
