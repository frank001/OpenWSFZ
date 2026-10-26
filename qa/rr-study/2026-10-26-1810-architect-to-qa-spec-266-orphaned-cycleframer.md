# Architect to QA: issue #266. One pipeline owner: no orphaned CycleFramer, and "decoding off" means off

**Stamped:** 2026-10-26 18:10:16Z (`date -u`, when drafting began). **To: QA.** QA writes the OpenSpec change and the
Developer handoff (HK-015, HK-000). Branch `arch/framer-266`, off `origin/main` `dd61a7e9` (v0.64, local).

**The Captain, first-hand in the Architect's window:** *"write the spec for gh issue #266?"*. This spec is written.
QA may start the (k) review now. **The handoff waits on the Captain's two decisions in §6.**

This is a `src/` change (`src/OpenWSFZ.Daemon/`), so it needs a separate Developer session (HK-011), QA's HK-039
review before any live check, and `pre_merge_check.py` before any push (HK-006).

## 0. Evidence this rests on

- **Issue #266** (QA, filed 2026-10-25 15:05Z) and the board entries of 2026-10-25 14:59Z / 15:05Z.
- **The 8081 instance's first log**, `D:\Projects\claude\_qa-scratch\daemon-8081\logs\openswfz-20261025T135440Z.log`
  (log times are local, +01:00; UTC below). Read by the Architect on 2026-10-26, **counts and timestamps only**:
  - `Starting FT8 pipeline` + `CycleFramer started` at **13:55:51Z** (the Settings device change, decoding OFF),
    **13:57:26Z** (`POST /api/v1/decode/start`) and **14:16:05Z** (`decode/stop` at 14:16:04Z, then `decode/start`).
    No "stopped" line exists for the first framer (the framer logs its cancellation at Debug only, `CycleFramer.cs:436`).
  - `Cycle-grid realignment clamped`: **0** before the second start, **85** after it.
  - `decode(s) found` lines: 90 in total. **The first five cycles, 13:56:00–13:57:15Z, all before `decode/start`,
    found 0 + 12 + 14 + 19 + 14 = 59 decodes while `DecodingEnabled` was `false`.** The board's 13:57:00Z
    PSK Reporter warning ("10 decodes refused", identity placeholder) shows they reached the external-reporting path.
    ⇒ **a second defect, not in #266's text: with decoding "off" the daemon decodes and publishes.**
- **Product code, on `origin/main` `dd61a7e9`** (all lines grepped on that commit):
  - `Program.cs:389-391`: `framerCts`, `framerTask` (one slot each) and `restartSemaphore`.
  - `Program.cs:976-994`, the config `OnSaved` **device-change branch**: whenever `newDevice != runningDevice` it
    calls `RestartPipelineAsync(newDevice, stopCaptureManager: true)` **whatever `DecodingEnabled` is**, and returns.
  - `Program.cs:996-1041`, the **`DecodingEnabled` branch**: on false → true it calls **`StartPipeline(newDevice)` bare**
    (`:1009`, inside the semaphore but with no `StopFramerAsync`); on true → false it stops the framer and capture.
  - `Program.cs:1126-1151`, `StartPipeline`: `framerCts = new ...` and `framerTask = ...` overwrite the slots **without
    stopping the framer already in them**. That framer's token source is lost; nothing can cancel it again.
  - `Program.cs:1153-1172`, `StopFramerAsync`: cancels only what is in the slot.
  - `CaptureManager.cs:60, 90-97`: `Samples` is **one channel for the life of the process** (`SingleReader = false`).
    `StartAsync` (`:118`) stops and restarts the source but keeps the channel. ⇒ an orphaned framer keeps reading it,
    across every later stop/start, and two framers each take about half the chunks: each window then spans ~30 s of
    wall time, which is the 30-s stamp step, the duplicate stamps and the clamp on every window in the log.
  - `Program.cs:369-385`: `framerOutput` and `earlyOutput` are `SingleWriter = true`; two framers violate that
    contract (undefined behaviour in `System.Threading.Channels`, on top of the split).
  - `Program.cs:848`, the startup auto-start, and `CaptureAutoStartCoordinator.cs:119` (CaptureFailed / watchdog
    retries) **both refuse to start when `DecodingEnabled` is false**. `CaptureRecoveryState.DeriveCaptureState`
    (`src/OpenWSFZ.Web/CaptureRecoveryState.cs:140-142`) reports `Idle` when decoding is disabled. Only the device-change branch disagrees.
  - `CaptureAutoStartCoordinator.cs:38-45, 152-158`: an **adoption** (rotated device ID) only saves the config and
    relies on the device-change branch being the one start that follows ("No double restart, by construction").
