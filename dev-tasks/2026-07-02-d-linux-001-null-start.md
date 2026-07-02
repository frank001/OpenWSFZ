# Dev Handoff — D-LINUX-001 (amendment): null-start audio device on Linux

**Date:** 2026-07-02  
**Branch:** `fix/d-linux-001-settings-audio-device` (continue on same branch)  
**Supersedes:** the first fix in `f34c6e7`  
**Raised by:** QA — UAT FAIL; Captain confirmed non-functional after settings save

---

## What the first fix got right

`f34c6e7` correctly identified the pattern: when `GET /api/v1/audio/devices` returns
`[]` (Linux / no WASAPI), `audioOpaqueFields` should carry the configured device ID
forward through a save so it is not silently nulled out.

---

## What it got wrong — the null-start case

The guard in `web/js/settings.js` (line ~488) is:

```js
audioOpaqueFields = (devices.length === 0 && config.audioDeviceId)
    ? { audioDeviceId: config.audioDeviceId, ... }
    : {};
```

`config.audioDeviceId` is `null` on a fresh Linux install (or after any previous
settings save that wiped it). `null` is **falsy** in JavaScript, so the condition
evaluates to `false` → `audioOpaqueFields` stays `{}` → the save handler falls
through to:

```js
: (audioOpaqueFields.audioDeviceId ?? null)   // → null
```

…and the POST body contains `"audioDeviceId": null`. The daemon then has no audio
device and captures silence (`noise_floor = -120.0 dB`). Observed live on
2026-07-02; confirmed by Captain.

The Playwright UAT missed this because it pre-seeded `"pulse"` via the API before
loading the settings page, so `config.audioDeviceId` was non-null when the JS ran.

---

## Required change — `web/js/settings.js`

**File:** `web/js/settings.js`  
**Line:** ~488 (`audioOpaqueFields = ...` inside `DOMContentLoaded`)

### Before (broken)

```js
audioOpaqueFields = (devices.length === 0 && config.audioDeviceId)
    ? {
        audioDeviceId:           config.audioDeviceId,
        audioDeviceFriendlyName: config.audioDeviceFriendlyName ?? null,
      }
    : {};
```

### After (correct)

```js
// D-LINUX-001 (amended): when the device list is empty, ALWAYS capture the
// configured ID (or default to "pulse" if unconfigured) so a settings save
// never leaves the daemon without an audio device.  The explicit-(none) escape
// hatch is preserved: the 'change' listener on deviceSelect still clears
// audioOpaqueFields, so a deliberate operator selection of "(none)" is always
// authoritative.
audioOpaqueFields = (devices.length === 0)
    ? {
        audioDeviceId:           config.audioDeviceId || 'pulse',
        audioDeviceFriendlyName: config.audioDeviceFriendlyName ?? null,
      }
    : {};
```

**That is the entire code change.** Two things changed:
1. The `&& config.audioDeviceId` condition is removed — `audioOpaqueFields` is
   populated whenever the device list is empty, even when the existing value is null.
2. `config.audioDeviceId || 'pulse'` — if the config has null/empty, default to
   `"pulse"`, which is the PulseAudio device string the daemon uses to capture
   from the PulseAudio default source on Linux.

No change to the `change` listener or the save handler is required — the existing
code handles those paths correctly.

---

## Also update the deployment copy

The same file was deployed to `qa/rr-study/linux-daemon/web/js/settings.js` (a
copy the running daemon serves). After editing `web/js/settings.js`, copy it:

```bash
cp web/js/settings.js qa/rr-study/linux-daemon/web/js/settings.js
```

Note: `linux-daemon/web/` is a git-tracked directory — this file will show up
in `git status` and must be committed along with `web/js/settings.js`.

---

## Update the commit message

Replace or amend the `f34c6e7` commit message to note the amendment:

```
fix(settings): default audioDeviceId to "pulse" when unenumerated on Linux (D-LINUX-001)
```

Or, if amending is undesirable, a follow-up commit on the same branch is fine:

```
fix(settings): default to "pulse" when audioDeviceId is null on Linux (D-LINUX-001 amendment)
```

---

## Acceptance criteria

- [ ] Settings page opened on Linux daemon with **`audioDeviceId: null`** in config.
  - Save any setting without touching the audio dropdown.
  - `GET /api/v1/config` returns `"audioDeviceId": "pulse"`.
  - Daemon log shows audio capture active (not `noise_floor = -120.0 dB`).
- [ ] Settings page opened on Linux daemon with `audioDeviceId: "pulse"` already set.
  - Save any setting without touching the audio dropdown.
  - `GET /api/v1/config` still returns `"audioDeviceId": "pulse"`.
- [ ] Deliberate clear on Linux: open Settings, explicitly select "(none)" in the
  dropdown, save.
  - `GET /api/v1/config` returns `"audioDeviceId": null`.
  - (This is the operator's intentional choice; the fix must not block it.)
- [ ] Windows flow unaffected: `devices.length > 0` → `audioOpaqueFields = {}`
  → device ID taken from `deviceSelect.value` as before.
- [ ] `node --check web/js/settings.js` passes.

---

## QA note — revised UAT test

The Playwright script in `qa/uat-tmp/` has been removed. The revised test must
start from `audioDeviceId: null` (do **not** pre-seed via API before loading
the settings page). Acceptance criterion 1 above is the key regression scenario.

---

## References

- First fix: `f34c6e7` on branch `fix/d-linux-001-settings-audio-device`
- Original handoff: `dev-tasks/2026-07-01-d-linux-001-settings-wipe-audio-device.md`
- RUNBOOK §1.5 — Linux daemon config (`audioDeviceId: "pulse"`)
