## ADDED Requirements

### Requirement: The PSK Reporter upload is opt-in and inert by default

The configuration SHALL provide a `pskReporter` block with `enabled` (boolean, default `false`), `antennaInformation` (string, default `""`), `host` (string, default `report.pskreporter.info`) and `port` (integer, default `4739`). A configuration file without the block, or with `enabled` false, SHALL behave identically: the service SHALL create no socket, perform no DNS lookup and run no timer work. The Settings page SHALL NOT expose `host` or `port` (they are for the test listener and are set in the configuration file).

#### Scenario: Disabled does nothing

- **WHEN** `pskReporter.enabled` is false and batches 1 to 4 arrive for a full run of cycles
- **THEN** the injected socket factory SHALL NOT be called, no host name SHALL be resolved, and no record SHALL be queued

#### Scenario: A configuration without the block

- **WHEN** the stored configuration has no `pskReporter` key
- **THEN** it SHALL load as `enabled` false, `antennaInformation` empty, `host` `report.pskreporter.info`, `port` 4739, and saving it SHALL write those values back

### Requirement: Nothing is uploaded under a placeholder identity

While the receiver callsign (`tx.callsign`) is empty or Q-prefix (the ITU-unallocated placeholder range, default `Q1OFZ`), or the receiver locator (`tx.grid`) is empty, the service SHALL send nothing, even when `enabled` is true. It SHALL log this once per send window as a count with no callsign, and count the refused records by reason.

#### Scenario: The default identity

- **WHEN** `enabled` is true, `tx.callsign` is `Q1OFZ` and batches arrive
- **THEN** no datagram SHALL be sent and the socket factory SHALL NOT be called

#### Scenario: An empty locator

- **WHEN** `enabled` is true, `tx.callsign` is a real call and `tx.grid` is empty
- **THEN** no datagram SHALL be sent

### Requirement: The datagram is the page's simplified IPFIX, byte for byte

Each datagram SHALL be built exactly as `https://pskreporter.info/pskdev.html` specifies, and as the fixtures in `qa/rr-study/psk-reporter-262/` show: a 16-byte header (version `00 0A`, total length, export time in Unix seconds, sequence number, a random 4-byte session id constant for the process), then the template sets when due, then one receiver record, then the sender blocks; all integers big-endian; every set padded with zero bytes to a multiple of 4 with its length field including header and padding. The receiver descriptor SHALL be set id 3 (an options template with scope-field count 1), template id `0x9992`, fields `receiverCallsign` (30351.2), `receiverLocator` (30351.4), `decodingSoftware` (30351.8) and, only when `antennaInformation` is non-empty, `antennaInformation` (30351.9). The sender descriptors SHALL be set id 2: template id `0x9993` with the 8 fields `senderCallsign` (30351.1), `frequency` (30351.5, 4 bytes), `sNR` (30351.6, 1 byte), `iMD` (30351.7, 1 byte), `mode` (30351.10), `informationSource` (30351.11, 1 byte), `senderLocator` (30351.3), `flowStartSeconds` (IANA 150, 4 bytes), in that order; and template id `0x9994` with the same 7 fields without `senderLocator`. A sender record whose message carries a grid SHALL go in a `0x9993` block, one without in a `0x9994` block; a datagram carries one block per template that has records. Strings SHALL be a 1-byte length (at most 254) followed by UTF-8. `decodingSoftware` SHALL be `OpenWSFZ <VERSION>`; `frequency` SHALL be the dial frequency at capture plus the audio offset in Hz; `mode` SHALL be `FT8`; `informationSource` SHALL be 1; `flowStartSeconds` SHALL be the cycle start; `sNR` SHALL be the decode's SNR as a signed byte clamped to [-128, 127]; `iMD` SHALL be 0 in every record (OpenWSFZ does not measure it). A datagram SHALL NOT exceed 1,400 bytes.

#### Scenario: Golden bytes

- **WHEN** one receiver record and two sender records (one with a grid, one without) are encoded with a fixed session id, sequence number and export time and the templates due
- **THEN** the bytes SHALL equal the fixture hand-built from the page (`t1_8field_and_7field.hex`), including the 8-field block before the 7-field block, and with a non-empty antenna the fixture `t1_with_antenna.hex`

