## ADDED Requirements

### Requirement: Settings page — Logging section

The Settings page SHALL contain a "Logging" section that allows the operator to configure all file logging options. The section SHALL be rendered below the existing audio-device and port controls and SHALL participate in the same Save/Cancel flow.

#### Scenario: Logging section is present on the Settings page

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain a section headed "Logging" with controls for: an enable/disable toggle (`fileEnabled`), a directory text input (`directory`), a log-level selector (`fileLogLevel`), a rotation-schedule selector (`rotationSchedule`), a rotation-time input (`rotationTime`), a rotation-day-of-week selector (`rotationDayOfWeek`), and a max-files number input (`maxFiles`)

#### Scenario: Logging controls pre-filled from current config

- **WHEN** the Settings page JavaScript calls `GET /api/v1/config`
- **THEN** each logging control SHALL be populated with the value from `config.logging` (or the default if absent)

#### Scenario: rotationDayOfWeek control is conditionally visible

- **WHEN** `rotationSchedule` is set to any value other than `"weekly"`
- **THEN** the `rotationDayOfWeek` control and its label SHALL be hidden (display:none or equivalent)

- **WHEN** `rotationSchedule` is changed to `"weekly"`
- **THEN** the `rotationDayOfWeek` control SHALL become visible without a page reload

#### Scenario: rotationTime control hidden for session and hourly schedules

- **WHEN** `rotationSchedule` is `"session"` or `"hourly"`
- **THEN** the `rotationTime` control and its label SHALL be hidden

- **WHEN** `rotationSchedule` is changed to `"daily"` or `"weekly"`
- **THEN** the `rotationTime` control SHALL become visible

#### Scenario: Save includes logging config

- **WHEN** the operator changes any logging field and clicks Save
- **THEN** the `POST /api/v1/config` body SHALL include the updated `logging` object alongside the existing audio device and port fields

#### Scenario: Logging section disabled when fileEnabled is false

- **WHEN** the `fileEnabled` toggle is off
- **THEN** the directory, log level, rotation schedule, rotation time, day-of-week, and max-files controls SHALL be visually disabled (greyed out) and SHALL NOT be editable

- **WHEN** the `fileEnabled` toggle is turned on
- **THEN** the dependent controls SHALL become enabled and editable immediately without a page reload
