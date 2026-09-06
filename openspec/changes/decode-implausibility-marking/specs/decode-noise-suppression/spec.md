## MODIFIED Requirements

### Requirement: Suppression settings are independent of the ephemeral decode-panel column filter

The two persisted suppression settings SHALL be evaluated independently of, and ahead of, the
ephemeral `DecodeFilterState`/`DecodeFilterEvaluator` column filter (`decode-panel-filtering`
capability), and SHALL survive a daemon restart.

**This change inserts a third stage between them.** The decode pipeline order SHALL be:

1. **`decode-noise-suppression`** — removal. A suppressed decode is gone for panel and automation
   purposes.
2. **`decode-implausibility-marking`** — annotation. Evaluated only on decodes that survived stage 1,
   so a suppressed decode is never marked. This stage removes nothing.
3. **`decode-panel-filtering`** — the ephemeral column filter, unchanged.

The `decode-implausibility-marking` show/hide control SHALL NOT participate in this pipeline: it is a
rendering control applied at presentation time, and SHALL NOT remove a decode from the WebSocket
broadcast or from `QsoAnswererService`/`QsoCallerService` eligibility.

#### Scenario: Suppression settings survive a daemon restart

- **WHEN** the operator has set either suppression setting and the daemon is restarted
- **THEN** both settings SHALL retain their operator-set values

#### Scenario: Suppression and the column filter compose without interfering

- **WHEN** a suppression rule is active and a decode-panel column filter is also set
- **THEN** suppression SHALL be applied first and the column filter SHALL apply only to decodes that
  survived suppression

#### Scenario: A suppressed decode is never marked implausible

- **WHEN** a decode matches an active suppression rule **AND** would also satisfy the implausibility
  predicate
- **THEN** the decode SHALL be suppressed and SHALL NOT be marked, carrying no implausibility
  annotation anywhere

#### Scenario: Marking and suppression remain independently controllable

- **WHEN** the operator disables both suppression settings and leaves marking enabled
- **THEN** decodes that would have been suppressed SHALL be delivered normally, and SHALL be marked
  only where the implausibility predicate itself is satisfied
