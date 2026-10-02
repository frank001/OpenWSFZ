# Developer handoff: #205, `CycleArchiveService` silently loses a manifest row when another process has the manifest open

**Date:** 2026-10-02. **From:** QA. **To:** Developer. **Priority:** medium (quiet archive data loss, never a crash or a decode problem). **Issue:** https://github.com/frank001/OpenWSFZ/issues/205. `src/` is touched (`OpenWSFZ.Daemon` only, expected), so a separate Developer session does it (HK-011). **Only QA pushes.** The Captain said "fix it" on 2026-10-02.

## 1. The defect (found by the Developer's probe while root-causing flake #204)

`src/OpenWSFZ.Daemon/CycleArchiveService.cs`, `AppendManifestAsync` (~line 350):

```csharp
await using var writer = new StreamWriter(manifestPath, append: true) { NewLine = "\n" };
```

That asks for write access. If another process already holds the manifest open with a share mode that does not allow writing (the default `FileShare.Read` of `File.ReadAllLines`, an antivirus or indexer scan, an editor, `Get-Content`), the open throws a sharing violation. `WriterLoopAsync` (~line 232) catches it, logs "failed to archive a cycle — continuing", and moves on. **Nothing retries**, so the row is lost for good. The item's WAV was already written by `ProcessItemAsync` (~line 308 to 315), so the archive ends with a WAV that has no manifest row.

A further loss rides on the same failure path (QA's reading of the code, not yet shown by a test): `AppendManifestAsync` takes state **before** it knows the append worked. `Interlocked.Exchange(ref _droppedSincePreviousRow, 0)` runs at the top of the method, so if the append then fails, the **dropped-cycle count is consumed and never written**, and the explicit gap marker (the `dropped_before` column) silently under-reports. Prove or refute this with the test in section 4.

## 2. 🔴 Correction to QA's own issue text: `FileShare.ReadWrite` alone does NOT fix this

Issue #205 listed "open with `FileShare.ReadWrite` and/or retry". Think it through before you copy that: a sharing violation is decided by **both** handles. When a reader got in first with `FileShare.Read`, the writer's request for `FileAccess.Write` fails whatever share mode the *writer* offers. Changing the writer's share mode only affects readers who open **after** the writer. So:

- **The bounded retry is the actual fix and is mandatory.**
- Opening the writer with an explicit `FileStream(path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite)` is a secondary, optional hardening (it lets a later reader open while a row is being written). Do it only if you can say what it adds, and keep the existing header-on-create behaviour.

## 3. Required behaviour

1. **Bounded retry around the manifest append** for the sharing-violation case (`IOException` whose cause is a sharing violation; do not blanket-retry every exception, and let `OperationCanceledException` through). A small, **named-constant** attempt count and backoff (no magic numbers). The retry delay must be an **injectable seam** (a `Func<TimeSpan, CancellationToken, Task>` or the project's existing delay abstraction, as the other services use), because TESTING_STRATEGY.md section 11 forbids fixed sleeps as barriers and warns that a no-op delay seam turns a retry into a free-running loop (found 2026-10-01, capture-autostart): in the test, park the seam rather than returning `Task.CompletedTask`.
2. **No state is consumed before the append succeeds.** Take `_droppedSincePreviousRow` only when the row is really written, or add the taken count back if the append finally fails. State which you chose.
3. **A final failure is loud, specific and counted**, not silent: after the retries are spent, log one Warning naming the filename (not message text, HK-037) and say the WAV exists without its manifest row; keep a simple counter if the service already exposes counters (do not invent a new surface for it).
4. Do not change what a successful append writes (header, columns, order, line endings) or the retention logic.
5. If the cycle-audio-archive spec (`openspec/specs/cycle-audio-archive/spec.md`, "Sidecar manifest records per-cycle provenance", ~line 114) or `REQUIREMENTS.md` should state that an externally held manifest must not lose a row, add the requirement text and a scenario and make sure a test carries the `FR-###:` DisplayName prefix (G3). If it genuinely needs a new FR, tell QA before inventing the number (FR-082 is the last on `main`; `decoding_improvement` already uses FR-078 to 081, so check both).

## 4. Tests (test-first; deterministic, no sleeps)

- **The regression test the Developer's probe already is:** hold the manifest open with `FileShare.Read` (as `File.ReadAllLines` does), process an item, and show on the **base** that the manifest ends with the header plus row 1 only and the logger records "failed to archive a cycle"; then, **on the fix**, the reader is released from inside the injected delay seam on the first retry (a deterministic hook, no wall-clock wait) and the row **lands**, in order.
- A test that a reader holding the file for **longer than the retry budget** produces the loud, specific Warning and does not stall the writer loop for later items (the next item's row still lands once the file is free).
- A test that the **dropped-cycle count is not lost** when the first append attempt fails and a later attempt succeeds (the gap marker still appears on the row that eventually lands).
- Existing `CycleArchiveServiceTests` keep passing as they are (they now wait on `ItemProcessedForTests`, which fires after the manifest writer is closed, so the retry must complete before the signal).

## 5. Acceptance (QA checks)

1. The probe-style test fails on the base and passes on the fix (quote both), and a **load loop** (N runs of the `CycleArchiveServiceTests` class under CPU burners, N and failure counts quoted before and after) is clean on the fix; kill your burner processes by ID and say you checked for orphans (HK-019).
2. No `Task.Delay`/`Thread.Sleep` as a barrier in tests, no retry attribute, no skip. `check_test_delay_sync.py` OK. Tell QA which delay seam you used.
3. Unfiltered `dotnet test OpenWSFZ.slnx -c Release` on **Windows** and **WSL Debian** (commands and per-assembly counts, HK-022; WSL without `nohup`, `/home/frank/.dotnet` on `PATH`). 🔴 Ask QA before running the suite: CPU shared.
4. `git diff --stat origin/main -- native` is **empty**; `src/` limited to `OpenWSFZ.Daemon` (say so if anything else is touched, and why).
5. `check_version_bump.py origin/main` and `check_version_docs.py` run and quoted (commit first, the bump gate reads git); if the gate asks for a bump, bump and tell QA. `openspec validate --all --strict` if you touched a spec.
6. The closing commit message states the root cause (TESTING_STRATEGY.md section 11 item 4). No push.

## 6. Process

Cut `fix/205-cycle-archive-manifest-retry` from `origin/main` (`git fetch` first, it is now at the flake-fix commit). macOS cannot be run locally: QA will push the branch for a CI run when you are done.

## 7. References

- Issue #205; flake #204 and its closing commit `8d6cded8` (the tests that already wait on `ItemProcessedForTests`); `dev-tasks/2026-10-02-flaky-fr-ux-002-watchdog-and-cycle-archive-manifest-order.md`.
- `src/OpenWSFZ.Daemon/CycleArchiveService.cs` (`WriterLoopAsync`, `ProcessItemAsync`, `AppendManifestAsync`); `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs`.
- Standing rules: HK-011, HK-022, HK-037 (no message text in logs), TESTING_STRATEGY.md section 11.
