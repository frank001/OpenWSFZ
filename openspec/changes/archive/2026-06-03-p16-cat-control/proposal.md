## Why

OpenWSFZ currently requires the operator to manually configure the dial frequency (`decodeLog.dialFrequencyMHz`) so that ALL.TXT decode logs and the UI status bar show the correct value. This is error-prone and breaks silently — a mismatch between the actual rig frequency and the configured value produces misleading log entries. Connecting to the rig via CAT (Computer-Aided Transceiver) eliminates the manual step and keeps the displayed frequency truthful in real time. CAT control is also a required architectural prerequisite for TX and PTT, which are on the v1.0 roadmap.

## What Changes

- **New `IRadioConnection` abstraction** in `OpenWSFZ.Abstractions` — `ConnectAsync`, `DisconnectAsync`, `GetDialFrequencyMhzAsync`, `IsConnected`; keeps the polling layer rig-agnostic for future protocol support.
- **New `OpenWSFZ.Rig` project** — houses two `IRadioConnection` implementations: `SerialCatConnection` (direct serial, `FA;` command) and `RigctldConnection` (TCP client to a running `rigctld` daemon on localhost:4532). The operator selects via `cat.rigModel`.
- **New `CatPollingService`** in `OpenWSFZ.Daemon` — `IHostedService` that polls the rig at the configured interval and updates `decodeLog.dialFrequencyMHz` in memory.
- **New `cat` config section** in `AppConfig` — `{ enabled, rigModel, serialPort, baudRate, pollIntervalSeconds }`; defaults to disabled so existing installs are unaffected.
- **Settings page CAT section** — enable toggle, port, baud rate, and poll interval fields; CAT status indicator (connected / disconnected / disabled) in the status bar.
- **Only read-only CAT commands** are sent in this change (`FA;` — VFO-A frequency query). No frequency-set, mode-set, or PTT commands. The radio cannot be disturbed.

## Capabilities

### New Capabilities
- `cat-control`: Rig frequency polling via two selectable transports — `SerialCatConnection` (direct serial) and `RigctldConnection` (TCP to `rigctld`); `IRadioConnection` abstraction; `CatPollingService`; CAT configuration schema; UI status indicator.

### Modified Capabilities
- `configuration`: `AppConfig` gains a `cat` object (`enabled`, `rigModel`, `serialPort`, `baudRate`, `pollIntervalSeconds`). Default config and Settings REST API updated accordingly.

## Impact

- **New project:** `src/OpenWSFZ.Rig/` — new csproj, references `OpenWSFZ.Abstractions`; referenced by `OpenWSFZ.Daemon`.
- **New test project:** `tests/OpenWSFZ.Rig.Tests/` — unit tests for `SerialCatConnection`, `RigctldConnection`, and `CatPollingService` using mocked `IRadioConnection`.
- **`OpenWSFZ.Abstractions`:** gains `IRadioConnection` interface.
- **`OpenWSFZ.Daemon`:** gains `CatPollingService` hosted service; DI wiring for `IRadioConnection`; `AppConfig.Cat` property.
- **`AppConfig` schema:** non-breaking addition of optional `cat` object; round-trip fidelity preserved.
- **Settings REST API (`GET`/`POST /api/v1/config`):** `cat` object included in responses.
- **Web frontend:** Settings page gains CAT section; status bar shows dial frequency and CAT indicator.
- **Solution (`OpenWSFZ.slnx`):** new `OpenWSFZ.Rig` and `OpenWSFZ.Rig.Tests` projects added.
- **Dependencies:** `System.IO.Ports` NuGet package added to `OpenWSFZ.Rig` (cross-platform serial support).
- **No Hamlib dependency** — clean-room serial CAT protocol implementation.
- **Reference hardware for acceptance testing:** a CAT-capable rig on COM6 (Windows), 9600 baud; a second COM port reserved for PTT (out of scope this change).
