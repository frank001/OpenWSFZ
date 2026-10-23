# QA code review: #257, inbound Reply parsed with the real WSJT-X wire layout, `6ab44e30f4676ea13c32d8806d347b2008b2a53c` (HK-039 record)

Reviewed-commit: 6ab44e30f4676ea13c32d8806d347b2008b2a53c

Verdict: APPROVED with ONE required cosmetic change (a comment line in `WsjtxDatagramTests.cs` has double-encoded characters; see "Required change"). The code and the tests are right. QA's `pre_merge_check.py` runs on the exact tip before any push (the Captain's rule); nothing is pushed.

**Stamped:** 2026-10-23, `date -u` ~16:55Z at the start of the run. **Reviewer:** QA. **Task:** `dev-tasks/2026-10-23-257-inbound-reply-wire-layout.md` (`304e2524`, A1.5 `65cbf8a0`). **Commit:** branch `fix/reply-parse-wire-layout`, one commit off `origin/main` `326a8af7`, local in the Developer's worktree. 11 files: `VERSION` (0.61), `README.md`, `REQUIREMENTS.md`, `WsjtxDatagram.cs`, `WsjtxDatagramTests.cs`, `ExternalReportingServiceTests.cs`, and the 5 OpenSpec files.

## What I checked, and what I found

| Check | Result |
|---|---|
| Parent and scope | One parent `326a8af7`. `git diff --stat origin/main 6ab44e30 -- native` is empty. Only the three C# files named in the task, VERSION, the two doc anchors and the OpenSpec change |
| Source (`WsjtxDatagram.cs`, +35/-17) | `DecodeReply` reads Time, snr, delta time, delta frequency, Mode, Message, then Low confidence (`TryReadBool`) and Modifiers (new `Reader.TryReadByte`), both optional, nothing after them consulted. The `New` read is gone. `TryReadByte` follows `TryReadBool` exactly (returns false at the end of the buffer). A truncation inside Time to Message still throws and `TryDecode` returns false |
| Handler untouched | `ExternalReportingService.cs` is not in the diff; `ReplyMessage`, `IExternalReplyTarget` unchanged. The Developer found no need to change them (the Architect's Y2 holds so far) |
| Comments | The `DecodeReply` summary now gives the real layout and cites `NetworkMessage.hpp` (Reply, In, 4) and the capture; the class provenance note says Reply, Halt Tx and Free Text were checked against the header and Reply against a real GridTracker2 capture, the other richer types stay best-effort. Accurate |
| Fixtures | U1 is the 68-byte P1 capture as a literal hex string with a per-field comment (it matches `qa/rr-study/2026-10-23-1630-…` byte for byte). U2 to U6 and U10 are mechanical cuts and edits of that array. No helper shares the parser's field list. U5 cuts at 60 (inside the message, bytes 53 to 65) and 36 (inside delta time, bytes 32 to 39): both inside required fields, as intended |
| `BuildReplyDatagram` | Rewritten as a literal hex prefix (header through Mode `~`), then the message length and UTF-8 bytes, then the literal trailer `0000` (Low confidence, Modifiers). No `New` byte. The five callers (`:580` #251's T4, `:1304`, `:1345`, `:1981`, `:2025`) are unchanged in their assertions |
| No New-byte Reply fixture left | `grep` over `src/` and `tests/`: `MessageType.Reply` only at `WsjtxDatagram.cs:269` (dispatch); `BuildReplyDatagram` defined once, five call sites; the old `TryDecode_Reply_ExtractsMessage` is replaced by U1. The only "New" left in `WsjtxDatagramTests.cs` is U1's display name "(no New byte)" |
| OpenSpec | Compared by md5 against `qa/refset`: `.openspec.yaml`, `design.md`, `proposal.md` and `specs/external-reporting/spec.md` are **identical** to QA's change; `tasks.md` is identical to QA's version at `304e2524` and lacks only the one sentence QA added later in `65cbf8a0` (the Architect's A1.5: record what the daemon did with the second identical Reply at L-2). That sentence is already in the dev-task, so this is not a required change; the Developer may copy `tasks.md` from `qa/refset` `65cbf8a0` in the same fix commit if convenient. `openspec validate --all --strict` passes per the Developer; QA's own run is inside `pre_merge_check.py` |

## Mutation check (QA, the spec's U1 requirement)

Clean detached checkout of exactly `6ab44e30` (`D:\Projects\claude\_qa-scratch\257-review\tree`), Windows. Put `_ = r.TryReadBool(out _); // New` back as the first line of `DecodeReply` (the old parser), run the Daemon test project with the filter `DisplayName~#257|FullyQualifiedName~WsjtxDatagramTests|FullyQualifiedName~ExternalReportingServiceTests`: **11 failed, 69 passed.** The failures: **U1, U2 (both cases), U3, U4, U6, U10, and the four handler-path tests that use `BuildReplyDatagram` including #251's T4.** U5 passes either way (it only asserts rejection without a throw), as the Developer said; it guards against a too-tolerant fix. U1 is therefore not decorative. The mutation was reverted (`git status` clean).

## Required change (cosmetic, one line)

`tests/OpenWSFZ.Daemon.Tests/WsjtxDatagramTests.cs` line 168 in the commit reads `// â”€â”€ Decode: Reply (#257) â”€â€¦`: the box-drawing characters of the original comment (`// ── Decode: Reply …`, bytes `e2 94 80`) were written back double-encoded. It compiles and changes no behaviour, but it is an encoding regression in a file the repository keeps in UTF-8 (no other changed file has it; `ExternalReportingServiceTests.cs` and `WsjtxDatagram.cs` are clean). **Restore the proper characters or use plain ASCII dashes on that line, as a new commit on top.** QA will review the delta (one line) and re-run `pre_merge_check.py` on the new tip.

## Next

The Developer fixes line 168. QA runs the full pre-merge check on the exact new tip, including the Linux/WSL leg (a run on `6ab44e30` is in progress and will say now if anything else needs fixing in the same round), then asks the Captain for the push go. Live L-1 and L-2 follow the merge and a redeploy.
