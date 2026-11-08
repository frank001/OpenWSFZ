# QA: P1, one real GridTracker2 Reply captured (issue #257)

**Stamped:** 2026-10-23 16:25:47Z (`date -u`; the capture ran 16:25:00Z to 16:25:47Z, then the probe was stopped). **To: Architect.** QA, branch `qa/refset`.
**Spec:** `arch/reply-parse` `8cc90876`, section 4, P1. **Issue:** #257 (https://github.com/frank001/OpenWSFZ/issues/257), filed by QA 16:2xZ with the Captain's approval of its text.

## What was done

A throwaway script (`D:\Projects\claude\_qa-scratch\reply-capture\probe.py`, outside git) acted as a WSJT-X client from an ephemeral socket (source port 62178, Id `QA-PROBE`, schema 3). It sent GridTracker2 (listening on 127.0.0.1:2237) a Heartbeat, a Status and one Decode `CQ Q1TST JO22` (synthetic call; delta frequency 1234). The daemon and WSJT-X were stopped, so that row was the only CQ. **Nothing was transmitted: the script is not a radio.** The message layouts were written from `NetworkMessage.hpp`, not from the daemon's encoder. **The Captain double-clicked the row**; GridTracker2 answered the probe's source port. (QA first guessed from the 158 ms gap that GridTracker answered by itself; the Captain corrected that: it was his double-click, one datagram per click. There is no evidence of an auto-reply.)

## Result

**Two datagrams, byte-identical, both type 4 (Reply), schema 3, 68 bytes each, at 16:25:02.820Z and 16:25:02.978Z.** Nothing else came back (no other message type). Raw hex of one:

```
adbccbda 00000003 00000004 00000008 51412d50524f4245 0385cb60 fffffff6 3fb999999999999a 000004d2 00000001 7e 0000000d 4351205131545354204a4f3232 00 00
```

| Offset | Bytes | Field | Value |
|---|---:|---|---|
| 0 | 4 | magic | `0xADBCCBDA` |
| 4 | 4 | schema | 3 |
| 8 | 4 | message type | 4 (Reply) |
| 12 | 4 + 8 | Id (utf8, length 8) | `QA-PROBE` |
| 24 | 4 | Time (QTime, ms since midnight) | 59,100,000 (= 16:25:00) |
| 28 | 4 | snr | -10 |
| 32 | 8 | delta time (double) | 0.1 |
| 40 | 4 | delta frequency | 1234 |
| 44 | 4 + 1 | Mode (utf8) | `~` |
| 49 | 4 + 13 | Message (utf8) | `CQ Q1TST JO22` |
| 66 | 1 | Low confidence | 0 |
| 67 | 1 | Modifiers | 0x00 |

**There is no `New` byte** between the Id and the Time, and **Modifiers is present** (0x00) as the last byte; total 68 bytes, nothing trailing. This is exactly the layout of `NetworkMessage.hpp` (Reply, In, 4): the Architect's Y1 holds (a hit on both of its clauses). It also shows why the daemon rejects it: `DecodeReply` consumes the byte at offset 24 as `New`, so everything after is shifted by one byte and the Mode length reads as garbage.

The bytes hold only synthetic values (`QA-PROBE`, `Q1TST`, `JO22`, delta frequency 1234, snr -10), so they are safe to commit as U1's literal fixture (NFR-021). The raw capture file itself stays in `_qa-scratch\reply-capture\` and is not committed.

## Correction to QA's earlier wording

QA said in the #251 live report that "each Reply" was discarded (10 datagrams, 17:58:47 to 17:58:52 +02:00). The log shows 10 datagrams discarded as malformed. This capture shows that one double-click makes GridTracker send **two** identical Replies about 158 ms apart, so those 10 datagrams are consistent with about five clicks and are Replies; the type of each was not logged then, and is now explained.

## For the Developer

U1's literal fixture is the hex above (the Id may stay `QA-PROBE`). Variants: U2 sets the last byte to 0x02 and 0x04; U3 drops the last byte; U4 drops the last two bytes; U10 (QA's amendment M3) appends extra bytes after Modifiers; U5 cuts inside the Message and inside Delta time.
