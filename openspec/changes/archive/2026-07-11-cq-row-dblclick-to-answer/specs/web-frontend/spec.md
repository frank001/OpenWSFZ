## MODIFIED Requirements

### Requirement: Decode table — clickable CQ rows (TX-D01)

CQ decode table rows SHALL be clickable, and SHALL require a double-click (not a single
click) to arm TX. Double-clicking a CQ row while the TX controller is `Idle` SHALL:

1. Extract the partner callsign, audio frequency offset, and CQ cycle start time from
   the decode row.
2. Call `POST /api/v1/tx/answer-cq` with `{ callsign, frequencyHz, cqCycleStartUtc }`.
3. On HTTP 200: call `renderTxPanel` with the returned status (system is now armed and
   waiting for the correct FT8 answer phase; TX fires within 0–30 s at most).
4. On HTTP 409 (controller not Idle): log a console warning; no UI change.
5. On other error: log to console; no UI change.

A single click on a CQ row SHALL have no effect — it SHALL NOT call
`POST /api/v1/tx/answer-cq` and SHALL NOT change TX controller state. The row SHALL
still render its existing hover/cursor affordance (`.decode-cq:hover`, `cursor: pointer`)
so it continues to read as an interactive element; discoverability of the double-click
requirement is via that affordance and operator documentation, not an in-app prompt.

**Callsign extraction** from the CQ message:
- 3-token CQ (`CQ callsign grid`): token at index 1
- 4-token CQ (`CQ modifier callsign grid`): token at index 2

**Frequency:** the `offsetHz` value of the decode row (the audio frequency in Hz at
which the signal was detected).

**`cqCycleStartUtc`:** the UTC cycle-start timestamp of the decode row, formatted as an
ISO 8601 string (e.g. `"2026-06-22T17:29:15Z"`). The decode row's timestamp column
contains this value; the frontend SHALL parse it from the row data at render time and
store it as a data attribute or in a closure for retrieval when the row is double-clicked.

Decode row timestamp format: `YYMMDD_HHMMSS` (UTC). Parsing:
```javascript
function parseFt8CycleStartUtc(ft8Ts) {
  // ft8Ts example: "260622_172915"
  const [date, time] = ft8Ts.split('_');
  return `20${date.slice(0,2)}-${date.slice(2,4)}-${date.slice(4,6)}` +
         `T${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}Z`;
}
```

Double-clicking a CQ row while the controller is NOT Idle SHALL have no effect (the
double-click is silently ignored; a 409 response is swallowed with a console warning).

#### Scenario: Double-clicking a CQ row calls answer-cq with phase info and arms the TX panel

- **WHEN** the controller is `Idle` and the operator double-clicks a CQ row with
  message `"CQ Q1ABC JO33"`, `offsetHz = 1500`, and row timestamp `"260622_172915"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "cqCycleStartUtc": "2026-06-22T17:29:15Z" }`
- **AND** on HTTP 200 the TX panel SHALL update to the armed appearance

#### Scenario: A single click on a CQ row does not arm TX

- **WHEN** the controller is `Idle` and the operator clicks (once, not followed by a
  second click) a CQ row with message `"CQ Q1ABC JO33"`
- **THEN** no `POST /api/v1/tx/answer-cq` request SHALL be sent
- **AND** the TX controller state SHALL remain unchanged

#### Scenario: Double-clicking a 4-token CQ row extracts the callsign correctly

- **WHEN** the operator double-clicks a CQ row with message `"CQ DX Q9XYZ FN42"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with `callsign = "Q9XYZ"`

#### Scenario: Double-clicking a CQ row when not Idle has no effect

- **WHEN** the controller state is `TxAnswer` (active QSO) and the operator
  double-clicks a CQ row
- **THEN** no `POST /api/v1/tx/answer-cq` request SHALL be sent
  (or the resulting 409 SHALL be silently swallowed)
