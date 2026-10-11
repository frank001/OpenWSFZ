## ADDED Requirements

### Requirement: The subtraction cycle budget SHALL have an optional replay-only override and an unchanged default

The decoder's per-cycle wall-clock budget for pass 0 plus the residual pass SHALL remain 13 s. An optional override, resolved once when the decoder is constructed, MAY replace it for replay measurements on hosts slower than the station. The override is replay-only by intent and SHALL NOT be a `config.json` key or a Settings-page field. With the override unset, the value passed to the residual pass SHALL be exactly the value the build before this change passes, and the decode output SHALL be unchanged.

A valid override is a number of seconds greater than or equal to 13, or the word `unlimited`. Any other value (below 13, zero, negative, non-numeric, empty) SHALL be refused when the decoder is constructed with an error naming the variable and the rule; it SHALL NOT be clamped or ignored.

#### Scenario: Unset is byte-identical to the current build

- **WHEN** no override is set
- **THEN** the budget passed to the residual pass at both call sites (one-stage and two-stage) equals 13 s minus the elapsed pass-0 time, as in the build before this change
- **AND** a fixed cycle decoded with the override unset yields the same decodes as the build before this change

#### Scenario: A valid number of seconds raises the budget

- **WHEN** the override is set to a number of seconds of at least 13
- **THEN** the budget passed to the residual pass is that many seconds minus the elapsed pass-0 time

#### Scenario: "unlimited" removes the deadline

- **WHEN** the override is set to `unlimited`
- **THEN** the residual pass is called without a deadline and is not abandoned for time

#### Scenario: An invalid value is refused

- **WHEN** the override is set to a value below 13, to zero, to a negative number, to text that is not a number or `unlimited`, or to an empty string
- **THEN** constructing the decoder fails with an error that names the variable and states the valid range
- **AND** no decode runs with a different budget

### Requirement: The effective subtraction budget SHALL be logged on every residual-pass line and once when an override is active

Every residual-pass summary log line SHALL carry the effective budget as a trailing field `budgetMs` (milliseconds, or `unlimited`). The existing fields of that line (`residualDecodes`, `elapsedMs`, `deadlineAbandoned`, `containedException`, `fittedSignals`) SHALL keep their names, order and meaning, so that each cycle's residual-pass duration and abandoned/completed flag remain readable by the replay harness. When an override is active, the decoder SHALL log one warning at construction that states the value and that it is for replay only. The line SHALL stay aggregate-only (no message text, no callsigns).

#### Scenario: The default is visible in the log

- **WHEN** a residual pass completes with the override unset
- **THEN** the log line ends with `budgetMs=13000`

#### Scenario: An override is visible in the log

- **WHEN** the override is `30` (seconds)
- **THEN** the construction warning states a 30 s replay-only override
- **AND** every residual-pass line ends with `budgetMs=30000`

#### Scenario: Existing consumers keep working

- **WHEN** the residual-pass log line is parsed by the current tests and by the replay harness
- **THEN** every existing field is found with the same name and meaning
