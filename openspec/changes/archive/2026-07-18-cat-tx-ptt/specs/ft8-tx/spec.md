## ADDED Requirements

### Requirement: PTT method configuration

`OpenWSFZ.Abstractions` SHALL define a `PttConfig` record, referenced from `AppConfig` as a top-level `Ptt` field (sibling to `Cat`, not nested inside it), with the following fields and defaults:

```csharp
public string Method            { get; init; } = "AudioVox"; // AudioVox | CatCommand | SerialRtsDtr
public string SerialPort        { get; init; } = <platform default, same convention as CatConfig.SerialPort>;
public string SerialLine        { get; init; } = "Rts";       // Rts | Dtr
public int    LeadTimeMs        { get; init; } = 50;
public int    TailTimeMs        { get; init; } = 50;
public int    WatchdogTimeoutMs { get; init; } = 20000;
```

A missing or partial `ptt` key in the configuration file SHALL deserialise with all fields at their defaults. An unrecognised `Method` or `SerialLine` value SHALL be logged at Warning and treated as `"AudioVox"` / `"Rts"` respectively, rather than throwing.

The daemon SHALL register exactly one `IPttController` implementation in the DI container, selected at startup from `AppConfig.Ptt.Method`:
- `"AudioVox"` → `AudioOnlyPttController` (unchanged from the existing implementation)
- `"CatCommand"` → `CatPttController`
- `"SerialRtsDtr"` → `SerialRtsDtrPttController`

#### Scenario: Default configuration preserves existing VOX behaviour

- **WHEN** a configuration file has no `ptt` key at all
- **THEN** `AppConfig.Ptt.Method` SHALL be `"AudioVox"` and the daemon SHALL register `AudioOnlyPttController` exactly as it does today

#### Scenario: CatCommand method registers CatPttController

- **WHEN** `AppConfig.Ptt.Method` is `"CatCommand"` at daemon startup
- **THEN** the DI container SHALL register `CatPttController` as the singleton `IPttController`

#### Scenario: SerialRtsDtr method registers SerialRtsDtrPttController

- **WHEN** `AppConfig.Ptt.Method` is `"SerialRtsDtr"` at daemon startup
- **THEN** the DI container SHALL register `SerialRtsDtrPttController` as the singleton `IPttController`

#### Scenario: Unrecognised method falls back to AudioVox

- **WHEN** `AppConfig.Ptt.Method` is a value other than `"AudioVox"`, `"CatCommand"`, or `"SerialRtsDtr"`
- **THEN** the daemon SHALL log a Warning naming the invalid value and register `AudioOnlyPttController` as if `Method` were `"AudioVox"`

---

### Requirement: CatPttController keys PTT over the CAT link

`OpenWSFZ.Daemon` SHALL provide a class `CatPttController : IPttController` that asserts PTT via `ICatPttGate.SetPttAsync` (see `cat-control`) and plays the loaded TX audio via the same WASAPI playback mechanism as `AudioOnlyPttController`, sequenced as follows:

`KeyDownAsync`:
1. Call `ICatPttGate.SetPttAsync(true)`.
2. Wait `AppConfig.Ptt.LeadTimeMs`.
3. Begin WASAPI playback of the loaded audio buffer and await its completion (or cancellation).

`KeyUpAsync`:
1. Stop any in-progress playback and release the audio device.
2. Wait `AppConfig.Ptt.TailTimeMs`.
3. Call `ICatPttGate.SetPttAsync(false)`.

PTT SHALL be released (via `ICatPttGate.SetPttAsync(false)`) on any exception raised during steps 1–3 of `KeyDownAsync`, on cancellation, and on `DisposeAsync`, even if playback has not started or has not completed.

#### Scenario: KeyDownAsync asserts PTT before audio starts

- **WHEN** `LoadAudio` has been called with a valid buffer and `KeyDownAsync` is called
- **THEN** `ICatPttGate.SetPttAsync(true)` SHALL be called, and WASAPI playback SHALL NOT begin until at least `LeadTimeMs` has elapsed after that call returns

#### Scenario: KeyUpAsync releases PTT after audio and tail time

- **WHEN** `KeyUpAsync` is called while audio is playing
- **THEN** playback SHALL stop, at least `TailTimeMs` SHALL elapse, and only then SHALL `ICatPttGate.SetPttAsync(false)` be called

#### Scenario: PTT is released when playback throws

- **WHEN** WASAPI playback throws an exception after PTT has been asserted
- **THEN** `CatPttController` SHALL still call `ICatPttGate.SetPttAsync(false)` before the exception propagates to the caller

