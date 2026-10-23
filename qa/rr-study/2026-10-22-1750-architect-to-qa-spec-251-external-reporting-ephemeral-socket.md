# Architect to QA: issue #251. External reporting sends and receives on one ephemeral socket

**Stamped:** 2026-10-22 ~17:50Z (`date -u` 17:45:14Z when drafting began). **To: QA** (QA writes the Developer
handoff, HK-015). Branch `arch/ext-reporting-251` (off `origin/main` `9d5ba635`; local).
**The Captain, first-hand in the Architect's window (~17:44Z):** *"now we are actually live and making qso's we need to
fix gh issue #251 ASAP. prepare the specs for qa, don't engage them yet."* ⇒ **Priority: ASAP.** This spec is
**prepared, not issued**: QA starts on it only when the Captain says so.

## 1. The defect (#251, confirmed by QA's test and code reading, 2026-10-22)

`ExternalReportingService` binds a socket to the **primary target's own port** (`ReuseAddress`, D-014 Part A,
`ExternalReportingService.cs:386-419`) and **sends to that port from that same socket** (D-014 Part B, `:703-724`). On
Windows, a unicast datagram to `127.0.0.1:<port>` goes to the **oldest** socket bound to that port. If the daemon starts
before GridTracker, the daemon's own socket is the oldest, so it receives its own Status/Decode datagrams and
GridTracker receives nothing. Today's workaround (GridTracker and the target on 2238, daemon rebound second) breaks
again the moment GridTracker restarts while the daemon runs.

**The root cause is a premise in D-014, not a race.** The class remarks (`:41-42`) say *"WSJT-X convention: the app
listens on the same port it sends to"*. In the WSJT-X UDP protocol, as far as the Architect knows, it is the other way
round. The **server** (GridTracker, JTAlert) binds the well-known port, e.g. 2237. The **client** (WSJT-X, and
OpenWSFZ in its place) sends from an **ephemeral** port, and the server replies to the datagram's source address and
port. Under that model the start-order problem cannot happen, because the client never holds the server's port.
**This premise is checked mechanically in P0 before any code is written. If P0 contradicts it, stop and come back.**

## 2. Requirements (for the Developer, via QA)

- **R1 One socket per primary target, ephemeral, never on the target port.** The primary target (index 0 of the
  enabled targets) gets **one** `UdpClient` bound to `IPAddress.Any`, port **0** (OS-assigned). All outbound datagrams
  to the primary target are sent from it, and the inbound listener (`InboundLoopAsync`) receives on it. No socket in
  the service binds the target's port, with or without `ReuseAddress`.
- **R2 Stable source port.** The socket is created when a primary target first exists and disposed when none does
  (disabled, empty targets, or a non-degraded follower, as today). A change of the primary target's host or port does
  **not** recreate it, so the peer keeps seeing the same source port and the dispose/rebind race noted at `:730-732`
  goes away.
- **R3 Windows ICMP reset (`SIO_UDP_CONNRESET`).** When the peer is not running, each send to a closed localhost port
  makes Windows raise `ConnectionReset` (10054) on the **next receive** on the same socket. With send and receive on
  one socket that is now the normal case (GridTracker closed). On Windows, disable it on the socket with
  `IOControl(SIO_UDP_CONNRESET, false)` (`-1744830452`), guarded by `OperatingSystem.IsWindows()`. The receive loop
  must still survive any `SocketException` (existing behaviour) without a busy spin.
- **R4 What is removed.** Drop D-014 Part A (bind on the target port) and Part B (send through the bound inbound
  socket), together with `_primaryFallbackClient`, `_inboundBoundPort` and the rebind logic in `Reconcile`. The class
  remarks at `:41-42` are corrected to the client/server model.
- **R5 Unchanged.** Secondary targets keep their own outbound-only ephemeral clients and receive nothing, as today.
  The follower/leader relay, the inert-by-default rule (no sockets when disabled or with no targets),
  `honourInboundCommands` gating, Halt Tx always honoured, the malformed-datagram rule, the callsign suppression
  filter, Status/Decode/Clear/Close contents, and `instanceId` all stay as they are. No config schema change: the
  target's `port` still means "where the server listens".
