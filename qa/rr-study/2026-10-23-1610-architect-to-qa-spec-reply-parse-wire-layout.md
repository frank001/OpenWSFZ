# Architect to QA: inbound Reply is parsed with the wrong wire layout (GitHub issue: QA files it, number TBD)

**Stamped:** 2026-10-23 ~16:10Z (`date -u` 16:09:10Z when drafting began). **To: QA** (QA files the issue and writes the
Developer handoff, HK-015). Branch `arch/reply-parse` (off `origin/main` `74c75792`; local).
**The Captain, first-hand in the Architect's window (~16:08Z), on "Option A: GitHub issue + Architect spec":** *"option A."*
⇒ **Issued.** QA may start on receipt. Independent of #251, which this spec does **not** hold. The live steps need
#251's build, though (see H1).

## 1. The defect (found by QA in #251 live L-d, 2026-10-23; confirmed in source by the Architect at 16:03Z)

- **Live (QA, build `a920910c`):** with `honourInboundCommands` true and file log level Debug, GridTracker's Reply
  datagrams reached the daemon. Each one was logged *"discarded a malformed inbound datagram"*: 10 between 17:58:47 and
  17:58:52 +02:00.
- **QA control, hand-built datagrams, synthetic `Q1TST`:**
  - A Reply **without** a `New` byte was discarded as malformed (15:59:49Z).
  - The same Reply **with** a `New` byte parsed, and was then "not found" (15:59:52Z).