#### Scenario: KeyDownAsync without LoadAudio throws InvalidOperationException

- **WHEN** `KeyDownAsync` is called before `LoadAudio` has been called
- **THEN** the method SHALL throw `InvalidOperationException` without calling `ICatPttGate.SetPttAsync`

#### Scenario: DisposeAsync releases PTT if asserted

- **WHEN** `DisposeAsync` is called while PTT is asserted
- **THEN** `ICatPttGate.SetPttAsync(false)` SHALL be called before disposal completes

---

### Requirement: SerialRtsDtrPttController keys PTT via a serial control line

`OpenWSFZ.Daemon` SHALL provide a class `SerialRtsDtrPttController : IPttController` that asserts PTT by setting a serial port's RTS or DTR line (per `AppConfig.Ptt.SerialLine`) high, and plays the loaded TX audio via the same WASAPI playback mechanism as `AudioOnlyPttController`, sequenced identically to `CatPttController`'s `KeyDownAsync`/`KeyUpAsync` steps but asserting/de-asserting the configured serial line in place of `ICatPttGate.SetPttAsync`.

`SerialRtsDtrPttController` SHALL open its own serial port (`AppConfig.Ptt.SerialPort`) independently of any CAT connection; it SHALL NOT share a connection, port handle, or synchronisation gate with `CatPollingService` or `ICatPttGate`.

#### Scenario: KeyDownAsync asserts the configured line before audio starts

- **WHEN** `AppConfig.Ptt.SerialLine` is `"Rts"` and `KeyDownAsync` is called
- **THEN** the serial port's RTS line SHALL be set high, and WASAPI playback SHALL NOT begin until at least `LeadTimeMs` has elapsed after that call returns

#### Scenario: KeyUpAsync de-asserts the configured line after audio and tail time

- **WHEN** `KeyUpAsync` is called while audio is playing
- **THEN** playback SHALL stop, at least `TailTimeMs` SHALL elapse, and only then SHALL the configured serial line be set low

#### Scenario: DTR line is used when configured

- **WHEN** `AppConfig.Ptt.SerialLine` is `"Dtr"`
- **THEN** `KeyDownAsync`/`KeyUpAsync` SHALL assert/de-assert the DTR line instead of RTS

#### Scenario: Independent of the CAT connection

- **WHEN** `AppConfig.Cat.Enabled` is `false` and `AppConfig.Ptt.Method` is `"SerialRtsDtr"`
- **THEN** `SerialRtsDtrPttController` SHALL still be able to open its configured serial port and key PTT, independent of CAT being disabled

#### Scenario: Port open failure surfaces as an exception, not a silent no-op

- **WHEN** `AppConfig.Ptt.SerialPort` names a port that does not exist or is already in use
- **THEN** `KeyDownAsync` SHALL throw rather than silently proceeding to play audio with no PTT asserted

---

### Requirement: PTT failsafe watchdog

Any `IPttController` implementation that asserts a physical PTT signal (`CatPttController`, `SerialRtsDtrPttController`) SHALL start a watchdog timer, set to `AppConfig.Ptt.WatchdogTimeoutMs`, the instant PTT is asserted in `KeyDownAsync`. If `KeyUpAsync` has not completed the PTT-release step before the watchdog elapses, the implementation SHALL force PTT release immediately (bypassing `TailTimeMs`) and SHALL log at Error level. The watchdog SHALL be cancelled as soon as `KeyUpAsync` begins executing its release step.

This requirement does not apply to `AudioOnlyPttController`, which asserts no independent physical PTT signal (VOX keying is entirely the rig's own responsibility).

#### Scenario: Watchdog forces release when key-up never arrives

- **WHEN** PTT has been asserted for longer than `WatchdogTimeoutMs` without `KeyUpAsync` being called
- **THEN** the controller SHALL force PTT release and log an Error containing the elapsed hold duration

#### Scenario: Watchdog does not fire during normal operation

- **WHEN** `KeyUpAsync` completes its release step before `WatchdogTimeoutMs` has elapsed
- **THEN** the watchdog timer SHALL be cancelled and SHALL NOT force a second release

#### Scenario: Watchdog fires even if playback hangs

- **WHEN** WASAPI playback does not return control within `WatchdogTimeoutMs` of `KeyDownAsync` asserting PTT
- **THEN** PTT SHALL still be forcibly released by the watchdog, independent of whether playback ever completes
