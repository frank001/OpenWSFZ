# adif-log Specification

## Purpose

Specifies ADIF 3.x QSO logging: when a record is written (on operator confirmation or at
`QsoComplete`), what fields it contains, and the conditions (watchdog/operator abort,
confirmation cancelled) under which no record is written.

## Requirements

### Requirement: ADIF log file written on QSO completion

A new component `AdifLogWriter` in `OpenWSFZ.Daemon` SHALL append one ADIF 3.x record to `ADIF.log` when a QSO is confirmed by the operator (via `POST /api/v1/tx/log-qso` when `tx.qsoConfirmation = true`) or at `QsoComplete` (when `tx.qsoConfirmation = false`). The file SHALL be located in the same directory as `decodeLog.path` (resolved at startup). Relative paths in `decodeLog.path` are resolved from the directory containing the daemon executable. The ADIF filename is `ADIF.log` and is not separately configurable.

The file SHALL be opened in append mode for each write and closed immediately after, matching the ALL.TXT write pattern.

If the QSO is aborted (watchdog fired or operator abort) before the final TX, no record SHALL be written. If `tx.qsoConfirmation = true` and the operator presses Cancel in the confirmation dialog, no record SHALL be written.

#### Scenario: ADIF record written when operator confirms (qsoConfirmation = true)

- **WHEN** a QSO completes, `tx.qsoConfirmation = true`, and the operator presses Log QSO in the confirmation dialog
- **THEN** one ADIF record SHALL be appended to `ADIF.log` containing all confirmed fields

#### Scenario: ADIF record written at QsoComplete (qsoConfirmation = false)

- **WHEN** a QSO completes (TX_73 transmission finished) and `tx.qsoConfirmation = false`
- **THEN** one ADIF record SHALL be appended to `ADIF.log` containing at minimum: `CALL`, `GRIDSQUARE`, `MODE`, `FREQ`, `RST_SENT`, `RST_RCVD`, `QSO_DATE`, `TIME_ON`, `TIME_OFF`, `OPERATOR`, `MY_GRIDSQUARE`

#### Scenario: No record written on watchdog abort

- **WHEN** the watchdog fires before `QsoComplete`
- **THEN** no ADIF record SHALL be written

#### Scenario: No record written on operator abort

- **WHEN** `POST /api/v1/tx/abort` is received before `QsoComplete`
- **THEN** no ADIF record SHALL be written

#### Scenario: No record written when operator cancels confirmation dialog

- **WHEN** a QSO completes, `tx.qsoConfirmation = true`, and the operator presses Cancel in the dialog
- **THEN** no ADIF record SHALL be written

#### Scenario: File created if absent

- **WHEN** `ADIF.log` does not yet exist and the first QSO is logged
- **THEN** `AdifLogWriter` SHALL create the file (and any missing parent directories) and write the first record

---

### Requirement: ADIF record field content

Each ADIF record written by `AdifLogWriter` SHALL contain the following mandatory fields with values as specified, plus optional fields when non-empty values are supplied:

**Mandatory fields:**

| Field | Value |
|---|---|
| `CALL` | Active partner callsign |
| `GRIDSQUARE` | Partner grid locator (omitted if null/empty) |
| `MODE` | `FT8` |
| `BAND` | ITU band name derived from dial frequency (e.g. `40m`); omitted if frequency is 0.0 |
| `FREQ` | Dial frequency in MHz formatted to 6 decimal places (trailing zeros trimmed); omitted if 0.0 |
| `RST_SENT` | RST report sent (e.g. `+00`, `R+00`) |
| `RST_RCVD` | RST report received (e.g. `+05`, `-12`) |
| `QSO_DATE` | UTC date formatted `YYYYMMDD` |
| `TIME_ON` | UTC time of QSO start formatted `HHMMSS` |
| `TIME_OFF` | UTC time of QSO end (FT8 cycle-start floor at last-TX entry) formatted `HHMMSS` |
| `OPERATOR` | Operator callsign (from request body `operatorCallsign` when via POST; from `tx.callsign` when auto-logged) |
| `MY_GRIDSQUARE` | Operator grid locator |

**Optional fields (included when the supplied value is non-null and non-empty):**

| ADIF Field | Source |
|---|---|
| `NAME` | `PartnerName` / `name` in POST body |
| `TX_PWR` | `TxPower` / `txPower` in POST body |
| `COMMENT` | `Comment` / `comment` in POST body |
| `PROP_MODE` | `PropMode` / `propMode` in POST body |
| `STX_STRING` | `ExchSent` / `exchSent` in POST body |
| `SRX_STRING` | `ExchRcvd` / `exchRcvd` in POST body |

#### Scenario: BAND derived correctly for 40 m band

- **WHEN** dial frequency is `7.074` MHz
- **THEN** the ADIF record SHALL contain `<BAND:3>40m`

#### Scenario: BAND omitted when dialFrequencyMHz is 0.0

- **WHEN** dial frequency is `0.0`
- **THEN** the ADIF record SHALL NOT contain a `BAND` field and SHALL NOT contain a `FREQ` field

#### Scenario: RST_RCVD populated from partner report

- **WHEN** the partner transmitted `Q1OFZ Q1TST +12` and the QSO is logged
- **THEN** the ADIF record SHALL contain `<RST_RCVD:3>+12`

#### Scenario: Optional NAME field written when supplied

- **WHEN** the POST body contains `name = "John"`
- **THEN** the ADIF record SHALL contain `<NAME:4>John`

#### Scenario: Optional TX_PWR field written when supplied

- **WHEN** the POST body contains `txPower = "100"`
- **THEN** the ADIF record SHALL contain `<TX_PWR:3>100`

#### Scenario: Optional PROP_MODE field written when supplied

- **WHEN** the POST body contains `propMode = "TR"`
- **THEN** the ADIF record SHALL contain `<PROP_MODE:2>TR`

#### Scenario: Optional STX_STRING field written when supplied

- **WHEN** the POST body contains `exchSent = "599001"`
- **THEN** the ADIF record SHALL contain `<STX_STRING:6>599001`

#### Scenario: Optional SRX_STRING field written when supplied

- **WHEN** the POST body contains `exchRcvd = "599042"`
- **THEN** the ADIF record SHALL contain `<SRX_STRING:6>599042`

#### Scenario: Empty optional fields omitted from ADIF

- **WHEN** the POST body contains `comment = ""` (empty string)
- **THEN** the ADIF record SHALL NOT contain a `COMMENT` field

#### Scenario: TIME_OFF reflects FT8 cycle-start floor

- **WHEN** the last TX begins at 11:08:37 UTC and the QSO is confirmed
- **THEN** the `TIME_OFF` field SHALL be `113000` (reflecting the cycle start 11:08:30 UTC, not 11:08:37)

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
