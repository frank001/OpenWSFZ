## ADDED Requirements

### Requirement: The audio the coherent fallback reads is chosen by `decoder.coherentFallbackAudio`, and an absent key reads `Both`

The configuration SHALL provide `decoder.coherentFallbackAudio`, one of `Original`, `Residual`, `Both` (JSON as the enum name, case-insensitive on read).
When the key is absent the value SHALL be `Both` (Captain, 2026-10-28); an explicit value SHALL be kept. The value SHALL be read once per decode window and take
effect on the next window. The key SHALL be settable through the configuration file and the configuration API; there is no Settings-page control.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.coherentFallbackAudio`
- **THEN** the effective value SHALL be `Both`

#### Scenario: An explicit value

- **WHEN** the configuration sets `Original`, `Residual` or `Both`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.coherentFallbackAudio`
- **THEN** the key SHALL keep the value it had

### Requirement: Each mode reads a defined audio

`Original` SHALL give the fallback the cycle's normalised audio exactly as before this change. `Residual` SHALL give it the step-down residual buffer: the third
pass's buffer if the third pass ran, else the residual pass's buffer if that completed, else the original audio. `Both` SHALL run the fallback on the residual
buffer, then on the original audio, on one candidate snapshot, and SHALL merge the two result sets by payload before publication, keeping the residual row where
both runs found the same payload; where no residual buffer is usable it SHALL run the original audio once.

#### Scenario: Original

- **WHEN** the mode is `Original`
- **THEN** the fallback SHALL receive the same audio reference as the first passes and its output SHALL equal the build before this change

#### Scenario: Both finds the same payload twice

- **WHEN** the mode is `Both` and both runs return the same payload
- **THEN** exactly one row SHALL be published for it and it SHALL be the residual row

#### Scenario: Both with no usable residual buffer

- **WHEN** the mode is `Both` and no residual buffer is available
- **THEN** the fallback SHALL run once, on the original audio

### Requirement: `Both` shares one time budget, and a spent budget loses the second run, not the cycle

`Both` SHALL run both fallbacks within the single budget that applies to the fallback (the cycle budget less the publish reserve). The second run SHALL receive
the time left of that budget. If nothing is left (`leftMs <= 0`) the second run SHALL NOT start and its eligible candidates SHALL be counted as abandoned, and the
first run's results SHALL still be published. If something is left but less than one run needs, the second run SHALL stop claiming candidates at its budget.

#### Scenario: The budget is spent when the second run is due (N-1 a)

- **WHEN** the mode is `Both` and `leftMs <= 0` when the second run is due
- **THEN** the second run SHALL NOT start, its eligible candidates SHALL be counted abandoned, and the first run's results SHALL publish

#### Scenario: The budget is nearly spent (N-1 b)

- **WHEN** the mode is `Both` and `0 < leftMs` is less than one run's wall time
- **THEN** the second run SHALL stop claiming candidates at its budget, and the fallback SHALL end within the cycle budget less the publish reserve, allowing for the candidate in flight when the budget is reached

### Requirement: The fallback's log line states the audio and the merge

The `Coherent fallback:` log line SHALL end with `audio=` and the mode's label: `original`, `residual3`, `residual2` or `residual-unavailable`; in `Both`,
`both(<level>)` with `<level>` one of `residual3`, `residual2`, `unavailable`, followed by `fromOriginal=N, fromResidual=N, inBoth=N` (payload counts after the merge).