- **Source:** `src/OpenWSFZ.Daemon/WsjtxDatagram.cs` `DecodeReply` (`:294-310` on `a920910c`; the file is unchanged by
  #251) reads `TryReadBool` "New" before `Time`. Its comment says *"The inbound Reply datagram has the same field
  layout as the outbound Decode datagram"*. That is the wrong premise.
- **The protocol:** WSJT-X `Network/NetworkMessage.hpp`, Reply table, verbatim. Read 2026-10-23 from the master-branch
  mirror `raw.githubusercontent.com/saitohirga/WSJT-X/master/Network/NetworkMessage.hpp`, schema 3. It is not pinned to
  the 2.7.0 tag, and P1 settles that for the client that matters:

  ```
  Reply         In        4                      quint32
                          Id (target unique key) utf8
                          Time                   QTime
                          snr                    qint32
                          Delta time (S)         float (serialized as double)
                          Delta frequency (Hz)   quint32
                          Mode                   utf8
                          Message                utf8
                          Low confidence         bool
                          Modifiers              quint8
  ```

  There is **no `New` field**, and there is a trailing **`Modifiers`** byte (0x00 none, 0x02 SHIFT, 0x04 CTRL, 0x08 ALT,
  0x10 META, 0x20 KEYPAD, 0x40 group switch). QA read the same layout from the TR4W wiki copy.
- **Why the tests never caught it:** both Reply fixtures are built in the daemon's own wrong layout, with a `New` byte.
  They are `WsjtxDatagramTests.cs` `TryDecode_Reply_ExtractsMessage` and `ExternalReportingServiceTests.cs`
  `BuildReplyDatagram` (`:1358`, used by 5 tests and by #251's T4). A test that shares the parser's assumption cannot
  check a wire format. That is ledger E39, the Architect's.
- **Consequence:** Reply from GridTracker has never worked since external reporting shipped. Halt Tx works live (L-c).
- **The other inbound types, checked by the Architect against the same header:**
  - **Halt Tx** (Id, Auto Tx Only bool) matches `DecodeHaltTx`.
  - **Free Text** (Id, Text utf8, Send bool) matches `DecodeFreeText`.
  - **Heartbeat** is not in scope.

## 2. Requirements (for the Developer, via QA)

- **R1 Real layout.** After the header and Id, `DecodeReply` reads, in order:
  1. Time (`quint32`)
  2. snr (`qint32`)
  3. Delta time (8-byte IEEE double)
  4. Delta frequency (`quint32`)
  5. Mode (utf8)
  6. Message (utf8)
  7. Low confidence (bool)
  8. Modifiers (`quint8`)

  There is no `New` field.
- **R2 Trailing fields are tolerant.**
  - **Low confidence and Modifiers are optional.** When they are absent (an older client, or a datagram that ends after
    Message), the Reply still parses. `TryReadBool` is already this pattern, and a `TryReadByte` follows it.
  - **Trailing bytes after Modifiers are ignored,** per the protocol's rule that new fields are appended.
  - **A truncation inside a required field** (Time through Message) still returns `false` from `TryDecode`, as today.
- **R3 Record unchanged.** `InboundMessage.ReplyMessage(string Message, uint DeltaFrequencyHz)` keeps its shape. The
  handler (`ExternalReportingService.HandleReply`, the callsign extraction, `IExternalReplyTarget`) is **not** touched.
  - Modifiers are read and discarded. What OpenWSFZ should do with SHIFT and the like is a separate question, and not
    part of this fix.
  - If the Developer finds the handler must change, **stop and come back** (prediction Y2).
- **R4 Comments tell the truth.**
  - Replace the `DecodeReply` summary with the real layout, citing `NetworkMessage.hpp` (Reply, In, 4).
  - In the class provenance note (`:14-23`), state that Reply, Halt Tx and Free Text have been checked against
    `NetworkMessage.hpp`. Add P1's capture if it was made.
  - Outbound types stay "best-effort". Their status does not change here.
- **R5 Scope.** Only `src/OpenWSFZ.Daemon/WsjtxDatagram.cs` and the two test files. No OpenSpec requirement text
  states the Reply layout today (the Architect grepped `openspec/`). QA decides whether to add an ADDED-only scenario,
  "a Reply laid out per NetworkMessage.hpp parses".

## 3. Tests (Developer writes them; QA reviews per HK-039)

**The rule that fixes E39:** the Reply fixture bytes are **not** produced by any helper that encodes the daemon's own
field list.

- **The fixture is a literal `byte[]`.** Hex, with a per-field comment.
- **It comes from P1's capture when there is one.** It holds the synthetic `Q1TST`, so it may be committed.
- **Otherwise it is written by hand from the header table above.** Its comment cites `NetworkMessage.hpp`.

| id | arrange | assert |
|---|---|---|
| U1 real Reply | the literal fixture: Modifiers 0x00, message `CQ Q1TST JO22`, Δf 1234 | `TryDecode` true; `ReplyMessage` with that message and Δf 1234 |
| U2 Modifiers ignored | U1 with Modifiers 0x02 (SHIFT), then 0x04 | the same result as U1 |
| U3 no Modifiers | U1 with the last byte cut | parses, as U1 |
| U4 no Low confidence, no Modifiers | U1 ending after Message | parses, as U1 |
| U5 truncated required field | U1 cut inside Message, and cut inside Delta time | `TryDecode` false, no throw |
| U6 null Mode | U1 with Mode length `0xFFFFFFFF` | parses (Mode is unused) |
| U7 handler path | `BuildReplyDatagram` in `ExternalReportingServiceTests.cs` rewritten to the real layout; the 5 tests using it (including #251's T4) | unchanged asserts, green |
| U8 old fixture removed | `TryDecode_Reply_ExtractsMessage` rewritten to the real layout (or replaced by U1) | no test in the repo still builds a Reply with a `New` byte. QA greps for it |
| U9 regression | the full unfiltered suite | green |

**Mutation check (QA, at review):** U1 must **fail** on the current `DecodeReply` (with the `New` read put back). If it
passes, U1 is decorative. **Stop and come back.**

## 4. QA steps

- **P1 Capture one real GridTracker Reply. Optional but preferred; minutes; no transmit.**
  - **Probe script.** A throwaway script under `_qa-scratch\reply-capture\` acts as a WSJT-X client from an ephemeral
    socket (Id e.g. `QA-PROBE`, schema 3). It sends GridTracker on 2237 a Heartbeat, a Status, and one Decode
    `CQ Q1TST JO22`.
  - **The Captain double-clicks** that line in GridTracker. GridTracker sends the Reply to the script's source port,
    and the script saves the raw bytes.
  - **Nothing transmits.** The script is not a radio. Run it with the daemon stopped, or with its external reporting
    off, so the only CQ Q1TST row is the probe's.
  - **QA records the structure.** Total length, the offset and length of each field, whether a `New` byte appears
    (expected: no), and whether Modifiers is present (expected: yes, 0x00).
  - **The bytes are synthetic** (`Q1TST`, `QA-PROBE`), so they may become U1's fixture.
  - **If GridTracker won't show the probe's decode,** or the Captain can't spare the moment, skip P1. U1 is then
    hand-built from the header.
  - **Needs the Captain** for the double-click. HK-027: no instrument records GridTracker's outbound Reply, so a human
    actuator is justified.
- **H1 Handoff** to a Developer session (HK-011), on branch `fix/reply-parse-wire-layout`.
  - **If PR #256 (#251) has merged,** branch off the post-merge `main`.
  - **If not,** branch off `fix/251-ext-reporting-ephemeral-socket` tip `a920910c`, and rebase once #256 lands. #251
    rewrote `ExternalReportingServiceTests.cs`, so this avoids a needless conflict. Live L-1 also needs #251's receive
    path.
- **H2 Review:** the HK-039 record including the mutation check, then the unfiltered suite.
- **H3 `pre_merge_check.py`:** run on a clean checkout of the exact tip **before any push**. This is the Captain's
  2026-10-23 rule for `src/` changes.
- **H4 Live acceptance on the station, build with #251 + this fix:**
  - **L-1, safe at any time.** With `honourInboundCommands` true and log level Debug, QA's hand-built Reply in the
    **real** layout (synthetic `Q1TST`, sent to the daemon's source port) is logged *"Reply named 'Q1TST' … not found"*,
    **not** "malformed". This is the exact inverse of QA's 15:59:49Z control.
  - **L-2, Captain at the radio, on his say-so only, because it starts a QSO.** He double-clicks a CQ in GridTracker,
    and the daemon logs the Reply as parsed and engages the CQ. If he does not want to run it, record it **NOT
    EXERCISED**: L-1 plus U1 then carry the parse, and the engage path stays live-unproven.
  - **After either:** restore `honourInboundCommands` false and log level Information, read them back, and record.
  - **Recording:** times from `date -u`. No callsigns or message text from on-air traffic (NFR-021/HK-037); `Q1TST` is
    fine.
- **H5 Merge to `main`** on the Captain's go, with CI green. Close the issue with the PR link.
- **H6 `decoding_improvement`:** the next DI sync carries this fix (with #251 if both are waiting).

## 5. Non-goals

- Acting on Reply Modifiers.
- Outbound datagram layouts. GridTracker displays them correctly live; they get no audit here.
- Schema 3 encoding.
- The station's stale `logging.directory`, a side finding by QA (harmless, gitignored).
- Relaying Reply between leader and follower instances.

## 6. Prediction (to be scored at the ruling)

| id | prediction | P | class |
|---|---|---:|:---:|
| Y1 | P1 (if run) shows GridTracker's Reply in exactly the header layout: no `New` byte, Modifiers present | 0.85 | C |
| Y2 | The fix needs no change outside `WsjtxDatagram.cs` and the two test files (R3 holds) | 0.80 | C |
| Y3 | L-1 passes on the first live try | 0.90 | C |
| Y4 | If L-2 is run, the double-clicked CQ engages on the first try (the engage path has never run live from a real Reply) | 0.60 | H |

*Architect. Docs only; `src/`/`native/` diff empty.*
