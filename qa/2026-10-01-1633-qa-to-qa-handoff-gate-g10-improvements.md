# QA-to-QA handoff: stop flaky tests being WRITTEN (prevention), with Gate G10 as the backstop

**Date:** 2026-10-01 (created 16:33 UTC, reworked 16:46 UTC after the Captain redirected from detection to prevention and ruled out anything Windows-only). **From:** QA. **To:** QA (a later session). **Status:** NOT STARTED (the Captain said to write this and stop).

## 1. Why, and what the Captain asked for

Two flaky tests surfaced within one day on the SUB-FEAS merge branch (D-015 `SelectResponderAsync_NoneMode_CapturesPartnerGridIntoQsoRecord`; `CaptureAutoStartCoordinatorTests` NotFound/Ambiguous). The Captain's points, in order:

1. G10 only catches flaky tests **after** they are introduced. The goal is to stop the **obvious** ones being written in the first place. Not every flake is preventable, and that is accepted.
2. **Nothing may make the project Windows-only.** Anything adopted must work on Windows, Linux and macOS (CI matrix: `windows-latest`, `ubuntu-latest`, `macos-latest`, `.github/workflows/ci.yml:22-31`; WSL Debian is used for the Linux gate runs).

QA's read-only audit (2026-10-01, `merge/sub-feas-local`) found the rule is not ignored but **never put in front of the author**, and the gate cannot see the real causes:

- **The rule is in `TESTING_STRATEGY.md` §11 only.** `prompts/DEVELOPER.md` and `prompts/ENGINEER.md` never mention `Poll`, `TestSupport`, G10 or flakes (their testing section is only "confirm the approach with the user"). There is no analyzer, no hook (`core.hooksPath` unset), and no project instruction file for test authoring. A Developer session meets the rule only when G10 fails.
- **Prose exceptions.** `test-delay-debt.md` accepts "permanent justified exceptions". D-015's `Task.Delay(50)` (`QsoCallerServiceTests.cs` ~1727) was one ("no externally observable condition to poll for"), yet the D-015 fix found an observable condition.
- **Semantic blind spots with no delay literal.** D-015's real cause was `WaitForBatchDrainedAsync` polling `Reader.Count == 0` (dequeued, not processed), a helper copied to 56 call sites. The capture-autostart flake is a no-op `delayAsync: (_, _) => Task.CompletedTask` seam plus an exact-count assertion. §11's wording covers neither.
- **Gate robustness.** Per-line regex (a call split across lines escapes it), matches inside comments, and no tests of its own (`tools/tests/` holds only `test_gather_live_run_artefacts.py`).

