## ADDED Requirements

### Requirement: `decoder.crossCyclePrior` and `decoder.crossCyclePriorShadow` switch the template stage and its shadow null on, and an absent key reads off

The configuration SHALL provide the booleans `decoder.crossCyclePrior` and `decoder.crossCyclePriorShadow`. When a key is absent the value SHALL be `false`. With `decoder.crossCyclePrior` `false` the published rows of every cycle SHALL be identical to the decoder without this change, nothing SHALL be written to the prior store, no log line SHALL be written and no existing batch SHALL change. Both keys SHALL be read once per decode window and take effect on the next window, and SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset them); there is no Settings-page control. `decoder.crossCyclePriorShadow` SHALL have no effect while `decoder.crossCyclePrior` is `false`.

#### Scenario: The keys are absent

- **WHEN** the configuration has neither key
- **THEN** both effective values SHALL be `false`, the prior store SHALL stay empty, no `Cross-cycle prior:` line SHALL be written and no batch 6 SHALL be published

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys, or only one of the two
- **THEN** the key that is not in the post SHALL keep the value it had

#### Scenario: Entries that are not a staged cycle

- **WHEN** the setting is `true` and the decoder is called through the early decode or the single-batch entry
- **THEN** nothing SHALL be read from or written to the prior store and no line SHALL be written

### Requirement: The decoder keeps the messages it published in batches 1 to 5 for 90 seconds, and never a batch-6 message

While `decoder.crossCyclePrior` is `true`, on a staged cycle, the decoder SHALL keep per instance the messages published in batches 1 to 5 of each cycle (text, frequency, dt, batch) for the last 6 cycles (90 s, both parities), keyed by the cycle's 15 s slot. It SHALL clear the store when the band differs from the previous staged cycle's (a null band on both counting as no change). A prior SHALL count only when its slot is exactly 2, 4 or 6 slots (30, 60 or 90 s) before the current cycle's (live) or 1, 3 or 5 slots (shadow). A message published by the template stage (batch 6) SHALL NEVER be written to the store.

#### Scenario: A batch-6 message is not a prior

- **WHEN** a cycle publishes a message as batch 6
- **THEN** the store SHALL hold only what batches 1 to 5 published, and no later cycle SHALL find that message at the age of the batch-6 publish

#### Scenario: A missing cycle

- **WHEN** the cycle 30 s, 60 s or 90 s before the current one has no entry
- **THEN** no prior SHALL be offered at that age, and no older prior SHALL be offered in its place

#### Scenario: A band change

- **WHEN** the band of the current staged cycle differs from the previous staged cycle's
- **THEN** the store SHALL be emptied before the cycle's own messages are recorded

### Requirement: Priors are tested as known 79-tone templates on the fallback's residual, and detections are published as batch 6

