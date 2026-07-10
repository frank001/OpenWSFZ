## MODIFIED Requirements

### Requirement: WaitAnswer — waiting for a CQ response

While in `WaitAnswer`, the service SHALL scan each decode batch for messages matching
`{our_callsign} {any_callsign} {any_grid}` (i.e., a station answering our CQ with
their callsign and grid), skipping any responder whose callsign is not currently
visible/engageable under the active `DecodeFilterState` (`decode-panel-filtering` capability).

**`CallerPartnerSelect = First`:** The first matching, non-filtered-out response found in the
batch SHALL be selected automatically. The service SHALL immediately advance to `TxReport`. If
every matching response in a cycle is filtered out, the service SHALL remain in `WaitAnswer` for
that cycle, exactly as if no response had been decoded — subject to the same retry/watchdog
budget as a genuinely empty cycle (the filter does not grant an exemption from retry counting).

**`CallerPartnerSelect = None`:** No automatic selection. The service SHALL apply the
CSS class `decode-responder` signal by broadcasting a `txState` event (state
`"WaitAnswer"`, partner `null`). The operator selects a responder by double-clicking a
highlighted row; `POST /api/v1/tx/select-responder` calls `SelectResponderAsync`.
A responder callsign that is currently filtered out under the active `DecodeFilterState` SHALL
NOT be highlighted as `decode-responder` and a `SelectResponderAsync` call naming a filtered-out
callsign SHALL be rejected (no state transition) — the filter applies uniformly regardless of
partner-selection mode, not only to the automatic `First` path.
`SelectResponderAsync` stores a `_pendingResponder` (callsign, frequency, answer
phase) and writes a wakeup batch. On the next cycle at the correct answer phase, the
service fires `TxReport` for the pending responder.

If no response arrives within the retry/watchdog budget, the service retransmits the CQ
(see Retry requirement below).

The A-01 skip guard is applied: the first cycle after entering `WaitAnswer` is the
CQ station's own TX window; silence there does not count as a missed response.

Once a responder has been selected and the service has advanced past `WaitAnswer`, the active
filter state SHALL NOT be re-evaluated for the remainder of that QSO — a filter change while a
QSO is in progress SHALL NOT abort it (the operator's existing Abort/Stop controls are the only
mechanism for that).

#### Scenario: First mode auto-engages on first response

- **WHEN** `CallerPartnerSelect = First`, the service is in `WaitAnswer`, and a
  decode batch contains `"PD2FZ Q1ABC JO22"`  (where `PD2FZ` is our callsign)
- **THEN** the service SHALL select `Q1ABC` as partner and advance to `TxReport`

#### Scenario: None mode does not auto-engage

- **WHEN** `CallerPartnerSelect = None`, the service is in `WaitAnswer`, and a
  decode batch contains `"PD2FZ Q1ABC JO22"`
- **THEN** the service SHALL remain in `WaitAnswer` and SHALL NOT transmit

#### Scenario: None mode advances after SelectResponderAsync

- **WHEN** `CallerPartnerSelect = None` and `SelectResponderAsync("Q1ABC", 1500.0,
  cycleStart, ct)` is called while the service is in `WaitAnswer`
- **THEN** the service SHALL store `Q1ABC` as the pending responder and SHALL fire
  `TxReport` at the next cycle boundary of the correct answer phase

#### Scenario: A-01 guard — first empty cycle is skipped

- **WHEN** the service enters `WaitAnswer` and the first subsequent batch is empty
  (no response)
- **THEN** the service SHALL NOT count this as a missed response (it was our own TX
  window); `_skipNextRetry` SHALL be cleared and no retry SHALL be triggered

#### Scenario: First mode skips a filtered-out responder in favour of the next one

- **WHEN** `CallerPartnerSelect = First`, the service is in `WaitAnswer`, and a decode batch
  contains a response from `Q1TST` (filtered out under the active `DecodeFilterState`) followed
  by a response from `Q2ABC` (not filtered out)
- **THEN** the service SHALL skip `Q1TST` entirely and select `Q2ABC` as partner

#### Scenario: First mode — all responses filtered out — cycle treated as empty

- **WHEN** `CallerPartnerSelect = First` and every response in a decode batch is filtered out
  under the active `DecodeFilterState`
- **THEN** the service SHALL remain in `WaitAnswer` for that cycle, subject to the same
  retry/watchdog accounting as a genuinely empty cycle

#### Scenario: None mode — SelectResponderAsync rejects a filtered-out callsign

- **WHEN** `CallerPartnerSelect = None` and `SelectResponderAsync` is called naming a callsign
  currently filtered out under the active `DecodeFilterState`
- **THEN** the call SHALL be rejected — no `_pendingResponder` SHALL be stored and no state
  transition SHALL occur

#### Scenario: Filter change mid-QSO does not abort an already-engaged QSO

- **WHEN** the service has already advanced past `WaitAnswer` for a given partner, and the
  operator then changes the filter such that the active partner would now be filtered out
- **THEN** the in-progress QSO SHALL continue unaffected — the filter is not re-checked once
  engagement has begun
