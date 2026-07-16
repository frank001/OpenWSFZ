# daemon-host Specification

## Purpose

Specifies the daemon process's startup and shutdown behaviour: the welcome banner,
loopback-only network binding, clean shutdown on Ctrl-C/SIGTERM, config-file path override
via CLI flag and environment variable, and logging-pipeline initialisation/flush ordering
relative to the web host.

## Requirements

### Requirement: Welcome banner on startup

On startup the daemon SHALL print a welcome banner to stdout once the HTTP listener is bound and ready to accept connections. The banner SHALL include the full loopback URL (`http://127.0.0.1:<port>`) so the operator knows exactly where to open their browser. When the instance is running as a detached background worker (`--background-worker`, `daemon-background-mode`), the daemon SHALL NOT attempt to write the banner to stdout — stdout is not guaranteed to be valid once the process has detached from its console — and SHALL instead rely on the equivalent Information-level startup log line, which reaches the file sink that `daemon-background-mode` guarantees is active for a background worker.

#### Scenario: Banner emitted after listener is ready

- **WHEN** the daemon starts and Kestrel successfully binds to the configured port, and the instance is NOT a background worker
- **THEN** the daemon SHALL write a line containing the string `http://127.0.0.1:<port>` to stdout before returning control

#### Scenario: Banner includes operator instruction

- **WHEN** the banner is printed
- **THEN** the banner SHALL include a human-readable instruction directing the operator to open the URL in a browser (e.g., `"open this in your browser"` or equivalent)

#### Scenario: E2E test captures banner on stdout

- **WHEN** the published binary is launched as a subprocess with stdout piped, and it is NOT a background worker
- **THEN** the subprocess's stdout SHALL contain the banner text within 10 seconds of launch

#### Scenario: Background worker never attempts to write the banner to stdout

- **WHEN** the daemon starts as a background worker (`--background-worker`) and Kestrel successfully binds to the configured port
- **THEN** the daemon SHALL NOT call any direct `Console` write for the banner, and SHALL NOT crash as a result of stdout being unavailable after detachment

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

### Requirement: Restart as a graceful-shutdown trigger

In addition to SIGINT (Ctrl-C) and SIGTERM, the daemon SHALL support an API-initiated restart as a third trigger of its existing graceful shutdown sequence (WebSocket abort, capture-pipeline stop and dispose, logging-pipeline flush, process exit). No part of the existing SIGINT/SIGTERM shutdown sequence itself SHALL change; restart reuses it unmodified as its final step, after first spawning the replacement process (see the `remote-daemon-restart` capability).

#### Scenario: API-initiated restart runs the same shutdown sequence as Ctrl-C

- **WHEN** a restart is triggered via `POST /api/v1/system/restart` (and not refused because a QSO is transmitting)
- **THEN** the daemon SHALL run the same WebSocket-abort → capture-pipeline-stop → logging-flush → exit-0 sequence that already runs on SIGINT/SIGTERM

#### Scenario: Restart-triggered shutdown still exits 0

- **WHEN** the daemon stops as part of an API-initiated restart
- **THEN** the process SHALL exit with code 0, matching the existing "clean shutdown" requirement's exit-code convention for SIGINT/SIGTERM

---

### Requirement: Relaunch CLI flag recognised at startup

The daemon SHALL accept an optional `--relaunched-from <pid>` CLI argument at startup, identifying that this instance was spawned to replace another instance as part of a restart. This flag SHALL be purely informational/behaviour-gating (see the `remote-daemon-restart` capability's bind-retry requirement) and SHALL NOT be required for normal startup — its absence SHALL mean "this is an ordinary cold start," exactly as today.

#### Scenario: Startup without the flag behaves exactly as before this change

- **WHEN** the daemon is launched with no `--relaunched-from` argument
- **THEN** startup behaviour SHALL be unchanged from before this change, including failing immediately on a port-bind conflict

#### Scenario: Startup with the flag is logged

- **WHEN** the daemon is launched with `--relaunched-from <pid>`
- **THEN** the daemon SHALL log, at Information level, that it was started as a relaunch and the PID of the process it is replacing

---

### Requirement: Background CLI flags recognised at startup

The daemon SHALL accept two optional CLI flags related to background/detached operation, following the existing `--relaunched-from`-style convention (purely informational/behaviour-gating, not required for normal startup, silently ignored by any build that predates them): `--background`, identifying that at cold start the daemon SHOULD spawn a detached replacement of itself (see `daemon-background-mode`) and exit; and `--background-worker`, identifying that this instance IS the detached replacement (or has itself been spawned as one during a restart) and SHALL detach itself from its inherited console/controlling terminal before any other startup work. Absence of both flags SHALL mean an ordinary cold start, exactly as before either flag existed.

#### Scenario: Startup without either flag behaves exactly as before this change

- **WHEN** the daemon is launched with neither `--background` nor `--background-worker`
- **THEN** startup behaviour SHALL be unchanged from before this change

#### Scenario: Older build ignores the new flags

- **WHEN** a daemon build that predates this change is launched with `--background` or `--background-worker`
- **THEN** the daemon SHALL start normally, silently ignoring the unrecognised flag(s)
