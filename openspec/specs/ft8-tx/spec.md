# ft8-tx Specification

## Purpose

Specifies the FT8 transmit pipeline: message encoding via the native shim, GFSK audio
synthesis from the resulting tone sequence, the PTT abstraction and its `AudioVox`/
`CatCommand`/`SerialRtsDtr` keying implementations with a shared failsafe watchdog, and the
TX control REST API.

## Requirements

### Requirement: FT8 message encoding via native shim

The `Ft8LibInterop` class SHALL expose a managed method `EncodeMessage(string message, byte[] tonesOut)` that calls a new native entry point `ft8_encode_message` via P/Invoke. The method SHALL write exactly 79 tone indices (each in the range 0–7) into `tonesOut`. The native entry point SHALL be added to `ft8_shim.c` using `libft8`'s existing pack and encode functions. `FT8_SHIM_VERSION` SHALL be bumped to `20260017`.

The managed constant `EncodedToneCount` SHALL be `79`.

#### Scenario: Valid standard message encodes to 79 tones

- **WHEN** `EncodeMessage("Q1OFZ Q1TST JO33", tones)` is called with a 79-element buffer
- **THEN** the method SHALL return without throwing, `tones` SHALL contain exactly 79 values each in range 0–7, and the encoded symbols SHALL be decodable by `ft8_decode_all` when synthesised into audio

#### Scenario: tonesOut too small throws ArgumentException

- **WHEN** `EncodeMessage` is called with a buffer shorter than 79 elements
- **THEN** the method SHALL throw `ArgumentException` before calling the native function

#### Scenario: Unpackable message throws InvalidOperationException

- **WHEN** `EncodeMessage` is called with a message string that the native packer rejects (e.g. exceeds 35 characters or contains invalid characters)
- **THEN** the method SHALL throw `InvalidOperationException` with the message text and native error code

#### Scenario: Version check fails for shim older than 20260017

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at a version prior to `20260017`
- **THEN** the ABI self-test SHALL throw `InvalidOperationException` naming the version mismatch before any encode or decode call is attempted

---

### Requirement: GFSK audio synthesis from tone sequence

A new class `Ft8AudioSynthesiser` in `OpenWSFZ.Ft8` SHALL accept 79 tone indices and a base audio frequency (Hz), and produce a `float[]` buffer of mono PCM samples at 48 000 Hz representing the GFSK-modulated FT8 transmission.

Parameters (fixed by FT8 specification):
- Symbol rate: 6.25 baud (160 ms per symbol)
- Tone spacing: 6.25 Hz
- Total duration: 79 × 160 ms = 12 640 ms → 79 × 7680 = 607 680 samples at 48 000 Hz
- Frequency of tone index `t`: `baseFrequencyHz + t × 6.25 Hz`
- Phase continuity: instantaneous phase is accumulated across symbol boundaries (continuous-phase FM)
- Amplitude: normalised to 0.5 peak (–6 dBFS) to provide headroom

The synthesiser SHALL produce a rectangular frequency pulse (no Gaussian shaping) for v1. The output SHALL be interoperable with WSJT-X's FT8 decoder (verified via loopback test).

#### Scenario: Output length is correct

- **WHEN** `Synthesise(tones, baseFrequencyHz: 897.0)` is called with a valid 79-element tone array
- **THEN** the returned `float[]` SHALL have length exactly 607 680

#### Scenario: Output is within amplitude bounds

- **WHEN** `Synthesise` is called with any valid tone array
- **THEN** every sample in the output SHALL be in the range [−0.5, 0.5]

#### Scenario: Phase is continuous across symbol boundaries

- **WHEN** two adjacent symbols have different tone indices
- **THEN** the synthesised waveform SHALL have no discontinuity in instantaneous phase at the boundary (the final phase of symbol N becomes the initial phase of symbol N+1)

#### Scenario: WSJT-X decodes loopback transmission

- **WHEN** audio synthesised from `EncodeMessage("Q1OFZ Q1TST JO33", ...)` at base frequency 897 Hz is played through VoiceMeeter and received by WSJT-X
- **THEN** WSJT-X SHALL decode the message as `Q1OFZ Q1TST JO33` with DT within ±0.5 s of the cycle boundary

---

### Requirement: PTT abstraction

A new interface `IPttController` SHALL be defined in `OpenWSFZ.Abstractions`:

```
KeyDownAsync(CancellationToken) → Task   // begin transmission
KeyUpAsync(CancellationToken)   → Task   // end transmission
```

The interface SHALL extend `IAsyncDisposable`. Implementations SHALL be registered in the DI container as singletons.

A v1 implementation `AudioOnlyPttController` in `OpenWSFZ.Daemon` SHALL implement `IPttController` using `NAudio.Wasapi.WasapiOut`. `KeyDownAsync` SHALL open the configured audio output device, initialise it with the pre-loaded TX audio buffer, and begin playback. `KeyUpAsync` SHALL stop playback, drain the device, and release it. The audio buffer SHALL be set via a separate `LoadAudio(float[] samples)` method before `KeyDownAsync` is called.

#### Scenario: KeyDownAsync starts audio playback on the configured output device

- **WHEN** `LoadAudio` has been called with a valid sample buffer and `KeyDownAsync` is called
- **THEN** the configured WASAPI output device SHALL begin playing the audio within 200 ms

#### Scenario: KeyUpAsync stops playback and releases the device

- **WHEN** `KeyUpAsync` is called while audio is playing
- **THEN** playback SHALL stop within 100 ms and the WASAPI device handle SHALL be released

#### Scenario: KeyDownAsync without LoadAudio throws InvalidOperationException

- **WHEN** `KeyDownAsync` is called before `LoadAudio` has been called
- **THEN** the method SHALL throw `InvalidOperationException` without attempting to open the audio device

#### Scenario: DisposeAsync releases all resources

- **WHEN** `DisposeAsync` is called (including on abnormal exit)
- **THEN** any open WASAPI device handle SHALL be released and no further audio SHALL play

---

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

---

### Requirement: TX control REST API

The daemon SHALL expose the following endpoints:

- `POST /api/v1/tx/abort` — immediately abort any active QSO and return to IDLE. Returns HTTP 200 with current TX status.
- `GET /api/v1/tx/status` — return the current TX state machine phase and active QSO partner (if any).

#### Scenario: GET /api/v1/tx/status returns Idle when no QSO active

- **WHEN** a client sends `GET /api/v1/tx/status` and no QSO is in progress
- **THEN** the server SHALL respond HTTP 200 with `{ "state": "Idle", "partner": null }`

#### Scenario: GET /api/v1/tx/status returns active state during QSO

- **WHEN** a QSO is in progress in state `WaitReport` with partner `Q1TST`
- **THEN** `GET /api/v1/tx/status` SHALL return `{ "state": "WaitReport", "partner": "Q1TST" }`

#### Scenario: POST /api/v1/tx/abort while idle returns 200

- **WHEN** `POST /api/v1/tx/abort` is called while the state machine is in Idle
- **THEN** the server SHALL respond HTTP 200 and the state SHALL remain Idle

#### Scenario: POST /api/v1/tx/abort during active QSO aborts and returns 200

- **WHEN** `POST /api/v1/tx/abort` is called during an active QSO
- **THEN** the state machine SHALL abort to Idle, PTT SHALL be released, and the server SHALL respond HTTP 200
