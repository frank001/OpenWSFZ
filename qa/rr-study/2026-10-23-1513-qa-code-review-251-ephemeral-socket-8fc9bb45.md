# QA code review: #251, external reporting on one OS-assigned socket, `8fc9bb4521e67a4d477f69ccdfcb076bbe1128f5` (HK-039 record)

Reviewed-commit: 8fc9bb4521e67a4d477f69ccdfcb076bbe1128f5

Verdict: APPROVED (no change required). Nothing is pushed. Live acceptance (L-a to L-e) needs the Captain at the station and has not been done; the merge is the Captain's (HK-010).

**Stamped:** 2026-10-23T15:13:37Z by `date -u`. **Reviewer:** QA. **Task:** `dev-tasks/2026-10-23-251-external-reporting-ephemeral-socket.md` (`72b8c0a1` on `qa/refset`). **Commit:** branch `fix/251-ext-reporting-ephemeral-socket`, one commit off `origin/main` `74c75792`, local in the Developer's worktree. 8 files: `VERSION`, `ExternalReportingService.cs`, `ExternalReportingServiceTests.cs`, and the 5 OpenSpec files.

## What I checked, and what I found

| Check | Result |
|---|---|
| Parent and scope | One parent `74c75792`. `git diff --stat 74c75792 8fc9bb45 -- native` is empty. Only the two named C# files, `VERSION` 0.59 to 0.60 and the OpenSpec change |
| OpenSpec files | All five are **byte-identical** to `qa/refset` (`cmp` on each) |
| R1 one socket | `new UdpClient(AddressFamily.InterNetwork)` bound to `IPAddress.Any`:0, created when a primary exists (`Reconcile`), used for every send to the primary and by `InboundLoopAsync`. No code path binds a target's port |
| R2 stable source port | `_primaryTarget` is set on every call; the socket is created only when `_inboundClient is null` and disposed only when `newPrimary is null`; a changed host or port keeps it |
| R3 | `IOControl(unchecked((int)0x9800000C), [0], null)` behind `OperatingSystem.IsWindows()`, in try/catch with a Debug log. `[0]` is the same `byte[]` as `new byte[] { 0 }` |
| R4 removal | `_primaryFallbackClient`, `_inboundBoundPort`, the rebind block, fallback creation and disposal, the send-path branch, the teardown lines and the D-014 comments are gone. Class remarks now say client/server. The Developer's grep: nothing outside the one file reads either field (I confirmed in `src/` and `tests/`) |
| R5 unchanged | Secondary targets, relay, gating, Halt Tx, malformed rule, filter and datagram contents are not in the diff |
| Failure to create the socket | Warning logged; sends to the primary and inbound commands are off until a config change retries. Same weakness as the old bind failure, no worse. Accepted |
| Races | Dispose while the loop is in `ReceiveAsync` is caught as `ObjectDisposedException`; the loop re-reads `_inboundClient` under `_targetsLock` as before |

## The deviation the Developer asked me to look at first

The 11 existing inbound tests (Halt Tx x2, malformed, Reply x2, Free Text, Close, the follower-relay Halt Tx pair, the two relay-leak tests) now send to `GetInboundEndpoint(sut)`, the daemon's own socket, instead of the target port. I read all 11 hunks: **only the destination changed; no assertion changed.** This is correct: the daemon no longer listens on the target port, and a peer's real behaviour is to reply to the source, which T4 proves separately. **My handoff was wrong to say the existing suite "passes unchanged" (T8); my K1 touch list did not name the tests that address the target port. Accepted as the necessary consequence of the fix; the error is QA's.** The secondary, relay, inert-by-default, gating and Disabled tests are textually unchanged.

## Tests: do they discriminate? (HK-025(k), run by QA)

Full unfiltered `dotnet test OpenWSFZ.slnx` on a clean detached worktree at the exact commit (`D:\Projects\claude\_qa-scratch\251-review\tree`), Windows, exit 0:

| Assembly | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Ft8 | 580 | 0 | 0 |
| Daemon | 784 | 0 | 0 |
| Web | 402 | 0 | 0 |
| Config | 170 | 0 | 0 |
| Rig | 41 | 0 | 0 |
| Audio | 40 | 0 | 0 |
| Traceability | 34 | 0 | 0 |
| LicenseInventory | 24 | 0 | 0 |
| TestSupport | 12 | 0 | 0 |
| E2E | 9 | 0 | 0 |
| **Total** | **2096** | **0** | **0** |

This equals the Developer's counts. Log: `D:\Projects\claude\_qa-scratch\251-review\fulltest.log`.

**Mutation 1 (the Architect's addition to K2): T6 with the `DisableUdpConnectionReset(client)` call commented out.** Filter `DisplayName~#251`, Daemon tests: **T6 FAILS** ("Expected ... to be empty ... found 'external-reporting: inbound socket error — continuing.'"), **T1 to T5 and T7 pass** (6 passed, 1 failed). T6 therefore fires on R3 alone.

**Mutation 2: the new tests against the OLD service source** (`74c75792`'s `ExternalReportingService.cs`, same filter): **T1, T3, T4, T5, T7 FAIL; T2 and T6 pass.** T2 passes on the old code by design (a peer bound first is the oldest socket on Windows, so it already received). T6 passes on the old code **vacuously** (the old socket was bound to the closed port itself, so it never took an ICMP error). Both are the Developer's statements, and both are reproduced here. T6's job is R3, and Mutation 1 shows it does that.

Both scratch edits were reverted (`git status` clean).

## Notes (none requires a change)

1. **T6 reports "passed" on Linux and macOS, not "skipped"** (early `return`, the repo's convention in `CaptureManagerTests`; xunit 2.9.3 has no runtime skip). Accepted. Anyone reading a Linux CI run must know T6 proved nothing there.
2. **Not exercised:** Linux and macOS (no run here; CI on a push is the check), and the live path with GridTracker (L-a to L-e). `T2`/`T6` Windows-only semantics are as above.
3. **Exposure, unchanged:** the socket binds every interface (`IPAddress.Any`), as the old one did; an OS-assigned port is harder to guess than 2237. A loopback-only bind for a localhost target would be tighter, but LAN and multicast targets need the wide bind. Not a #251 matter; the Architect may want a separate line.
4. The class remarks and field comments are accurate; the two stale doc comments on `GetInboundClient`/`WaitForInboundBoundAsync` were reworded correctly.

## Next

Push the branch so CI runs on three OSes (needs the Captain's go; QA pushes for the Developer). Then, on the Captain's go for a PR: open it with CI green. Live acceptance L-a to L-e at the station with the Captain; close #251 with the PR link; the next `decoding_improvement` sync carries the fix.
