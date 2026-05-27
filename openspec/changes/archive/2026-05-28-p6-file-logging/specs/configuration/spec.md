## MODIFIED Requirements

### Requirement: Configuration file persistence

The application SHALL persist operator settings to a JSON configuration file. The file SHALL be read at startup and written atomically (write-to-temp then rename) on Save to prevent corruption. The configuration schema SHALL contain `audioDeviceName` (nullable string), `port` (integer), and `logging` (object) at minimum.

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
- **THEN** it SHALL contain `audioDeviceName: null`, `port: 8080`, and a `logging` object with `fileEnabled: false`, `directory: "logs"`, `fileLogLevel: "Information"`, `rotationSchedule: "daily"`, `rotationTime: "00:00"`, `rotationDayOfWeek: "Monday"`, and `maxFiles: 7`; and the daemon SHALL start successfully using those values

---

## ADDED Requirements

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
