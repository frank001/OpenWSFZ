## ADDED Requirements

### Requirement: TX panel — QSO Transcript section

The TX panel SHALL contain a **QSO Transcript** section, occupying the same DOM location
previously used by the "TX History" abort-reason list (`FR-062`, superseding the unspecified
`FR-UX-002` abort-only behaviour), rendered as `<ol id="tx-transcript-log">` inside
`<div id="tx-transcript-section">`. The section SHALL remain hidden until its first entry is
appended, exactly as the prior TX History section did.

The section SHALL record, as a single unified, newest-on-top, chronological list:

1. **Sent** entries — every standard FT8 message the operator's own station actually transmits.
2. **Received** entries — every decoded message belonging to the operator's own tracked
   conversation (matched by callsign token against the operator's own callsign or the active
   partner), sourced from the raw `decode` WebSocket feed **before** any `decode-panel-filtering`
   column-filter or `decode-noise-suppression` gating is applied to it.
3. **Abort** entries — an abort reason string, exactly as previously produced by `FR-UX-002`,
   now folded inline into this same list instead of a separate one.
4. **Partner-change** entries — a separator noting the tracked partner has changed, whenever
   `currentTxPartner` transitions to a new non-null value from a different previous value.

The list SHALL be capped at 100 entries; when a new entry would exceed the cap, the oldest
entry SHALL be dropped.

Sent and received entries SHALL be visually distinguished by direction: sent entries SHALL carry
CSS class `transcript-sent`; received entries SHALL carry CSS class `transcript-received`. Abort
and partner-change entries SHALL carry CSS class `transcript-event` and SHALL NOT be colorized
by direction.

#### Scenario: Section is hidden until first entry

- **WHEN** the page loads and no transcript entry has yet been recorded
- **THEN** `#tx-transcript-section` SHALL be `hidden`

#### Scenario: Sent message is recorded once per transmission step

- **WHEN** a `txState` event is received with `state: "TxAnswer"` and the previous state was
  `"Idle"` (answerer role)
- **THEN** exactly one new entry with CSS class `transcript-sent` SHALL be appended to
  `#tx-transcript-log`, containing the text `{partner} {callsign} {grid}` for the current
  partner/callsign/grid

#### Scenario: Repeated push of the same state does not duplicate the entry

- **WHEN** two consecutive `txState` events are received both carrying `state: "TxAnswer"` with
  no state change in between
- **THEN** only one `transcript-sent` entry for that transmission step SHALL exist in
  `#tx-transcript-log`

#### Scenario: A retried transmission is logged again

- **WHEN** the state machine re-enters `"TxReport"` after having left it for `"WaitRr73"` and
  timing out back to `"TxReport"` (a retry)
- **THEN** a second `transcript-sent` entry for the report message SHALL be appended, distinct
  from the first

#### Scenario: Received message from the tracked partner is recorded even when column-filtered

- **WHEN** a `decode` WebSocket event arrives whose message tokens include the active partner's
  callsign, and the current `decode-panel-filtering` column filter would hide that decode's row
  in `#decodes-table` (`tr.hidden === true`)
- **THEN** a `transcript-received` entry for that message SHALL still be appended to
  `#tx-transcript-log`

#### Scenario: Unrelated traffic is not recorded

- **WHEN** a `decode` WebSocket event arrives whose message tokens include neither the operator's
  own callsign nor the active partner's callsign
- **THEN** no entry SHALL be appended to `#tx-transcript-log` for that decode

#### Scenario: Partner change appends a separator entry

- **WHEN** `currentTxPartner` changes from `"Q2XYZ"` to `"Q3ABC"`
- **THEN** a `transcript-event` separator entry noting the new partner SHALL be appended before
  any further `transcript-sent`/`transcript-received` entries for `"Q3ABC"`

#### Scenario: Abort reason appears inline in the transcript

- **WHEN** the daemon reports a `txState` event transitioning to `"Idle"` with a non-null
  `abortReason`
- **THEN** a `transcript-event` entry containing that reason SHALL be appended to
  `#tx-transcript-log`, in chronological order alongside any sent/received entries for that QSO

#### Scenario: List is capped at 100 entries

- **WHEN** a 101st transcript entry (of any kind) is appended
- **THEN** the oldest entry SHALL be removed from `#tx-transcript-log`, leaving exactly 100
