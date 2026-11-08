# ft8-late-subtraction Specification

## Purpose
Defines the late subtract-and-decode round (LATE-SUB L1'): behind `decoder.lateSubtractionRound` (default OFF), after the coherent fallback a further subtraction round runs on the fallback's audio and publishes any new decodes as batch 5. With the setting OFF the decode path is unchanged. Added by change `late-sub-round` (v0.68, FR-102; accepted on the third night, 2026-10-31).
## Requirements
### Requirement: `decoder.lateSubtractionRound` switches the late round on, and an absent key reads off

The configuration SHALL provide the boolean `decoder.lateSubtractionRound`. When the key is absent the value SHALL be `false` and every decode code path SHALL be as it was before this change. The key SHALL be read once per decode window and take effect on the next window. It SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset it); there is no Settings-page control.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.lateSubtractionRound`
- **THEN** the effective value SHALL be `false`, no `Late subtraction round:` line SHALL be written, no extra native decode SHALL run and batches 1 to 4 SHALL be equal to the build before this change

#### Scenario: An explicit value

- **WHEN** the configuration sets the key to `true` or `false`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.lateSubtractionRound`
- **THEN** the key SHALL keep the value it had

### Requirement: The late round runs only on Deep, after the fallback ran, on a residual buffer

With the setting `true`, one late subtraction round SHALL run in a cycle only when all of these hold: the decoding depth is Deep; the coherent fallback ran in this cycle (whether or not it published anything); pass 0 decoded at least one message; and `CohFallbackAudioSelector.Select`, called as the fallback calls it, returns a residual buffer (the third pass's buffer, else the residual pass's buffer). When any condition fails the round SHALL be skipped, counted, and logged with the reason, and no extra native decode SHALL run.

#### Scenario: Normal depth

- **WHEN** the setting is `true` and the depth is Normal
- **THEN** no round SHALL run and the log line SHALL say `outcome=skipped-normal-depth`

#### Scenario: The fallback did not run

- **WHEN** the setting is `true`, the depth is Deep and the coherent fallback is off
- **THEN** no round SHALL run and the log line SHALL say `outcome=skipped-fallback-not-run`

#### Scenario: Pass 0 decoded nothing

- **WHEN** the setting is `true` and pass 0 decoded nothing
- **THEN** no round SHALL run and the log line SHALL say `outcome=skipped-nothing-decoded`

#### Scenario: Select returns the original audio

- **WHEN** the setting is `true` and `Select` returns the original audio (the audio mode is `Original`, or the residual pass was abandoned or failed, or nothing was fitted)
- **THEN** no round SHALL run and the log line SHALL say `outcome=skipped-no-residual`

#### Scenario: The residual buffer is the third pass's or the residual pass's

- **WHEN** the setting is `true` and `Select` returns the third pass's buffer, or the residual pass's buffer because the third pass did not run
- **THEN** the round SHALL read that buffer and the log line SHALL say `buffer=R3` or `buffer=R2`

### Requirement: The round subtracts the signals behind the published batch 3 and batch 4 decodes, from a buffer it does not modify

The round SHALL call `SubtractionPass.RunThirdPassAsync` once, on the buffer `Select` returned, with the primary decoder only (no coherent fallback on the new buffer). The signals to fit SHALL be the natives behind the decodes the per-message mapping published in batches 3 and 4: the first occurrence of each text in the cycle, not already published, and plausible, with `FreqHz` as the native's own (rounded for a fallback native) and `Dt` unrounded. The known set SHALL be the natives of batch 1 and the raw natives of batch 2; those are not re-fitted. A fit entry the encoder cannot re-encode SHALL be skipped as in the third pass and counted in the log line. The buffer the fallback was handed SHALL NOT be modified.

#### Scenario: The fit list is the published batch 3 and batch 4

- **WHEN** batch 3 published one decode and batch 4 published one decode
- **THEN** exactly those two signals SHALL be fitted, with the batch-4 signal's `Dt` equal to the fallback's unrounded `OutDtS`, and the batch-1 and batch-2 signals SHALL NOT be fitted

#### Scenario: A text the mapping did not publish is not fitted

- **WHEN** a batch-3 native repeats a batch-1 text, or is implausible, or a batch-4 native repeats a batch-3 text or is implausible
- **THEN** that native SHALL NOT be in the fit list

