## MODIFIED Requirements

### Requirement: Outbound Clear message

The service SHALL send a WSJT-X-protocol Clear datagram only when the daemon shuts down gracefully
(`ExternalReportingService.StopAsync`), sent alongside the existing Close datagram before the
outbound sockets close. The service SHALL NOT send a Clear datagram on any other cadence — in
particular, it SHALL NOT send one at the start of every decode cycle. This corrects a defect
present since this capability's original implementation: real WSJT-X (per its own
`NetworkMessage.hpp` protocol documentation) sends Clear only on an explicit operator
"erase Band Activity window" action or on its own graceful shutdown — never on its ordinary decode
cadence, which is identical to this service's. A third-party consumer (GridTracker2, JTAlert, ...)
treats Clear as "discard everything accumulated from this source"; sending it every ~15-second
decode cycle caused such a consumer's own accumulated state (e.g. a spot map) to be wiped every
cycle instead of persisting across a session, in stark contrast to a real WSJT-X source.

#### Scenario: No Clear datagram is sent during ordinary decode-cycle operation

- **WHEN** the service is running with at least one enabled target and successive decode cycles
  produce Decode datagrams, regardless of how many (or how few) decodes each cycle contains
- **THEN** no Clear datagram SHALL be sent at any point during this ordinary operation

#### Scenario: Clear sent on graceful shutdown

- **WHEN** the daemon receives a shutdown signal and `ExternalReportingService.StopAsync` runs
- **THEN** a Clear datagram SHALL be sent to every enabled target, alongside the existing Close
  datagram, before the outbound sockets close

---

### Requirement: Outbound Decode message

The service SHALL send one WSJT-X-protocol Decode datagram per `DecodeResult` delivered on the
existing per-cycle decode batch (the same feed `QsoAnswererService` subscribes to per its own spec),
carrying: UTC time, SNR, delta-time, delta-frequency (Hz), mode (`"~"` for FT8, matching WSJT-X's own
convention), the decoded message text, and the low-confidence flag. The `New` flag SHALL be `true`
(this service does not replay historical decodes).

**Absolute exclusion, no exceptions:** a `DecodeResult` whose `Region` is `null` (unresolved/unknown)
or whose `Region.Synthetic` is `true` (R&R-study synthetic entry, NFR-021 Q-prefix convention) SHALL
NEVER produce an outbound Decode datagram, to any target, under any circumstance. This exclusion is
enforced unconditionally inside `ExternalReportingService` itself, independent of
`DecodeNoiseSuppressionConfig.SuppressUnknownRegion`/`SuppressSynthetic` (which gate only the decode
panel and QSO automation and can be disabled by the operator) — it is not exposed as, and SHALL NOT
be exposed as, any Settings-page control or config field. This is a data-integrity/privacy floor:
nothing this application cannot vouch for as real, resolved amateur-radio traffic may leave the
machine via this channel, regardless of what the operator has configured elsewhere.

#### Scenario: One decode produces one Decode datagram per enabled target

- **WHEN** a decode cycle yields exactly one `DecodeResult` with a resolved, non-synthetic `Region`
- **THEN** exactly one Decode datagram carrying that result's fields SHALL be sent to each enabled
  target

#### Scenario: Unknown-region and synthetic decodes are never broadcast, even with suppression disabled

- **WHEN** `DecodeNoiseSuppressionConfig.SuppressUnknownRegion` and `SuppressSynthetic` are both
  `false` (the exact condition that lets such decodes reach this service's inbound channel), and a
  decode cycle contains a `DecodeResult` with `Region: null` and another with `Region.Synthetic: true`
- **THEN** neither `DecodeResult` SHALL produce an outbound Decode datagram to any target

---

### Requirement: Settings page — External Programs tab

The Settings page SHALL gain a new tab labelled **"External Programs"**, following the existing tab
pattern (FR-035, FR-043). The tab SHALL display: an **Enabled** checkbox bound to
`externalReporting.enabled`; an editable table of targets (columns: Name, Host, Port, Enabled,
Delete) with an **"Add target"** button that appends a blank row (`name = ""`, `host = "127.0.0.1"`,
`port = 2237`, `enabled = true`); a **"Honour inbound commands (Reply / Free Text)"** checkbox bound
to `externalReporting.honourInboundCommands`, with adjacent explanatory text stating that Halt Tx is
always honoured regardless of this setting; and a **"Restrict external Reply to the current
decode-panel filter"** checkbox bound to `externalReporting.restrictExternalRepliesToDecodeFilter`,
nested under/beside the "Honour inbound commands" control since it has no effect unless that one is
also checked, with adjacent explanatory text stating that unchecked (the default) allows a
third-party program to Reply to any currently decoded station regardless of the operator's own
decode-panel filter. All changes SHALL participate in the existing unsaved-changes flow (FR-040) and
SHALL be posted via `POST /api/v1/config` on Save. Per FR-016, this tab SHALL ship only once the
backend round-trip (config persistence and the running `ExternalReportingService`) is fully
implemented and testable end-to-end.

#### Scenario: Adding a target row

- **WHEN** the operator clicks "Add target" on the External Programs tab
- **THEN** a new blank row SHALL appear pre-filled with `host = "127.0.0.1"`, `port = 2237`,
  `enabled = true`, and the unsaved-changes indicator SHALL appear

#### Scenario: Honour-inbound-commands checkbox persists independently of Enabled

- **WHEN** the operator checks "Honour inbound commands" and saves, with `Enabled` already `true`
- **THEN** `POST /api/v1/config` SHALL include `externalReporting.honourInboundCommands: true`

#### Scenario: Restrict-external-replies checkbox defaults unchecked and persists when set

- **WHEN** the operator opens the External Programs tab on a config with no prior
  `restrictExternalRepliesToDecodeFilter` value
- **THEN** the checkbox SHALL render unchecked (matching the `false` default), and if the operator
  checks it and saves, `POST /api/v1/config` SHALL include
  `externalReporting.restrictExternalRepliesToDecodeFilter: true`
