# remote-daemon-restart Specification

## Purpose

Specifies the restart API endpoint, the self re-exec process-relaunch mechanism, the
in-flight-transmission safety gate, and the port hand-off sequencing between the old and new
daemon process instances — allowing an operator to apply settings that require a full daemon
restart (e.g. `ptt.method`, Remote Access bind address) from a remote browser, without physical
or console access to the machine the daemon runs on.

## Requirements

### Requirement: Restart endpoint

The daemon SHALL expose `POST /api/v1/system/restart`. When invoked while no QSO is transmitting, it SHALL respond `202 Accepted` and then relaunch the daemon process (spawn a new instance, then gracefully stop the current one) without requiring any external process supervisor, OS service, or operator action to bring the new instance back up. The endpoint is subject to the same authentication middleware as every other `/api/*` path (no separate auth mechanism is introduced).

#### Scenario: Restart request returns 202 and the daemon comes back on the same port

- **WHEN** a client sends `POST /api/v1/system/restart` and no QSO is currently transmitting
- **THEN** the daemon SHALL respond `202 Accepted`, and within the bind-retry budget (see "Bind-retry on relaunch" below) a new daemon process SHALL be listening on the same configured port, with no operator action taken in between

#### Scenario: Restart request over LAN requires the configured passphrase

- **WHEN** `RemoteAccess.Enabled` is `true`, `RemoteAccess.Passphrase` is a non-empty string, and a non-loopback client sends `POST /api/v1/system/restart` without a correct `X-Api-Key` header
- **THEN** the request SHALL be rejected with `401`, identically to any other `/api/*` endpoint, and the daemon SHALL NOT restart

#### Scenario: Restart applies the currently-persisted configuration

- **WHEN** the daemon restarts via this endpoint
- **THEN** the new process SHALL load configuration from the same config file path as the process it replaced (same CLI `--config`/`OPENWSFZ_CONFIG` resolution), reflecting whatever is currently persisted on disk (including any settings saved but not yet applied, such as `ptt.method`)

---

### Requirement: Restart refused while a QSO is transmitting

`POST /api/v1/system/restart` SHALL check whether a QSO is currently transmitting (mirroring the existing `IQsoController.Keying` guard already used by `POST /api/v1/ptt/test`) and SHALL refuse the request rather than interrupting an in-progress over-the-air transmission.

#### Scenario: Restart rejected during an active transmission

- **WHEN** `IQsoController.Keying` is `true` and a client sends `POST /api/v1/system/restart`
- **THEN** the daemon SHALL respond `409 Conflict` naming the reason (a QSO is currently transmitting), and SHALL NOT restart, spawn a new process, or otherwise alter the in-progress transmission

#### Scenario: Restart succeeds once transmission ends

- **WHEN** a prior `POST /api/v1/system/restart` was rejected with 409 because a QSO was transmitting, and the operator subsequently waits for the QSO to finish (or calls the existing `POST /api/v1/tx/abort`) before retrying
- **THEN** the retried `POST /api/v1/system/restart` SHALL proceed per the "Restart endpoint" requirement above

---

### Requirement: Self re-exec relaunch mechanism

Restarting SHALL be implemented by the daemon spawning a new instance of itself — same executable and CLI arguments — before the current instance stops, so the new instance can begin listening without depending on any external supervisor. When the current process was launched via the `dotnet` generic host (a framework-dependent launch, e.g. `dotnet OpenWSFZ.Daemon.dll` or `dotnet run`), the relaunch command SHALL re-invoke `dotnet` with the daemon assembly's own location as the first argument; when launched as a self-contained/apphost executable, the relaunch command SHALL invoke that same executable directly. In both cases the new process SHALL be launched with an additional CLI flag identifying it as a relaunch (e.g. `--relaunched-from <pid>`), and any older build that does not recognise this flag SHALL ignore it without error (matching this project's existing "unknown arguments are silently ignored" CLI-parsing convention).

#### Scenario: Relaunch under `dotnet run` / framework-dependent launch resolves the managed assembly

- **WHEN** the current process's `Environment.ProcessPath` is the `dotnet` executable (a framework-dependent launch)
- **THEN** the spawned child process's command line SHALL include the daemon assembly's own file path as an argument to `dotnet`, followed by the original CLI arguments and the relaunch flag

#### Scenario: Relaunch under a self-contained/apphost executable relaunches that executable directly

- **WHEN** the current process's `Environment.ProcessPath` is not the `dotnet` executable (a self-contained apphost)
- **THEN** the spawned child process SHALL be a new instance of that same executable, launched with the original CLI arguments and the relaunch flag

#### Scenario: Relaunch flag is a no-op on an older build

- **WHEN** a daemon build that predates this change is launched with `--relaunched-from <pid>`
- **THEN** the daemon SHALL start normally, silently ignoring the unrecognised flag

#### Scenario: Relaunch command is logged before the current process begins stopping

- **WHEN** a restart is triggered
- **THEN** the daemon SHALL log the resolved relaunch command (executable and arguments) at Information level before spawning the child process

#### Scenario: A failure to spawn the child aborts the restart before the current process stops

- **WHEN** `POST /api/v1/system/restart` attempts to spawn the child process and process creation itself fails (e.g., the resolved executable path does not exist)
- **THEN** the daemon SHALL log the failure and SHALL NOT proceed to stop the current instance — the currently-running daemon SHALL remain up and serving requests

---

### Requirement: Spawn-before-stop ordering

The daemon SHALL spawn the new (child) process before stopping the current (parent) process, so the child's bind-retry window (see below) overlaps with, rather than follows, the parent's shutdown sequence.

#### Scenario: Child process is spawned prior to the parent's shutdown sequence beginning

- **WHEN** a restart proceeds (not refused per the transmitting-QSO check)
- **THEN** the child process SHALL be spawned, and only once that spawn has been confirmed to have started SHALL the parent process begin its existing graceful-shutdown sequence (WebSocket abort, capture-pipeline stop, log flush, process exit)

---

### Requirement: Bind-retry on relaunch

A daemon process launched with the relaunch flag (`--relaunched-from <pid>`) SHALL retry binding its configured HTTP port if the initial bind attempt fails because the port is still in use, up to a fixed total budget, before giving up. A daemon process launched without the relaunch flag SHALL NOT retry a bind failure — it SHALL fail immediately, exactly as today.

#### Scenario: Relaunched instance retries a bind conflict while the old instance is still shutting down

- **WHEN** a daemon is started with `--relaunched-from <pid>` and its first attempt to bind the configured port fails because the port is still held by the process it is replacing
- **THEN** the daemon SHALL wait and retry the bind attempt, repeating until either the bind succeeds or a fixed total time budget (20 seconds) is exhausted

#### Scenario: Relaunched instance gives up after the retry budget is exhausted

- **WHEN** a daemon started with `--relaunched-from <pid>` has retried binding for the full 20-second budget without success
- **THEN** the daemon SHALL log an error describing the failure and SHALL exit with a non-zero exit code

#### Scenario: A normal (non-relaunch) startup still fails fast on a port conflict

- **WHEN** a daemon is started without `--relaunched-from` and its configured port is already in use by an unrelated process
- **THEN** the daemon SHALL fail immediately with no retry, exactly matching its behaviour before this change

#### Scenario: Retrying the bind does not repeat side-effecting startup work

- **WHEN** a relaunched instance's first bind attempt fails and it retries
- **THEN** the retry SHALL re-attempt only the host-listener bind step, and SHALL NOT re-open audio devices, re-construct the native decoder, or re-open any serial port — those are only initiated after a bind attempt has already succeeded
