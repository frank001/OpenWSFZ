## QA Review — settings-audio-output-device

**Verdict: APPROVED** — 2026-06-14
**Reviewer:** QA Engineer
**Branch:** `feat/settings-audio-output-device` (`9ad1574`)
**Test result:** 349 passed, 0 failed, 0 skipped

---

## Pre-archive to-do list

The following items must be resolved before archiving this change. Neither is a
blocking defect — the branch has been cleared for merge — but both represent
open debt that would otherwise be lost when the change artifact is archived.

### TODO-1 — Add "zero render devices" unit test for WasapiAudioOutputDeviceProvider

**Spec scenario (specs/audio-output-device/spec.md):**
> WHEN GetDevicesAsync() is called on a host with no audio render devices
> THEN return empty list (zero elements)

The existing tests cover:
- Enumerate override returns two devices → two returned ✅
- Enumerate override throws → empty list returned ✅

**Missing:** enumerate override returns `[]` → empty list returned. The production
code handles this correctly (the loop produces no elements), but the spec scenario
is undemonstrated by any test.

**Fix:** Add one test to `WasapiAudioOutputDeviceProviderTests.cs`:
```csharp
[Fact(DisplayName = "FR-XXX: WasapiAudioOutputDeviceProvider returns empty list when no render devices are present")]
public async Task GetDevicesAsync_ReturnsEmptyList_WhenEnumerateOverrideReturnsEmpty()
{
    var provider = new WasapiAudioOutputDeviceProvider(
        NullLogger<WasapiAudioOutputDeviceProvider>.Instance,
        () => Array.Empty<AudioDeviceInfo>());

    var devices = await provider.GetDevicesAsync();

    devices.Should().BeEmpty("zero render devices must produce an empty list, not an error");
}
```

---

### TODO-2 — Assign formal FR numbers and update FR-NEW test tags

All 8 new tests use the prefix `"FR-NEW:"` in their display names. The
`TestAssemblyScanner` regex requires `(FR|NFR)-\d{3}` (three decimal digits).
`"NEW"` does not match, so all 8 tests are invisible to the traceability gate —
the gate passes only because these tests are *ignored*, not because they are
tracked.

**Affected tests (8 total):**

| File | Display name |
|------|-------------|
| `WasapiAudioOutputDeviceProviderTests.cs` | `FR-NEW: SubprocessAudioOutputDeviceProvider returns empty list without throwing` |
| `WasapiAudioOutputDeviceProviderTests.cs` | `FR-NEW: WasapiAudioOutputDeviceProvider returns device list via enumerate override` |
| `WasapiAudioOutputDeviceProviderTests.cs` | `FR-NEW: WasapiAudioOutputDeviceProvider returns empty list and does not throw when enumerate override throws` |
| `JsonConfigStoreTests.cs` | `FR-NEW: AppConfig.AudioOutputDeviceId and AudioOutputFriendlyName default to null` |
| `JsonConfigStoreTests.cs` | `FR-NEW: Config without audioOutputDeviceId deserialises to null (backward compat)` |
| `JsonConfigStoreTests.cs` | `FR-NEW: AudioOutputDeviceId and AudioOutputFriendlyName round-trip via config file` |
| `AudioOutputDevicesEndpointTests.cs` | `FR-NEW: GET /api/v1/audio/output-devices returns 200 with JSON array of render devices` |
| `AudioOutputDevicesEndpointTests.cs` | `FR-NEW: GET /api/v1/audio/output-devices returns 200 with empty array when no render devices` |

**Fix:** Assign the next available FR numbers (FR-052 onwards, or whatever the
current ceiling is), register them in `openspec/specs/`, and replace `FR-NEW`
with the assigned IDs in each test's `DisplayName`. Also add the new
`audio-output-device` spec to `openspec/specs/audio-output-device/spec.md` and
update `openspec/specs/configuration/spec.md` and
`openspec/specs/web-frontend/spec.md` with the additions from this change.

---

### TODO-3 (Optional) — Rename WasapiAudioOutputDeviceProviderTests.cs

The `SubprocessAudioOutputDeviceProviderTests` class lives in
`WasapiAudioOutputDeviceProviderTests.cs`. The file name implies WASAPI content
only. Consider renaming to `AudioOutputDeviceProviderTests.cs`.

**Classification:** Observation — no functional impact.

---

## Positive observations (for the record)

- `DeviceState.Disabled` included in WASAPI enumeration — matches spec wording precisely.
- Null-posting logic in `settings.js` correctly resolves both fields to `null` when the placeholder is selected.
- `snapshotForm()` correctly includes `audioOutputDeviceId` — no spurious dirty state on load.
- Pre-select guard handles "device no longer present" case cleanly.
- `InMemoryAudioOutputDeviceProvider` default stub in `WebApp.cs` ensures test hygiene.
