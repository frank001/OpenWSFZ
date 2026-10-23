## 1. Tests first (each must be able to fail; real localhost UDP, no socket mocks)

- [ ] 1.1 T1 daemon first: service started, then a fake peer binds the target port (with `ReuseAddress`); the peer receives a Status and a Decode within the poll timeout.
- [ ] 1.2 T2 peer first: peer bound, then the service started; as T1.
- [ ] 1.3 T3 peer restart: as T1, then the peer socket is disposed and a new one binds the same port while the service runs; the new peer receives.
- [ ] 1.4 T4 replies reach the daemon: the peer receives a datagram, then sends Halt Tx (and a Reply, with `honourInboundCommands` true) to the **source endpoint**; "handled" is as the existing handler tests define it.
- [ ] 1.5 T5 target port free: with a primary target on P the test can bind P (assert only that the bind succeeds; `ExclusiveAddressUse` semantics differ off Windows).
- [ ] 1.6 T6 peer absent, **Windows only, explicit skip elsewhere**: at least 20 sends to a closed port, then a peer binds and sends Halt Tx to the source endpoint; assert Halt Tx handled, loop alive, **and zero "inbound socket error" log entries** (capturing logger). Show that the row fails with the `SIO_UDP_CONNRESET` call removed.
- [ ] 1.7 T7 stable source port: the primary target's port changed through the config store mid-run; the peer sees the same source port before and after.
- [ ] 1.8 T8 regression: the existing suite for secondary targets, follower/relay, inert-by-default, gating and malformed input passes **unchanged** (show the unchanged tests in the diff stat). The two D-014 tests (AC-1 `:462`, AC-2 `:538`) are replaced, and the report says so.
- [ ] 1.9 All waits are `OpenWSFZ.TestSupport.Poll.*` with a timeout; no fixed delay as a synchronisation (TESTING_STRATEGY section 11; Gate G10).

## 2. Implementation

- [ ] 2.1 `ExternalReportingService.Reconcile`: one IPv4 `UdpClient` on `IPAddress.Any`:0 for the primary target; created when a primary first exists, disposed when none does; a changed host or port keeps it (Decisions 1 and 2).
- [ ] 2.2 Remove D-014 Part A and Part B, `_primaryFallbackClient`, `_inboundBoundPort`, the rebind block, the fallback creation and disposal (`:128-138`, `:382-383`, `:386-442`, `:710-732`, `:955-960`, `:966-972`) (Decision 4). Correct the class remarks at `:41-42`.
- [ ] 2.3 Windows: `IOControl(unchecked((int)0x9800000C), new byte[] { 0 }, null)` behind `OperatingSystem.IsWindows()`, never fatal (Decision 3).
- [ ] 2.4 Nothing in `native/`, the web layer, the config schema, the follower/leader relay or the datagram encoding; `git diff --stat` confirms.

## 3. Verification

- [ ] 3.1 `dotnet build`, the **full unfiltered** `dotnet test OpenWSFZ.slnx`; `openspec validate --all --strict`; quote the exact command lines and counts (HK-022).
- [ ] 3.2 `VERSION` bump per G9b (user-facing: yes; `origin/main` is 0.59). Commit before running `check_version_bump.py`; it reads the proposal from git.
- [ ] 3.3 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA reviews (HK-039), runs the mutation checks and the full suite on a clean worktree; the Captain signs off the merge (HK-010).
- [ ] 3.4 Live acceptance on the station, with the Captain (L-a to L-e of the Architect's spec, section 4): started before GridTracker, GridTracker restart, Halt Tx, Reply (only on his say-so), `netstat` shows the daemon not on 2237. Then close #251 with the PR link; the next `decoding_improvement` sync carries the fix.
