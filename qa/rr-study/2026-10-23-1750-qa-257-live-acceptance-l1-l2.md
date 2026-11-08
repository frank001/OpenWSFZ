# QA: #257 live acceptance, L-1 and L-2 (the inbound Reply, on the station)

**Stamped:** 2026-10-23 16:49Z (`date -u`). **To: Architect.** QA, branch `qa/refset`.
**Build:** `fix/reply-parse-wire-layout` tip `e8ef95448ab9321af7c5ff8d38f7d7d3b4829b85` (VERSION 0.61, shim 20260069), deployed to `D:\Projects\claude\_run-main` at 16:44:11Z, daemon started 16:44:26Z (pid 13540, OS-assigned port 57118), GridTracker2 holding 2237. **HK-039 record for this tip:** `qa/rr-study/2026-10-23-1700-qa-code-review-257-reply-wire-layout-6ab44e30.md` (addendum, `3316d9d6`). The branch is NOT pushed and not merged: this ran on the local build, the Captain's go ("start the daemon that is about to be pushed").
**Go:** the Captain, in QA's window: "1. go" for L-1 and "run L-2" for L-2.
**Recording rules:** times from `date -u`/the daemon log (+02:00 local = UTC+2). No callsign of an on-air station is recorded here (NFR-021/HK-037): it appears as `<call>`. The operator's own call is allowed. The daemon logs are under `D:\Projects\claude\OpenWSFZ\artefacts\20260914_1822_rr-study-s1s8\daemon-logs` (the station's stale log directory; each save of the logging setting starts a new file, so the evidence is across `…T164527Z`, `…T164543Z`, `…T164621Z` and later).

## L-1: PASS (the safe step)

With `honourInboundCommands` true and file log level Debug (set 16:45:27Z), QA sent the real 68-byte GridTracker2 Reply (the P1 capture, synthetic `Q1TST`) to the daemon's port at 16:45:30.451Z. Log, 18:45:30.458 and .459 +02:00 (16:45:30.458Z): `Reply named 'Q1TST' which was not found in this instance's own current decode batch …` and `TryEngageExternal: ignoring external reply — 'Q1TST' is not present as a CQ in the most recent decode batch.` **Not "malformed"; zero "malformed inbound datagram" lines in the session's log.** This is the exact inverse of the 15:59:49Z control (the same layout was rejected on the old build). Y3 (L-1 passes first try): HIT. Config restored 16:45:43Z.

## L-2: PASS, and the daemon transmitted three times (the Captain was at the radio)

`honourInboundCommands` true and Debug set 16:46:21Z; the daemon capturing and decoding (cycle 16:46:15: 13 displayed). The Captain double-clicked one CQ in GridTracker2's Call Roster. Daemon log (18:xx +02:00; UTC = minus 2 h):

| UTC | Event |
|---|---|
| 16:46:49.872 | First Reply parsed and routed: `TryEngageExternal: engaging '<call>' at 1997 Hz via external reply` |
| 16:46:49.873 to .878 | `QsoAnswererService: pending CQ target '<call>' … answering at B phase`; `HoldTxFreq=true — transmitting at operator-set 2481 Hz`; watchdog armed 60 min; state TxAnswer; `TX → "<call> PD2FZ JO33"` |
| 16:46:49.890 | PTT asserted (RTS), TX audio 485,508 samples (10,115 ms) |
| **16:46:50.000** | **The SECOND identical Reply (128 ms after the first): `ignoring external reply for '<call>' — not Idle (state="TxAnswer")`: ignored harmlessly, no second engagement, no error** (the Architect's A1.5) |
| 16:47:00.203 | PTT released; TX complete; state WaitReport |
| 16:47:15.613 to 16:47:28.456 | no response, retry 1/3: second transmission, PTT 16:47:15.617 to 16:47:28.456 |
| 16:47:45.624 to 16:47:58.449 | no response, retry 2/3: third transmission, PTT 16:47:45.629 to 16:47:58.449 |
| 16:47:58.468 | The Captain pressed Halt TX in GridTracker2: `Halt Tx received — aborting any in-progress transmission.` |
| 16:47:58.482 | `aborted to Idle (was: "WaitReport")`; PTT was already released at 16:47:58.449 |

**Three transmissions (KeyDown 3, KeyUp 3), no response from the other station, stopped by the Captain.** The engage path from a real Reply, which the Architect's Y4 called 0.6 and "never run live", **engaged on the first try: Y4 HIT.** Y2 (no change outside `WsjtxDatagram.cs` and the two test files): holds on the reviewed commit; the handler engaged without a change.

**Config restored 16:48:37.250Z, read back:** `honourInboundCommands` false, file log level Information, target `127.0.0.1:2237`, fallback true, depth Deep, threads 0; the daemon still pid 13540, port 57118.

## Two observations (descriptive, not gates, not part of #257; for the Architect)

- **O1: a misleading log line.** For a CQ that was then engaged, the handler first logged `Reply named '<call>' which was not found in this instance's own current decode batch …`. The same Reply was then engaged by `TryEngageExternal`, which found the CQ in its own recent batch. So the handler's "not found" check and the answerer's "present as a CQ in the most recent decode batch" check look at different data (or at different moments). The wording says the Reply was not routed; it was. QA did not trace the cause.
- **O2: late-start transmission.** The first transmission started 4.9 s into its 15-second cycle (`answering at B phase`, PTT at 16:46:49.890 against a slot start at :45) with the audio shortened to 10,115 ms. QA has not checked this against the design; it is existing answerer behaviour and unrelated to the Reply parser.

## Where this leaves #257

Parse fixed (U1 to U10, L-1), routed and engaged live (L-2), the second Reply is ignored harmlessly (A1.5), Halt TX works (L-c earlier and again here). **Not done:** the push, the CI run and the PR. The Captain decides those.
