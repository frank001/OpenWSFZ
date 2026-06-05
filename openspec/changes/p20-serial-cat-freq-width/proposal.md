## Why

`SerialCatConnection.SetDialFrequencyMhzAsync` hard-codes an 11-digit FA command format (`FA00014074000;`), but different Yaesu/Kenwood rig families use 8, 9, or 11 digits. A rig that uses 9-digit format will silently ignore the 11-digit set command, leaving the operator with a tune button that returns 200 OK yet moves nothing. The rig reveals its own format on every poll response — the software simply needs to read it.

## What Changes

- `SerialCatConnection` gains a `volatile int _freqWidth` field, initialised to zero.
- `GetDialFrequencyMhzAsync` records `digitCount` from the first successful FA; response and stores it in `_freqWidth`.
- `SetDialFrequencyMhzAsync` uses the stored `_freqWidth` to format the FA set command; falls back to 11 until the first poll completes.
- `LogDebug` entries are added to both serial I/O methods to make the exact bytes exchanged visible in Trace-level logs.
- The `cat-control` spec scenarios for `SerialCatConnection` are corrected: the fixed "11-digit" and "15 characters long" language is replaced with "8–11 digits" and the self-calibration behaviour is specified.
- Unit tests are extended with 9-digit and 11-digit rig scenarios for both GET and SET paths.

## Capabilities

### New Capabilities

*(none — this is a corrective change to an existing capability)*

### Modified Capabilities

- `cat-control`: The `SerialCatConnection` requirement currently mandates `FA<11-digit-Hz>;` format for both GET responses and SET commands, and specifies "15 characters long" as the validity check. These are being corrected to reflect the actual 8–11 digit range accepted on GET and the self-calibrating width used on SET.

## Impact

- **`src/OpenWSFZ.Rig/SerialCatConnection.cs`** — implementation change; public API (`IRadioConnection`) unchanged.
- **`tests/OpenWSFZ.Rig.Tests/`** — new test cases for 9-digit and 11-digit rig scenarios.
- **`openspec/specs/cat-control/spec.md`** — delta spec correcting the FA format scenarios.
- No config schema changes. No user-visible behavioural changes when the rig already uses 11-digit format. Rigs using fewer digits will now tune correctly.
