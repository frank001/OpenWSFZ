## Why

The `region-lookup` capability's seed data (`CallsignRegionDefaults.cs`) is a small, hand-curated,
deliberately partial sample (~38 prefix-block entries) explicitly modelled on the `cty.dat`-style
convention but never actually sourced from a real country file — a documented Non-Goal of
`f-002-callsign-structure-region-lookup`. CQ/ITU zone columns are `null` throughout, and most
DXCC entities are entirely unrepresented, so most decoded callsigns resolve to `"Unknown"` rather
than a useful continent/entity label. Real, actively-maintained country-file data (country-files.com,
maintained by Jim Reisert AD1C — the de facto standard amateur-radio "country file" format) exists
and is redistributable under an MIT-style license (verified directly against
`country-files.com/copyright/` this session). Sourcing from it gives operators full DXCC entity and
CQ/ITU zone coverage instead of a sparse sample. Raised as GitHub issue #40; this proposal resolves
its three open questions (licensing, vendor-vs-fetch, format conversion) and scopes the work.

## What Changes

- Add a conversion component that parses country-files.com's **XML** country-file release (chosen
  over the classic fixed-column `cty.dat` text format specifically to avoid hand-writing a parser
  for its inline override syntax — `(#)`, `[#]`, `<lat/long>`, `{cc}`, `~#~`, and the `=`-prefixed
  exact-callsign flag) and maps its **prefix-block entries** into this project's existing
  `CallsignRegionEntry` shape (`PrefixStart`, `PrefixEnd`, `Entity`, `Continent`, `CqZone`,
  `ItuZone`).
- Add a new, explicitly operator-triggered **"refresh region data"** backend operation that fetches
  the current XML release live from country-files.com on request, converts it, and overwrites the
  runtime `callsign-regions.json` via the existing `CallsignRegionStore` write path. This is **not**
  automatic on daemon startup — ordinary startup gains no new hard network dependency or failure
  mode.
- `CallsignRegionDefaults.cs` (the small, git-committed, compiled-in fallback used only when
  `callsign-regions.json` is absent) may be modestly expanded using real prefix-block/entity/zone
  data from the same source, but **never** with individual-callsign exception rows (see NFR-021
  note below) — it remains prefix-block-only, exactly as today.
- A "Region data" settings-page tab ships in this change: a status summary (entry count, last
  refresh outcome/timestamp/release version), a "Refresh region data" button, and a read-only
  callsign lookup tool (diagnostic — resolves entity/continent/CQ/ITU zone for a typed callsign,
  same matching logic the decoder uses). Per this project's UI-visibility rule (controls only
  appear once their backend is fully implemented and testable end-to-end), this GUI ships alongside
  the now-proven backend rather than in a separate change. Full per-entry CRUD editing of
  individual region-table rows remains out of scope — see design.md's GUI-scope decision for why.
- **Not a privacy exception**: `callsign-regions.json` — like `frequencies.json`, `prop-modes.json`,
  and `app.json` — already resolves to the platform user-data directory via `ConfigPathResolver`
  (`Program.cs`), not anywhere inside the git repository. It has never been VCS-committed. The
  refreshed runtime file may therefore carry the country file's individual-callsign exception
  entries (e.g. `=4U1VIC`) unfiltered if the conversion includes them — it is a local working
  document, the same status as `ALL.TXT`/`ADIF.log`, not a committed artifact. NFR-021 (no real
  third-party callsigns in version control) is therefore satisfied structurally, not by a new
  filtering step, and this change does not add one for that file. The one hard constraint this
  change does enforce: `CallsignRegionDefaults.cs`, which **is** git-committed, must never contain
  or be regenerated from those individual-callsign rows.

## Capabilities

### New Capabilities

- `region-lookup-data-refresh`: an operator-triggered backend operation that fetches, converts, and
  installs a fresh, real DXCC-entity/CQ/ITU-zone country-file dataset into the running daemon's
  `callsign-regions.json`, on demand, without restarting the daemon or affecting decode
  accept/reject behaviour.

### Modified Capabilities

- `region-lookup`: `CallsignRegionDefaults.cs`'s committed seed data may gain additional real
  prefix-block/entity/CQ/ITU-zone entries (still prefix-block-only, still excluding individual
  callsigns) — an additive data-coverage change, not a behavioural one; no existing requirement's
  contract changes. Included here for traceability since the seed-data content is part of what
  `region-lookup`'s "Missing configuration file creates a default file with seed data" scenario
  depends on.

## Impact

- **New code**: an XML country-file parser/converter (new project or module under
  `src/OpenWSFZ.Daemon/` or a new `src/OpenWSFZ.CountryFileConversion/`-style component — left to
  design.md/the implementing developer), and a new refresh-operation entry point (e.g. a daemon
  admin/CLI hook or internal API — left to design.md).
- **Modified**: `src/OpenWSFZ.Daemon/CallsignRegionDefaults.cs` (optionally, additive real data).
- **Unaffected**: `ICallsignRegionStore`/`CallsignRegionStore`'s existing load/write/lookup
  contract, `Ft8Decoder`'s callsign-structure-validation path, the decode-result payload shape, and
  every existing `region-lookup` requirement/scenario (this change is purely a data-sourcing and
  refresh-mechanism addition on top of the existing store).
- **Dependencies**: outbound HTTPS fetch to `country-files.com` at the time of an operator-triggered
  refresh only (no new always-on dependency).
- **Third-party data**: country-files.com data used under its published MIT-style permissive
  license (`country-files.com/copyright/`); attribution is good practice (e.g. a log line noting
  the source and release version) but not a hard gate for this operator-pull flow, since nothing is
  redistributed through this project's own repository or build artifacts.
