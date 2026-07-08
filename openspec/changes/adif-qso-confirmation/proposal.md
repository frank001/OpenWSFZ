## Why

The operator currently has no visual cue, while decodes are scrolling past, of whether a
calling station (or its country/continent) has already been worked. That judgement today
requires manually cross-referencing the callsign against a separately-opened ADIF log —
impractical during a live, fast-moving FT8 session where a decision to answer a CQ must be
made within seconds. Since the daemon already writes every confirmed QSO to `ADIF.log`
(`adif-log` capability) and already resolves each decode's country/continent for display
(`region-lookup` capability), the data needed to answer "have I worked this before?" already
exists in the system — it is not currently cross-referenced or surfaced.

## What Changes

- Add a new **`qso-confirmation`** capability: the daemon builds an in-memory index of every
  distinct callsign ever logged to `ADIF.log` (parsed at startup, kept live as new QSOs are
  appended during the session), resolves each logged callsign's DXCC entity ("country") and
  continent ("region") via the existing `ICallsignRegionStore`, and attaches a `workedBefore`
  field (`call`/`country`/`region`, each an independent boolean) to every decode-result payload
  delivered over the existing WebSocket decode channel — mirroring exactly how the `region-lookup`
  capability already attaches its `region` field, with the same fully-advisory,
  never-affects-decode-acceptance guarantee.
- Extend the `web-frontend` capability: three new readonly checkbox columns — **P** (Partner),
  **C** (Country), **R** (Region) — appear in `#decodes-table`, immediately after the existing
  Region column, populated directly from the decode payload's new `workedBefore` field with no
  separate network round-trip.
- **Match semantics** (explicitly confirmed by the Captain): "worked before" means *anywhere* in
  the whole `ADIF.log` history — any band, any mode, no time bound. Country and Region are two
  independent, differently-grained checks against the same underlying entity/continent lookup:
  Country is DXCC-entity-only (e.g. "Germany"); Region is continent-only (e.g. "EU") and is
  therefore strictly coarser and will tend to check more readily than Country.
- Unresolved ("Unknown") or synthetic (NFR-021, R&R-study `Q`-prefix) entities/continents never
  count as a match on either side of the comparison — two different unrecognised or synthetic
  callsigns must never falsely appear as "worked before" against each other.

## Capabilities

### New Capabilities

- `qso-confirmation`: parses `ADIF.log` into an in-memory worked-before index (callsign, DXCC
  entity, continent), keeps it live as new QSOs are logged during the session, and attaches a
  `workedBefore` advisory field to every decode-result payload.

### Modified Capabilities

- `web-frontend`: `#decodes-table` gains three new readonly checkbox columns (P/C/R) after the
  existing Region column, rendered from the new `workedBefore` payload field.

## Impact

- **Backend**: `src/OpenWSFZ.Abstractions/DecodeResult.cs` (new field), a new
  `IWorkedBeforeIndex`/implementation in `OpenWSFZ.Daemon` (new ADIF reader — no ADIF parser
  exists in the codebase today, only the writer in `AdifLogWriter.cs`), `Ft8Decoder.cs` (attach
  the field alongside the existing `Region` resolution), `AdifLogWriter.cs` (register newly-logged
  QSOs into the live index), `Program.cs` (DI registration, startup load).
- **Frontend**: `web/index.html` (`#decodes-table` markup, placeholder-row `colspan`),
  `web/js/main.js` (`handleDecodes()` cell rendering), `web/css/app.css` (narrow, right-most
  checkbox columns).
- **No breaking changes**: purely additive payload field and additive table columns; existing
  consumers of the decode payload and existing table columns are unaffected.