#### Scenario: Templates not due and an SNR below the byte range

- **WHEN** a datagram is encoded without templates and a record's SNR is -132
- **THEN** the bytes SHALL equal `t1_templates_not_due_snr_clamped.hex`, with `sNR` the byte `0x80`

#### Scenario: iMD is always zero

- **WHEN** any record is encoded
- **THEN** its `iMD` byte SHALL be 0

### Requirement: Datagram cadence, templates, sequence number and source port

The service SHALL send at most one datagram every 5 minutes, from a timer started when the service starts (first send after a random offset of 0 to 60 seconds) and not synchronised to the wall clock, except that a full datagram SHALL be sent at once; an empty window SHALL send nothing. The template sets SHALL be included in the first three datagrams and then at least once per hour. The sequence number SHALL start at 0 for each process (with a new random session id), increase by the number of sender records in each datagram sent (the receiver record is not counted), and not advance for a datagram that is not sent. All datagrams SHALL leave from one IPv4 UDP socket created once per enable (re-created only after `enabled` goes false then true) and never bound to port 4739.

#### Scenario: Templates cadence

- **WHEN** five datagrams are sent and then an hour and a minute pass
- **THEN** datagrams 1 to 3 SHALL carry the template sets, 4 and 5 SHALL NOT, and the next one after the hour SHALL

#### Scenario: Sequence advances by sender records

- **WHEN** datagrams of 2, 0 (none sent) and 5 sender records are sent in turn
- **THEN** their sequence numbers SHALL be s, s+2 and s+7 with s starting at 0

#### Scenario: Cadence under a fake clock

- **WHEN** 20 minutes of batches are fed under a fake clock
- **THEN** at most one datagram SHALL go per 5 minutes unless one is full, a full datagram SHALL go at once, and every datagram SHALL be at most 1,400 bytes

#### Scenario: One source port

- **WHEN** several datagrams are sent in one enabled period
- **THEN** the socket factory SHALL have been called once and every datagram SHALL have used that socket

### Requirement: The sender is extracted strictly by classifying tokens

The reported sender SHALL be derived from the message text by classifying tokens, never by counting them. A callsign token contains at least one digit and one letter, optionally with `/` parts; a token in angle brackets is a hash. A CQ modifier is 1 to 4 letters or exactly 3 digits. A grid is `[A-R]{2}[0-9]{2}` and is not `RR73`. `CQ [modifier] <callsign> [grid]` SHALL give the callsign (and the grid when present); the standard `<to> <from> <extension>` form SHALL give `<from>` (token 1), and its grid only when this message carries one in the grid position. There SHALL be no fallback to token 0. A hashed sender (including a hash the decoder resolved to text), a keyword, free text, telemetry or anything unparseable SHALL NOT be reported. The callsign SHALL be kept exactly as decoded, prefixes and suffixes included. The station's own call, compared on the base call with prefix and suffix stripped and case-insensitively, SHALL NOT be reported.

#### Scenario: The sender table

- **WHEN** the messages `CQ Q1ABC JO22`, `CQ DX Q1ABC JO22`, `CQ DX Q1ABC`, `CQ POTA Q1ABC JO22`, `CQ 123 Q1ABC`, `CQ Q1ABC/P`, `Q2DEF Q1ABC -12`, `Q2DEF Q1ABC R-05`, `Q2DEF Q1ABC RR73`, `Q2DEF Q1ABC JO22` are classified
- **THEN** each SHALL give Q1ABC (or Q1ABC/P) as sender, with the grid JO22 only for those that carry it in the grid position, and `RR73` SHALL never be taken as a grid

#### Scenario: Not reported

- **WHEN** `Q2DEF <...> -12`, `<...> Q1ABC 73`, `<Q1ABC> Q2DEF -12`, `CQ DX`, free text, a telemetry message, `Q1ABC RR73; Q2DEF <Q3GHI> -08` and a message whose sender is the station's own call (also as `/P`) are classified
- **THEN** none SHALL be reported, each with its reason counted, and no case SHALL return token 0

### Requirement: The source is the same decode stream GridTracker receives, with the same exclusions

