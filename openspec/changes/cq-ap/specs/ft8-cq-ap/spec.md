## ADDED Requirements

### Requirement: `decoder.cqApEnabled` switches the CQ a-priori attempt, and an absent key reads off

The configuration SHALL provide the boolean `decoder.cqApEnabled`. When the key is absent (or the `decoder` section is missing) the value SHALL be `false`, and with `false` every decode outcome on a fixed set of cycles SHALL be identical to the build before this setting existed, QSO-context a-priori decoding included. The key SHALL be read once per decode window and take effect on the next window. It SHALL be settable through the configuration file and the configuration API (a partial post is an overlay and SHALL NOT reset it); there is no Settings-page control.

#### Scenario: The key is absent

- **WHEN** the configuration has no `decoder.cqApEnabled`
- **THEN** the effective value SHALL be `false`, no CQ a-priori attempt SHALL run, no `cq-ap:` line SHALL be written and no decode SHALL carry the tag `cq`

#### Scenario: An explicit value

- **WHEN** the configuration sets the key to `true` or `false`
- **THEN** that value SHALL be kept after a save and a reload, and be the effective value from the next window

#### Scenario: A partial configuration post

- **WHEN** a configuration post carries other keys and not `decoder.cqApEnabled`
- **THEN** the key SHALL keep the value it had, including an explicit `true`

#### Scenario: The flag reaches the native decode

- **WHEN** the setting is `true` for a cycle
- **THEN** the thread-local native flag SHALL be set on the decoding thread before every native decode of that cycle (pass 0, the residual pass, the third pass and the late round), and SHALL be `false` for every native decode of a cycle with the setting `false`

### Requirement: The CQ attempt forces bits 0 to 28 and 74 to 76, after normalisation, and uses belief propagation only

With the setting `true`, the attempt SHALL force exactly 32 payload positions: bits 0 to 28 (the first call field, `n29a` = c28(`CQ`) `<< 1` | `ipa` 0) and bits 74 to 76 (`i3` = 1), each to the bit value ft8_lib's encoder gives for a standard `CQ` message, with the belief-propagation sign convention (bit 1 is a positive LLR). The forced LLRs SHALL be written after `ftx_normalize_logl`, at a magnitude of 1.01 times the largest absolute value of the normalised non-forced entries. The attempt SHALL run belief propagation only with the same iteration limit as the normal attempt; the OSD SHALL NOT be entered from it, and a thread-local counter of OSD entries from the CQ attempt SHALL read 0. The QSO-context a-priori path (its positions, its scaling and its OSD fallback) SHALL be unchanged.

#### Scenario: Positions and values

- **WHEN** `CQ Q1ABC JO22` is encoded with ft8_lib's encoder and the forcing pattern is read
- **THEN** exactly 32 positions SHALL be forced, each equal to the encoded bit, and no position outside bits 0 to 28 and 74 to 76 SHALL be forced

#### Scenario: Magnitude and order

- **WHEN** the attempt is run on a raw LLR vector
- **THEN** every non-forced entry SHALL equal the raw value scaled by the normalisation computed over all raw entries, and every forced entry SHALL have magnitude 1.01 times the largest normalised non-forced magnitude, with the sign of its bit

#### Scenario: The sign matters

- **WHEN** a clean, noise-free `CQ Q1ABC JO22` is presented to the attempt
- **THEN** the right-sign override SHALL decode it and the opposite-sign override SHALL NOT

#### Scenario: No OSD

- **WHEN** a run in which belief propagation fails on many CQ attempts is made with the setting `true`
- **THEN** the counter of OSD entries from the CQ attempt SHALL read 0, and a test copy that does enter the OSD SHALL read more than 0

### Requirement: The CQ attempt is extra, never instead, on failed candidates in every pass

With the setting `true`, the CQ attempt SHALL run only on a candidate whose normal attempt (QSO-context a-priori included) failed, in every pass of the native decode and on every buffer it is called on, and it SHALL never replace a normal attempt. It SHALL be part of the decode determination before the branch that discards a failed candidate, so a decode it makes SHALL pass through the cross-pass dedup, the text decode and the hash handling, SHALL be published at most once, and SHALL mark its candidate decoded for the coherent fallback (the fallback SHALL NOT retry it). A decode the normal attempt makes SHALL be identical with the setting `true` and `false`, and its candidate SHALL NOT be counted as a CQ attempt.

#### Scenario: Normal decodes are unchanged

- **WHEN** a cycle is decoded with the setting `true` and the normal attempt decodes a message
- **THEN** that decode (text, frequency, time offset, SNR) SHALL equal the decode with the setting `false`, and its tag SHALL be `none`

#### Scenario: A CQ decode clears the fallback

- **WHEN** the CQ attempt decodes a weak CQ that the normal attempt missed
- **THEN** that candidate SHALL NOT be eligible for the coherent fallback, and the CQ SHALL be published once even if two candidates decode to it

#### Scenario: A non-CQ message

- **WHEN** a message that is not a CQ is presented with the setting `true`
- **THEN** it SHALL never be decoded with the tag `cq`

### Requirement: Every decode carries an apKind, and one `cq-ap:` line is written per cycle while the setting is on

Every decode SHALL carry an `apKind`, `none` or `cq`, from the native result to the managed decode record; it SHALL NOT appear in the decode panel, `ALL.TXT` or the UDP datagrams. While the setting is `true` the decoder SHALL write one Information line per cycle, `cq-ap: attempts=N decodes=M`, where N is the number of CQ attempts made by every native decode of the cycle and M the number of `cq` decodes published (past the plausibility filter and the text de-duplication); counts only, never a callsign or message text. With the setting `false` no such line SHALL be written. A decode the CQ attempt makes SHALL pass the same CRC, plausibility filter and text de-duplication as any decode.

#### Scenario: The tag and the line

- **WHEN** the setting is `true` and a cycle publishes one `cq` decode
- **THEN** that decode's tag SHALL be `cq`, all others `none`, and exactly one `cq-ap:` line SHALL be written for the cycle with `decodes=1`

#### Scenario: An implausible CQ decode

- **WHEN** the CQ attempt produces a CRC-valid message that fails the plausibility filter
- **THEN** it SHALL be dropped and SHALL NOT be counted as published

#### Scenario: The setting is off

- **WHEN** the setting is `false`
- **THEN** no `cq-ap:` line SHALL be written

### Requirement: A CQ-AP decode is never uploaded to PSK Reporter

A decode with `apKind = cq` SHALL NOT be uploaded to PSK Reporter. It SHALL be counted under a new exclusion reason `ap=` on the per-window accounting line (`..., dedup=N, ap=N`), on the per-datagram line (`... dedup=N ap=N queue-dropped=N ...`) and in the status counters (`window.ap`); `ap` SHALL be a count only and SHALL NOT be a refusal reason. The exclusion SHALL apply before every other per-decode exclusion, so a `cq` decode is counted under `ap=` only. `ALL.TXT`, the UDP datagrams and the decode panel SHALL be unchanged.

#### Scenario: A mixed batch

- **WHEN** a batch holds two `cq` decodes and one ordinary decode
- **THEN** only the ordinary decode SHALL be reported, and `ap=2` SHALL be counted

#### Scenario: Only AP decodes

- **WHEN** a window holds only `cq` decodes
- **THEN** no datagram SHALL be sent, `ap` SHALL count them, and the status SHALL NOT be refused
