## Context

`ExternalReportingService.cs` on `origin/main` `74c75792` (unchanged since `9d5ba635`): the class remarks claim the WSJT-X convention is that the app listens on the port it sends to (`:41-42`); `Reconcile` binds `_inboundClient` to the primary target's port with `ReuseAddress` (`:386-419`, D-014 Part A) and creates `_primaryFallbackClient` when no inbound socket exists (`:421-442`); `SendToAllEnabledAsync` sends to the primary target through `_inboundClient ?? _primaryFallbackClient` (`:710-724`, D-014 Part B, with the dispose/rebind race comment at `:730-732`); `StopAsync`/`DisposeAsync` dispose them (`:955-960`); `InboundLoopAsync` reads `_inboundClient` and swallows every `SocketException` at Debug (`:966-1000`, the log line at `:995`).

## Decisions

1. **One socket, OS-assigned port, never the target's port.** `new UdpClient(AddressFamily.InterNetwork)` bound to `IPAddress.Any`, port 0, as the former bind and the fallback client were IPv4. Used for every send to the primary target and for the receive loop. (Spec R1; K5.)
2. **Stable source port.** Created when `newPrimary` first becomes non-null and disposed when it becomes null (disabled, empty targets, or a non-degraded follower, as today). A change of the primary's host or port keeps the socket. The `ObjectDisposedException` branch in the send path stays as a guard for shutdown. (R2.)
3. **Windows connection reset.** On Windows, `socket.IOControl(unchecked((int)0x9800000C), new byte[] { 0 }, null)` (`SIO_UDP_CONNRESET` = `-1744830452`), guarded by `OperatingSystem.IsWindows()`, wrapped so that a failure is a Debug log and never fatal. The receive loop keeps its catch-all for `SocketException` (no busy spin: the next `ReceiveAsync` after one reset succeeds). (R3; K5.)
4. **Removal.** `_primaryFallbackClient`, `_inboundBoundPort`, the `desiredInboundPort` rebind block, the fallback creation and disposal, and the comments at `:128-138`. `_inboundClient` may be kept under a clearer name (for example `_primaryClient`) at the Developer's choice, but the loop must read it under `_targetsLock` as today. (R4; K1.)
5. **Tests use real localhost UDP sockets, no socket mocks.** The two D-014 tests (`:462` AC-1, `:538` AC-2) assert the defect's mechanism and are **replaced**. Waits are positive-condition polls (`OpenWSFZ.TestSupport.Poll.*`) with a timeout, never a fixed delay (K6, TESTING_STRATEGY section 11). The Windows-only row has an explicit skip elsewhere. (Section 3 of the spec.)
6. **T6 must be able to fail without R3 (K2).** The receive loop already survives a reset, so "loop alive, Halt Tx handled" passes with R3 removed. T6 also asserts that no "inbound socket error" entry was logged after at least 20 sends to the closed port (a capturing logger). On Windows, without R3, those resets surface as exactly those entries.

## Risks

- **A peer that depended on the daemon listening on the target port stops reaching it.** Only replies to the daemon's own datagrams arrive. Accepted: it is the WSJT-X client model, and GridTracker replies to the source (T4 proves it; L-c and L-d prove it live).
- **Windows ICMP reset** if R3 is wrong or fails silently: the receive loop still survives; T6 notices through the log.
- **Cross-platform test semantics.** `ExclusiveAddressUse` and `ReuseAddress` behave differently on Linux and macOS. T5 asserts only that a bind of the target port succeeds; T6 is skipped off Windows.
- **Live acceptance touches the station's GridTracker and WSJT-X set-up** and needs the Captain at the station (L-a to L-e).
