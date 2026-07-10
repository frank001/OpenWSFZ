## MODIFIED Requirements

### Requirement: Auto-answer first decoded CQ

While in `Idle` with `tx.autoAnswer = true`, the service SHALL inspect each decode batch for FT8 messages matching the CQ pattern (`CQ <callsign> <grid>`), skipping any CQ whose callsign is not currently visible/engageable under the active `DecodeFilterState` (`decode-panel-filtering` capability). On the first matching, non-filtered-out CQ, the service SHALL:

1. Record the caller callsign and audio frequency
2. Generate the answer message: `<caller>  <ours>  <grid>` where `<ours>` and `<grid>` come from `tx.callsign` and `tx.grid`
3. Encode and synthesise the TX audio at the caller's audio frequency
4. Call `IPttController.KeyDownAsync` to begin transmission
5. Advance to `TxAnswer`; after playback completes, advance to `WaitReport`

If multiple CQs are decoded in the same cycle, the first non-filtered-out one in the decoded list SHALL be selected — a filtered-out CQ SHALL be skipped entirely for this cycle's selection, not merely deprioritised. If every decoded CQ in a cycle is filtered out, the service SHALL remain in `Idle` and SHALL NOT transmit, exactly as if no CQ had been decoded at all. If `tx.callsign` or `tx.grid` is empty or whitespace-only, the CQ SHALL be ignored and a Warning logged.

Once a CQ has been selected and the service has advanced past `Idle`, the active filter state SHALL NOT be re-evaluated for the remainder of that QSO — a filter change while a QSO is in progress SHALL NOT abort it (the operator's existing Abort/Stop controls are the only mechanism for that).

**TX frequency selection:** When the service answers a CQ and `tx.holdTxFreq` is `false`, the TX frequency SHALL be the caller's decoded `freqHz` (existing behaviour). The service SHALL additionally update `tx.txAudioOffsetHz` in `IConfigStore` to match and push an `audioOffset` WebSocket event so the waterfall cursor reflects the actual transmission frequency.

When `tx.holdTxFreq` is `true`, the TX frequency SHALL be `tx.txAudioOffsetHz` from the current config. The service SHALL NOT modify `txAudioOffsetHz` or push an `audioOffset` event in this case.

This TX frequency selection logic applies to all transmitted messages in a session (answer, report, Tx73, retries). The TX frequency is fixed at the start of each CQ answer and does not change mid-session regardless of `holdTxFreq`.

#### Scenario: CQ triggers auto-answer

- **WHEN** the service is in `Idle`, `tx.autoAnswer` is `true`, and a decode batch contains `CQ Q1TST JO22`
- **THEN** the service SHALL advance to `TxAnswer`, begin transmitting `Q1TST Q1OFZ JO33`, and advance to `WaitReport` after the TX slot completes

#### Scenario: Multiple CQs in one cycle — first selected

- **WHEN** a decode batch contains `CQ Q1TST JO22` and `CQ Q2ABC KP20`
- **THEN** the service SHALL answer `Q1TST` (first in list) and ignore `Q2ABC`

#### Scenario: Non-CQ decodes in Idle are ignored

- **WHEN** the service is in `Idle` and the decode batch contains only `Q2ABC Q3DEF +05`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit

#### Scenario: Empty callsign or grid prevents auto-answer

- **WHEN** `tx.callsign` is empty and a CQ is decoded
- **THEN** the service SHALL ignore the CQ, log a Warning, and remain in `Idle`

#### Scenario: Filtered-out CQ is skipped, next non-filtered CQ engaged instead

- **WHEN** a decode batch contains `CQ Q1TST JO22` (filtered out under the active
  `DecodeFilterState`) followed by `CQ Q2ABC KP20` (not filtered out)
- **THEN** the service SHALL skip `Q1TST` entirely and answer `Q2ABC`

#### Scenario: All CQs in a cycle filtered out — no engagement

- **WHEN** every CQ in a decode batch is filtered out under the active `DecodeFilterState`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit, identical to a cycle with no
  CQs at all

#### Scenario: Filter change mid-QSO does not abort an already-engaged QSO

- **WHEN** the service has already advanced past `Idle` for a given partner, and the operator then
  changes the filter such that the active partner would now be filtered out
- **THEN** the in-progress QSO SHALL continue unaffected — the filter is not re-checked once
  engagement has begun

#### Scenario: Hold TX Freq false — TX at caller's frequency, cursor updated

- **WHEN** the service answers a CQ from `Q1TST` at 1234 Hz and `tx.holdTxFreq` is `false`
- **THEN** the service SHALL transmit at 1234 Hz
- **AND** `IConfigStore.Current.Tx.TxAudioOffsetHz` SHALL be updated to 1234
- **AND** an `audioOffset` WebSocket event SHALL be pushed with `txHz = 1234`

#### Scenario: Hold TX Freq true — TX at operator-set frequency, cursor unchanged

- **WHEN** the service answers a CQ from `Q1TST` at 1234 Hz and `tx.holdTxFreq` is `true` and `tx.txAudioOffsetHz` is 1500
- **THEN** the service SHALL transmit at 1500 Hz
- **AND** `IConfigStore.Current.Tx.TxAudioOffsetHz` SHALL remain 1500
- **AND** no `audioOffset` WebSocket event SHALL be pushed by the answerer