After the last other batch of a staged cycle (batch 5 with the late round, else the fallback's batch), the decoder SHALL take the distinct texts the store holds at the live ages, nearest first, and exclude, counting each kind separately, the texts already published in batches 1 to 5 of the current cycle, the texts with a `<...>` hashed field and the texts the encoder refuses. On the buffer `CohFallbackAudioSelector.Select` hands the fallback and the late round it SHALL compute for each remaining text, as a 79-tone template, S_E = the mean over the 79 symbols of P[known tone] divided by the mean of P over the 8 bins (a symbol with no power counting 1), the powers coming from a baseband (mix at the carrier, 61-tap Hann-windowed-sinc low-pass at 900 Hz, decimation by 6) correlated per symbol over 320 samples at bins 0 to 7 with symbols outside the buffer zero-padded, over the prior's frequency +-3.0 Hz in 0.5 Hz steps and its start +-0.12 s in 0.01 s steps (start = dt + 0.48 s), keeping the maximum S_E* and its position. A template SHALL be detected when S_E* is at least T_E, a shipped constant that is `+infinity` until QA's training arm sets it (and that replay can set). Detections SHALL be mapped to decodes with the path tag 3, with the frequency of the maximum rounded to integer Hz, its dt and the coherent SNR at that position (the managed equivalent of the native `cf_snr_db`), de-duplicated by text against the cycle, and published as batch 6 through the fallback's batch hand-off only when non-empty. With no residual buffer the stage SHALL be skipped, counted and logged as `skipped-no-residual`. The buffer SHALL NOT be modified.

#### Scenario: A known message inside the window

- **WHEN** a message published 30 s earlier is present in the residual buffer within +-3 Hz and +-0.12 s of its prior's position, with S_E* at or above T_E
- **THEN** it SHALL be published in batch 6 with the path tag 3 and not appear in batches 1 to 5 of that cycle

#### Scenario: A known message outside the window

- **WHEN** the message is present further from the prior's position than the window
- **THEN** it SHALL NOT be detected

#### Scenario: T_E is the placeholder

- **WHEN** T_E is `+infinity`
- **THEN** no template SHALL be detected and no batch 6 SHALL be published, whatever the audio

#### Scenario: The managed detector equals the reference

- **WHEN** the detector is run on QA's fixture buffers
- **THEN** S_E* SHALL equal the reference's within 1e-3 relative and the position of the maximum SHALL be equal, for the found, centre, corner, wrong-message, noise-only and two outside-window cases

### Requirement: Templates run in parallel, nearest prior first, and stop starting at the cycle budget

The stage SHALL run the templates on up to `EffectiveSubtractionThreads` workers that claim them nearest prior first, and SHALL stop STARTING templates when the cycle's elapsed time reaches the 13 s cycle budget less the fallback's 250 ms publish reserve. Templates that were not started SHALL be counted as abandoned; templates that were started SHALL finish, and detections finished before the deadline SHALL be published.

#### Scenario: The budget is gone

- **WHEN** the cycle's budget is spent before the stage starts
- **THEN** no template SHALL start, every template SHALL be counted abandoned and nothing SHALL be published

#### Scenario: A short budget

- **WHEN** the budget runs out after k templates have started
- **THEN** exactly the k nearest priors SHALL have been tested

### Requirement: The shadow null tests the opposite-parity priors and publishes nothing

With `decoder.crossCyclePriorShadow` and `decoder.crossCyclePrior` both `true`, after the live batch is out the decoder SHALL run the same detector, window and threshold on the priors at the shadow ages (15, 45 and 75 s), with the same exclusions, against the same buffer. Shadow detections SHALL be counted and logged and SHALL NOT be published or stored.

#### Scenario: A shadow detection

- **WHEN** a message published 15 s earlier is present in this cycle's buffer at its prior's position
- **THEN** `shadowDetected` SHALL count it, no batch 6 SHALL carry it and the store SHALL NOT hold it

### Requirement: One counts-only log line per staged cycle and a numbers-only diagnostic sink

While `decoder.crossCyclePrior` is `true` the decoder SHALL write one Information line per staged cycle beginning `Cross-cycle prior:` with counts and numbers only: the outcome, the live and shadow prior counts, the excluded counts (already decoded, hashed, refused; live and shadow), the tested, detected, shadow-detected and abandoned counts, the published count, the threshold, the stage times and `batch6PublishMs`. It SHALL NOT contain message text or a callsign. An internal diagnostic sink, null by default, SHALL be called once per tested template, live and shadow, with numbers only: the kind, S_E*, the prior's age in cycles, the argmax's offsets from the prior's position in Hz and seconds, and the cycle's start stamp, and SHALL carry no text, callsign, payload or hash. A sink that throws SHALL NOT cost the cycle a decode.

#### Scenario: The line has no text

- **WHEN** the stage has run on a cycle whose priors are synthetic messages
- **THEN** the line SHALL contain none of their text, callsigns or fields, and every count SHALL be an integer

#### Scenario: A throwing sink

- **WHEN** the sink throws on every call
- **THEN** the cycle's batch 6 SHALL still be published

### Requirement: A template is detected only if its second data block matches (R15, T_P) and no decode of another text sits next to it (R14)

The template stage SHALL compute S_P, the template statistic restricted to frame symbols 43 to 71 (the mean of the same per-symbol ratios over those 29 symbols; a symbol with no power counts 1), from the same correlations at the S_E* argmax with no second search, and SHALL detect a template only when S_E* >= T_E and S_P >= T_P. T_P SHALL be a named constant with the placeholder value 0.0 in this build, settable for replay through an internal setter with a read-back. A template that clears T_E and fails T_P SHALL be counted as parity-rejected, live and shadow separately. A detection SHALL NOT be published when batches 1 to 5 of the same cycle hold a decode with a different text within 3.125 Hz and 0.2 s of the argmax, both in the product's own dt convention (the argmax converted back from WSJT-X's by the 0.6 s offset before the comparison); it SHALL be counted as vetoed-colocated, live and shadow separately. The veto SHALL be on by default and settable for replay through an internal setter with a read-back, and with it off the sink SHALL still say whether it would have vetoed. With both flags off nothing in this requirement SHALL run.

