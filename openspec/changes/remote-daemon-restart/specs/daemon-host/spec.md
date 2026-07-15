## ADDED Requirements

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
