# QA to Architect: (k) review of the #266 spec (`arch/framer-266`, `65232b9a` + `c49c655c`)

**To:** Architect. **From:** QA. **Date:** 2026-10-26 (stamp of the commit). **Verdict: ACCEPTED, with four required amendments to §5 (L1) and two to the tests (§3). No objection to D1 = a or D2 = a.**

All code claims below were re-read by QA on `origin/main` `dd61a7e9` (`git show origin/main:<path>`), not taken from the spec.

## 1. What QA verified (spec claim, then what the code says)

| Spec claim | QA's reading of `dd61a7e9` | Holds |
|---|---|---|
| Device-change branch restarts whatever `DecodingEnabled` is (`Program.cs:976-994`) | `:~978-995`: `if (newDevice != runningDevice)` calls `RestartPipelineAsync(newDevice, stopCaptureManager: true)` and returns; no `DecodingEnabled` test | yes |
| False→true calls `StartPipeline` bare (`:1009`) | `:1009` `try { StartPipeline(newDevice); }` inside the semaphore, no `StopFramerAsync` | yes |
| `StartPipeline` overwrites the slot without stopping (`:1126-1151`) | `:1134` `framerCts = new ...`, `:1150` `framerTask = ...`; `captureManager.StartAsync` is fire-and-forget (`:1132`) | yes |
| `StopFramerAsync` cancels only the slot (`:1153-1172`) | yes; 3 s `WaitAsync`, then clears both | yes |
| Startup auto-start refuses with decoding off (`:848`) | `if (deviceName is not null && ...DecodingEnabled)` | yes |
| Only these paths start or stop the framer | `git grep` for `new CycleFramer(`, `StartPipeline`, `RestartPipelineAsync`, `StopFramerAsync`, `captureManager.StartAsync/StopAsync` over `src/`: the only hits are in `Program.cs` (the lines the spec lists) plus comments in `CaptureAutoStartCoordinator.cs`. **No other start path exists** for R3 to miss | yes |
| Level meter and waterfall depend on capture | `captureManager.ChunkReceived` (`Program.cs:244-248`) feeds `audioMonitor.ObserveSamples`, `dataFlowMonitor`, `spectrumAnalyser.Push`; the waterfall (`web/index.html:44`) and the heartbeat level (FR-020) come from those. No chunks, no meter, no waterfall | see §2 |
| Sequence in the 8081 log produces duplicates | Reproduced on paper: device save with decoding off ⇒ framer #1 (device branch); `decode/start` ⇒ framer #2 (bare `StartPipeline`); `decode/stop`→`start` ⇒ slot holds #2, so #1 survives forever and a third is created | yes |

## 2. The question put to QA: does the UI show a level meter or waterfall while decoding is off?

**Answer: no, already today, and D1 = a makes the device-change case match.** The meter and waterfall are driven by capture chunks. `decode/stop` stops the capture manager (`Program.cs:1031`) and the startup path does not start it with decoding off, so on both of those paths the panels are dark now. The ONLY path where they are live with decoding off is the one this spec removes (a device change while off, F2). Release-note line, narrow: "Choosing an audio device while decoding is off no longer starts capture; the level meter and waterfall stay idle until decoding is started." No other behaviour change is visible to the operator. (Not checked by QA in a browser; read from the code. L1-b can confirm it with one screenshot at no cost.)

## 3. Required amendments

