## ADDED Requirements

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

#### Scenario: Version check fails for shim 20260016 with encode absent

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260016`
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

### Requirement: TX control REST API

The daemon SHALL expose the following endpoints:

- `POST /api/v1/tx/abort` — immediately abort any active QSO and return to IDLE. Returns HTTP 200 with current TX status.
- `GET /api/v1/tx/status` — return the current TX state machine phase and active QSO partner (if any).

#### Scenario: GET /api/v1/tx/status returns IDLE when no QSO active

- **WHEN** a client sends `GET /api/v1/tx/status` and no QSO is in progress
- **THEN** the server SHALL respond HTTP 200 with `{ "state": "Idle", "partner": null }`

#### Scenario: GET /api/v1/tx/status returns active state during QSO

- **WHEN** a QSO is in progress in state `WaitReport` with partner `Q1TST`
- **THEN** `GET /api/v1/tx/status` SHALL return `{ "state": "WaitReport", "partner": "Q1TST" }`

#### Scenario: POST /api/v1/tx/abort while idle returns 200

- **WHEN** `POST /api/v1/tx/abort` is called while the state machine is in IDLE
- **THEN** the server SHALL respond HTTP 200 and the state SHALL remain IDLE

#### Scenario: POST /api/v1/tx/abort during active QSO aborts and returns 200

- **WHEN** `POST /api/v1/tx/abort` is called during an active QSO
- **THEN** the state machine SHALL abort to IDLE, PTT SHALL be released, and the server SHALL respond HTTP 200