Where G10 runs (verified 2026-10-01): blocking CI job (`ci.yml:454`), and `tools/pre_merge_check.py:673` locally (HK-006: on the Captain's initiative only). It is automated, not a human review step.

## 2. The plan: four layers, earliest first

### Layer 1: put the rule where the author reads it (docs only, works everywhere, do first)
- Add a short **"Tests that do not flake"** section to `prompts/DEVELOPER.md` and `prompts/ENGINEER.md` (and `QA.md` for QA's own tests): wait on a **positive condition** via `OpenWSFZ.TestSupport.Poll`; never a fixed delay; never treat "queue empty" as "processed"; never replace a delay seam with a no-op if the test then asserts an exact count on state the background loop also changes (park it, or poll).
- Extend `TESTING_STRATEGY.md` §11 with those two real causes (queue-empty is not processed; no-op delay seams), citing D-015 (`ada7b488`) and the capture-autostart flake as evidence.
- Add a one-line **test-authoring checklist** to the dev-task handoff template, for any task that adds async tests.
- **Platform scope of numeric and memory assertions (found 2026-10-01, PR #196 macOS).** A bit-exact float golden (a SHA-256 of float output recorded on one machine) is valid only on the platform and architecture that recorded it: x86-64 Windows and Linux agreed, Apple Silicon did not (4 tests red on macOS, deterministically). Rule for authors: either compare against a reference computed **in the same process** (a single-thread run, an unoptimised path), or record goldens **per platform** and select by `RuntimeInformation`, or compare with a stated tolerance. Never one x86 golden asserted on every OS. Likewise a memory-return assertion (`PrivateMemorySize64`, `RssAnon`) needs an explicit branch for each OS the CI matrix runs (Windows, Linux, macOS); an allocator that keeps freed pages reads as 0 freed. The developer cannot run macOS locally, so push the branch early: CI runs on any branch push (`ci.yml` `branches: ['**']`), which gives the macOS result in about 6 minutes, before a PR exists.

### Layer 2: make the right pattern the easy one (C# test support, works everywhere)
Hand-rolled drain helpers are how the weak `Reader.Count == 0` spread. Put the correct primitives in `OpenWSFZ.TestSupport` so nobody rewrites them per file:
- A "batch was **processed**" wait for the service tests. The Developer's `fix/qso-test-sync-settle-and-drain` (@`dc5b9cf7`, returned by QA's review 2026-10-01 for 2 changes) built `ObservedDecodeChannel` (an observing reader: channel empty AND the reader touched again after the last dequeue) and `WakeupChannelProbe` (swaps the service's `_wakeupChannel` by reflection for a counting, discarding channel; each test asserts `Discarded == 1`). **Adopt and generalise what it finally lands, do not duplicate.** Lessons from the review that the generalised helper must keep:
  - **Count writes on the writer side** (`dequeued == written && readerEvents > lastDequeueEvent`). An unbounded channel hands a written item straight to a reader parked in `ReadAsync`, so `Count` stays 0 (confirmed on .NET 10.0.302: 0 with a parked `ReadAsync`, 1 with a parked `WaitToReadAsync`). The services park in `ReadAsync` in every state except Idle/WaitAnswer/WaitRr73, so a `Count == 0` check alone passes before anything is dequeued.
  - **The helper needs its own tests** (parked-`ReadAsync` handoff, true after a processed batch, false while queued). A gate helper without tests is the same blind spot as G10 having none.
  - The probe relies on reflection over an `internal readonly` field; the clean version is an internal seam, which is an `src/` change (HK-011): propose it to the Architect/Captain, do not make it.
- A parked-delay helper (a `delayAsync` seam that parks on a `TaskCompletionSource` the test controls) as the standard replacement for `=> Task.CompletedTask`.

### Layer 3: compile-time enforcement with `Microsoft.CodeAnalysis.BannedApiAnalyzers` (adopt only after the cross-platform proof in section 4)
A NuGet analyzer that runs inside the compiler during `dotnet build`, so a banned call is an error at authoring time (editor and CLI), not a CI failure later. Scope it to the **test projects only**; the shared `tests/OpenWSFZ.TestSupport` poll implementation needs the delay and is exempt.
- Ban `Task.Delay` (all overloads), `Thread.Sleep` (all overloads), and `ChannelReader<T>.Count`, via a `BannedSymbols.txt` in the tests. This also catches `const`/variable delays and multi-line calls, which the regex cannot.
- A justified exception is `#pragma warning disable RS0030 // <reason>` **at the site** (replaces the prose-in-a-far-away-file exceptions). Decide whether a reviewer can reject an empty reason mechanically (a short Python check that every `RS0030` disable carries non-empty text); recommended yes.
- Still needing a pragma on purpose: the 7 legitimate non-literal delays (`Task.Delay(Timeout.Infinite, ct)` parks and one `_delay` field), the absence-proof delays (`ConsoleDetacher:64`, `DecodePump:270`, `ExternalReporting:1470`, `LoggingRotation:128`), mock latency (`Caller:1315`, `CatPolling:326/334`, `CaptureManager:29`), feeders (`Answerer:1152/1978`), and `DaemonStartup:79/134`. Each gets a reasoned pragma or a migration.
- **Not expressible by banned-API**: the no-op `delayAsync => Task.CompletedTask` seam (3 sites, all `CaptureAutoStartCoordinatorTests`). That stays covered by Layers 1 and 2 plus a small G10 pattern (below).

### Layer 4: Gate G10 stays as the cross-platform backstop (Python, runs on all three CI platforms)
Keep `tools/check_test_delay_sync.py`; improve it only where Layer 3 cannot:
- Flag `delayAsync`-named arguments bound to `=> Task.CompletedTask` unless a `// G10-allow: <reason>` marker (non-empty) is on the line or the line above. Measured today: 3 sites.
- Flag `Reader.Count == 0` / `<= 0` in a poll as a belt-and-braces match if Layer 3 is not adopted. Measured today: 2 sites (the two `WaitForBatchDrainedAsync` helpers; the Developer's branch replaces both, so on the post-merge tree the hit count should be 0).
- Flag a **bare `_wakeupChannel.Reader.TryRead(...)` drain** used as a synchronisation step (a drain with no delay literal, so G10 cannot see it). Found by the Developer (2026-10-01): `QsoAnswererServiceTests.cs` ~1388, 1413, 1781, same race as the 8 settle sites; the fix is `WakeupChannelProbe.Discard`. Decide whether to flag every `_wakeupChannel.Reader.TryRead` in tests (simple) or only those followed by a state assertion; recommended: every one, with a `// G10-allow:` marker for the legitimate ones. Re-measure the hit count on the post-merge tree before relying on "3".
- `QsoAnswererServiceExternalReplyTests` has its own channel and helper (it failed once in the Developer's 20-run baseline) and is outside the Developer's helper fix; triage it when building this layer.
- **Platform-scope declaration rule (G10 extension, caught-late but mechanical).** A static lint cannot know whether a golden was recorded cross-platform; it can only force the author to **declare** the scope. Proposed predicate (code, HK-021): a test file that (a) loads a golden (`Golden(` / `*-golden*` / `golden.csv`) or (b) compares against a 64-hex string literal, or (c) reads `PrivateMemorySize64`, `WorkingSet64` or `/proc/self`, must carry, in the same test method or the line above it, EITHER an OS/architecture guard (`OperatingSystem.Is*`, `RuntimeInformation`, a platform-conditional attribute) OR a `// G10-platform: <scope and why>` marker with a non-empty reason. **Measured 2026-10-01 on `26374f60` by `git grep`:** (a)/(b) match 4 files (`SubfeasNativeSpeedTests.cs` 7 hits, plus the three win-x64 binary-pin files `AwgnFpReplayTests`, `FpParityP3Tests`, `Row0rCarryForwardTests`, each 1 hit, which would need a marker such as `win-x64 binary pin`); (c) matches 1 file (`SubfeasNativeSpeedTests.cs`, 2 hits). Honest limit: the lint documents intent, it does not prove portability; CI's macOS job remains the real catch (it did catch this one). Build-time companion, only if the macOS experiment confirms FMA: `-ffp-contract=off` in the native build recipes so arm64 stops diverging from x86-64 (a product-numerics decision for the Captain, not a test fix).
- Robustness: ignore matches in `//` and `/* */` comments; match calls split across lines.
- Add **`tools/tests/test_check_test_delay_sync.py`** (none exists): each existing shape, each new pattern firing, the marker accepted with a reason and rejected when empty, comments ignored, multi-line matched, and the legitimate non-literal delays NOT flagged.
- If Layer 3 lands and covers the delay and `Count` cases, retire the debt-file mechanism for them (the pragma is the exception record) and keep G10 for the seam pattern only.

## 3. Licence check (done 2026-10-01, before planning; Captain's order)

`Microsoft.CodeAnalysis.BannedApiAnalyzers`, from the NuGet registry (`api.nuget.org`, registration metadata):
- **Licence: MIT** (`licenseExpression: MIT`) on 5.0.0, 5.3.0 and 5.6.0; project `github.com/dotnet/roslyn`. **Passes the permissive-only policy** (`standing-licence-policy.md`: MIT/BSD/ISC; repo is AGPL-3.0).
- **No dependencies** (5.6.0 `dependencyGroups` is empty). Latest stable seen: **5.6.0, published 2026-07-02**. The registry also lists 5.0.0-1.* prereleases; do not use those.
- It is a **build-time analyzer**: reference it with `PrivateAssets="all"` so it is not a runtime dependency and ships nothing.
- **Still to do when building** (not yet done): run `tools/LicenseInventoryCheck` after adding the reference, and update `THIRD-PARTY-NOTICES.md` if that check requires it (the repo ships a 74-line notices file; MIT requires attribution). Quote the check's output, do not infer it.
- The licence was read from registry metadata, not from the packaged licence file. Confirm against the package's own license file when it is restored.

## 4. The cross-platform proof (no Windows-only; the Captain's condition)

Reasoning, not yet shown: the analyzer is a compiler plug-in distributed as a NuGet package, platform-independent, and the repo already ships a Roslyn source generator (`src/OpenWSFZ.Web/OpenWSFZ.Web.csproj:10`) that builds on all three CI platforms. **QA has not built this analyzer in this repo; do not claim cross-platform until it is shown.**

Proof before Layer 3 lands anywhere:
1. On a **throwaway QA branch**, add the package reference and a `BannedSymbols.txt` to **one** test project, with one deliberately banned call.
2. Build on **Windows** and on **WSL Debian**: the banned call must fail the build on both with the same diagnostic id (`RS0030`), and the same project must build clean without the call. Quote commands, exit codes, and diagnostics.
3. Add the check to the CI matrix by simply building (no new job is needed: the existing build covers all three), and read the **macOS** result from CI; do not assume it.
4. If any platform fails, **drop Layer 3** and rely on Layers 1, 2 and 4. The Captain's ruling beats the tooling.
5. 🔴 **Do not run builds or test suites while the Developer or QA is in a timing/load run** (CPU is shared, MEMORY.md; 13 overlapped Engineer passes on 2026-09-30 disturbed a QA run). Check with the Developer first.

## 5. Sequencing

Layers 1 and 2's docs part are safe now (no overlap). The overlap with the Developer is real: `fix/qso-test-sync-settle-and-drain` (handoff `dev-tasks/2026-10-01-test-sync-settle-delays-and-batch-drained-helper.md`, commit `874c92c5`) rewrites the same two helpers and removes debt entries from `test-delay-debt.md`; the capture-autostart fix (`dev-tasks/2026-10-01-capture-autostart-coordinator-load-flake.md`) touches the seam sites. **Build Layers 3 and 4 only after both are reviewed and merged**, so new rules land against a clean tree with the fewest debt entries (the strongest form: clean code, not grandfathering). Fallback if the Captain wants it sooner: build on a QA branch and list the 5 known sites as debt for the Developer's branches to delete (small, predictable conflict in `test-delay-debt.md`).

Order of work: Layer 1 (docs) -> Layer 2 (adopt the Developer's helper, add the parked-delay helper) -> the cross-platform proof (section 4) -> Layer 3 -> Layer 4 plus its tests.

## 6. Method and acceptance

1. Branch from `origin/main`. `git branch --show-current` before every commit. **Never `git add -A`**, stage by path.
2. Test-first: write the gate tests (and one deliberately-banned fixture) first, watch them fail, then implement.
3. Prove each rule **fires**, quoting hit counts against a copy of the pre-fix tree or synthetic fixtures (today: seam 3, `Reader.Count` 2, non-literal legitimate delays 7 and **not** flagged by G10).
4. Prove nothing fires wrongly: `python tools/check_test_delay_sync.py` OK on the real tree, and the full build clean, on **each** of Windows and WSL Debian.
5. State each rule's detection predicate as code, not prose (HK-021), so a reviewer reproduces the hit counts. Quote the exact commands, exit codes and pass counts (HK-022).
6. Commit locally. **Ask the Captain before any push or PR** (HK-033). `prompts/*.md` edits are QA-owned documents; no `src/` or `native/` change is needed for Layers 1, 3 or 4, and Layer 2 touches only `tests/OpenWSFZ.TestSupport` (state `git diff --stat -- src/ native/` empty, HK-029). Update the board in the same edit as any board-changing result (HK-024).

## 7. Open questions for the Captain (ask one at a time, before building)

- Layer 3 pragma justification: enforce a non-empty reason mechanically (a small Python check), or trust review? (QA recommends enforce.)
- After Layer 3, retire G10's debt file for delays and `Count`, or keep both layers? (QA recommends retire the debt file, keep G10 for the seam pattern.)
- Should `pre_merge_check.py` run the new gate tests as part of G10, or leave them to CI only?
- Wait for the Developer merges (recommended), or build on a QA branch with 5 debt entries?

## 8. Evidence and references

- Hit counts measured 2026-10-01 on `merge/sub-feas-local` by `grep` over `tests/**/*.cs`: non-literal `Task.Delay` 7; multi-line `Task.Delay(` 0; `Reader.Count == 0` 2; no-op `delayAsync` 3; `WaitOne(n)`/`.Wait(n)`/`SpinWait` 0. `python tools/check_test_delay_sync.py --list`: 23 bare-delay sites across 10 files.
- Where the rule lives today: `TESTING_STRATEGY.md` §11 (lines ~342-360); absent from `prompts/DEVELOPER.md`, `prompts/ENGINEER.md`.
- Gate: `tools/check_test_delay_sync.py` (`DELAY_RE`, `scan_file`, `find_untracked`), `test-delay-debt.md`, `tests/OpenWSFZ.TestSupport/Poll.cs` (`UntilAsync`, `WaitForEqualAsync`, `WaitForCallAsync`, `WaitForCallCountAsync`).
- Developer report 2026-10-01 (20-run, 32-busy-loop WSL protocol, whole `OpenWSFZ.Daemon.Tests` unfiltered): base 8/20 failed (capture-autostart family 6, A-01 2.2 caller test 1, `ExternalReply` test 1); with the helper fix only 16/20 clean (4 failures, all capture-autostart); fix plus the capture-autostart branch `d185d8a2` overlaid in a scratch copy 20/20. The 8 settle sites themselves did not fail at n=20, so their fix rests on the mechanism read from the code. QA's review of that branch (read-only, no suites run) returned it for the counter fix and helper tests above.
- D-015 mechanism: commit `ada7b488` (`WaitForResponderRecordedAsync`). Dev handoffs: `dev-tasks/2026-10-01-d015-qsocaller-partnergrid-flake.md`, `dev-tasks/2026-10-01-capture-autostart-coordinator-load-flake.md`, `dev-tasks/2026-10-01-test-sync-settle-delays-and-batch-drained-helper.md`.
- Licence evidence: NuGet registry metadata for `microsoft.codeanalysis.bannedapianalyzers` (queried 2026-10-01). Policy: `standing-licence-policy.md`; tooling: `tools/LicenseInventoryCheck`, `THIRD-PARTY-NOTICES.md`.
- Standing rules: HK-006, HK-011, HK-021, HK-022, HK-024, HK-029, HK-033.
