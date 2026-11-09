## RENAMED Requirements

- FROM: `### Requirement: `decoder.lateSubtractionRound` switches the late round on, and an absent key reads off`
- TO: `### Requirement: `decoder.lateSubtractionRound` switches the late round, and an absent key reads on`

## MODIFIED Requirements

### Requirement: `decoder.lateSubtractionRound` switches the late round, and an absent key reads on

The configuration SHALL provide the boolean `decoder.lateSubtractionRound`. When the key is absent (or the `decoder` section is missing) the value SHALL be `true`; an explicit `false` SHALL turn the late round off, and every decode code path SHALL then be as it was before the setting existed. The key SHALL be read once per decode window and take effect on the next window. It SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset it); there is no Settings-page control.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.lateSubtractionRound`
- **THEN** the effective value SHALL be `true`, and the daemon's decoder SHALL read `true`

#### Scenario: An explicit false

- **WHEN** the configuration sets the key to `false`
- **THEN** the effective value SHALL be `false`, no `Late subtraction round:` line SHALL be written, no extra native decode SHALL run and batches 1 to 4 SHALL be equal to the build before the setting existed

#### Scenario: An explicit value

- **WHEN** the configuration sets the key to `true` or `false`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.lateSubtractionRound`
- **THEN** the key SHALL keep the value it had, including an explicit `false`
