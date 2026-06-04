## 1. Core implementation — SerialCatConnection

- [x] 1.1 Add `private volatile int _freqWidth = 0;` field and `private const int DefaultFreqWidth = 11;` constant to `SerialCatConnection`
- [x] 1.2 In `GetDialFrequencyMhzAsync`, after the successful parse, add `if (_freqWidth == 0) _freqWidth = digitCount;` to record the rig's native digit width on the first successful response
- [x] 1.3 In `SetDialFrequencyMhzAsync`, replace the hardcoded `D11` format with `var width = _freqWidth > 0 ? _freqWidth : DefaultFreqWidth;` and use `hz.ToString().PadLeft(width, '0')` to build the command
- [x] 1.4 Add an optional `ILogger? logger = null` parameter to the internal `SerialCatConnection(ISerialPort, ...)` constructor; add `LogDebug` calls that log the exact string written in `SetDialFrequencyMhzAsync` and the raw string returned in `GetDialFrequencyMhzAsync`
- [x] 1.5 Update `RigModelFactory.Create` to accept an optional `ILoggerFactory? loggerFactory = null` and pass `loggerFactory?.CreateLogger<SerialCatConnection>()` to the `SerialCatConnection` public constructor
- [x] 1.6 Add `ILoggerFactory` to `CatPollingService`'s constructor parameters; pass it to `RigModelFactory.Create` inside `CreateConnection` so serial I/O debug messages flow to the log file at Trace level

## 2. Unit tests — SerialCatConnectionTests

- [x] 2.1 Add test: calling `SetDialFrequencyMhzAsync` **before** any `GetDialFrequencyMhzAsync` writes an 11-digit FA command (verifies the `DefaultFreqWidth` fallback is applied)
- [x] 2.2 Add test: after a **9-digit** GET response (`FA007074000;`), calling `SetDialFrequencyMhzAsync(7.074)` writes `FA007074000;` — verifying calibration for a 9-digit rig
- [x] 2.3 Add test: after an **11-digit** GET response (`FA00014074000;`), calling `SetDialFrequencyMhzAsync(14.074)` writes `FA00014074000;` — verifying calibration for an 11-digit rig
- [x] 2.4 Add test: digit width discovered from a 9-digit response is stable across subsequent GETs — a second GET with the same response does not reset or change the stored width

## 3. Spec maintenance

- [x] 3.1 Confirm the existing `SetDialFrequencyMhzAsync_WritesCorrectCommand` theory test still passes with the new implementation (it tests pre-calibration fallback behaviour — expected output remains 11-digit)

## 4. Verification

- [x] 4.1 Run `dotnet test` on `OpenWSFZ.Rig.Tests` and confirm all existing and new tests pass with no regressions
- [x] 4.2 Run the full test suite (`dotnet test`) and confirm green across all projects
- [x] 4.3 Start the daemon, select a frequency from the dropdown while CAT is connected; confirm the radio tunes and the Trace log shows the exact FA set command sent (e.g. `FA014074000;` for a 9-digit rig, `FA00014074000;` for an 11-digit rig)
