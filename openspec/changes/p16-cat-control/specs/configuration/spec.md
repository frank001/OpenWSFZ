## ADDED Requirements

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
