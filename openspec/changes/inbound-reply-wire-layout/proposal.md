**User-facing:** yes

## Why

Issue #257. A Reply that GridTracker2 sends when its operator double-clicks a CQ never reaches the daemon's Reply handler: `WsjtxDatagram.DecodeReply` reads a leading `New` boolean that the WSJT-X Reply message does not have, so the datagram is discarded as malformed. Reply from GridTracker2 has probably never worked since external reporting shipped.

The WSJT-X protocol (`Network/NetworkMessage.hpp`, Reply, In, type 4) is: Id, Time, snr, delta time (double), delta frequency, mode, message, low confidence, Modifiers (`quint8`). There is no `New` field (that is Decode's). **Confirmed against the real client:** QA captured GridTracker2's Reply to a synthetic CQ on 2026-10-23 (P1): 68 bytes, schema 3, no `New` byte, Low confidence 0x00 and Modifiers 0x00 as the last two bytes. The parse was written from the wrong premise that Reply echoes the Decode layout, and the repo's tests built their datagrams in the same wrong layout, so nothing caught it.

Architect spec: `qa/rr-study/2026-10-23-1610-architect-to-qa-spec-reply-parse-wire-layout.md` (`arch/reply-parse`, `8cc90876`); QA (k) review with amendments M1 to M4: `qa/rr-study/2026-10-23-1625-qa-k-review-reply-parse-wire-layout.md`; P1 capture: `qa/rr-study/2026-10-23-1630-qa-p1-gridtracker-reply-capture.md`. The Captain chose option A (issue plus Architect spec), 2026-10-23.

## What Changes

- `DecodeReply` reads, after the header and Id: Time (`quint32`), snr (`qint32`), delta time (double), delta frequency (`quint32`), mode (utf8), message (utf8), then **Low confidence and Modifiers as optional** trailing fields; bytes after Modifiers are ignored. A truncation inside Time through Message still makes `TryDecode` return `false`.
- A small `TryReadByte` on the reader, following `TryReadBool`.
- Comments tell the truth: the `DecodeReply` summary cites `NetworkMessage.hpp` (Reply, In, 4); the class provenance note says Reply, Halt Tx and Free Text were checked against that header and Reply against a real capture.
- Tests (see tasks): a literal byte fixture from the P1 capture, no helper that shares the parser's field list; the two existing Reply builders are rewritten to the real layout.

**Unchanged:** `InboundMessage.ReplyMessage(string Message, uint DeltaFrequencyHz)`, `ExternalReportingService.HandleReply`, the callsign extraction, `IExternalReplyTarget`, Halt Tx and Free Text (checked, they match), the outbound encoders, the schema accepted on decode (1, 2, 3). Modifiers are read and discarded: what OpenWSFZ should do with SHIFT and the like is a separate question.

## Non-goals

Acting on Reply Modifiers; auditing outbound datagram layouts (GridTracker displays them correctly live); schema 3 encoding; relaying Reply between leader and follower; the station's stale `logging.directory`.

## Capabilities

### Modified Capabilities

- `external-reporting`: an inbound Reply laid out as `NetworkMessage.hpp` defines it is parsed.

## Impact

`src/OpenWSFZ.Daemon/WsjtxDatagram.cs`, `tests/OpenWSFZ.Daemon.Tests/WsjtxDatagramTests.cs` and `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`. No `native/` change. `VERSION` bump per G9b (user-facing: yes): from the `origin/main` value, with README and REQUIREMENTS anchors.
