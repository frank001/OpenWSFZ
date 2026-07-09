## Context

`qso-confirmation` (archived 2026-07-09) resolves three independent booleans per decode —
Partner/Country/Region worked-before — from an in-memory index built by `AdifReader` (which
today deliberately reads only `<call:N>` tags, per its original design's minimal-parser
decision) and kept live via `AdifLogWriter.AppendQsoAsync`'s success path. `RegionInfo` (the
`region-lookup` capability) already resolves `CqZone`/`ItuZone` on every decode, sourced from
`cty.plist`, but `WorkedBeforeIndex` doesn't track either dimension yet. `WorkedBeforeInfo.Region`
is a plain boolean covering "continent worked, ever" — no band awareness anywhere in this
capability.

Separately, D-013 (merged `bbf9420`, PR #63, 2026-07-09) fixed `QsoAnswererService`/
`QsoCallerService` writing a stale/wrong `BAND` to `ADIF.log` whenever CAT was connected. This
change was explicitly gated on that fix landing — band data in `ADIF.log` was not trustworthy
before it.

## Goals / Non-Goals

**Goals:**
- Extend `WorkedBeforeIndex` to track, per worked value on all five axes (callsign, DXCC entity,
  continent, CQ zone, ITU zone), *which bands* that value has been worked on — not just whether
  it has been worked at all.
- Resolve each of the five worked-before dimensions as one of three states — never worked,
  worked on a different band than the session's current active band, or worked on the current
  band — for every decode, with no additional network round-trip.
- Rename the three existing dimensions (Partner→Contact, Country→Country [unchanged],
  Region→Continent) to resolve a naming collision with the pre-existing Region *display* column
  (`region-lookup` capability), and add CQ Zone/ITU Zone as two new dimensions.
- Preserve the capability's existing advisory-only guarantee: any resolution failure (missing
  file, malformed line, missing/unresolvable band, lookup miss) degrades gracefully — a
  worked-before dimension resolves to "never" rather than throwing or withholding a decode.

**Non-Goals:**
- No GUI filtering/opt-out mechanism (`decode-panel-filtering`, a separate dependent change).
- No changes to `QsoAnswererService`/`QsoCallerService` automation behaviour (also
  `decode-panel-filtering`).
- No IARU Region or Grid Square dimensions (no data source for the former; structurally
  message-content-derived, not a callsign property, for the latter — both explicitly deferred).
- No change to `AdifLogWriter`'s ADIF record *format* — `BAND` is already written correctly
  (D-013); this change only adds a *reader* for band data that already exists in the file.

## Decisions

### Decision 1 — `WorkedBeforeState` enum replaces `bool` for all five dimensions

```csharp
public enum WorkedBeforeState
{
    Never,          // never worked on this axis, any band
    DifferentBand,  // worked on this axis, but not on the session's current active band
    ThisBand,       // worked on this axis, on the session's current active band
}

public sealed record WorkedBeforeInfo(
    WorkedBeforeState Contact,
    WorkedBeforeState Country,
    WorkedBeforeState Continent,
    WorkedBeforeState CqZone,
    WorkedBeforeState ItuZone)
{
    public static readonly WorkedBeforeInfo None = new(
        WorkedBeforeState.Never, WorkedBeforeState.Never, WorkedBeforeState.Never,
        WorkedBeforeState.Never, WorkedBeforeState.Never);
}
```

**Rationale:** a three-way enum is the direct, explicit representation of the three-way UI
distinction — cheaper to reason about at every layer (index, payload, rendering) than
reconstructing "different band" from two separate booleans (`workedAnyBand && !workedThisBand`)
at render time, which risks the two facts drifting inconsistently if computed in more than one
place.

**Alternative considered — keep booleans, add a parallel `bool workedThisBand` per axis:**
rejected; doubles the payload's field count for no representational benefit over a single
three-valued field, and invites exactly the "computed in two places, could disagree" risk above.

**Serialization:** follow this codebase's existing camelCase/string-enum convention for JSON
payload fields (see `RegionInfo`/existing `workedBefore` precedent) — exact casing left to the
implementing developer, consistent with `adif-qso-confirmation`'s original design.md leaving the
same latitude.

### Decision 2 — `WorkedBeforeIndex` moves from flat `HashSet<T>` to per-value band-tracking

Each of the five dimensions' index moves from `HashSet<string>`/`HashSet<int>` ("have I worked
this value, ever") to `Dictionary<TValue, HashSet<string>>` (value → set of band names worked
on). A value with an empty band set cannot occur — a value only enters the dictionary when at
least one historical QSO contributes it, and always with at least one band (or the sentinel
below).

