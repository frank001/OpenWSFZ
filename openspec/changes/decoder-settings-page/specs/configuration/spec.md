## ADDED Requirements

### Requirement: Decoder configuration schema

The `AppConfig` schema SHALL include an optional `decoder` object that controls the OSD gate parameters. If the `decoder` key is absent from the config file, the daemon SHALL behave as if `decoder` were `new DecoderConfig()` — the three OSD parameters take their D-009 calibrated defaults (`kMinScorePass2: 10`, `osdCorrThreshold: 0.10`, `osdNhardMax: 60`). All fields within the `decoder` object SHALL have defaults matching the calibrated values, so that a partial `decoder` object (e.g., only `kMinScorePass2` present) loads without error.

The `decoder` object SHALL contain:

- `kMinScorePass2` (int, default `10`, valid range [5, 30]) — pass-1 candidate score floor.
- `osdCorrThreshold` (float, default `0.10`, valid range [0.05, 0.40]) — OSD normalised correlation gate.
- `osdNhardMax` (int, default `60`, valid range [30, 100]) — OSD maximum Hamming-distance gate.

#### Scenario: Missing decoder key uses calibrated defaults

- **WHEN** the config file has no `decoder` key
- **THEN** the effective decoder parameters SHALL be `kMinScorePass2 = 10`, `osdCorrThreshold = 0.10`, and `osdNhardMax = 60`

#### Scenario: decoder object round-trips correctly

- **WHEN** a config file contains `{ "decoder": { "kMinScorePass2": 7, "osdCorrThreshold": 0.15, "osdNhardMax": 50 } }`
- **THEN** `GET /api/v1/config` SHALL return those exact values and `POST /api/v1/config` with a modified `decoder` object SHALL persist the change

#### Scenario: Partial decoder object uses defaults for missing fields

- **WHEN** a config file contains `{ "decoder": { "kMinScorePass2": 8 } }` with no `osdCorrThreshold` or `osdNhardMax`
- **THEN** `AppConfig.Decoder.OsdCorrThreshold` SHALL be `0.10f` and `AppConfig.Decoder.OsdNhardMax` SHALL be `60`

---

### Requirement: Decoder configuration validation in POST /api/v1/config

`POST /api/v1/config` SHALL validate the `decoder` sub-object when present, clamping out-of-range values and logging a warning (same pattern as `cat.pollIntervalSeconds` and `tx.retryCount` / `tx.watchdogMinutes`).

Validation rules:

| Field | Minimum | Maximum | Action on violation |
|---|---|---|---|
| `kMinScorePass2` | 5 | 30 | Clamp to range; log Warning with original and clamped values |
| `osdCorrThreshold` | 0.05 | 0.40 | Clamp to range; log Warning with original and clamped values |
| `osdNhardMax` | 30 | 100 | Clamp to range; log Warning with original and clamped values |

#### Scenario: kMinScorePass2 below minimum is clamped to 5

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "kMinScorePass2": 2 } }`
- **THEN** the server SHALL clamp `kMinScorePass2` to `5`, log a Warning stating the original value `2` and clamped value `5`, and persist `5`

#### Scenario: kMinScorePass2 above maximum is clamped to 30

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "kMinScorePass2": 50 } }`
- **THEN** the server SHALL clamp `kMinScorePass2` to `30`, log a Warning, and persist `30`

#### Scenario: osdCorrThreshold below minimum is clamped to 0.05

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "osdCorrThreshold": 0.01 } }`
- **THEN** the server SHALL clamp `osdCorrThreshold` to `0.05`, log a Warning, and persist `0.05`

#### Scenario: osdCorrThreshold above maximum is clamped to 0.40

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "osdCorrThreshold": 0.90 } }`
- **THEN** the server SHALL clamp `osdCorrThreshold` to `0.40`, log a Warning, and persist `0.40`

#### Scenario: osdNhardMax below minimum is clamped to 30

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "osdNhardMax": 10 } }`
- **THEN** the server SHALL clamp `osdNhardMax` to `30`, log a Warning, and persist `30`

#### Scenario: osdNhardMax above maximum is clamped to 100

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "osdNhardMax": 150 } }`
- **THEN** the server SHALL clamp `osdNhardMax` to `100`, log a Warning, and persist `100`

#### Scenario: In-range decoder values are accepted without clamping

- **WHEN** `POST /api/v1/config` is called with `{ "decoder": { "kMinScorePass2": 10, "osdCorrThreshold": 0.10, "osdNhardMax": 60 } }`
- **THEN** the server SHALL persist those values unchanged and SHALL NOT log any clamping Warning

#### Scenario: GET /api/v1/config includes decoder section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include a `decoder` object (or `null` if the field has not been set) containing the current `kMinScorePass2`, `osdCorrThreshold`, and `osdNhardMax` values
