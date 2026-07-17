# DEV TASK — `engagement-target-validation` QA code-review findings (pre-merge)

**Date:** 2026-07-17
**OpenSpec change:** `engagement-target-validation` (not yet archived; still on `feat/engagement-target-validation`)
**Branch:** `feat/engagement-target-validation`
**Status:** **RESOLVED 2026-07-17/18.** Findings D and E fixed, regression-tested, and re-verified
live against the Captain's real, running production daemon (real CAT, real 29,013-entry
`callsign-regions.json`, real `POST /api/v1/tx/engage-decode` — see `tasks.md` task 7.3 for the
full record: `3A2TEST`/Monaco now `200` Allowed, the `6K`-incident shape still `409` Rejected, and
`IsSeedData` confirmed to survive a genuine `POST /api/v1/system/restart` as `false`). Finding F
fixed and covered by two new integration tests; not separately live-exercised (see task 7.3's note
on why unit coverage is the better instrument for that one). Full suite + `pre_merge_check.py`
green after all three fixes landed. Originally found during QA's full code review of the branch
(not a live session — static review of every touched file plus the two dev-tasks already on this
branch). One finding (D) was a root-cause candidate for the still-open Finding B in
`dev-tasks/2026-07-17-engagement-target-validation-live-verification-findings.md` — read that file
first if you haven't; this one assumed it.
**Found by:** QA, code review (not live testing).
**Severity:** **High** for Findings D and E (both were confirmed-in-code defects that would
misbehave on real, currently-shipping data, not merely hypothetical). **Medium** for Finding F
(a real gap, but narrower blast radius and had a straightforward decision to close it).

Mechanical gates are clean — `python3 tools/pre_merge_check.py` re-run by QA: full suite green,
Gate G3 (traceability) pass, Gate G8 (`openspec validate --strict --all`) 56/56, AOT publish WARN
only (pre-existing local-toolchain gap, unrelated). **None of that catches the three findings
below** — they're logic/design gaps, not build or spec-schema failures.

---

## Finding D (OPEN, High) — `ContainsDigit(matchedPrefix)` is the wrong signal; likely explains Finding B

### What's wrong

`EngagementTargetValidator.RemainderFitsGrammar` (`src/OpenWSFZ.Daemon/EngagementTargetValidator.cs:63-90`)
picks exactly one remainder shape based on whether the *matched region-store prefix itself*
contains a digit:

- prefix has a digit → remainder must be letters-only (Finding A's fix, for `"EC5"`-style entries
  where the digit is genuinely the call-district marker, already consumed).
- prefix has no digit → remainder must be digit-run-then-suffix.

This assumes a prefix's digit is *always* the callsign's mandatory call-area digit, fully consumed.
That's false for any DXCC prefix that is itself digit-leading as part of the entity identifier —
not a call-district marker at all — with the callsign's real call-area digit still to come
*after* the matched prefix.

### Concrete repro — no live data needed, it's in the shipped seed table

`src/OpenWSFZ.Daemon/CallsignRegionDefaults.cs` lists, verbatim:

```csharp
new("3A", "3A", "Monaco",  "EU", null, null),   // line 61
new("4X", "4X", "Israel",  "AS", null, null),   // line 69
new("9A", "9A", "Croatia", "EU", null, null),   // line 62
```

Take a genuine Monaco callsign, `3A2XYZ` (real Monaco calls are always `3A2...`). Matched prefix is
`"3A"` (contains `'3'`) → `ContainsDigit` is true → the algorithm demands the remainder `"2XYZ"` be
**letters-only** → fails on the leading `'2'` → **rejected**, even though this is an entirely
ordinary, well-formed callsign. Same shape for `4X`/`9A`-prefixed calls with their own call-area
digit still to follow. **No test in the suite exercises this** — every digit-in-prefix regression
test added for Finding A (`EngagementTargetValidatorTests.cs`) uses `"EC5"`-style data only, where
the prefix's digit genuinely is the last digit of the callsign.

This is very likely the mechanism behind Finding B's six still-unexplained live rejections — it's
the same disagreement class the existing dev-task's "structural hypothesis" section already
flagged (region-store prefix boundary landing *inside* the true digit-run, its `TM100XYZ` example),
just demonstrated here with concrete, already-shipping data instead of a hypothetical.

### Recommended fix — try both remainder shapes when the prefix carries a digit; don't pick one

Rather than the heavier redesign the existing dev-task speculated about (anchoring on
`Ft8Decoder.TryParseCallsignShape`'s last-digit-backward parse, which would need a second helper
promoted out of `Ft8Decoder` and a bigger surface to re-verify), a narrower fix closes both the
`EC5` case and the `3A2XYZ`/`TM100XYZ` case with the *existing* two shapes, just tried as
alternatives instead of an either/or gate:

