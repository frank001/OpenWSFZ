# decode-noise-suppression Specification

## Purpose

Specifies operator-controlled, persisted suppression of two classes of decode-pipeline noise: (a)
decodes whose region/DXCC lookup resolves to `Unknown` (suspected decoder false positives rather
than genuine unrecognised-prefix misses), and (b) decodes flagged as R&R Synthetic-study Q-prefix
test traffic (the `region-lookup` capability's dedicated `RegionInfo.Synthetic` carve-out).
Suppression is applied upstream of the decode-panel WebSocket broadcast and of
`QsoAnswererService`/`QsoCallerService` eligibility, and is independent of, and evaluated ahead of,
the existing ephemeral `DecodeFilterState`/`DecodeFilterEvaluator` column filter
(`decode-panel-filtering` capability). `ALL.TXT` (`decode-log` capability) is never affected by
either setting. The Unknown-region control is always interactive regardless of region-data
presence; only its computed default (before an explicit operator choice is made) depends on
whether the active region table currently has any loaded entries.

## Requirements

### Requirement: Suppressed decodes are excluded from the decode panel and from QSO-controller eligibility

A decode matching an active suppression rule SHALL NOT be broadcast to the live decode panel, and
SHALL NOT be included in the batch delivered to `QsoAnswererService` or `QsoCallerService` — it
SHALL be treated as if it never arrived for these two purposes (a rule is "active" per the
Unknown-region or R&R-synthetic requirements below). `ALL.TXT` SHALL continue to receive every
decode exactly as it does today, unaffected by either suppression setting.

#### Scenario: A suppressed decode does not reach the decode panel

- **WHEN** a decode matches an active suppression rule
- **THEN** the decode SHALL NOT be delivered over the WebSocket decode channel to any connected
  client

#### Scenario: A suppressed decode is never eligible for automation

- **WHEN** a decode matches an active suppression rule
- **THEN** the decode SHALL NOT be included in the batch delivered to `QsoAnswererService` or
  `QsoCallerService`, and SHALL therefore never be able to result in a logged QSO or a
  `WorkedBeforeIndex` registration from this decode

#### Scenario: ALL.TXT is unaffected by suppression

- **WHEN** a decode matches an active suppression rule
- **THEN** the decode SHALL still be appended to `ALL.TXT` exactly as it would be if no suppression
  rule were active

---

### Requirement: Unknown-region suppression control is always interactive

The Region data settings page's "Suppress Unknown region/DXCC decodes" control SHALL remain
interactive (enabled, clickable) at all times, regardless of whether region data has been loaded.
It SHALL NOT be disabled, greyed out, or otherwise made non-interactive based on region-data
presence or absence.

#### Scenario: Control is interactive before any region-data refresh

- **WHEN** an operator opens the Region data settings page and no region-data refresh has ever
  succeeded (the active region table is empty or seed-only)
- **THEN** the "Suppress Unknown region/DXCC decodes" control SHALL be interactive and the operator
  SHALL be able to check or uncheck it

#### Scenario: Control is interactive after region data is present

- **WHEN** an operator opens the Region data settings page after a successful region-data refresh
- **THEN** the "Suppress Unknown region/DXCC decodes" control SHALL remain interactive

---

### Requirement: Unknown-region suppression defaults on region-data presence until the operator chooses explicitly

The persisted Unknown-region suppression setting SHALL support three states: unset (no explicit
operator choice yet), explicitly enabled, or explicitly disabled. While unset, the effective
(applied) value SHALL be computed from whether the active region table currently has any loaded
entries: disabled (do not suppress) while the region table has no loaded entries, enabled
(suppress) once the region table has at least one loaded entry. The moment the operator explicitly
checks or unchecks the control, the setting SHALL become explicit (enabled or disabled) and SHALL
remain exactly as the operator set it regardless of any subsequent region-data refresh activity —
an explicit operator choice SHALL NOT be silently reverted or recomputed by this default logic.

#### Scenario: Unset setting does not suppress before region data exists

- **WHEN** the Unknown-region suppression setting has never been explicitly set by the operator and
  the active region table has no loaded entries
- **THEN** decodes with an unresolved (`Unknown`) region SHALL NOT be suppressed

#### Scenario: Unset setting starts suppressing once region data is loaded

- **WHEN** the Unknown-region suppression setting has never been explicitly set by the operator and
  a region-data refresh subsequently succeeds, populating the region table
- **THEN** decodes with an unresolved (`Unknown`) region SHALL begin being suppressed from that
  point on, without requiring any settings-page action

#### Scenario: An explicit operator choice persists regardless of region-data state

- **WHEN** the operator has explicitly set the Unknown-region suppression setting (enabled or
  disabled), and region data is subsequently refreshed, cleared, or remains unchanged
- **THEN** the setting SHALL continue to apply exactly as the operator set it, and SHALL NOT be
  recomputed from region-data presence

---

### Requirement: R&R-synthetic suppression reuses the existing Region.Synthetic flag and defaults enabled

The "Suppress R&R Synthetic decodes" setting SHALL suppress any decode whose resolved region is
flagged as synthetic (the `region-lookup` capability's dedicated Q-prefix carve-out), and SHALL NOT
introduce a separate callsign-pattern detection mechanism. This setting SHALL default to enabled
(suppressing synthetic decodes) on a fresh configuration, independent of region-data presence.

#### Scenario: Synthetic-flagged decode is suppressed by default

- **WHEN** a decode's resolved region is flagged synthetic and the operator has not changed the
  R&R-synthetic suppression setting from its default
- **THEN** the decode SHALL be suppressed per the "Suppressed decodes are excluded ..." requirement

#### Scenario: Operator disables synthetic suppression to observe a study run

- **WHEN** the operator unchecks the "Suppress R&R Synthetic decodes" control
- **THEN** decodes whose resolved region is flagged synthetic SHALL be delivered to the decode panel
  and included in QSO-controller batches normally, exactly as any other decode

---

### Requirement: Suppression settings are independent of the ephemeral decode-panel column filter

The two suppression settings SHALL be persisted (surviving a daemon restart) and SHALL be
evaluated upstream of, and independently from, the existing ephemeral `DecodeFilterState`/
`DecodeFilterEvaluator` column filter (`decode-panel-filtering` capability). Neither suppression
setting SHALL be represented as an axis of `DecodeFilterState`, and neither SHALL be reset by a
daemon restart.

#### Scenario: Suppression settings survive a daemon restart

- **WHEN** the daemon restarts after an operator has explicitly configured either suppression
  setting
- **THEN** the previously-configured suppression settings SHALL still apply after restart, in
  contrast to the column filter, which resets to unfiltered on every restart

#### Scenario: Suppression and the column filter compose without interfering

- **WHEN** a decode is not suppressed by either suppression setting, and the column filter
  additionally applies its own axis restrictions
- **THEN** the decode's visibility SHALL be determined by the column filter's existing rules,
  unaffected by the suppression stage having already passed it through
