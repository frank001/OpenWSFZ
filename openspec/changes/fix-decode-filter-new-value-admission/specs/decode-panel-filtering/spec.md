## ADDED Requirements

### Requirement: Attribute allow-list axes auto-admit previously-unseen values

The daemon SHALL track which values have been observed this session for each of the four
attribute allow-list axes (DXCC entity, Continent, CQ Zone, ITU Zone). When a decode carries a
value on one of these axes that has never been observed this session, and that axis's current
allow-list is narrowed-but-non-empty (a non-null array containing at least one value), the daemon
SHALL admit the new value into that axis's allow-list, so it is considered visible/engageable by
default — matching the behavior of an axis that has never been touched. A value already observed
this session, whether currently included or explicitly excluded by the operator, SHALL NOT be
re-admitted or altered by this mechanism.

This auto-admission SHALL be performed by the daemon itself, independent of any connected browser
client, so it applies identically during headless operation (`daemon-background-mode`,
`--background`/`--background-worker`) as it does with a browser tab attached.

An axis whose current allow-list is explicitly empty (`[]` — the operator has deselected every
value on that axis) SHALL NOT auto-admit new values — this preserves the existing "an axis with an
explicit empty selection filters everything on that axis" behavior exactly, including for values
never before seen.

Whenever an auto-admission changes the current `DecodeFilterState`, the daemon SHALL broadcast the
updated state via the existing `decodeFilterChanged` WebSocket event, identical to an
operator-driven `POST /api/v1/decode-filter`, so every connected client's popup and rendered table
converge on the same authoritative state the daemon itself evaluated engagement against.

#### Scenario: A brand-new DXCC entity is admitted into a narrowed-but-non-empty axis

- **WHEN** the DXCC-entity allow-list axis is narrowed to `{"Germany", "Monaco"}` (the operator
  previously deselected at least one other, already-seen entity) and a decode arrives whose
  resolved entity is `"Wallis and Futuna"`, never before seen this session
- **THEN** the daemon SHALL admit `"Wallis and Futuna"` into the allow-list (now
  `{"Germany", "Monaco", "Wallis and Futuna"}`), and the decode SHALL be considered
  visible/engageable on this axis

#### Scenario: An already-seen, explicitly-excluded value is never re-admitted

- **WHEN** the DXCC-entity allow-list axis is narrowed to `{"Germany"}` after the operator
  explicitly deselected `"Monaco"` (previously seen), and a further decode arrives resolving to
  `"Monaco"`
- **THEN** the allow-list SHALL remain `{"Germany"}` — `"Monaco"` SHALL NOT be re-admitted, and the
  decode SHALL remain not visible/engageable on this axis

#### Scenario: An explicitly empty axis never auto-admits

- **WHEN** the DXCC-entity allow-list axis is explicitly empty (`[]`, e.g. via "Select None") and
  a decode arrives whose resolved entity has never been observed this session
- **THEN** the allow-list SHALL remain `[]`, and the decode SHALL NOT be considered
  visible/engageable on this axis

#### Scenario: An untouched (null) axis is unaffected by admission tracking

- **WHEN** the DXCC-entity allow-list axis has never been narrowed (still `null`) and a decode
  arrives whose resolved entity has never been observed this session
- **THEN** no state change or broadcast SHALL occur — the axis remains `null` (no restriction),
  matching its existing default behavior

#### Scenario: Auto-admission applies without any browser client connected

- **WHEN** the daemon is running headless (`--background`, no browser tab connected) with a
  narrowed-but-non-empty DXCC-entity axis, and a decode arrives resolving to a never-before-seen
  entity
- **THEN** the daemon SHALL still admit the new entity into the allow-list and make it
  engageable to `QsoAnswererService`/`QsoCallerService` on that same decode cycle, identical to
  the attended case

#### Scenario: Admission is visible to the same decode cycle's engagement decision

- **WHEN** a decode carrying a never-before-seen attribute value on a narrowed-but-non-empty axis
  is processed by the daemon
- **THEN** `QsoAnswererService`/`QsoCallerService`'s engagement-decision evaluation of that same
  decode, later in the same cycle, SHALL see the already-admitted (updated) filter state — not
  the pre-admission state