- **If the matched prefix contains no digit:** unchanged — remainder must fit digit-run(1..`DigitRunMax`)
  + suffix. (A prefix with no digit anywhere means the whole callsign has no digit unless the
  remainder supplies one — there's no ambiguity to resolve here, and the current single-path
  behaviour is already correct: a remainder with no digit at all, e.g. a genuine no-digit-run
  garble, is correctly rejected today. Don't touch this branch.)
- **If the matched prefix contains a digit:** the remainder is valid if it fits **either**
  (a) letters-only suffix (0..`SuffixLengthMax`) — the prefix's digit was the whole call-area digit
  (`EC5` case), **or** (b) digit-run(1..`DigitRunMax`) + suffix — the prefix's digit was part of the
  entity identifier only, and the callsign's real call-area digit still follows (`3A2XYZ`,
  `TM100XYZ` cases). Reject only if *neither* shape fits.

I traced this by hand against every existing test in `EngagementTargetValidatorTests.cs` plus the
new repro shapes above, before writing this down — all pass under the OR'd version, including the
ones that must still reject (`EC5A1B`, `EC5ABCDEFG`, the `6KER05BPPBQ` incident itself — its
remainder `"ER05BPPBQ"` fails both the letters-only and the digit-run-first checks, so it's still
correctly rejected). Please re-verify independently rather than taking my hand-trace as gospel —
that's exactly the kind of thing a second pair of eyes exists to catch.

**Caution carried over from the existing dev-task, still applies:** this fix should still be
checked against a real region-data-refreshed daemon before being called done, per Finding B's own
"do not implement the redesign blind" note — this repro is proven against the shipped seed table,
not yet against live country-files.com data, so there may be a further disagreement pattern this
doesn't cover. Get the fix in, then re-run task 7.3's live verification pass rather than closing
Finding B purely on this analysis.

### Tests required

- Regression tests in `EngagementTargetValidatorTests.cs` for `3A2XYZ` (Allowed) and, ideally, the
  `TM100XYZ`-shaped case from the existing hypothesis (Allowed) — both currently rejected, both
  must become Allowed.
- Full re-run of the existing Finding-A regression tests (`EC5M`, `EC5A1B`, `EC5ABCDEFG`, `EC5`
  alone) to confirm the OR'd logic doesn't regress them.
- Re-run of the `6KER05BPPBQ` incident test (`EngagementTargetValidationRegressionTests.cs`) to
  confirm it still rejects.

---

## Finding E (OPEN, High) — `IsSeedData` silently flips to `false` on a daemon's second-ever launch

### What's wrong

`CallsignRegionStore.LoadAsync` (`src/OpenWSFZ.Daemon/CallsignRegionStore.cs:131-182`):

- File absent (first-ever run) → writes `CallsignRegionDefaults.Entries` to disk, leaves
  `_isSeedData == true`. **Correct**, and tested
  (`IsSeedData_FileAbsent_StaysTrueAfterSeedWrite`).
- File present, valid JSON → unconditionally sets `_isSeedData = false` (line 170).

The problem: the first branch's own seed-write means the file **exists on disk after that first
run**. Every subsequent daemon start reads that same file back through the second branch — which
has no way to tell "this is the seed table I wrote myself last time" from "this is a real
operator-refreshed table" — and sets `IsSeedData` to `false` regardless.

**Net effect: any daemon that has been restarted even once, ever, has `IsSeedData == false` — even
if the operator has never run a single region-data refresh.** This directly contradicts the
requirement you wrote into `spec.md` ("Only seed region data is loaded — validation is inactive...
every candidate token SHALL be treated as valid... identical to the system's behaviour before this
capability existed") and Decision 2's stated goal ("No behaviour change whatsoever when only seed
region data is loaded"). Combined with Finding D, this means the gate is very likely active — and
wrong — for ordinary users on the second launch of a completely default install, no refresh ever
run, hitting `3A`/`4X`/`9A`-prefixed calls.

No test catches this because every "real file loaded" test in `CallsignRegionStoreTests.cs` writes
distinct custom JSON (e.g. a Monaco/Australia/Fictional-Land fixture) rather than replaying the
actual seed-write-then-restart sequence a real install goes through.

### Recommended fix

Provenance needs to be determined from the file's own content, not from whether the file merely
exists. Simplest option: add a persisted marker to the on-disk DTO itself
(`CallsignRegionsFile` / `CallsignJsonContext`), e.g. a boolean `IsSeedData` (or a `"source"`
string) written alongside `Entries`:

- The first-run seed-write (`LoadAsync`'s file-absent branch) writes the marker as `true`.
- `SaveAsync` (the refresh endpoint) always writes the marker as `false`.
- `LoadAsync`'s file-present branch reads the marker from the file and sets `_isSeedData`
  accordingly, instead of assuming `false` unconditionally.

**One migration question you'll need to make a call on, and document the reasoning for (this is
exactly the kind of thing that should get an "Alternative considered" note in `design.md` the way
Decisions 1-4 already do):** an on-disk `callsign-regions.json` that predates this feature entirely
won't have the new marker field. Deserializing a missing boolean will default to `false` in most
JSON setups — meaning a pre-existing installation's file (which could itself be either an old seed
write or a genuine prior refresh — there's no way to know retroactively) will default to
"not seed" either way. That's probably the safer default of the two available (an operator who's
been running this daemon a while is more likely to have refreshed at least once than not), but it
should be a stated decision, not an accident of `default(bool)`.

