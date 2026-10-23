## Context

`WsjtxDatagram.DecodeReply` on `origin/main` `326a8af7` (`:299-310`) reads `TryReadBool` (New), Time, SNR, DeltaTime, DeltaFrequency, Mode, Message, `TryReadBool` (LowConfidence). Its summary comment says the inbound Reply has the same layout as the outbound Decode. That is wrong: the WSJT-X Reply message has no `New` field and ends with a Modifiers byte. `TryDecode` returns `false` for a real Reply because the shifted reads end in an `EndOfStreamException`, and `ExternalReportingService` logs "discarded a malformed inbound datagram" at Debug.

## Decisions

1. **Read the real layout** (R1 of the spec): Time (`ReadUInt32`), snr (`ReadInt32`), delta time (`ReadDouble`), delta frequency (`ReadUInt32`), Mode (`ReadString`), Message (`ReadString`), then `TryReadBool` for Low confidence and the new `TryReadByte` for Modifiers.
2. **Optional trailing fields, tolerant of appended fields** (R2): Low confidence and Modifiers may be absent; bytes after Modifiers are not consulted. Required fields (Time through Message) still throw on truncation and `TryDecode` returns `false`, as today.
3. **Handler untouched** (R3): the decoder returns the same `ReplyMessage(Message, DeltaFrequencyHz)`. If the Developer finds the handler must change, stop and report to QA.
4. **Fixtures are not produced by the parser's own field list** (the fix for the way the old defect hid): the Reply fixture is a literal `byte[]` with a per-field comment, taken from the P1 capture (`qa/rr-study/2026-10-23-1630-qa-p1-gridtracker-reply-capture.md`). The other cases (U2 to U6, U10) are mechanical edits of that array, not a second encoder.
5. **The two existing Reply builders are rewritten** (`WsjtxDatagramTests.TryDecode_Reply_ExtractsMessage`, `ExternalReportingServiceTests.BuildReplyDatagram`, five uses including #251's T4) so that no test in the repository builds a Reply with a `New` byte.

## Risks

- **A client that does send a `New` byte** (none known) would now be rejected or misparsed. The protocol header and the real GridTracker2 capture agree there is none.
- **The real client sends Reply twice per double-click** (two identical datagrams about 158 ms apart). The handler is not changed here; whether it should de-duplicate is not part of this fix.
