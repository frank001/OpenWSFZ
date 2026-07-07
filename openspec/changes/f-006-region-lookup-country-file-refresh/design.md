## Context

`region-lookup` (`f-002-callsign-structure-region-lookup`, archived 2026-07-04) added an advisory
continent/entity lookup for decoded callsigns, resolved via `ICallsignRegionStore` from
`callsign-regions.json`. Its seed data, `CallsignRegionDefaults.cs`, is a small, hand-picked,
~38-entry sample with CQ/ITU zone columns `null` throughout — a documented Non-Goal at the time.
GitHub issue #40 tracks sourcing real data instead; this change scopes and resolves that.

Primary-source research this session (direct `curl` against the live site, not training-data
recall) against `country-files.com`:

- **Licensing** (`country-files.com/copyright/`): an MIT-style permissive license — "Permission is
  hereby granted, free of charge... to use, copy, modify, merge, publish, distribute, sublicense,
  and/or sell copies of the Software... subject to: The above copyright notice and this permission
  notice shall be included in all copies or substantial portions of the Software." No royalty, no
  separate consent needed; only obligation is carrying the notice with any copy made.
- **Format** (`country-files.com/cty-dat-format/`): the classic `cty.dat` is fixed-column text —
  country name, CQ zone, ITU zone, 2-letter continent, lat/long, GMT offset, then a primary DXCC
  prefix followed by comma-separated alias prefixes terminated by `;`. Alias prefixes carry inline
  override syntax: `(#)` CQ zone override, `[#]` ITU zone override, `<lat/long>` override, `{cc}`
  continent override, `~#~` GMT-offset override, and a leading `=` flags an alias as an **exact
  full-callsign match** rather than a prefix block (this is where individual real callsigns like
  `=4U1VIC`, `=TO5M` live in the format). An **XML variant** of the same release exists carrying the
  same information in a structured, parseable form.
- **Release cadence**: irregular, event-driven off DXCC entity/prefix allocation changes (observed
  releases roughly every 1–3 weeks in the site's post history — 10, 26, 27, 29 June 2026 — not a
  fixed schedule).
- **NFR-021 (this project's privacy policy)**: no real/assignable third-party callsign may appear
  anywhere in version control; a violation is a merge-blocking defect. The country file's
  individual-callsign exception entries (the `=`-flagged aliases) are exactly such data. Separately,
  `callsign-regions.json` (like `frequencies.json`, `prop-modes.json`, `app.json`) already resolves
  to the platform user-data directory via `ConfigPathResolver` (`Program.cs`), never inside the git
  repository — confirmed by reading `Program.cs` directly this session. It is a local runtime
  working document, the same status as `ALL.TXT`/`ADIF.log`, not a committed artifact.
- **Correction (QA review, before merge)**: an earlier exploration session had already concluded
  that a GUI affordance was necessary for this change, specifically because
  `callsign-regions.json` is an operator-maintained working document — an operator has no other way
  to confirm a refresh happened, what it installed, or how a given callsign currently resolves.
  That decision was never captured in any committed artifact (not the proposal's GitHub issue
  thread, not this project's memory notes), and this design.md as first drafted regressed it,
  declaring "no GUI, deferred to fast-follow" as a Non-Goal instead. The Captain caught this before
  merge (fresh compile, cleared cache, no control found anywhere in the app) and selected the GUI
  scope in the new Decision below. Recorded here plainly so an uncaptured scope decision made in a
  prior session doesn't silently regress again.

## Goals / Non-Goals

**Goals:**
- Add a converter from country-files.com's XML release to this project's existing
  `CallsignRegionEntry` shape, ingesting prefix-block entries (with real CQ/ITU zone data) at full
  DXCC-entity coverage.
- Add an explicit, operator-triggered backend refresh operation that fetches the current release
  live, converts it, and installs it into the running daemon's `callsign-regions.json` without a
  restart.
- Keep `CallsignRegionDefaults.cs` (git-committed) as a small, safe, prefix-block-only fallback —
  optionally expanded with additional real prefix-block/entity/zone rows, never with individual
  callsigns.
- Preserve every existing `region-lookup` requirement/scenario unchanged; this change is additive.

**Non-Goals:**
- No full CRUD editing of individual region-table entries (view/add/edit/delete persisted
  per-row) — see Decision 6 for why this is out of scope even though a GUI ships in this change.
- No automatic/scheduled refresh — startup behaviour is unchanged; the network fetch only happens
  when explicitly triggered.
- No filtering of individual-callsign exception entries out of the *runtime* `callsign-regions.json`
  — per the Captain's explicit ruling this session, that file is a local working document outside
  VCS and may carry them unfiltered if the conversion includes them. (Filtering **is** required for
  `CallsignRegionDefaults.cs` specifically, since that file is git-committed — see Decision 2.)
- No ingestion of the individual-callsign exception list's finer semantics (e.g. contest-vs-DXCC
  dual attribution like `4U1VIC`). Only prefix-block rows are converted; exact-callsign rows are
  either dropped or passed through opaquely per Decision 2 — not specially interpreted.

## Decisions

### Decision 1 — Convert from the XML release, not the classic `cty.dat` text format

The XML variant carries the same data as `cty.dat` in element/attribute form, avoiding a
hand-written parser for `cty.dat`'s inline override syntax (`(#)`, `[#]`, `<lat/long>`, `{cc}`,
`~#~`) and its comma/semicolon continuation-line conventions. Lower implementation risk, easier to
unit test with small fixture XML documents.

