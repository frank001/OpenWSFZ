# Developer Handoff — gridtracker-udp-reporting: Linux CI failure blocking PR #70

**Date:** 2026-07-12
**Prepared by:** QA Engineer
**Status:** Required fix, blocking merge of `feat/gridtracker-udp-reporting` (PR #70)
**Scope:** One test failure, `ubuntu-latest` only, both CI runs on the PR; Windows and macOS are green.

---

## 1. Context

While preparing to merge PR #70 (after the 2026-07-12 review-fixes pass — D-014 + the absolute
exclusion — had already been reviewed and approved on the strength of a **local, Windows-only**
`dotnet test` run), I checked the PR's own CI status before merging, per standard practice. It is
not green:

- `Build & Test (windows-latest)` — pass
- `Build & Test (macos-latest)` — pass
- `Build & Test (ubuntu-latest)` — **fail**, both duplicate runs, same test
- `Gate G9 — Version governance` — was also failing (unrelated doc-drift from task 9's VERSION
  bump; fixed directly on the branch in commit `fe081c7`, docs-only, no action needed from you)

This document covers the one remaining item: the Linux test failure.

## 2. The failure

`OutboundToPrimaryTarget_UsesSharedInboundPort` (`ExternalReportingServiceTests.cs:315-355`, one
of the two D-014 regression tests added in `c49b81f`) times out on `ubuntu-latest`:

```
D-014 AC-2: outbound sends to the primary target originate from the shared inbound port [FAIL]
System.OperationCanceledException : The operation was canceled.
   at ...UdpClient.<ReceiveAsync>...
   at ExternalReportingServiceTests.OutboundToPrimaryTarget_UsesSharedInboundPort() line 344
```

Line 344 is `var result = await fakePeer.ReceiveAsync(recvCts.Token);` — the 3-second receive
window elapses with `fakePeer` never seeing any datagram at all (not even a Heartbeat/Status burst,
which the test comment notes fires almost immediately). It passes reliably on Windows and macOS.

## 3. Likely root cause — please confirm/investigate, don't just silence the test

The test's own doc comment (and `design.md` Decision 7) already documents an empirically-found
**Windows** platform quirk: when two `UdpClient`s share one local port via `SO_REUSEADDR`, Windows
delivers an incoming unicast datagram to only the *first-bound* socket. The test was written
assuming this generalises — `fakePeer` binds first (line 332, before the daemon starts), so it
"should" win delivery of the daemon's own outbound send to that shared port.

Linux's `SO_REUSEADDR` semantics for UDP are documented (and generally observed) to differ: rather
than first-bind-wins, unicast delivery to a `SO_REUSEADDR`-shared UDP port on Linux has historically
gone to the **last-bound** socket (kernel/version-dependent; this is not the `SO_REUSEPORT`
load-balanced-hash case, which needs that separate socket option and behaves differently again). In
this test, the daemon's own `_inboundClient` binds *second* (inside `Reconcile`, called from
`StartAsync`, after `fakePeer` is already up). If Linux's last-bind-wins holds here, the daemon's
own outbound send — addressed to `127.0.0.1:port`, i.e. to itself — would be received by its own
`_inboundClient`/`InboundLoopAsync`, not by `fakePeer`, which would explain the observed timeout
exactly: `fakePeer` gets nothing, ever, in the 3-second window.

**This may not be purely a test artifact.** If the diagnosis above is right, it implies something
worth confirming for real Linux deployments too: in the realistic scenario this whole feature
targets (GridTracker2 already running on the same host, bound first to the shared port; OpenWSFZ
starts second and shares the port via `ReuseAddress` per D-014 Part A) — on Linux, OpenWSFZ's own
outbound sends to that same loopback port could conceivably be captured by OpenWSFZ's *own*
listener rather than ever reaching GridTracker2's socket, the mirror-image problem to the Windows
finding already documented (which was about *inbound* delivery, not outbound-looped-back delivery).
Please investigate on an actual Linux box (or reason carefully from kernel behaviour if one isn't
available) whether this is real, and if so, add a Decision 7 addendum for Linux symmetric to the
existing Windows one — do not just tweak the test until it's green without settling whether there's
a genuine cross-platform risk here.

