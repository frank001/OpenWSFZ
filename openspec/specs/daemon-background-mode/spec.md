# daemon-background-mode Specification

## Purpose

Specifies the `--background`/`--background-worker` CLI flags, the platform-specific
console/terminal detachment mechanisms (Win32 `FreeConsole()` on Windows, a `SIGHUP`-ignoring
`PosixSignalRegistration` on Linux/macOS), the bounded spawn-and-confirm cold-start sequence, the
forced-file-logging/no-console-sink observability guarantee for a detached worker, and the
propagation of detached status across every future self-relaunch — allowing an operator to run
the daemon detached from its originating console/terminal (`dotnet run -- --background`, or a
published apphost) so that closing that console/terminal does not terminate the process.

## Requirements

### Requirement: `--background` spawns a detached instance and returns control immediately

The daemon SHALL accept a `--background` CLI flag. When present at what is otherwise an ordinary cold start (no `--relaunched-from`, no `--background-worker`), the daemon SHALL spawn a replacement instance of itself with `--background-worker` appended to its arguments (reusing the existing relaunch-command resolution mechanism), then exit — without waiting for that replacement to complete its own startup beyond the bounded confirmation below.

#### Scenario: `--background` cold start hands the shell back

- **WHEN** the daemon is launched with `--background` and no `--relaunched-from`/`--background-worker`
- **THEN** the daemon SHALL spawn a child process with `--background-worker` (plus all original CLI arguments) and SHALL exit once that spawn is confirmed to have started, without requiring the child to have finished its own startup first

#### Scenario: Spawn failure aborts cleanly

- **WHEN** `--background` is present and spawning the child process itself fails (e.g. the resolved executable path does not exist)
- **THEN** the daemon SHALL print a diagnosable error and exit non-zero, and SHALL NOT report a successful background launch

---

### Requirement: `--background-worker` detaches the process in place

The daemon SHALL accept a `--background-worker` CLI flag, identifying that this instance is the actual detached worker (as opposed to `--background`, which identifies the original interactive invocation that spawns one). When present, before any other startup work (config load, logging pipeline construction, host building), the daemon SHALL detach itself from its inherited console/controlling terminal using the platform-appropriate mechanism, then proceed with normal startup in place. It SHALL NOT spawn another child.

#### Scenario: Windows worker detaches via FreeConsole

- **WHEN** the daemon is launched with `--background-worker` on Windows
- **THEN** the daemon SHALL call the Win32 `FreeConsole` function on itself before any other startup work, so that subsequently closing whatever console it was attached to at launch does not terminate the process

#### Scenario: POSIX worker ignores SIGHUP

- **WHEN** the daemon is launched with `--background-worker` on Linux or macOS
- **THEN** the daemon SHALL register a handler that ignores `SIGHUP` before any other startup work, so that subsequently closing the terminal that launched it does not terminate the process

#### Scenario: `--background-worker` alone never spawns another child

- **WHEN** the daemon is launched with `--background-worker` (with or without `--relaunched-from`)
- **THEN** the daemon SHALL NOT spawn any additional process as a result of this flag — it detaches itself and continues starting up directly

---

### Requirement: Background status propagates across every future restart

An instance that was launched as (or has become, via `--background-worker`) a detached background instance SHALL cause every subsequent replacement spawned via `POST /api/v1/system/restart` (`remote-daemon-restart`) to also be launched with `--background-worker`, so that detached status persists across restarts by default rather than requiring the operator to specify `--background` again.

#### Scenario: Restarting a background instance produces a background replacement

- **WHEN** `POST /api/v1/system/restart` is invoked on an instance that was itself started with `--background-worker`
- **THEN** the spawned replacement's arguments SHALL include `--background-worker` in addition to `--relaunched-from <pid>`

#### Scenario: Restarting a non-background instance produces a non-background replacement

- **WHEN** `POST /api/v1/system/restart` is invoked on an instance that was started without `--background`/`--background-worker`
- **THEN** the spawned replacement's arguments SHALL NOT include `--background-worker`, matching today's existing (unchanged) behaviour

---

### Requirement: A background instance is never silently unobservable

A daemon instance running with `--background-worker` SHALL guarantee file logging is active, regardless of the persisted `logging.fileEnabled` configuration value, and SHALL NOT configure a console log sink.

#### Scenario: File logging is forced on for a background worker even when config disables it

- **WHEN** the daemon is launched with `--background-worker` and the persisted configuration has `logging.fileEnabled` set to `false`
- **THEN** the daemon SHALL still write logs to a file for the duration of that process, and SHALL log one Warning-level line naming the resolved log file path before continuing startup

#### Scenario: The persisted config file is not modified by the force-on

- **WHEN** file logging is forced on for a background worker per the scenario above
- **THEN** the on-disk `config.json`'s `logging.fileEnabled` value SHALL remain whatever the operator last saved — the force-on SHALL be in-memory for that process only

#### Scenario: No console sink is configured for a background worker

- **WHEN** the daemon is launched with `--background-worker`
- **THEN** the logging pipeline SHALL NOT configure a console output sink for that process

---

### Requirement: Bounded confirmation on `--background` cold start

After spawning the detached child, the original `--background` invocation SHALL poll the daemon's own status endpoint on the resolved port for up to a fixed budget before exiting, reporting either a successful confirmation or an explicit "could not confirm yet" caveat — never an unbounded wait and never a silent exit with no feedback at all.

#### Scenario: Confirmed startup within the budget

- **WHEN** the spawned child begins responding successfully to its status endpoint within the confirmation budget
- **THEN** the original `--background` invocation SHALL print a confirmation naming the child's process ID and the resolved log file path, then exit 0

#### Scenario: Unconfirmed startup after the budget is exhausted

- **WHEN** the spawned child has not yet responded successfully to its status endpoint once the confirmation budget is exhausted
- **THEN** the original `--background` invocation SHALL print a message stating that startup could not be confirmed within the budget and naming the resolved log file path to check, then exit 0 (the spawn itself having already succeeded)

---

### Requirement: Unknown flags remain forward-compatible

A daemon build that predates `--background`/`--background-worker` SHALL ignore either flag without error, matching this project's existing CLI-parsing convention.

#### Scenario: Older build ignores the new flags

- **WHEN** a daemon build that predates this change is launched with `--background` or `--background-worker`
- **THEN** the daemon SHALL start normally, silently ignoring the unrecognised flag(s)
