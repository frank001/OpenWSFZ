**User-facing:** no

## Why

On `sol` (Linux, FX-8350), OpenWSFZ's cycle-to-cycle consistency is worse than WSJT-X's because OpenWSFZ's own capture timing wanders (replay-consistency sweeps 1-5, shift test, step test, log step, 2026-10-16). The step test reproduces 0.94 [0.81, 1.07] of the capture-side gap; OpenWSFZ's capture is stepped forward (audio skipped) in 21 of 180 windows against WSJT-X's 3 of 180, all 21 while the previous cycle's residual pass was still running. The decoder is deterministic (180 of 180).

**Nothing in the product can see audio being lost on Linux.** Source read (`origin/main` `25aaf90f`):

- `ArecordAudioSource` redirects `arecord`'s stderr (`RedirectStandardError = true`) and nothing reads it, so ALSA overrun lines are invisible, and a stderr pipe that is never drained eventually fills and blocks `arecord` altogether.
- `CaptureManager`'s bounded channel (16 chunks, `DropOldest`) drops chunks with no callback and no log.
- `CycleFramer` measures the result of any loss (`wanted`, the sample-stream-versus-wall-clock error at each window start), but only logs it when clamped (Warning); the applied value is at Debug.

The Captain decided to instrument first and fix afterwards (2026-10-17, "spec it for qa"; Architect spec `qa/rr-study/2026-10-17-0927-architect-to-qa-spec-capture-loss-instrument.md`, amendment 1 `7c31c1dd`).

## What Changes

- `ArecordAudioSource` **drains stderr** concurrently with stdout, logs every `overrun` line at Warning with the receive time (UTC, milliseconds) and `arecord`'s own line verbatim, and counts them (`CaptureOverrunCount`). Other lines are logged at Information, rate-limited. `arecord` is started with `LC_ALL=C` so the text is not localised.
- `CaptureManager` **counts channel drops** via the channel's `itemDropped` callback (`CaptureChannelDroppedChunks`) and logs the first and every 100th at Warning, with the UTC millisecond time.
- `CycleFramer` logs **every window's realignment at Information**: the cycle start, `wanted` and applied, in samples. The arithmetic is untouched.
- The three counters are added to `DaemonStatus` (`GET /api/v1/status` and the WebSocket `status` event), the way `CycleArchiveDroppedCycles` is. **The `Heartbeat:` log line is NOT changed**: FR-067 fixes its text byte for byte and supervisor scripts string-match it.
- **Capture behaviour is unchanged.** Same `arecord` arguments, same stdout handling, same chunks (byte-identical, tested), same realignment arithmetic.

## Non-goals

No fix (buffer size, thread count, priority, #234). No GUI change. No macOS `sox` source (same stderr pattern; follow-up). No Windows `WasapiAudioSource` change (it already warns on its own drops).

## Capabilities

### Modified Capabilities

- `audio-capture`: capture-loss visibility requirements (stderr drain and overrun counting on the `arecord` source, channel-drop counting, per-window realignment logging, counters on the status surface).

## Impact

`src/OpenWSFZ.Audio/ArecordAudioSource.cs`, `src/OpenWSFZ.Audio/CaptureManager.cs`, `src/OpenWSFZ.Ft8/CycleFramer.cs` (one log line), `src/OpenWSFZ.Web/DaemonStatus.cs`, `src/OpenWSFZ.Web/WebApp.cs`, `src/OpenWSFZ.Web/WebSocketHub.cs`, `src/OpenWSFZ.Daemon/Program.cs` (provider wiring); tests in `tests/OpenWSFZ.Audio.Tests` and `tests/OpenWSFZ.Ft8.Tests`. Nothing in `native/`; no shim change.