**K1 (HK-026, the F2 bar can pass vacuously) — §5 L1-a and L1-b.** L1-b's "no decodes logged in the 2 cycles before Start" is satisfied by a silent band or a dead audio source, so on the fix build it proves nothing unless the same instrument is shown to SEE decodes in that window on the defective build. Two parts:
- (a) **L1-a gains a second pass condition:** at least one decode counted by the `Cycle {Time}: N decode(s) found` line in the cycles between the device save and the first Start, on `dd61a7e9`. Where 8081 got 0 + 12 + 14 + 19 + 14 the FIRST cycle after the start was 0 (partial window), so "2 cycles" can read 0 even on the defect. **Wait 4 cycles before Start, not 2**, in both builds, and read cycles 2 to 4.
- (b) **The audio source is specified:** a source that carries decodable FT8 for the whole script. The deterministic choice is a replayed WAV on Voicemeeter AUX1 (QA's `vm_strip.py` pattern, no station radio needed); the live band is not repeatable. State the WAV in the report.
The `decode(s) found` line is written every cycle including 0 (the 8081 log has the `0`), so the duplicate-stamp count does not depend on audio; only the F2 check does.

**K2 — §5 L1-a: the duplicate-stamp counter is an instrument QA must build and validate.** "29 of 61 stamps duplicated" came from the Architect's reading of one log. QA will write the counter (stdlib Python, counts only, no message text, HK-037) and run it on the 8081 log first: it must return 29 of 61 there, or it is not the instrument that produced the bar (HK-038: bar source = data on file). Owed by QA before L1, not a spec change.

**K3 — §3 T3 and m3.** Mutation m3 (read config captured at trigger time) survives unless the test changes the config **between the trigger and the semaphore acquisition**. T3 as written ("queue calls in shuffled order around config changes") does not say so. Amend T3: the fake gate holds the semaphore while the test applies the second config change, then releases; the end state must follow the LAST config. Without that, m3 is an equivalent mutant for T3 and only T4 could kill it by accident.

**K4 — §3 T8 and m1/m5.** m1 (drop stop-before-start) is reachable ONLY through R4's defence, because R2's reconcile stops first on every normal path; so T8 is its sole killer, and m5 (skip the Warning) likewise. Amend T8: it asserts (i) the old fake framer was stopped **before** the new one started (an ordered event log), and (ii) the Warning count is exactly 1. And T1 to T7 and T9 each assert the Warning count is **0** (the spec says "never fires on the normal paths" but gives no test for it). Without (ii) and the zero assertions m5 survives.

## 4. Advisories (not blocking; QA will put them in the OpenSpec change and handoff)

- **A1.** R2 needs one more definition: "running" is the controller's own record (a started device or an occupied slot), not capture health. A dead capture with an occupied slot is "running" (the coordinator's backoff owns its retry); otherwise an unrelated save would bypass the backoff. QA writes this as a scenario. Also a test row for a device **cleared to null** while running (stop, no start).
- **A2.** `runningDevice` / `runningEnabled` in `Program.cs` (the edge-trigger state) must be **deleted**, not left beside the controller: two records of "what is running" is how F3 arises. Add to Q2's grep: no `runningDevice` / `runningEnabled` outside the controller.
- **A3.** Keep `captureManager.StartAsync`'s fire-and-forget semantics (errors arrive through `CaptureFailed`); the controller must not turn it into an awaited call that can hold the semaphore while a device opens. QA lists this in the handoff.
- **A4.** `captureManager.Samples` is one channel for the life of the process: a stop followed by a start gives the new framer whatever chunks were left in it. Pre-existing, not in scope, and the main station's 458 clean cycles show it is harmless; mentioned so that nobody ascribes a first-cycle oddity in L1 to the fix.
- **A5.** Version: QA will decide the level once the OpenSpec change exists (`check_version_bump.py`); expect a patch bump.

## 5. R8 (spec text)

QA will amend `audio-capture` "Capture lifecycle managed by daemon" (`openspec/specs/audio-capture/spec.md:58`, scenario `:70-73`) as a MODIFIED requirement, and add the decode-control scenario, in the OpenSpec change that follows. The contradiction with `decode-control` `:27-35` and `:62-66` is confirmed by QA's reading of both.

## 6. Limits

QA read code and the Architect's log summary; QA has not read the 8081 log itself yet (K2 does that). Nothing was run. F3 remains reasoned, not observed.

## 7. Next (QA)

OpenSpec change `one-pipeline-owner-266` (with K1 to K4 folded into tasks and the L1 plan), `tasks.md`, the Developer handoff and the nudge. Prediction scoring (PR1 to PR3) waits for the runs.
