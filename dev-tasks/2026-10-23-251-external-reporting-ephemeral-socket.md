# Developer task: #251, external reporting sends and receives on one OS-assigned socket

**Date:** 2026-10-23
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-23: the go for #251 (relayed by the Architect at 14:48Z, confirmed in QA's window), and "yes, write them" for this handoff. Architect spec: `qa/rr-study/2026-10-22-1750-architect-to-qa-spec-251-external-reporting-ephemeral-socket.md` (`arch/ext-reporting-251`, `4ed1dd0f`). QA (k) review with amendments K1 to K8: `qa/rr-study/2026-10-23-1450-qa-k-review-251-external-reporting-ephemeral-socket.md`.
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative.**
**Branch:** `fix/251-ext-reporting-ephemeral-socket`, cut from **`origin/main` `74c75792`** (the spec's `9d5ba635` is out of date; #253 and #254 have landed). Never commit to `main`. **Do not touch `native/`.**
**OpenSpec change:** `openspec/changes/external-reporting-ephemeral-client-socket/` (proposal, design, specs delta, tasks). It is on QA's branch `qa/refset`; copy it onto your branch unchanged (it is part of this change), and say if you edit it.
**Version:** `User-facing: yes`, so a `VERSION` bump is required by G9b (`origin/main` is 0.59, so 0.60 unless QA says otherwise). Commit before running `tools/check_version_bump.py`: it reads the proposal from git.

---

## 0. Why (one paragraph)

With external reporting on and a localhost primary target, GridTracker2 receives nothing when the daemon starts before it. The service binds a socket to the target's own port (D-014 Part A) and sends to that port from that same socket (D-014 Part B); on Windows the datagram goes to the **oldest** socket on the port, which is the daemon's own. The premise behind D-014 is wrong: in the WSJT-X protocol the server holds the well-known port and the client sends from an OS-assigned port. QA checked this on the station on 2026-10-23: GridTracker2 holds 2237, WSJT-X 2.7.0 holds only an ephemeral port.

## 1. Precise scope (file and line numbers are on `origin/main` `74c75792`)

All in `src/OpenWSFZ.Daemon/ExternalReportingService.cs` and `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`.

1. **One socket per primary target, OS-assigned, IPv4.** `new UdpClient(AddressFamily.InterNetwork)` bound to `IPAddress.Any`, port 0. All sends to the primary target go from it and the inbound loop receives on it. **No socket in the service binds a target's port**, with or without `ReuseAddress`.
2. **Stable source port.** Create it when a primary target first exists (index 0 of the enabled targets), dispose it when none does (disabled, empty targets, a non-degraded follower, as today). A change of the primary's host or port **does not** recreate it.
3. **Windows `SIO_UDP_CONNRESET`.** `socket.Client.IOControl(unchecked((int)0x9800000C), new byte[] { 0 }, null)` (this is `-1744830452`), behind `OperatingSystem.IsWindows()`. A failure is a Debug log, never fatal. Note the overload takes a **byte array**, not a bool.
4. **Remove D-014 Part A and Part B.** `_primaryFallbackClient` (`:135`), `_inboundBoundPort` (`:138`), the `desiredInboundPort` rebind block (`:386-419`), the fallback creation and disposal (`:382-383`, `:421-442`), the send-path branch (`:710-724`) and the dispose/rebind race comment (`:730-732`), the teardown (`:955-960`), and what `InboundLoopAsync` reads (`:966-972`). Correct the class remarks (`:41-42`) and the field comments (`:128-138`) to the client/server model. You may rename `_inboundClient`; the loop must still read it under `_targetsLock`.
5. **Unchanged:** secondary targets, the follower/leader relay, inert-by-default (no sockets when disabled or with no targets), `honourInboundCommands` gating, Halt Tx always honoured, the malformed-datagram rule, the callsign suppression filter, the datagram contents, `instanceId`. **No config schema change.**
6. **Confirm and say what you found:** how many places read `_inboundClient` or `_primaryFallbackClient` besides those listed (grep, then list them).

## 2. Tests (test-first; HK-025(k): each must be able to fail)

Real localhost UDP sockets, no mocks of the socket. Each is a `[Fact]` with a `#251` display name; the full table is `tasks.md` section 1 (T1 to T8). In short:

| id | what it proves |
|---|---|
| T1 daemon first | the service starts, then a peer binds the target port (with `ReuseAddress`): the peer receives Status and Decode |
| T2 peer first | as T1 with the order reversed |
| T3 peer restart | the peer socket is replaced while the service runs: the new peer receives |
| T4 replies reach the daemon | Halt Tx and a Reply (with `honourInboundCommands` true) sent to the **datagram's source endpoint** are handled |
| T5 target port free | a bind of the target port succeeds while the service runs |
| T6 peer absent | **Windows only, explicit skip elsewhere.** At least 20 sends to a closed port, then Halt Tx to the source endpoint: handled, loop alive, **and zero "inbound socket error" log entries** (capturing logger). **Show that T6 fails with the `SIO_UDP_CONNRESET` call removed** |
| T7 stable source port | the target's port changed through the config store mid-run: the peer sees the same source port |
| T8 regression | the existing suite for secondary targets, relay, inert-by-default, gating and malformed input passes **unchanged** |

The two D-014 tests (`:462` AC-1, `:538` AC-2) assert the defect's mechanism and are **replaced**; say so in the report. **Waits are positive-condition polls (`OpenWSFZ.TestSupport.Poll.*`) with a timeout, never a fixed delay** (TESTING_STRATEGY section 11; Gate G10). T5 asserts only that the bind succeeds (`ExclusiveAddressUse` semantics differ on Linux and macOS). Do not use `Thread.Sleep`.

## 3. Not in scope

Inbound commands from secondary targets; multicast server addresses; the `leaderUrl` fault (#195); radio control (#252); IPv6 hosts; any `native/` change; any config edit on the station.

## 4. What QA will read (the report)

- The **full unfiltered** `dotnet test OpenWSFZ.slnx`: quote the exact command line and the counts (passed / failed / skipped). A filtered run does not count (HK-022).
- `openspec validate --all --strict`; the G9b result.
- The commit hash(es); the list of replaced and changed tests and why; the T6 mutation result; the grep result of 1.6; anything surprising.
- `git diff --stat -- native/` empty.
- **Stop and tell QA before pushing anything.** QA reviews the commit (HK-039) and commits a `Reviewed-commit:` record before any run on it. QA pushes branches and opens the PR on the Captain's go; the merge is the Captain's.

## 5. After the merge (QA and the Captain, not you)

Live acceptance L-a to L-e on the station with the Captain present (the daemon started before GridTracker, GridTracker restarted while the daemon runs, Halt Tx, Reply only on his say-so, `netstat` shows the daemon not on 2237); #251 closed with the PR link; the next `decoding_improvement` sync carries the fix.
