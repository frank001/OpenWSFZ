## ADDED Requirements

### Requirement: Geographically implausible decodes are marked, never removed

A geographically implausible decode SHALL be annotated and SHALL still be broadcast to the panel.
A decode is geographically implausible when its transmitted grid is inconsistent with the DXCC
entity its callsign's prefix resolves to. Marking SHALL NOT remove the decode from the WebSocket
broadcast, SHALL NOT remove it from the batch delivered to `QsoAnswererService` or
`QsoCallerService`, and SHALL NOT affect `ALL.TXT`.

The concrete inconsistency predicate is the one ratified by the PO from the `FP-MARK` measurement's
candidate table (R-CONT / R-CQZ / R-ENT). Whichever is ratified, it SHALL be categorical and SHALL
NOT introduce a numeric threshold, distance bound or other tunable parameter.

#### Scenario: An implausible decode is marked and still delivered

- **WHEN** a decode carries a grid that the ratified predicate finds inconsistent with the entity its
  callsign's prefix resolves to
- **THEN** the decode SHALL be delivered to the decode panel carrying an implausibility annotation,
  and SHALL remain eligible for `QsoAnswererService`/`QsoCallerService` exactly as an unmarked decode
  is

#### Scenario: ALL.TXT is unaffected by marking

- **WHEN** a decode is marked implausible
- **THEN** the decode SHALL still be appended to `ALL.TXT` exactly as it would be if marking were
  disabled

### Requirement: Marking requires positive contradiction, never absence of evidence

A decode SHALL NOT be marked when the evidence needed to evaluate the predicate is absent. A decode
carrying no grid, or carrying a callsign whose prefix the active region store cannot resolve, SHALL
be treated as unmarked.

This keeps marking disjoint from `decode-noise-suppression`'s unknown-region rule, so a single decode
is never counted against two independent controls for the same underlying cause.

#### Scenario: A decode with no grid is not marked

- **WHEN** a decode carries no Maidenhead grid
- **THEN** the decode SHALL NOT be marked implausible

#### Scenario: A decode whose prefix does not resolve is not marked

- **WHEN** the active region store returns no region for the decode's callsign prefix
- **THEN** the decode SHALL NOT be marked implausible, and its disposition SHALL be governed solely
  by the `decode-noise-suppression` unknown-region setting

### Requirement: The decode panel visually distinguishes marked decodes

The decode panel SHALL render a marked decode with a visual indicator distinguishing it from an
unmarked decode, without hiding any field the decode would otherwise display.

#### Scenario: Marked decode is visually distinguishable

- **WHEN** a marked decode is rendered in the decode panel and the show/hide setting is set to show
- **THEN** the row SHALL carry a visible implausibility indicator, and every column value SHALL
  remain readable

### Requirement: Marked decodes transition to Dismissed and are never deleted

A marked decode SHALL support a `Dismissed` state, reachable by explicit operator action or by
age-out after a configurable interval. A dismissed decode SHALL be hidden from the default decode
panel view while remaining retrievable and countable.

🛑 A marked or dismissed decode SHALL NOT be deleted from the application's own record by either
transition, so that the feature's false-marking rate remains measurable after deployment.

#### Scenario: Operator dismisses a marked decode

- **WHEN** the operator dismisses a marked decode
- **THEN** the decode SHALL move to `Dismissed`, SHALL be hidden from the default panel view, and
  SHALL remain retrievable and counted

#### Scenario: A marked decode ages out to Dismissed rather than being deleted

- **WHEN** a marked decode has been marked for longer than the configured age-out interval
- **THEN** the decode SHALL move to `Dismissed` and SHALL NOT be deleted

#### Scenario: Dismissal never reaches ALL.TXT

- **WHEN** a decode moves to `Dismissed` by either route
- **THEN** `ALL.TXT` SHALL be unchanged by the transition

### Requirement: Show/hide of marked decodes is an operator-controlled, persisted rendering setting

The settings page SHALL expose a persisted control determining whether marked decodes are shown or
hidden in the decode panel. The control SHALL be interactive at all times and SHALL survive a daemon
restart.

🛑 This control SHALL affect **rendering only**. When set to hide, a marked decode SHALL still be
broadcast and SHALL still be delivered to `QsoAnswererService`/`QsoCallerService` — hiding SHALL NOT
be implemented as suppression.

#### Scenario: Hiding marked decodes does not change automation eligibility

- **WHEN** the operator sets the control to hide marked decodes
- **THEN** marked decodes SHALL NOT be rendered in the decode panel, **AND** SHALL still be delivered
  to `QsoAnswererService` and `QsoCallerService` exactly as when shown

#### Scenario: The setting survives a restart

- **WHEN** the operator sets the control and the daemon is restarted
- **THEN** the control SHALL retain the operator's value

### Requirement: Marking does not confer automation ineligibility

Marking SHALL have no effect on `QsoAnswererService` or `QsoCallerService` eligibility in this
capability's first delivered phase. Any change making marked decodes automation-ineligible SHALL be a
separate change, gated on the measured false-marking rate on real traffic.

#### Scenario: A marked decode remains automation-eligible

- **WHEN** a decode is marked implausible and automation is otherwise eligible to act on it
- **THEN** the automation services SHALL treat it exactly as they would an unmarked decode
