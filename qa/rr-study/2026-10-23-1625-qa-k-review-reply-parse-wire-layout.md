# QA (k) review: the Reply-parse spec (inbound Reply read with the wrong wire layout)

**Stamped:** 2026-10-23 ~16:25Z (`date -u` 16:21:44Z at the start of the read). **To: Architect.** QA, branch `qa/refset`.
**Reviewed:** `arch/reply-parse` `8cc90876`, spec `qa/rr-study/2026-10-23-1610-architect-to-qa-spec-reply-parse-wire-layout.md`.
**Go:** the Captain, in QA's window, 2026-10-23 ("1. confirmed", on the Reply fix, option A).
**Read against:** `origin/main` `326a8af7` (PR #256 merged 16:17:50Z; this includes #251 and VERSION 0.60).

## Verdict: ACCEPT, with amendments M1 to M4. No refusal on HK-021(k) grounds.

## 1. FILE:LINE re-check (on `326a8af7`)

| Spec reference | On `origin/main` | Result |
|---|---|---|
| `WsjtxDatagram.cs` `DecodeReply` `:294-310` | method at `:299-310`, its summary comment above it | ✅ |
| class provenance note `:14-23` | `:14-23` ("best-effort" paragraph; Reply, Halt Tx, Free Text named in it) | ✅ |
| `ReplyMessage(string Message, uint DeltaFrequencyHz)` | `:111`, unchanged | ✅ |
| `BuildReplyDatagram` `:1358` | `ExternalReportingServiceTests.cs:1358`; call sites `:580` (#251's T4), `:1304`, `:1345`, `:1981`, `:2025` = **5 uses including T4** (the spec's "5 tests and by T4" reads as 6; the table's U7 says 5 including T4, which is right) | ✅ (wording only) |
| `TryDecode_Reply_ExtractsMessage` | `WsjtxDatagramTests.cs:171`, builds the datagram with `buf.Add(1); // New = true` | ✅ |
| no `TryReadByte` yet | none in the file; `TryReadBool` is the only optional-field reader | ✅ (the Developer adds one) |
| `HandleReply` untouched | `ExternalReportingService.cs:1071`; the case at `:1003` | ✅ |

The only other places that name Reply in `src/` and `tests/` are the ones above (grep: `BuildReplyDatagram`, `TryDecode_Reply`, `MessageType.Reply`, `ReplyMessage`, `DecodeReply`); no third fixture exists.

## 2. Amendments

- **M1 (H1 is now simple).** PR #256 has merged. Branch `fix/reply-parse-wire-layout` off `origin/main` `326a8af7`. Drop the "otherwise branch off a920910c" case.
- **M2 (P1: capture EVERY datagram, with a type histogram).** The Captain's second double-click produced **10 datagrams** discarded as malformed in about 5 seconds (17:58:47 to 17:58:52 +02:00), which is more than one Reply per click. So GridTracker sends several datagrams around one double-click, and QA's earlier wording ("each Reply was discarded") claimed more than the log shows: the log shows 10 datagrams discarded as malformed, type unknown. By the daemon's own rule a datagram of a defined type with no handler (for example HighlightCallsign 13 or Configure 15) returns **unsupported**, not malformed, so a "malformed" one must have failed inside a type that the daemon does decode. That makes Reply the likely cause, not the proven one. **P1 must save every datagram it receives, record the message type of each, and report the histogram**, so that Y1 is scored on the Reply bytes and the extra datagrams are explained.
- **M3 (R2's second clause has no test).** R2 says trailing bytes after Modifiers are ignored. No row U1 to U9 tests it. Add **U10: U1 with extra trailing bytes after Modifiers parses as U1.** Without it a parser that rejects trailing bytes passes the table.
- **M4 (a note for L-2 and Y4).** The daemon engages a Reply only if the named call is a CQ in the daemon's **own** most recent decode batch (`TryEngageExternal`), and the Reply handler first checks the same batch. So L-1's hand-built Reply for the synthetic `Q1TST`, which the daemon never decoded, is correctly logged "not found" (this is the exact inverse of the 15:59:49Z control and is the right pass condition), while L-2 needs a real CQ that the daemon itself decoded and sent to GridTracker. The radio must be on and receiving, the daemon running (not stopped, unlike P1), and the Captain at the radio.

## 3. Checks on the tests (HK-025(k), validity and precision)

- **U1:** validity branch: on the current `DecodeReply` it fails (the `New` read consumes a byte, then `Time` and the rest misalign; the first string length is garbage and the read throws). It fires only on the layout, so it discriminates. QA runs the mutation at review, as the spec says.
- **U2, U3, U4:** precision: each would fail on a parser that insists on a Modifiers byte or a Low confidence byte, and pass on the tolerant parser R2 asks for. They are not decorative.
- **U5:** the truncation row returns false on the current parser too (it fails on any short buffer), so it guards against a *too tolerant* fix, which is the right direction.
- **U6:** null Mode (`0xFFFFFFFF`): `ReadString` already returns null, so it passes on today's code with the right field order and guards the new order. Acceptable.
- **U7, U8:** the greps in U8 are mechanical and QA runs them; today `TryDecode_Reply_ExtractsMessage` and `BuildReplyDatagram` both write the `New` byte.
- **U9:** the full unfiltered suite.
No row fires the same way on both branches of the validity-versus-precision split, so none is decorative.

## 4. Predictions (the Architect's, not scored here)

Y1 (P1 shows the header layout) and Y4 (the first L-2 engages) are the ones I cannot pre-score. Y2 holds on reading: the handler needs no change if `DecodeReply` returns the same `ReplyMessage`. Y3 (L-1 passes first try) holds on reading: the control datagram at 15:59:52Z already took the "not found" path.

## 5. Next

(1) The GitHub issue text goes to the Captain before filing (QA told him so). (2) P1 needs GridTracker up, the daemon stopped, and the Captain's double-click. (3) The OpenSpec scenario (ADDED-only, "a Reply laid out per NetworkMessage.hpp parses") and the dev-task. (4) Developer, then HK-039 review with the U1 mutation, then `pre_merge_check.py` on a clean checkout before any push.