The service SHALL receive every batch the decode pump publishes (batches 1 to 4 when the coherent fallback is on), after the operator's noise suppression, and SHALL NOT receive early-decode preview rows. Decodes whose `Region` is null (unknown) or `Synthetic` SHALL never be encoded, by the same rule as `external-reporting`, which is not operator-configurable. The batch SHALL carry the dial frequency of the cycle at capture; a cycle without a known dial frequency SHALL report nothing and be counted.

#### Scenario: Exclusions

- **WHEN** a batch holds synthetic and unknown-region decodes among real ones
- **THEN** only the real ones SHALL be encoded and the others counted by reason

#### Scenario: Dial frequency at capture

- **WHEN** a batch captured at 7.074 MHz reaches the service after CAT has moved to 14.074 MHz
- **THEN** each record's frequency SHALL be 7,074,000 Hz plus its audio offset

#### Scenario: All four batches arrive

- **WHEN** a fallback-on cycle publishes batches 1 to 4
- **THEN** all four SHALL reach the service, and the service's own channel SHALL have capacity 4 x 2 + 2 = 10 with the fallback on (8 with it off), DropOldest, separate from the capacity-2 external-reporting channel

### Requirement: One report per call per five minutes, one per call and band per hour

For each call the service SHALL leave at least 5 minutes between records; for each (call, band) it SHALL send at most one record per 60 minutes. A band change starts a new (call, band) key but still respects the 5-minute minimum. Duplicates SHALL be removed before formatting. The band SHALL be the band of the dial frequency at capture.

#### Scenario: Dedup

- **WHEN** the same call is decoded three times within 4 minutes on one band
- **THEN** one record SHALL be queued; a further decode at 6 minutes on the same band SHALL queue none; one at 61 minutes on the same band SHALL queue one; and one at 7 minutes on another band SHALL queue one

### Requirement: A failure never reaches the decoder

DNS or socket errors SHALL be logged at Warning once per send window (not per record) and retried at the next window. The queue held across failures SHALL be bounded, the oldest records dropped and counted. The service SHALL NOT throw into the decode pump. Records SHALL be held in memory only and never written to disk.

#### Scenario: A socket that throws

- **WHEN** the socket's send throws
- **THEN** no exception SHALL reach the pump, one Warning SHALL be logged for that window, and the next window SHALL retry

### Requirement: Each datagram is accounted for with counts, never calls

For each datagram sent the service SHALL log one Information line with the UTC time, the number of records in it, the number of records excluded by reason (synthetic or unknown region, hashed or unparseable sender, own call, no dial frequency, dedup, placeholder identity) and the sequence number after it. The line SHALL NOT contain any callsign or message text.

#### Scenario: The log line

- **WHEN** a datagram of 3 records is sent after 2 own-call exclusions and 1 dedup
- **THEN** the line SHALL state 3 records, those exclusion counts and the new sequence number, and no callsign

### Requirement: The Settings page has the opt-in control

The Settings page SHALL provide a checkbox bound to `pskReporter.enabled` and a free-text field bound to `pskReporter.antennaInformation`, with the text: "Sends the calls and locators of stations you receive, with your call and locator, to the public PSK Reporter service." Saving SHALL post only the two keys the page shows (`enabled` and `antennaInformation`), never `host` or `port`, and a configuration POST that does not mention the `pskReporter` block SHALL leave it unchanged; a POST that changes only `pskReporter.antennaInformation` SHALL leave `enabled`, `host` and `port` as saved.

#### Scenario: Opt in through the page

- **WHEN** the operator ticks the checkbox, types an antenna description and saves
- **THEN** the stored configuration SHALL hold `enabled` true and that antenna text, and `host` and `port` SHALL be unchanged

#### Scenario: Nested overlay

- **WHEN** a configuration POST contains only `{"pskReporter":{"antennaInformation":"X"}}` while `enabled` is true
- **THEN** `enabled`, `host` and `port` SHALL keep their stored values

### Requirement: Privacy of the upload

The upload SHALL happen only while `enabled` is true. Tests and fixtures SHALL use Q-prefix callsigns only. The service SHALL store nothing beyond what is already logged and SHALL NOT log calls.

#### Scenario: No calls in logs

- **WHEN** a full run with real-looking Q-prefix calls is logged at every level
- **THEN** no callsign from the decodes SHALL appear in any log line written by the service
