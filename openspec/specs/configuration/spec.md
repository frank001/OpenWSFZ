## Purpose

This capability defines how OpenWSFZ persists and exposes application configuration: the on-disk configuration file and its first-run creation, the logging, decode-log, and CAT configuration schemas, the Settings REST API, and migration of legacy settings.
## Requirements
### Requirement: Configuration file persistence

The application SHALL persist operator settings to a JSON configuration file. The file SHALL be read at startup and written atomically (write-to-temp then rename) on Save to prevent corruption. The configuration schema SHALL contain `audioDeviceId` (nullable string), `audioDeviceFriendlyName` (nullable string), `audioOutputDeviceId` (nullable string), `audioOutputFriendlyName` (nullable string), `port` (integer), and `logging` (object) at minimum.

#### Scenario: Config file loaded at startup

- **WHEN** the daemon starts and a config file exists at the resolved path
- **THEN** the daemon SHALL read and deserialise the file, and the resulting settings SHALL be available to all services via the DI container before the web host starts

#### Scenario: Config file written atomically on Save

- **WHEN** `IConfigStore.SaveAsync()` is called
- **THEN** the implementation SHALL write the serialised config to a temporary file in the same directory, then rename it over the target file, and SHALL NOT leave a partially-written config file on disk if the process is interrupted

#### Scenario: Unknown fields in config file are preserved

- **WHEN** the daemon reads a config file that contains fields not present in the current `AppConfig` schema
- **THEN** the daemon SHALL not fail and SHALL preserve the unknown fields on the next write (round-trip fidelity)

---

### Requirement: Default configuration file created on first run

If no config file exists at the resolved path on startup, the daemon SHALL create a minimal default configuration file before proceeding, so the first run is in a known state.

#### Scenario: Default config created when file absent

- **WHEN** the daemon starts and no config file exists at the resolved path
- **THEN** the daemon SHALL create the file's parent directory if necessary, write the default configuration, and proceed without error

#### Scenario: Default config values are valid

- **WHEN** the default config file is created
- **THEN** it SHALL contain `audioDeviceId: null`, `audioDeviceFriendlyName: null`, `audioOutputDeviceId: null`, `audioOutputFriendlyName: null`, `port: 8080`, a `logging` object with `fileEnabled: false`, `directory: "logs"`, `fileLogLevel: "Information"`, `rotationSchedule: "daily"`, `rotationTime: "00:00"`, `rotationDayOfWeek: "Monday"`, and `maxFiles: 7`; **and** a `decodeLog` object with `enabled: false`, `path: "ALL.TXT"`, and `dialFrequencyMHz: 0.0`; and the daemon SHALL start successfully using those values

---

### Requirement: Logging configuration schema

The `AppConfig` schema SHALL include a `logging` object that controls the file logging sink. All fields SHALL have defaults so that existing config files without a `logging` key continue to load without error.

#### Scenario: logging object with all fields round-trips correctly

- **WHEN** a config file contains a `logging` object with all seven fields set to non-default values
- **THEN** `GET /api/v1/config` SHALL return those exact values and `POST /api/v1/config` with a modified `logging` object SHALL persist the change

#### Scenario: Missing logging object uses defaults

- **WHEN** a config file has no `logging` key
- **THEN** the daemon SHALL behave as if `logging` were `{ "fileEnabled": false, "directory": "logs", "fileLogLevel": "Information", "rotationSchedule": "daily", "rotationTime": "00:00", "rotationDayOfWeek": "Monday", "maxFiles": 7 }`

#### Scenario: fileLogLevel accepts valid level strings

- **WHEN** `logging.fileLogLevel` is set to one of `"Verbose"`, `"Debug"`, `"Information"`, `"Warning"`, `"Error"`, `"Fatal"`
- **THEN** the daemon SHALL accept the value and apply it to the file sink threshold

#### Scenario: rotationSchedule accepts valid schedule strings

- **WHEN** `logging.rotationSchedule` is set to one of `"session"`, `"hourly"`, `"daily"`, `"weekly"`
- **THEN** the daemon SHALL accept the value and configure rotation accordingly

