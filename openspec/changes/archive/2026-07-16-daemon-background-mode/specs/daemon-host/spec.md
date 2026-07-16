## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Background CLI flags recognised at startup

The daemon SHALL accept two optional CLI flags related to background/detached operation, following the existing `--relaunched-from`-style convention (purely informational/behaviour-gating, not required for normal startup, silently ignored by any build that predates them): `--background`, identifying that at cold start the daemon SHOULD spawn a detached replacement of itself (see `daemon-background-mode`) and exit; and `--background-worker`, identifying that this instance IS the detached replacement (or has itself been spawned as one during a restart) and SHALL detach itself from its inherited console/controlling terminal before any other startup work. Absence of both flags SHALL mean an ordinary cold start, exactly as before either flag existed.

#### Scenario: Startup without either flag behaves exactly as before this change

- **WHEN** the daemon is launched with neither `--background` nor `--background-worker`
- **THEN** startup behaviour SHALL be unchanged from before this change

#### Scenario: Older build ignores the new flags

- **WHEN** a daemon build that predates this change is launched with `--background` or `--background-worker`
- **THEN** the daemon SHALL start normally, silently ignoring the unrecognised flag(s)
