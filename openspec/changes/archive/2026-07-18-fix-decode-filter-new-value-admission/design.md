## Context

`decode-panel-filtering` (archived 2026-07-10) gives `#decodes-table` and the two QSO controller
services a shared, daemon-owned `DecodeFilterState`: four attribute allow-list axes (DXCC entity,
Continent, CQ Zone, ITU Zone) and five worked-before tri-state axes. `null` on an axis means "no
restriction"; a non-null array means "only these values pass."

The bug: `web/js/main.js` populates each attribute axis's popup checkboxes from a client-side
"seen this session" set that only ever grows as decodes render. The moment the operator unticks
one value, the change handler collapses the axis from `null` to `values.filter(checked)` — a
snapshot of *only what had been seen by that point*. Any attribute value that shows up afterward
and was never part of that snapshot — a genuinely new DXCC entity, continent, CQ zone, or ITU
zone — fails `DecodeFilterEvaluator.IsVisible`'s `Contains()` check and is silently excluded, both
from the table and from `QsoAnswererService`/`QsoCallerService`'s engagement decision, which read
the identical `DecodeFilterState` from `IDecodeFilterStore`.

A frontend-only fix (auto-grow the array client-side, then `POST` the correction) was considered
and rejected during exploration: this daemon can run fully headless via `daemon-background-mode`
(`--background`/`--background-worker`), with no browser tab ever open to notice a new value and
correct the state. The daemon itself must be authoritative for admission, so the fix applies
identically whether or not anything is watching.

## Goals / Non-Goals

**Goals:**
- A previously-unseen attribute value arriving on a *narrowed* axis (non-null, non-empty array)
  is auto-admitted into that axis's allow-list by the daemon itself, at decode time, before the
  same decode cycle's batch reaches `QsoAnswererService`/`QsoCallerService`.
- This applies identically whether a browser tab is attached or the daemon is running headless.
- Every connected client is notified of the daemon-driven admission via the existing
  `decodeFilterChanged` WebSocket event, so no tab's popup/table silently disagrees with what the
  daemon actually evaluated.
- `DecodeFilterState`'s wire shape and `DecodeFilterEvaluator.IsVisible`/`isDecodeVisible`'s
  predicate are unchanged — this is purely about what array is stored, not how it's evaluated.
- The existing, already-correct "an explicit empty selection (`[]`) filters everything on that
  axis" behavior (current spec, `decode-panel-filtering` Requirement 1, Scenario 2) is preserved
  exactly — an axis the operator has driven to fully empty (e.g. via "Select None") continues to
  block every value, including future new ones. Auto-admission only applies to a *narrowed but
  non-empty* array (some values excluded, not all).

**Non-Goals:**
- No change to the worked-before tri-state axes (Ctc/DXCC/Cnt/CQz/ITz) — their candidate set is a
  fixed 3-value enum, always fully offered, and cannot exhibit this snapshot problem. Verified,
  not re-fixed.
- No change to `DecodeFilterEvaluator.IsVisible` / `isDecodeVisible`'s predicate logic.
- No persistence of the daemon's "seen this session" tracking — it resets on restart, same
  ephemeral posture as `DecodeFilterState` itself.
- No frontend logic changes required for correctness (`web/js/main.js`'s own `seenEntities`/etc.
  sets remain, but only for populating popup checkbox candidates — a purely additive, harmless
  duplication of tracking that already existed before this change, now no longer load-bearing for
  correctness since the daemon is authoritative).

## Decisions

### Decision 1 — Admission lives on `IDecodeFilterStore`, not a separate service

Add one method to the existing interface:

```csharp
public interface IDecodeFilterStore
{
    DecodeFilterState Current { get; }
    void Set(DecodeFilterState state);

    /// <summary>
    /// Called once per newly-arrived <see cref="DecodeResult"/>. For each of the decode's
    /// resolved attribute values (DXCC entity, Continent, CQ Zone, ITU Zone) not yet observed
    /// this session: if the corresponding axis is currently narrowed (non-null AND non-empty
    /// allow-list), admits the value into that axis's allow-list. Always records the value as
    /// "seen" regardless of admission, for future popup candidate population.
    /// </summary>
    /// <returns>
    /// The updated <see cref="DecodeFilterState"/> if any axis actually changed, or
    /// <see langword="null"/> if nothing needed admitting (no state change, no broadcast
    /// required).
    /// </returns>
    DecodeFilterState? AdmitNewValues(DecodeResult decode);
}
```

