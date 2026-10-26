## 1. Tests first (each able to fail; against the controller with a fake capture, a fake framer factory that counts live framers and records an ordered event log, a fake configuration store and a gate on the semaphore; test names start with their FR id for gate G3)

Requirement ids (confirm against `origin/main`'s `REQUIREMENTS.md`; use the next free ones if FR-097 is taken): FR-097 one owner, level-triggered reconcile, at most one framer, observable; FR-098 a device change while decoding is off is saved only.

Every test T1 to T7 and T9 to T11 also asserts the R4 Warning count is **0** (K4).

- [ ] 1.1 **T1 (FR-098, the #266 repro).** Decoding off, device A saved: 0 framers, capture not started (D1). Then `DecodingEnabled = true`: **exactly 1** framer, on A.
- [ ] 1.2 **T2 (FR-097).** Decoding on, running on A; 50 alternations of off/on: live framers never exceed 1 at any step (the fake factory records the maximum); ends at 1.
- [ ] 1.3 **T3 (FR-097, ordering, F3; kills m3).** With the semaphore held by the test gate, queue `ReconcileAsync` calls in shuffled order (seeded; sort nothing by hash) for each of: device change + Start; Stop + Start; Start + Stop; **change the configuration again while they wait**, then release. The end state follows the **last** configuration, and the maximum live framer count is at most 1 in every permutation. A variant that reads the configuration at trigger time must fail it.
- [ ] 1.4 **T4 (FR-097).** Device change A to B while running: one stop, one start, 1 framer on B. The same device saved again: no action (no stop, no start).
- [ ] 1.5 **T5 (FR-097).** `forceRestart` (the retry path) while running: one stop then one start. While decoding is off: nothing. With a failed capture and the record standing: still "running" (a save of another key causes no start).
- [ ] 1.6 **T6 (FR-098, F2).** With decoding off, no path (device change, adoption, retry, watchdog) starts capture or a framer, and none produces a pipeline-started line.
- [ ] 1.7 **T7 (FR-097).** Shutdown while running: 0 framers, capture stopped, in today's order (health monitor, framer, decoder dispose, capture); shutdown racing a reconcile waits for it and leaves 0.
- [ ] 1.8 **T8 (FR-097, the defence; kills m1 and m5).** The slot pre-seeded with a live fake framer: the start step stops it **before** the new framer starts (asserted from the ordered event log) and logs **exactly one** Warning (the text of the spec, no callsign).
- [ ] 1.9 **T9 (FR-097, adoption).** An adoption save while decoding is on: exactly one start. The existing `CaptureAutoStartCoordinatorTests` pass **unchanged**.
- [ ] 1.10 **T10 (FR-097).** `AudioDeviceId` set to null while running: stop, no start.
- [ ] 1.11 **T11 (FR-097, log).** One `Pipeline started` and one `Pipeline stopped` line per transition with the reason; over any scripted sequence, starts minus stops equals the live framer count (0 or 1).
- [ ] 1.12 Existing suites unchanged and green: the decode-control web tests, the config-save tests, the pump and capture tests.

## 2. Implementation

- [ ] 2.1 `PipelineController` (collaborators injected; `ReconcileAsync(string reason, bool forceRestart = false)`; the framer slot; the semaphore; the R4 defence; the R5 lines; `captureManager.StartAsync` kept fire-and-forget).
- [ ] 2.2 `Program.cs`: construct and wire it; delete `framerCts`, `framerTask`, `StartPipeline`, `StopFramerAsync`, `RestartPipelineAsync`, `runningDevice`, `runningEnabled`; the `OnSaved` handler becomes one `ReconcileAsync("config")` when the device or `DecodingEnabled` changed; the coordinator's `startCaptureAsync` becomes `ReconcileAsync("capture-retry", forceRestart: true)`; startup auto-start unchanged except through the coordinator; the shutdown hook calls the controller's stop under its semaphore.
- [ ] 2.3 `CaptureAutoStartCoordinator.cs` doc comments (`:35`, `:38-45`, `:67`, `:152-158`) name the controller instead of `RestartPipelineAsync` and "OnSaved's device-change branch"; no behaviour change.
- [ ] 2.4 `REQUIREMENTS.md`: the FR-097 and FR-098 rows (QA's wording in the handoff); `VERSION` bump (G9b; `User-facing: yes`); no `native/` change, no shim bump.

## 3. Verification

- [ ] 3.1 `dotnet build`, the full unfiltered `dotnet test OpenWSFZ.slnx` with the exact command lines and per-project counts (HK-022); `openspec validate --all --strict`; `python tools/check_version_bump.py origin/main`; the traceability gate clean.
- [ ] 3.2 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA reviews every commit (HK-039) before any live run; `pre_merge_check.py` runs from a clean checkout of the exact commit before any push (HK-006).
- [ ] 3.3 **QA mutations (Q1), each alone, each must be killed:** m1 drop the stop-before-start in the start step (T8); m2 let a device change start when decoding is off (T1, T6); m3 read the configuration captured at trigger time (T3); m4 restart on an unchanged-device save (T4); m5 skip the R4 Warning (T8); plus m6 treat a failed capture as not running (T5) and m7 leave a start path outside the controller (Q2).
- [ ] 3.4 **Q2 single-owner grep** on the reviewed commit: `new CycleFramer(`, writes to the framer slot, `captureManager.StartAsync/StopAsync`, `runningDevice`, `runningEnabled`: hits only in the controller and tests. Report the grep and its hits. `git diff --stat -- native/` empty.
- [ ] 3.5 **K2, before L1 (QA, no station time):** write the duplicate-stamp counter (stdlib Python, counts only, reads the `Window emitted` / `Cycle {Time}` lines, no message text) and run it on the 8081 log `D:\Projects\claude\_qa-scratch\daemon-8081\logs\openswfz-20261025T135440Z.log`. It must reproduce the Architect's count (29 duplicated of 62 distinct stamps in 91 windows) or the discrepancy is explained, before L1-a is read (HK-038).
- [ ] 3.6 **Live check L1 (QA, on the Captain's go; his PC, not the station's daemon).** Scratch instance under `D:\Projects\claude\_qa-scratch\framer-266\`, a replayed WAV on a Voicemeeter bus as the source (state the WAV), the script of design decision 11. **L1-a, on `main` `dd61a7e9` (positive control, HK-026): PASS = at least one duplicated cycle stamp in the first 20 cycles after Start AND at least one decode counted in cycles 2 to 4 before Start**; if either does not occur, L1-b is VOID and QA reports first. **L1-b, on the fix build after HK-039 APPROVED: PASS = 0 duplicated stamps in the 40 cycles; no pipeline start before the first Start; starts minus stops is 1 after each Start; 0 decodes in cycles 2 to 4 before Start.** Reported, not a bar: clamp warnings, decodes per cycle, one screenshot of the idle waterfall while off.
- [ ] 3.7 Merge needs the Captain's sign-off (HK-010).
