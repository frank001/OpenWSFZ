## ADDED Requirements

### Requirement: Configuration file persistence

The application SHALL persist operator settings to a JSON configuration file. The file SHALL be read at startup and written atomically (write-to-temp then rename) on Save to prevent corruption. The Phase 2 schema SHALL contain at minimum `audioDeviceName` (nullable string) and `port` (integer).

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
- **THEN** it SHALL contain `audioDeviceName: null` and `port: 8080` at minimum, and the daemon SHALL start successfully using those values

---

### Requirement: Configuration REST API

The web server SHALL expose `GET /api/v1/config` and `POST /api/v1/config` endpoints to allow the UI to read and write the operator's configuration.

#### Scenario: GET returns current config

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and the current in-memory configuration serialised as JSON

#### Scenario: POST writes and persists config

- **WHEN** a client sends `POST /api/v1/config` with a valid JSON body
- **THEN** the server SHALL update the in-memory configuration, call `IConfigStore.SaveAsync()`, and respond with HTTP 200 and the updated configuration as JSON

#### Scenario: POST with malformed JSON returns 400

- **WHEN** a client sends `POST /api/v1/config` with a body that is not valid JSON
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify or persist the configuration