#### Scenario: rotationDayOfWeek ignored when schedule is not weekly

- **WHEN** `logging.rotationSchedule` is not `"weekly"`
- **THEN** the `rotationDayOfWeek` field SHALL be stored and round-tripped but SHALL have no effect on rotation behaviour

---

### Requirement: Configuration REST API

The web server SHALL expose `GET /api/v1/config` and `POST /api/v1/config` endpoints to allow the UI to read and write the operator's configuration.

#### Scenario: GET returns current config

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and the current in-memory configuration serialised as JSON, including `audioDeviceId`, `audioDeviceFriendlyName`, `audioOutputDeviceId`, and `audioOutputFriendlyName` fields

#### Scenario: POST writes and persists config

- **WHEN** a client sends `POST /api/v1/config` with a valid JSON body containing `audioDeviceId`, `audioDeviceFriendlyName`, `audioOutputDeviceId`, and `audioOutputFriendlyName`
- **THEN** the server SHALL update the in-memory configuration, call `IConfigStore.SaveAsync()`, and respond with HTTP 200 and the updated configuration as JSON

#### Scenario: POST clearing output device selection persists null values

- **WHEN** a client sends `POST /api/v1/config` with `audioOutputDeviceId: null` and `audioOutputFriendlyName: null`
- **THEN** the server SHALL persist both fields as `null` and respond with HTTP 200

#### Scenario: Config file without audioOutputDeviceId deserialises without error

- **WHEN** the daemon starts and the config file contains no `audioOutputDeviceId` or `audioOutputFriendlyName` keys (i.e. an existing pre-FR-048 config file)
- **THEN** the daemon SHALL deserialise successfully, treating both fields as `null`, and SHALL start normally

#### Scenario: POST with malformed JSON returns 400

- **WHEN** a client sends `POST /api/v1/config` with a body that is not valid JSON
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify or persist the configuration

---

### Requirement: Legacy audioDeviceName migration

The daemon SHALL silently migrate config files that contain the legacy `audioDeviceName` field (written by versions prior to p7) so that existing operators are not disrupted.

#### Scenario: Legacy config file is read without error

- **WHEN** the daemon starts and the config file contains an `audioDeviceName` key but no `audioDeviceId` key
- **THEN** the daemon SHALL treat the value of `audioDeviceName` as `audioDeviceId`, set `audioDeviceFriendlyName` to `null`, and start normally — including starting audio capture if the migrated ID is non-null

#### Scenario: Re-save after migration writes new schema

- **WHEN** the operator saves settings (via `POST /api/v1/config`) after a legacy config has been loaded
- **THEN** the written config file SHALL contain `audioDeviceId` and `audioDeviceFriendlyName` fields and SHALL NOT be required to retain the legacy `audioDeviceName` key

---

### Requirement: Decode log configuration schema

The `AppConfig` schema SHALL include a `decodeLog` object that controls the ALL.TXT decode log. All fields SHALL have defaults so that existing config files without a `decodeLog` key continue to load without error.

The `decodeLog` object SHALL contain:
- `enabled` (bool, default `false`) — whether the decode log is written.
- `path` (string, default `"ALL.TXT"`) — absolute or relative path to the output file; relative paths are resolved from the directory containing the executable.
- `dialFrequencyMHz` (double, default `0.0`) — the transceiver dial frequency in MHz, written to each log line.

#### Scenario: decodeLog object with all fields round-trips correctly

- **WHEN** a config file contains a `decodeLog` object with all three fields set to non-default values
- **THEN** `GET /api/v1/config` SHALL return those exact values and `POST /api/v1/config` with a modified `decodeLog` object SHALL persist the change

#### Scenario: Missing decodeLog object uses defaults

- **WHEN** a config file has no `decodeLog` key
- **THEN** the daemon SHALL behave as if `decodeLog` were `{ "enabled": false, "path": "ALL.TXT", "dialFrequencyMHz": 0.0 }`

#### Scenario: decodeLog.enabled false suppresses file output

- **WHEN** `decodeLog.enabled` is `false` (or absent)
- **THEN** no decode log file SHALL be opened or written, regardless of `path` or `dialFrequencyMHz`

