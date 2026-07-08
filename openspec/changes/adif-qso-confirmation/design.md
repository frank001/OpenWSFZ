## Context

`adif-log` (see `openspec/specs/adif-log/spec.md`) writes one ADIF 3.x record per completed QSO
to `ADIF.log`, append-only, via `AdifLogWriter.AppendQsoAsync`. No component in this codebase
reads `ADIF.log` back — it is a write-only sink today. `region-lookup` (see
`openspec/specs/region-lookup/spec.md`) resolves a decoded callsign token's DXCC entity and
continent via `ICallsignRegionStore.TryGetRegion`, attached to the decode-result WebSocket
payload as `RegionInfo? Region` (`DecodeResult.cs`), rendered by the frontend as the table's
existing "Region" column (`openspec/specs/web-frontend/spec.md`, "Decode table — region column").

The Captain has replaced this repository's `ADIF.log` with their real personal log (826 lines,
757 distinct callsigns, genuine WSJT-X-format export) specifically to validate this feature
against live data. Confirmed by direct inspection: real-world ADIF records here carry `CALL`
and `GRIDSQUARE` but no `COUNTRY`/continent tag — there is no shortcut around resolving
country/continent from the callsign the same way live decodes already do.

Two explicit decisions from the Captain scope this design tightly:

- **Country vs Region are two independent, differently-grained checks**, not duplicates of each
  other or of the existing Region *display* column: Country = DXCC entity only (e.g. "Germany");
  Region = continent only (e.g. "EU").
- **Match scope is unbounded**: any prior QSO anywhere in `ADIF.log`'s full history counts, with
  no band/mode/date restriction.

## Goals / Non-Goals

**Goals:**
- Resolve, for every decode, three independent booleans — has this exact callsign, this DXCC
  entity, or this continent appeared anywhere in `ADIF.log` before — and deliver them on the
  existing decode-result WebSocket payload with no additional round-trip.
- Keep the worked-before index live for the running session: a QSO logged five minutes ago must
  be reflected on the very next decode of that station, without a daemon restart.
- Match the `region-lookup`/`adif-log` error-handling posture exactly: missing file, malformed
  lines, or any resolution failure degrade to "not worked before" (unchecked), never an error
  surfaced to the operator, and never a decode withheld from the UI.
- Render three new readonly checkbox columns on the existing decode table, positioned after the
  current Region column, using the existing per-row rendering path.

**Non-Goals:**
- No band- or mode-scoped matching (explicitly ruled out by the Captain — "any time, any
  band/mode").
- No new ADIF *writer* behaviour — `AdifLogWriter`'s record format and write triggers are
  unchanged.
- No general-purpose ADIF import/export tooling, no editing of `ADIF.log` from the GUI, no
  display of individual matched historical QSO details (date, band, etc.) — the checkboxes are a
  yes/no advisory signal only.
- No persistence of the worked-before index itself — it is rebuilt from `ADIF.log` at every
  daemon startup, matching `ICallsignRegionStore`'s load-at-startup convention.

## Decisions

### Decision 1 — New `qso-confirmation` capability, not folded into `adif-log`

A new capability directory (`openspec/specs/qso-confirmation/`) owns the ADIF *reader*, the
in-memory index, and the `workedBefore` payload field. `adif-log` is left as a pure writer
capability, unmodified.

**Rationale:** `adif-log`'s existing spec is entirely about *when and what* gets written on QSO
completion — a different lifecycle and a different set of scenarios than "resolve worked-before
state for an incoming decode." Bolting a reader/index/matching capability onto the writer's spec
would conflate two independently-testable concerns (write-on-complete vs read-and-index-at-
startup-and-on-write) under one capability, making both harder to reason about in isolation. The
new capability *depends on* `adif-log`'s file (same path, same format) and *depends on*
`region-lookup`'s `ICallsignRegionStore` for entity/continent resolution, but owns none of their
requirements.

**Alternative considered — extend `adif-log` with new requirements:** rejected; would mean a
single spec file covers both "what AdifLogWriter writes" and "how something else reads and
indexes what was written," which is a weaker separation than keeping the reader as its own
capability with its own Purpose statement.

### Decision 2 — A minimal, purpose-built ADIF reader, not a general parser

The reader only needs to extract `CALL` field values from ADIF 3.x tagged-field records
(`<call:N>VALUE`), tolerating the header block (`ADIF Export`, `<adif_ver:...>`, `<eoh>`) that
precedes the first record. It does not need to parse any other field, does not need to handle
ADIF's alternate (non-tagged) formats, and does not need to be a general-purpose ADIF library.

**Rationale:** the only downstream use is "which callsigns have been logged" — pulling every
`<call:N>` token via a simple case-insensitive tag scan is sufficient and keeps the parser small
and easy to reason about for malformed-input handling (Decision 4). A line that fails to yield a
`CALL` token is simply skipped, not treated as a fatal parse error for the whole file.

**Alternative considered — adopt or vendor a third-party ADIF library:** rejected as
disproportionate; this project has no other ADIF-parsing need, and a general library would bring
parsing surface (and failure modes) for dozens of fields this feature never reads.

### Decision 3 — Callsign matching reuses the frontend's existing portable-suffix rule, ported to the backend

`web/js/main.js` already has `tokenMatchesCallsign(token, callsign)` (exact match, or a
`callsign + "/"` prefix match, for CQ click-to-answer against portable suffixes like `PD2FZ/P`).
The Partner (P) check needs the same semantics server-side: a decode's primary callsign token is
"worked before" if it exactly matches a historically-logged `CALL`, OR if either side is a
portable-suffixed variant of the other's base callsign.

**Rationale:** using two different matching rules for the same conceptual "is this the same
station" question (one client-side for CQ-answering, one server-side for worked-before) would be
inconsistent and confusing to reconcile later. Porting the existing, already-tested rule is lower
risk than inventing a new one.

**Alternative considered — exact string match only:** rejected; a station identified as
`PD2FZ/P` today and logged as plain `PD2FZ` a year ago is very obviously "worked before" to a
human operator, and an exact-only match would under-report.

### Decision 4 — Unknown and synthetic entities/continents never match

Both the live-decode side and the historical-ADIF-log side run every resolved callsign through
`ICallsignRegionStore.TryGetRegion`. A `null` result (lookup miss) or a `Synthetic == true`
result is excluded from the Country/Region index and from Country/Region matching entirely —
never inserted into the worked-before sets, and never checked against them.

**Rationale:** two callsigns that both fail to resolve are not known to share a country or
continent — they're simply both unknown. Treating "Unknown" as a country of its own (so any two
unresolved prefixes would falsely co-match) would actively mislead the operator, which is worse
than under-reporting. Synthetic Q-prefix callsigns are R&R-study test traffic (NFR-021) with no
real-world DXCC meaning, and must not contaminate a real operator's worked-before state — this is
the same reasoning `region-lookup` already applies to keep synthetic traffic from being
misattributed to a real entity.

