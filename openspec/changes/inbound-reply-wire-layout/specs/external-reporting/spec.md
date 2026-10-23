## ADDED Requirements

### Requirement: An inbound Reply laid out per the WSJT-X protocol is parsed

The service SHALL parse an inbound Reply datagram (message type 4) whose fields, after the header and Id, are, in order: Time (`quint32`), snr (`qint32`), delta time (8-byte IEEE double), delta frequency (`quint32`), mode (utf8), message (utf8), and then optionally Low confidence (bool) and Modifiers (`quint8`), as defined by WSJT-X `NetworkMessage.hpp` (Reply, In, 4). The Reply SHALL NOT carry a `New` field. Low confidence and Modifiers MAY be absent, and bytes after Modifiers SHALL be ignored. A datagram truncated inside Time through message SHALL be discarded as malformed without raising an error.

#### Scenario: A Reply as GridTracker2 sends it is parsed

- **WHEN** the service receives a Reply datagram of 68 bytes, schema 3, with message `CQ Q1TST JO22`, delta frequency 1234, Low confidence 0 and Modifiers 0x00
- **THEN** the datagram SHALL be handed to the Reply handler with that message and that delta frequency, and SHALL NOT be logged as malformed

#### Scenario: Modifiers are read and ignored

- **WHEN** the same Reply carries Modifiers 0x02 (SHIFT) or 0x04 (CTRL)
- **THEN** it SHALL be parsed exactly as with Modifiers 0x00

#### Scenario: Trailing fields may be absent

- **WHEN** the same Reply ends after Low confidence, or ends after the message
- **THEN** it SHALL still be parsed

#### Scenario: Appended bytes are ignored

- **WHEN** the same Reply carries extra bytes after Modifiers
- **THEN** it SHALL be parsed exactly as without them

#### Scenario: A truncated Reply is discarded

- **WHEN** a Reply datagram ends inside the message text or inside delta time
- **THEN** it SHALL be discarded as malformed, a Debug entry SHALL be written, and the receive loop SHALL continue
