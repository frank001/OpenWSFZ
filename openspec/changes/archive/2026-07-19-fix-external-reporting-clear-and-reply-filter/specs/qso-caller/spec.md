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
partner-selection mode, not only to the automatic `First` path. This unconditional rejection
applies to `SelectResponderAsync` itself, i.e. to the manual/browser call path; the
`external-reporting` capability's inbound-Reply engagement path
(`TryEngageExternalResponder`) calls into the same underlying state transition but applies its own,
separately-configurable filter check instead — see "External reply engages a specific responder"
below.
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

---

## ADDED Requirements

### Requirement: External reply engages a specific responder

`QsoCallerService` SHALL expose `Task<bool> TryEngageExternalResponder(string callsign,
CancellationToken ct = default)`, callable in-process by the `external-reporting` capability's
inbound Reply handler (via `IExternalReplyTarget`, implemented by `QsoControllerRouter`). When
called while the service is in `WaitAnswer` and `callsign` matches a responder observed answering
the active CQ this session, the service SHALL engage exactly as
`SelectResponderAsync` would (advancing the pending-responder state and firing `TxReport` at the
next correct answer phase), returning `true`.

Whether a responder that is currently filtered out under the active `DecodeFilterState` may still
be engaged via this method depends on `externalReporting.restrictExternalRepliesToDecodeFilter`
(`configuration`/`external-reporting` capabilities): when `false` (the default), a filtered-out
responder SHALL still be engaged — an explicit external command is treated as authoritative
regardless of what the operator's own decode-panel filter happens to be hiding. When `true`, a
filtered-out responder SHALL be rejected exactly as an unobserved callsign would be. This flag has
no effect on the manual `SelectResponderAsync` entry point (double-click, `POST
/api/v1/tx/select-responder`) or on the `CallerPartnerSelect = First` automatic-selection path —
both continue to respect the active `DecodeFilterState` unconditionally, unaffected by this flag in
either state.

If `callsign` has not been observed responding to the active CQ this session, or the service is not
in `WaitAnswer`, the call SHALL take no action and return `false`; a matching Information-level log
entry SHALL record the reason.

#### Scenario: External reply engages an observed responder

- **WHEN** the service is in `WaitAnswer`, `Q1TST` has been observed responding to the active CQ
  this session (not filtered out), and `TryEngageExternalResponder("Q1TST")` is called
- **THEN** the service SHALL store `Q1TST` as the pending responder and fire `TxReport` at the next
  correct answer phase, and the call SHALL return `true`

#### Scenario: Default config — external reply to a filtered-out responder still engages

- **WHEN** `externalReporting.restrictExternalRepliesToDecodeFilter` is `false` (the default), and
  `TryEngageExternalResponder("Q1TST")` is called and `Q1TST` has been observed responding but is
  currently filtered out under the active `DecodeFilterState`
- **THEN** the service SHALL store `Q1TST` as the pending responder and fire `TxReport` at the next
  correct answer phase, exactly as if the responder were not filtered out

#### Scenario: Restrict-to-filter opted in — external reply to a filtered-out responder is a no-op

- **WHEN** `externalReporting.restrictExternalRepliesToDecodeFilter` is `true`, and
  `TryEngageExternalResponder("Q1TST")` is called and `Q1TST` has been observed responding but is
  currently filtered out under the active `DecodeFilterState`
- **THEN** the call SHALL be rejected — no `_pendingResponder` SHALL be stored and no state
  transition SHALL occur, and the call SHALL return `false`

#### Scenario: External reply to an unobserved callsign is a no-op

- **WHEN** `TryEngageExternalResponder("Q9ZZZ")` is called and `Q9ZZZ` has not been observed
  responding to the active CQ this session
- **THEN** the call SHALL take no action and SHALL return `false`

#### Scenario: External reply while not in WaitAnswer is a no-op

- **WHEN** the service is not in `WaitAnswer` and `TryEngageExternalResponder` is called for any
  callsign
- **THEN** the call SHALL take no action and SHALL return `false`
