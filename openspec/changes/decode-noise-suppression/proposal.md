## Why

Operators sometimes see decodes with implausible callsigns (e.g. `UE1QQU/R`, `YV1QKN/P`,
`YU4ZWV/P`) whose region/DXCC lookup resolves to `null` and renders as `"Unknown"` in the decode
panel. These are suspected decoder false positives, not genuine unrecognised-prefix misses.
Today, `"Unknown"` decodes can never be excluded via the existing decode-panel region/DXCC column
filter — `DecodeFilterEvaluator` and `decodeFilter.js` deliberately fail open on a null region (an
active allow-list never excludes an unresolved attribute), and the filter popup only offers
checkbox values it has seen resolved, so `"Unknown"` is not even a selectable value. Separately,
the R&R Synthetic study's Q-prefix test traffic (already resolved to a distinct
`"Synthetic (R&R Study)"` region per the `region-lookup` capability) is indistinguishable from real
decodes in the live decode panel today, and can feed `WorkedBeforeIndex` or trigger
`QsoAnswererService`/`QsoCallerService` auto-engagement during a normal listening session.

The product owner wants operator-controlled suppression for both classes of noise, surfaced on the
existing Region data settings page, without disturbing the intentionally fail-open design of the
existing column filter.

## What Changes

- Add a **"Suppress Unknown region/DXCC decodes"** setting to the Region data settings page. When
  enabled, any decode whose resolved region is `null` (displayed as `"Unknown"`) is fully
  suppressed: excluded from the decode-panel broadcast, from `WorkedBeforeIndex` updates, and from
  `QsoAnswererService`/`QsoCallerService` auto-engagement eligibility — treated as if it never
  arrived. This is a persisted, operator-controlled setting (not the ephemeral, non-persisted
  `DecodeFilterState`).
- This control is **always interactive** — it is never disabled or greyed out, regardless of
  whether region data has been loaded. Only its *out-of-the-box default value* depends on
  region-data presence: it defaults to unchecked while `callsign-regions.json` has never been
  populated (a fresh install shows `"Unknown"` for every decode simply because no data exists yet,
  which is not evidence of a false positive, and defaulting to checked here would make the app
  appear to decode nothing). Once region data is present, new installs/first-touch default to
  checked. Critically, any explicit choice the operator has made is persisted and is never
  silently overwritten by this default logic afterward — the operator is always in control.
- Add a **"Suppress R&R Synthetic decodes"** setting to the same page. Detection reuses the
  existing `RegionInfo.Synthetic` flag (the `region-lookup` capability's dedicated Q-prefix
  carve-out) rather than introducing a new callsign-pattern heuristic — a decode already resolved
  as `"Synthetic (R&R Study)"` is what gets suppressed. This setting defaults to **checked** (on)
  out of the box. Same suppression effect as above (panel, worked-before, auto-engagement). An
  operator observing an R&R study run against a live instance must explicitly uncheck it to see
  synthetic decodes come through normally.
- Both settings are independent of each other and of the existing `DecodeFilterState`/
  `DecodeFilterEvaluator` column filter — this is a separate, persisted pre-filter suppression
  stage evaluated upstream, not a new filter axis. `ALL.TXT` (the `decode-log` capability's raw
  ground-truth record) is explicitly **not** affected by either setting — suppression only affects
  the live decode panel, worked-before tracking, and QSO automation eligibility, consistent with
  the existing precedent that region-resolution outcomes never gate what reaches `ALL.TXT`.
- Persist both settings via the existing `JsonConfigStore` pattern used elsewhere on the Region
  data tab.

## Capabilities

### New Capabilities
- `decode-noise-suppression`: operator-controlled, persisted suppression of (a) decodes with
  unresolved (`Unknown`) region/DXCC and (b) decodes flagged as R&R-synthetic test traffic, applied
  upstream of decode-panel broadcast, `WorkedBeforeIndex`, and QSO-automation eligibility, with
  region-data-presence-dependent (but never operator-locking) default behaviour for the Unknown
  setting.

### Modified Capabilities
- None. Suppression is inserted upstream of the existing `decode-panel-filtering`,
  `qso-answerer`, `qso-caller`, and `decode-log` capabilities' inputs — each continues to see
  exactly the decode set its existing requirements describe (for `decode-log`/`ALL.TXT`, every
  decode, unaffected; for the others, decodes that have already passed the new suppression stage).
  No existing requirement text changes. (To be confirmed in design.md; if implementation reveals
  a genuine requirement-level change to any of these, the corresponding delta spec will be added
  before `tasks.md` is finalised.)

## Impact

- **Affected code**: decode-ingestion pipeline (wherever `DecodeResult`/region resolution fans out
  to `ALL.TXT`, WebSocket broadcast, `WorkedBeforeIndex`, and the QSO controller services — exact
  insertion point to be pinned down in design.md); Region data settings page
  (`web/settings.html`, `web/js/settings.js`); a new persisted settings model alongside the
  existing `JsonConfigStore`-backed region-data settings; region-data-status check (reused from
  `region-lookup-data-refresh` for the Unknown-setting's default-value gating, not for
  enable/disable).
- **Not affected**: `ALL.TXT`/`decode-log`, the existing `DecodeFilterState`/`DecodeFilterEvaluator`
  column filter and its API (`GET`/`POST /api/v1/decode-filter`), `region-lookup`'s resolution
  logic itself.
- **Testing**: per standing project policy, any change touching the
  `QsoAnswererService`/`QsoCallerService` filtering/eligibility hook requires re-running
  `qa/decode-filter-synth-verify/live_verify_9_axes.py` before merge, in addition to new unit/
  integration coverage for the suppression gate and the region-data-presence default logic.
