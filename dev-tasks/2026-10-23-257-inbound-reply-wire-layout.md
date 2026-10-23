# Developer task: #257, parse the inbound Reply with the real WSJT-X wire layout

**Date:** 2026-10-23
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-23: option A for the Reply defect (Architect spec), confirmed in QA's window ("1. confirmed"), and "the text is fine, let's do it now" for the issue and P1. Architect spec: `qa/rr-study/2026-10-23-1610-architect-to-qa-spec-reply-parse-wire-layout.md` (`arch/reply-parse`, `8cc90876`, pushed). QA (k) review with amendments M1 to M4: `qa/rr-study/2026-10-23-1625-qa-k-review-reply-parse-wire-layout.md`. P1 capture of the real GridTracker2 Reply: `qa/rr-study/2026-10-23-1630-qa-p1-gridtracker-reply-capture.md`.
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative** (QA runs it on a clean checkout before any push, the Captain's rule).
**Branch:** `fix/reply-parse-wire-layout`, cut from **`origin/main`** (`326a8af7` or later; #256 has merged). Never commit to `main`. **Do not touch `native/`.**
**OpenSpec change:** `openspec/changes/inbound-reply-wire-layout/` (proposal, design, specs delta, tasks) on QA's branch `qa/refset` (pushed): copy it onto your branch unchanged and say if you edit it.
**Version:** `User-facing: yes`, so a `VERSION` bump is required by G9b (take the next number from `origin/main`'s `VERSION`). **Set the README.md and REQUIREMENTS.md anchor sentences ("The current release is vX.Y") to the same version in the same commit, and run `python tools/check_version_docs.py` (G9a)**: the last branch failed exactly there.

---

## 0. Why (one paragraph)

`WsjtxDatagram.DecodeReply` (`src/OpenWSFZ.Daemon/WsjtxDatagram.cs:299-310`) reads a leading `New` boolean that the WSJT-X Reply message (type 4) does not have, so every Reply GridTracker2 sends on a double-click is discarded as malformed (issue #257). The real layout, confirmed by QA against GridTracker2 itself on 2026-10-23, is: header, Id, Time (`quint32`), snr (`qint32`), delta time (double), delta frequency (`quint32`), mode (utf8), message (utf8), Low confidence (bool), Modifiers (`quint8`). There is no `New`.

## 1. Precise scope

All in `src/OpenWSFZ.Daemon/WsjtxDatagram.cs` and the two test files, `tests/OpenWSFZ.Daemon.Tests/WsjtxDatagramTests.cs` and `ExternalReportingServiceTests.cs`.

1. **`DecodeReply`:** the real order above. Low confidence via `TryReadBool`; Modifiers via a new `TryReadByte` that follows `TryReadBool` (returns false at the end of the buffer instead of throwing). **Both are optional; bytes after Modifiers are ignored.** A truncation inside Time through Message still makes `TryDecode` return `false` (the existing catch does it).
2. **Comments tell the truth:** replace the `DecodeReply` summary with the real layout, citing `NetworkMessage.hpp` (Reply, In, 4); in the class provenance note (`:14-23`) state that Reply, Halt Tx and Free Text were checked against `NetworkMessage.hpp` and Reply also against a real GridTracker2 capture (P1). Outbound types stay "best-effort".
3. **Not changed:** `InboundMessage.ReplyMessage(string Message, uint DeltaFrequencyHz)`, `ExternalReportingService.HandleReply`, the callsign extraction, `IExternalReplyTarget`, Halt Tx and Free Text. Modifiers are read and discarded. **If you find the handler must change, stop and tell QA.**
4. **Confirm and say what you found:** a grep over `src/` and `tests/` for every place that builds or reads a Reply (QA found `BuildReplyDatagram` at `ExternalReportingServiceTests.cs:1358` with five uses including #251's T4, and `TryDecode_Reply_ExtractsMessage` at `WsjtxDatagramTests.cs:171`).

## 2. Tests (test-first; HK-025(k): each must be able to fail)

**The rule that fixes the way this defect hid:** the Reply fixture bytes are a **literal `byte[]`** (hex with a per-field comment), **not** produced by any helper that encodes the daemon's own field list. The U1 fixture is the P1 capture, 68 bytes:

```
adbccbda 00000003 00000004 00000008 51412d50524f4245 0385cb60 fffffff6 3fb999999999999a 000004d2 00000001 7e 0000000d 4351205131545354204a4f3232 00 00
```
(magic, schema 3, type 4, Id `QA-PROBE`, Time 59,100,000, snr -10, delta time 0.1, delta frequency 1234, Mode `~`, message `CQ Q1TST JO22`, Low confidence 0, Modifiers 0.) The bytes are synthetic and safe to commit.

| id | what it proves |
|---|---|
| U1 real Reply | the literal fixture: `TryDecode` true, `ReplyMessage` message `CQ Q1TST JO22`, delta frequency 1234. **Must fail on the current `DecodeReply`: show it** |
| U2 Modifiers ignored | U1 with the last byte 0x02 and then 0x04: same result as U1 |
| U3 no Modifiers | U1 with the last byte cut: parses as U1 |
| U4 no Low confidence, no Modifiers | U1 ending after the message: parses as U1 |
| U5 truncated required field | U1 cut inside the message and cut inside delta time: `TryDecode` false, no throw |
| U6 null Mode | U1 with Mode length `0xFFFFFFFF` and no Mode bytes: parses |
| U7 handler path | `BuildReplyDatagram` rewritten to the real layout; the five tests that use it (including #251's T4) keep their assertions and pass |
| U8 old fixture removed | `TryDecode_Reply_ExtractsMessage` rewritten (or replaced by U1). **No test in the repo may still build a Reply with a `New` byte**: QA greps for it |
| U9 regression | the full unfiltered suite |
| **U10 appended bytes (QA's amendment M3)** | U1 with extra bytes after Modifiers: parses as U1. Without it nothing tests R2's "ignore trailing bytes" |

Waits, if any, are `OpenWSFZ.TestSupport.Poll.*` with a timeout; no fixed delays.

## 3. Not in scope

Acting on Reply Modifiers; any outbound datagram layout; schema 3 encoding; leader/follower Reply relay; de-duplicating the two identical Replies GridTracker2 sends per double-click (a separate question); any `native/` change; any station config edit.

## 4. What QA will read (the report)

- The **full unfiltered** `dotnet test OpenWSFZ.slnx`: the exact command line and the counts (passed / failed / skipped); a filtered run does not count (HK-022).
- `openspec validate --all --strict`; `check_version_docs.py` (G9a) and `check_version_bump.py` (G9b).
- The commit hash(es); the list of replaced and changed tests and why; the U1 failure on the old `DecodeReply`; the grep result of 1.4; anything surprising.
- `git diff --stat -- native` empty.
- **Stop and tell QA before pushing anything.** QA reviews the commit (HK-039) with the U1 mutation (the `New` read put back must make U1 fail), runs `pre_merge_check.py` on a clean checkout of the exact tip before any push, then asks the Captain for the push go. The merge is the Captain's.

## 5. After the merge (QA and the Captain, not you)

Live acceptance on the station with the fixed build: **L-1** (QA's hand-built real-layout Reply for the synthetic call is logged "not found", not "malformed"; safe at any time, with `honourInboundCommands` true and Debug logging, then restored) and **L-2** (a GridTracker double-click on a CQ that the daemon itself decoded engages a QSO: only with the Captain at the radio and on his say-so, otherwise NOT EXERCISED). Close #257 with the PR link; the next `decoding_improvement` sync carries the fix.
