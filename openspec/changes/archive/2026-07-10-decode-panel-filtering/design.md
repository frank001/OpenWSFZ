## Context

`#decodes-panel` renders every `DecodeResult` the daemon produces, each already carrying
`Region` (entity/continent/CQ-zone/ITU-zone, `region-lookup`) and `WorkedBefore` (five tri-state
dimensions, once `qso-confirmation-band-awareness` lands) on the same WebSocket payload —
sufficient raw data for both the display and the automation decision this change needs, without
any new field on `DecodeResult` itself. Separately, `QsoAnswererService` and `QsoCallerService`
each read `DecodeBatch` from their own dedicated server-side `Channel` (`Program.cs`'s decode
pump fan-out) — no coupling to the browser DOM at all, confirmed by direct inspection during this
feature's exploration. Any filtering that must affect automation, not just display, has to be
evaluated server-side, in a place both services can reach.

The codebase already has one precedent for "the same predicate logic must exist identically in
both the frontend and the backend, deliberately ported rather than shared at runtime" —
`qso-confirmation`'s Decision 3 (portable-suffix callsign matching, JS `tokenMatchesCallsign`
ported to C#). This change follows the same pattern rather than inventing a new one.

## Goals / Non-Goals

**Goals:**
- A daemon-owned, ephemeral (not persisted, resets on restart), shared (not per-browser-tab)
  filter state covering four attribute-allow-list dimensions (DXCC entity, Continent, CQ Zone,
  ITU Zone) and a worked-before tri-state selection across all five columns (Ctc/DXCC/Cnt/CQz/
  ITz) — the latter is meaningful on Ctc (dupe-hiding: "don't show me stations I've already
  worked on this band," a genuinely common contest/DX operating need) even though Ctc has no
  attribute-allow-list section (there is no small enumerable value-set for "which specific
  callsign" the way there is for continent or zone number).
- A single, shared filter-evaluation predicate, implemented once in C# and ported (not shared at
  runtime) to JS, so display filtering and automation-gating filtering can never silently drift
  apart from each other.
- `QsoAnswererService`/`QsoCallerService` consult this predicate at exactly one decision point
  each (per the proposal's narrowed scope — engagement time only, not continuous enforcement).
- Multi-tab consistency: changing the filter from one browser tab is reflected in every other
  connected tab's popup state and rendered table, via a WebSocket push, not just a REST
  read-on-demand.

**Non-Goals:**
- No persistence of filter state across a daemon restart (explicit — "not retained").
- No per-browser-tab/per-session-identity scoping (explicit — "the small addition," Captain's own
  words; this app has no existing notion of client identity to scope by, and building one is out
  of scope for this change).
- No attribute-allow-list section on the Ctc column (no enumerable value-set to select from).
- No continuous re-evaluation of the filter against an in-progress QSO (explicit — existing
  Abort/Stop controls cover that case).
- No IARU Region or Grid Square filter columns (both out of scope for the underlying
  `qso-confirmation-band-awareness` change this depends on).

## Decisions

### Decision 1 — Filter state shape

```csharp
public sealed record DecodeFilterState(
    HashSet<string>?            AllowedEntities   = null, // null = no restriction (all shown)
    HashSet<string>?            AllowedContinents = null,
    HashSet<int>?               AllowedCqZones    = null,
    HashSet<int>?               AllowedItuZones   = null,
    HashSet<WorkedBeforeState>? ContactStates     = null, // per-dimension worked-before selection
    HashSet<WorkedBeforeState>? CountryStates     = null,
    HashSet<WorkedBeforeState>? ContinentStates   = null,
    HashSet<WorkedBeforeState>? CqZoneStates      = null,
    HashSet<WorkedBeforeState>? ItuZoneStates     = null)
{
    public static readonly DecodeFilterState Unfiltered = new(); // all null = show everything
}
```

**Implementation note (deviation from the type originally sketched here):** the axes are
`HashSet<T>?`, not `IReadOnlySet<T>?` — `System.Text.Json`'s source generator cannot deserialise
an interface-typed collection (`IReadOnlySet<T>` has no public constructor/factory it can target
at read time), and `DecodeFilterState` must round-trip through both the REST endpoint and the
`decodeFilterChanged` WebSocket payload. The null-vs-empty-set semantics below are unaffected —
this is a wire-format implementation detail, not a behavioural change.

`null` (not an empty set) means "no restriction on this axis" — the default, all-selected state.
An empty, non-null set would mean "nothing passes this axis," which is a valid state an operator
could reach by unchecking everything in a popup, distinct from "this axis was never touched."

**Rationale:** nullable-set-per-axis directly represents "untouched/no filter" vs. "actively
narrowed to this subset" without a separate boolean-per-axis flag, and composes simply — a value
passes an axis if that axis's set is `null` or contains the value.

**Alternative considered — a single opaque "filter expression" object (e.g. a small predicate
tree):** rejected as needless generality; the filter shape here is fixed and small (nine
independent, always-AND'd axes), not an open-ended query language the operator builds.

### Decision 2 — Single shared predicate, ported not shared, mirroring `qso-confirmation` precedent

```csharp
public static class DecodeFilterEvaluator
{
    public static bool IsVisible(DecodeResult decode, DecodeFilterState filter);
}
```

A decode is visible/engageable if it passes every active (non-null) axis in `filter`. An
unresolved/`null` attribute value (e.g. `Region: null`, or a `WorkedBefore` sub-field absent)
SHALL NOT be excluded by an active attribute-allow-list filter on that axis — fails open, same
advisory posture as every other degrade-gracefully rule in this feature family (never silently
hide a decode because metadata failed to resolve). The worked-before axes default to `Never`
when `WorkedBefore` is absent, which participates normally in a `ContactStates`-style filter
exactly like a resolved `Never`.

`QsoAnswererService`/`QsoCallerService` call `DecodeFilterEvaluator.IsVisible` directly (C#, same
assembly graph) at their one engagement-decision point each. `web/js/main.js` gets a hand-ported
JS twin, `isDecodeVisible(decode, filterState)`, structurally identical, exercised against the
same payload shape the decode already carries.

**Rationale:** matches the one existing precedent in this codebase for "the same station-matching
logic must exist in two languages, kept consistent by disciplined 1:1 porting rather than a
shared runtime" (`qso-confirmation` Decision 3). A shared filter-evaluation library across
C#/JS isn't practical in this stack; porting with a clear, small, testable predicate and tests on
both sides is the established mitigation for the "kept in two places" risk, not new risk this
change introduces.

**Alternative considered — server attaches a computed `filteredOut: bool` to every decode
payload, frontend just reads it, no JS-side predicate at all:** rejected. This would mean a
filter change doesn't take effect for already-delivered rows still in the table without a
re-render trigger from the server, and doesn't remove the need for the JS-side predicate anyway
for *future* rows unless every payload recomputes against the very latest filter — which is fine
for newly-arriving decodes but leaves already-rendered rows stale until their own next update.
Client-side evaluation against a pushed filter-state object (Decision 3) re-evaluates the whole
visible table immediately on a filter change, which is the more correct interactive behaviour.

### Decision 3 — Filter state is daemon-owned, in-memory, broadcast on change

A new `IDecodeFilterStore` singleton (analogous in spirit to `IConfigStore` but explicitly
**not** persisted — no `SaveAsync`-to-disk, no JSON file involvement) holds the current
`DecodeFilterState`. `GET /api/v1/decode-filter` reads it; `POST /api/v1/decode-filter` replaces
it (whole-object replace, not partial-patch — matches this codebase's existing `POST
/api/v1/config` whole-object-replace convention rather than inventing PATCH semantics
new to this API surface) and pushes a new WebSocket event (`decodeFilterChanged`, carrying the
new `DecodeFilterState`) to all connected clients, so every open tab's popup and rendered table
update immediately — this is what makes "last tab wins" actually *visible* to the other tabs,
not just true in the background.

**Rationale:** direct implementation of the proposal's "small addition" instruction — reuses the
existing WebSocket broadcast mechanism (`WebSocketHub`) and the existing whole-object-POST
convention, no new persistence machinery, no new client-identity concept.

### Decision 4 — Column-header popup UI

Clicking a DXCC/Cnt/CQz/ITz header opens a popup with two sections (attribute allow-list +
worked-before tri-state); clicking the Ctc header opens a popup with only the worked-before
section. Populating the attribute allow-list's candidate values (e.g. "which DXCC entities to
offer as checkboxes") uses the values seen in the currently-rendered/recently-decoded rows, not a
static enumeration of all ~340 DXCC entities or all 40 CQ zones — offering checkboxes for values
that have never appeared in this session would be visually overwhelming and not actionable
("filter out Antarctica" when nothing from Antarctica has ever been decoded this session is not
useful). Left to the implementing developer: exact windowing (e.g. "values seen in the current
table" vs. "values seen this session, including scrolled-off rows" — the latter requires the
frontend to track distinct-values-seen independently of the capped/trimmed row list).

**Rationale:** directly serves the "which values am I willing to see at all" framing from the
exploration — showing every theoretically-possible value regardless of relevance would make the
popup unusable, not just large.

## Risks / Trade-offs

- **[Risk] JS/C# predicate drift** (Decision 2's accepted trade-off, not eliminated) →
  Mitigation: mirrored unit tests on both sides against the same set of representative
  `(decode, filterState) → visible` cases, reviewed together whenever either side changes — same
  mitigation posture already accepted for `tokenMatchesCallsign`/`MatchesCallsign`.
- **[Risk] Filter changes mid-batch — a CQ evaluated as visible by the frontend a moment before
  the operator changes the filter could still be engaged by the backend on the same or a very
  close decode cycle** → Mitigation: accepted, matches the proposal's explicit non-goal (not
  continuously enforced, no strictness guarantee once a QSO is engaging) — this is a race that
  exists by design, not an oversight; the operator's Abort control is the backstop.
- **[Risk] Attribute allow-list candidate population (Decision 4) could differ between what the
  operator sees offered in the popup and what actually varies in the underlying data if
  windowing is chosen naively** → Mitigation: flagged explicitly for the implementing developer
  to make a deliberate choice, not an accidental one; not blocking, since either reasonable
  choice (current-table vs. session-seen) is defensible and correctness doesn't depend on which.

## Migration Plan

1. `DecodeFilterState` record + `DecodeFilterEvaluator.IsVisible` (C#), with unit tests covering
   each axis independently and in combination, plus the fail-open-on-unresolved-value rule.
2. `IDecodeFilterStore` singleton + `GET`/`POST /api/v1/decode-filter` + `decodeFilterChanged`
   WebSocket event.
3. `QsoAnswererService`/`QsoCallerService`: inject `IDecodeFilterStore`, call
   `DecodeFilterEvaluator.IsVisible` at the one engagement-decision point each (skip-and-continue-
   scanning on a filtered-out candidate, per the proposal's exact scope).
4. Frontend: clickable column headers, popup UI (two-section for DXCC/Cnt/CQz/ITz, one-section
   for Ctc), `isDecodeVisible` JS port, row-hide-on-render plus re-evaluation of already-rendered
   rows on `decodeFilterChanged`.
5. No data migration — purely new, in-memory, additive state and API surface.

## Open Questions

None outstanding at design time. Windowing choice for attribute-allow-list candidate population
(Decision 4) is intentionally left to the implementing developer as a judgement call, not a
blocking unknown.
