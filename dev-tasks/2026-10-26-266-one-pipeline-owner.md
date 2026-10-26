# Developer task: issue #266, one owner for the capture pipeline (no orphaned CycleFramer; "decoding off" means off)

**Date:** 2026-10-26
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off before merge, HK-010)
**Authorised by:** the Captain, 2026-10-26 18:13:25Z, in the Architect's window: *"go with your recommendations."* (D1 = a, a device change while decoding is off is saved only; D2 = a, one owner). Architect spec `qa/rr-study/2026-10-26-1810-architect-to-qa-spec-266-orphaned-cycleframer.md` on `arch/framer-266` (§11 Amendment 1, `70c8bc01`, adopts QA's K1 to K4); QA's (k) review `qa/rr-study/2026-10-26-1900-qa-to-architect-k-review-spec-266-orphaned-cycleframer.md` (`qa/refset` `7577c297`). Where this note and the OpenSpec text differ, the OpenSpec text wins.
**Status:** Proposed. HK-011: a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative.**
**Branch:** `fix/pipeline-owner-266`, cut from **`origin/main`** (`dd61a7e9`, v0.64, or later). Never commit to `main`. The previous branch `feat/psk-reporter-262` is merged: leave it.
**OpenSpec change:** `openspec/changes/one-pipeline-owner-266/` on QA's branch `qa/refset`: copy `.openspec.yaml`, `proposal.md`, `design.md`, `tasks.md`, `specs/audio-capture/spec.md` and `specs/decode-control/spec.md` unchanged in your first commit (`git show qa/refset:<path>`). It validates under `openspec validate --strict`.
**Version:** the proposal says `User-facing: yes`: bump `VERSION` (G9b; 0.65 expected) and what carries it; confirm with `python tools/check_version_bump.py origin/main`. **No `native/` change, no shim bump.**
🔒 NFR-021: logs carry counts, device identifiers and reasons, never message text or callsigns. 🛑 Licence: no new package expected.

---

## 0. The defect, in four lines