#### Scenario: The same station's next, different message

- **WHEN** the buffer holds the next message of the station whose previous message is the prior, at the prior's position, and T_P is 1.9
- **THEN** the old template SHALL clear T_E, fail T_P, be counted parity-rejected and not be published, and with T_P 0.0 it SHALL be published

#### Scenario: The same message repeated

- **WHEN** the buffer holds the same message at the prior's position and T_P is 1.9
- **THEN** it SHALL be published

#### Scenario: A different text beside the argmax

- **WHEN** a decode of batches 1 to 5 with a different text lies 0.19 s or 3.0 Hz from the argmax
- **THEN** the detection SHALL be vetoed and counted, and at 0.21 s or 3.2 Hz it SHALL NOT be

#### Scenario: The sink and the line

- **WHEN** a template is tested
- **THEN** the sink record SHALL carry S_P, the prior's frequency, dt and batch and the veto flag, and no text, and the log line SHALL carry the vetoed-colocated and parity-rejected counts, live and shadow, and no text

### Requirement: The QSO queues hold six batches a cycle, and PSK Reporter never uploads a template decode

With the coherent fallback ON, the answerer and caller queues (and the PSK Reporter queue) SHALL hold two cycles of six batches plus two spare, 14, and drop the OLDEST when full; with it OFF the capacity SHALL stay 8. A decode whose `Path` is the template path (3) SHALL NOT be uploaded to PSK Reporter: it SHALL be counted under the reason `template` in the window line, the datagram line and the status counters, after the AP rule and before the region rule, and the other consumers of the batch (the panel, ALL.TXT, the QSO services, external reporting) SHALL still receive it.

#### Scenario: Two cycles of six batches while a service is blocked

- **WHEN** two full cycles of six batches are queued and the service has not read
- **THEN** nothing SHALL be dropped, and a third cycle SHALL drop the oldest batches

#### Scenario: A mixed batch

- **WHEN** a batch holds one ordinary row and one template row
- **THEN** only the ordinary row SHALL be uploaded and the window line SHALL report `template=1`

### Requirement: A batch-6 template row never starts an exchange with a new station

The QSO answerer SHALL NOT answer a CQ, and the QSO caller SHALL NOT engage a station that answered its CQ, when the only row that would have done so is a template decode (`Path` = the template path); it SHALL log the late-batch outcome `ignored-template` and start nothing, immediate or deferred. The same message in any other batch SHALL behave as before, a template row SHALL still advance an exchange already in progress, and an operator-initiated engagement (an external Reply, an operator-selected responder) SHALL be unchanged.

#### Scenario: A CQ found only by the template stage

- **WHEN** the answerer is Idle with auto-answer on and a batch-6 batch holds a template CQ row
- **THEN** nothing SHALL be transmitted or held, the state SHALL stay Idle and the log SHALL carry `ignored-template`

#### Scenario: A mixed batch

- **WHEN** a batch-6 batch holds a template CQ and an ordinary CQ from another station
- **THEN** the answer SHALL go to the ordinary CQ
