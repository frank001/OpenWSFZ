**User-facing:** yes

## Why

v1.0 is defined (`REQUIREMENTS.md`, `IMPLEMENTATION_PLAN.md`) as the point where OpenWSFZ can make a confirmed two-way FT8 contact: RX + CAT control + TX. RX and CAT (frequency read/set) and TX (audio synthesis) all exist, but nothing in the software can actually key the transmitter — the only `IPttController` today (`AudioOnlyPttController`) plays TX audio out a sound device and relies entirely on the rig's own VOX to key up. `IRadioConnection` explicitly documents that no PTT command exists yet. Closing this gap is the last item standing between the current release and the v1.0 gate.

## What Changes

- Extend `IRadioConnection` with a `SetPttAsync(bool transmitting, CancellationToken)` member (amending the existing "no PTT" restriction, same pattern as the earlier `SetDialFrequencyMhzAsync` amendment). `SerialCatConnection` implements it with the Kenwood/Yaesu-family `TX;`/`RX;` commands (same dialect as its existing `FA;` frequency commands); `RigctldConnection` implements it with `\set_ptt 1\n` / `\set_ptt 0\n`, consuming the `RPRT` acknowledgement the same way `SetDialFrequencyMhzAsync` already does.
- Introduce a serialization mechanism inside `CatPollingService` so frequency polling and CAT PTT commands can never interleave bytes on the same serial port / TCP socket — the single highest-risk part of this change.
- Add two new `IPttController` implementations alongside the existing `AudioOnlyPttController` (which is kept, unmodified in behaviour, as the default): a CAT-command controller that sequences `SetPttAsync` around the existing WASAPI TX-audio playback, and a serial RTS/DTR line-toggle controller that keys PTT via a raw control line independent of any CAT link. The WASAPI playback logic currently embedded in `AudioOnlyPttController` is extracted into a shared internal helper so it is not duplicated.
- Add an operator-selectable PTT method to configuration (`AudioVox` | `CatCommand` | `SerialRtsDtr`), defaulting to `AudioVox` so existing configurations are unaffected. `SerialRtsDtr` gets its own independent serial port + line (RTS or DTR) configuration, since in practice that wiring is frequently on a different port than the CAT link.
- Add a hard watchdog ceiling and guaranteed-release semantics (exception paths, `DisposeAsync`, daemon shutdown) so a stuck key-down can never leave the rig transmitting.
- Extend `ISerialPort` / `SerialPortWrapper` with RTS/DTR line control (currently absent) to support the new controller and its unit tests.
- Add a `FR-0##` requirement (and `REQUIREMENTS.md` version-history row) documenting the new capability, following the FR-045 amendment style.
- Ship a hardware-acceptance.md manual test plan (no CI substitute exists for keying a real radio) covering both new PTT mechanisms, the failsafe watchdog, and a genuine confirmed two-way QSO, tying into `IMPLEMENTATION_PLAN.md` release gate R3.

No new UI is introduced by this change — the existing CAT status badge (already driven by `ICatState.Status`) is sufficient; per FR-016 no speculative "PTT active" indicator is added without one being explicitly requested.

## Capabilities

### New Capabilities

_(none — this change extends two existing capabilities rather than introducing a new one)_

### Modified Capabilities

- `cat-control`: `IRadioConnection` gains `SetPttAsync`; `SerialCatConnection` and `RigctldConnection` implement it; `CatPollingService` gains a serialization mechanism guaranteeing polling and PTT commands never interleave on the wire.
- `ft8-tx`: the `IPttController` abstraction gains two new implementations (CAT-command and serial RTS/DTR), a shared WASAPI-playback helper, a configurable PTT method selector, lead/tail timing, and a failsafe watchdog. `AudioOnlyPttController`'s existing behaviour and requirements are unchanged.

## Impact

- **Code**: `OpenWSFZ.Abstractions` (`IRadioConnection`, `CatConfig` or a new `PttConfig`), `OpenWSFZ.Rig` (`SerialCatConnection`, `RigctldConnection`, `ISerialPort`, `SerialPortWrapper`), `OpenWSFZ.Daemon` (`CatPollingService`, `AudioOnlyPttController` refactor, two new `IPttController` implementations, `Program.cs` DI wiring).
- **Config**: additive fields only; existing `openswfz.json` files continue to work unchanged (default PTT method preserves today's VOX-only behaviour).
- **Hardware**: requires a CAT-capable rig and/or a serial interface with RTS/DTR wired to PTT to validate; a manual hardware-acceptance gate is added, matching the precedent set by `p16-cat-control`.
- **Requirements**: one new FR added to `REQUIREMENTS.md`.
- **Safety**: this is the first change in the project that can key a real transmitter under software control — failsafe/watchdog behaviour is treated as a hard requirement, not a nice-to-have.