---

### Requirement: CAT configuration schema

The `AppConfig` schema SHALL include an optional `cat` object that controls the CAT rig connection. If the `cat` key is absent from the config file, the daemon SHALL behave as if `cat` were `{ "enabled": false }` — no serial port is opened and CAT polling does not start. All fields within the `cat` object SHALL have defaults so that a partial `cat` object (e.g. only `enabled` present) loads without error.

The `cat` object SHALL contain:
- `enabled` (bool, default `false`) — whether CAT polling is active
- `rigModel` (string, default `"SerialCat"`) — selects the transport implementation; the two recognised values are `"SerialCat"` (direct serial) and `"RigCtld"` (TCP to a running `rigctld` daemon); unknown values SHALL log a Warning and set `enabled` to `false`
- `serialPort` (string, default `"COM6"` on Windows, `"/dev/ttyUSB0"` on Linux, `"/dev/cu.usbserial"` on macOS) — serial port name; used only when `rigModel` is `"SerialCat"`
- `baudRate` (int, default `9600`) — serial port baud rate; used only when `rigModel` is `"SerialCat"`
- `rigctldHost` (string, default `"127.0.0.1"`) — hostname or IP address of the `rigctld` daemon; used only when `rigModel` is `"RigCtld"`
- `rigctldPort` (int, default `4532`) — TCP port of the `rigctld` daemon; used only when `rigModel` is `"RigCtld"`
- `pollIntervalSeconds` (int, default `1`, minimum `1`, maximum `60`) — how often to query the rig; values outside the range SHALL be clamped with a Warning

#### Scenario: Missing cat key uses defaults

- **WHEN** the config file has no `cat` key
- **THEN** `AppConfig.Cat.Enabled` SHALL be `false` and no serial port SHALL be opened

#### Scenario: cat object round-trips correctly

- **WHEN** a config file contains a `cat` object with all five fields set to non-default values
- **THEN** `GET /api/v1/config` SHALL return those exact values and `POST /api/v1/config` with a modified `cat` object SHALL persist the change

#### Scenario: Unknown rigModel disables CAT with warning

- **WHEN** `cat.rigModel` is set to a value not recognised by the factory (e.g. `"UnknownRig2000"`)
- **THEN** the daemon SHALL log a Warning naming the unrecognised model, treat `cat.enabled` as `false`, and start normally without opening a serial port

#### Scenario: pollIntervalSeconds out of range is clamped

- **WHEN** `cat.pollIntervalSeconds` is set to a value less than 1 or greater than 60
- **THEN** the daemon SHALL clamp the value to the valid range, log a Warning stating the original and clamped values, and use the clamped value

#### Scenario: rigModel SerialCat uses serialPort and baudRate

- **WHEN** `cat.rigModel` is `"SerialCat"`
- **THEN** the daemon SHALL use `cat.serialPort` and `cat.baudRate` to open the serial connection and SHALL NOT open any TCP connection

#### Scenario: rigModel RigCtld uses rigctldHost and rigctldPort

- **WHEN** `cat.rigModel` is `"RigCtld"`
- **THEN** the daemon SHALL connect to `cat.rigctldHost:cat.rigctldPort` via TCP and SHALL NOT open any serial port

#### Scenario: Default config includes cat object with enabled false

- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include a `cat` object with at minimum `"enabled": false`

---

### Requirement: CAT configuration exposed via Settings REST API

The `GET /api/v1/config` and `POST /api/v1/config` endpoints SHALL include the `cat` object in their request and response bodies alongside the existing config fields.

#### Scenario: GET /api/v1/config includes cat section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include a `cat` object with `enabled`, `rigModel`, `serialPort`, `baudRate`, and `pollIntervalSeconds` fields

#### Scenario: POST /api/v1/config with cat.enabled true persists change

- **WHEN** a client sends `POST /api/v1/config` with `{ "cat": { "enabled": true, "serialPort": "COM6", "baudRate": 9600 } }`
- **THEN** the daemon SHALL persist the change and `CatPollingService` SHALL attempt to connect on the next poll cycle

