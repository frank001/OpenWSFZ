## ADDED Requirements

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
