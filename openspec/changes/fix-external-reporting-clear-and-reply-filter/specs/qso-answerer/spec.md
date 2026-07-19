## MODIFIED Requirements

### Requirement: External reply engages a specific decoded CQ

`QsoAnswererService` SHALL expose `Task<bool> TryEngageExternal(string callsign, CancellationToken
ct = default)`, callable in-process by the `external-reporting` capability's inbound Reply handler
(via `IExternalReplyTarget`, implemented by `QsoControllerRouter`). When called while the service is
in `Idle` and `callsign` matches the source callsign of a CQ present in the most recent decode batch,
the service SHALL engage exactly as it would for that CQ under its existing auto-answer path
(Requirement: "Auto-answer first decoded CQ"), advancing to `TxAnswer` and returning `true`. This
SHALL apply regardless of the value of `tx.autoAnswer` — an explicit external reply is a one-shot
manual instruction, not automatic behaviour, so it is not gated by the auto-answer toggle.

Whether a CQ that is currently filtered out under the active `DecodeFilterState` may still be
engaged via this method depends on
`externalReporting.restrictExternalRepliesToDecodeFilter` (`configuration`/`external-reporting`
capabilities): when `false` (the default), a filtered-out CQ SHALL still be engaged — an explicit
external command is treated as authoritative regardless of what the operator's own decode-panel
filter happens to be hiding. When `true`, a filtered-out CQ SHALL be rejected exactly as an unknown
callsign would be. This flag has no effect on any other engagement path — the internal auto-answer
CQ scan (Requirement: "Auto-answer first decoded CQ") and any manual, browser-driven engagement
SHALL continue to respect the active `DecodeFilterState` unconditionally, unaffected by this flag in
either state.

If `callsign` does not match any currently decoded CQ eligible under the rule above, or the service
is not in `Idle`, or `tx.callsign`/`tx.grid` is empty, the call SHALL take no action and return
`false`; a matching Information-level log entry SHALL record the reason.

#### Scenario: External reply engages a matching decoded CQ

- **WHEN** the service is in `Idle`, the most recent decode batch contains `CQ Q1TST JO22` (not
  filtered out), and `TryEngageExternal("Q1TST")` is called
- **THEN** the service SHALL advance to `TxAnswer`, begin transmitting the answer to `Q1TST`, and the
  call SHALL return `true`

#### Scenario: External reply works even when autoAnswer is disabled

- **WHEN** `tx.autoAnswer` is `false`, the service is `Idle`, and `TryEngageExternal("Q1TST")` is
  called for a callsign present as a CQ in the current decode batch
- **THEN** the service SHALL engage `Q1TST` exactly as in the enabled case, unaffected by
  `tx.autoAnswer`

#### Scenario: External reply to an unknown callsign is a no-op

- **WHEN** `TryEngageExternal("Q9ZZZ")` is called and no CQ from `Q9ZZZ` is present in the most
  recent decode batch
- **THEN** the service SHALL remain `Idle`, SHALL NOT transmit, and the call SHALL return `false`

#### Scenario: Default config — external reply to a filtered-out callsign still engages

- **WHEN** `externalReporting.restrictExternalRepliesToDecodeFilter` is `false` (the default), and
  `TryEngageExternal("Q1TST")` is called and `Q1TST`'s CQ is present but filtered out under the
  active `DecodeFilterState`
- **THEN** the service SHALL advance to `TxAnswer`, begin transmitting the answer to `Q1TST`, and the
  call SHALL return `true`, exactly as if the CQ were not filtered out

#### Scenario: Restrict-to-filter opted in — external reply to a filtered-out callsign is a no-op

- **WHEN** `externalReporting.restrictExternalRepliesToDecodeFilter` is `true`, and
  `TryEngageExternal("Q1TST")` is called and `Q1TST`'s CQ is present but filtered out under the
  active `DecodeFilterState`
- **THEN** the service SHALL remain `Idle`, SHALL NOT transmit, and the call SHALL return `false`

#### Scenario: External reply while already engaged is a no-op

- **WHEN** the service is not in `Idle` (already mid-QSO with a different partner) and
  `TryEngageExternal` is called for any callsign
- **THEN** the in-progress QSO SHALL continue unaffected, no new engagement SHALL occur, and the call
  SHALL return `false`
