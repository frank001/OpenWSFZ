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

With `decoder.engine` effective as `lean`, a cycle SHALL be decoded by one call of `ftz_decode_cycle` per window: the spectrogram (the primary pass's configuration), the candidates (`ftx_find_candidates` with the primary pass's parameters: minimum score 10, at most 140), tier A on every candidate (magnitude likelihoods, belief propagation, CRC-14, unpack), and nothing else: no tier B, no CQ-AP, no OSD, no subtraction. The classic decoder, its native calls and its batches SHALL NOT be entered. The input SHALL be conditioned as the primary pass conditions it, and the results SHALL pass the same per-cycle text de-duplication, plausibility filter, region and worked-before steps as every classic batch. The results SHALL be published as one batch, the cycle's batch 1, through the existing publish path. The early decode SHALL return nothing under `lean`.

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