### Tests required

- A test that runs `LoadAsync` **twice** against the same store/path (simulating a daemon
  restart) with no operator action in between, and asserts `IsSeedData` is still `true` after the
  second load — this is the scenario missing from the current suite.
- A test that `SaveAsync` followed by a fresh `LoadAsync` (simulating "refresh, then restart")
  correctly reports `IsSeedData == false`.
- A test for the missing-marker/pre-existing-file migration case, per whatever default you decide
  above.

---

## Finding F (OPEN, Medium) — manual `engage-decode` aborts the active QSO *before* validating the new target

### What's wrong

`src/OpenWSFZ.Web/WebApp.cs:1345-1366` ("Step 1: Abort if not Idle") runs unconditionally, ahead of
the new engagement-target-validation check in Step 2 (~1390 CQ-row branch, ~1445 directed-message
branch). So: operator double-clicks a decode row → its target gets rejected (409) → operator
declines the confirmation prompt → the target is correctly never armed, **but their prior
in-progress QSO has already been aborted for nothing** by Step 1, before the rejection was even
known.

Neither `design.md` nor `spec.md` addresses this ordering, and it isn't covered by either new
endpoint test (`EngageDecode_CqRow_RejectedTarget_Returns409AndDoesNotEngage` and the
confirm-retry test both start from `QsoState.Idle`, so there's nothing to abort in either case).

### Recommended fix

Reorder: extract the candidate callsign and run `IEngagementTargetValidator.Validate` *before*
Step 1's abort, so a 409 with no `confirm` leaves an in-progress QSO completely untouched. This
likely means restructuring the CQ-row-vs-directed-message parsing to happen ahead of the abort
call (it currently happens after, in Step 2) — check whether the abort is actually needed at all
before the target is known valid, or whether it's safe to move the whole abort block to
immediately before the first `qsoController.AnswerCqAsync`/`EngageAtAsync` call.

If reordering turns out to be more invasive than it looks (e.g. some downstream state depends on
having aborted first), the alternative is a documented decision to accept the current behaviour —
but that should be an explicit call in `design.md`'s Decision 4, not silent.

### Tests required

- A test that starts the fixture in a non-`Idle` state with an active QSO, issues an
  `engage-decode` for a target the validator rejects, and asserts the QSO is **still active**
  (state unchanged, partner unchanged) after the 409 — currently there's no test with a non-`Idle`
  starting state anywhere in the new engagement-target-validation coverage.

---

## Required before this branch is merge-ready

1. Fix Finding D (`RemainderFitsGrammar`), with the new regression tests.
2. Fix Finding E (`IsSeedData` provenance), with the restart-sequence tests.
3. Resolve Finding F — either reorder the abort, or make and document the decision to leave it.
4. Re-run task 7.3 (live/manual verification) against a real region-data-refreshed daemon after 1-2
   land, since both are corrections to logic that live testing already found broken once.
5. Re-run `python3 tools/pre_merge_check.py` after all of the above (per HK-006 — do this before
   telling QA it's ready again).

## References

- `dev-tasks/2026-07-17-engagement-target-validation-live-verification-findings.md` — Findings A/B/C;
  this document's Finding D is a concrete root-cause candidate for that file's still-open Finding B.
- `src/OpenWSFZ.Daemon/EngagementTargetValidator.cs:63-90` (`RemainderFitsGrammar`), `:92-97`
  (`ContainsDigit`) — Finding D.
- `src/OpenWSFZ.Daemon/CallsignRegionDefaults.cs:61-69` — the `3A`/`4X`/`9A` entries used as Finding
  D's concrete repro.
- `tests/OpenWSFZ.Daemon.Tests/EngagementTargetValidatorTests.cs` — existing Finding-A regression
  tests to re-verify; where Finding D's new tests belong.
- `src/OpenWSFZ.Daemon/CallsignRegionStore.cs:131-182` (`LoadAsync`), `:94-118` (`SaveAsync`) —
  Finding E.
- `tests/OpenWSFZ.Daemon.Tests/CallsignRegionStoreTests.cs` — where Finding E's restart-sequence
  tests belong.
- `src/OpenWSFZ.Web/WebApp.cs:1345-1366` (Step 1 abort), `:1388-1404` / `:1442-1456` (validation
  call sites) — Finding F.
- `tests/OpenWSFZ.Web.Tests/EngageDecodeEndpointTests.cs` — where Finding F's non-`Idle`-starting-state
  test belongs.
- `openspec/changes/engagement-target-validation/{design.md,tasks.md,specs/engagement-target-validation/spec.md}` —
  will need updating once D/E/F are resolved, the same way Finding A's fix updated them (task 3.5
  precedent).
