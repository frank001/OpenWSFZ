# Developer handoff: `DaemonE2ETests` run the daemon against the REAL `%APPDATA%` config and default port: isolate them

**Date:** 2026-10-02. **From:** QA. **To:** Developer. **Priority:** medium (a test run silently rewrites the station's live config). **Scope:** `tests/OpenWSFZ.E2E.Tests` only, no `src/` or `native/` change. **Only QA pushes.** Captain approved this handoff on 2026-10-02.

## 1. The defect, found (QA, 2026-10-02)

`tests/OpenWSFZ.E2E.Tests/DaemonE2ETests.cs` (FR-007 `WelcomeBanner_AppearsOnStdoutWithinTimeout`, FR-002 `StatusEndpoint_ReachableAfterBanner`) call `DaemonProcess.StartAsync(startupTimeout: …)` with **no `configPath` and no `explicitPort`**. `DaemonProcess.StartAsync` then passes neither `--config` nor `--port`, so the published daemon resolves the **platform default config, `%APPDATA%\OpenWSFZ\config.json`, which on the QA/station machine is the station's real config**, and the default port.

Consequences, observed:

- On 2026-10-02 at 11:33:14 local the station's real `config.json` was **rewritten** by the default-ON build (the one-time migration writes the file back on `Load`) while a Developer ran the unfiltered Windows suite. Nothing else ran the new code at that moment; QA's later runs found the file already migrated. The same exposure applied to the nhard 40 migration earlier.
- Any full `dotnet test` on this machine can also collide with a live station daemon on the default port.
- The sibling class `SelfContainedNonAotE2ETests` already does this correctly: its own comment explains the isolation, and its `IsolatedDaemonEnvironment` (temp directory, `DaemonProcess.ReserveEphemeralPort()`, explicit `configPath`) is the model. `BackgroundColdStartE2ETests` passes `--config` too.

## 2. Required behaviour

1. Both `DaemonE2ETests` tests start their daemon with an **isolated temp `--config`** and an **explicit ephemeral port**, deleted on dispose, exactly as `SelfContainedNonAotE2ETests.IsolatedDaemonEnvironment` does. Prefer to **reuse or share that helper** rather than copy it (move it to a small internal class in the E2E project if that is cleanest).
2. `git grep -n "DaemonProcess.StartAsync" tests` and `git grep -n "ProcessStartInfo" tests`: no E2E or other test may start a daemon (or any process that loads the config store) without `--config`. If you find another, fix it the same way and say so.
3. Make it **impossible to repeat by accident**: in `DaemonProcess.StartAsync`, if `configPath` is null, **throw** (or default to a fresh temp path), so a future test cannot silently use the real config. Say which you chose and why.
4. Do not change the tests' assertions or DisplayNames (the `FR-007:` and `FR-002:` prefixes stay, G3 depends on them).

## 3. Acceptance (QA checks)

1. A test that **proves the isolation**: after running the two tests, the file at `%APPDATA%\OpenWSFZ\config.json` is untouched. Do this on a **throwaway copy of the environment, never by running against the station's file**: point the test at a sentinel by setting `APPDATA` (or `OPENWSFZ_CONFIG` as appropriate) to a temp directory for the test process, run the two tests, and assert nothing was created or modified there.
2. The same two tests fail on the base (Before: with `APPDATA` pointed at the sentinel directory they create or modify a config there), then pass.
3. Unfiltered `dotnet test OpenWSFZ.slnx -c Release` on **Windows** and on **WSL Debian** (exact commands and per-assembly counts, HK-022; WSL without `nohup`, with `/home/frank/.dotnet` on `PATH`). 🔴 **Before you run the suite, QA checks the station config's modification time; after, QA checks it again** (QA does this, not you, but do not run anything else against `%APPDATA%`).
4. `check_test_delay_sync.py` OK, `check_version_bump.py origin/main` and `check_version_docs.py` run and quoted (a bump should not be needed for a tests-only change; if the gate says so, tell QA first), `openspec validate --all --strict`.
5. `git diff --stat origin/main -- src native` is **empty**. No push.

## 4. Process

Cut `fix/e2e-daemon-test-isolation` from `origin/main` (`git fetch` first). Report the answer to section 2 item 2 (any other offender?) and item 3 (throw or default). 🔴 The CPU is shared: ask QA before you run the suite.

## 5. References

- `tests/OpenWSFZ.E2E.Tests/DaemonE2ETests.cs`, `DaemonProcess.cs` (`StartAsync`, `ReserveEphemeralPort`), `SelfContainedNonAotE2ETests.cs` (`IsolatedDaemonEnvironment`), `BackgroundColdStartE2ETests.cs`.
- `src/OpenWSFZ.Config/ConfigPathResolver.cs` (CLI flag, then `OPENWSFZ_CONFIG`, then `%APPDATA%`).
- Standing rules: HK-011 (this change is tests only), HK-022.
