## Why

`qso-confirmation` (shipped, archived 2026-07-09) tells the operator whether a decode's
callsign, DXCC entity, or continent has been worked *at all, ever*. In practice this
under-serves the most common real use of "worked before" in the hobby: band-specific award
tracking (5-Band DXCC, per-band zone awards) and the single most frequent real-time question in
a live session — "have I already worked this exact station on the band I'm on right now?" A
station worked on 40m last year reads identically today, on 20m, as a station worked on 20m ten
minutes ago — both simply show a checkmark. The operator has no way to tell "already got this
one on this band" from "worked before, but this band is still new" without leaving the app to
cross-reference a log by hand, which defeats the purpose of a glance-able indicator during a
fast-moving FT8 session. This mirrors an indicator style already familiar from WSJT-X-adjacent
logging tools (JTAlert and similar), which the Captain specifically pointed to as the target
behaviour.

Separately, the existing three-column set (Partner/Country/Region) has a naming problem noticed
while scoping this change: "Partner" is not the term hams use ("Contact" is), and "Region" as a
worked-before column label collides with the *unrelated, pre-existing* Region *display* column
(which shows `"{continent} — {entity}"` and is not part of `qso-confirmation` at all) — both
worth fixing while this capability is already being touched, rather than leaving the collision
in place indefinitely.

This change also deliberately reopens a non-goal from `qso-confirmation`'s original design
("No band- or mode-scoped matching... any time, any band/mode") — a conscious, Captain-directed
reversal based on real operating experience, not scope creep.

## What Changes

- **Rename the three existing worked-before columns**, no behaviour change to what they measure:
  Partner → **Contact** (`Ctc`), Country → **DXCC**, Region → **Continent** (`Cnt`) — the last
  rename specifically to stop colliding with the pre-existing, unrelated Region display column.
- **Add two new worked-before dimensions**, using data already resolved on every decode but not
  yet indexed for worked-before purposes: **CQ Zone** (`CQz`) and **ITU Zone** (`ITz`), sourced
  from `RegionInfo.CqZone`/`ItuZone` (`region-lookup` capability, itself sourced from
  `cty.plist`).
- **Make all five worked-before indicators band-aware and tri-state**, replacing today's binary
  checkmark/empty glyph:
  - *Never worked* (on this axis, any band) — empty/neutral.
  - *Worked before, but not on the current session's active band* — a distinct "still wanted on
    this band" glyph.
  - *Worked before on the current session's active band* — the existing green-checkmark "done"
    glyph.
  This requires `WorkedBeforeIndex` to track, per worked value on each of the five axes, *which
  bands* it has been worked on — not just whether it has been worked at all — and requires
  `AdifReader` to additionally parse each ADIF record's `<band:N>` tag (today it deliberately
  reads only `<call:N>`) and keep the (value, band) pairing per historical record.
- **"Current active band"** is resolved via the same live-CAT-aware three-tier rule
  (`WebApp.ResolveEffectiveFrequency`) already used elsewhere in this codebase for dial
  frequency, mapped through the same `AdifLogWriter.DeriveBand`-style frequency→band-name table.
- Explicitly **out of scope**: IARU Region (no data source exists in `cty.plist`; would need a
  separately-curated table) and Grid Square (exchanged in message content, not a static callsign
  property — structurally unlike the other five axes). Both deferred to a possible future change,
  not abandoned.
- Explicitly **out of scope for this change**: any GUI filtering/opt-out mechanism on
  `#decodes-panel`, and any change to `QsoAnswererService`/`QsoCallerService` automation
  behaviour. Both are covered by the dependent follow-on change `decode-panel-filtering`, which
  requires this change's tri-state/band-tracking data model to exist first.

## Capabilities

### New Capabilities

(none — this change modifies existing capabilities only)

### Modified Capabilities

- `qso-confirmation`: `WorkedBeforeIndex`/`WorkedBeforeInfo` grow from 3 boolean dimensions to 5,
  each becoming a tri-state (band-aware) value instead of a plain boolean; `AdifReader` widens to
  parse `<band:N>` per ADIF record, in addition to the existing `<call:N>` extraction, and to
  resolve CQ Zone/ITU Zone via `ICallsignRegionStore` alongside the existing entity/continent
  resolution.
- `web-frontend`: the three existing decode-table worked-before columns are renamed
  (Ctc/DXCC/Cnt) and two new columns added (CQz/ITz); the rendering logic for all five moves from
  a binary checkmark/empty glyph to a three-state glyph reflecting never-worked /
  worked-different-band / worked-this-band. Additionally (folded in mid-implementation at the
  Captain's request, task 8): a new **Band** column is inserted between Time and dB, showing the
  session's current active band for that decode — reuses this change's existing `currentBand`
  resolution, no new backend logic.

## Impact

- **Backend**: `src/OpenWSFZ.Abstractions/WorkedBeforeInfo.cs` (3 booleans → 5 tri-state values),
  `src/OpenWSFZ.Abstractions/IWorkedBeforeIndex.cs` (interface shape follows the data model
  change), `src/OpenWSFZ.Daemon/WorkedBeforeIndex.cs` (flat `HashSet<T>` per dimension → per-value
  band-tracking for all five dimensions), `src/OpenWSFZ.Daemon/AdifReader.cs` (parse `<band:N>` in
  addition to `<call:N>`, preserve the per-record value/band pairing), `src/OpenWSFZ.Ft8/Ft8Decoder.cs`
  (CQ Zone/ITU Zone resolution alongside the existing entity/continent resolution in the
  worked-before attachment point), `src/OpenWSFZ.Daemon/AdifLogWriter.cs` (live-registration path
  extended to also register the QSO's band, not just the callsign).
- **Frontend**: `web/index.html` (`#decodes-table` column headers — 3 renamed, 2 added, 1 more
  inserted for Band, `colspan` updates), `web/js/main.js` (tri-state glyph rendering, replacing
  `makeWorkedBeforeCell`; Band cell rendering), `web/css/app.css` (styling for the new "worked,
  different band" glyph state; Band column width/alignment).
- **Band column (task 8)**: `src/OpenWSFZ.Abstractions/DecodeResult.cs` gains `string? Band = null`
  (appended last, no positional call-site breakage); `src/OpenWSFZ.Ft8/Ft8Decoder.cs` populates it
  from the same `currentBand` parameter already resolved for worked-before purposes.
- **Dependency, already satisfied**: this change relies on `ADIF.log`'s `BAND` field being
  trustworthy going forward, which required D-013 (merged `bbf9420`, PR #63, GitHub issue #62
  closed, 2026-07-09) — `QsoAnswererService`/`QsoCallerService` previously wrote a stale/wrong
  `BAND` whenever CAT was connected. D-013 landing first is why this change is buildable with
  integrity now.
- **No breaking changes to the WebSocket payload's other fields** — `workedBefore`'s shape
  changes (3 booleans → 5 tri-state values), which IS a breaking change to that specific field's
  contract; no other part of the decode-result payload is affected.
- **Follow-on dependency**: `decode-panel-filtering` (separate change, not yet proposed) depends
  on this change's tri-state data model existing before its filter-popup "worked-before" section
  and automation-gating logic can be built.
