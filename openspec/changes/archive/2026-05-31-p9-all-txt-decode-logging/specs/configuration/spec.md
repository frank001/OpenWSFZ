## ADDED Requirements

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

#### Scenario: Default config includes decodeLog section

- **WHEN** the daemon creates a default config file on first run
- **THEN** the file SHALL include a `decodeLog` section with `enabled: false`, `path: "ALL.TXT"`, and `dialFrequencyMHz: 0.0`

## MODIFIED Requirements

### Requirement: Default configuration file created on first run

If no config file exists at the resolved path on startup, the daemon SHALL create a minimal default configuration file before proceeding, so the first run is in a known state.

#### Scenario: Default config created when file absent

- **WHEN** the daemon starts and no config file exists at the resolved path
- **THEN** the daemon SHALL create the file's parent directory if necessary, write the default configuration, and proceed without error

#### Scenario: Default config values are valid

- **WHEN** the default config file is created
- **THEN** it SHALL contain `audioDeviceId: null`, `audioDeviceFriendlyName: null`, `port: 8080`, a `logging` object with `fileEnabled: false`, `directory: "logs"`, `fileLogLevel: "Information"`, `rotationSchedule: "daily"`, `rotationTime: "00:00"`, `rotationDayOfWeek: "Monday"`, and `maxFiles: 7`; **and** a `decodeLog` object with `enabled: false`, `path: "ALL.TXT"`, and `dialFrequencyMHz: 0.0`; and the daemon SHALL start successfully using those values
