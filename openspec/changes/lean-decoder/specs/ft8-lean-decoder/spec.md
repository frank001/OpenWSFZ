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

The configuration SHALL provide the integer `decoder.threads`, default 2, applied clamped to 1 to 8, no effect while the engine is `classic`. The lean engine's output SHALL NOT depend on it.

#### Scenario: Out of range

- **WHEN** `decoder.threads` is 0 or 99
- **THEN** the lean engine SHALL use 1 or 8 respectively

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