### Requirement: IFrequencyStore DI registration and path resolution

The `IFrequencyStore` service SHALL be registered as a singleton in the DI container during daemon startup, alongside `IConfigStore`. The concrete `FrequencyStore` class SHALL be the registered implementation.

The resolved path for `frequencies.json` SHALL follow the same convention as `app.json`: by default, the file is located in the same directory as the daemon executable. An environment variable or CLI argument override for the data directory SHALL also apply to `frequencies.json` when present.

#### Scenario: IFrequencyStore is available to all services via DI

- **WHEN** the daemon starts and DI is configured
- **THEN** any service that depends on `IFrequencyStore` SHALL receive a resolved singleton instance before any web request is handled

#### Scenario: FrequencyStore path resolves to the executable directory by default

- **WHEN** no path override is configured
- **THEN** `FrequencyStore` SHALL look for `frequencies.json` in the same directory as the daemon executable

#### Scenario: FrequencyStore path uses the data-directory override when set

- **WHEN** the data-directory override (environment variable or CLI argument) is set to a custom path
- **THEN** `FrequencyStore` SHALL resolve `frequencies.json` within that directory, consistent with how `IConfigStore` resolves `app.json`

#### Scenario: Default frequencies.json is included in the default config created on first run

- **WHEN** the daemon creates default files on first run (both `app.json` and `frequencies.json` are absent)
- **THEN** both files SHALL be created: `app.json` with the standard default config values and `frequencies.json` with the 15-entry default FT8 frequency list

---

### Requirement: TX configuration schema

The `AppConfig` schema SHALL include a `Tx` property of type `TxConfig`. If the `tx` key is absent from the config file, the daemon SHALL behave as if `tx` were the default `TxConfig()` — no TX behaviour changes and the system remains receive-only.

`TxConfig` SHALL be a record with the following fields and defaults:

| Field | Type | Default | Description |
|---|---|---|---|
| `AutoAnswer` | bool | `false` | Master enable for the QSO auto-answerer. When `false` the state machine remains in `Idle` regardless of decoded CQs and no transmission occurs. The operator must set this to `true` via Settings before any auto-answer TX takes place. |
| `Callsign` | string | `"Q1OFZ"` | Our station callsign. Default is a Q-prefix ITU-unallocated call per NFR-021. |
| `Grid` | string | `"JO33"` | Our Maidenhead grid locator (4-character minimum). |
| `RetryCount` | int | `3` | Number of retransmits per waiting state before aborting the QSO. Clamped to minimum 1. |
| `WatchdogMinutes` | int | `4` | Watchdog timer duration in minutes. Matching WSJT-X default. Clamped to minimum 1. |
| `RxAudioOffsetHz` | int | `1500` | RX frequency cursor position in Hz (0–3000). Persisted so the waterfall cursor survives a restart. |
| `TxAudioOffsetHz` | int | `1500` | TX frequency cursor position in Hz (0–3000). Auto-updated by the QSO answerer when `HoldTxFreq` is false. |
| `HoldTxFreq` | bool | `false` | When `true`, the answerer transmits at `TxAudioOffsetHz` regardless of the caller's frequency; when `false`, it follows the caller's audio frequency and updates `TxAudioOffsetHz` automatically. |

All fields SHALL have defaults so that a partial or absent `tx` object loads without error.

#### Scenario: Missing tx key uses defaults

- **WHEN** the config file has no `tx` key
- **THEN** `AppConfig.Tx.AutoAnswer` SHALL be `false`, `Tx.Callsign` SHALL be `"Q1OFZ"`, `Tx.Grid` SHALL be `"JO33"`, `Tx.RetryCount` SHALL be `3`, and `Tx.WatchdogMinutes` SHALL be `4`

#### Scenario: AutoAnswer defaults to false — no transmission without explicit opt-in

- **WHEN** the config file has no `tx` key, or `tx.autoAnswer` is absent or `false`
- **THEN** the `QsoAnswererService` SHALL remain in `Idle` regardless of decoded CQ messages and SHALL NOT transmit

