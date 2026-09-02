## ADDED Requirements

### Requirement: 12-bit hash resolution requires a unique probe-chain match

The native decode pipeline SHALL display a 12-bit-hash-resolved callsign **only when its probe chain
holds exactly one matching entry**. When the chain holds two or more matching entries, the decoded
text SHALL use the existing unresolved-hash placeholder (`<...>`), and **the decode itself SHALL be
retained** — suppression withholds a name, it never discards a decode.

A 12-bit callsign hash is a many-to-one reference over the amateur callsign population, so a probe
chain in the session-scoped hash table can hold more than one matching entry. When it does, no
candidate callsign is more justified than any other, and displaying the first is a claim the data
does not support.

This rule SHALL apply unconditionally on all bands and under all operating conditions. It SHALL NOT
be gated on a band, a runtime flag, a configuration setting, or an operator preference.

Scope is the 12-bit hash path only. The 22-bit and 10-bit hash paths SHALL be unaffected.

#### Scenario: An ambiguous probe chain suppresses the callsign

- **WHEN** a Type 1/2/3 message references a 12-bit callsign hash
- **AND** the session hash table's probe chain for that hash holds two or more matching entries
  (for example, synthetic callsigns `Q1ABC` and `Q2XYZ` both announced earlier in the session and
  colliding on the same 12-bit code)
- **THEN** the decoded text SHALL contain `<...>` in that callsign's position
- **AND** the decoded text SHALL NOT contain either candidate callsign

#### Scenario: A unique probe-chain match still resolves

- **WHEN** a Type 1/2/3 message references a 12-bit callsign hash
- **AND** the probe chain for that hash holds exactly one matching entry
- **THEN** the decoded text SHALL contain that callsign, exactly as it did before this change

#### Scenario: Suppression never costs a decode

- **WHEN** a decode cycle contains messages whose 12-bit hash references are ambiguous
- **THEN** the number of decodes reported for that cycle SHALL be identical to the number reported
  by a run of the same audio without this rule
- **AND** each affected decode's frequency, time offset, SNR and payload SHALL be unchanged — the
  callsign token is the only field that differs

#### Scenario: The 22-bit hash path is unaffected

- **WHEN** a Type 1/2/3 message references a 22-bit callsign hash, whether or not that hash resolves
- **THEN** the resolution behaviour SHALL be exactly as it is today, with no suppression applied

### Requirement: Suppression is observable and does not blind the existing sizing instrument

The 12-bit hash-path sizing counters SHALL continue to count what **would** have been displayed
after this rule ships, so that readings taken before and after the change remain directly
comparable and the effect of the rule can be re-measured at any time.

Consequently the internal "the table resolved this hash" signal SHALL retain its existing meaning —
it SHALL reflect the hash table's own result and SHALL NOT be falsified to express a suppression
decision. Suppression SHALL be carried by a separate signal.

A process-lifetime count of suppressed callsigns SHALL be exported natively, bound in managed code,
and reported in the existing per-cycle 12-bit hash-path log line.

#### Scenario: The existing sizing counters are unchanged by suppression

- **WHEN** a decode cycle emits messages whose 12-bit hash references are ambiguous and are
  therefore suppressed
- **THEN** the displaying, ambiguous and divergent counts SHALL increment exactly as they did before
  this change, counting what would have been displayed
- **AND** the per-code cluster table SHALL likewise be unaffected by the suppression decision

#### Scenario: The suppression count agrees with the ambiguous count

- **WHEN** a run completes
- **THEN** the suppressed count SHALL equal the ambiguous count exactly

⚠️ This scenario is a **wiring invariant** between the site where suppression is decided and the
site where it is counted; a disagreement proves those two sites disagree. It cannot detect an error
in the multiplicity computation itself, because both counts descend from it — that is the first
Requirement's scenarios' job.

#### Scenario: The suppressed count is reported per cycle

- **WHEN** a decode cycle completes
- **THEN** the cumulative suppressed count SHALL appear in the same per-cycle log line that already
  reports the displaying, ambiguous and divergent counts

#### Scenario: Counting suppression does not count decode attempts

- **WHEN** a message's 12-bit hash lookup is performed and suppressed, but the message's text decode
  subsequently fails and the message is never emitted
- **THEN** the suppressed count SHALL NOT increment for that message

⚠️ The hash-lookup callback runs during text decode, which also runs for messages that are then
discarded. A count taken at the callback would measure decode **attempts**, not **displays**, and
would not agree with the ambiguous count.