**Sentinel for unknown/missing band:** a historical ADIF record may have no parseable `<band:N>`
tag (a truncated line, or a pre-D-013 record written while `DecodeLogConfig.DialFrequencyMHz`
was `0.0`, which never got `BAND` written at all — see `AdifLogWriter.BuildAdifRecord`'s
`DialFrequencyMHz != 0.0` guard). Such a record still contributes its callsign/entity/continent/
zone to the "worked, ever" fact (so `WorkedBeforeState.Never` is correctly avoided), but
contributes to no specific band, and therefore can never make `WorkedBeforeState.ThisBand` true
on its own — the value can only ever resolve to `DifferentBand` at best from that record, even
if the session's current band happens to coincidentally match nothing (there's nothing to match
against). This is a deliberate under-report, not a defect: claiming "worked on this exact band"
from a record with no known band would be fabricating information the source data doesn't have.

**Rationale:** this is the minimal structural change that supports the tri-state resolution —
"is this value present at all" (→ not `Never`) and "is the current band in its band-set" (→
`ThisBand` vs `DifferentBand`) are both O(1)/O(band-set-size) lookups against this shape, no
behavioural change to the existing Unknown/synthetic-exclusion posture (Decision 4 of the
original `qso-confirmation` design, unchanged and still honoured — Unknown/synthetic entries are
excluded from insertion into any of the five dictionaries, exactly as before).

