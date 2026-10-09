# Developer handoff: three CI flake fixes (test-only)

**Date:** 2026-10-08. **From:** QA. **To:** Developer. **Priority:** normal (after the OSD-FIX work; none of these blocks a merge). **Authorised:** the Captain, 2026-10-08, QA's window: *"hand the flake fixes to the developer"*. That also releases the hold on item 1 (the WebSocket fix, held 2026-10-05: "tell the developer to hold"); QA reads the plural as covering it and says so here so you can check with the Captain if in doubt.

All three are **test-only** (`tests/`). No `src/` or `native/` change is expected; if a fix needs one, stop and tell QA.

## Branch

One branch per fix is cleanest (they touch different files and may merge separately): `fix/flake-early-decode-ws` (item 1, start from your local WIP commit on `fix/early-decode-ws-subscribe-race`), `fix/flake-daemon-startup-timing` (item 2), `fix/flake-qso-answerer-a01-2-2` (item 3). Each off the current `origin/main`. NEVER commit to `main`. QA pushes and opens PRs on the Captain's go.

## The standard for a flake fix

`TESTING_STRATEGY.md` §11 (read it): wait on a **positive condition** (`OpenWSFZ.TestSupport.Poll.*`), never a fixed delay; "queue empty" is not "processed"; a wall-time bound is a delay literal in disguise. For each fix give **before/after loop evidence** (at least 200 iterations of the single test in cold processes; if it does not reproduce on the unfixed binary, say so plainly: these have shown only on loaded CI runners), **one mutation** that makes the new test fail, and a **sibling check** (grep the same file for the same pattern; fix or list).

## Item 1: FR-083 6.2f, the WebSocket flake (CI #1079 and two earlier occurrences)

`tests/OpenWSFZ.Web.Tests/EarlyDecodeProtocolTests.cs`, `Client_ReceivesEarlyFrame_AndResolvingDecodeFrame`. A 5 s `TaskCanceledException` in `ReadFrameOfTypeAsync`. Cause (read from `WebSocketHub.cs` ~L306): a publish-before-subscribe race. The test publishes straight after `ws.ConnectAsync`, but the hub registers the socket (`RegisterSocket`) only after the upgrade completes and sends its first `status` frame, so a publish in that window is dropped. Fix: after `ConnectAsync`, read the hub's first `status` frame (the positive signal that the socket is registered) **before** publishing; no delay. Your WIP commit already does this for this test; finish it (after-fix loop, mutation, sibling check: the other WebSocket tests already drain the first frame, this class is the only one with the pattern).

## Item 2: #217, `remote-daemon-restart 3.5(a)` (CI #1081, Windows)

https://github.com/frank001/OpenWSFZ/issues/217. `tests/OpenWSFZ.Daemon.Tests/DaemonStartupTests.cs:~38`, `NonRelaunchStartup_FailsFastOnPortConflict_NoRetry`: asserts `sw.ElapsedMilliseconds < DaemonStartup.DefaultRetryIntervalMs` (500 ms) on the **cold** first `StartAsync`; CI measured 522 ms. Replace the wall-time bound with a positive "no retry happened" signal (count the bind attempts through a hook or logger on the non-relaunch path and assert exactly one), or if a time bound is kept, set it well above the cold-start cost and below two retry intervals and state where the number comes from. Check 3.5(b) and the neighbours for the same pattern.

## Item 3: #218, `A-01 2.2` (CI #1081, Ubuntu)

https://github.com/frank001/OpenWSFZ/issues/218. `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:~604`, `WaitReport_SecondEmptyCycle_FiresRetry`: after waiting for the PTT `KeyUpAsync` count to reach 2 it asserts `State == WaitReport` immediately; the retry returns to `WaitReport` only after the transmit-and-release sequence, so the read races the transition (failure showed `TxAnswer`). Fix: `await Poll.WaitForEqualAsync(() => _sut!.State, QsoState.WaitReport, ...)` after the `KeyUp` wait, then keep the `Received(2)` assertions. Check the A-01 2.x family and `WaitReport_SilenceAfterRetry_IsSkipped` (see the comment around L2900) for the same read-once pattern.

## Verification

Full unfiltered `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js` per branch (quote the exact commands and counts; a filtered-out suite is silent, not green, HK-022). Bracket the station config's mtime around the run. **Tell QA before you start a full suite: a TRAIN timing run is on the PC** (arms are timed against each other; QA records the CPU load of each process, so a suite that overlaps is noted, not forbidden).

## Report back

Per item: the change and FILE:LINE; the loop evidence (iterations, pass/fail, binary); the mutation and its failure message; the sibling check; what you could not do, said plainly.
