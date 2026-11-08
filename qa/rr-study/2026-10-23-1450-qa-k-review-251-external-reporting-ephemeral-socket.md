# QA (k) review: #251 spec, external reporting on one ephemeral socket

**Stamped:** 2026-10-23 14:50Z (`date -u`). **To: Architect.** QA, branch `qa/refset`.
**Reviewed:** `arch/ext-reporting-251` `4ed1dd0f`, spec `qa/rr-study/2026-10-22-1750-architect-to-qa-spec-251-external-reporting-ephemeral-socket.md`.
**Go:** the Captain, in QA's window 2026-10-23 (~14:5xZ): "yes, go ahead with the review". The Architect relayed his go at 14:48Z; he confirmed it here.
**Read against:** `origin/main` `74c75792` (the spec was written against `9d5ba635`).
**Scope of this note:** step (1) of the spec's order, and the part of P0 that needs no new action. No `src/` change, no OpenSpec change and no dev-task has been written yet.

## Verdict: ACCEPT, with amendments K1 to K7. No refusal on HK-021(k) grounds.

The defect analysis holds against the code. The change set is small and well fenced. One test row (T6) is decorative as written (K2); it is fixable inside the spec.

## 1. FILE:LINE re-check (every reference, on `74c75792`)

`git diff 9d5ba635 74c75792` is **empty** for `src/OpenWSFZ.Daemon/ExternalReportingService.cs` and for `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`, so every number in the spec is still right.

| Spec reference | On `74c75792` | Result |
|---|---|---|
| `:41-42` "WSJT-X convention: listens on the same port it sends to" | `ExternalReportingService.cs:41-42` | ✅ |
| `:386-419` D-014 Part A (bind on the target port, `ReuseAddress`) | `:386-419` (`:405` `ReuseAddress`, `:406` `Bind(IPAddress.Any, port)`) | ✅ |
| `:703-724` D-014 Part B (send through the bound inbound socket) | `:710-724` (`:714` `_inboundClient ?? _primaryFallbackClient`) | ✅ |
| `:730-732` dispose/rebind race comment | `:730-732` | ✅ |
| tests `:462` AC-1, `:538` AC-2 | `ExternalReportingServiceTests.cs:462`, `:538` | ✅ |

**Not named in the spec but touched by R4 (the Developer must change them too):** the fallback-client creation and disposal in `Reconcile` (`:421-442`, and `:382-383`); the teardown in `StopAsync`/`DisposeAsync` (`:955-960`); and the inbound loop's reading of `_inboundClient` (`:966-972`). Fields: `_primaryFallbackClient` (`:135`), `_inboundClient` (`:137`), `_inboundBoundPort` (`:138`); the comment block at `:128-131`.

## 2. Findings

- **K1 (accept, record).** The spec's R4 list is incomplete as above. Add `:128-138`, `:382-383`, `:421-442`, `:955-960`, `:966-972` to the handoff's touch list.
- **K2 (T6 is decorative for R3).** `InboundLoopAsync` already catches every `SocketException` (including 10054), logs at **Debug** ("inbound socket error — continuing") and continues (`:995`). So T6's asserts ("Halt Tx handled, loop alive, no error-level log") also pass **with R3 removed**. Validity is fine, precision is not: the row fires either way. **Amend T6:** also assert that **zero** "inbound socket error" entries were logged after the ≥ 20 sends to the closed port (a capturing logger), and that the Halt Tx arrives. Without R3 on Windows the ICMP resets surface as exactly those entries, so the row then discriminates.
- **K3 (H5 is stale).** DI sync 7 already ran: PR #255 merged 2026-10-22 19:43:25Z. This fix cannot ride that sync; it rides the **next** one (sync 8). Update H5.
- **K4 (H1 branch point).** Branch off `origin/main` `74c75792` (M4 has landed: #253 and #254). The spec's `9d5ba635` is out of date.
- **K5 (R1 and R3 implementation detail).** R1 should say `AddressFamily.InterNetwork` (IPv4), as the former bind and the fallback `new UdpClient()` both are; IPv6 hosts stay out of scope as today. R3: `-1744830452` equals `0x9800000C` (checked); `Socket.IOControl(int, byte[], byte[])` needs a `byte[] {0}` option, not a `bool`. State both in the handoff.
- **K6 (cross-platform and flake rules).** T6 is Windows-only: give it an explicit skip with a reason on other OSes (CI runs three OSes). T1 to T3 and T7 must wait on a positive condition (`OpenWSFZ.TestSupport.Poll.*`), not a fixed "2 intervals" delay; the spec's upper bound should be the Poll timeout. T5's `ExclusiveAddressUse` has different semantics off Windows; assert only that the bind of P succeeds.
- **K7 (behaviour change to record in OpenSpec and the issue).** After this change, a peer that sends commands **unsolicited** to the target port (not as a reply to a datagram) no longer reaches the daemon; only replies to the daemon's own datagrams do. That is the WSJT-X client model, and the daemon sends a Status within seconds of start, so the window is short. Put one scenario for it into the OpenSpec delta so it is a decision, not a surprise.
- **K8 (R6 wording).** `openspec/specs/external-reporting/spec.md` on `main` does not encode the shared bind (grep for D-014, bind, same port, shared, reuse found nothing; it mentions only the default port 2237 and a generic "inbound listener"). The delta is therefore **ADDED-only**; the "modify or remove" clause has nothing to act on. The Developer re-greps before writing the delta.

Nothing in the spec asks for a number from an older build, so HK-038 does not apply.

## 3. P0 (premise check): the half that needs no action

Read at 14:5xZ, `Get-NetUDPEndpoint`, process names and port numbers only:
- **GridTracker2 holds `0.0.0.0:2237`** (and `0.0.0.0:49221`, purpose not checked). It is the only holder of 2237.
- **WSJT-X is not running**, so its client port is **unrecorded**. X1 is therefore NOT yet scored, and the premise is not yet confirmed.

**To finish P0:** the Captain starts WSJT-X 2.7.0 reporting to GridTracker on 2237 (or says so, and QA starts it with TX off), and QA reads `netstat -ano -p udp` once. Minutes, no radio.

## 3a. P0 RESULT (QA, 14:53:40Z `date -u`; the Captain started WSJT-X; the radio was OFF)

`Get-NetUDPEndpoint`, process names and port numbers only:
- **GridTracker2 (pid 37080): `0.0.0.0:2237`** (and `0.0.0.0:49221`).
- **wsjtx (pid 36780): `0.0.0.0:64988` only.** It holds **no** socket on 2237.

Reading: the premise holds on the binding side. The server (GridTracker) holds the well-known port; the client (WSJT-X 2.7.0) holds an OS-assigned port in the dynamic range. **X1: confirmed for the bind** (a prediction of the Architect's; scoring is the Architect's). **Two limits, stated so they are not lost:** (a) the radio was off, so no Status/Decode datagram flow was observed, only the socket the client holds; (b) which target port WSJT-X's UDP Server setting points at was not read, only its local port. Neither changes the premise, which concerns who binds the well-known port.

## 4. Next steps (in the spec's order)

(2) finish P0, on the Captain's word; (3) OpenSpec change `external-reporting-ephemeral-client-socket` and the dev-task, with K1 to K8 applied; (4) Developer session (HK-011); (5) QA review (HK-039); (6) live acceptance with the Captain at the station. The merge is the Captain's (HK-010).
