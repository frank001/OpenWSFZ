/**
 * Settings page logic.
 * - Loads audio devices and current config from the API on page load.
 * - Populates the device selector and port field.
 * - Handles Save: POSTs updated config and shows success/error feedback.
 *
 * @module settings
 */

import { getConfig, getDevices, postConfig } from './api.js';

const deviceSelect          = /** @type {HTMLSelectElement} */ (document.getElementById('device-select'));
const portInput             = /** @type {HTMLInputElement}  */ (document.getElementById('port-input'));
const cycleCountdownToggle  = /** @type {HTMLInputElement}  */ (document.getElementById('cycle-countdown-toggle'));
const logLevelSelect        = /** @type {HTMLSelectElement} */ (document.getElementById('log-level-select'));
const saveBtn               = /** @type {HTMLButtonElement} */ (document.getElementById('save-btn'));
const feedback              = /** @type {HTMLElement}       */ (document.getElementById('feedback'));

// ── Load config and devices ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [config, devices] = await Promise.all([getConfig(), getDevices()]);

    // Populate device selector.
    deviceSelect.innerHTML = '';

    // Always add a "none" option so the operator can explicitly deselect.
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
        opt.value       = dev.id;    // persist by device ID (WasapiAudioSource.GetDevice needs the GUID)
        opt.textContent = dev.name;
        deviceSelect.appendChild(opt);
      }
    }

    // Pre-select the currently configured device.
    deviceSelect.value = config.audioDeviceName ?? '';

    // Pre-fill port.
    portInput.value = String(config.port);

    // Pre-check the cycle countdown toggle.
    cycleCountdownToggle.checked = config.showCycleCountdown ?? false;

    // Pre-select the current log level (default to 'Information' if not set).
    logLevelSelect.value = config.logLevel ?? 'Information';

  } catch (err) {
    showFeedback(`Failed to load settings: ${err.message}`, 'error');
  }
});

// ── Save ──────────────────────────────────────────────────────────────────

saveBtn.addEventListener('click', async () => {
  saveBtn.disabled = true;
  clearFeedback();

  const audioDeviceName    = deviceSelect.value.trim() || null;
  const port               = parseInt(portInput.value, 10);
  const showCycleCountdown = cycleCountdownToggle.checked;
  const logLevel           = logLevelSelect.value;

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    showFeedback('Port must be a number between 1 and 65535.', 'error');
    saveBtn.disabled = false;
    return;
  }

  try {
    await postConfig({ audioDeviceName, port, showCycleCountdown, logLevel });
    showFeedback('Saved ✓', 'success');
    // Re-enable after a short delay so the operator can see the feedback.
    setTimeout(() => { saveBtn.disabled = false; }, 2000);
  } catch (err) {
    showFeedback(`Save failed — ${err.message}`, 'error');
    saveBtn.disabled = false;
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────

function showFeedback(message, type) {
  feedback.textContent = message;
  feedback.className   = type; // 'success' | 'error'
}

function clearFeedback() {
  feedback.textContent = '';
  feedback.className   = '';
}
