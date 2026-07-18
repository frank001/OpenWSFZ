# Developer Handoff — N8: `DecodeFilterStoreAdmitNewValuesTests`' 3.6 concurrency test asserts an invariant the production code never promised

**Date:** 2026-07-18
**Prepared by:** QA Engineer
**Defect ID:** N8 (Low — test-only defect; no production impact, see `openspec/qa-backlog.md`)

---

## 1. Context

The merge-to-main CI run for PR #85 (`feat/qso-transcript-panel`, **FR-062**) failed
`Build & Test (ubuntu-latest)` on a single test:

```
FR-061: 3.6: concurrent Set calls racing AdmitNewValues never throw or corrupt internal state [FAIL]
Expected store.Current.AllowedItuZones to contain 1 item(s), but found 2: {0, 27}.
```

Run: https://github.com/frank001/OpenWSFZ/actions/runs/29649266618

**Confirmed unrelated to PR #85.** That PR touches zero `.cs` files (it is a frontend-only
change — `web/js/qsoTranscript.js` and DOM wiring in `web/js/main.js`). This test belongs to
`fix-decode-filter-new-value-admission` (**FR-061**, PR #83), which merged to `main` roughly five
hours earlier with this exact test passing on all three platforms — both on the PR's own checks
and its archive-commit run (`a48de7c`). The test lost a timing race it was always exposed to; PR
#85's merge commit just happened to be the push that triggered the losing draw. QA re-ran the
same failed CI job after confirming this (`gh run rerun 29649266618 --failed`) to restore a green
`main` promptly while this handoff tracks the proper fix.

### 1.1 Root cause

`tests/OpenWSFZ.Web.Tests/DecodeFilterStoreAdmitNewValuesTests.cs:176`,
`ConcurrentSetCallsRacingAdmitNewValues_NeverThrowOrCorruptState`:

```csharp
var store = new DecodeFilterStore();
store.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Seed" } });

var admitTasks = Enumerable.Range(0, 100).Select(i => Task.Run(() =>
{
    var region = new RegionInfo(Continent: "EU", Entity: $"Entity{i}", Synthetic: false, CqZone: 14, ItuZone: 27);
    store.AdmitNewValues(MakeDecode(region));
}));

var setTasks = Enumerable.Range(0, 20).Select(i => Task.Run(() =>
    store.Set(DecodeFilterState.Unfiltered with { AllowedItuZones = new HashSet<int> { i } })));

await Task.WhenAll(admitTasks.Concat(setTasks));

store.Current.AllowedItuZones.Should().NotBeNull().And.HaveCount(1);
```

`DecodeFilterStore.Set` and `.AdmitNewValues` (`src/OpenWSFZ.Web/WebApp.cs:1910` and `:1916`)
share one lock (`_lock`, `WebApp.cs:1900`), so there is never torn or corrupted state — the test's
own headline claim ("never throw or corrupt internal state") genuinely holds and is not in
question. The problem is the *final* assertion, which additionally requires exactly one
`AllowedItuZones` entry, on the implicit assumption that whichever `Set()` call is scheduled last
among the 20 is authoritative for the whole test.

That assumption doesn't hold. All 100 `AdmitNewValues` tasks share the identical `ItuZone: 27`
value (only `Entity` varies per task), so exactly one of them wins `_seenItuZones.Add(27)`
(`WebApp.cs:1964`, `AdmitOne`) and is the *only* task among the 100 that can ever admit zone 27 —
but there is no ordering constraint on *when*, relative to the 20 `Set()` calls, that single
successful admission's lock acquisition happens. If it happens after the last `Set()` lands, it
reads whatever single-item `AllowedItuZones` that `Set()` just wrote (a narrowed-but-non-empty
axis — exactly the condition `AdmitOne` requires to admit into it) and produces a valid two-item
copy, e.g. `{0, 27}`. This is a legal interleaving under `Task.WhenAll` with two independent task
groups and no barrier between them — not a bug in `DecodeFilterStore`.

The test's own preceding comment (`DecodeFilterStoreAdmitNewValuesTests.cs:179-188`) already says
as much:

> "This test only proves AdmitNewValues and Set can run concurrently against the same lock
> without throwing or leaving a corrupted/torn HashSet behind — not that every admission survives
> an arbitrary racing Set."

— directly contradicting the `HaveCount(1)` assertion two lines later, which *does* require every
(single) admission to be visible in a specific way relative to the last `Set()`. The assertion is
simply asking for a stronger guarantee than either the code or the test's own stated intent
provides.

### 1.2 Why this is a test defect, not a production defect

`DecodeFilterStore.Set`'s last-write-wins-under-one-lock semantics are intentional, pre-existing,
and already documented — see the test file's own comment (lines 179-188) referencing
`fix-decode-filter-new-value-admission`'s `design.md` Decision 3 ("Set() is a whole-object
replace... A Set() call that reads a live store.Current snapshot outside the lock and later
writes it back can legitimately clobber an admission that landed in between — that is accepted
behaviour, not a bug"). Nothing about the observed `{0, 27}` result violates that contract: no
value was corrupted, no exception was thrown, and the final state is a fully valid
`DecodeFilterState`. **Do not change `DecodeFilterStore`, `AdmitOne`, or the locking discipline**
— there is no bug there to fix.

---

## 2. Branch

Suggested name: `fix/n8-admitnewvalues-set-race-test-flake`, off `main`.

---

## 3. Action

**File:** `tests/OpenWSFZ.Web.Tests/DecodeFilterStoreAdmitNewValuesTests.cs`, test
`ConcurrentSetCallsRacingAdmitNewValues_NeverThrowOrCorruptState` (~line 176-208).

Loosen the final assertion to match what the test's own comment already claims to be proving —
"no throw, no corruption, no torn HashSet" — rather than a specific final cardinality that depends
on unconstrained task-scheduling order. Suggested shape:

```csharp
await Task.WhenAll(admitTasks.Concat(setTasks));

// No exception propagated from any task above (xUnit would already have failed this test if one
// had). Whichever writer's state landed last is a fully valid, internally consistent
// DecodeFilterState — never a torn/partial HashSet. Exact membership is intentionally NOT
// asserted beyond that: AllowedItuZones may legitimately end up as a single-item set from the
// last Set() to run, or a two-item set if the one AdmitNewValues call that wins the race to admit
// ItuZone 27 (see AdmitOne, WebApp.cs:1961) happens to land after that last Set() — both are
// correct, race-safe outcomes under DecodeFilterStore's documented last-write-wins-under-one-lock
// contract (design.md Decision 3, fix-decode-filter-new-value-admission). See N8,
// openspec/qa-backlog.md, for the full analysis of why a stricter assertion here is wrong, not
// merely flaky.
var finalItuZones = store.Current.AllowedItuZones;
finalItuZones.Should().NotBeNull();
finalItuZones!.Should().NotBeEmpty();
finalItuZones.Should().BeSubsetOf(Enumerable.Range(0, 20).Append(27),
    "every member must be either a value some Set() call wrote or the one admitted ItuZone (27) — never a corrupted/unrelated value");
```

Do not weaken the test beyond this — it should still fail if `Set`/`AdmitNewValues` ever throw,
deadlock, or produce a value outside the legal set (which would indicate genuine corruption or a
lost/duplicated write, unlike the accepted 1-vs-2-item ambiguity this task is narrowing the
assertion around).

---

## 4. Acceptance Criteria

QA will verify all of the following before approving merge:

- [ ] **AC-1:** The revised assertion no longer requires an exact `AllowedItuZones` count; it
  requires non-null, non-empty, and membership drawn only from `{0..19} ∪ {27}` (i.e. still fails
  on genuine corruption, an unrelated stray value, or a lost lock).
- [ ] **AC-2:** No change to `src/OpenWSFZ.Web/WebApp.cs` (`DecodeFilterStore`, `Set`,
  `AdmitNewValues`, `AdmitOne`) — this is a test-only fix; production locking/last-write-wins
  semantics are correct as-is (see §1.2).
- [ ] **AC-3:** Run `dotnet test --filter "FullyQualifiedName~DecodeFilterStoreAdmitNewValuesTests"`
  **repeatedly** (at least 10 times locally) to build confidence the assertion is now scheduling-
  order-independent, not just not-observed-failing-this-time — a single green run proves nothing
  given this defect's nature.
- [ ] **AC-4:** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings.
- [ ] **AC-5:** `dotnet test OpenWSFZ.slnx -c Release` — full suite green.
- [ ] **AC-6:** CI green on all three platforms (this defect's whole reason for existing is that
  it only manifests under real parallel-scheduling timing CI actually has and local runs may not
  reproduce as reliably).

---

## 5. References

- `openspec/qa-backlog.md` — **N8** entry (2026-07-18), the diagnosis this task implements; mark
  it resolved once this merges (QA will do this at close-out, not part of this task's diff).
- CI run that surfaced the failure:
  https://github.com/frank001/OpenWSFZ/actions/runs/29649266618 (`ubuntu-latest`, `Test (Release)`
  step, `DecodeFilterStoreAdmitNewValuesTests.ConcurrentSetCallsRacingAdmitNewValues_NeverThrowOrCorruptState`).
- `src/OpenWSFZ.Web/WebApp.cs`:
  - `DecodeFilterStore` — line 1893 (class + `_lock` field, line 1900).
  - `Set` — line 1910.
  - `AdmitNewValues` — line 1916.
  - `AdmitOne` — line 1961 (the copy-on-write admission helper; its doc comment already explains
    the intentional narrowed-but-non-empty / null / empty-axis rules this task does not touch).
- `tests/OpenWSFZ.Web.Tests/DecodeFilterStoreAdmitNewValuesTests.cs`:
  - Fix target — `ConcurrentSetCallsRacingAdmitNewValues_NeverThrowOrCorruptState`, line 176-208.
  - The sibling concurrency test just above it (`ParallelAdmitNewValuesAndSetCalls_...`, line
    152-174) is **not** affected — it only races `AdmitNewValues` calls against each other (no
    `Set()` in the mix) and asserts an exact count that genuinely does hold in that scenario (no
    admission may be lost when the axis is never replaced out from under it). Leave it unmodified.
- Related but distinct: `openspec/qa-backlog.md` **N6**/**N7** — a different, previously-resolved
  class of test-isolation flake (unscoped static WebSocket registry, cross-test contamination).
  N8 is a single-test assertion-too-strict defect, not a repeat of that mechanism — noted here
  only because both surfaced as "CI failed on an unrelated PR's merge-to-main run."
- `openspec/changes/archive/2026-07-18-fix-decode-filter-new-value-admission/design.md` (or
  wherever it lands post-archive) — Decision 3, the original source of the
  last-write-wins-is-accepted-behaviour contract this task's fixed assertion must remain
  consistent with.