#### Scenario: tx object round-trips correctly

- **WHEN** a config file contains `{ "tx": { "callsign": "Q9XYZ", "grid": "IO91", "retryCount": 5, "watchdogMinutes": 8 } }`
- **THEN** `GET /api/v1/config` SHALL return those exact values and `POST /api/v1/config` with a modified `tx` object SHALL persist the change

#### Scenario: Default config file includes tx object

- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include a `tx` object with all fields set to their default values

#### Scenario: RetryCount below 1 is clamped to 1

- **WHEN** `tx.retryCount` is set to `0` or a negative value
- **THEN** the daemon SHALL clamp it to `1`, log a Warning, and use the clamped value

#### Scenario: WatchdogMinutes below 1 is clamped to 1

- **WHEN** `tx.watchdogMinutes` is set to `0` or a negative value
- **THEN** the daemon SHALL clamp it to `1`, log a Warning, and use the clamped value

#### Scenario: TxConfig with new audio offset fields round-trips through JSON

- **WHEN** a `TxConfig` with `rxAudioOffsetHz = 900`, `txAudioOffsetHz = 1800`, and `holdTxFreq = true` is serialised to JSON and deserialised again
- **THEN** all three fields SHALL have their original values

#### Scenario: Existing app.json without audio offset fields deserialises with defaults

- **WHEN** `app.json` contains a `tx` object without `rxAudioOffsetHz`, `txAudioOffsetHz`, or `holdTxFreq`
- **THEN** the deserialised `TxConfig` SHALL have `RxAudioOffsetHz = 1500`, `TxAudioOffsetHz = 1500`, and `HoldTxFreq = false`
- **AND** the daemon SHALL start without error

#### Scenario: Audio offset fields appear in app.json after first save

- **WHEN** the daemon receives a `POST /api/v1/audio-offset` request and saves config
- **THEN** `app.json` SHALL contain `"rxAudioOffsetHz"`, `"txAudioOffsetHz"`, and `"holdTxFreq"` in the `tx` object

---

### Requirement: TX configuration exposed via Settings REST API

`GET /api/v1/config` and `POST /api/v1/config` SHALL include the `tx` object in their request and response bodies alongside existing config fields.

#### Scenario: GET /api/v1/config includes tx section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include a `tx` object with `autoAnswer`, `callsign`, `grid`, `retryCount`, and `watchdogMinutes` fields

#### Scenario: POST /api/v1/config with updated callsign persists change

- **WHEN** a client sends `POST /api/v1/config` with `{ "tx": { "autoAnswer": true, "callsign": "Q9XYZ", "grid": "IO91", "retryCount": 3, "watchdogMinutes": 4 } }`
- **THEN** the daemon SHALL persist the change and subsequent calls to `QsoAnswererService` SHALL use `Q9XYZ` as the station callsign with auto-answer enabled

---

### Requirement: TxConfig QSO confirmation and retained log fields

The `TxConfig` section of `AppConfig` SHALL include four new fields governing the QSO confirmation dialog and retained log values:

| JSON key | C# property | Type | Default | Description |
|---|---|---|---|---|
| `qsoConfirmation` | `QsoConfirmation` | bool | `true` | When true, the confirmation dialog is shown; ADIF written only on OK. When false, auto-log at QsoComplete. |
| `retainedTxPower` | `RetainedTxPower` | string | `""` | Last TX power value marked Retain; pre-fills the Tx Power field in the next dialog. |
| `retainedComment` | `RetainedComment` | string | `""` | Last comment value marked Retain; pre-fills the Comments field in the next dialog. |
| `retainedPropMode` | `RetainedPropMode` | string | `""` | Last propagation mode value marked Retain; pre-fills the Prop Mode dropdown in the next dialog. |

**STJ default-field hazard (lesson 6):** `QsoConfirmation` defaults to `true`. Because STJ source-gen deserialises missing JSON `bool` fields as `false`, a `[JsonConstructor]`-annotated constructor with parameter default `bool qsoConfirmation = true` SHALL be provided on `TxConfig` to ensure the correct default on first-run and on upgrade of existing config files that lack this field.