#### Scenario: A fit entry that cannot be re-encoded

- **WHEN** one fit entry cannot be re-encoded
- **THEN** it SHALL be skipped, the others SHALL be fitted, and the log line SHALL show `refused=1`

#### Scenario: The input buffer is not modified

- **WHEN** the round has run
- **THEN** the array the fallback was handed SHALL hold the values it held before the round

### Requirement: The round obeys the cycle's budget and is all-or-nothing

The round SHALL be given what remains of the cycle's 13 s budget, measured from the start of the decode, and SHALL obey the pass's own deadline and reserve logic. No new budget constant SHALL be introduced. An abandoned round, and a round that fails with a contained exception, SHALL publish nothing, SHALL NOT throw, and SHALL NOT affect batches 1 to 4, which have already been handed off.

#### Scenario: The round is abandoned on the budget

- **WHEN** the pass reports the deadline exceeded
- **THEN** no batch 5 SHALL be handed off, the log line SHALL say `outcome=abandoned` and `published=0`, and the abandoned counter SHALL increase by one

#### Scenario: The round fails

- **WHEN** the pass fails with a contained exception
- **THEN** no batch 5 SHALL be handed off, the log line SHALL say `outcome=failed`, and the failed counter SHALL increase by one

#### Scenario: Nothing to fit

- **WHEN** the fit list is empty, or nothing in it can be re-encoded
- **THEN** the round SHALL publish nothing and the log line SHALL say `outcome=no-new`

### Requirement: New decodes are published as batch 5, after the fallback's batch, and the round is the cycle's last hash-table access

New decodes of the round SHALL be mapped like any other decode (the same per-cycle text de-duplication, plausibility filter and region and worked-before bycatch, residual provenance) and handed off as batch 5 through the batch hand-off the fallback uses, only when non-empty, and only after the fallback's own batch has been handed off. The batch hand-off SHALL accept the number 5 without a new callback. The round's native decode SHALL start after the fallback's text unpack, and SHALL be the last hash-table access of the cycle, under the decode gate. A batch 5 SHALL reach the decode panel, `ALL.TXT`, decode-filter admission and external reporting as any supplementary batch does, and the QSO services SHALL treat it as heard and never as a cycle.

#### Scenario: A round with new decodes

- **WHEN** the round decodes one message that no earlier batch of the cycle published
- **THEN** batch 5 SHALL be handed off with that message after batch 4, and batches 1 to 4 SHALL be unchanged

#### Scenario: A round with no new decode

- **WHEN** the round decodes only messages already published in the cycle
- **THEN** no batch 5 SHALL be handed off

#### Scenario: The native order

- **WHEN** a cycle runs the fallback, publishes batch 4 and runs the round
- **THEN** the recorded order SHALL be the fallback's unpack, batch 4's hand-off, the round's native decode, batch 5's hand-off

#### Scenario: The consumers

- **WHEN** the pump receives batch number 5
- **THEN** the panel, `ALL.TXT`, filter admission, the answerer, the caller and external reporting SHALL receive it, numbered 5, and the cycle-audio archive SHALL still run once for the cycle

### Requirement: One log line per Deep cycle while the setting is on

While the setting is `true`, each Deep cycle SHALL write one Information line `Late subtraction round: outcome=<outcome>, buffer=<R3|R2|->, fit=<n>, refused=<n>, new=<n>, published=<n>, fbEndMs=<ms>, startMs=<ms>, elapsedMs=<ms>, endMs=<ms>, batch=5, batch5PublishMs=<ms|-1>.` with `<outcome>` one of `ran`, `no-new`, `abandoned`, `failed`, `skipped-normal-depth`, `skipped-fallback-not-run`, `skipped-nothing-decoded`, `skipped-no-residual`. The times SHALL be milliseconds on the decode's own clock (the clock of `fbStartMs`). `batch5PublishMs` SHALL be `-1` when nothing was handed off. The line SHALL carry aggregates only and no message text.

#### Scenario: A round that ran

- **WHEN** the round ran and published one decode
- **THEN** exactly one such line SHALL be written, with `outcome=ran`, `new=1`, `published=1`, and `startMs`, `elapsedMs` and `endMs` satisfying `endMs - startMs = elapsedMs` on the decode's clock

#### Scenario: The setting is off

- **WHEN** the setting is `false`
- **THEN** no such line SHALL be written