Note this only affects Country/Region matching. The Partner (P) check is a plain callsign string
comparison (Decision 3) and does not depend on region resolution at all — an unresolvable
callsign can still be flagged "worked before" on the Partner column even though it never
contributes to Country/Region.

### Decision 5 — In-memory index, built at startup, updated incrementally on new writes

`IWorkedBeforeIndex` (name illustrative; implementing developer may rename) loads once at daemon
startup by reading and parsing the full `ADIF.log` (same path-resolution logic `AdifLogWriter`
already uses — extract the shared path-resolution helper rather than duplicating it), producing
three in-memory sets: worked callsigns (uppercased, as logged), worked DXCC entities, worked
continents (the latter two built by running every distinct logged callsign through
`ICallsignRegionStore.TryGetRegion` once, per Decision 4). `AdifLogWriter.AppendQsoAsync`, on a
successful write, also registers the just-logged callsign into the same live index — so a QSO
logged mid-session is reflected on the next decode of that station without waiting for a
restart or a file re-read.

**Rationale:** mirrors `ICallsignRegionStore`'s existing load-once-then-serve-from-memory
pattern, which this codebase already trusts for a similarly-shaped read-mostly lookup table.
Re-parsing the whole file on every decode (hundreds of times a session) would be wasteful and
unnecessary; incremental registration on write is a small, targeted addition to
`AdifLogWriter`'s existing success path.

**Alternative considered — re-read and re-parse `ADIF.log` on every decode:** rejected;
unnecessary I/O and parsing cost on a hot-ish path (every ~15s decode cycle) for data that only
changes on a QSO completion, which is already a well-defined event with an existing hook point.

### Decision 6 — Payload shape mirrors `RegionInfo`'s pattern: one non-null advisory record per decode

Add `WorkedBeforeInfo? WorkedBefore` to `DecodeResult` (or, given the index degrades cleanly to
"nothing worked" rather than "unknown," a non-nullable `WorkedBeforeInfo` with all-false defaults
is also acceptable — left to the implementing developer, both render identically on the
frontend). Shape: three independent booleans, `Call`/`Country`/`Region`, attached inside
`Ft8Decoder.cs`'s existing native-result mapping loop, in the same try/catch-degrade-to-default
block style already used for `Region` resolution (lines ~308–327).

**Rationale:** consistency with the one existing precedent for "advisory, per-decode, resolved
server-side, delivered on the same payload" data in this codebase.

## Risks / Trade-offs