- **R6 OpenSpec.** A change `external-reporting-ephemeral-client-socket`, with a delta to `openspec/specs/
  external-reporting/spec.md`: an added requirement *"The primary target is sent to and listened on from one
  OS-assigned port; the service never binds a target's port"*, with scenarios for both start orders and for a peer
  restart. Any requirement or scenario that encodes D-014's shared bind is modified or removed in that delta.
- **R7 Version.** `VERSION` bump per G9b. No `native/` change, so no shim bump.

## 3. Tests (Developer writes them; QA reviews per HK-039). Real localhost UDP sockets, no mocks of the socket

The two D-014 tests (`ExternalReportingServiceTests.cs:462` AC-1, `:538` AC-2) assert the defect's mechanism, so they
are **replaced**, not kept. New tests, each a `[Fact]` with a `#251` display name:

| id | arrange | assert |
|---|---|---|
| T1 daemon first | service started, then a fake peer binds the target port (with `ReuseAddress`, as GridTracker does) | peer receives a Status and a Decode within 2 intervals |
| T2 peer first | peer bound, then service started | as T1 |
| T3 peer restart | T1, then the peer socket is disposed and a new one binds the same port while the service runs | new peer receives within 2 intervals |
| T4 replies reach the daemon | peer receives a datagram, then sends Halt Tx (and Reply with `honourInboundCommands` true) **to the datagram's source endpoint** | Halt Tx handled; Reply routed, as the existing handler tests define "handled" |
| T5 target port free | service running with a primary target on port P | the test can bind P **exclusively** (`ExclusiveAddressUse = true`, no `ReuseAddress`): the service holds nothing on P |
| T6 peer absent (Windows) | service sends ≥ 20 datagrams to a closed port, then a peer binds and sends Halt Tx to the source endpoint | Halt Tx handled; the receive loop is alive; no error-level log |
| T7 stable source port | primary target's port changed through the config store mid-run | source port seen by the peer is unchanged before and after |
| T8 regression | the existing suite for secondary targets, follower/relay, inert-by-default, gating and malformed input | unchanged and green |

Timing in T1–T7 uses the service's own interval or a test-short interval, with an upper bound in the assert. No
`Thread.Sleep` without a bound (flake rule).

## 4. QA steps

