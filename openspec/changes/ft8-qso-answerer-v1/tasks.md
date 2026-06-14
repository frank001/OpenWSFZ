## 1. Native Shim — Encode Entry Point

- [x] 1.1 Add `ft8_encode_message(const char* message, uint8_t* tones_out, int tones_capacity)` to `ft8_shim.c` using libft8's pack and encode functions
- [x] 1.2 Declare `ft8_encode_message` in `ft8_shim.h`
- [x] 1.3 Bump `FT8_SHIM_VERSION` to `20260017` in `ft8_shim.h`
- [x] 1.4 Rebuild `libft8.dll` (and Linux/macOS equivalents) and update binaries in the repository

## 2. Managed Interop — Encode Binding

- [x] 2.1 Update `FT8_SHIM_VERSION` constant in `Ft8LibInterop.cs` to `20260017`
- [x] 2.2 Add P/Invoke declaration for `ft8_encode_message` in `Ft8LibInterop.cs`
- [x] 2.3 Implement `EncodeMessage(string message, byte[] tonesOut)` managed wrapper with argument validation (tonesOut.Length ≥ 79; negative return code → `InvalidOperationException`)
- [x] 2.4 Add `EncodedToneCount = 79` constant to `Ft8LibInterop`
- [x] 2.5 Add unit tests: valid message encodes to 79 tones; short buffer throws; unpackable message throws

## 3. GFSK Audio Synthesiser

- [x] 3.1 Create `Ft8AudioSynthesiser` class in `OpenWSFZ.Ft8`
- [x] 3.2 Implement `Synthesise(byte[] tones, double baseFrequencyHz) → float[]` using continuous-phase rectangular-pulse FM at 48 000 Hz
- [x] 3.3 Verify output length is exactly 607 680 samples (79 × 7680)
- [x] 3.4 Verify amplitude bound ±0.5 and phase continuity across symbol boundaries
- [x] 3.5 Add unit tests: output length, amplitude bounds, phase continuity at symbol boundary

## 4. PTT Abstraction

- [x] 4.1 Add `IPttController` interface to `OpenWSFZ.Abstractions` (`KeyDownAsync`, `KeyUpAsync`, `IAsyncDisposable`)
- [x] 4.2 Implement `AudioOnlyPttController` in `OpenWSFZ.Daemon` using `NAudio.Wasapi.WasapiOut`
- [x] 4.3 Implement `LoadAudio(float[] samples)` on `AudioOnlyPttController`; throw `InvalidOperationException` from `KeyDownAsync` if not called first
- [x] 4.4 Ensure `DisposeAsync` releases the WASAPI device handle in all exit paths (normal, exception, abort)
- [x] 4.5 Register `IPttController` → `AudioOnlyPttController` as singleton in DI
- [x] 4.6 Add unit tests for `AudioOnlyPttController` using a mock WasapiOut or testable seam

## 5. TX Configuration

- [x] 5.1 Create `TxConfig` record in `OpenWSFZ.Abstractions` with fields: `Callsign` (`"Q1OFZ"`), `Grid` (`"JO33"`), `RetryCount` (`3`), `WatchdogMinutes` (`4`)
- [x] 5.2 Add `TxConfig? Tx { get; init; } = null` property to `AppConfig` (null treated as default `TxConfig()`)
- [x] 5.3 Add `TxConfig` to the JSON serialisation context (`ConfigJsonContext`)
- [x] 5.4 Add clamping logic for `RetryCount < 1` and `WatchdogMinutes < 1` at config load with Warning log
- [x] 5.5 Update default config creation to include `tx` object with all default values
- [x] 5.6 Add unit tests: missing `tx` key uses defaults; values clamp correctly; round-trip serialisation

## 6. QSO Answerer State Machine

