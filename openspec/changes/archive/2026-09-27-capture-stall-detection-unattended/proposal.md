**User-facing:** yes

## Why

GitHub issue **#188**. The capture watchdog and the live data-flow signal only work while a browser
tab is open. On an unattended run, which is the normal mode for `qa/endurance/`, nothing in the
daemon can see a silent capture stall, and nothing outside it can either.

Verified against `origin/main` @ `5a9290c6` on 2026-09-24:

- `AudioWatchdog.TickAsync` has **one** call site: `WebSocketHub.HandleAsync` (`WebSocketHub.cs:348`),
  which runs once per accepted WebSocket connection. With no client connected, the watchdog never ticks.
  It exists (`AudioWatchdog.cs:11-14`) to catch "silent-stop scenarios that no WASAPI event handler
  can detect", and those are exactly the failures an unattended run cannot otherwise survive.
- `DataFlowMonitor` is the correct stall signal, because any chunk counts, whatever its amplitude. But its only consumer
  is the same per-connection loop (`WebSocketHub.cs:335`), and it is not on `GET /api/v1/status`.
- `GET /api/v1/status` (`WebApp.cs:299-314`) serves two fields that cannot show a stall:
  - `captureActive` = `CaptureManager.IsCapturing`. `CaptureManager.cs:22-38` documents that this
    stays `true` through a stall that throws nothing.
  - `audioActive` = `AudioActivityMonitor.IsActive`, a **one-way latch** that only the WebSocket loop
    resets. With no client connected it reads `true` for the rest of the process after the first
    non-zero sample.
- The `Heartbeat: captureActive=…, audioActive=…, dataFlowing=…` log line is written from the same
  per-connection loop, so an unattended run has **no heartbeat line in its log at all**. The standing
  pre-arm check (`operational-note-audio-endpoint-guid-goes-stale`) tells the operator to look for
  that line, and it can only exist when a browser happens to be open.

Two further defects in the same loop, found while tracing the issue:

- **The shared flags are drained by every connected client.** Each connection calls
  `dataFlowMonitor.ConsumeAndReset()` and `audioMonitor.ConsumeAndReset()` on its own 5 s timer.
  With N clients, the singleton watchdog is ticked N times per 5 s window, so during a real stall
  its 15 s threshold is reached after about 15/N s. The per-window result each client sees also
  depends on how its timer phase lines up with the others'.
- **`audioActive` means three different things.** In the WebSocket heartbeat it means data flowing
  (B21). In the initial WebSocket `status` event it is `IsCapturing` (`WebSocketHub.cs:300`).
  On `GET /api/v1/status` it is the amplitude latch. FR-020 describes a fourth meaning, amplitude
  within the last 5 s, which the shipped code no longer implements.

**Impact.** On a 24 h unattended run, a capture pipeline that goes silent without throwing leaves
the daemon reporting healthy for the rest of the window, and no restart is attempted. The
supervisor's independent check (newest-WAV mtime) is the only thing that can catch it. That check exists
only because the daemon cannot report its own state. It also needs the cycle audio archive switched on.

## What Changes

- **Capture health is evaluated by the daemon, not by the web client.** A single daemon-lifetime
  ticker, every 5 s, owns the per-window evaluation. It consumes the data-flow and activity windows
  exactly once per window, ticks the one `AudioWatchdog` exactly once per window, and writes the
  `Heartbeat:` log line, whether or not any WebSocket client is connected.
- **WebSocket connections become readers.** The per-connection heartbeat loop sends the ticker's
  latest snapshot. It no longer calls any `ConsumeAndReset()` and no longer ticks the watchdog.
- **`GET /api/v1/status` gains live, non-latching capture-health fields:** `dataFlowing` (last
  completed window), `lastChunkAgeMs` (time since the most recent chunk, computed at request time
  from a monotonic clock) and `watchdogRestartCount`.
- **`audioActive` gets one meaning everywhere:** the `dataFlowing` value of the most recent
  completed window, on REST, the initial WebSocket `status` event and the WebSocket heartbeat.
  FR-020 is amended to match (see design D4). **Captain-ratified 2026-09-24.**
- The `Heartbeat:` log line **keeps its exact current format**. Older QA supervisor scripts
  string-match on it (`*"Heartbeat:"*"=false"*`).

**Out of scope:** re-resolving a stale device ID, retry backoff and the recovery state machine. Those are
issue #187, change `capture-device-reresolution`, which builds on this change's status surface.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `audio-capture`: adds three requirements for daemon-owned capture-health evaluation, the live
  data-flow fields on the status endpoint, and a single meaning for `audioActive`.

## Impact

- **Code (`src/`, HK-011 — Developer session required):** `OpenWSFZ.Web` (`WebSocketHub`,
  `WebApp`, `DaemonStatus`, `DataFlowMonitor`, `AudioActivityMonitor`, a new ticker type) and
  `OpenWSFZ.Daemon/Program.cs` (wiring). No `native/` change. No decoder change. No shim change.
- **API:** `GET /api/v1/status` and the WebSocket `status` payload each gain three fields, an
  additive JSON change. `audioActive` changes meaning on REST (latch → last window) and on the
  initial WebSocket `status` event (`IsCapturing` → last window). The only known REST reader,
  `qa/endurance/endurance_supervisor.py`, reads `captureActive` and `decodingEnabled`, not `audioActive`.
- **Behaviour on unattended runs:** the S6 watchdog becomes **active** on every run, including R&R
  and endurance runs. That is the intent. It is also a behaviour change QA must expect: a genuine
  15 s stall now causes a pipeline restart that previously never happened.
- **Docs:** `REQUIREMENTS.md` FR-020 amendment (design D4).
- **Adoption gate:** closing this issue is one of the two stated preconditions (with #187) before
  direct-USB-CODEC capture can become a default.
