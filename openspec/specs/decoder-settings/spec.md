# decoder-settings Specification

## Purpose

Specifies the `DecoderConfig` schema, its optional presence on `AppConfig`, when
`SetDecodeParams` is applied to the native decoder, and the Advanced Decoder Settings
section of the settings UI that edits it.

## Requirements

### Requirement: DecoderConfig schema

`OpenWSFZ.Abstractions` SHALL define a `DecoderConfig` record with the following fields and defaults:

| Field | Type | Default | Valid range | Description |
|---|---|---|---|---|
| `KMinScorePass2` | int | `10` | [5, 30] | Pass-1 candidate score floor (D-009 calibrated). Controls how many pass-1 candidates are admitted to LDPC/OSD. Lower = more sensitivity (and more false positives). |
| `OsdCorrThreshold` | float | `0.10f` | [0.05, 0.40] | OSD normalised correlation gate. Candidates below this threshold are rejected as likely noise CRC-14 coincidences. |
| `OsdNhardMax` | int | `60` | [30, 100] | OSD maximum Hamming distance gate. Candidates with more than this many hard-decision bit errors are rejected. |

All fields SHALL have defaults matching the D-009 R&R study calibrated values. The record SHALL use `[JsonConstructor]` with matching parameter defaults so that JSON objects with missing fields deserialise to the calibrated defaults rather than zero-values (per Lesson 6 — STJ source-gen ignores C# `init` property defaults for missing JSON fields).

#### Scenario: DecoderConfig with all fields round-trips through JSON

- **WHEN** a `DecoderConfig` with `KMinScorePass2 = 7`, `OsdCorrThreshold = 0.15f`, and `OsdNhardMax = 50` is serialised to JSON and deserialised again
- **THEN** all three fields SHALL equal their original values

#### Scenario: Missing decoder key in app.json deserialises with calibrated defaults

- **WHEN** a `DecoderConfig` is deserialised from a JSON object with no fields present (`{}`)
- **THEN** `KMinScorePass2` SHALL be `10`, `OsdCorrThreshold` SHALL be `0.10f`, and `OsdNhardMax` SHALL be `60`

---

### Requirement: AppConfig.Decoder nullable sub-object

`AppConfig` SHALL include a nullable `Decoder` property of type `DecoderConfig?`, defaulting to `null`. A `null` value SHALL be treated by all consumers as equivalent to `new DecoderConfig()` (calibrated defaults). Existing config files without a `decoder` key SHALL deserialise `AppConfig.Decoder` as `null` and start normally.

#### Scenario: AppConfig without decoder key deserialises successfully

- **WHEN** an `AppConfig` is deserialised from a JSON object that contains no `decoder` key
- **THEN** `AppConfig.Decoder` SHALL be `null` and the daemon SHALL start without error

#### Scenario: AppConfig with decoder key deserialises to DecoderConfig

- **WHEN** an `AppConfig` is deserialised from a JSON object containing `{ "decoder": { "kMinScorePass2": 8 } }`
- **THEN** `AppConfig.Decoder.KMinScorePass2` SHALL be `8`, `AppConfig.Decoder.OsdCorrThreshold` SHALL be `0.10f`, and `AppConfig.Decoder.OsdNhardMax` SHALL be `60`

---

### Requirement: SetDecodeParams called at daemon startup and on config save

The daemon SHALL call `Ft8LibInterop.SetDecodeParams` with the effective decoder parameters (from `AppConfig.Decoder ?? new DecoderConfig()`) at two points:

1. During daemon startup, after the native library has been loaded and before audio capture begins.
2. Whenever `IConfigStore.OnSaved` fires, so the next decode cycle uses the updated values.

`Ft8LibInterop.SetDecodeParams` SHALL call `EnsureInitialized()` internally before setting the native statics, so it is safe to call before the first `DecodeAll` invocation.

#### Scenario: Decoder parameters take effect on the next cycle after a config save

- **WHEN** the operator saves a new `DecoderConfig` via `POST /api/v1/config`
- **THEN** the daemon SHALL call `SetDecodeParams` before the start of the next 15-second decode cycle, and the new parameter values SHALL be used by `ft8_decode_all` for that cycle and all subsequent cycles

#### Scenario: Startup applies calibrated defaults when decoder key is absent

- **WHEN** the daemon starts with an `app.json` that has no `decoder` key
- **THEN** `Ft8LibInterop.SetDecodeParams` SHALL be called with `KMinScorePass2 = 10`, `OsdCorrThreshold = 0.10f`, and `OsdNhardMax = 60` before the first decode cycle

---

### Requirement: Advanced Decoder Settings section in settings UI

The settings page (`settings.html`) SHALL include a collapsible "Advanced Decoder Settings" section implemented as a native HTML `<details>`/`<summary>` element. The section SHALL be collapsed by default. It SHALL contain:

- A disclaimer: *"Default values are calibrated by R&R study — change with caution."*
- A numeric input for **Pass-1 Score Floor (K)** bound to `decoder.kMinScorePass2`, with `min="5"` and `max="30"`.
- A numeric input (step `0.01`) for **OSD Correlation Threshold** bound to `decoder.osdCorrThreshold`, with `min="0.05"` and `max="0.40"`.
- A numeric input for **OSD Max Hard Errors** bound to `decoder.osdNhardMax`, with `min="30"` and `max="100"`.
- A **"Reset to defaults"** button that resets the three inputs to their calibrated values (`10`, `0.10`, `60`) without saving, requiring the operator to click the main save button to persist.

Changes SHALL be included in the `POST /api/v1/config` payload sent by the existing settings save mechanism. A note SHALL inform the operator that changes take effect on the next decode cycle without a restart.

#### Scenario: Advanced Decoder Settings section is present but collapsed by default

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain a `<details>` element with a `<summary>` containing the text "Advanced Decoder Settings", and the element SHALL NOT have the `open` attribute

#### Scenario: Settings page loads current decoder values from GET /api/v1/config

- **WHEN** `settings.js` initialises and `GET /api/v1/config` returns a `decoder` object
- **THEN** the three decoder inputs SHALL be pre-populated with the values from the response

#### Scenario: Settings page applies calibrated defaults when decoder is null

- **WHEN** `settings.js` initialises and `GET /api/v1/config` returns a response with no `decoder` key
- **THEN** the three decoder inputs SHALL be pre-populated with the calibrated defaults: `10`, `0.10`, `60`

#### Scenario: Reset to defaults button restores calibrated values without saving

- **WHEN** the operator clicks "Reset to defaults"
- **THEN** the three inputs SHALL be set to `10`, `0.10`, `60` without sending any network request

#### Scenario: Decoder values are included in the save payload

- **WHEN** the operator changes decoder values and clicks the main settings save button
- **THEN** `settings.js` SHALL include a `decoder` object in the `POST /api/v1/config` body with the current input values
