# QA code review (HK-039): #266 one pipeline owner, Developer `27b11251`

Reviewed-commit: 27b11251bcde3392f46706b2fcb64efaaef68257
Verdict: APPROVED for the code (four advisories); RETURNED for one documentation change R-1, see the addendum at the end. Next gate: `pre_merge_check.py` on a clean checkout of this exact commit (HK-006), then K2 (the duplicate-stamp counter on the 8081 log) and L1 on the Captain's go.

**Branch:** `fix/pipeline-owner-266` (`f5c97a1a` openspec copy, `27b11251` fix) off `origin/main` `dd61a7e9`. **Spec:** OpenSpec `one-pipeline-owner-266` (`qa/refset` `e8be9046`); Architect spec `arch/framer-266` with Amendment 1.

## What QA did

1. Read `PipelineController.cs` whole (251 lines) and the whole `Program.cs` diff. `git diff --stat origin/main -- native` empty (Developer's statement; `pre_merge_check` repeats it).
2. Clean detached worktree at exactly `27b11251` (`D:\Projects\claude\_qa-scratch\p266-review`).
3. **Q2 single-owner grep** (QA's own run, `src`, `*.cs`, excluding `bin`/`obj`): pattern `new CycleFramer\(|framerCts|framerTask|captureManager\.(StartAsync|StopAsync)|runningDevice|runningEnabled|RestartPipelineAsync|restartSemaphore|StartPipeline|StopFramerAsync`. **All 16 hits are in `src/OpenWSFZ.Daemon/PipelineController.cs`** (`_runningDevice` at :47, :101, :127, :131, :133, :156, :170, :191; `captureManager.StartAsync/StopAsync` at :91, :92; `new CycleFramer(` at :94; `StopFramerAsync` at :153, :166, :181, :195). Zero hits in `Program.cs`, `CaptureAutoStartCoordinator.cs` or `src/OpenWSFZ.Web`. A second sweep for any other `CycleFramer(` / capture `StartAsync`/`StopAsync` caller in Daemon and Web found none. **m7 (a start path outside the controller): none exists.**
4. `dotnet test tests/OpenWSFZ.Daemon.Tests --filter "FullyQualifiedName~PipelineController|FullyQualifiedName~CaptureAutoStartCoordinator"` (a FILTERED run: the new class plus the unchanged coordinator tests, not the full suite): **32 passed, 0 failed.**
5. QA mutations, each alone on the clean tree, same filter, reverted after each:

| # | Mutation | Result |
|---|---|---|
| m1 | start step does not stop the framer it finds (`_framer = null`) | KILLED (1 fail, T8) |
| m2 | `DecodingEnabled` ignored in `desired` | KILLED (8 fail) |
| m3 | config read before the semaphore (read at trigger time) | KILLED (6 fail; the variant needed both edits: the first alone is dead code) |
| m4 | restart on an unchanged-device save | KILLED (2 fail) |
| m5 | R4 Warning demoted to Information | KILLED (1 fail, T8) |
| m6 | `forceRestart` ignored while running | KILLED (2 fail) |
| m8 | shutdown flag never set (a late reconcile may restart) | KILLED (1 fail) |
| m9 | `Pipeline started` line demoted to Debug | KILLED (1 fail) |

(The first m8 attempt, removing the flag check, did not compile under warnings-as-errors; the replacement above is the working variant.)

## Findings

None required. Verified in the code: reconcile reads `_config.Current` after `_gate.WaitAsync` (decision 2); "running" is `_runningDevice`, the owner's own record, so a dead capture is still running and the coordinator's `forceRestart` restarts it; `forceRestart` with decoding off is a no-op (the `desired is null` branch); the start step stops a found framer first and warns exactly once; `captureManager.StartAsync` stays fire-and-forget (`{ _ = ...; }`); shutdown keeps the order health monitor, framer, decoder dispose, capture stop, capture dispose, under the same semaphore. `runningDevice` / `runningEnabled` are gone; the two new locals `lastSavedDevice` / `lastSavedEnabled` only decide whether to ask the controller, which is how an unrelated save is kept from acting, as design decision 2 intends.

## Advisories (none blocking)

- **A-1. Monitor resets happen only on a start.** The old `RestartPipelineAsync(null)` (device cleared) reset the audio, data-flow and spectrum monitors; a stop-only transition now does not (as `decode/stop` never did). Cosmetic at worst (a stale activity indicator until its own timeout). Developer's choice 1; accepted, worth one line in the report.
- **A-2. The startup start is logged with reason `capture-retry`** (the coordinator's `startCaptureAsync` is wired to that reason for every automatic start). The start/stop lines are therefore right in count but the first line of a daemon run says "retry". Cosmetic; QA's L1 counters read counts, not reasons.
- **A-3. A start that throws between `_startCapture` and `framer.Start()`** leaves capture started and `_runningDevice` null, so the next reconcile starts again (harmless: the capture manager restarts its source). Not reachable by any observed fault; noted.
- **A-4. The shutdown hook now catches and logs a failure of pipeline shutdown** (the old code let it propagate) and skips `loggingPipeline.Dispose()` only if shutdown throws. Developer's choice 3; acceptable.

Process: `tasks.md` untouched by the Developer (correct, QA's); FR-097/098 rows added with revision 1.61; VERSION 0.65 and README agree (`check_version_bump.py` OK per the Developer, repeated by `pre_merge_check`).

## Not done by this review

The full unfiltered suite, Playwright (none relevant), G3/G9/G10, the WSL and publish checks: **not run here**, they are `pre_merge_check.py`'s job. No live run: **K2** (the 8081 counter, which must reproduce 29 duplicated of 62 distinct stamps in 91 windows) and **L1-a / L1-b** (scratch instance, replayed WAV, positive control on `dd61a7e9` first) are still owed, L1 on the Captain's go. NFR-021: the new log lines carry device identifiers and reasons only (inspection); tests use no callsigns.

## ADDENDUM 2026-10-26 (after `pre_merge_check.py`): one required change, in the documentation only

`pre_merge_check.py` on a clean checkout of `27b11251` returned **NOT READY**: **G9a FAIL**, every other gate PASS (build, full suite Windows and WSL, G3, G9b, G10, OpenSpec strict, both publishes). Log: `D:\Projects\claude\_qa-scratch\p266-logs\pre_merge_check_27b11251.txt`. Cause: `REQUIREMENTS.md` still carries the anchor sentence for v0.64 while `VERSION` and `README.md` say 0.65 (`check_version_docs.py`: "REQUIREMENTS.md cites v0.64 but VERSION says 0.65").

- **R-1 (required, one line, no `src/` change):** edit the anchor sentence in `REQUIREMENTS.md` to read `The current release is v0.65.`, run `python tools/check_version_docs.py` and report its output.
- This review's sentence "VERSION 0.65 and README agree" was true but covered two of the three documents; the third was left to the gate, as the section above says. The code verdict stands: the diff `27b11251..<fix>` must show **no change under `src/` or `native/`**, and QA will check that and re-run `pre_merge_check` on the new commit.
- **Revised verdict: RETURNED for R-1 (code approved).** HK-039 for the fix commit: a new record will name its hash.
