**User-facing:** yes

## Why

Issue #266 (QA, 2026-10-25): on the second instance (port 8081) a device change made while decoding was off, followed by `decode/start`, left **two `CycleFramer`s running on the one process-lifetime capture channel**. Each took about half the chunks, so every window spanned about 30 s of wall time, the cycle stamps stepped by 30 s with duplicates, 85 of 90 cycles decoded nothing, and only a daemon restart cured it (Architect spec `arch/framer-266`, §0; the main station is not affected: 1 pipeline start in 458 cycles).

Reading the code for the fix found two more things from the same root (Architect spec §1):

- **F2.** With decoding off, a device change starts a full pipeline: the daemon decodes, writes `ALL.TXT`, shows the decodes and feeds external reporting (59 decodes in 5 cycles on the 8081 instance while `DecodingEnabled` was `false`).
- **F3.** The two `OnSaved` branches are edge-triggered and each runs in its own task; `SemaphoreSlim` is not FIFO, so two quick saves can run in the other order and leave a pipeline the configuration does not describe (reasoned from the code, not observed).

The standing specs also contradict each other: `audio-capture` (2026-05, before decode control) says a device change always restarts capture; `decode-control` says nothing starts while decoding is off and that `decode/start` on a running pipeline leaves it running without a restart.

The Captain decided on 2026-10-26 (18:13:25Z): **D1 = a**, a device change while decoding is off is saved only; **D2 = a**, one owner for the whole pipeline (not a ten-line patch).

## What Changes

- A new class in `src/OpenWSFZ.Daemon/` (working name `PipelineController`) is the only code that constructs a `CycleFramer`, writes the framer slot, starts or stops capture, resets the audio, data-flow and spectrum monitors, or holds the serialising semaphore. `Program.cs` keeps wiring only. The edge-trigger state `runningDevice` / `runningEnabled` is deleted.
- One entry point, `ReconcileAsync(reason, forceRestart)`: inside the semaphore it reads the **current** configuration and converges (run on `AudioDeviceId` iff it is non-null and `DecodingEnabled` is true; restart on a different device or when forced; start when desired and stopped; stop when not desired and running; otherwise nothing).
- Every path goes through it: startup auto-start, CaptureFailed and watchdog retries, the configuration save handler (both branches collapse into one call) and shutdown.
- At most one framer, defended: the start step stops anything found in the slot first and logs one Warning if it ever had to.
- Observable: Information lines `Pipeline started on '{Device}' (reason: {Reason}).` and `Pipeline stopped (reason: {Reason}).`.
- `audio-capture` "Capture lifecycle managed by daemon" is corrected to condition the start and the device-change restart on `DecodingEnabled`; `decode-control` gains the one-owner requirement with its scenarios.
- **Visible behaviour change (narrow):** choosing an audio device while decoding is off no longer starts capture, so the level meter and waterfall stay idle until decoding is started (they are already idle after `decode/stop` and at startup with decoding off; they are driven by capture chunks).
- `REQUIREMENTS.md`: FR-097 and FR-098 (numbers to be confirmed against `origin/main`). `VERSION` bump (G9b; 0.65 expected). **No `native/` change, no shim bump.**

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `audio-capture`: "Capture lifecycle managed by daemon" now depends on `DecodingEnabled`.
- `decode-control`: ADDED "The pipeline has one owner and is reconciled from the current configuration".

## Impact

- `src/OpenWSFZ.Daemon/Program.cs` (the framer slot, `StartPipeline`, `StopFramerAsync`, `RestartPipelineAsync`, the `OnSaved` handler, the shutdown hook), a new controller class, `CaptureAutoStartCoordinator.cs` (a doc comment only; its tests pass unchanged).
- Out of scope: #238 (lazy grid realignment; the 85 clamps are a symptom of the split), the 3-s framer and 10-s capture stop timeouts, the UI, the one process-lifetime `Samples` channel.
