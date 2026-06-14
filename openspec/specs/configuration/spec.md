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

