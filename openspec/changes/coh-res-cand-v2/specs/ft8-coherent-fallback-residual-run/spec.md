## ADDED Requirements

### Requirement: `decoder.coherentFallbackResidualCandidates` switches the third fallback run on, and an absent key reads off

The configuration SHALL provide the boolean `decoder.coherentFallbackResidualCandidates`. When the key is absent the value SHALL be `false`, no extra candidate snapshot SHALL be taken, no third fallback run SHALL be made, and every decode code path and the coherent-fallback log line SHALL be as they were before this change. The key SHALL be read once per decode window and take effect on the next window. It SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset it); there is no Settings-page control. It SHALL act only with the coherent fallback on, Deep depth and the audio mode `Both`.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.coherentFallbackResidualCandidates`
- **THEN** the effective value SHALL be `false`, exactly one candidate snapshot SHALL be taken per cycle (pass 0's), exactly two fallback runs SHALL be made, both reading it, and the coherent-fallback log line SHALL carry no `resRun` field

#### Scenario: An explicit value

- **WHEN** the configuration sets the key to `true` or `false`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.coherentFallbackResidualCandidates`
- **THEN** the key SHALL keep the value it had

#### Scenario: Original and Residual modes

- **WHEN** the setting is `true` and the audio mode is `Original` or `Residual`
- **THEN** no extra snapshot SHALL be taken, no third run SHALL be made and the log line SHALL carry no `resRun` field

### Requirement: A third, last fallback run reads the residual audio with the residual buffer's own candidate snapshot

With the setting `true`, the coherent fallback on, Deep depth, the audio mode `Both` and a residual buffer (the buffer `CohFallbackAudioSelector.Select` returns, the third pass's else the residual pass's), the decoder SHALL copy the fallback's candidate snapshot immediately after the native decode of that buffer, on the thread that ran it. The two fallback runs that exist without this setting (the residual audio, then the original audio, both with pass 0's snapshot, on the shared budget) SHALL be unchanged. After them a THIRD run SHALL read the same residual audio with the snapshot of that buffer's own decode, on what is left of the shared budget. It SHALL NOT be started when nothing is left (`resRun=skipped-budget`) or when that snapshot is missing (`resRun=no-snapshot`), and neither case SHALL fail the cycle. Without a residual buffer it SHALL NOT run (`resRun=no-residual`).

#### Scenario: The third pass's buffer is chosen

- **WHEN** the setting is `true`, the mode is `Both` and the third pass ran
- **THEN** the first two runs SHALL receive pass 0's snapshot, the third run SHALL read the third pass's buffer with the snapshot taken after that buffer's decode, and the log line SHALL say `resRun=ran` and `resCand=residual-R3`

#### Scenario: The residual pass's buffer is chosen

- **WHEN** the setting is `true`, the mode is `Both` and the third pass did not run but the residual pass fitted at least one signal
- **THEN** the third run SHALL read the residual pass's buffer with the snapshot taken after its decode and the log line SHALL say `resCand=residual-R2`

#### Scenario: No snapshot, or no budget

- **WHEN** the chosen buffer's snapshot is missing, or the budget is spent after the second run
- **THEN** the third run SHALL NOT be started, the cycle SHALL publish exactly what the first two runs produce, and the log line SHALL say `resRun=no-snapshot` or `resRun=skipped-budget`

### Requirement: The third run's new-text rows are gated at 1097 Hz and R-F4 never ungates them

A row of the third run SHALL be considered for publication only when its F1b gate passed (state `NewGated`); a row above T1 SHALL NOT be published whatever `decoder.coherentFallbackResidualUngated` says, and the third run's rows SHALL NOT enter the merge that applies that setting. A row whose text is not already published in the cycle (batches 1 to 3, or the first two runs) SHALL be kept only when its published integer frequency, in Hz, is at most 1097; otherwise it SHALL be dropped and counted. The comparison SHALL be on the integer the row is published with. Kept rows SHALL join batch 4 after the first two runs' rows, through the per-cycle text de-duplication, so no text is published twice in a cycle and no row of the first two runs is displaced.

#### Scenario: The gate boundary

- **WHEN** a new-text row of the third run is published at 1097 Hz, and another at 1098 Hz
- **THEN** the first SHALL be published and the second SHALL be dropped and counted in `resNewGated`

#### Scenario: R-F4 is on

- **WHEN** `decoder.coherentFallbackResidualUngated` is `true` and the third run has a row above T1 (state `GatedOut`)
- **THEN** that row SHALL NOT be published, while the same setting still admits the first residual run's `GatedOut` rows

#### Scenario: A text already published

- **WHEN** the third run re-finds a text published in batches 1 to 3 or by the first two runs
- **THEN** it SHALL NOT be published again, SHALL NOT be counted in `resNew`, and SHALL NOT be gated

### Requirement: The coherent-fallback log line carries the third run's aggregates

While the setting is effective, the `Coherent fallback:` line SHALL end with `resRun`, `resCand`, `resEligible`, `resNew` (new-text rows before the gate), `resNewGated`, `resNewKept` and `resWallMs`; with the setting off it SHALL be byte-identical to the line before this change. Aggregates only: no message text and no callsign.

#### Scenario: The fields are present only while effective

- **WHEN** the setting is `true` in `Both` mode
- **THEN** the line SHALL carry the seven fields; **WHEN** it is `false`, they SHALL be absent