- [x] 6.1 Create `QsoAnswererService` class in `OpenWSFZ.Daemon` implementing `IHostedService`
- [x] 6.2 Define `QsoState` enum: `Idle`, `TxAnswer`, `WaitReport`, `TxReport`, `WaitRr73`, `Tx73`, `QsoComplete`
- [x] 6.3 Subscribe to decode pipeline output via `Channel<IReadOnlyList<DecodeResult>>` (wire into existing decode event publication point)
- [x] 6.4 Implement CQ detection in `Idle`: match pattern `CQ <callsign> <grid>`, select first result
- [x] 6.5 Implement `TxAnswer` → `WaitReport` transition: encode + synthesise + `KeyDownAsync`, await playback, advance state
- [x] 6.6 Implement `WaitReport` handler: match `<ours> <partner> <report>`; on match → `TxReport`; on partner-works-other → abort; on no-match → retry or abort
- [x] 6.7 Implement `TxReport` → `WaitRr73` transition: encode `<partner> <ours> R+00`, synthesise, transmit
- [x] 6.8 Implement `WaitRr73` handler: match RR73 or RRR addressed to us; on match → `Tx73`; on no-match → retry or abort
- [x] 6.9 Implement `Tx73` → `QsoComplete`: encode `<partner> <ours> 73`, transmit, signal completion
- [x] 6.10 Implement watchdog timer: start on leaving `Idle`; reset on each state transition; abort on expiry
- [x] 6.11 Implement retry counter: increment per no-response cycle; reset on state advance; abort at `tx.retryCount`
- [x] 6.12 Implement `POST /api/v1/tx/abort` handler: set cancellation flag, call `KeyUpAsync`, abort to `Idle`
- [x] 6.13 Implement `GET /api/v1/tx/status` endpoint returning current state and partner
- [x] 6.14 Push `txState` WebSocket events on every state transition
- [x] 6.15 Add unit tests for all state transitions using mock `IPttController` and injected decode batches

## 7. ADIF Log Writer

- [x] 7.1 Create `AdifLogWriter` class in `OpenWSFZ.Daemon`
- [x] 7.2 Implement path resolution: resolve directory from `decodeLog.path`; append `ADIF.log`
- [x] 7.3 Implement `AppendQsoAsync(QsoRecord record)`: open append, write ADIF fields in tagged format `<FIELD:len>value`, write `<EOR>\r\n`, close
- [x] 7.4 Implement `QsoRecord` value type capturing: partner callsign, partner grid, RST sent/received, QSO start/end UTC, operator callsign and grid, dial frequency
- [x] 7.5 Implement BAND derivation from `dialFrequencyMHz` (ITU band names); omit BAND and FREQ when frequency is 0.0
- [x] 7.6 Wire `AdifLogWriter` into `QsoAnswererService`: call `AppendQsoAsync` on `QsoComplete`
- [x] 7.7 Handle write failure gracefully: log Warning, do not throw, do not change QSO state
- [x] 7.8 Add unit tests: correct ADIF field format, EOR terminator, BAND derivation, FREQ omission when 0.0, no write on abort

## 8. Integration & Validation

- [ ] 8.1 Build solution; confirm 0 errors, 0 warnings
- [ ] 8.2 Run full test suite; confirm all existing 341 tests pass plus new tests green
- [ ] 8.3 Run loopback validation: WSJT-X sends CQ via VoiceMeeter → OpenWSFZ auto-answers → full 6-message exchange completes → ADIF.log entry written → WSJT-X logs the contact
- [ ] 8.4 Verify WSJT-X reports DT within ±0.5 s for OpenWSFZ transmissions
- [ ] 8.5 Verify operator abort (`POST /api/v1/tx/abort`) stops TX mid-QSO and returns to Idle
- [ ] 8.6 Verify watchdog abort: configure `tx.watchdogMinutes = 1`, allow WSJT-X to go silent mid-QSO; confirm abort logged and no ADIF entry written
- [ ] 8.7 Update G3 traceability gate to include new spec IDs
