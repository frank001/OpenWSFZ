## Requirements

### Requirement: Welcome banner on startup

On startup the daemon SHALL print a welcome banner to stdout once the HTTP listener is bound and ready to accept connections. The banner SHALL include the full loopback URL (`http://127.0.0.1:<port>`) so the operator knows exactly where to open their browser.

#### Scenario: Banner emitted after listener is ready

- **WHEN** the daemon starts and Kestrel successfully binds to the configured port
- **THEN** the daemon SHALL write a line containing the string `http://127.0.0.1:<port>` to stdout before returning control

#### Scenario: Banner includes operator instruction

- **WHEN** the banner is printed
- **THEN** the banner SHALL include a human-readable instruction directing the operator to open the URL in a browser (e.g., `"open this in your browser"` or equivalent)

#### Scenario: E2E test captures banner on stdout

- **WHEN** the published binary is launched as a subprocess with stdout piped
- **THEN** the subprocess's stdout SHALL contain the banner text within 10 seconds of launch

---

### Requirement: Loopback-only bind enforcement

The daemon SHALL bind exclusively to the loopback interface (`127.0.0.1`) in v1. Any attempt to bind to a non-loopback address SHALL be overridden silently and a warning SHALL be logged to stderr.

#### Scenario: Daemon binds only to 127.0.0.1

- **WHEN** the daemon starts with default or any configuration
- **THEN** the Kestrel listener SHALL be bound to `127.0.0.1` and NOT to `0.0.0.0` or any non-loopback address

#### Scenario: Non-loopback address is overridden

- **WHEN** a `--port` or future config option specifies a non-loopback bind address
- **THEN** the daemon SHALL silently override it to `127.0.0.1`, log a `WARN` message to stderr, and continue starting up

---

### Requirement: Clean shutdown on Ctrl-C and SIGTERM

The daemon SHALL handle Ctrl-C (SIGINT) and SIGTERM signals by initiating a graceful shutdown sequence and exiting with code 0.

#### Scenario: Ctrl-C triggers clean exit

- **WHEN** the operator sends SIGINT (Ctrl-C) to the running daemon process
- **THEN** the daemon SHALL begin its graceful shutdown sequence and exit with code 0

#### Scenario: SIGTERM triggers clean exit

- **WHEN** the host OS sends SIGTERM to the daemon process
- **THEN** the daemon SHALL begin its graceful shutdown sequence and exit with code 0

#### Scenario: Abnormal exit uses non-zero code

- **WHEN** the daemon exits due to an unhandled exception or startup failure
- **THEN** the process SHALL exit with a non-zero code and SHALL print a diagnostic message to stderr

---

### Requirement: Config-file path override via CLI flag and environment variable

The daemon SHALL accept a `--config <path>` CLI argument and an `OPENWSFZ_CONFIG` environment variable. When either is provided it SHALL override the platform default config-file path. The CLI flag takes precedence over the environment variable.

#### Scenario: --config flag overrides default path

- **WHEN** the daemon is launched with `--config /custom/path/config.json`
- **THEN** the daemon SHALL load and save configuration from `/custom/path/config.json` instead of the platform default path

#### Scenario: OPENWSFZ_CONFIG env var overrides default path

- **WHEN** the daemon is launched with `OPENWSFZ_CONFIG=/custom/config.json` set in the environment and no `--config` flag
- **THEN** the daemon SHALL use the path from the environment variable

#### Scenario: CLI flag takes precedence over env var

- **WHEN** both `--config` flag and `OPENWSFZ_CONFIG` are set
- **THEN** the daemon SHALL use the path from the `--config` flag

#### Scenario: Resolved config path logged at startup

- **WHEN** the daemon starts
- **THEN** it SHALL log a line at INFO level naming the resolved config-file path and its source (flag / env-var / default) before the web host starts accepting connections

---

### Requirement: Logging pipeline initialised before web host

The daemon SHALL configure and open the logging pipeline (including the file sink, if enabled) before `WebApplication.Build()` is called, so that log events emitted during application startup are captured.

#### Scenario: File sink open before first application log event

- **WHEN** the daemon starts with `logging.fileEnabled` true
- **THEN** the log file SHALL exist on disk before the welcome banner is written to stdout

#### Scenario: Early startup errors captured in file

- **WHEN** the daemon fails to bind to the configured port during startup
- **THEN** the error SHALL appear in the file log (if file logging is enabled) as well as on the console

---

### Requirement: Logging pipeline flushed on shutdown

The daemon SHALL flush and cleanly close the file logging sink as part of its graceful shutdown sequence, after the web host has stopped accepting connections.

#### Scenario: File flushed before process exit

- **WHEN** the operator sends SIGINT or SIGTERM and the daemon begins graceful shutdown
- **THEN** all buffered log events SHALL be written to the file sink before the process exits, and the file handle SHALL be closed cleanly

#### Scenario: No log events lost on Ctrl-C

- **WHEN** the operator presses Ctrl-C immediately after a log event is emitted
- **THEN** that log event SHALL be present in the log file after the process exits

---

### Requirement: CycleFramer and Ft8Decoder wired into daemon lifecycle

The daemon SHALL instantiate `CycleFramer` and `Ft8Decoder` in `Program.cs` and start
`CycleFramer.RunAsync` on `ApplicationStarted` (after `CaptureManager.StartAsync` is
called). On `ApplicationStopping` the daemon SHALL cancel the `CycleFramer`'s
`CancellationToken` and await `CycleFramer.RunAsync` before disposing, mirroring the
existing pattern used for `CaptureManager`.

#### Scenario: CycleFramer starts when capture is active

- **WHEN** the daemon starts and a device is configured
- **THEN** `CycleFramer.RunAsync` SHALL be started on `ApplicationStarted` in the same
  callback that calls `CaptureManager.StartAsync`

#### Scenario: CycleFramer does not start when no device is configured

- **WHEN** the daemon starts and `AppConfig.AudioDeviceName` is null
- **THEN** `CycleFramer.RunAsync` SHALL NOT be called and `CycleFramer` SHALL remain idle

#### Scenario: CycleFramer restarts when capture device changes

- **WHEN** `POST /api/v1/config` is called with a new non-null `audioDeviceName`
- **THEN** any running `CycleFramer` session SHALL be cancelled and a new one SHALL be
  started after `CaptureManager.StartAsync` returns

#### Scenario: CycleFramer is stopped on daemon shutdown

- **WHEN** the daemon receives a shutdown signal (Ctrl-C or SIGTERM)
- **THEN** `CycleFramer`'s `CancellationToken` SHALL be cancelled and `RunAsync` SHALL
  be awaited (with a 3-second timeout) before the process exits
