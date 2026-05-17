## ADDED Requirements

### Requirement: Daemon starts with sane defaults

The daemon SHALL start without requiring any command-line arguments,
binding to `127.0.0.1:8080` and serving the bundled web UI.

#### Scenario: Launch with no arguments

- **WHEN** the daemon binary is launched with no arguments
- **THEN** it binds to `127.0.0.1:8080` within 2 seconds
- **AND** it logs a single startup line containing the bound address,
  the daemon version, and the build's git short SHA when available

### Requirement: Daemon honours command-line overrides

The daemon SHALL accept `--bind <host>` and `--port <port>` flags that
override the default bind address and port. Unknown flags MUST cause a
non-zero exit with a usage message printed to stderr.

#### Scenario: Override port

- **WHEN** the daemon is launched with `--port 9090`
- **THEN** it binds to `127.0.0.1:9090` instead of the default port

#### Scenario: Unknown flag rejects

- **WHEN** the daemon is launched with `--frobnicate`
- **THEN** it exits with a non-zero status
- **AND** stderr contains a usage line listing the supported flags

### Requirement: Daemon shuts down gracefully

The daemon SHALL respond to SIGINT (Ctrl-C) and SIGTERM by closing
listening sockets, sending a WebSocket close frame to every connected
client, and exiting with status 0 within 5 seconds.

#### Scenario: SIGINT during operation

- **WHEN** the daemon is running with at least one connected WebSocket
  client
- **AND** SIGINT is delivered to the daemon process
- **THEN** the listening socket is closed within 1 second
- **AND** all WebSocket clients receive a close frame
- **AND** the process exits with status 0 within 5 seconds total

### Requirement: Daemon emits structured startup and shutdown logs

The daemon SHALL emit at minimum one log line at startup and one at
shutdown, each containing a timestamp, severity, component, and a
human-readable message, written to stderr in a single-line format that
is greppable.

#### Scenario: Startup line shape

- **WHEN** the daemon starts successfully
- **THEN** stderr contains a line matching the pattern
  `<ISO-8601-timestamp> <LEVEL> <component> <message>` describing the
  bind address

#### Scenario: Shutdown line shape

- **WHEN** the daemon receives a shutdown signal and exits cleanly
- **THEN** stderr contains a final line at INFO or higher recording
  the shutdown reason and total uptime in seconds
