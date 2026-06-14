## Context

OpenWSFZ already enumerates WASAPI **capture** (input) endpoints via `IAudioDeviceProvider`
/ `WasapiAudioDeviceProvider` and exposes them through `GET /api/v1/audio/devices`. The
selected device is persisted in `AppConfig.AudioDeviceId` / `AudioDeviceFriendlyName` and
displayed in the Settings → Radio hardware tab.

Before a TX pipeline can route audio to the transceiver, the operator must be able to
select which **render** (output/playback) endpoint to use. This design mirrors the existing
capture-device pattern precisely, differing only in `DataFlow.Render` instead of
`DataFlow.Capture`.

The existing provider is registered under `IAudioDeviceProvider`. We cannot repurpose that
registration for output devices without ambiguity in the DI container.

## Goals / Non-Goals

**Goals:**
- Introduce `IAudioOutputDeviceProvider` — a new interface with the same contract as
  `IAudioDeviceProvider` (`GetDevicesAsync`) — to keep the two flows separately injectable.
- Implement `WasapiAudioOutputDeviceProvider` on Windows using `DataFlow.Render` via the
  same `StaThread.Run` dispatch used by the capture provider.
- Provide a `PlatformAudioOutputDeviceProvider` factory (`#if WASAPI_SUPPORTED` for
  Windows; `SubprocessAudioOutputDeviceProvider` stub for Linux/macOS returning an empty
  list until a TX pipeline exists on those platforms).
- Register `IAudioOutputDeviceProvider` as a singleton in `WebApp.cs`.
- Expose `GET /api/v1/audio/output-devices` returning `[{id, name}]`, structurally
  identical to the capture endpoint.
- Extend `AppConfig` with `audioOutputDeviceId` (nullable string, default `null`) and
  `audioOutputFriendlyName` (nullable string, default `null`).
- Update `ConfigJsonContext` for the new fields.
- Add an **Audio output device** `<select id="output-device-select">` to the Radio
  hardware tab of `settings.html`, placed immediately below `#device-select`.
- Add `getOutputDevices()` to `api.js`.
- Include `audioOutputDeviceId` and `audioOutputFriendlyName` in the `POST /api/v1/config`
  save payload and surface them in `GET /api/v1/config`.

**Non-Goals:**
- Implementing the TX pipeline itself — this change only provisions the device selection.
- Linux-specific output device enumeration — the stub returns an empty list; this is
  acceptable while TX is Windows-only.
- Refresh button for the output device list — the capture device list has no refresh
  button either; parity maintained.
- Hotplug / live refresh of the output device list — out of scope for this change.

## Decisions

### D1 — Separate `IAudioOutputDeviceProvider` interface rather than parameterising the existing one

**Chosen:** New interface, structurally identical to `IAudioDeviceProvider`.

**Alternatives considered:**
- *Reuse `IAudioDeviceProvider`* — register two instances differentiated by a key or
  named options. This complicates DI (`IKeyedServiceProvider` or factory lambda) and
  makes consumer code less legible.
- *Add a `DataFlow` parameter to `IAudioDeviceProvider.GetDevicesAsync`* — couples the
  capture abstraction to a WASAPI concept; breaks the existing test doubles.

**Rationale:** Clean DI registration; each endpoint injects the exact type it needs;
unit tests for the output provider are independent of the capture provider tests.

### D2 — Endpoint path `GET /api/v1/audio/output-devices`

**Chosen:** Dedicated path, parallel to `/api/v1/audio/devices`.

**Alternative considered:** `/api/v1/audio/devices?flow=render` — avoids a new route
but requires query-param handling and makes the API harder to describe in specs.

**Rationale:** Consistent with the existing REST style; discoverable; no query-param
complexity.

### D3 — `audioOutputDeviceId` / `audioOutputFriendlyName` field names in AppConfig

**Chosen:** Prefix `audioOutput` to parallel `audioDeviceId` / `audioDeviceFriendlyName`.

**Alternative considered:** `txAudioDeviceId` — clearer TX intent but premature;
"output" is the OS-layer concept and is more neutral.

**Rationale:** Naming follows the OS abstraction (input = capture, output = render).
The TX pipeline can reference these fields by their stable names without renaming later.

### D4 — Placement of output device selector in the UI

**Chosen:** A new `<div class="field-group">` immediately below `#device-select` and
above the CAT fieldset in the Radio hardware tab.

**Rationale:** Groups all audio I/O controls together at the top of the tab, with CAT
below — consistent with the logical flow of an RF + audio signal chain.

### D5 — Linux stub returns empty list

**Chosen:** `SubprocessAudioOutputDeviceProvider` returns `[]` and logs a debug message.

**Rationale:** `aplay --list` output format differs from `arecord --list-devices`; TX
is not yet supported on Linux; an empty list is the safe, non-throwing behaviour
consistent with the capture provider's empty-list contract.

## Risks / Trade-offs

- **WASAPI COM / AOT incompatibility** — identical risk to the existing capture provider
  (documented in `WasapiAudioDeviceProvider.cs`). Mitigation: same `#if WASAPI_SUPPORTED`
  guard; no new exposure.
- **Empty list on Linux** — operators running on Linux will see "No devices found" for
  the output selector. Mitigation: acceptable until a TX pipeline exists on Linux;
  clearly communicated by the UI's existing "No devices found" disabled option.
- **Config round-trip** — adding nullable fields to `AppConfig` (a positional record)
  requires care with `System.Text.Json` deserialization and `ConfigJsonContext`. Tests
  must cover the missing-field case. Mitigation: explicit default values (`= null`) on
  the record and a new round-trip test scenario.

## Migration Plan

1. Add new fields to `AppConfig` with `= null` defaults — existing `app.json` files
   without these fields deserialise to `null` without error (no migration required).
2. Deploy — no restart or manual config edit needed; the output device selector simply
   shows "No device selected" until the operator chooses and saves.
3. Rollback — removing the fields from `AppConfig` and reverting the endpoint leaves
   existing config files with two unknown fields, which are already preserved by
   round-trip fidelity (existing requirement).

## Open Questions

None — design is self-contained and all decisions are resolved above.
