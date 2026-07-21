# Flaky test — FR-060 `IsSeedData becomes false after a successful SaveAsync`

**Date surfaced:** 2026-07-21 (during the `fix-flaky-test-delay-synchronization` closeout pre-merge run)
**Test:** `tests/OpenWSFZ.Daemon.Tests/CallsignRegionStoreTests.cs:418`
`FR-060: engagement-target-validation 1.5: IsSeedData becomes false after a successful SaveAsync`
**Owner area:** `engagement-target-validation` (PR #81) — NOT the delay-sync work.

## Symptom

Failed once in a full `dotnet test -c Release` run on **Windows** (1 of 567 in
`OpenWSFZ.Daemon.Tests`), duration 4 ms. In the **same** pre-merge run:
- Passed 535/535 on the WSL Debian leg (this test included).
- Re-ran in isolation on Windows immediately after — passed (`--filter DisplayName~"IsSeedData
  becomes false"` → 2/2; `--filter FullyQualifiedName~IsSeedData_` → 8/8).

So this is an order-/parallelism-dependent flake, not a regression, and is **unrelated** to the
delay-synchronization change (which touches zero C#). It reproduces only under full-suite parallel
execution, not in isolation — pointing at shared state (seed-data/`IsSeedData` flag or a store file)
bleeding between fixtures rather than a `Task.Delay` sync-barrier of the kind G10 covers.

## Suggested next step (not done here)

Investigate `CallsignRegionStore` seed-data state isolation between `CallsignRegionStoreTests`
fixtures — likely a shared on-disk store path or a static/`IsSeedData` flag not reset per test.
This is a state-isolation flake, a different root cause from the `Task.Delay` barriers Gate G10
addresses, so it is out of scope for that change and tracked separately here.
