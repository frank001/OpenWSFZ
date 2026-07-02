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

- [x] Saving any settings tab on the Linux daemon UI **does not** change
      `audioDeviceId` when the audio device dropdown is empty.
- [x] `GET /api/v1/config` after a settings save still returns
      `"audioDeviceId": "pulse"` (or whatever was previously configured).
- [ ] The regression test passes. — **No automated test added; see Implementation
      notes below for why, and what was verified instead.**
- [x] The fix does not break the Windows settings flow (where the dropdown IS
      populated and saving the selected device must still work).

---

## References

- `web/js/settings.js` — client-side settings serialisation  
- `src/OpenWSFZ.Daemon/Program.cs` — `POST /api/v1/config` handler  
- `src/OpenWSFZ.Config/` — config merge/deserialise logic  
- `qa/rr-study/RUNBOOK.md` §1.5 — Linux daemon config (`audioDeviceId: "pulse"`)  
- Deferred QA items: R3-O1, R3-O2 in MEMORY.md — related pattern of falsy-value
  substitution in `settings.js` parse blocks  

---

## Implementation notes (2026-07-02)

**Step 3 finding — server merge behaviour confirmed:** `POST /api/v1/config` in
`WebApp.cs` (`await store.SaveAsync(config, ct)`, line ~433) fully replaces
`store.Current` with the deserialised request body — there is no field-level
merge anywhere in the config pipeline. This is exercised deliberately by
existing tests (`AudioConfigIntegrationTests.PostConfig_PersistsUpdatedConfig_AndSubsequentGetReflectsChange`,
`LogLevel_RoundTrips_ViaConfigApi`), which post partial payloads and expect the
rest of the config to fall back to `AppConfig` defaults. Adding server-side
null-preservation would contradict this existing, intentional contract (and
would prevent an operator from ever *deliberately* clearing a field via a full
save). **The fix is client-side only**, per the task's own contingency note.

**Fix implemented in `web/js/settings.js`:**
- New `audioOpaqueFields` module-level variable, following the existing
  `catOpaqueFields` (FR-039) "carry forward server-managed fields the UI
  can't edit" pattern.
- On load, if `devices.length === 0` (the Linux case — `GET /api/v1/audio/devices`
  never enumerates) and `config.audioDeviceId` is non-null, the loaded
  `audioDeviceId`/`audioDeviceFriendlyName` are captured into
  `audioOpaqueFields`. `deviceSelect.value` still falls back to `''`
  ("(none)") since there's no matching `<option>`, but the real value is now
  remembered.
- Scoped strictly to the **empty-list** case, not "value doesn't match any
  option" — this deliberately leaves the pre-existing Windows
  disconnected/unplugged-device behaviour untouched, so an operator can still
  select "(none)" to deliberately clear a stale device on Windows.
- A `change` listener on `deviceSelect` clears `audioOpaqueFields` the moment
  the operator interacts with the dropdown, so a genuine selection (including
  explicitly picking "(none)" after first picking something else) is always
  authoritative and never silently reverted.
- The Save handler now falls back to `audioOpaqueFields.audioDeviceId` /
  `audioDeviceFriendlyName` when `deviceSelect.value` is empty, instead of
  unconditionally sending `null`.
- Windows flow (populated list, value matches an enumerated option) is
  unaffected: `audioOpaqueFields` stays `{}`, so `audioDeviceId` is taken
  straight from `deviceSelect.value` exactly as before.

**Why no automated regression test (step 4) was added:** the repository has
no JS test runner, harness, or `package.json` of any kind (`find` for
`package.json` / `.eslintrc*` at repo root returned nothing) — this mirrors
the prior R3-O1/R3-O2 JS-only fix (`eee59ca`), which also shipped without an
automated test. A C#-level regression test asserting "`POST` with
`audioDeviceId: null` does not overwrite the stored value" was considered and
rejected: it would assert server behaviour that is intentionally *not* being
changed (see Step 3 finding above) and would contradict the existing
`AudioConfigIntegrationTests` contract tests. What **was** verified:
- `node --check web/js/settings.js` — syntax valid.
- Full `AudioConfigIntegrationTests` suite (9 tests) re-run — all pass
  unchanged, confirming the server-side contract is untouched.
- Manual code-path trace through both the Linux (`devices.length === 0`) and
  Windows (populated list, matched/unmatched/user-cleared) scenarios (see
  above).

Recommend a UAT scenario (browser + WSL2 daemon, per the original defect
report) as the practical verification step for this fix, added to the next
UAT session.
