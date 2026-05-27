## Context

`AppConfig` has a single `AudioDeviceName` field that has always held the OS-internal device identifier (e.g. the WASAPI GUID string). The field name is misleading and the value is not operator-readable. `AudioDeviceInfo` already carries both `Id` and `Name`; the friendly name is available when the operator selects a device on the settings page but is discarded before it reaches the config. The fix is a schema rename plus a companion field, with a silent migration path for existing config files.

Current data flow:
```
operator selects device → settings.js POSTs { audioDeviceName: "{guid}" }
                       → AppConfig.AudioDeviceName = "{guid}"
                       → DaemonStatus.AudioDevice  = "{guid}"
                       → status bar shows "{guid}"
```

Target data flow:
```
operator selects device → settings.js POSTs { audioDeviceId: "{guid}", audioDeviceFriendlyName: "Jabra EVOLVE LINK" }
                       → AppConfig.AudioDeviceId = "{guid}", AudioDeviceFriendlyName = "Jabra EVOLVE LINK"
                       → DaemonStatus.AudioDevice = "Jabra EVOLVE LINK"
                       → status bar shows "Jabra EVOLVE LINK"
```

## Goals / Non-Goals

**Goals:**
- Status bar, heartbeat, and status events display the human-readable device name wherever one is available.
- Log messages use the friendly name with a GUID fallback.
- Existing `config.json` files with `audioDeviceName` continue to function: capture starts correctly; only the display name is missing until the operator re-saves.
- The rename is clean — no legacy field lurks in the serialised schema after a re-save.

**Non-Goals:**
- Dynamic resolution of friendly name from a running device list (the name is stored at selection time, not looked up live).
- Updating the friendly name automatically if the operator renames the device in Windows Sound settings.
- Changing any WASAPI or audio-source code — the device identifier string passed to `CaptureManager.StartAsync` is unchanged.

## Decisions

### D1 — Store friendly name at selection time, not at status-event build time

**Decision:** Persist `audioDeviceFriendlyName` in `config.json` when the operator saves settings. Do not look it up dynamically from `IAudioDeviceProvider` when building `DaemonStatus`.

**Rationale:** Dynamic lookup requires an async call to `IAudioDeviceProvider.GetDevicesAsync()` on every status/heartbeat cycle. If the device list is momentarily unavailable (device removed, driver reload), the displayed name would flicker or go blank. Storing the name at selection time is simpler, always fast, and correct for the common case: operators choose a device, leave it plugged in, and expect to see its name. The only downside is staleness if the OS device label changes — acceptable for v1.

---

### D2 — Migration via post-load fixup in JsonConfigStore, not via a legacy JsonPropertyName on AppConfig

**Decision:** In `JsonConfigStore.LoadAsync()`, after deserialising to `AppConfig`, if `AudioDeviceId` is null, read the raw `JsonDocument` for a `audioDeviceName` key and promote its value to `AudioDeviceId`. Do not add a `LegacyAudioDeviceName` property to the `AppConfig` record itself.

**Rationale:** Keeping the legacy field on `AppConfig` would pollute the model indefinitely. A post-load fixup in the store is a one-time migration: the legacy key is consumed, the `AppConfig` in memory has the correct field names, and the next `SaveAsync` writes the new schema. The fixup is ~5 lines of `JsonDocument` code and requires no new serialiser registrations.

The existing "unknown fields are preserved" behaviour means `audioDeviceName` will be written back verbatim if `AudioDeviceId` is populated (they coexist on the first save after migration). That is acceptable — on the second save both the new fields are present and `audioDeviceName` is dropped because it is not part of the `AppConfig` schema.

Actually: on re-save after migration, `AppConfig` is serialised from the in-memory record, which only contains `audioDeviceId` and `audioDeviceFriendlyName`. The raw "unknown fields" preservation only applies if the implementation threads unknown fields through a `JsonObject` — if the current `JsonConfigStore` does a simple `JsonSerializer.Serialize(config)`, the legacy `audioDeviceName` key is dropped on first re-save. Either behaviour is correct: the device ID was migrated; the legacy key is redundant.

---

### D3 — `AppConfig.AudioDeviceId` and `AppConfig.AudioDeviceFriendlyName` are both nullable

**Decision:** Both fields are `string?`. `AudioDeviceId == null` means no device is configured (same semantics as the old `AudioDeviceName == null`). `AudioDeviceFriendlyName == null` means no friendly name is stored (legacy migration path or device was configured before p7 landed).

**Display fallback chain:** `AudioDeviceFriendlyName ?? AudioDeviceId ?? "(no device)"`.

---

### D4 — No new FR required; this corrects a pre-existing defect in FR-019 / the web-frontend spec

**Decision:** The Settings page spec already states the status bar SHALL display "the active audio device **name**" and the status event carries an `audioDevice` field. Displaying the GUID is a spec violation, not a missing feature. This change adds a new FR (FR-025) to make the requirement explicit and testable, but there is no new capability being introduced.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Existing integration or unit tests construct `AppConfig` with `AudioDeviceName` — they will fail to compile | All such tests are updated in this change as part of task 5 |
| A config saved by p7 is loaded by an older build that still uses `AudioDeviceName` | Older builds see `audioDeviceId` as an unknown field → `AudioDeviceName` is null → no device starts. Acceptable for a pre-release product; document in changelog. |
| The WASAPI device list changes between the operator's last save and the next session (device renamed or replaced) | `AudioDeviceId` still holds the original GUID; capture will start if the GUID is still valid. The friendly name shown will be stale but capture is unaffected. A future phase may re-resolve on startup. |
| `AudioDeviceFriendlyName` contains characters that break log format | Log message uses string interpolation — no injection risk; worst case the name contains special chars which are harmless in a log line. |

## Migration Plan

1. `AppConfig.cs` — rename field, add companion field.
2. `JsonConfigStore.cs` — add post-load fixup (5 lines).
3. `WebApp.cs`, `Program.cs` — update all references.
4. `settings.js` — update pre-select and POST body.
5. Tests — update `AppConfig` constructions.
6. Verify build and test suite green.

**Rollback:** Set `audioDeviceId` back to `audioDeviceName` in config.json manually, or revert the commit. No data is lost — the GUID is always preserved.

## Open Questions

None. All decisions are resolved.
