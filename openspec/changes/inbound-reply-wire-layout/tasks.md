## 1. Tests first (each must be able to fail; fixtures are literal byte arrays, never a helper that shares the parser's field list)

- [ ] 1.1 **U1 real Reply:** the literal 68-byte fixture from the P1 capture (hex in `qa/rr-study/2026-10-23-1630-qa-p1-gridtracker-reply-capture.md`, per-field comment, citing `NetworkMessage.hpp`): `TryDecode` true; `ReplyMessage` with message `CQ Q1TST JO22` and delta frequency 1234. **It must fail on the current `DecodeReply`** (show it).
- [ ] 1.2 **U2 Modifiers ignored:** U1 with the last byte 0x02, then 0x04: the same result as U1.
- [ ] 1.3 **U3 no Modifiers:** U1 with the last byte cut: parses as U1.
- [ ] 1.4 **U4 no Low confidence and no Modifiers:** U1 ending after the message: parses as U1.
- [ ] 1.5 **U5 truncation:** U1 cut inside the message and cut inside delta time: `TryDecode` false, no throw.
- [ ] 1.6 **U6 null Mode:** U1 with the Mode length `0xFFFFFFFF` (and its bytes removed): parses (Mode is unused).
- [ ] 1.7 **U10 appended bytes:** U1 with extra trailing bytes after Modifiers: parses as U1.
- [ ] 1.8 **U7 handler path:** `ExternalReportingServiceTests.BuildReplyDatagram` rewritten to the real layout (from the literal fixture, with the message substituted by a literal per case, or one literal array per message); the five tests that use it (including #251's T4) keep their assertions and pass.
- [ ] 1.9 **U8 old fixture removed:** `WsjtxDatagramTests.TryDecode_Reply_ExtractsMessage` rewritten to the real layout or replaced by U1. `grep` that no test in the repo still builds a Reply with a `New` byte.
- [ ] 1.10 **U9 regression:** the full unfiltered `dotnet test OpenWSFZ.slnx`.

## 2. Implementation

- [ ] 2.1 `DecodeReply`: the real field order (Decision 1), Low confidence via `TryReadBool`, Modifiers via a new `TryReadByte` (Decisions 1 and 2).
- [ ] 2.2 Comments: the `DecodeReply` summary and the class provenance note, as in the proposal.
- [ ] 2.3 Nothing outside `WsjtxDatagram.cs` and the two test files; the handler is untouched (Decision 3). `git diff --stat -- native` empty.

## 3. Verification

- [ ] 3.1 `dotnet build`, the full unfiltered `dotnet test OpenWSFZ.slnx`; `openspec validate --all --strict`; quote the exact command lines and counts (HK-022).
- [ ] 3.2 `VERSION` bump per G9b (user-facing: yes) from the `origin/main` value, with the README and REQUIREMENTS anchors set to the same version (G9a: `python tools/check_version_docs.py`). Commit before running `check_version_bump.py`.
- [ ] 3.3 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA reviews (HK-039) including the U1 mutation (the `New` read put back must make U1 fail), runs `pre_merge_check.py` on a clean checkout of the exact tip BEFORE any push (the Captain's rule), then asks the Captain for the push go; the merge is his (HK-010).
- [ ] 3.4 Live acceptance on the station with the fixed build: L-1 (QA's hand-built real-layout Reply for the synthetic call is logged "not found", not "malformed") and L-2 (a GridTracker double-click on a CQ the daemon itself decoded engages a QSO; only with the Captain at the radio and on his say-so, otherwise recorded NOT EXERCISED).
