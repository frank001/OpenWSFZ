## Context

OpenWSFZ currently decodes FT8 signals via a P/Invoke binding to `libft8.dll`. The shim (`ft8_shim.c`) exports only decode entry points — `ft8_decode_all`, `ft8_get_last_pass_counts`, `ft8_get_last_noise_floor_db`. No encode capability exists anywhere in the managed codebase.

The project already has:
- `AudioOutputDeviceId` in `AppConfig` and `IAudioOutputDeviceProvider` (added in p20)
- `NAudio.Wasapi` (assumed transitive dependency for existing capture; WASAPI playback uses the same library)
- A cycle framer that knows FT8 cycle boundaries
- An internal decode event pipeline feeding the WebSocket event bus

Test fixture: VoiceMeeter software audio loopback. No radio hardware. PTT = audio output on/off.

## Goals / Non-Goals

**Goals:**
- Add `ft8_encode_message` to the native shim (bump version to `20260017`)
- Synthesise GFSK audio from encoded symbols in managed C#
- Play TX audio through the configured output device via WasapiOut
- Drive a 6-message QSO answerer state machine from the existing decode event pipeline
- Write an ADIF record for each completed QSO
- Abstract PTT behind `IPttController` so that serial/CAT keying can be added later
- Add `tx` section to `AppConfig` (callsign, grid, retry count, watchdog, ADIF path)

**Non-Goals:**
- Caller role (originating CQ) — deferred
- Manual CQ selection — deferred (TX-D01)
- Configurable TX frequency offset — deferred (TX-D02)
- Real callsign/grid in settings UI — deferred (TX-D03)
- SNR-derived signal reports — deferred (TX-D04)
- Serial/CAT/VOX PTT — deferred
- General Settings page — deferred (TX-D07)
- Precise cycle-boundary TX start (< 50 ms) — deferred; v1 accepts ~100–200 ms late start

## Decisions

### D1 — Encode via native shim, synthesise audio in C#

**Options considered:**
- A: Add `ft8_encode_message` to the shim; C# synthesises GFSK audio
- B: Implement full encode path in C# (message packing → LDPC → symbols → audio)
- C: Shell out to the Python R&R synthesiser

**Chosen: A.** Message packing (text → 77 bits) involves CRC, hash tables for compressed callsigns, and LDPC — the same code that WSJT-X uses. Bugs here cause undecodable transmissions. Re-using the native library's pack/encode path is the safe choice. Audio synthesis (symbols → float samples) is simple trigonometry with no protocol risk and is straightforward to unit-test in C#. Option C is rejected — subprocess overhead and Python dependency are unacceptable for production.

**Shim addition:**
```c
int ft8_encode_message(const char* message, uint8_t* tones_out, int tones_capacity);
```
Returns number of tones written (79 on success), or negative error code. `tones_out` receives tone indices 0–7 for each of the 79 FT8 symbols. `tones_capacity` must be ≥ 79. Version bumps to `20260017`.

### D2 — GFSK audio synthesis at 48 000 Hz in C#

FT8 uses 8-tone continuous-phase GFSK. Parameters (fixed by the FT8 specification):
- Symbol rate: 6.25 baud (160 ms/symbol)
- Tone spacing: 6.25 Hz
- GFSK bandwidth-time product: BT = 2.0
- Total symbols: 79 → total duration 79 × 160 ms = 12 640 ms
- Output sample rate: 48 000 Hz (matches WASAPI default observed in test logs)

The Gaussian frequency filter for GFSK with BT = 2.0 is very wide — at BT = 2.0 the impulse response is narrow enough that adjacent-symbol blurring is minimal; many implementations use a rectangular (non-Gaussian) frequency pulse for FT8. The Python synthesiser in `qa/rr-study/synth/` uses a Gaussian; v1 may use a rectangular pulse for simplicity (correctness verified against WSJT-X in the loopback test).

Output: `float[]` at 48 000 Hz mono, normalised to ±0.5 peak to leave headroom. Stereo conversion (L=R=mono value) if the WASAPI device requires stereo.

### D3 — State machine runs on the decode event pipeline thread

**Options considered:**
- A: `QsoAnswererService` subscribes to a `Channel<DecodeResult>` fed by the decode pipeline
- B: `QsoAnswererService` is called directly from `CycleFramer`/`Ft8Decoder` via injected callback
- C: `QsoAnswererService` polls a shared decode result store

**Chosen: A.** A `Channel<DecodeResult, IReadOnlyList<DecodeResult>>` (per-cycle) allows the answerer to consume cycle results asynchronously without blocking the decode thread. The decode pipeline already publishes results to the WebSocket event bus via a similar mechanism. The answerer is another consumer of the same cycle output.