- **[Risk] A very large personal `ADIF.log` (multi-thousand QSOs, multi-year operators) makes
  startup parsing or the in-memory index noticeably slow or memory-heavy** → Mitigation: the
  Captain's real log is 826 lines/757 callsigns; even an order of magnitude larger (tens of
  thousands of lines) is trivial for a one-time startup parse and a handful of in-memory string
  sets. Flagged as a known, currently-non-blocking trade-off, same posture as `region-lookup`'s
  linear-scan risk in the F-006 design.
- **[Risk] Malformed or truncated `ADIF.log` (e.g. a line cut off mid-write by a crash, or a
  third-party logger's non-conforming export) causes the reader to misparse a `CALL` token or
  throw** → Mitigation: per-line try/parse with skip-and-warn on failure (Decision 2); a total
  parse failure (e.g. file unreadable) degrades to an empty index, not a startup failure — same
  posture as `CallsignRegionStore`'s malformed-file handling.
- **[Risk] Country/Region checks silently under-report if `callsign-regions.json` has partial
  coverage** (a known, accepted `region-lookup` non-goal) → Mitigation: this is inherent to
  reusing `ICallsignRegionStore` — not a new risk introduced by this change, and consistent with
  the existing Region *display* column already being subject to the same coverage gaps.
- **[Risk] Race between `AdifLogWriter` registering a new QSO into the index and a concurrent
  decode reading it** → Mitigation: the index's read/write surface needs simple thread-safety
  (e.g. `lock` around set mutation/lookup, or concurrent collections) — small data volumes make
  this a non-perf-sensitive correctness detail, not an optimisation problem.

## Migration Plan

1. Add the ADIF reader + `IWorkedBeforeIndex`/implementation in `OpenWSFZ.Daemon`, with unit
   tests against small hand-written fixture ADIF text (synthetic Q-prefix callsigns per NFR-021,
   never real third-party callsigns in committed fixtures).
2. Extract/share the ADIF path-resolution logic between `AdifLogWriter` and the new index (avoid
   duplicating `ResolveAdifPath`'s directory-join logic).
3. Wire startup load in `Program.cs` (DI registration, load-at-startup call).
4. Add the `WorkedBefore` field to `DecodeResult`, resolve it in `Ft8Decoder.cs` alongside the
   existing `Region` resolution.
5. Register newly-logged QSOs into the live index from `AdifLogWriter.AppendQsoAsync`'s success
   path.
6. Frontend: three new columns in `web/index.html`, rendering in `web/js/main.js`, narrow/
   right-most styling in `web/css/app.css`.
7. No data migration: `ADIF.log`'s on-disk format is completely unchanged — this change only adds
   a reader for a file that already exists and is already being written. An operator with no
   `ADIF.log` yet sees all three columns unchecked for every decode, which is correct (nothing
   worked before), not an error state.

### Decision 7 — P/C/R indicator is a readonly `<span>` glyph, not a disabled checkbox (post-review correction)

The initial implementation followed this design's original Open Question resolution
(`disabled` checkbox, `accent-color` styling). After manual review against the real dark theme,
the Captain found the disabled-checkbox state too washed-out to read at a glance while decodes
scroll past — exactly the risk the Open Question flagged, but the `accent-color` mitigation
proved insufficient in practice (most browsers suppress `accent-color` on `:disabled` controls
regardless, per the code comment already in `app.css`). The Captain's direction: replace the
checkbox with a plain `<span>` per cell — a green checkmark glyph (reusing the existing
`--color-success` token already used elsewhere for positive-state indicators, e.g. the Call-CQ
button) when the corresponding `workedBefore` boolean is `true`, and empty when `false`. No
`disabled` attribute is needed since a `<span>` has no interactive semantics to suppress in the
first place.

**Rationale:** a coloured glyph against the existing dark background reads at a glance during a
fast-moving session — the original goal of this feature — whereas a disabled form control's
suppressed styling actively works against that goal. A `<span>` is also simpler than a checkbox
plus disabling machinery for a value that was never meant to be interactive.

**Impact:** `web/js/main.js`'s `makeWorkedBeforeCell` renders a `<span>` (e.g. textContent `"✓"`
when true, empty string when false) instead of an `<input type="checkbox" disabled>`; `app.css`'s
checkbox-specific rules (`accent-color`, `cursor: default` on `input[type="checkbox"]`) are
replaced with a rule styling the checkmark glyph in `--color-success`. `web-frontend/spec.md`'s
requirement text and scenarios are updated accordingly (indicator span, not checkbox) — see the
spec delta for the corrected requirement.

## Open Questions

None remaining — the one open item (disabled-checkbox visual legibility) is resolved by
Decision 7 above.
- Exact TypeScript-less JSDoc typing and exact field-naming casing (`workedBefore` vs `worked_before`
  etc.) on the WebSocket payload are left to the implementing developer, following this codebase's
  existing `region`/camelCase convention.
