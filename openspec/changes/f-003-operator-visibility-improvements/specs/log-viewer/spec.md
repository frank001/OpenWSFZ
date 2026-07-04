## ADDED Requirements

### Requirement: Settings page exposes a polled tail of the daemon's active log file

The settings page SHALL provide a "Logs" tab, alongside the existing General/Radio
hardware/Logging/Advanced/Frequencies tabs, that polls `GET /api/v1/logs/tail?lines=150` on a
fixed interval and renders the returned lines in display order (oldest first, newest last).

#### Scenario: Logs tab shows the last 150 lines of the active log file

- **WHEN** the operator opens the settings page's Logs tab and file logging is enabled with an
  active log file
- **THEN** the tab SHALL display up to the last 150 lines of that file, refreshed automatically on
  an interval

#### Scenario: Logs tab handles file logging being disabled

- **WHEN** the operator opens the Logs tab and file logging is disabled (no active log file)
- **THEN** the tab SHALL show an empty/placeholder state rather than an error

---

### Requirement: `GET /api/v1/logs/tail` returns the last N lines of the active log file

`GET /api/v1/logs/tail` SHALL accept an optional `lines` query parameter (default 150) and return
the last *N* lines of the daemon's currently active log file as JSON.

#### Scenario: Default request returns the last 150 lines

- **WHEN** a client sends `GET /api/v1/logs/tail` with no `lines` parameter
- **THEN** the response SHALL contain at most the last 150 lines of the active log file

#### Scenario: Explicit line count is honoured

- **WHEN** a client sends `GET /api/v1/logs/tail?lines=50`
- **THEN** the response SHALL contain at most the last 50 lines of the active log file

#### Scenario: No active log file returns an empty result, not an error

- **WHEN** file logging is disabled or no log file has been created yet
- **THEN** `GET /api/v1/logs/tail` SHALL return an empty line list with HTTP 200, not an error
  status

---

### Requirement: A standalone full-log page is available with no auto-refresh

A standalone page (`web/logs.html`), reached via a link or button from the settings page's Logs
tab, SHALL fetch the daemon's entire currently active log file exactly once on page load via
`GET /api/v1/logs/full`, and SHALL NOT poll or auto-refresh — new log content is only shown after
the operator manually reloads the browser page.

#### Scenario: Full-log page shows the complete active log file on load

- **WHEN** the operator navigates to `web/logs.html`
- **THEN** the page SHALL fetch and display the complete contents of the currently active log file

#### Scenario: Full-log page does not auto-refresh

- **WHEN** new lines are appended to the active log file after `web/logs.html` has loaded
- **THEN** the page SHALL NOT reflect those new lines until the operator manually reloads the page

---

### Requirement: `GET /api/v1/logs/full` returns the complete active log file as plain text

`GET /api/v1/logs/full` SHALL return the complete contents of the daemon's currently active log
file with `Content-Type: text/plain`.

#### Scenario: Full log is returned as plain text

- **WHEN** a client sends `GET /api/v1/logs/full` while an active log file exists
- **THEN** the response SHALL have `Content-Type: text/plain` and a body equal to that file's
  complete current contents

#### Scenario: No active log file returns an empty body, not an error

- **WHEN** file logging is disabled or no log file has been created yet
- **THEN** `GET /api/v1/logs/full` SHALL return an empty body with HTTP 200, not an error status
