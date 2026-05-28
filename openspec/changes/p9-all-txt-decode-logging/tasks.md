## 1. Requirements

- [x] 1.1 Add `FR-027` to `REQUIREMENTS.md`: *Dial frequency configuration — the operator SHALL be able to configure the radio dial frequency (in MHz) via a `decodeLog.dialFrequencyMHz` field (double, default `0.0`) in `AppConfig`. The value is used when writing the ALL.TXT decode log.*
- [x] 1.2 Add `FR-028` to `REQUIREMENTS.md`: *WSJT-X compatible ALL.TXT decode log — when `decodeLog.enabled` is `true`, the daemon SHALL append one line per decoded FT8 message to `decodeLog.path` (default `ALL.TXT`) after each decode cycle in WSJT-X format: `YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,5:F1} {freq,4} {message}`. File write failures SHALL be logged at Warning and SHALL NOT interrupt the decode pipeline.*
- [x] 1.3 Also formally add `FR-026` to `REQUIREMENTS.md` (was implemented in tests but never recorded): *FT8 decode throughput — the FT8 decoder SHALL complete each 15-second decode cycle within 13 seconds of wall-clock time. No more than 2 Goertzel candidates SHALL be evaluated per (time-position, base-frequency) sweep pair.*

## 2. Configuration model

- [x] 2.1 Create `src/OpenWSFZ.Abstractions/DecodeLogConfig.cs` — a `sealed record DecodeLogConfig` with `bool Enabled = false`, `string Path = "ALL.TXT"`, `double DialFrequencyMHz = 0.0`; follow the pattern of `LoggingConfig.cs`
- [x] 2.2 Add `DecodeLogConfig DecodeLog { get; init; } = new();` property to `AppConfig` in `src/OpenWSFZ.Abstractions/AppConfig.cs`
- [x] 2.3 Verify `dotnet build -c Release` is still green (0 errors, 0 warnings) after config changes

## 3. AllTxtWriter service

- [x] 3.1 Create `src/OpenWSFZ.Daemon/AllTxtWriter.cs` — a class `AllTxtWriter` with constructor `(IConfigStore configStore, ILogger<AllTxtWriter> logger)` and method `Task AppendAsync(DateTime cycleUtc, IReadOnlyList<DecodeResult> results)`
- [x] 3.2 Implement `AppendAsync`: if `decodeLog.enabled` is `false` or `results` is empty, return immediately; otherwise open `decodeLog.path` in append mode (create file and directories if absent), write one line per result using the format `$"{cycleUtc:yyMMdd}_{result.Time.Replace(":", "")}     {dialMhz:F3} Rx FT8 {result.Snr,6} {result.Dt,5:F1} {result.FreqHz,4} {result.Message}"`, close file; catch `IOException`/`UnauthorizedAccessException`, log Warning, return without throwing
- [x] 3.3 Register `AllTxtWriter` as a singleton in `Program.cs` DI container
- [x] 3.4 In `Program.cs` decode pump (line ~234), capture `DateTime.UtcNow` immediately before `DecodeAsync`, then call `await allTxtWriter.AppendAsync(cycleUtc, results)` after `decodeEventBus.Publish(results)`

## 4. Settings UI

- [x] 4.1 In the Settings page (`src/OpenWSFZ.Web/`), add a numeric input for `decodeLog.dialFrequencyMHz` (label: "Dial frequency (MHz)"; step 0.001; placeholder "e.g. 7.074")
- [x] 4.2 Add a checkbox for `decodeLog.enabled` (label: "Write ALL.TXT decode log")
- [x] 4.3 Add a text input for `decodeLog.path` (label: "ALL.TXT path"; placeholder "ALL.TXT"); shown only when `decodeLog.enabled` is checked
- [x] 4.4 Ensure the three new fields are included in the `POST /api/v1/config` payload sent on Save

## 5. Tests

