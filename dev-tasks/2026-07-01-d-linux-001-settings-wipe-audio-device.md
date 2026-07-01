# Dev Handoff — D-LINUX-001: Settings save wipes `audioDeviceId` on Linux

**Date:** 2026-07-01  
**Branch:** `fix/d-linux-001-settings-audio-device`  
**Raised by:** QA — observed during WSL2 R&R environment bring-up  

---

## Context

The Linux daemon has no WASAPI audio device enumeration. `GET /api/v1/audio/devices`
returns `[]` on Linux by design — the audio device is configured manually as
`"audioDeviceId": "pulse"` in the JSON config file.

When the operator opens Settings in the browser UI and saves any setting, the
settings page serialises the audio device dropdown value (which is empty / null,
because the device list is unpopulated) and POSTs the entire config including
`"audioDeviceId": null`. This silently overwrites the manually configured `"pulse"`
value, and the daemon stops capturing audio on the next pipeline restart.

The defect was triggered in the 2026-07-01 session: the operator opened the
now-current settings page (tabs layout), changed an unrelated setting, and saved.
The daemon log subsequently showed `noise_floor=-120.0 dB` (silence) on all cycles.
Manual `curl -X POST /api/v1/config` with the full correct body was required to
recover.

---

## Actions

1. **Locate the settings save handler** in `web/js/settings.js`.  
   Find the section that serialises the audio device fields into the save payload
   (look for `audioDeviceId`, the device `<select>` element, or the General /
   Audio tab save block).

2. **Apply the following guard before including `audioDeviceId` in the payload:**  
   Only include `audioDeviceId` (and `audioDeviceFriendlyName`) in the POST body
   if the device dropdown has a non-empty selected value.  
   If the dropdown is empty (i.e. `select.value === ""` or the options list is
   empty), **omit** both fields from the payload entirely so the server retains
   the existing value.

   Suggested pattern (adjust to match existing code style):
   ```js
   const deviceSelect = document.getElementById("audioDeviceSelect"); // adjust id
   if (deviceSelect && deviceSelect.value) {
       payload.audioDeviceId = deviceSelect.value;
       payload.audioDeviceFriendlyName = ...; // existing logic
   }
   // else: omit — server keeps its current value
   ```

3. **Check `POST /api/v1/config` server-side merge behaviour** in `Program.cs` or
   the relevant config endpoint handler. Confirm whether a `null` value in the
   posted JSON overwrites an existing non-null value, or is treated as "no change".
   If the server treats `null` as an explicit override (likely), the client-side
   guard in step 2 is sufficient. If the server already merges, document that
   explicitly as the fix instead.

4. **Add a regression test** in `Web.Tests` (or `Config.Tests`):  
   - POST a config with `"audioDeviceId": null` to a daemon whose current config
     has `"audioDeviceId": "pulse"`.  
   - Assert that `GET /api/v1/config` still returns `"audioDeviceId": "pulse"`  
     (i.e. the null did not overwrite the existing value).  
   *Note:* This test may require a server-side fix rather than a client-side guard,
   depending on findings from step 3.

---

## Acceptance criteria

- [ ] Saving any settings tab on the Linux daemon UI **does not** change
      `audioDeviceId` when the audio device dropdown is empty.
- [ ] `GET /api/v1/config` after a settings save still returns
      `"audioDeviceId": "pulse"` (or whatever was previously configured).
- [ ] The regression test passes.
- [ ] The fix does not break the Windows settings flow (where the dropdown IS
      populated and saving the selected device must still work).

---

## References

- `web/js/settings.js` — client-side settings serialisation  
- `src/OpenWSFZ.Daemon/Program.cs` — `POST /api/v1/config` handler  
- `src/OpenWSFZ.Config/` — config merge/deserialise logic  
- `qa/rr-study/RUNBOOK.md` §1.5 — Linux daemon config (`audioDeviceId: "pulse"`)  
- Deferred QA items: R3-O1, R3-O2 in MEMORY.md — related pattern of falsy-value
  substitution in `settings.js` parse blocks  