- **P0 Premise check, before the handoff. Minutes, no radio needed.** On the PC, with the daemon stopped or external
  reporting off:
  - Start WSJT-X 2.7.0 (rig "None", or the Captain's config with TX off) reporting to GridTracker on 2237.
  - Read `netstat -ano -p udp` and record which local port WSJT-X's process holds and which GridTracker holds.
  - **Expected:** GridTracker on 2237, WSJT-X on an ephemeral port only.
  - If WSJT-X also holds 2237, the premise is wrong: **stop and report to the Architect.** Nothing beyond process
    names and port numbers is recorded.
  - Needs the Captain's OK for the minutes WSJT-X runs, because the station is live.
- **H1 Handoff** to a Developer session (HK-011), branch `fix/251-ext-reporting-ephemeral-socket` off `origin/main`.
  If the COH-FALLBACK merge (M4) has landed by then, branch off the post-merge `main`.
- **H2 Review** of the diff (HK-039 record), then the unfiltered suite on the Developer's tip.
- **H3 Live acceptance on the station (the Captain's go; he is live, so he picks a moment between QSOs):**
  - **L-a:** set the target back to **2237** and GridTracker to 2237, with the daemon running on the fixed build,
    **started before** GridTracker. GridTracker shows decodes within one cycle.
  - **L-b:** restart GridTracker while the daemon runs. Decodes resume within one cycle.
  - **L-c:** Halt Tx from GridTracker reaches the daemon (daemon log line). Safe to test at any time.
  - **L-d:** Reply from GridTracker (double-click a CQ) reaches the daemon. **It starts a QSO, so only with the
    Captain at the radio and on his say-so.** Otherwise it is recorded NOT EXERCISED and rests on T4.
  - **L-e:** `netstat` shows the daemon not holding 2237.
  - Record each result with its time from `date -u`. No callsigns or message text (NFR-021/HK-037).
- **H4 Merge to `main`** on the Captain's go, with CI green. While CI runs, update and close #251 with the PR link.
- **H5 `decoding_improvement`:** if DI sync 7 (COH-FALLBACK merge spec M6) has not run yet, let it carry this fix as
  well, so one sync does both. Otherwise the next sync picks it up.
- **H6 Station config:** after L-a, the station keeps port 2237, the original. QA reads it back and records it.

## 5. Non-goals

Inbound commands from secondary targets; multicast server addresses (unchanged: a send to a multicast group from an
ephemeral socket works as before); the `leaderUrl` fault (#195); radio control (#252).

## 6. Prediction (to be scored at the ruling)

| id | prediction | P | class |
|---|---|---:|:---:|
| X1 | P0 shows WSJT-X on an ephemeral port only, GridTracker alone on 2237 | 0.85 | C |
| X2 | T1–T7 green on the Developer's first PR tip, with no change to R1–R5 | 0.65 | C |
| X3 | L-a, L-b, L-c, L-e pass on the first live try | 0.75 | C |

*Architect. Docs only; `src/`/`native/` diff empty.*

---

## Amendment 1 (2026-10-23 ~15:0xZ `date -u`): QA's (k) review ACCEPTED IN FULL

**Issued** on the Captain's go, 14:48Z (Architect's window), which he confirmed in QA's window. QA's review is
`qa/rr-study/2026-10-23-1450-qa-k-review-251-external-reporting-ephemeral-socket.md` (`qa/refset`). Every FILE:LINE
above still holds on `main` `74c75792`: `git diff 9d5ba635 74c75792` is empty for both files. All eight points
are adopted, and the text above is to be read with them:

- **A1.1 (K1) R4 touch list completed.** It adds `ExternalReportingService.cs:128-138` (comment + fields
  `_primaryFallbackClient`, `_inboundClient`, `_inboundBoundPort`), `:382-383` and `:421-442` (fallback-client
  creation/disposal in `Reconcile`), `:955-960` (teardown) and `:966-972` (the inbound loop's read of the client).
- **A1.2 (K2) T6 now discriminates.** The loop already swallows every `SocketException` at Debug (`:995`), so as
  first written T6 passed with R3 removed (my error, E34). T6 now also asserts **zero** "inbound socket error" log
  entries after the ≥ 20 sends to the closed port (capturing logger), plus the Halt Tx arriving. **Mutation
  check required:** T6 must FAIL on Windows with the R3 `IOControl` line removed. QA shows this in the HK-039 review.
- **A1.3 (K3) H5.** DI sync 7 ran (PR #255, 2026-10-22 19:43:25Z), so this fix rides **DI sync 8**. H5's
  conditional resolves to its "otherwise" branch.
- **A1.4 (K4) H1.** Branch off `origin/main` `74c75792`.
- **A1.5 (K5) R1/R3 detail.** R1: the client is `AddressFamily.InterNetwork` (IPv4), as before; IPv6 is out of
  scope. R3: `Socket.IOControl(-1744830452 /* 0x9800000C SIO_UDP_CONNRESET */, new byte[] { 0 }, null)`; my
  "`IOControl(SIO_UDP_CONNRESET, false)`" named the wrong signature (E35).
- **A1.6 (K6) cross-platform / flake.** T6 is skipped explicitly, with a stated reason, off Windows. T1–T3 and T7
  wait on a positive condition (`OpenWSFZ.TestSupport.Poll.*`), and the Poll timeout is the upper bound (no fixed
  "2 intervals" sleep). T5 asserts only that the bind of P succeeds (`ExclusiveAddressUse` semantics differ off Windows).
- **A1.7 (K7) behaviour change, recorded as a decision.** After the fix, a peer that sends commands
  **unsolicited** to the target port (not as a reply to one of the daemon's datagrams) no longer reaches the daemon.
  This is the WSJT-X client model, and the daemon sends Status within seconds of start. The OpenSpec delta carries
  one scenario for it, and the PR description and the #251 close note state it. I had not stated it (E38).
- **A1.8 (K8) R6.** The main spec never encoded the shared bind (QA's grep), so the delta is **ADDED-only**. The
  "modify or remove" clause is void (E36). The Developer re-greps before writing.

**Prediction scoring:** **X1 HIT** (P0, QA 14:53:40Z, radio off: GridTracker2 alone on `0.0.0.0:2237`; wsjtx
2.7.0 on `0.0.0.0:64988` only). Limits: no datagram flow observed, and WSJT-X's configured target port was not
read; neither bears on who binds the well-known port. X2 is read against R1–R5 **as amended here** (the
amendments precede any build). X3 is unchanged.

No bar moves; T1–T8 and L-a..L-e are otherwise as written. *Docs only; `src/`/`native/` diff empty.*