**Alternative considered — parse classic `cty.dat`:** rejected for this change; more prior art in
the ham-radio tooling ecosystem, but strictly more parsing surface area (and more edge cases: a
malformed override token silently mis-parsing a zone is a worse failure mode than a missing XML
element, which a standard XML parser/schema-mismatch will surface loudly). Revisit only if the XML
release is ever discontinued.

### Addendum (implementation-time correction) — the real release mechanics

Verified live against `country-files.com` at implementation time (not the original design-time
session), correcting three assumptions baked into Decision 1 and Decision 5 below:

- There is no plain, directly-fetchable `cty.xml` resource. The XML variant is **`cty.plist`** — an
  Apple property-list file, which is itself well-formed XML (`<dict><key>ALIAS</key>
  <dict><key>Country</key><string>…</string>…</dict>…</dict>`) but ships with an external DOCTYPE
  reference to an Apple DTD URL. The converter MUST parse with `DtdProcessing.Ignore` and a `null`
  `XmlResolver` so no external DTD fetch is ever attempted.
- `cty.plist` ships **inside a ZIP archive** alongside `README.TXT`/`HISTORY.TXT`/`copyright.txt`,
  not as a bare file. `ICountryFileSource` therefore does one extra in-memory step — download the
  ZIP, extract the `cty.plist` entry, decode it to text — before handing XML text to
  `ICountryFileConverter`. This stays inside `ICountryFileSource`; `ICountryFileConverter`'s contract
  (pure XML-string → `IReadOnlyList<CallsignRegionEntry>`, no I/O) is unaffected, so Decision 5's
  fetch/convert split and its "fixture XML, no network" test strategy both still hold exactly as
  written.
- A stable, version-independent URL exists and always serves the current release, removing any need
  to scrape an index/RSS page to discover "the latest version":
  `https://www.country-files.com/cty/download/cty_plist.zip`. `ICountryFileSource`'s HTTP
  implementation fetches this fixed URL.
- The plist schema is flatter and simpler than `cty.dat`'s override-token syntax implied: it is one
  entry per alias (a prefix block **or** an exact callsign — never both), keyed by the alias string
  itself, each carrying its *already-resolved* `Country`/`CQZone`/`ITUZone`/`Continent` values (plus
  `Latitude`/`Longitude`/`GMTOffset`, not mapped to `CallsignRegionEntry`) and a plain
  `ExactCallsign` boolean — no `(#)`/`[#]`/`{cc}`/`~#~` override tokens to interpret at all, since
  they're pre-applied per-alias by the data producer. This makes the converter *simpler* than
  originally scoped, not harder: `prefixBlocksOnly` mode is just "skip entries where
  `ExactCallsign == true`"; the mapped entry is always `PrefixStart == PrefixEnd == alias` (a
  single-value range, matching the shape every existing `CallsignRegionDefaults` entry already uses).
