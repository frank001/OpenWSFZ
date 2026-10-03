## ADDED Requirements

### Requirement: An early decode SHALL start when the window being filled holds the configured cut before its end

When `decoder.earlyDecodeEnabled` is true, the daemon SHALL start an early decode of the window being filled when it first holds `180 000 - round(12 000 x decoder.earlyDecodeCutSeconds)` samples (156 000 at the default cut of 2.0 s), and SHALL decode a **copy** of exactly that many samples, zero-filled to 180 000. Capture SHALL continue into the original window, untouched. The flag and the cut SHALL be read once per window, at the point the window's dial frequency is snapshotted. An early window that cannot be queued SHALL be dropped and counted as skipped, never queued behind another.

#### Scenario: The cut is reached

- **WHEN** a window with the default cut has stored 156 000 samples and the flag is on
- **THEN** exactly one early window of 156 000 samples followed by 24 000 zeros is produced for that cycle, and the original window keeps filling

#### Scenario: A chunk overshoots the trigger

- **WHEN** the chunk that carries the window past 156 000 stored samples ends at 157 500
- **THEN** the early window still holds exactly 156 000 samples of audio followed by zeros

#### Scenario: One early window per cycle

- **WHEN** a window is emitted and the next one starts filling
- **THEN** the early trigger is armed again, and each cycle produces at most one early window

### Requirement: An early decode SHALL never delay or queue behind the ordinary decode