## 4. Required fix — make the test assertion deterministic, not a race

Regardless of the investigation above, the test itself needs to stop depending on unspecified
OS/kernel arbitration behaviour for which of two same-port sockets receives a given unicast
datagram — that's inherently unportable. Recommended approach: assert the *sending* socket's own
local port directly, rather than inferring it by racing a second socket to receive the packet over
the wire.

`ExternalReportingServiceTests.cs` already has a reflection helper for exactly this class of check
(`GetInboundClient`, line 229). Something like:

```csharp
[Fact(DisplayName = "D-014 AC-2: outbound sends to the primary target originate from the shared inbound port")]
public async Task OutboundToPrimaryTarget_UsesSharedInboundPort()
{
    // ... existing setup, start the SUT ...

    var inboundClient = GetInboundClient(sut);
    inboundClient.Should().NotBeNull();
    ((IPEndPoint)inboundClient!.Client.LocalEndPoint!).Port.Should().Be(port,
        "the primary target's outbound sends must originate from the shared bound inbound port");

    // If you still want a wire-level proof for the non-contended case (no competing peer bound to
    // the port), that's a legitimate separate/second assertion — just don't have anything else
    // sharing the exact same port while making it, or you're back to racing OS arbitration.
}
```

This sidesteps the platform-dependent race entirely and will pass deterministically on all three
CI platforms. If you also want to keep an end-to-end wire-level proof, do it in a configuration
where nothing else contends for the port (i.e. without `CreateFakePeer` also bound there), so there
is exactly one socket for the OS to deliver to.

## 5. Acceptance Criteria

- [x] Root cause of the Linux failure understood and documented — concluded **genuine Linux
      delivery-ambiguity risk**, not a pure test artifact: reasoned from documented Linux
      `SO_REUSEADDR` UDP semantics (historically last-bind-wins, vs. Windows' first-bind-wins)
      that OpenWSFZ's own outbound send to a same-host peer on the shared port could be delivered
      back to OpenWSFZ's own `_inboundClient` instead of reaching the peer, since OpenWSFZ binds
      second in the realistic startup order. Not confirmed against a real two-process Linux run
      (no live GridTracker2/second peer available in this environment) — logged as an open,
      unconfirmed-on-real-hardware risk in `design.md` Decision 7's new "Linux addendum," carried
      forward alongside the existing tasks 2.6/10.3 no-live-GridTracker2 caveat rather than fixed
      in this pass.
- [x] `OutboundToPrimaryTarget_UsesSharedInboundPort` (or its replacement) passes reliably on all
      three CI platforms — verified via `gh pr checks 70` after pushing: all three `Build & Test`
      jobs pass on both duplicate CI runs, plus Gate G9; no pending/failing checks.
- [x] No other existing test regressed — full `OpenWSFZ.Daemon.Tests` suite re-run locally:
      391/391 passing (same count as before this fix).
- [x] `tasks.md` 10.1's test-count figure updated if the test count changes — not needed, count
      unchanged (391); added a new task 10.4 instead documenting this fix's own investigation and
      verification.
- [x] PR #70's CI is fully green (all `Build & Test` jobs + Gate G9) before requesting re-review —
      confirmed, `gh pr checks 70` exits 0.

## 6. References

- Failing job: https://github.com/frank001/OpenWSFZ/actions/runs/29188067906/job/86637683759
  (and the duplicate run, job `86637681293`)
- `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:236-260` — the existing Windows
  finding's doc comment, immediately above the two D-014 tests.
- `openspec/changes/gridtracker-udp-reporting/design.md` — Decision 7, "Verification status" note.
- `dev-tasks/2026-07-12-gridtracker-udp-reporting-review-fixes.md` §3.3/§3.4 — where this test was
  originally specified.