- Licensing text pulled live from `copyright.txt` inside the ZIP matches design.md's Context section
  verbatim — the MIT-style permissive license conclusion is unchanged.

### Decision 2 — Two different data paths get two different privacy rules, driven by where each file lives

- `CallsignRegionDefaults.cs` is **git-committed** C# source. The conversion path used to
  (re)generate or expand it MUST discard any entry sourced from an exact-callsign (`=`-flagged)
  row — only prefix-block rows (`PrefixStart`/`PrefixEnd` covering a range, or a single prefix
  where `PrefixStart == PrefixEnd`) are eligible. This is enforced by a dedicated conversion mode/
  flag (e.g. `--prefix-blocks-only`) used specifically when producing content destined for this
  file, and by a regression test asserting no individual full-callsign-shaped entry appears in the
  committed defaults.
- The **runtime** `callsign-regions.json`, produced by the operator-triggered refresh operation,
  is never committed (confirmed structurally — see Context). It may include exact-callsign entries
  unfiltered if the conversion includes them; this change does not add filtering logic to that
  path, matching the Captain's explicit direction this session.

**Alternative considered — filter exact-callsign entries out of every conversion path uniformly:**
rejected as unnecessary complexity once it was confirmed the runtime file structurally never
reaches VCS; a single filter mode reserved for the one path that actually needs it (the committed
fallback) is simpler and matches the actual risk.

### Decision 3 — Operator-triggered refresh is a new REST endpoint, not a CLI flag or automatic timer

Following the existing pattern of other operator actions in this codebase (`POST
/api/v1/frequencies`, `POST /api/v1/prop-modes`, `POST /api/v1/tx/*` — see `WebApp.cs`), add `POST
/api/v1/region-data/refresh`. This makes the capability independently testable (curl/integration
test) without requiring a GUI, consistent with the UI-visibility rule (backend proven first, GUI
control follows as a fast-follow once this endpoint is stable). Rejected a CLI-only flag (would
require a daemon restart to invoke, defeating the "no restart needed" goal) and an automatic
background timer (Non-Goal — adds an always-on network dependency and an unpredictable staleness/
update-timing surface with no operator visibility into when a change might land).

### Decision 4 — `ICallsignRegionStore` gains a `SaveAsync`, mirroring `IFrequencyStore`

