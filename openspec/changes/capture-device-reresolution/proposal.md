## Why

GitHub issue **#187**. `config.json`'s `audioDeviceId` holds a Windows MMDevice **endpoint ID**
(`{0.0.1.00000000}.{GUID}`). That ID can change after a replug, a driver re-initialisation or a power
cycle, while `audioDeviceFriendlyName` stays the same. When it changes, the daemon retries the dead ID
every 5 seconds for the rest of the process and never recovers.

Verified against `origin/main` @ `5a9290c6` on 2026-09-24:

- The `CaptureFailed` handler (`Program.cs:361-395`) re-reads `configStore.Current.AudioDeviceId`,
  the same possibly-stale string, and retries after a flat 5 s. It has **no cap, no backoff, no
  escalation and no re-resolution**. `captureRestartCount` (`:388`) is logged and never read.
- The watchdog restart action (`Program.cs:401-420`) and the startup auto-start (`Program.cs:742-744`)
  also use `configStore.Current.AudioDeviceId` verbatim. A GUID that rotated **while the daemon was
  stopped** therefore fails at startup and enters the same endless loop. The 2026-08-03 incident
  was hit at arm time.
- Nothing outside the log shows the loop: `captureActive` flickers, and the process stays alive.

Observed 2026-08-03, "Microphone (2- USB Audio CODEC )":
`{d451e08c-…}` → `{67987b85-…}` with the friendly name unchanged; `0x80070490 Element not found`,
`Chunks received: 0`, repeating. The same device class carries today's direct-CODEC endurance arm.

**Impact.** A mid-run replug or driver re-init causes permanent, total, silent loss of capture for
the rest of an unattended window. The Captain has ruled this, with #188, a precondition for making
direct-USB-CODEC capture a default.

## What Changes

- **Re-resolution by friendly name.** Before every *automatic* capture start (startup auto-start,
  `CaptureFailed` retry, watchdog restart), the daemon checks the configured ID against the
  currently **active** capture endpoints. If the ID is absent and **exactly one** active endpoint
  has the configured friendly name, byte-for-byte, the daemon adopts that endpoint's ID. It never
  guesses: zero matches, two or more matches, a disabled-only match or a failed enumeration all
  mean no adoption.
- **Adopted ID is persisted** to `config.json` through the normal config save path, with the
  friendly name unchanged, and logged at Warning with the old and new ID. This is a
  **Captain-ratified 2026-09-24** (design D3).
- **Bounded backoff, never giving up.** Automatic restarts follow 5 → 10 → 20 → 40 → 60 s, then
  stay at 60 s indefinitely. The schedule resets once a restarted session delivers its first chunk.
  Capture must keep trying (the standing directive "audio capture must always be running"),
  because a device unplugged for an hour must be picked up again when it returns.
- **Recovery state on `GET /api/v1/status`:** `captureState`
  (`Idle` | `Capturing` | `Recovering` | `DeviceUnavailable`), `captureRestartCount`,
  `consecutiveCaptureFailures` and `lastCaptureError`.
- `AudioDeviceInfo` gains an availability flag, so the resolver can tell an active endpoint from a
  disabled one. The provider already enumerates `Active | Disabled`, but the record cannot say which.

**Out of scope:** the TX output device (`audioOutputDeviceId`) has the same defect class. It is
flagged for a separate issue and not fixed here. The Architect → QA handoff for both changes is
`openspec/changes/capture-stall-detection-unattended/architect-to-qa-handoff.md`. Operator-initiated device changes
through `POST /api/v1/config` keep their current behaviour exactly: no re-resolution of an ID the
operator has just chosen.

**Depends on:** `capture-stall-detection-unattended` (#188). That change supplies the daemon-lifetime
ticker, `lastChunkAgeMs` and the status fields this change extends, and the live acceptance test
below reads them.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `audio-capture`: adds requirements for re-resolving a stale device ID, a bounded automatic-restart
  backoff, and capture recovery state on the status endpoint.
- `audio-device`: adds a requirement that each enumerated device reports whether it is currently
  available for capture.

## Impact

- **Code (`src/`, HK-011 — Developer session required):** `OpenWSFZ.Daemon/Program.cs` (restart
  paths), `OpenWSFZ.Abstractions` (`AudioDeviceInfo`, possibly a small resolver interface),
  `OpenWSFZ.Audio` (WASAPI provider reports endpoint state), `OpenWSFZ.Web` (`DaemonStatus`, the
  devices endpoint). No `native/`, decoder or shim change.
- **Config file:** the daemon may now **write** `config.json` on its own initiative, once per
  adopted re-resolution. It already writes it on shutdown and on operator saves.
- **API:** additive fields on `GET /api/v1/status`, the WebSocket `status` event and
  `GET /api/v1/audio/devices` (`available`).
- **Cross-platform:** the resolver works only through `IAudioDeviceProvider`. On macOS, `Id == Name`,
  so it is a no-op. On Linux, `hw:N,M` can also move across a replug, and name matching applies
  unchanged. Live verification is Windows only. This is stated, not hidden.
