## ADDED Requirements

### Requirement: `decoder.coherentFallbackResidualUngated` switches the F1b gate off for the residual-audio run, and an absent key reads off

The configuration SHALL provide the boolean `decoder.coherentFallbackResidualUngated`. When the key is absent the value SHALL be `false` and the fallback SHALL behave exactly as it did before this change. The key SHALL be read once per decode window and take effect on the next window. It SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset it); there is no Settings-page control. It acts only when `decoder.coherentFallbackAudio` is `Both`.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.coherentFallbackResidualUngated`
- **THEN** the effective value SHALL be `false` and the published fallback batch SHALL be equal to the build before this change

#### Scenario: An explicit value

- **WHEN** the configuration sets the key to `true` or `false`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.coherentFallbackResidualUngated`
- **THEN** the key SHALL keep the value it had

#### Scenario: The audio mode is not Both

- **WHEN** the key is `true` and `decoder.coherentFallbackAudio` is `Original` or `Residual`
- **THEN** the fallback SHALL behave exactly as it does with the key `false`

### Requirement: In Both mode a GatedOut row of the residual-audio run is treated as a gated-in row from the merge onwards

With the setting `true` and `decoder.coherentFallbackAudio` = `Both`, a fallback row whose state is `GatedOut` (CRC-valid, a new payload, F1b above T1) and which comes from the run that read the residual audio SHALL enter the merge, `CoherentFallbackSelector.Select`, the text unpack, the per-cycle text de-duplication and `IsPlausibleMessage` exactly as a `NewGated` row does. A `GatedOut` row of the run that read the original audio SHALL NOT be admitted, and the original run keeps T1 unchanged. The admitted row SHALL keep its true state for diagnostics and SHALL NOT be relabelled `NewGated` in any counter or log. The native code and T1 SHALL be unchanged.

#### Scenario: A residual-run GatedOut row is published

- **WHEN** the setting is `true`, the mode is `Both`, and the residual run has a CRC-valid new-payload row with F1b above T1 that passes de-duplication and plausibility
- **THEN** its message SHALL be published in the fallback batch with the residual row's frequency, dt and SNR

#### Scenario: An original-run GatedOut row is not published

- **WHEN** the setting is `true`, the mode is `Both`, and only the original run has a `GatedOut` row for a payload
- **THEN** that payload SHALL NOT be published

#### Scenario: An admitted residual row displaces a same-payload original row

- **WHEN** the setting is `true`, a residual-run `GatedOut` row and an original-run `NewGated` row carry the same payload
- **THEN** exactly one message SHALL be published for it, from the residual row, and the original row SHALL be dropped by the merge

#### Scenario: The edge rule applies across mixed states

- **WHEN** the setting is `true` and two admitted rows carry the same payload, the first at a window edge and the second not
- **THEN** the non-edge row SHALL be the one published

#### Scenario: The original run was not started for budget reasons

- **WHEN** the setting is `true`, the residual run completed and the second run was not started because no budget was left
- **THEN** the residual run's `GatedOut` rows SHALL still be admitted and published, and the abandoned count of the second run SHALL be unchanged

#### Scenario: Only an original-audio run exists

- **WHEN** the setting is `true`, the mode is `Both` and no usable residual buffer exists, so the fallback runs once on the original audio
- **THEN** no `GatedOut` row SHALL be admitted

#### Scenario: The setting is off

- **WHEN** the setting is `false`
- **THEN** no `GatedOut` row SHALL be admitted in any mode, and the published fallback batch SHALL be equal to the build before this change

### Requirement: The fallback log line counts the admitted rows

With the setting `true`, the `Coherent fallback:` log line SHALL gain `ungated=N`, the number of published fallback messages that came from admitted `GatedOut` rows; the field SHALL NOT be printed when the setting is `false`. The counters `fromOriginal`, `fromResidual` and `inBoth` SHALL count admitted residual rows as found by the residual run. The `Gated` statistic SHALL keep its meaning (rows at or below T1).

#### Scenario: The setting is on and rows were admitted

- **WHEN** the setting is `true` and two admitted `GatedOut` rows are published in a cycle
- **THEN** the line SHALL contain `ungated=2` and `fromResidual` SHALL include those two payloads

#### Scenario: The setting is off

- **WHEN** the setting is `false`
- **THEN** the line SHALL NOT contain `ungated=` and its other fields SHALL be as before this change