`CallsignRegionStore`'s existing `WriteAsync` (atomic write-to-temp-then-rename) is currently
private, called only from `LoadAsync`'s missing-file path. Add a public `SaveAsync(IReadOnlyList
<CallsignRegionEntry> entries, CancellationToken)` to `ICallsignRegionStore`/`CallsignRegionStore`
that reuses the same atomic-write logic and updates the in-memory `Entries` only after a successful
write — mirroring `IFrequencyStore.SaveAsync`'s existing contract exactly. The refresh endpoint
depends on this new method, not on any new store implementation.

### Decision 5 — Conversion and fetch are separate, independently-testable components

- `ICountryFileSource` (or similarly named): fetches the current release from country-files.com
  over HTTPS and returns XML text ready for `ICountryFileConverter`. Per the Addendum above, this
  includes an internal ZIP-download-and-extract step (the release ships as `cty_plist.zip`) — that
  detail is fully encapsulated inside the HTTP implementation, not part of the interface contract.
  Fakeable in tests (return canned fixture XML text) so no test depends on network access.
- `ICountryFileConverter` (or similarly named): pure function from XML bytes/document to
  `IReadOnlyList<CallsignRegionEntry>`, with a mode flag controlling whether exact-callsign rows are
  dropped (used for `CallsignRegionDefaults.cs` regeneration) or passed through (used for the
  runtime refresh path). Pure and synchronous — no I/O — trivially unit-testable with small
  hand-written fixture XML (using fictional Q-prefix/placeholder data per NFR-021, never real
  country-file content copied into a committed test fixture, to avoid the same VCS concern this
  design otherwise routes around).
- The refresh endpoint composes both: fetch → convert (exact-callsign rows passed through) → `
  ICallsignRegionStore.SaveAsync`.

**Alternative considered — a single monolithic "refresh" class doing fetch+parse+write:** rejected;
splitting fetch and convert makes both independently unit-testable and keeps the one component that
needs network access (`ICountryFileSource`) trivially fakeable.

### Decision 6 — GUI scope: status summary + refresh trigger + read-only lookup, not full CRUD editing

Per the Context correction above, the Captain, the developer, and QA discussed three tiers of GUI
investment for this change and the Captain selected the middle tier:

1. **Refresh button only** — rejected as too thin: an operator triggering a refresh with no
   visibility into whether it worked (how many entries, which release, did it fail) is barely
   better than no GUI at all.
2. **Status summary + refresh button** (entry count, last-refresh outcome/timestamp/release
   version) — **in scope**. Closes the "did it work" gap with a `GET
   /api/v1/region-data/status` endpoint mirrored by a small read-only panel.
3. **Read-only lookup tool** (type a callsign, see what it currently resolves to — entity,
   continent, CQ/ITU zone, or "no match") — **in scope**. `callsign-regions.json` after a real
   refresh is ~29,000 rows; an operator has no practical way to eyeball whether a specific prefix
   is covered correctly without a lookup tool, and this is also the natural diagnostic surface for
   "why did this callsign resolve to Unknown."
4. **Full view + add/edit/delete individual records, persisted** — explicitly **out of scope**,
   selected against for three independent reasons: (a) 29,013 entries after a real refresh is not
   a hand-editable table the way the 5–10-row Frequencies tab is; (b) `SaveAsync` is a whole-list
   atomic replace with no per-entry CRUD contract — building one is its own design surface; (c)
   enabling manual edits that must survive a future refresh would require a provenance/merge model
   (distinguishing operator-edited entries from country-file-sourced ones so a refresh doesn't
   silently discard an operator's correction) that is a separate change, not a GUI addition to this
   one. No provenance field, no per-entry endpoint, and no merge-on-refresh logic is added in this
   change.

**Alternative considered — defer all GUI to a fast-follow (the original "no GUI" Non-Goal):**
rejected on review. The nearest analogous feature in this exact codebase, the Frequencies tab (an
operator-editable list backed by its own REST endpoint — `web/settings.html` lines 521–547), was
never held to a "backend proven first, GUI is fast-follow" bar; there is no precedent in this
codebase for shipping an operator-facing backend capability with zero GUI reachability, and
`callsign-regions.json` specifically is described throughout this design as an "operator-maintained
working document" — a document nobody can view or refresh without the GUI this decision adds.

## Risks / Trade-offs

- **[Risk] country-files.com is unreachable or returns an unexpected/changed XML shape at refresh
  time** → Mitigation: the refresh endpoint SHALL leave the existing `callsign-regions.json`/
  in-memory `Entries` untouched on any fetch or parse failure (same "don't overwrite on failure"
  posture `CallsignRegionStore.LoadAsync` already uses for a malformed file), log a Warning, and
  return a clear error to the caller. No partial/corrupt overwrite.
- **[Risk] XML schema drifts in a future country-files.com release, breaking the converter
  silently (e.g. missing zone data parsed as a false `null` rather than erroring)** → Mitigation:
  converter validates required elements/attributes are present per entry and surfaces a count
  mismatch or parse exception rather than silently defaulting; refresh endpoint treats any
  converter exception as a failed refresh (previous data retained, per the risk above).
- **[Risk] Full DXCC-entity dataset is significantly larger than today's ~38 entries (a full
  prefix-block table is on the order of several thousand rows), and `CallsignRegionStore.
  TryGetRegion` is a linear scan** → Mitigation: acceptable for this change — a few thousand string-
  range comparisons per decoded token is not a hot-path performance concern at FT8's decode
  cadence (seconds between decode cycles, not per-sample). Flagged as a known trade-off, not
  blocking; an index (e.g. grouping by prefix length/first character) is a follow-up if profiling
  ever shows otherwise.
- **[Risk] Operator triggers a refresh mid-decode-cycle, causing `Entries` to change while a lookup
  is in flight** → Mitigation: `Entries` is already read via a `volatile` field reference in the
  existing implementation (whole-list swap, not in-place mutation), so an in-flight `TryGetRegion`
  call either sees the old list or the new one, never a torn/partial one. No new synchronization
  needed beyond what `SaveAsync` already provides by construction (assign-after-write, same pattern
  as `LoadAsync`).

### Addendum 2 (implementation-time correction) — SaveAsync must guarantee the synthetic entry

Discovered live during this change's own manual end-to-end verification (task 5.2, run against
the real country-files.com release): the pre-existing, unconditional `region-lookup` requirement
"Synthetic Q-prefix callsigns resolve to a distinct synthetic region" has no refresh carve-out, yet
a real country-file release naturally contains no `Q`-series entry (it isn't a real DXCC prefix).
A first-pass implementation that installed the converted release as-is therefore silently regressed
that requirement — `Q1ABC` resolved to `"Unknown"` instead of `"Synthetic (R&R Study)"` after a
live refresh, confirmed by an actual `POST /api/v1/region-data/refresh` run against the live release
(29,012 real entries converted; 0 of them synthetic).

Fix: `CallsignRegionStore.SaveAsync` now guarantees the synthetic entry survives *any* caller's
replacement list — if the supplied list contains no entry with `Synthetic == true`, the canonical
one is appended from `CallsignRegionDefaults.Entries` before writing. This is enforced at the store
layer (not the refresh endpoint) so the invariant holds for every current and future `SaveAsync`
caller, not just this one. Re-running the same live verification after the fix: 29,013 entries
active (29,012 real + 1 synthetic), `Q1ABC` correctly resolves to `"Synthetic (R&R Study)"`. The
refresh endpoint's `entryCount` response field reports `regionStore.Entries.Count` (the actual
post-save active count) rather than the converter's raw output count, so the two numbers can never
quietly disagree.

## Migration Plan

1. Add `ICountryFileSource`/`ICountryFileConverter` (and concrete implementations) as new,
   independently unit-tested components.
2. Add `ICallsignRegionStore.SaveAsync` and its `CallsignRegionStore` implementation (mirroring
   `IFrequencyStore.SaveAsync`); add a unit test confirming atomic write + in-memory update, and
   confirming a failed write leaves `Entries` unchanged.
3. Add `POST /api/v1/region-data/refresh` to `WebApp.cs`, composing fetch → convert → `SaveAsync`,
   with the failure-preserves-existing-data behaviour from the Risks section.
4. (Optional, additive) Regenerate/expand `CallsignRegionDefaults.cs` using the prefix-blocks-only
   conversion mode against a snapshot of the current release; add/keep a regression test asserting
   no exact-callsign-shaped entry is present in the committed defaults.
5. No data-migration risk: `callsign-regions.json`'s on-disk schema is unchanged (same
   `CallsignRegionEntry` shape); this change only affects how the file's *content* is produced, not
   its format. Rollback is a plain code revert; no schema downgrade needed. An operator who never
   triggers a refresh sees no behavioural change at all.

## Open Questions

- Should the refresh endpoint return summary statistics (e.g. entity/prefix-block counts converted,
  release version/date if present in the XML) so an operator can confirm what happened? Recommend
  yes, left to the implementing developer's judgement on exact response shape.
- Should `CallsignRegionDefaults.cs` actually be expanded in this change, or left exactly as today
  and only the refresh mechanism added? Both are consistent with the proposal; left to the
  implementing developer — expanding it is optional/additive, not required for the core capability
  to work (an operator can always refresh at first run to get full coverage immediately).
- Exact endpoint response/error shape and HTTP status codes for fetch-failure vs parse-failure vs
  success are left to the implementing developer, following existing conventions in `WebApp.cs`.