**Alternative considered — store `(value, band)` tuples in a single flat set per dimension, no
dictionary:** rejected; a "is any band worked for this value" query would require a linear scan
in the worst case (or a second parallel flat set duplicating "worked ever" — which was rejected
for the same reason as Decision 1's alternative). The dictionary shape gets both queries directly.

### Decision 3 — `AdifReader` widens to parse `<band:N>` per record, preserving the pairing

`AdifReader.ReadCallsigns(path) : IReadOnlyList<string>` is replaced (or accompanied — the
implementing developer's call, but not both indefinitely; avoid two divergent read paths over
the same file) by a method returning one entry per record with both fields, e.g.:

```csharp
internal readonly record struct AdifLogEntry(string Call, string? Band);
internal static IReadOnlyList<AdifLogEntry> ReadEntries(string path, ILogger? logger = null);
```

Per-line parsing extends to also scan for a `<band:N>` tag on the same line as (or same record
as) a matched `<call:N>` tag — reuse the exact `<tag:N>VALUE` extraction logic already proven for
`CALL` (a second `Regex`/positional-length parse, not a new parsing strategy). A record with a
parseable `CALL` but no parseable `BAND` yields `AdifLogEntry(Call, Band: null)` — not a skipped
record; only a genuinely unparseable `CALL` remains a skip condition (unchanged from today).

**Rationale:** the original minimal-parser design (`adif-qso-confirmation` design.md Decision 2 —
"only needs to extract CALL field values... does not need to parse any other field") is
extended by exactly one field, not abandoned — still not a general-purpose ADIF library, still a
simple per-line tagged-field scan, still degrades a malformed line to "skip, log a Warning" for
the fields it can't parse rather than failing the whole file.

**Alternative considered — adopt a general ADIF parsing library at this point, now that two
fields are needed:** still rejected, same reasoning as the original decision — this capability
has no need for the other ~15 fields `AdifLogWriter` writes, and a general library brings parsing
surface for all of them.

### Decision 4 — "Current active band" resolution threads through `Ft8Decoder.DecodeAsync`

`Ft8Decoder.DecodeAsync` gains a new optional parameter, resolved once per decode cycle by the
existing decode pump (`Program.cs`) exactly where it already resolves `dialFreq` for `ALL.TXT`
(reusing `WebApp.ResolveEffectiveFrequency`, now trustworthy per D-013) and converted to a band
name via the same frequency→band-name table `AdifLogWriter.DeriveBand` already implements
(extract `DeriveBand` to a shared location — e.g. a small static helper both `AdifLogWriter` and
`Ft8Decoder`'s caller can reference — rather than duplicating the frequency-range table, mirroring
`adif-qso-confirmation`'s own precedent of extracting `AdifPathResolver` for the same reason).

```csharp
Task<IReadOnlyList<DecodeResult>> DecodeAsync(
    float[] pcm, DateTime cycleStart, string? currentBand = null, CancellationToken ct = default);
```

`IWorkedBeforeIndex.Resolve` gains the same parameter:

```csharp
WorkedBeforeInfo Resolve(string callsignToken, string? currentBand);
```

When `currentBand` is `null` (dial frequency unresolvable — no CAT, no manual fallback set, or
outside all known ham bands), every dimension that would otherwise resolve `ThisBand` instead
resolves `DifferentBand` (if worked at all) — the tri-state degrades to a binary distinction
gracefully, consistent with this capability's established advisory posture, rather than
guessing or throwing.

**Rationale:** mirrors the existing, already-proven pattern of per-cycle dial-frequency
resolution and threading (`CycleFramer`'s `DialFrequencyMHz` snapshot, `Program.cs`'s `dialFreq`
variable) — this is one more thing resolved at the same point in the same pipeline, not a new
architectural pattern.

**Alternative considered — resolve "current band" inside `WorkedBeforeIndex` itself, giving it
direct access to `ICatState`/`IConfigStore`:** rejected; `WorkedBeforeIndex` would need to
duplicate `ResolveEffectiveFrequency`'s tier logic or take on new dependencies it doesn't
otherwise need, and — more importantly — the *whole point* of D-013 was that resolving dial
frequency correctly is easy to get subtly wrong when done in more than one place. Passing the
already-correctly-resolved value in from the one place it's computed avoids reintroducing that
exact risk in a new location.

### Decision 5 — Live registration (`AdifLogWriter.AppendQsoAsync`) passes band, not just callsign

`IWorkedBeforeIndex.Register(string callsign)` becomes `Register(string callsign, string? band)`.
`AdifLogWriter.AppendQsoAsync` already computes `DeriveBand(record.DialFrequencyMHz)` for its own
`BAND` tag — pass that same already-computed value straight through, no new computation.

**Rationale:** trivial, direct consequence of Decision 2 — the live-update path must contribute
to the same per-value band-tracking the startup load path populates.

## Risks / Trade-offs

- **[Risk] Pre-D-013 historical records in an operator's real `ADIF.log` may have a wrong `BAND`
  (from the defect this change's prerequisite fixed), not just a missing one** → Mitigation: this
  is inherent and unfixable retroactively (D-013's own fix note: corrupted historical ADIF data
  can't be un-corrupted). A pre-existing wrong-band record will cause an incorrect `ThisBand` vs
  `DifferentBand` classification for that one historical contribution, indistinguishable from a
  correct one. Accepted, same posture as `region-lookup`'s accepted partial-coverage risk — not
  blocking, not silently hidden either; worth a one-line callout in the operator-facing behaviour
  if there's a natural place for it (e.g. a Settings-page note), left to the implementing
  developer's judgement.
- **[Risk] `AdifReader`'s widened parsing surface (two tags instead of one) roughly doubles its
  per-line regex/parse cost** → Mitigation: negligible at this data volume (hundreds to low
  thousands of historical lines, one-time startup parse) — same non-concern as the original
  design's "large ADIF.log" risk, unchanged order of magnitude.
- **[Risk] `Ft8Decoder.DecodeAsync`'s signature change ripples to every call site, including
  tests** → Mitigation: new parameter is optional (`= null`), degrading gracefully as described
  in Decision 4 — existing call sites and tests compile and behave identically (binary
  never/worked, no `ThisBand` distinction) without modification unless a test specifically wants
  to exercise the new behaviour.

## Migration Plan

1. `WorkedBeforeState` enum + `WorkedBeforeInfo` record shape change
   (`src/OpenWSFZ.Abstractions/`).
2. `AdifReader.ReadEntries` (widened parser) with unit tests against small hand-written fixture
   ADIF text (synthetic Q-prefix callsigns per NFR-021, mixing present/missing/malformed `BAND`
   tags).
3. `WorkedBeforeIndex` internal rework (dictionary-of-band-sets per dimension, five dimensions
   total including the two new CQ/ITU zone ones) + `Resolve`/`Register` signature changes.
4. Extract shared `DeriveBand`-equivalent helper; wire "current band" resolution into
   `Program.cs`'s decode pump alongside the existing `dialFreq` resolution.
5. `Ft8Decoder.DecodeAsync` new optional parameter, threaded to `_workedBeforeIndex.Resolve`.
6. `AdifLogWriter.AppendQsoAsync`'s live-registration call updated to pass band.
7. Frontend: column header rename (Ctc/DXCC/Cnt) + two new columns (CQz/ITz) in
   `web/index.html`; tri-state glyph rendering in `web/js/main.js` (`makeWorkedBeforeCell`
   becomes three-way, not two-way); new glyph state styling in `web/css/app.css`.
8. No data migration: `ADIF.log`'s on-disk format is unchanged (D-013 already ensured `BAND` is
   written correctly going forward) — this change only adds a *reader* for a field that already
   exists in the file.

## Open Questions

None outstanding — all prerequisite design questions (naming, tri-state vs. toggle vs.
per-dimension doubling, current-band resolution source) were resolved directly with the Captain
before this design was drafted.