**Rationale:** the store already owns `_current` and is the only thing that may safely mutate it
(single-writer discipline via its internal lock, Decision 3). Introducing a separate
"admission service" would need its own reference to the store anyway and adds an indirection with
no benefit — `DecodeFilterStore` is the natural, minimal home, mirroring how `Set` already lives
there for the POST-driven whole-object-replace path.

**Alternative considered — a free-standing `DecodeFilterAdmission` static helper (mirroring
`DecodeFilterEvaluator`'s naming), taking the store as a parameter:** rejected. Unlike
`DecodeFilterEvaluator.IsVisible` (a pure function ported 1:1 to JS), admission needs mutable,
session-lived "seen" state and must be exclusive with `Set()` — that's an object's job, not a
static function's.

### Decision 2 — Daemon-side "seen" tracking is new, internal state on `DecodeFilterStore`

`DecodeFilterStore` (the concrete `internal sealed` class in `OpenWSFZ.Web/WebApp.cs`) gains four
private `HashSet<T>` fields (entities seen, continents seen, CQ zones seen, ITU zones seen),
guarded by the same lock as `_current` (Decision 3). These mirror `main.js`'s
`seenEntities`/`seenContinents`/`seenCqZones`/`seenItuZones` but are authoritative and
independent of any browser connection.

**Rationale:** the frontend's existing "seen" tracking was always meant to answer "what's worth
offering as a checkbox," a UI concern; the daemon needs its own answer to "has this attribute
value ever been decided upon by the operator," a correctness concern, and the two must not be
conflated onto one piece of state owned by whichever browser tab happens to be open (or not open
at all, per this change's whole premise).

### Decision 3 — Copy-on-write under a lock, not in-place `HashSet` mutation

`AdmitNewValues` must not mutate the `HashSet<T>` instances referenced by `_current`'s allow-list
fields in place — `DecodeFilterEvaluator.IsVisible` and `isDecodeVisible`'s C#/JS `Contains()`
calls may be reading that exact same collection concurrently from `QsoAnswererService`/
`QsoCallerService` (each on their own channel-reader thread) or from a `GET
/api/v1/decode-filter` request thread. `HashSet<T>` is not thread-safe for concurrent
read-during-mutate.

Implementation: a private `readonly object _lock`; `AdmitNewValues` and `Set` both take it for
their full read-modify-write. Admission builds a **new** `HashSet<T>` (copy of the current set
plus the new value) and produces a new `DecodeFilterState` via `with`, then assigns
`_current = updated` — the same "replace the whole record" discipline `Set` already uses, just
computed instead of received wholesale from a POST body.

**Rationale:** this is the same category of risk the original design already accepted for
concurrent `Set()` calls from multiple browser tabs (last-write-wins, no corruption) — the lock
and copy-on-write extend that same safety net to the new writer, rather than introducing a new,
narrower race.

### Decision 4 — Hook point: the decode pump, before the QSO-controller fan-out

`src/OpenWSFZ.Daemon/Program.cs`'s decode pump (`await foreach` over `framerOutput.Reader`,
currently computing `visibleResults` and fanning out to `qsoAnswererChannel`/`qsoCallerChannel`/
`externalReportingChannel`) calls `decodeFilterStore.AdmitNewValues(r)` for each `r` in
`visibleResults`, **before** `qsoAnswererChannel.Writer.TryWrite(batch)` /
`qsoCallerChannel.Writer.TryWrite(batch)`. If any call returns a non-null updated state, the
daemon broadcasts once per batch (coalesced, not once per admitted value) via a new
`DecodeFilterEventBus.Publish(state)` — a thin façade over `WebSocketHub.BroadcastDecodeFilterChanged`,
constructed the same way as the existing `DecodeEventBus`/`CatEventBus`/`AudioOffsetEventBus`
(`new DecodeFilterEventBus(appScope)`, before `WebApp.Create` runs, threaded into the pump
closure).

**Rationale — "before the fan-out," not after:** admitting first means the very same decode that
introduced the new value is evaluated by `QsoAnswererService`/`QsoCallerService` against the
*already-corrected* state, on the same cycle — not one cycle later. This is the whole point of
moving admission server-side: zero-cycle latency between "a new entity appears" and "it's
engageable," matching what a fully-attended, instantly-reacting operator would have wanted to do
by hand.

**Alternative considered — admit inside `QsoAnswererService`/`QsoCallerService` themselves, at
their existing `DecodeFilterEvaluator.IsVisible` call site:** rejected. Two services would each
need to call `AdmitNewValues` and both would race to be "first" for the same decode/value on the
same cycle (harmless given Decision 3's lock, but redundant), and the WebSocket broadcast/table
UI would only learn about the admission if one of the two services also owned a broadcast
call — a responsibility neither currently has. A single hook point upstream of both is simpler
and matches the existing "decode pump is where visibleResults is finalized before every consumer"
architecture already used for `DecodeNoiseSuppressionFilter.Apply`.

### Decision 5 — "Explicitly empty" (`[]`) is never auto-admitted into

Per the Goals section: an axis whose current array is empty (`[]`, e.g. via "Select None") keeps
meaning "block everything, including anything not yet seen" — `AdmitNewValues` only acts when the
axis's array is **non-null and non-empty** (some, not all, values excluded). An empty array is
left untouched.

**Rationale:** this preserves the existing, already-specified, and correct
`decode-panel-filtering` scenario ("An axis with an explicit empty selection filters everything on
that axis") without contradiction. Auto-admitting into a deliberately-emptied axis would silently
undo an operator's explicit "hide all of this axis for now" action the instant something new
showed up — a different and worse bug than the one this change fixes.

## Risks / Trade-offs

- **[Risk] A new writer (the decode pump) now mutates `IDecodeFilterStore` alongside the existing
  POST-driven writer** → Mitigation: Decision 3's lock + copy-on-write; behaviorally this is the
  same "last write wins, no corruption" contract already accepted for concurrent multi-tab
  `POST`s, just with one more legitimate writer.
- **[Risk] Broadcast frequency** — a session decoding many distinct new entities in a short span
  (e.g. a contest opening) could fire `decodeFilterChanged` frequently → Mitigation: per-batch
  coalescing (Decision 4) bounds it to at most once per ~15s decode cycle, matching the existing
  batch cadence, not once per decode or per admitted value.
- **[Risk] Daemon-side "seen" tracking and the frontend's own client-side tracking
  (`seenEntities`/etc. in `main.js`) are now two independent trackers of a similar concept** →
  Mitigation: accepted; the frontend's tracker was never load-bearing for correctness even before
  this change (Decision 4 of the original design left "windowing" as an implementation detail),
  and `decodeFilterChanged` keeps every tab's actual filter *state* in sync regardless of whether
  its local "seen" set agrees. A future cleanup could have the frontend derive its candidate list
  from server-pushed data instead, but that is out of scope here.
- **[Risk] Standing policy** — this change touches `IDecodeFilterStore` directly and alters
  engagement-gating behavior → Mitigation: `qa/decode-filter-synth-verify/live_verify_9_axes.py`
  re-run before merge is a required task (not optional), with a new scenario added for the
  auto-admission path specifically (narrow an axis, then decode a station from an entity/
  continent/zone never seen this session, confirm it is NOT excluded).

## Migration Plan

1. `IDecodeFilterStore.AdmitNewValues` + `DecodeFilterStore`'s internal "seen" tracking, lock, and
   copy-on-write admission logic, with unit tests in `OpenWSFZ.Web.Tests` covering: first-seen
   value on a narrowed axis is admitted; first-seen value on an unnarrowed (`null`) axis is a
   no-op (returns `null`, no broadcast); first-seen value on an explicitly-empty (`[]`) axis is
   NOT admitted (Decision 5); an already-seen, already-excluded value is never re-admitted;
   independent behavior across all four attribute axes and in combination; concurrent-call
   safety (no `HashSet` corruption under parallel `AdmitNewValues`/`Set` calls).
2. New `DecodeFilterEventBus` (mirrors `DecodeEventBus`), constructed alongside the others in
   `Program.cs` before `WebApp.Create`.
3. Decode pump (`Program.cs`) calls `AdmitNewValues` per decode in `visibleResults`, before the
   QSO-controller channel fan-out; coalesces any resulting state change into a single
   `DecodeFilterEventBus.Publish` per batch.
4. `qa/decode-filter-synth-verify/live_verify_9_axes.py`: add the new-value-admission scenario;
   re-run in full against real hardware/synthetic decode injection per standing policy before
   merge.
5. No data migration — purely new, in-memory, additive state, same ephemeral/non-persisted
   posture as the rest of `decode-panel-filtering`.

## Open Questions

None outstanding — both forks raised during exploration (deny-list vs. auto-admit; frontend-only
vs. daemon-side) were decided by the Captain before this design was finalized.