Today `Program.cs` holds one framer slot (`framerCts`, `framerTask`, lines 389-390) and starts framers from three places that do not agree: the config device-change branch (`:~978-995`, restarts whatever `DecodingEnabled` is), the `DecodingEnabled` false-to-true branch (`:1009`, a **bare** `StartPipeline`, no stop first) and the retry path. `StartPipeline` (`:1126`) overwrites the slot without stopping what is in it, so the first framer becomes unstoppable and keeps reading the process-lifetime `Samples` channel: two framers split the audio (#266). A device change while decoding is off starts a full pipeline (F2). The two `OnSaved` branches are edge-triggered and unordered (F3).

## 1. What you build

A `PipelineController` in `src/OpenWSFZ.Daemon/` (a new file; collaborators injected as delegates or small interfaces, as `CaptureAutoStartCoordinator` does) that is the **only** code that: constructs a `CycleFramer`; holds the framer slot; calls `captureManager.StartAsync` / `StopAsync`; resets `audioMonitor`, `dataFlowMonitor`, `spectrumAnalyser`; holds the semaphore. One entry point:

`Task ReconcileAsync(string reason, bool forceRestart = false)`: inside the semaphore, read `configStore.Current` **now**:

| Situation | Action |
|---|---|
| desired = `AudioDeviceId` non-null **and** `DecodingEnabled` true | |
| running on a different device, or `forceRestart` with desired | stop, then start |
| desired, not running | start |
| not desired, running | stop |
| otherwise (incl. Start while running, same device saved again, `forceRestart` while decoding is off) | nothing |

- **"Running" = the controller's own record** that it started a pipeline on a device and has not stopped it. A dead capture with the record standing is still "running" (the coordinator retries it with `forceRestart`).
- **The start step** stops anything found in the slot before starting; if it found something it logs exactly one Warning: `Pipeline start found a framer still running; stopped it first (reason: {Reason}).` It must never fire on a normal path.
- **Logs (Information):** `Pipeline started on '{Device}' (reason: {Reason}).` and `Pipeline stopped (reason: {Reason}).` Keep the existing `Starting FT8 pipeline` and `CycleFramer started` lines as they are.
- **Keep `captureManager.StartAsync` fire-and-forget** (`_ =`): faults arrive through `CaptureFailed`; do not await it under the semaphore.
- **Wiring in `Program.cs`:** the `OnSaved` handler calls `ReconcileAsync("config")` once when the device or `DecodingEnabled` changed (both old branches collapse); the coordinator's `startCaptureAsync` calls `ReconcileAsync("capture-retry", forceRestart: true)`; startup auto-start keeps going through the coordinator (it already refuses with decoding off); the shutdown hook stops through the controller under its semaphore, **in today's order** (health monitor, framer, decoder dispose, capture) and waits for an in-progress reconcile.
- **Delete** `framerCts`, `framerTask`, `StartPipeline`, `StopFramerAsync`, `RestartPipelineAsync`, `runningDevice`, `runningEnabled` from `Program.cs`. Two records of "what is running" is how F3 arises.
- `CaptureAutoStartCoordinator.cs`: doc comments only (`:35`, `:38-45`, `:67`, `:152-158`): name the controller; no behaviour change; **`CaptureAutoStartCoordinatorTests` pass unchanged**.
- **Out of scope:** #238, the 3-s framer and 10-s capture stop timeouts, the UI, the `Samples` channel, anything under `native/`.

## 2. Tests (the Developer writes them; `tasks.md` section 1 has the rows)

T1 to T11 against the controller with a fake capture, a fake framer factory (counts live framers, records an **ordered event log**), a fake config store and a gate on the semaphore. Three requirements QA will check, because the mutations below survive without them:

- **T3** changes the configuration **between the trigger and the semaphore acquisition** (hold the semaphore from the test, change the config again, release); the end state follows the last configuration; a variant that reads the config at trigger time must fail.
- **T8** pre-seeds the slot with a live fake framer and asserts, from the event log, that it was stopped **before** the new one started, **and** that exactly one Warning was logged.
- **Every other test** asserts the Warning count is **0**.

Test names start with their FR id (G3). Use `OpenWSFZ.TestSupport.Poll.*` for any wait, never a fixed delay (`TESTING_STRATEGY.md` §11); no real audio device, no real clock.

## 3. `REQUIREMENTS.md` (QA's wording; confirm the numbers are free on `origin/main`)

| id | title | text |
|---|---|---|
| FR-097 | The capture pipeline has one owner, reconciled from the current configuration | One component SHALL be the only code that constructs the cycle framer, writes its slot and starts or stops capture, serialised by one semaphore; it SHALL converge on the configuration read inside the semaphore (run iff `AudioDeviceId` is non-null and `DecodingEnabled` is true), SHALL leave a running pipeline alone when asked to start it again, SHALL keep at most one framer alive at every step, SHALL stop any framer found before starting a new one and warn once if it had to, and SHALL log each start and stop with its reason. |
| FR-098 | A device change while decoding is off is saved only | While `DecodingEnabled` is false, a change of `AudioDeviceId` SHALL be persisted and SHALL NOT start capture, the framer or any decode; the next start of decoding SHALL use the stored device. |

Each row needs a test whose DisplayName starts with its id (mapping in `tasks.md` section 1).

## 4. Acceptance (what QA checks)

- T1 to T11, each able to fail. QA's mutations, each alone: **m1** drop the stop-before-start in the start step (T8); **m2** let a device change start while decoding is off (T1, T6); **m3** config read at trigger time (T3); **m4** restart on an unchanged-device save (T4); **m5** skip the Warning (T8); **m6** a failed capture treated as not running (T5); **m7** a start path left outside the controller (the grep).
- **Q2 grep** on the reviewed commit: `new CycleFramer(`, writes to the framer slot, `captureManager.StartAsync/StopAsync`, `runningDevice`, `runningEnabled` only in the controller (and tests).
- Full unfiltered `dotnet test OpenWSFZ.slnx` green (exact command lines and per-project counts, HK-022), `openspec validate --all --strict`, version and traceability gates, `git diff --stat -- native/` empty.
- Then QA reviews (HK-039), runs `pre_merge_check.py` from a clean checkout of the exact commit (HK-006), and L1 (the live scratch-instance check) on the Captain's go before he is asked for the push and the merge.

## 5. Report back

Commit hashes; the exact test command lines with counts; which test carries which FR id; where the controller lives and its public surface; the list of existing tests whose fixtures you changed (FILE:LINE); the output of the Q2 grep yourself; confirmation that the diff touches nothing under `native/`; any place the spec and the code disagree. Do not push.