All four fields SHALL round-trip correctly through `GET /api/v1/config` / `POST /api/v1/config` and SHALL survive unknown-field preservation on config save.

#### Scenario: QsoConfirmation defaults to true when field absent from config

- **WHEN** the daemon loads an `appconfig.json` that has a `tx` section but no `qsoConfirmation` key
- **THEN** `TxConfig.QsoConfirmation` SHALL be `true`

#### Scenario: QsoConfirmation = false persists and is read back

- **WHEN** `POST /api/v1/config` is called with `tx.qsoConfirmation = false` and the daemon is restarted
- **THEN** `TxConfig.QsoConfirmation` SHALL be `false` after restart

#### Scenario: Retained fields default to empty string when absent

- **WHEN** the daemon loads an `appconfig.json` that has no `retainedTxPower`, `retainedComment`, or `retainedPropMode` keys
- **THEN** all three SHALL be empty strings (not null)

#### Scenario: Retained fields updated by POST /api/v1/tx/log-qso

- **WHEN** `POST /api/v1/tx/log-qso` is called with `txPower = "100"` and `retainTxPower = true`
- **THEN** `TxConfig.RetainedTxPower` SHALL be `"100"` and the updated value SHALL be present in the next `GET /api/v1/config` response

#### Scenario: Retained fields included in qsoReview WS event

- **WHEN** the `qsoReview` WebSocket event is emitted and `TxConfig.RetainedTxPower = "100"`
- **THEN** the event payload SHALL include `"retainedTxPower": "100"`

---

### Requirement: TxConfig gains Role and CallerPartnerSelect fields

`TxConfig` SHALL include two new fields:

```csharp
public TxRole                Role                { get; init; } = TxRole.Answerer;
public CallerPartnerSelectMode CallerPartnerSelect { get; init; } = CallerPartnerSelectMode.First;
```

Both fields SHALL have backward-compatible defaults so that existing config files
without these keys deserialise correctly (per lesson 6: STJ source-gen uses `0` for
absent enum fields — the `[JsonConstructor]` on `TxConfig` MUST carry explicit default
parameter values for both fields).

**`TxRole` enum:**
```csharp
public enum TxRole { Answerer = 0, Caller = 1 }
```

**`CallerPartnerSelectMode` enum:**
```csharp
public enum CallerPartnerSelectMode { First = 0, None = 1 }
```

Both enums SHALL be defined in `OpenWSFZ.Abstractions`.

#### Scenario: Existing config without Role field loads as Answerer

- **WHEN** a config file contains a `tx` object with no `role` key
- **THEN** `config.Tx.Role` SHALL equal `TxRole.Answerer`
- **AND** the daemon SHALL start without error

#### Scenario: Existing config without CallerPartnerSelect loads as First

- **WHEN** a config file contains a `tx` object with no `callerPartnerSelect` key
- **THEN** `config.Tx.CallerPartnerSelect` SHALL equal `CallerPartnerSelectMode.First`

#### Scenario: Role field round-trips through GET/POST config

- **WHEN** `POST /api/v1/config` is called with `{ "tx": { "role": "Caller", ... } }`
- **THEN** `GET /api/v1/config` SHALL subsequently return `"tx": { "role": "Caller", ... }`

#### Scenario: CallerPartnerSelect field round-trips through GET/POST config

- **WHEN** `POST /api/v1/config` is called with
  `{ "tx": { "callerPartnerSelect": "None", ... } }`
- **THEN** `GET /api/v1/config` SHALL subsequently return
  `"tx": { "callerPartnerSelect": "None", ... }`

---

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

---

### Requirement: Remote access configuration schema
The `AppConfig` schema SHALL include a `remoteAccess` object that controls LAN binding and passphrase authentication. If the `remoteAccess` key is absent from the config file, the daemon SHALL behave as if `remoteAccess` were `{ "enabled": false, "passphrase": null }` — the web interface remains loopback-only with no authentication change.

`RemoteAccessConfig` SHALL be a record with the following fields and defaults:

