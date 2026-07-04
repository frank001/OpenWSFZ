# file-logging Specification

## Purpose

Specifies the daemon's file logging sink: session-based rotation, scheduled rotation,
retention of old log files, and live reconfiguration without a restart.

## Requirements

### Requirement: File logging sink

When file logging is enabled, the daemon SHALL write all log events at or above the configured file log-level threshold to a file sink simultaneously with the console sink. The two sinks SHALL operate independently; disabling the file sink SHALL not affect console output.

#### Scenario: File sink inactive when disabled

- **WHEN** `logging.fileEnabled` is `false` (the default)
- **THEN** no log file SHALL be created and no file I/O SHALL occur

#### Scenario: File sink active when enabled

- **WHEN** `logging.fileEnabled` is `true` and the daemon starts
- **THEN** a log file SHALL be created in the configured directory and log events SHALL be written to it

#### Scenario: File log level filters independently of console

- **WHEN** `logging.fileLogLevel` is set to `"Warning"` and `logging.fileEnabled` is `true`
- **THEN** the file SHALL contain only log events at Warning level or above, regardless of the console log level

#### Scenario: Invalid directory falls back gracefully

- **WHEN** `logging.directory` contains a path the daemon cannot create or write to
- **THEN** the daemon SHALL log a Warning to the console sink, skip opening the file sink, and continue starting up normally

---

### Requirement: Session rotation

Each application start SHALL open a new log file with a UTC-timestamped name. The file from a previous session SHALL never be appended to.

#### Scenario: New file created on each startup

- **WHEN** the daemon starts with `logging.fileEnabled` true
- **THEN** a new file named `openswfz-<yyyyMMddTHHmmssZ>.log` SHALL be created, where the timestamp is the UTC time of startup

#### Scenario: Previous session file is not modified

- **WHEN** the daemon starts and a log file from a prior session exists in the directory
- **THEN** that file SHALL remain unchanged; the new session SHALL write only to the new file

---

### Requirement: Scheduled log rotation

The daemon SHALL support automatic log rotation on a configurable schedule: `"session"` (startup only), `"hourly"`, `"daily"`, or `"weekly"`. When a scheduled rotation fires, the current log file SHALL be closed and a new timestamped file SHALL be opened.

#### Scenario: No scheduled rotation when schedule is "session"

- **WHEN** `logging.rotationSchedule` is `"session"`
- **THEN** the log file SHALL not be rotated for the lifetime of the process (only session rotation applies)

#### Scenario: Hourly rotation

- **WHEN** `logging.rotationSchedule` is `"hourly"`
- **THEN** the daemon SHALL rotate the log file at each UTC hour boundary (HH:00:00Z)

#### Scenario: Daily rotation at configured time

- **WHEN** `logging.rotationSchedule` is `"daily"` and `logging.rotationTime` is `"03:00"`
- **THEN** the daemon SHALL rotate the log file each day when UTC time reaches 03:00

#### Scenario: Weekly rotation at configured day and time

- **WHEN** `logging.rotationSchedule` is `"weekly"`, `logging.rotationDayOfWeek` is `"Sunday"`, and `logging.rotationTime` is `"00:00"`
- **THEN** the daemon SHALL rotate the log file each Sunday at 00:00 UTC

#### Scenario: Rotation timer recalculated after each fire

- **WHEN** a scheduled rotation fires
- **THEN** the next rotation time SHALL be calculated from the current UTC time, not by adding a fixed interval to the previous fire time

---

### Requirement: Log file retention

After each rotation (session or scheduled), the daemon SHALL enforce the configured maximum number of retained log files by deleting the oldest files when the limit is exceeded.

#### Scenario: Files within limit are not deleted

- **WHEN** the number of `openswfz-*.log` files in the log directory is less than or equal to `logging.maxFiles`
- **THEN** no files SHALL be deleted

#### Scenario: Oldest files deleted when limit exceeded

- **WHEN** rotation produces a new file and the total count exceeds `logging.maxFiles`
- **THEN** the daemon SHALL delete the oldest files (by filename sort, which is chronological for ISO-8601 names) until the count equals `logging.maxFiles`

#### Scenario: Deletion failure is non-fatal

- **WHEN** a retention deletion fails (e.g. the file is open in another process)
- **THEN** the daemon SHALL log a Warning and continue; the rotation itself SHALL not be aborted

#### Scenario: maxFiles clamped to minimum of 1

- **WHEN** `logging.maxFiles` is configured as zero or a negative number
- **THEN** the daemon SHALL treat it as `1`, log a Warning at startup, and retain at least the current file

---

### Requirement: Live logging reconfiguration

When the operator saves new logging settings via the Settings page, the daemon SHALL apply the changes without restarting the process.

#### Scenario: Enabling file logging takes effect immediately

- **WHEN** the operator changes `fileEnabled` from `false` to `true` and saves
- **THEN** a new log file SHALL be opened and subsequent log events SHALL be written to it, within 2 seconds of the save

#### Scenario: Disabling file logging takes effect immediately

- **WHEN** the operator changes `fileEnabled` from `true` to `false` and saves
- **THEN** the current log file SHALL be flushed and closed, and no further file I/O SHALL occur

#### Scenario: Log level change takes effect immediately

- **WHEN** the operator changes `fileLogLevel` and saves
- **THEN** subsequent log events in the file sink SHALL reflect the new threshold
