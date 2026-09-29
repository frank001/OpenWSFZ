## ADDED Requirements

### Requirement: The operator controls the archive from the Settings page

The Settings page SHALL contain an **Audio archive** group with a mode selector, a directory text field (blank meaning the default location, sent as `null`), a maximum-size field (MB), a maximum-age field (hours) and a write-manifest checkbox. The group SHALL be sent on every save and SHALL participate in the FR-040 unsaved-changes flow. Server-side validation SHALL match how `CycleArchiveService` treats each value (design D5). A field that needs a restart SHALL say so on the page.

#### Scenario: Mode set in the UI survives reload and an unrelated save

- **WHEN** the operator sets the archive mode to All, saves, reloads the page, and then saves an unrelated setting
- **THEN** the page SHALL show All after the reload and again after the second save

#### Scenario: A blank directory means the default location

- **WHEN** the operator leaves the directory field blank and saves
- **THEN** `cycleAudioArchive.directory` SHALL be persisted as `null`