| Field | Type | Default | Description |
|---|---|---|---|
| `Enabled` | bool | `false` | When `true`, Kestrel binds to `0.0.0.0` instead of `127.0.0.1`. Requires daemon restart to take effect. |
| `Passphrase` | string? | `null` | Shared passphrase for non-loopback access. `null` or empty = no auth required. Stored as plaintext. |

All fields SHALL have defaults so that a partial or absent `remoteAccess` object loads without error.

#### Scenario: Missing remoteAccess key uses defaults
- **WHEN** the config file has no `remoteAccess` key
- **THEN** `AppConfig.RemoteAccess.Enabled` SHALL be `false` and `AppConfig.RemoteAccess.Passphrase` SHALL be `null`

#### Scenario: remoteAccess object with both fields round-trips correctly
- **WHEN** a config file contains `{ "remoteAccess": { "enabled": true, "passphrase": "test" } }`
- **THEN** `GET /api/v1/config` SHALL return `remoteAccess.enabled = true` and `remoteAccess.passphrase = "test"`
- **AND** `POST /api/v1/config` with a modified `remoteAccess` object SHALL persist the change

#### Scenario: remoteAccess.enabled false with passphrase set is valid
- **WHEN** the config file contains `{ "remoteAccess": { "enabled": false, "passphrase": "secret" } }`
- **THEN** the daemon SHALL start normally, bind to loopback, and ignore the passphrase

#### Scenario: Config file without remoteAccess field deserialises without error
- **WHEN** the daemon starts and `app.json` contains no `remoteAccess` key (i.e. a pre-LAN-access config file)
- **THEN** the daemon SHALL deserialise successfully with `RemoteAccess.Enabled = false` and SHALL start normally

#### Scenario: Default config created on first run includes remoteAccess with defaults
- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include a `remoteAccess` object with `enabled: false` and `passphrase: null`

---

### Requirement: ICallsignGrammarStore DI registration and path resolution

The `ICallsignGrammarStore` service SHALL be registered as a singleton in the DI container during
daemon startup, alongside `IConfigStore` and `IFrequencyStore`. The concrete
`CallsignGrammarStore` class SHALL be the registered implementation.

The resolved path for `callsign-grammar.json` SHALL follow the same convention as
`frequencies.json`: by default, the file is located in the same directory as the daemon
executable. The data-directory override (environment variable or CLI argument) SHALL also apply
to `callsign-grammar.json` when present.

#### Scenario: ICallsignGrammarStore is available to all services via DI

- **WHEN** the daemon starts and DI is configured
- **THEN** any service that depends on `ICallsignGrammarStore` SHALL receive a resolved singleton
  instance before any web request is handled

#### Scenario: CallsignGrammarStore path resolves to the executable directory by default

- **WHEN** no path override is configured
- **THEN** `CallsignGrammarStore` SHALL look for `callsign-grammar.json` in the same directory as
  the daemon executable

#### Scenario: CallsignGrammarStore path uses the data-directory override when set

- **WHEN** the data-directory override is set to a custom path
- **THEN** `CallsignGrammarStore` SHALL resolve `callsign-grammar.json` within that directory

#### Scenario: Default callsign-grammar.json is included in the default files created on first run

- **WHEN** the daemon creates default files on first run and `callsign-grammar.json` is absent
- **THEN** the file SHALL be created with built-in default grammar values (digit-run maximum 3,
  total-length maximum 11, the `Q`-series synthetic carve-out present)

---

### Requirement: ICallsignRegionStore DI registration and path resolution

The `ICallsignRegionStore` service SHALL be registered as a singleton in the DI container during
daemon startup, alongside `ICallsignGrammarStore`. The concrete `CallsignRegionStore` class SHALL
be the registered implementation, following the same path-resolution convention (executable
directory by default, data-directory override when set).

#### Scenario: ICallsignRegionStore is available to all services via DI

- **WHEN** the daemon starts and DI is configured
- **THEN** any service that depends on `ICallsignRegionStore` SHALL receive a resolved singleton
  instance before any web request is handled

#### Scenario: Default callsign-regions.json is included in the default files created on first run

