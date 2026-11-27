## ADDED Requirements

### Requirement: `decoder.engine` selects the classic or the lean decoder, and an absent or unknown value reads classic

The configuration SHALL provide the string `decoder.engine`, with the values `classic` and `lean`. When the key is absent, when the `decoder` section is missing, and when the value is anything other than the word `lean` (case and surrounding white space ignored), the effective engine SHALL be `classic`. The value SHALL be kept as written on a load and an unrelated save. It SHALL be set through the configuration file and the API only (no Settings-page control); the configuration POST SHALL be an overlay, so a body without the key leaves it as it was. It SHALL be read once per window and take effect on the next window. With `classic`, every native call, published row, batch, counter, log line and `DecodeResult.Path` value SHALL be exactly as in the build before the key existed.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.engine`
- **THEN** the effective engine SHALL be `classic` and the lean native call SHALL never be made

#### Scenario: An unknown value

- **WHEN** `decoder.engine` is `turbo` or an empty string
- **THEN** the effective engine SHALL be `classic`, and the stored value SHALL stay as written after an unrelated save

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys
- **THEN** `decoder.engine` SHALL keep the value it had

### Requirement: `decoder.threads` sets the lean engine's worker count

The configuration SHALL provide the integer `decoder.threads`, default 0 meaning automatic, no effect while the engine is `classic`. An absent key and 0 SHALL resolve, where the setting is applied, to the smaller of the daemon host's logical processor count and 16, at least 1; a value 1 to 16 SHALL be explicit and respected; a negative value SHALL be clamped to 1 and a value above 16 to 16, never to automatic. The lean engine's output SHALL NOT depend on it.

#### Scenario: Out of range

- **WHEN** `decoder.threads` is -5 or 99
- **THEN** the lean engine SHALL use 1 or 16 respectively

#### Scenario: Automatic

- **WHEN** `decoder.threads` is absent or 0 on a host with 64 logical processors
- **THEN** the lean engine SHALL use 16, and on a host with 4 it SHALL use 4

### Requirement: With engine `lean` a cycle makes one native call and does not enter the classic decoder

With `decoder.engine` effective as `lean`, a cycle SHALL be decoded by one call of `ftz_decode_cycle` per window: the spectrogram (the primary pass's configuration), the candidates (`ftx_find_candidates` with the primary pass's parameters: minimum score 10, at most 140), tier A on every candidate (magnitude likelihoods, belief propagation, CRC-14, unpack), and, from step 2b, tier B on every candidate that failed tier A and is not a duplicate position, and CQ-AP on every candidate that failed both: nothing else, no OSD, no subtraction. The classic decoder, its native calls and its batches SHALL NOT be entered. The input SHALL be conditioned as the primary pass conditions it, and the results SHALL pass the same per-cycle text de-duplication, plausibility filter, region and worked-before steps as every classic batch. The results SHALL be published as one batch, the cycle's batch 1, through the existing publish path. The early decode SHALL return nothing under `lean`.

#### Scenario: Equality with the classic primary pass

- **WHEN** the committed synthetic fixtures `synth-qso-01` to `synth-qso-03` are decoded by the lean engine and by the classic decoder's primary pass with CQ-AP and OSD off
- **THEN** the sets of decoded message texts SHALL be equal

#### Scenario: The classic path is not entered

- **WHEN** a cycle runs with engine `lean`
- **THEN** exactly one lean native call SHALL be made and no classic native decode call or getter SHALL be made

### Requirement: The lean engine's output is deterministic and independent of the thread count

Candidates SHALL be processed in parallel by the configured number of workers of a fixed pool created once, but the decoded results SHALL be sorted by frequency, then time, then payload before anything touches the callsign table or leaves the call. Two runs on the same audio and the same starting callsign-table state SHALL give byte-identical output, and so SHALL runs at 1, 2, 4 and 8 threads.

#### Scenario: Thread counts

- **WHEN** the same audio is decoded from the same hash state at 1, 2 and 4 threads, and again at 2 and 1
- **THEN** every output SHALL be byte-identical

### Requirement: A native failure never stops the daemon

Every buffer index in the lean native code SHALL be bounds-checked. A native error SHALL be returned as a code (`-1` argument, `-2` allocation, `-3` access violation caught, `-4` audio that is not decodable: NaN, infinity or a sample beyond 1e6), never raised. The managed layer SHALL log a code, publish the results the call had already written, and run the next cycle; an exception around the call SHALL be logged and yield no results for that cycle only. The lean native code SHALL be built and run under AddressSanitizer and UndefinedBehaviorSanitizer on Linux in CI, with at least 10,000 fuzz runs on random, clipped, silent and DC audio and truncated buffers, without a crash or a sanitizer report.

#### Scenario: A native error code

- **WHEN** the native call returns an error code with some results written
- **THEN** a warning carrying the code SHALL be logged, those results SHALL be published, and the next cycle SHALL be decoded normally

### Requirement: One counts-only log line per lean cycle

Each lean cycle SHALL write one Information line carrying counts and times only: candidates, tier-A decodes, results, threads, the abandoned flag, the error code, and per stage (spectrogram, candidates, tier A, unpack, total) the wall and CPU milliseconds. No line SHALL carry a message text or a callsign.

#### Scenario: Text never reaches a log line

- **WHEN** a lean cycle decodes messages
- **THEN** no log line of the cycle SHALL contain any decoded text or callsign

### Requirement: `FT8_SHIM_VERSION` 20260073 adds `ftz_decode_cycle` and `ftz_shutdown` and changes nothing else

The native shim version SHALL be 20260073; the new exports are `ftz_decode_cycle` and `ftz_shutdown`; `FT8Result` SHALL stay 48 bytes and every existing export and decode outcome SHALL be unchanged.

#### Scenario: Classic is unchanged

- **WHEN** the decoder runs with the key absent
- **THEN** the recorded native calls, batches and log lines SHALL equal those recorded on the build before this change

### Requirement: Tier B publishes a row only when it is CRC-valid, new and gated, one row per payload

For every candidate that failed tier A and is not a duplicate position (an earlier undecoded candidate at the same frequency and time), tier B SHALL run the coherent fallback's per-candidate body on a coherent context owned by one worker (fine sync, coherent likelihoods with the multi-set walk on, belief propagation, CRC). A row SHALL be published if and only if it is CRC-valid, its payload is not one tier A produced, and its F1b is at most T1 = 17.552446 dB (F1b SHALL be computed only for a CRC-valid new payload). Several rows with one payload SHALL give one published row: the first, in the sorted order, whose estimate is not on a window edge, else the first. A published tier-B row SHALL carry the coherent SNR and the estimate's frequency (rounded to the nearest even integer Hz) and time, and the fallback's provenance tag.

#### Scenario: Equality with the classic fallback

- **WHEN** the weak-signal fixture the classic ordinary decode misses is decoded by the lean engine with CQ-AP off
- **THEN** the lean engine SHALL publish, as tier B, the payload the classic fallback's first run publishes after the primary pass

#### Scenario: A payload tier A found

- **WHEN** a candidate's coherent output equals a payload tier A produced
- **THEN** it SHALL NOT be published again and no text SHALL appear twice in a cycle

#### Scenario: One payload at two positions

- **WHEN** two candidates give the same new, gated payload and one estimate is on a window edge
- **THEN** exactly one row SHALL be published, from the non-edge estimate

### Requirement: CQ-AP runs after tier B, as FR-103

With `decoder.cqApEnabled` on, a candidate that failed tier A and produced no CRC-valid tier-B output SHALL get one belief-propagation-only attempt with payload bits 0 to 28 and 74 to 76 forced to the encoder's own CQ pattern, exactly as FR-103; its decodes SHALL carry `ApKind` `cq` and SHALL be counted. With the setting off the attempt SHALL NOT run.

#### Scenario: A drifting CQ

- **WHEN** a CQ whose carrier drifts too far for tier B to integrate is decoded with the setting on and off
- **THEN** the setting on SHALL decode more cycles, every extra decode tagged `cq`, and with the setting off the CQ-AP counters SHALL be zero

### Requirement: A wall-clock budget stops tier B and CQ-AP and returns what exists

The managed layer SHALL give the native call the 13 s cycle budget less the 250 ms publish reserve less the time already used. Tier B and CQ-AP SHALL check it between candidates; a stage that finds it spent SHALL stop, the abandoned flag SHALL be set, the skipped candidates SHALL be counted, and the results found so far SHALL be returned and SHALL be a subset of an unbudgeted run's results. Tier A SHALL NOT be budgeted.

#### Scenario: A zero budget

- **WHEN** the budget is 0 ms
- **THEN** no tier-B or CQ-AP row SHALL be returned, abandoned SHALL be set, every eligible candidate SHALL be counted as skipped, and nothing SHALL crash

### Requirement: Subtract-and-retry rounds find signals the subtraction unmasks

With the loop on (the managed layer always asks for it), after round 0 the native call SHALL run up to three rounds. A round SHALL subtract every result not yet subtracted whose unpacked text is re-encodable (no hash placeholder, at least three tokens) from a residual buffer using the data-aided fit on the original audio's analytic signal (computed once per cycle; the tones from the payload; a fit that answers "no valid fit" contributes zero; the fits run on the worker pool and are summed in the sorted result order), recompute the residual's spectrogram in full, search it (minimum score the decoder's residual floor, at most 200 candidates), keep only candidates whose base frequency lies within 50 Hz below to 100 Hz above a signal subtracted in that round, and decode those with tier A, tier B and CQ-AP. The loop SHALL stop when a round adds nothing, after round 3, or when the budget is gone; every result SHALL carry its round.

#### Scenario: A masked signal

- **WHEN** a weak message that a strong signal masks in round 0 is decoded with the loop on and off
- **THEN** with the loop on the weak message SHALL be published, tagged round 1, and with the loop off only the strong one SHALL be

#### Scenario: The patch window

- **WHEN** a residual candidate lies outside 50 Hz below to 100 Hz above every signal subtracted in the round
- **THEN** it SHALL NOT be attempted

#### Scenario: Nothing more to find

- **WHEN** round 1 finds nothing new
- **THEN** the cycle SHALL run no further round and report one round run

### Requirement: A residual decode is published under today's gates only

A residual decode SHALL be dropped if its payload equals, or is the RR73-aware same transmission of, any payload already found in the cycle, and if its text was already published in the cycle. A residual tier-B row SHALL be published if its F1b is at most T1, or (with `decoder.coherentFallbackResidualUngated` on and the fallback audio mode Both) whatever its F1b, counted as ungated; with `decoder.coherentFallbackResidualCandidates` on (Both mode) only an F1b-passed row at most 1097 Hz SHALL be published, and with it off that frequency rule SHALL NOT apply.

#### Scenario: The 1097 Hz rule

- **WHEN** an F1b-passed residual tier-B row is at 1098 Hz
- **THEN** it SHALL be dropped with the residual-candidates setting on and published with it off

### Requirement: A round the budget stops publishes nothing

A round SHALL NOT start with less than 1,500 ms of the budget left, the fits SHALL be cancelled at the budget less that reserve, and a round the budget stops SHALL publish nothing, set abandoned and end the loop, earlier rounds standing.

#### Scenario: A zero budget starts no round

- **WHEN** the budget is 0 ms
- **THEN** no round SHALL run and round 0's results SHALL be returned

### Requirement: The log line splits the subtraction cost

The per-cycle `lean:` line SHALL add, as counts and milliseconds only, the rounds run, the ungated count, the wall and CPU of the whole subtract-and-retry stage, its fit CPU, search CPU and decode CPU separately, and per round the signals fitted, subtracted and with no valid fit, the candidates found and kept, the results, and the wall and CPU of each step.

#### Scenario: Fit and search shown apart

- **WHEN** a cycle runs round 1
- **THEN** the line SHALL show the fit CPU and the search CPU as separate figures

### Requirement: The lean cycle publishes three batches, batch 1 before round 1

With the lean engine a cycle SHALL be decoded through the staged entry whatever the classic switches say. Batch 1 (round 0's results) SHALL be delivered exactly once, always (empty if nothing was decoded or the native call failed), and SHALL be handed over by the native call right after round 0 is unpacked, so that it is published while rounds 1 to 3 run; the native call SHALL NOT wait on the consumer. Batch 2 (rounds 1 to 3) and batch 3 (the cross-cycle stage's detections) SHALL be delivered only when non-empty. A text SHALL be published once per cycle across the batches.

#### Scenario: Batch 1 leaves before round 1

- **WHEN** the native call is held inside round 0's hand-off until the publisher has batch 1
- **THEN** batch 1 SHALL reach the publisher (the hand-off SHALL NOT time out), before the native call returns

#### Scenario: A native error

- **WHEN** the native call fails with nothing written
- **THEN** batch 1 SHALL still be delivered once, empty, and no other batch

### Requirement: The cross-cycle stage runs on the lean engine's final residual

With `decoder.crossCyclePrior` on, the native call SHALL return the final residual (the buffer as of the last subtraction made; results found in the last round are not subtracted for its sake). The existing template stage SHALL run on it unchanged and publish its detections as batch 3 with the template provenance tag, never entering the prior store; priors SHALL be recorded from batches 1 and 2. A cycle in which nothing was subtracted SHALL have no residual and the stage SHALL be a counted, logged skip. The residual SHALL be the same bytes at any thread count.

#### Scenario: A prior is found on the residual

- **WHEN** a message published 30 s earlier is present below the decode threshold in this cycle's audio
- **THEN** it SHALL be published as batch 3, and the prior store SHALL be unchanged by it

### Requirement: `decoder.effort` fast runs no tier B and one round

`decoder.effort` SHALL be `normal` (default) or `fast`; an absent key and any unknown value SHALL read `normal`. It SHALL be read once per cycle and apply only with the lean engine. `fast` SHALL run no tier B and at most one subtract-and-retry round; CQ-AP and the cross-cycle stage SHALL be unchanged.

#### Scenario: Fast

- **WHEN** a cycle is decoded with effort fast
- **THEN** the statistics SHALL show tier B neither eligible nor attempted and at most one round run

### Requirement: The fit is cheaper and gives the same bytes

The data-aided fit SHALL produce the same `out_shat` bytes and return code as before it was made cheaper, for every input; a reference mode of the fit SHALL exist so that a test can run both in one process and compare them.

#### Scenario: Reference and fast fit

- **WHEN** at least 30 signals (seeded noise at several signal-to-noise ratios, offsets and drifts, and the masked-signal fixture) are fitted in the reference mode and in the fast mode
- **THEN** every `out_shat` array and every return code SHALL be equal byte for byte

### Requirement: A fit is skipped when nothing could be hiding near the signal

With the fit-skip rule on (the default in the lean cycle; switchable off through the call's flags) a result of round r SHALL be fitted and subtracted only if some candidate of round r that did not decode lies within 50 Hz below to 100 Hz above its frequency. The statistics SHALL count, per round, the signals fitted and the signals skipped. With the rule off the cycle SHALL be what it was without the rule, byte for byte.

#### Scenario: A lone signal

- **WHEN** a round has one candidate and it decodes
- **THEN** its fit SHALL be skipped, no fit CPU SHALL be spent, and the published set SHALL equal the rule-off set

#### Scenario: What the rule can lose

- **WHEN** a masked signal was never a candidate of round 0
- **THEN** with the rule on it SHALL NOT be found by round 1, and with the rule off it SHALL be

### Requirement: A residual tier-B row is published when F1b-passed or ungated

In a residual round a CRC-valid, new tier-B row SHALL be published if its F1b is at most T1, or, with the ungating on, whatever its F1b, at any frequency (counted as ungated); `decoder.coherentFallbackResidualCandidates` SHALL have no effect on it.

#### Scenario: The flag does not restrict

- **WHEN** an F1b-failed residual row is at 2400 Hz with the ungating on and the residual-candidates flag on
- **THEN** it SHALL be published and counted as ungated

### Requirement: No residual after a half-subtracted round, and publisher errors propagate

A cycle that ends in an error (other than a fault) after a round's subtraction started SHALL return no residual buffer. An exception from the batch publisher SHALL propagate, after the native call's task has been awaited.

#### Scenario: An error after the first chunk

- **WHEN** a round's fits fail after their first chunk
- **THEN** the earlier rounds' results SHALL be returned and no residual

### Requirement: The operator sets the lean decoder's thread count, engine and effort on the Settings page

The Settings page's Advanced Decoder Settings SHALL offer `decoder.threads` (an integer 1 to 16 explicit; default automatic, stored as 0 or absent), `decoder.engine` (`classic` default, `lean`) and `decoder.effort` (`normal` default, `fast`). An absent key SHALL show the default (for threads, the resolved automatic value with an "Automatic" hint, falling back to 2 and no hint when the daemon reports no processor count), a stored value SHALL be shown as stored, and an unknown stored engine or effort word SHALL show the default and be sent back as stored until the operator changes the select. The help text SHALL give the daemon host's logical processor count (from the status endpoint, never the browser's), say that more threads show the lean decoder's results sooner at the cost of more total CPU, give the one measurement with its limits, and say that the setting applies only with the lean engine and that the maximum is 16. A save SHALL NOT write a number the operator did not enter: an untouched thread field SHALL post 0 (a stored explicit value posts as stored), a touched field SHALL post its number clamped to 1 to 16 even when it equals the automatic value, "Reset to defaults" SHALL restore automatic, and an unchanged engine or effort select SHALL post nothing for a key that was never stored. The help text SHALL also give the three-point measurement and the memory cost (about 32 MB per worker while it subtracts) and say that automatic uses every logical processor up to 16. The config POST SHALL keep a `threads` of 0 and clamp any other value outside 1 to 16 with a warning, storing the clamped value. The lean engine's workers SHALL be capped at 16 and its results SHALL be byte-identical at 1, 2, 4, 8 and 16 threads.

#### Scenario: A save without touching the field

- **WHEN** the operator saves the Settings page without touching the thread field, on a config with no `threads`
- **THEN** the page SHALL post `threads` 0 and no `engine` or `effort`, and the stored value SHALL stay automatic

#### Scenario: A value above the cap

- **WHEN** the config POST carries `threads` 64
- **THEN** 16 SHALL be stored and a warning logged

#### Scenario: Sixteen threads

- **WHEN** a cycle is decoded at 16 threads
- **THEN** its results, tiers, rounds and residual SHALL equal those at 1 thread, byte for byte


### Requirement: The lean engine is the default, a stored classic is migrated once, and the lean engine publishes the strongest of its duplicates

`decoder.engine` SHALL default to `lean`: an absent key, a missing decoder section, a fresh install and any value other than the word `classic` SHALL read `lean`. A config that holds `decoder.engine` as `classic` and does not carry the server-owned marker `decoder.leanEngineMigrationApplied` SHALL be rewritten to `lean` once, with the marker set and the file saved; after the marker an explicit `classic` SHALL be respected and no request body SHALL set or clear the marker. `decoder.kMinScorePass2` SHALL remain a setting. Of two or more hits of one round with the same payload (round 0) or the same transmission (a residual round), and of two or more results of one round with the same rendered text, the hit with the highest candidate sync score SHALL be published at its own frequency and time; equal scores SHALL keep the earlier hit in ascending frequency order; an earlier round's decode SHALL stand over a later round's copy; output SHALL stay byte-identical at 1, 2, 4, 8 and 16 threads.

#### Scenario: A stored classic is migrated once

- **WHEN** a config holds `engine` `classic` and no marker
- **THEN** it SHALL load as `lean` with the marker set and the file rewritten, and a `classic` the operator chooses afterwards SHALL be kept

#### Scenario: The stronger duplicate is at the higher frequency

- **WHEN** two hits of one round carry the same payload and the higher-score hit is at the higher frequency
- **THEN** the higher-score hit SHALL be published, at its own frequency

#### Scenario: Equal scores

- **WHEN** two same-payload hits have equal scores
- **THEN** the one at the lower frequency SHALL be published, as before


### Requirement: A test-only probe reports why the lean engine misses a weak signal beside a strong one, without changing what it publishes

With the native flag `FTZ_FLAG_PROBE` set (by the replay harness only; the daemon SHALL NOT set it) and a caller-supplied probe buffer, the lean cycle SHALL fill the buffer with numbers only (no message text, no payload): a `SUB` row for every signal subtracted (round, frequency, time, the fit's amplitude, and the suppression in dB of the signal's footprint of 8 tone columns by 79 symbols between the waterfall of the round's input and the waterfall of the residual), a `CAND` row for every candidate the search returned in every round (frequency, time, sync score, whether the round's patch filter kept it, one exclusive outcome code and the stage columns), and, in rounds 1 to 3, `LOW` rows from one extra search of the residual with floor 0 and cap 400 that is never decoded. The buffer SHALL be bounds-checked: a row that does not fit sets an overflow flag and is dropped. With the flag off nothing SHALL be allocated or computed, and with it on the published decodes SHALL be byte-identical at every thread count.

#### Scenario: The flag changes nothing that is published

- **WHEN** a cycle is decoded with and without the flag on the same audio and hash state
- **THEN** the results, tiers and rounds SHALL be identical, at 1, 2, 4, 8 and 16 threads

#### Scenario: A strong and a weak signal 10 Hz apart

- **WHEN** the probe is on
- **THEN** there SHALL be one `SUB` row for the strong signal with suppression above 0 dB, and a `CAND` row near the weak one

#### Scenario: A buffer that is too small

- **WHEN** the probe buffer holds fewer rows than the cycle produces
- **THEN** the rows that fit SHALL be returned, the overflow flag SHALL be set, and nothing SHALL be written past the end


### Requirement: The lean engine fits every published result from its decoded payload, whatever its text

In every residual round the lean engine SHALL consider every published result that is not yet subtracted for the fit, under the step-2e skip rule unchanged, regardless of its rendered text: a result whose text carries a `<...>` hash placeholder, or has fewer than three tokens, SHALL be fitted like any other. The fit's tones SHALL come from the decoded 77-bit payload, never from the text. The classic decoder is not affected.

#### Scenario: A result with a hash placeholder is fitted

- **WHEN** a result whose text is `<...> Q5XYZ/P` is published in round 0 and a candidate fails to decode inside its patch window
- **THEN** a `SUB` row SHALL be written for it in round 1, the round's fit count SHALL include it, and a weaker signal it masked SHALL be found

#### Scenario: A result with fewer than three tokens is fitted

- **WHEN** a result whose text is `CQ Q5XYZ/P` is published in round 0 and a candidate fails to decode inside its patch window
- **THEN** it SHALL be fitted and subtracted in round 1 like any other