- [x] 5.1 Add `AllTxtWriterTests.cs` to `tests/OpenWSFZ.Daemon.Tests/` (create the project if it does not already exist, following the pattern of `OpenWSFZ.Config.Tests`); use `[Trait("Category", "Unit")]`
- [x] 5.2 Add test `FR-028: line format matches WSJT-X ALL.TXT exactly` — create a mock `IConfigStore` returning `DecodeLogConfig { Enabled = true, Path = tmpFile, DialFrequencyMHz = 7.074 }`, call `AppendAsync` with `cycleUtc = 2026-05-28T17:29:30Z` and a single `DecodeResult { Time = "17:29:30", Snr = 3, Dt = 0.2, FreqHz = 2252, Message = "DL4DSA PD1BER JO22" }`, assert the written line is `"260528_172930     7.074 Rx FT8      3   0.2 2252 DL4DSA PD1BER JO22"` (3 spaces before "0.2")
- [x] 5.3 Add test `FR-028: nothing written when disabled` — `Enabled = false`; assert file is not created
- [x] 5.4 Add test `FR-028: nothing written when results empty` — `Enabled = true` but empty result list; assert file is not created
- [x] 5.5 Add test `FR-028: file write failure does not throw` — point `Path` to an invalid location (e.g. `"Z:\\nonexistent\\ALL.TXT"`); assert `AppendAsync` completes without throwing and logs a Warning

## 6. Verification

- [x] 6.1 `dotnet build -c Release` — 0 errors, 0 warnings
- [x] 6.2 `dotnet test -c Release` — all tests green, including new `AllTxtWriterTests`
      — Re-certified 2026-05-28: 190 passed, 0 failed, 0 skipped (4 new Daemon.Tests + 186 existing)
- [ ] 6.3 Run the daemon against a live or recorded FT8 session; confirm `ALL.TXT` is created and each line matches the expected column layout against a known WSJT-X `ALL.TXT` for the same signals
      ← REQUIRES CAPTAIN: live hardware smoke test

## 7. Defects — Round 34 (2026-05-28 smoke test)

### D16 — DT field width (5 chars → 4 chars)
- [x] D16.1 `AllTxtWriter.cs` line 75: `{result.Dt,5:F1}` → `{result.Dt,4:F1}`
- [x] D16.2 `AllTxtWriterTests.cs`: update FR-028 line-format expected string — 2 spaces before "0.2" (was 3)
- [x] D16.3 `specs/decode-log/spec.md`: update column alignment scenario and field-width description; remove "3 spaces" note
- [x] D16.4 `REQUIREMENTS.md`: fix FR-028 format string `{dt,5:F1}` → `{dt,4:F1}`; add CRLF note

### D17 — Line endings (LF → CRLF)
- [x] D17.1 `AllTxtWriter.cs` line 62: `NewLine = "\n"` → `NewLine = "\r\n"`
- [x] D17.2 `specs/decode-log/spec.md`: update line-termination clause to `\r\n`
- [x] D17.3 `REQUIREMENTS.md`: add CRLF clause to FR-028 (done as part of D16.4)

### D18 — Zero real FT8 decodes (diagnostic instrumentation only — no fix yet)
- [x] D18.1 `Ft8Decoder.cs`: add D18-1 PCM window statistics (count / min / max / rms) at Debug level
- [x] D18.2 `Ft8Decoder.cs`: add D18-2 Costas score at known 731 Hz / startSample ∈ [960, 1440] candidate
- [x] D18.3 `Ft8Decoder.cs`: add D18-3 LDPC initial parity failures at 731 Hz candidate
- [ ] D18.4 CAPTAIN: run one live decode cycle with Debug log level on `OpenWSFZ.Ft8` namespace; paste `[D18-1]`, `[D18-2]`, `[D18-3]` lines back to QA for root-cause determination
      ← REQUIRES CAPTAIN: live hardware run with debug logging
