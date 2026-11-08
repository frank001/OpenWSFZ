## ADDED Requirements

### Requirement: `decoder.coherentFallbackResidualCandidates` switches the residual-buffer candidate list on, and an absent key reads off

The configuration SHALL provide the boolean `decoder.coherentFallbackResidualCandidates`. When the key is absent the value SHALL be `false`, no extra candidate snapshot SHALL be taken and every decode code path SHALL be as it was before this change. The key SHALL be read once per decode window and take effect on the next window. It SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset it); there is no Settings-page control.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.coherentFallbackResidualCandidates`
- **THEN** the effective value SHALL be `false`, exactly one candidate snapshot SHALL be taken per cycle (pass 0's), both fallback runs SHALL read it and the coherent-fallback log line SHALL carry no `resCand` field

#### Scenario: An explicit value

- **WHEN** the configuration sets the key to `true` or `false`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.coherentFallbackResidualCandidates`
- **THEN** the key SHALL keep the value it had

### Requirement: The run that reads a residual buffer is given that buffer's own candidate snapshot

With the setting `true`, the coherent fallback on, Deep depth and the audio mode `Both` or `Residual`, the decoder SHALL copy the fallback's candidate snapshot immediately after the native decode of the residual pass's buffer and of the third pass's buffer, on the thread that ran that decode. The fallback run that reads the buffer `CohFallbackAudioSelector.Select` returns SHALL be given the snapshot of that same buffer. In `Both` mode the run that reads the original audio SHALL keep the original snapshot. No candidate lists SHALL be merged and the fallback's search window, gates and thresholds SHALL NOT change.

#### Scenario: The third pass's buffer is chosen

- **WHEN** the setting is `true`, the mode is `Both` and the third pass ran
- **THEN** the first fallback run SHALL read the third pass's buffer with the snapshot taken after that buffer's decode, the second run SHALL read the original audio with pass 0's snapshot, and the log line SHALL say `resCand=residual-R3`

#### Scenario: The residual pass's buffer is chosen

- **WHEN** the setting is `true`, the mode is `Both` and the third pass did not run but the residual pass fitted at least one signal
- **THEN** the first run SHALL read the residual pass's buffer with the snapshot taken after its decode and the log line SHALL say `resCand=residual-R2`

#### Scenario: Residual mode

- **WHEN** the setting is `true` and the mode is `Residual`
- **THEN** the single run SHALL read the chosen residual buffer with that buffer's snapshot

#### Scenario: Original mode

- **WHEN** the setting is `true` and the mode is `Original`
- **THEN** no extra snapshot SHALL be taken and the fallback SHALL behave as with the setting `false`

### Requirement: A missing snapshot never fails the cycle

When the snapshot of the chosen residual buffer is missing (the call returned nothing or failed), or no residual buffer exists, the run SHALL use the original snapshot, the cycle SHALL be counted and logged as `resCand=fallback-orig`, and neither the residual pass, the third pass nor the fallback SHALL lose their decodes or throw.

#### Scenario: The snapshot call fails

- **WHEN** the snapshot call after the residual pass's decode throws
- **THEN** the residual pass SHALL still return its decodes and the fallback SHALL not throw

#### Scenario: No residual snapshot

- **WHEN** the chosen buffer has no snapshot
- **THEN** every fallback run SHALL read the original snapshot and the log line SHALL say `resCand=fallback-orig`

### Requirement: Publication is unchanged and no text is published twice in a cycle

Rows from the fallback SHALL go through the same merge, selector and per-cycle text de-duplication as before this change.

#### Scenario: A fallback row repeats a text of batch 1

- **WHEN** a fallback run finds a payload whose text batch 1 already published in the same cycle
- **THEN** that text SHALL NOT be published again

### Requirement: The coherent-fallback log line reports the candidate lists while the setting is effective

While the setting is effective (`true`, fallback on, a staged Deep cycle, mode not `Original`) the `Coherent fallback:` line SHALL end with `resCand={residual-R2|residual-R3|fallback-orig}`, `resEligible` (the eligible candidates in the snapshot the residual-side run used) and `origEligible` (those in the original snapshot), aggregates only. When the setting is not effective the line SHALL be as before this change.

#### Scenario: The original run was never started

- **WHEN** the shared budget is spent after the first run
- **THEN** `origEligible` SHALL be the eligible count of the original snapshot and `abandoned` SHALL count that many abandoned candidates for the run not started
