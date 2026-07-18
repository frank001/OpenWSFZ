## Context

Confirmed live (2026-07-16): the Captain's daemon has real country-files.com data loaded
(`callsign-regions.json`, 29,013 entries, including a genuine `"6K"` → Republic of Korea entry).
A garbled decode, `6KER05BPPBQ`, was engaged and transmitted twice via `POST /api/v1/tx/engage-decode`
before manual abort (`logs/openswfz-20260716T194057Z.log:686-761`). It passed decode acceptance
(`callsign-structure-validation` — deliberately permissive, no positive allow-list) and passed the
region-lookup boolean check (`"6K"` genuinely matches — `Republic of Korea`, confirmed against the
live data file), because that check only asks "did *any* prefix match," never "does the matched
prefix explain the *whole* token."

Existing building blocks, none of which currently talk to each other for this purpose:
- `ICallsignGrammarStore.Current` (`CallsignGrammarConfig`: `DigitRunMax=3`, `TotalLengthMax=11`,
  `SuffixLengthMax=6`) — the shape grammar decode acceptance already enforces.
- `ICallsignRegionStore` (`CallsignRegionStore.TryGetRegion`, longest-prefix-match over `Entries`) —
  real data only present after an operator-triggered refresh (`region-lookup-data-refresh`); absent
  that, `CallsignRegionDefaults.Entries` (39 entries, explicitly documented as "intentionally
  partial") is loaded instead, with no existing signal distinguishing the two states.
- `Ft8Decoder.StripPortableSuffix` (private, `Ft8Decoder.cs:868`) — the existing `/`-suffix split
  used before shape evaluation.

## Goals / Non-Goals

**Goals:**
- Reject an engagement attempt (manual `engage-decode`, auto-answer arming, responder matching)
  when the region store's longest-matched real prefix is not immediately followed by a valid
  digit-run + suffix tail, using the grammar's own configured limits — not a new, second set of
  hardcoded numbers.
- No behaviour change whatsoever when only seed region data is loaded (no operator refresh yet run).
- No behaviour change to decode acceptance, `ALL.TXT`, decode-panel visibility, or worked-before
  indicators — this is a new decision point, not a retrofit of an existing one.
- Preserve operator authority on the one path a human is actually looking at a specific decode
  (manual `engage-decode`): a soft block the Captain can override, not a hard wall.

**Non-Goals:**
- Not touching `Ft8Decoder.IsPlausibleMessage`/`IsCallsignShapeInvalid` or `callsign-grammar.json`'s
  own rules.
- Not touching decoder tuning (Pass-1 Score Floor / OSD Correlation Threshold / OSD Max Hard
  Errors) — orthogonal, R&R-validated, out of scope.
- Not building a new prefix table — reusing the one already loaded for `region-lookup`.
- Not attempting to resolve every possible false-reject case from a coarser-than-reality region
  table entry — see Risks below; the manual-path override exists precisely because this can't be
  made perfect.

## Decisions

### Decision 1 — Add `ICallsignRegionStore.TryMatchPrefix`, don't duplicate the longest-match scan

`TryGetRegion` returns `RegionInfo?` with no matched-prefix length, so a second consumer can't
learn *where* the match ended without re-implementing longest-prefix-match against the already-public
`Entries`. Rather than duplicate that algorithm in the new capability, add one new method:

```csharp
// ICallsignRegionStore — additive, does not change TryGetRegion's existing contract/behaviour
CallsignRegionMatch? TryMatchPrefix(string callsignToken);
// new record: CallsignRegionMatch(RegionInfo Region, int MatchedPrefixLength)
```

`TryGetRegion` can become a thin wrapper (`TryMatchPrefix(token)?.Region`) so there is exactly one
matching implementation. This is additive to `ICallsignRegionStore` — it does not change any
documented behaviour of `TryGetRegion`, so the `region-lookup` capability's existing requirements
are unaffected; the interface simply grows.

**Alternative considered:** have the new validator scan `Entries` itself. Rejected — duplicates a
scan, and any future change to the matching rule (e.g. case-folding, tie-breaking) would need to be
kept in sync in two places.

### Decision 2 — Real-vs-seed data signal is an explicit provenance flag, not an entry-count heuristic

Needed to satisfy "no-op on seed data." An entry-count threshold (e.g. `Entries.Count > 1000`) is a
magic number that silently breaks if the seed table is ever extended, and says nothing about
*provenance* (an operator could, in principle, load a small custom file). Instead, `CallsignRegionStore`
tracks how the current table was populated:

```csharp
// ICallsignRegionStore — additive
bool IsSeedData { get; }   // true until either a real callsign-regions.json is loaded from disk
                            // at startup, or SaveAsync (the refresh endpoint) succeeds at least once
```

Set `false` the moment startup load reads an on-disk `callsign-regions.json` (as opposed to falling
back to `CallsignRegionDefaults.Entries`), and set `false` after any successful `SaveAsync`. The new
gate no-ops whenever `IsSeedData == true`.

**Alternative considered:** entry-count threshold. Rejected as a magic number with no semantic tie
to what's actually being asked ("has an operator ever supplied real data").

**Correction (found in QA code review, 2026-07-17, dev-task
`2026-07-17-engagement-target-validation-qa-review-findings`, Finding E):** the original
implementation set `IsSeedData = false` unconditionally the moment `LoadAsync`'s file-present branch
successfully read *any* on-disk file — including the very file the file-absent branch itself had
just written on the daemon's first-ever run. Since that seed-write means the file exists on disk for
every subsequent launch, this meant **any daemon that had been restarted even once, ever, reported
`IsSeedData == false`** — even with zero operator refreshes run — silently defeating the "no
behaviour change on seed data" goal above from the daemon's second launch onward. Fixed by persisting
an explicit provenance marker (`isSeedData: bool`) inside `callsign-regions.json` itself: the
file-absent seed-write branch writes it `true`; `SaveAsync` always writes it `false`; the file-present
load branch reads the marker from the file's own content instead of assuming `false`. A pre-existing
file from before this marker existed deserialises the missing property as `false` (documented
migration choice — an operator who has been running the daemon long enough to have a pre-existing
file is more likely to have refreshed at least once than not, and there is no way to tell
retroactively). Implementation: `CallsignRegionStore.LoadAsync`/`SaveAsync`/`WriteAsync`,
`CallsignRegionsFile.IsSeedData` (`CallsignJsonContext.cs`).

### Decision 3 — New validator is its own service, reusing existing grammar/region primitives

New interface `IEngagementTargetValidator` (Abstractions) / `EngagementTargetValidator` (Daemon),
injected via DI into `WebApp`, `QsoAnswererService`, `QsoCallerService`:

```csharp
EngagementValidationResult Validate(string callsignToken);
// EngagementValidationResult: Allowed | Rejected(string reason)
```

Algorithm:
1. If `regionStore.IsSeedData` → `Allowed` (gate inactive).
2. Strip portable suffix (reuse `Ft8Decoder.StripPortableSuffix` — promote it from `private` to an
   internal shared helper, e.g. move to `OpenWSFZ.Abstractions` or expose via
   `[InternalsVisibleTo]`, since `OpenWSFZ.Daemon` already references `OpenWSFZ.Ft8`). No second
   copy of this split logic.
3. `regionStore.TryMatchPrefix(baseCall)` — if no match at all → `Allowed` (an unlisted prefix is
   not evidence of invalidity; mirrors the existing exclusion-list philosophy: absence ≠ rejection).
4. If matched: `remainder = baseCall[match.MatchedPrefixLength..]`. **Whether the matched prefix
   itself already contains a digit changes what "valid remainder" means** (corrected 2026-07-17,
   found live — see the note below):
   - If the matched prefix contains **no** digit (e.g. `"DL"`), the remainder must supply the
     callsign's mandatory digit itself: a digit-run of 1 to `DigitRunMax` immediately at the
     start, followed by 0 to `SuffixLengthMax` letters only, consuming the entire remainder.
   - If the matched prefix **already contains** a digit (e.g. `"EC5"`), the remainder is
     suffix-only: 0 to `SuffixLengthMax` letters, no digit expected — the callsign's mandatory
     digit is already accounted for, inside the matched prefix.
   - Either way, if the remainder doesn't fit its applicable shape → `Rejected`.

This reuses `DigitRunMax`/`SuffixLengthMax` verbatim from `ICallsignGrammarStore.Current` — no
second copy of these numbers anywhere in the new capability.

**Correction (found live, 2026-07-17, first manual-verification pass after initial implementation):**
the original version of step 4 unconditionally required the remainder to start with a digit-run,
on the unstated assumption that a region-store prefix match is always purely alphabetic. Real
country-files.com data frequently isn't — it commonly breaks a single DXCC entity down by
call-district, baking the mandatory call-area digit directly into the matched prefix (e.g. `"EC5"`
for a specific Spanish call district). Under the original algorithm this meant *every* genuine
callsign whose longest region-store match happened to include its call-area digit was rejected —
observed live rejecting `EC5M` (and five more genuine calls in the same short session) with no
false-positive-shaped input involved at all, i.e. the false-positive rate on ordinary real traffic
approached "nearly every engage attempt," not an edge case. Fixed by inspecting the matched prefix
for a digit first and choosing the applicable remainder shape accordingly (implementation:
`EngagementTargetValidator.RemainderFitsGrammar`). The `6KER05BPPBQ` incident case that motivated
this whole capability still rejects correctly under the corrected algorithm (its matched prefix
`"6K"` also contains a digit, but the 9-character remainder `"ER05BPPBQ"` still fails the
suffix-only shape — it's neither letters-only nor within `SuffixLengthMax` — so the fix doesn't
regress the original defect it was built to catch).

**Second correction (found in QA code review, 2026-07-17, dev-task
`2026-07-17-engagement-target-validation-qa-review-findings`, Finding D — likely root cause of the
live-verification dev-task's still-open Finding B):** the first correction above assumed a digit
inside the matched prefix *always* means the whole mandatory call-area digit was already consumed
by the prefix. That's false for any DXCC entity whose region-store prefix is itself digit-leading
as part of the *entity identifier*, not the call-district marker — with the callsign's real
call-area digit still to come *after* the matched prefix. Concrete, already-shipping example from
`CallsignRegionDefaults.Entries`: Monaco's entry is `"3A"`; genuine Monaco calls are always
`3A2...` — the `'2'` is the real call-area digit, owned by the remainder, not the prefix. Under the
first correction, `3A2XYZ` matched prefix `"3A"` (contains a digit) → remainder `"2XYZ"` forced
into the letters-only shape → rejected, despite being an entirely ordinary callsign. Fixed by
trying **both** remainder shapes whenever the matched prefix contains a digit — letters-only suffix
(the `EC5` case) **or** digit-run-then-suffix (the `3A` case) — and rejecting only if neither fits.
Traced by hand against every existing regression test (`EC5M`, `EC5A1B`, `EC5ABCDEFG`, `EC5` alone,
`6KER05BPPBQ`) before landing: all still resolve identically under the OR'd version. Implementation:
`EngagementTargetValidator.RemainderFitsGrammar`/`FitsDigitRunThenSuffix`. **Re-verified live
against a real region-data-refreshed daemon, 2026-07-17/18 (task 7.3):** `3A2TEST` (the exact
Monaco/`3A` shape this correction targets) engaged cleanly (`200` Allowed) against the Captain's
real 29,013-entry `callsign-regions.json`; the original incident shape, reproduced against the same
daemon's real `"6K"` entry, still correctly returned `409` Rejected. See `tasks.md` task 7.3 for
the full live-verification record.

### Decision 4 — Asymmetric enforcement: hard-skip for automation, soft-block-with-override for the manual path

Automated arming (`QsoAnswererService` auto-answer / `QsoCallerService` responder matching) has no
human looking at the specific candidate — `Rejected` means: do not arm, log a skip line, continue
scanning. No override exists because there is no operator judgment being exercised at that instant.

Manual `POST /api/v1/tx/engage-decode` **is** a human looking at one specific row and choosing it —
the Captain may know something the table doesn't (a genuinely new allocation not yet in
country-files, or a table entry too coarse for the real administrative boundary). `Rejected` here
returns a `409` with the reason and `requiresConfirmation: true`; a repeat request carrying
`confirm: true` proceeds regardless of the check. This preserves final operator authority on the one
path where a human is actually exercising it, while still adding real friction against exactly the
kind of accidental/exploratory click that produced tonight's incident.

**Alternative considered:** hard-block on all three paths uniformly. Rejected — a coarse or
incomplete region-table entry (Decision 2's residual risk, see below) could then need a settings
round-trip or a full region-data refresh to recover from a single bad manual click, which is worse
than the problem being solved.

**Correction (found in QA code review, 2026-07-17, dev-task
`2026-07-17-engagement-target-validation-qa-review-findings`, Finding F):** `POST
/api/v1/tx/engage-decode`'s original implementation ran its unconditional "abort any in-progress
QSO" step *before* the validation check above, rather than after. So a rejected target's `409`
(with no `confirm`) still aborted the operator's prior in-progress QSO for nothing — the soft-block
correctly prevented arming the new target, but did so at the cost of the old one, before the
operator even saw the confirmation prompt. Fixed by moving the abort to immediately before the
dispatch call it actually gates (`AnswerCqAsync`/`EngageAtAsync`), i.e. *after* the validation
gate, for both the CQ-row and directed-message branches. The `73`-only and
not-addressed-to-us branches don't validate a target at all, so they still abort unconditionally,
same as before — this decision only reorders the two paths that were newly gated by this
capability. Implementation: `WebApp.cs`'s `AbortIfNotIdleAsync` local function, called once per
branch immediately before the branch's actual dispatch/return.

## Risks / Trade-offs

- **[Risk] A genuinely valid callsign is rejected because the region table's matched prefix is
  coarser or narrower than the true administrative boundary** (e.g. table has a 2-char entry where
  reality has a 3-char sub-allocation, or vice versa) → **Mitigation:** Decision 4's manual-path
  override; automated paths simply skip and wait for a cleaner decode, which is already normal
  behaviour for any unanswered/ambiguous decode.
- **[Risk] `StripPortableSuffix` promoted out of `Ft8Decoder` could drift from decode-acceptance's
  own portable-suffix handling if someone edits one copy later** → **Mitigation:** promote to one
  shared location and delete the private copy, don't leave two.
- **[Risk] `IsSeedData` provenance flag adds new mutable state to `CallsignRegionStore`** →
  **Mitigation:** same lifecycle/locking discipline already used for `Entries` (updated only after a
  successful load/save, per the existing `SaveAsync` atomicity contract) — no new concurrency
  surface.
- **[Trade-off] Engagement-time lookup is a second `TryMatchPrefix` scan, separate from the
  advisory `TryGetRegion` scan already done once per raw decode inside `Ft8Decoder`** — deliberately
  not threading match data through `DecodeResult` to avoid it. Engagement attempts are orders of
  magnitude rarer than raw decodes (one per operator click or per auto-answer arm, not one per
  decoded line per 15-second cycle), so a second linear scan at that rate is immaterial given the
  existing scan is already documented as acceptable at full per-decode cadence.

## Migration Plan

Purely additive — new interface members, new service, new call-site checks. Any daemon that has
never run a region-data refresh (`IsSeedData == true`) sees zero behavioural change on day one.
No data migration, no config migration, no rollback needed beyond a normal revert.

## Open Questions

- Exact wire shape of the `409`/`confirm` round-trip for `engage-decode` — left to `tasks.md`/
  implementation to match existing `WebApp.cs` response conventions.
- Whether `EngagementTargetValidator` should also be consulted before the jump-in paths
  (`EngagePoint.SendReport`/`SendRr73`) covered by the still-open
  `dev-tasks/2026-07-16-jump-in-sendrr73-no-adif-record.md` fix — those also arm a TX target from a
  decode-panel double-click. Recommend the same validator call is added there when that dev-task is
  implemented, but leaving it out of this change's `tasks.md` to avoid coupling two independent
  fixes; flag it in that dev-task's references instead.
