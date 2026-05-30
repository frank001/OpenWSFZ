## Requirements

### Requirement: ALL.TXT decode log file

The daemon SHALL append one line per decoded FT8 message to a configurable file (default: `ALL.TXT` beside the executable) after each decode cycle, when `decodeLog.enabled` is `true`. The line format SHALL be identical to the WSJT-X `ALL.TXT` format:

```
YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}
```

Where:
- `YYMMDD_HHMMSS` — UTC timestamp of the FT8 cycle slot (e.g. `260528_172930`).
- `D.DDD` — dial frequency in MHz from `decodeLog.dialFrequencyMHz`, formatted to 3 decimal places (e.g. `7.074`).
- `{snr,6}` — SNR in dB, right-justified in a 6-character field (e.g. `     3`, `   -11`).
- `{dt,4:F1}` — timing offset in seconds, right-justified in a 4-character field with 1 decimal place (e.g. ` 0.2`).
- `{freq,4}` — audio frequency offset in Hz, right-justified in a 4-character field (e.g. `2252`).
- `{message}` — decoded message text.

Each line SHALL be terminated with CRLF (`\r\n`) to match the WSJT-X ALL.TXT format. The file SHALL be opened in append mode for each cycle and closed after writing, so that lines are visible to external readers between cycles.

#### Scenario: Lines appended after each decode cycle

- **WHEN** `DecodeAsync` returns a non-empty result list and `decodeLog.enabled` is `true`
- **THEN** the daemon SHALL append one correctly-formatted line per result to `decodeLog.path`, using the UTC date of the decode call and the cycle-start time from each `DecodeResult.Time`

#### Scenario: Nothing written when disabled

- **WHEN** `decodeLog.enabled` is `false`
- **THEN** the daemon SHALL NOT open or write to `decodeLog.path`

#### Scenario: Nothing written when result list is empty

- **WHEN** `DecodeAsync` returns an empty result list and `decodeLog.enabled` is `true`
- **THEN** the daemon SHALL NOT write any lines to `decodeLog.path` for that cycle

#### Scenario: File created if absent

- **WHEN** `decodeLog.enabled` is `true` and the file at `decodeLog.path` does not yet exist
- **THEN** the daemon SHALL create the file (and any missing parent directories) on first write and append the decode lines

#### Scenario: File write failure does not affect decode output

- **WHEN** the daemon cannot write to `decodeLog.path` (e.g. permission denied, disk full)
- **THEN** the daemon SHALL log a Warning, skip writing for that cycle, and continue emitting decode results via the WebSocket event bus without interruption

#### Scenario: Correct column alignment matches WSJT-X

- **WHEN** a decode result with `Snr = 3`, `Dt = 0.2`, `FreqHz = 2252`, and `Message = "DL4DSA PD1BER JO22"` is written with `dialFrequencyMHz = 7.074` at cycle time `17:29:30` on 2026-05-28
- **THEN** the written line SHALL be exactly `260528_172930     7.074 Rx FT8      3  0.2 2252 DL4DSA PD1BER JO22`
  (note: 2 spaces before "0.2" = 1-char field separator + 1-char left-pad of "0.2" in a 4-char dt field)
