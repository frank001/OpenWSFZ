## ADDED Requirements

### Requirement: Restart Daemon action in Settings

The Settings page (Advanced tab) SHALL provide a single "Restart Daemon" action that calls `POST /api/v1/system/restart`. This SHALL be the one place in the UI that actually triggers a restart; any restart-required notice elsewhere in the UI SHALL link/point to this action rather than duplicating its own restart control.

#### Scenario: Restart Daemon action is present in the Advanced tab

- **WHEN** the operator opens Settings → Advanced
- **THEN** a "Restart Daemon" action SHALL be visible

#### Scenario: Restart-required notices link to the single restart action

- **WHEN** the operator changes `ptt.method` or a Remote Access bind-affecting setting and saves
- **THEN** the restart-required notice shown SHALL direct the operator to the Advanced tab's "Restart Daemon" action rather than presenting its own separate restart control

---

### Requirement: Restart requires explicit confirmation

The Restart Daemon action SHALL require the operator to explicitly confirm before the restart request is sent, unlike this page's other actions (Save, Retry, Refresh, Test), which act immediately with no confirmation prompt.

#### Scenario: Clicking Restart Daemon shows a confirmation prompt

- **WHEN** the operator clicks "Restart Daemon"
- **THEN** the UI SHALL present a confirmation prompt describing the disruption (the connection will drop briefly and any other connected operators will also be disconnected) before sending `POST /api/v1/system/restart`

#### Scenario: Declining the confirmation sends no request

- **WHEN** the operator is shown the confirmation prompt and declines/cancels it
- **THEN** the UI SHALL NOT send `POST /api/v1/system/restart`

#### Scenario: A 409 (QSO transmitting) response is shown as an actionable message, not a silent failure

- **WHEN** the operator confirms Restart Daemon and the server responds `409 Conflict` because a QSO is transmitting
- **THEN** the UI SHALL display a message explaining that restart was refused because a QSO is currently transmitting, and SHALL NOT show a "reconnecting" state (no restart is in progress)

---

### Requirement: Reconnect UX after a confirmed restart

After a restart request is accepted (`202`), the UI SHALL show a "reconnecting…" state and poll `GET /api/v1/status` until it succeeds, then automatically return to normal operation, rather than presenting the connection drop as an error.

#### Scenario: UI shows reconnecting state immediately after 202

- **WHEN** `POST /api/v1/system/restart` responds `202 Accepted`
- **THEN** the UI SHALL immediately show a "reconnecting…" state

#### Scenario: UI recovers automatically once the new instance is reachable

- **WHEN** the daemon has restarted and `GET /api/v1/status` begins responding successfully again
- **THEN** the UI SHALL clear the "reconnecting…" state and resume normal operation without requiring a manual page reload
