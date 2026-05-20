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