- **WHEN** the daemon creates default files on first run and `callsign-regions.json` is absent
- **THEN** the file SHALL be created with its seed region data, including the mandatory
  `"Synthetic (R&R Study)"` entry for the `Q`-prefix series

---

### Requirement: externalReporting configuration schema

`AppConfig` SHALL gain an `externalReporting` object with:
- `enabled` (bool, default `false`) — master switch; when `false`, `ExternalReportingService` opens
  no sockets
- `targets` (array, default `[]`) — each entry `{ name: string, host: string, port: int, enabled:
  bool }`; `name` is a free-text operator label (e.g. `"GridTracker2"`), not used on the wire
- `honourInboundCommands` (bool, default `false`) — whether inbound Reply/Free Text datagrams are
  acted upon; Halt Tx is unaffected by this flag (see `external-reporting` capability)
- `restrictExternalRepliesToDecodeFilter` (bool, default `false`) — when `false` (default), an
  inbound Reply naming a callsign currently hidden under the operator's decode-panel filter
  (`DecodeFilterState`) is still honoured by `qso-answerer`/`qso-caller`'s external-reply engagement
  paths; when `true`, such a Reply is rejected, matching the decode panel's own visibility exactly.
  Only meaningful when `honourInboundCommands` is also `true` (see `external-reporting` capability).

An entry with `port` outside `1`–`65535` SHALL be rejected on save with the same validation-error
pattern used elsewhere in `POST /api/v1/config` (HTTP 400, no partial persistence).

#### Scenario: Missing externalReporting key uses defaults

- **WHEN** the config file has no `externalReporting` key
- **THEN** `AppConfig.ExternalReporting.Enabled` SHALL be `false` and `Targets` SHALL be an empty
  list, and `RestrictExternalRepliesToDecodeFilter` SHALL be `false`

#### Scenario: externalReporting object round-trips correctly

- **WHEN** a config file contains an `externalReporting` object with `enabled: true`, two target
  entries, `honourInboundCommands: true`, and `restrictExternalRepliesToDecodeFilter: true`
- **THEN** `GET /api/v1/config` SHALL return those exact values and a subsequent `POST
  /api/v1/config` with a modified target list SHALL persist the change

#### Scenario: Out-of-range port rejected

- **WHEN** `POST /api/v1/config` includes an `externalReporting.targets` entry with `port: 70000`
- **THEN** the daemon SHALL return HTTP 400 and SHALL NOT persist any part of the request

#### Scenario: Default config includes externalReporting object with enabled false

- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include an `externalReporting` object with at minimum
  `"enabled": false, "targets": []`

#### Scenario: Missing restrictExternalRepliesToDecodeFilter key on an existing externalReporting object defaults to false

- **WHEN** a config file contains an `externalReporting` object from before this field existed
  (e.g. `{ "enabled": true, "targets": [...], "honourInboundCommands": true }` with no
  `restrictExternalRepliesToDecodeFilter` key)
- **THEN** `AppConfig.ExternalReporting.RestrictExternalRepliesToDecodeFilter` SHALL deserialise to
  `false`, preserving the new default (external Reply honoured regardless of the decode-panel
  filter) for any pre-existing installation

---

### Requirement: externalReporting configuration exposed via Settings REST API

`GET /api/v1/config` and `POST /api/v1/config` SHALL include the `externalReporting` object in their
request and response bodies alongside the existing config fields.

#### Scenario: GET /api/v1/config includes externalReporting section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include an `externalReporting` object with `enabled`, `targets`,
  `honourInboundCommands`, and `restrictExternalRepliesToDecodeFilter` fields

#### Scenario: POST /api/v1/config with a new target persists and takes effect

- **WHEN** a client sends `POST /api/v1/config` with `{ "externalReporting": { "enabled": true,
  "targets": [{ "name": "GridTracker2", "host": "127.0.0.1", "port": 2237, "enabled": true }],
  "honourInboundCommands": false, "restrictExternalRepliesToDecodeFilter": false } }`
- **THEN** the daemon SHALL persist the change and `ExternalReportingService` SHALL begin sending
  outbound datagrams to `127.0.0.1:2237` without requiring a daemon restart

