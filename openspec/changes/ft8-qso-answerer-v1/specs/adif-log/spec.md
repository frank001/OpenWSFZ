## ADDED Requirements

### Requirement: ADIF log file written on QSO completion

A new component `AdifLogWriter` in `OpenWSFZ.Daemon` SHALL append one ADIF 3.x record to `ADIF.log` when a QSO reaches `QsoComplete`. The file SHALL be located in the same directory as `decodeLog.path` (resolved at startup). Relative paths in `decodeLog.path` are resolved from the directory containing the daemon executable. The ADIF filename is `ADIF.log` and is not separately configurable in v1.

The file SHALL be opened in append mode for each write and closed immediately after, matching the ALL.TXT write pattern.

If `QsoComplete` is reached but the watchdog has fired or the operator aborted before TX_73 completed, no record SHALL be written.

#### Scenario: ADIF record appended on QSO completion

- **WHEN** a QSO completes (TX_73 transmission finished)
- **THEN** one ADIF record SHALL be appended to `ADIF.log` containing at minimum: `CALL`, `GRIDSQUARE`, `MODE`, `FREQ`, `RST_SENT`, `RST_RCVD`, `QSO_DATE`, `TIME_ON`, `TIME_OFF`, `OPERATOR`, `MY_GRIDSQUARE`

#### Scenario: No record written on watchdog abort

- **WHEN** the watchdog fires before `QsoComplete`
- **THEN** no ADIF record SHALL be written

#### Scenario: No record written on operator abort

- **WHEN** `POST /api/v1/tx/abort` is received before `QsoComplete`
- **THEN** no ADIF record SHALL be written

#### Scenario: File created if absent

- **WHEN** `ADIF.log` does not yet exist and the first QSO completes
- **THEN** `AdifLogWriter` SHALL create the file (and any missing parent directories) and write the first record

---

### Requirement: ADIF record field content

Each ADIF record written by `AdifLogWriter` SHALL contain the following fields with values as specified:

| Field | Value |
|---|---|
| `CALL` | Active partner callsign (from decoded CQ) |
| `GRIDSQUARE` | Partner grid locator (from decoded CQ, if present) |
| `MODE` | `FT8` |
| `BAND` | ITU band name derived from `decodeLog.dialFrequencyMHz` (e.g. `40m`); omitted if `dialFrequencyMHz` is 0.0 |
| `FREQ` | `decodeLog.dialFrequencyMHz` formatted to 6 decimal places; omitted if 0.0 |
| `RST_SENT` | `+00` (fixed for v1) |
| `RST_RCVD` | Signed integer string of the SNR from the partner's report message (e.g. `+05`, `-12`) |
| `QSO_DATE` | UTC date of cycle start of the received CQ, formatted `YYYYMMDD` (8 chars) |
| `TIME_ON` | UTC time of cycle start of the received CQ, formatted `HHMMSS` (6 chars, seconds precision) |
| `TIME_OFF` | UTC time when TX_73 playback completed, formatted `HHMMSS` (6 chars, seconds precision) |
| `OPERATOR` | `tx.callsign` |
| `MY_GRIDSQUARE` | `tx.grid` |

#### Scenario: BAND derived correctly for 40 m band

- **WHEN** `decodeLog.dialFrequencyMHz` is `7.074`
- **THEN** the ADIF record SHALL contain `<BAND:3>40m`

#### Scenario: BAND omitted when dialFrequencyMHz is 0.0

- **WHEN** `decodeLog.dialFrequencyMHz` is `0.0`
- **THEN** the ADIF record SHALL NOT contain a `BAND` field and SHALL NOT contain a `FREQ` field

#### Scenario: RST_RCVD populated from partner report

- **WHEN** the partner transmitted `Q1OFZ Q1TST +12` and the QSO completes
- **THEN** the ADIF record SHALL contain `<RST_RCVD:3>+12`

#### Scenario: RST_RCVD populated with negative report

- **WHEN** the partner transmitted `Q1OFZ Q1TST -07`
- **THEN** the ADIF record SHALL contain `<RST_RCVD:3>-07`

---

### Requirement: ADIF record format

Each record SHALL be formatted in ADIF 3.x tagged field format:

```
<FIELD_NAME:length>value
```

Records SHALL be terminated with `<EOR>` followed by CRLF. Each field SHALL appear on a single line. The file SHALL begin with an ADIF header block if no records have been written previously, or append directly if the file already exists.

#### Scenario: Correct ADIF tagged field format

- **WHEN** `CALL` is `Q1TST`
- **THEN** the written field SHALL be `<CALL:5>Q1TST`

#### Scenario: Record terminated with EOR

- **WHEN** any QSO record is written
- **THEN** the last element of the record SHALL be `<EOR>` followed by CRLF (`\r\n`)

#### Scenario: File write failure does not affect decode or QSO state

- **WHEN** `AdifLogWriter` cannot write to `ADIF.log` (e.g. permission denied, disk full)
- **THEN** the daemon SHALL log a Warning and continue operating; the QSO is still considered complete from the state machine's perspective