If the decoder is busy when the early window arrives (for example the previous cycle's residual pass), the early decode SHALL be skipped for that cycle, never queued. The skip SHALL be counted and logged per cycle. The ordinary decode at the slot end SHALL never be delayed by an early decode that has not started. If an early decode is still running when the window closes, the ordinary decode SHALL wait for it, and that wait SHALL be measured and logged.

#### Scenario: Decoder busy at the trigger

- **WHEN** the early window arrives while an ordinary decode or its residual pass is running
- **THEN** no early decode starts for that cycle, the cycle's log line reports `skipped=1`, and the ordinary decode of the running cycle is not slowed

#### Scenario: Early decode still running at the slot end

- **WHEN** the window closes while an early decode is running
- **THEN** the ordinary decode starts after it finishes, and the log line reports the wait in `finalWaitMs`

### Requirement: The early decode SHALL be a pass-0 decode whatever the subtraction setting is

The early decode SHALL run pass 0 only. It SHALL NOT read `decoder.subtractionEnabled`, SHALL NOT start the residual pass, and SHALL NOT change any state of the decoder instance that an ordinary decode reads.

#### Scenario: Subtraction is on

- **WHEN** `decoder.subtractionEnabled` is true and an early decode runs
- **THEN** no residual pass runs for the early window and the early decode takes about as long as a single-pass decode

### Requirement: An early decode SHALL be skipped when the dial frequency changed during capture

The early decode SHALL apply the decode pump's dial-frequency rule: if the live dial frequency differs from the window's snapshot, the early decode SHALL be skipped and counted.

#### Scenario: Band change mid-window

- **WHEN** the operator changes band after the window opened and before the early window arrives
- **THEN** no early decode runs for that cycle and no early row is shown

### Requirement: The early batch SHALL reach the decode panel only

The early batch SHALL be delivered to the decode panel, marked as early, and to nothing else. ALL.TXT, external reporting, the QSO answerer, the QSO caller, the cycle-audio archive and decode-filter admission SHALL receive nothing from the early batch; their behaviour SHALL be as it would be without the feature.

#### Scenario: An early decode finds a row

- **WHEN** an early decode returns a row
- **THEN** the panel shows it marked early, and no line is appended to ALL.TXT, no datagram is sent, no batch is written to the QSO channels, no archive entry is enqueued and no filter value is admitted because of it

### Requirement: The early batch SHALL pass the same visibility filter as the final batch

The early batch SHALL be filtered by the same decode-noise-suppression rules as batch 1, so that a row the operator has chosen to hide is not shown early.

#### Scenario: A suppressed row

- **WHEN** a row would be hidden from batch 1 by the noise-suppression setting
- **THEN** its early copy is not shown either

### Requirement: The final decode SHALL be unaffected by the early decode

For every cycle, the outcome of the ordinary decode SHALL be what it would be without the early decode. The build SHALL guarantee this by saving the process-global callsign-hash state before the early decode and restoring it after, so that the state the ordinary decode sees is the state it would have seen without the early decode. The restore SHALL run when the early decode fails or throws.

#### Scenario: An early-only callsign

- **WHEN** an early decode inserts a callsign that the final decode does not produce
- **THEN** that callsign is not in the hash table when the final decode runs, and the final decode's numeric outcome equals that of the same build with the feature off

#### Scenario: The early decode fails

- **WHEN** the early decode raises an exception or a contained native fault
- **THEN** the hash state is restored before the ordinary decode and the cycle's ordinary decode proceeds

### Requirement: A final row SHALL confirm a matching early row, and an unmatched early row SHALL stay marked

Within a cycle, a final row SHALL be matched to an early row by identical message text and a frequency difference of at most 10 Hz, one-to-one, deterministically. A matched early row SHALL be replaced in place by the final row, with the early mark removed and no duplicate row. An unmatched final row SHALL be added as today. An unmatched early row SHALL stay on the panel marked *unconfirmed*. The marks SHALL be exposed to keyboard and screen-reader users as text, not by colour alone. The confirmation and the final rows SHALL reach the panel in one frame.

#### Scenario: Confirmation

- **WHEN** batch 1 contains a row with the same text as an early row and a frequency within 10 Hz
- **THEN** the panel shows one row for it, in the early row's position, without the early mark

#### Scenario: Unconfirmed

- **WHEN** no final row matches an early row
- **THEN** the early row stays, marked unconfirmed, including when batch 1 is empty

#### Scenario: Two candidates

- **WHEN** two early rows could match one final row
- **THEN** the one with the smaller frequency difference is matched (ties: the earlier early row), and the other stays unconfirmed

### Requirement: The early decode SHALL be configurable and OFF by default

`decoder.earlyDecodeEnabled` SHALL default to false and `decoder.earlyDecodeCutSeconds` to 2.0, with an accepted range of 0.5 to 3.0 (out-of-range values clamped by the server). A configuration update that does not mention either field SHALL leave both as they were.

#### Scenario: Partial update

- **WHEN** a configuration POST changes only another decoder setting
- **THEN** both early-decode fields keep their stored values

#### Scenario: Out of range

- **WHEN** the cut is set to 5.0
- **THEN** the stored value is clamped to 3.0

### Requirement: Each cycle with the feature on SHALL write one aggregate log line

Each cycle SHALL write one file-log line, stamped to the millisecond, of the form `Early decode: n=<rows>, elapsedMs=<ms>, skipped=<0|1>, finalWaitMs=<ms>`. The line SHALL contain no message text.

#### Scenario: A skipped cycle

- **WHEN** the early decode is skipped
- **THEN** the line reads `n=0` and `skipped=1`

### Requirement: With the feature off, nothing SHALL change

With `decoder.earlyDecodeEnabled` false, the window producer, the decode pump, the panel events, ALL.TXT, external reporting, the QSO services and the archive SHALL make the same calls in the same order as before the feature existed, and no new WebSocket frame SHALL be sent.

#### Scenario: Characterisation

- **WHEN** a fixed set of recorded cycles is run with the flag off
- **THEN** the panel events, ALL.TXT lines, UDP datagrams and QSO-channel batches equal those of the pre-change build

#### Scenario: Flag on, other outputs

- **WHEN** the same cycles are run with the flag on
- **THEN** the ALL.TXT lines, UDP datagrams, QSO-channel batches and archive entries equal the flag-off run, and only the panel frames differ