The state machine processes one cycle batch at a time. TX is triggered by posting to a `TaskCompletionSource` or `Channel<TxRequest>` consumed by a dedicated TX task.

### D4 — TX timing: start-as-soon-as-ready (v1)

Decode results arrive ~100–200 ms into the next cycle boundary (40 ms decode time + CycleFramer emit latency). TX audio starts immediately on decode completion. This results in DT ≈ +0.1 to +0.2 s as seen by the counterparty. FT8 decoders tolerate DT up to approximately ±2.0 s. This is acceptable for v1.

Future improvement (not in this change): pre-generate audio for the likely next message before the cycle ends and start it at the precise boundary.

### D5 — PTT abstraction: IPttController in OpenWSFZ.Abstractions

```csharp
public interface IPttController : IAsyncDisposable
{
    Task KeyDownAsync(CancellationToken ct);
    Task KeyUpAsync(CancellationToken ct);
}
```

`AudioOnlyPttController` (v1 implementation): `KeyDownAsync` starts the WasapiOut player; `KeyUpAsync` stops it and releases the device. The TX audio buffer is supplied before `KeyDownAsync` is called.

Future implementations (`SerialPttController`, `CatPttController`) will be registered via DI without changing the state machine.

### D6 — ADIF log: append-on-completion, same directory as ALL.TXT

ADIF records are appended to `ADIF.log` in the same directory as `decodeLog.path` (resolved at startup). The file is opened in append mode, one record written, then closed — matching the ALL.TXT write pattern. If the QSO is incomplete (watchdog abort), no record is written.

ADIF 3.x format. Mandatory fields per completed QSO: `CALL`, `GRIDSQUARE`, `MODE` (`FT8`), `BAND` (derived from `decodeLog.dialFrequencyMHz`), `FREQ` (MHz), `RST_SENT` (`+00`), `RST_RCVD` (from decoded report), `QSO_DATE`, `TIME_ON`, `TIME_OFF`, `OPERATOR` (`tx.callsign`), `MY_GRIDSQUARE` (`tx.grid`).

The record is written when TX_73 completes (we have transmitted 73; QSO is considered complete from our perspective even if we never hear their acknowledgement).

### D7 — Watchdog: existing config field; hard-coded 4-minute default

The TX watchdog timer starts when the answerer leaves IDLE. If the watchdog fires before `QSO_COMPLETE`, the state machine aborts to IDLE. No ADIF record is written. The timer resets on every successful state transition.

`tx.watchdogMinutes` defaults to 4 (matching WSJT-X). Making it configurable via UI requires the General Settings page (TX-D07).

## Risks / Trade-offs

**[Risk] Shim version bump breaks existing installations** → Mitigation: ABI self-test (existing mechanism) detects the mismatch immediately on startup with a clear error message. No silent failure.

**[Risk] TX audio late start (DT +0.1–0.2 s) causes decode failure** → Mitigation: FT8 tolerance is ±2 s; loopback test will validate. If WSJT-X reports DT ≈ 0.1 s consistently, this is within normal operating parameters.

**[Risk] WasapiOut and WasapiCapture on the same device simultaneously** → In the loopback test, capture and playback are on different VoiceMeeter virtual devices, so no conflict. On a real radio with a single audio interface, RX/TX would use separate device instances (capture on input, playback on output) — the WASAPI API supports this.

**[Risk] State machine processes a CQ for a QSO already in progress** → The answerer ignores new CQs while not in IDLE state. Implemented as a guard at the top of the cycle handler.

**[Risk] Auto-answer starts transmitting before operator is aware** → This is expected behaviour for v1 and is the point of the loopback test. A UI indicator of TX state is required so the operator can abort.

## Migration Plan

1. Bump shim to 20260017 and rebuild `libft8.dll` (existing CI build step).
2. Update managed `FT8_SHIM_VERSION` constant in `Ft8LibInterop.cs`.
3. Add `TxConfig` to `OpenWSFZ.Abstractions`; extend `AppConfig` with `Tx` property.
4. Existing config files without a `tx` key load with defaults — no migration needed.
5. New ADIF.log is created on first QSO completion; no pre-existing file to migrate.

## Open Questions

- **Q1:** Should the UI show a TX state indicator (e.g., current QSO partner, state machine phase) or is a log entry sufficient for v1? *(Recommend: minimal — log only for v1; UI widget deferred to TX-D01 epic)*
- **Q2:** Which ADIF `BAND` value should be written when `dialFrequencyMHz` is 0.0 (decode log not configured)? *(Recommend: omit `BAND` field rather than write a misleading value)*
- **Q3:** Should `QsoAnswererService` be a hosted service (`IHostedService`) or a scoped component wired into the decode pipeline? *(Recommend: hosted service with its own `Channel` subscription — simpler lifetime management)*