- **The standing specs disagree with each other, and the code follows the older one:**
  - `openspec/specs/audio-capture/spec.md:58, 70-73` (2026-05, before decode control existed): a device change
    "SHALL stop the current capture session and start a new one". No mention of `DecodingEnabled`.
  - `openspec/specs/decode-control/spec.md:27-35` (FR-017, 2026-05-30): the pipeline starts at startup only when
    `DecodingEnabled` is true; **`:62-66`: `decode/start` while the pipeline runs SHALL leave it running "without a
    restart"**. The code violates that scenario: it starts a second framer.
- **Exposure of the main station:** QA counted 1 pipeline start, 0 clamps, 0 duplicated stamps in 458 cycles. A
  station that starts with decoding ON and uses `decode/stop` / `decode/start` is safe today (stop empties the slot
  first). The trigger is a device change (operator, or an adoption) **while decoding is off**, followed by a start.
- **Precedent for the testability fix:** `CaptureAutoStartCoordinator` was extracted from `Program.cs` (#187)
  precisely so the restart logic could be unit-tested. `Program.cs`'s top-level wiring has no test; that is why this
  defect shipped and why the fix must not stay there (§6 D2).

## 1. The defects, stated

- **F1 (the #266 defect).** More than one `CycleFramer` can run at once; the extra one can never be stopped; capture is
  split between them and decoding collapses until the process restarts.
- **F2 (found while writing this).** With `DecodingEnabled = false`, a device change starts a full pipeline: the daemon
  decodes, writes `ALL.TXT`, shows the decodes and feeds external reporting while the UI says decoding is off.
- **F3 (latent, same root).** The two `OnSaved` branches are **edge-triggered** and each runs in its own `Task.Run`.
  `SemaphoreSlim` does not guarantee FIFO order, so two quick saves (e.g. Stop then Start, or a device change then
  Start) can execute in the other order and leave the pipeline in a state the config does not describe. Not observed;
  stated from the code.

## 2. Requirements (for the Developer, via QA)

- **R1 One owner.** A new class in `src/OpenWSFZ.Daemon/` (working name `PipelineController`) owns, and is the only
  code that touches: the framer slot (`framerCts`/`framerTask`), `CycleFramer` construction, `captureManager`
  start/stop, the `audioMonitor` / `dataFlowMonitor` / `spectrumAnalyser` resets, and the serialising semaphore.
  `Program.cs` keeps the wiring only. Its collaborators are injected as delegates or small interfaces, as
  `CaptureAutoStartCoordinator` does, so every rule below is unit-testable with fakes and a fake clock.
- **R2 Level-triggered reconcile.** One entry point, `ReconcileAsync(string reason, bool forceRestart = false)`. Inside
  the semaphore it reads **`configStore.Current` at that moment** (not a value captured when the trigger fired) and
  converges:
  - desired = running on `AudioDeviceId` **iff** `AudioDeviceId` is non-null **and** `DecodingEnabled` is true
    (subject to D1);
  - running on a different device, or `forceRestart` ⇒ stop, then start if desired;
  - desired and not running ⇒ start; not desired and running ⇒ stop; otherwise **no action** (this is the
    decode-control `:62-66` scenario: Start while running does not restart).
  - Because every call reads the current config, the order in which queued calls run no longer matters (closes F3).
- **R3 Every path goes through it.** Startup auto-start (via the coordinator), CaptureFailed and watchdog retries (the
  coordinator's `startCaptureAsync` ⇒ `ReconcileAsync("capture-retry", forceRestart: true)`), the config `OnSaved`
  handler (both branches collapse into one `ReconcileAsync("config")` call when the device or `DecodingEnabled`
  changed), and shutdown (`StopAsync` under the same semaphore, keeping today's order: health monitor, framer,
  decoder dispose, capture). **No code outside the controller may construct a `CycleFramer` or write the slot**; QA
  checks this with a grep of `src/` (§4 Q2).
- **R4 At most one framer, defended.** The start step stops anything in the slot first. If it ever finds the slot
  occupied at a point where it should be empty, it stops the old framer, then logs **one Warning**
  (`"Pipeline start found a framer still running; stopped it first (reason: {Reason})."`). This is defence in depth;
  T1–T4 must show it never fires on the normal paths.
- **R5 Stopping is observable.** The controller logs at Information: `"Pipeline started on '{Device}' (reason:
  {Reason})."` and `"Pipeline stopped (reason: {Reason})."`. A log reader can then count starts minus stops, which is
  the number of framers that should be running (0 or 1). The existing `Starting FT8 pipeline` and `CycleFramer
  started` lines stay as they are (QA's tools and the 8081 analysis count them).
- **R6 Keep the adoption contract.** An adoption still causes exactly one start (`audio-capture/spec.md:197-199`).
  With R2 this holds naturally (the save triggers one reconcile, the device differs, one stop + one start). The
  existing `CaptureAutoStartCoordinatorTests` pass **unchanged**; the coordinator's doc comment `:38-45` is updated to
  name the controller instead of "OnSaved's device-change branch".
- **R7 Device change while decoding is off:** per the Captain's D1. Recommended: no capture, no framer (R2's rule as
  written). The Settings save still persists the device; the next `decode/start` starts on it.
- **R8 Spec text.** QA amends `audio-capture` "Capture lifecycle managed by daemon" (`:58`, scenario `:70-73`) to
  condition the restart on `DecodingEnabled` (per D1), and adds to `decode-control` the scenario "device changed while
  disabled, then Start ⇒ exactly one framer runs". Version bump per `check_version_bump.py` (QA decides the level).
- **Out of scope:** #238 (lazy grid realignment; the 85 clamps here are a symptom of the split, not that defect);
  the 3-s framer and 10-s capture stop timeouts; the UI. No `native/` change.

## 3. Tests (the Developer writes them; QA reviews per HK-039)

All against the controller with fake capture, fake framer factory (counts live framers) and fake config store.

- **T1 (the #266 repro).** Decoding off, device A set ⇒ 0 framers (D1 = a). Then `DecodingEnabled = true` ⇒
  **exactly 1** framer, on A.
- **T2.** Decoding on, running on A; 50 alternations of off/on ⇒ live framers never exceed 1 at any step (the fake
  factory records the maximum); ends at 1.
- **T3 (ordering, F3).** Queue `ReconcileAsync` calls in shuffled order around config changes (seeded; sort nothing
  by hash) for: device change + Start; Stop + Start; Start + Stop. The end state always matches the final config; the
  maximum live framer count is ≤ 1 in every permutation.
- **T4.** Device change A → B while running ⇒ one stop, one start, 1 framer on B. Same device saved again (no change)
  ⇒ no action (no restart; decode-control `:62-66`).
- **T5.** `forceRestart` (the retry path) while running ⇒ one stop then one start; while decoding is off ⇒ nothing.
- **T6 (F2).** With decoding off, no path (device change, adoption, retry, watchdog) starts capture or a framer.
- **T7.** Shutdown while running ⇒ 0 framers, capture stopped, in today's order; shutdown racing a reconcile waits
  for it (semaphore) and leaves 0.
- **T8.** R4's Warning fires when the slot is pre-seeded with a live fake framer, and the old one is stopped first.
- **T9 (adoption, R6).** An adoption save while decoding is on ⇒ exactly one start.
- Existing suites green, including `CaptureAutoStartCoordinatorTests` unchanged and the decode-control web tests.

## 4. QA steps

- **Q1 HK-039 review** of the Developer commit, with these **mutations** (each must be killed by T1–T9):
  (m1) drop the stop-before-start in the start step; (m2) let a device change start when decoding is off; (m3) read
  the config captured at trigger time instead of `Current` inside the semaphore; (m4) restart on an unchanged-device
  save; (m5) skip the Warning in R4.
- **Q2 Single-owner grep** on the reviewed commit: `new CycleFramer(` and any write to the framer slot occur only in
  the controller (and tests). Report the grep and its hits.
- **Q3** `git diff --stat -- native/` empty; `pre_merge_check.py` from a clean checkout of the exact commit (HK-006).

## 5. Live check L1 (the Captain's go: his PC, not his station's daemon)

A **separate scratch instance** (its own port and config under `D:\Projects\claude\_qa-scratch\framer-266\`, any
capture device that carries FT8 audio, e.g. the Voicemeeter bus the 8081 instance used). The main station's daemon
is not touched. About 15 minutes per build.

- **Script (both builds):** start with `decodingEnabled: false`; choose the device in Settings and save; wait 2
  cycles; press Start decoding; read 20 cycles; press Stop, then Start; read 20 more cycles.
- **L1-a positive control, on `main` `dd61a7e9`** (HK-026: the instrument must see the defect where it exists).
  **Pass = at least one duplicated cycle stamp in the first 20 cycles after Start.** Bar source: the 8081 log on the
  same code (29 of 61 stamps duplicated). If L1-a does not reproduce, L1-b is VOID (the script did not hit the path)
  and QA reports before going on.
- **L1-b, on the fix build (after HK-039 APPROVED).** Pass = all of:
  - **0 duplicated cycle stamps** in the 40 cycles (bar source: 0 duplicated stamps in 180 cycles after the 8081 process
    restart, #266's table; 0 in 458 cycles on the main station, QA's count; there is no legitimate cause of a duplicate);
  - **no pipeline start before the first Start** (D1 = a), and R5's starts − stops = 1 after each Start;
  - **no decodes logged** in the 2 cycles before Start (F2).
  - Reported, **not** a bar: clamp warnings (a clamp can follow a slow residual pass, as seen on sol; 0 of 458 on the
    Windows station is the reference) and decodes per cycle (band-dependent).
- Counts only from the logs (NFR-021, HK-037: no message text leaves the reading function).

## 6. For the Captain: two decisions before the handoff

**D1. What should choosing a device do while decoding is off?** (matters: it sets what "off" means)

| Option | What happens | Cost / risk |
|---|---|---|
| **a. Save only (recommended)** | The device is stored; nothing captures until Start. Same as startup and the automatic retries today. | Smallest change. No audio level / waterfall from that device until Start (QA to check whether the UI shows either while off; I have not). |
| b. Capture without decoding | Audio runs (level meter, waterfall), no framer, no decodes. | A new third state to build and test; the capture channel then fills and drops chunks, which today's loss counters would report as loss unless that is also changed. |
| c. As today, made safe | A full pipeline runs: decodes, `ALL.TXT`, external reporting, PSK Reporter. | Keeps F2: the 8081 instance made 59 decodes in 5 cycles with decoding "off", and they reached the upload path. Not recommended. |

**D2. How big a fix?** (matters: it decides whether this can recur)

| Option | What it is | Cost / risk |
|---|---|---|
| **a. One owner (recommended)** | §2 as written: a `PipelineController`, level-triggered, unit-tested (T1–T9). | My estimate, not measured: ~150 lines moved plus tests; one Developer round. Closes F1, F2 and F3, and makes the start/stop logic testable for the first time. |
| b. Minimal patch | `StartPipeline` stops the old framer first; the `DecodingEnabled` branch uses `RestartPipelineAsync`; the device branch checks `DecodingEnabled`. ~10 lines in `Program.cs`. | Fixes F1 and F2, not F3. No unit test can reach `Program.cs`'s top-level code, so only L1 would check it; a later edit there could bring it back unseen, as this one shipped. |

## 7. Limits, stated in the report

- F3 is reasoned from the code; nobody has observed it.
- One affected instance, one log. That the main station is clean rests on QA's count of its log (1 start, 458 cycles).
- I have not checked whether the web UI's level meter or waterfall work while decoding is off (bears on D1 b).

## 8. Predictions (blind; scored at the rulings)

- **PR1** L1-a reproduces on `dd61a7e9` (≥ 1 duplicated stamp in 20 cycles after Start). 0.90 C.
- **PR2** L1-b passes on the first fix build QA approves. 0.80 C.
- **PR3** Q2 finds no `CycleFramer` construction outside the controller on the first Developer commit. 0.75 C.

## 9. For QA, in order

1. (k) review of this spec; findings to the Architect.
2. After the Captain's D1/D2: the OpenSpec change (R8), `tasks.md`, the Developer handoff, the Developer nudge.
3. HK-039 review with Q1–Q2; `pre_merge_check.py` (Q3).
4. L1 on the Captain's go; then his push go and merge sign-off.
