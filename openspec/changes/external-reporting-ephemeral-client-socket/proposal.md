**User-facing:** yes

## Why

Issue #251: with external reporting on and the primary target on localhost, GridTracker2 receives nothing whenever the daemon starts **before** it. The station has run on a workaround since 2026-10-22 (GridTracker and the target port moved to 2238 so the daemon binds second), which breaks again the moment GridTracker restarts while the daemon runs.

The cause is a premise in D-014, not a race. `ExternalReportingService` binds a socket to the **primary target's own port** (`ReuseAddress`, D-014 Part A) and sends to that port **from that same socket** (D-014 Part B). On Windows a unicast datagram to `127.0.0.1:<port>` goes to the **oldest** socket bound to the port. If the daemon is first, its own socket receives its own Status and Decode datagrams and GridTracker receives nothing. The class remarks say "WSJT-X convention: the app listens on the same port it sends to". The convention is the other way round: the **server** (GridTracker, JTAlert) holds the well-known port and the **client** (WSJT-X, and OpenWSFZ in its place) sends from an OS-assigned port; the server replies to the datagram's source address and port.

**Premise checked on the station (QA, P0, 2026-10-23 14:53:40Z, radio off):** GridTracker2 holds `0.0.0.0:2237`; WSJT-X 2.7.0 holds `0.0.0.0:64988` only and nothing on 2237. Under the client/server model the start-order problem cannot happen, because the client never holds the server's port.

Architect spec: `qa/rr-study/2026-10-22-1750-architect-to-qa-spec-251-external-reporting-ephemeral-socket.md` (branch `arch/ext-reporting-251`, `4ed1dd0f`). QA (k) review: `qa/rr-study/2026-10-23-1450-qa-k-review-251-external-reporting-ephemeral-socket.md` (amendments K1 to K8 are applied here). The Captain's go: 2026-10-23, via the Architect's window (14:48Z) and confirmed in QA's window.

## What Changes

- The primary target (index 0 of the enabled targets) gets **one** IPv4 `UdpClient` bound to `IPAddress.Any`, port **0** (OS-assigned). All outbound datagrams to the primary target are sent from it, and the inbound listener receives on it. **No socket in the service binds a target's port**, with or without `ReuseAddress`.
- The socket is created when a primary target first exists and disposed when none does. A change of the primary target's host or port does **not** recreate it, so the peer keeps seeing the same source port.
- On Windows the socket disables `SIO_UDP_CONNRESET`, so a send to a closed localhost port does not make the next receive fail with 10054.
- D-014 Part A and Part B are removed, with `_primaryFallbackClient`, `_inboundBoundPort` and the rebind logic in `Reconcile`. The class remarks are corrected to the client/server model.
- **Unchanged:** secondary targets (outbound-only ephemeral clients), the follower/leader relay, inert-by-default, `honourInboundCommands` gating, Halt Tx always honoured, the malformed-datagram rule, the callsign suppression filter, the datagram contents, `instanceId`. No config schema change: a target's `port` still means "where the server listens".
- **Behaviour change to know about:** a peer that sends commands **unsolicited** to the target port (not as a reply to a datagram the daemon sent) no longer reaches the daemon. Only replies to the daemon's own datagrams do, which is how WSJT-X's own protocol works. The daemon sends a Status within seconds of starting.

## Non-goals

Inbound commands from secondary targets; multicast server addresses (a send to a multicast group from an ephemeral socket works as before); the `leaderUrl` fault (#195); radio control (#252); IPv6 hosts (as today).

## Capabilities

### Modified Capabilities

- `external-reporting`: the primary target is sent to and listened on from one OS-assigned port; the service never binds a target's port.

## Impact

`src/OpenWSFZ.Daemon/ExternalReportingService.cs` and `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs` only. No `native/` change, so no shim bump. `VERSION` bump per G9b (user-facing: yes).
