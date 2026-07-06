# Developer Handoff — D-012: hash_table_add over-counts rejects for already-known callsigns once the table is full

**Date:** 2026-07-06
**Prepared by:** QA Engineer
**Defect ID:** D-012 (new — found during live/real-corpus verification of
`feat/f-005-hash-table-saturation-diagnostic`, not yet merged)
**Severity:** Major — not a crash or data-loss bug (the hash table's actual contents and
resolution behaviour are unaffected), but it makes the exact metric F-005 exists to expose
report numbers that are meaningless once the table saturates, in a way that actively misleads
whoever reads it. Found via `feat/f-005-hash-table-saturation-diagnostic`'s own review process
working as intended — a synthetic-only test suite could not have caught it.
**OpenSpec change:** `openspec/changes/f-005-hash-table-saturation-diagnostic/` — this defect
is in F-001's `hash_table_add` (shim 20260031), not in anything F-005 added. F-005 didn't touch
`hash_table_add`'s body (confirmed by diff review — only comments changed near it). But F-005 is
the change that makes this counter operator-visible for the first time, so it should not merge
without this fixed: exposing a broken metric is worse than not exposing it. No spec change is
needed — the requirement F-005 already added
(`openspec/changes/f-005-hash-table-saturation-diagnostic/specs/hashed-callsign-resolution/spec.md`,
"Reject count reflects discarded announcements once the table is full") already says the right
thing; it's the native code that doesn't match it.
**Branch:** continue on `feat/f-005-hash-table-saturation-diagnostic` — do not open a new
branch. This must land before that branch merges.

---

## 1. Context — how this was found

QA verified F-005 end-to-end by replaying a real 9.5-hour off-air FT8 corpus
(`artefacts/20260615_live_run/save`, 2,291 WAVs, predates F-001/F-005, gitignored/local-only
per NFR-021) through the current build in a single process, then reading
`Ft8LibInterop.GetHashTableRejectCount()` at the end — the same session-end read the daemon
performs at shutdown. Result:

```
WAV files processed              : 2291 (0 failed/skipped)
Total decodes                    : 42,429   (all message types, all 2291 cycles)
Decodes with '<' hash placeholder: 3,258
Reject count DELTA               : 73,627
```

**73,627 rejects out of only 42,429 total decoded messages of any type is arithmetically
impossible** under the metric's documented meaning ("count of Type 4 announcements discarded
because the table was already full") — there cannot be more discarded Type-4-callsign-saves
than there are decoded messages in total. Chasing that contradiction down found the root cause
in `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, `hash_table_add` (lines 567–586):

```c
static void hash_table_add(callsign_table_t* tbl, const char* callsign, uint32_t hash)
{
    /* Guard: discard new callsigns when the table is full rather than looping
     * forever. ... */
    if (tbl->count >= HASH_TABLE_SIZE) { g_hash_table_reject_count++; return; }   // line 572

    uint16_t h10 = (hash >> 12) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    while (tbl->entries[idx].callsign[0] != '\0') {
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            !strcmp(tbl->entries[idx].callsign, callsign)) {
            tbl->entries[idx].hash &= 0x3FFFFFu; return; }   // "already known" — no increment
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash = hash;
}
```

The full-table check on line 572 runs **before** the loop that checks whether the callsign is
already stored. Once `tbl->count` reaches 256, **every subsequent call to `hash_table_add`
increments `g_hash_table_reject_count` and returns immediately — including re-announcements of
callsigns already resolvable in the table.** A real station calling CQ every couple of minutes
for nine hours, resolved correctly on its first appearance, gets miscounted as a fresh "reject"
on every later re-decode once the table happens to be full — which is exactly what a real 9.5h
corpus does and a synthetic 264-distinct-callsigns test (the existing
`HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive` test, extended for F-005
in tasks.md §4.2) never would, because every callsign in that test is unique and never repeated.

This is why the existing test suite (280/280 passing) never surfaced the bug, and why it took a
genuine real-traffic replay to find it.

**Why the early-return exists at all (don't just delete it):** the comment at
`hash_table_lookup` (lines 545–547) explains the actual constraint — `hash_table_add`'s linear
probe (`while (tbl->entries[idx].callsign[0] != '\0')`) has no iteration bound. When the table
is completely full (all 256 slots occupied, no `'\0'` terminator anywhere), that loop would spin
forever. The `tbl->count >= HASH_TABLE_SIZE` check was placed first specifically to avoid ever
entering that unbounded loop once the table is full — a real and necessary safety guard, just
placed so it also (incorrectly) skips the "already known" check for repeats.

---

## 2. Branch

Continue on `feat/f-005-hash-table-saturation-diagnostic`.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — reorder the check, bound the probe

Replace `hash_table_add` with a version that probes for an existing/empty slot **first** (bounded
at `HASH_TABLE_SIZE` iterations, mirroring `hash_table_lookup`'s own existing probe-limit guard
immediately above it, lines 545–553), and only consults `tbl->count` to decide reject-vs-insert
**after** confirming the callsign isn't already present:

```c
static void hash_table_add(callsign_table_t* tbl, const char* callsign, uint32_t hash)
{
    uint16_t h10 = (hash >> 12) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;

    /* Bounded probe (mirrors hash_table_lookup's guard above): safe even when the
     * table is completely full (all 256 slots occupied, no '\0' terminator to stop
     * an unbounded linear scan). When the table has room, an empty slot is always
     * reachable within HASH_TABLE_SIZE probes, so the bound never changes behaviour
     * in that case — it only prevents an infinite loop in the all-256-occupied case.
     * D-012: checking for an existing match BEFORE the full-table guard (rather than
     * after, as the previous version did) is the actual fix — a repeat announcement
     * of an already-known callsign must never increment g_hash_table_reject_count,
     * only a genuinely new callsign turned away for lack of room may. */
    for (int probe = 0; probe < HASH_TABLE_SIZE; probe++) {
        if (tbl->entries[idx].callsign[0] == '\0') break; /* empty slot — genuinely new, room found */
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            !strcmp(tbl->entries[idx].callsign, callsign)) {
            tbl->entries[idx].hash &= 0x3FFFFFu; return; /* already known — no-op, NOT a reject */
        }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }

    /* Not found after a full probe: this is a genuinely new callsign. Reject only
     * now, if the table has no room left. */
    if (tbl->count >= HASH_TABLE_SIZE) { g_hash_table_reject_count++; return; }

    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash = hash;
}
```

Note the loop termination cases are exhaustive and match the original design intent:
- **Empty slot found within the probe** → callsign is new; `idx` is the insert position;
  falls through to the `tbl->count` check (only relevant if, contradictorily, count already
  reads full while a slot is empty — should not happen, but the check is cheap insurance).
- **Matching entry found** → already known; return immediately, no count change either way.
- **Probe exhausts all `HASH_TABLE_SIZE` iterations without either** → table is completely
  full (every slot occupied, none matched); falls through to the `tbl->count >= HASH_TABLE_SIZE`
  check, which will be true, and rejects correctly.

### 3.2 — Version bump (do not skip — this changes existing behaviour)

This is a behaviour fix to an existing exported code path (not a new export), but per this
project's own `FT8_SHIM_VERSION` discipline every shim change gets a version bump so a stale
binary can be detected. Confirm the current value at implementation time (do not assume
`20260032` is still current — F-005's own tasks.md §1.1 flagged exactly this as easy to miss),
reserve the next sequential number (expected `20260033`), and update in lockstep:
- `FT8_SHIM_VERSION` in `ft8_shim.h`, plus its version-history comment block.
- The mirrored version-history comment block at the top of `ft8_shim.c`.
- `ExpectedShimVersion` in `Ft8LibInterop.cs`.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`.
- Rebuild `libft8.dll` via `rebuild_shim.bat` (no new `/EXPORT:` needed — no new symbol, just a
  behaviour fix inside an existing one) and confirm with `check_native_version.py`.

### 3.3 — Do not touch `hash_table_lookup` or the session-end/HTTP/WS wiring

Everything downstream of `g_hash_table_reject_count` (the getter, `HashTableRejectCountReporter`,
`DaemonStatus`, `WebApp.cs`, `WebSocketHub.cs`, and their tests) is correct as-is and does not
need to change — the bug is entirely inside the counting logic in `hash_table_add`, not in
anything that reads the counter afterward.

---

## 4. Tests

### 4.1 — New test: repeat announcement of an already-known callsign must NOT increment the count

This is the test that actually targets D-012 — the existing saturation test cannot, because
every callsign it uses is unique. Add to `HashedCallsignResolutionTests.cs` (or a new file
alongside `HashTableRejectCountTests.cs`, whichever fits better):

1. Saturate the table (reuse the existing 264-distinct-callsigns saturation helper, or a lighter
   variant — the goal is just `tbl->count >= HASH_TABLE_SIZE`, not a specific overflow amount).
2. Snapshot `Ft8LibInterop.GetHashTableRejectCount()`.
3. Re-announce (via a fresh Type 4 decode cycle) a callsign that was stored **before** saturation
   and is confirmed resolvable (e.g., one of the "entry #0–9 must remain resolvable" callsigns
   the existing test already asserts on).
4. Assert the reject count is **unchanged** (delta `== 0`) after that repeat announcement —
   this is the assertion that fails on the current code and passes after the 3.1 fix.

### 4.2 — Confirm the existing saturation test still passes unmodified

`HashedCallsignResolutionTests.HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive`
(with its `(rejectsAfter - rejectsBefore).Should().BeGreaterThanOrEqualTo(8)` assertion) must
still pass after the fix — genuinely new callsigns beyond capacity are still correctly rejected;
only the "already known, re-announced" case changes behaviour.

### 4.3 — Full regression

`OpenWSFZ.Ft8.Tests` (280 baseline), `OpenWSFZ.Daemon.Tests` (193), `OpenWSFZ.Web.Tests` (206)
must all stay green. `openspec validate --strict --all` must stay at 47/47.

### 4.4 — Recommended (not blocking): re-run the real-corpus check after the fix

QA's real-corpus replay harness (`tests/OpenWSFZ.Ft8.Tests/F005RealCorpusSaturationCheck.cs` —
currently a one-off verification file, not yet decided whether to keep permanently) can be
re-run against `artefacts/20260615_live_run/save` after this fix lands, to confirm the corrected
reject count is now a small, plausible number (order of magnitude comparable to the 700–1,000+
distinct nonstandard callsigns the 2026-07-06 endurance run's text-heuristic triage estimated),
not the current 73,627. This is confirmatory, not a gate — the unit tests in 4.1/4.2 are the
actual regression protection.

---

## 5. Acceptance Criteria

- [x] **AC-1:** `hash_table_add` checks for an already-known callsign before consulting
  `tbl->count`, for both the full-table and non-full-table cases — no code path can increment
  `g_hash_table_reject_count` for a callsign already present in the table. Implemented exactly
  as prescribed in §3.1 (bounded probe first, `tbl->count` check only after).
- [x] **AC-2:** The bounded-probe loop cannot infinite-loop when the table is completely full
  (all 256 slots occupied) — verified by the existing saturation test still passing (it already
  exercises exactly this state) plus the new 4.1 test.
- [x] **AC-3:** New test (4.1) passes: re-announcing an already-known callsign after saturation
  does not change the reject count.
  `HashedCallsignResolutionTests.RepeatAnnouncement_OfAlreadyKnownCallsign_AfterSaturation_DoesNotIncrementRejectCount`.
  **Discovered-item (not in the original plan):** the first draft of this test tried to store its
  own fresh "pre-existing" callsign before saturating independently of the existing saturation
  test, and was observed to run AFTER that test in practice — finding the table already
  permanently full (no reset entry point, by design) and its own fresh entry silently rejected.
  Root cause: xUnit does not guarantee method-execution order within a class by default (only
  cross-class/collection order is pinned in this suite, via `RunHashTableSaturationCollectionLastOrderer`).
  Fixed by adding a small class-scoped `[TestCaseOrderer]`
  (`RunD012RegressionAfterSaturationTestCaseOrderer`, new file `D012RegressionTestCaseOrder.cs`)
  pinning this test strictly after the saturation test, and rewriting the test to reuse that
  test's own guaranteed-resolvable `callsigns[0]` ("Q000000") instead of racing for a fresh slot.
- [x] **AC-4:** Existing saturation test (4.2) passes unmodified — genuinely new callsigns beyond
  capacity are still rejected and counted. Confirmed: not a single line of that test's body was
  touched; only the new `[TestCaseOrderer]` on the class (which does not alter its logic) was
  added to guarantee it runs first.
- [x] **AC-5:** Shim version bumped to `20260033` as expected. Both files' version-history
  comments updated (`ft8_shim.h` define + history block; `ft8_shim.c` mirrored block plus the
  D-012 entry), `ExpectedShimVersion` bumped in `Ft8LibInterop.cs`, `libft8.version.txt`
  refreshed, DLL rebuilt via `rebuild_shim.bat` and confirmed via `check_native_version.py`
  ("Result : OK — binary contains shim version 20260033"). No new `/EXPORT:` needed, none added.
- [x] **AC-6:** Full regression green: **Ft8 281/281** (280 baseline + the new D-012 test),
  **Daemon 193/193**, **Web 206/206**; `openspec validate --strict --all` **47/47**.
  Note: `F005RealCorpusSaturationCheck` (a local-only, gitignored-corpus-gated one-off check, not
  part of the "280 baseline") was run separately per AC-7 below, not as part of this count — see
  that section for why it cannot safely run interleaved with the rest of the suite on a machine
  where the corpus happens to be present locally.
- [x] **AC-7 (recommended, not blocking):** Real-corpus replay re-run performed — see §6.3 below
  for the result and why it is a legitimate pass, not a lingering defect, despite the raw number
  still looking large at first glance.

---

## 6. Implementation addendum — discovered-items not in the original plan

### 6.1 — Test-ordering hazard in the new D-012 regression test (fixed, see AC-3)

Covered under AC-3 above; not repeated here.

### 6.2 — `F005RealCorpusSaturationCheck` pollutes the shared suite when the corpus is present locally
(pre-existing risk, NOT part of D-012's own defect, NOT fixed here — flagged for awareness only)

Running the full `OpenWSFZ.Ft8.Tests` suite as one `dotnet test` invocation on a machine where
`artefacts/20260615_live_run/save` exists locally (as it does on this dev box) causes
`F005RealCorpusSaturationCheck` to actually replay the full 2,291-file corpus in-process instead
of skipping — and because that test class carries no `[Collection(HashTableSaturationCollectionDefinition.Name)]`
attribute, it can run in any position relative to the rest of the suite, including before classes
that assume an unsaturated table. Since the real corpus itself saturates the 256-slot hash table
(that is the entire premise of D-012), when it happens to run early it leaves the table
permanently full for every test that runs afterward, causing collateral failures unrelated to any
code defect:

- `HashTableRejectCountTests`'s two tests (which assume the counter reads `0` because "no other
  test in the assembly fills the table") both fail.
- `HashedCallsignResolutionTests`'s cross-cycle/same-cycle/never-announced tests fail because no
  new callsign can be stored any more.
- The dedicated saturation test itself fails its "entries #0–9 remain resolvable" assertion,
  because none of its own fresh entries could be stored either.

This was hit during this dev-task's own verification (a full-suite run showed 7 failures; a
re-run filtered to exclude `F005RealCorpusSaturationCheck` showed only the one genuine D-012 test
failure, which the `[TestCaseOrderer]` fix then resolved). It reproduces the same "shared,
never-reset native table" hazard class as the flaky-test issue already fixed by
`RunHashTableSaturationCollectionLastOrderer` (dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md)
— but for a *different* test, not yet folded into that pin.

**Not fixed as part of D-012** — this dev-task's scope is the native counting defect, not test
suite isolation, and `F005RealCorpusSaturationCheck` is explicitly documented as a one-off
verification tool "not yet decided whether to keep permanently." Recorded here so whoever next
touches this file (or decides F005RealCorpusSaturationCheck's fate) has the failure mode on
record. **CI is unaffected**: `artefacts/` is gitignored and never present there, so the test
always skips cleanly in CI regardless of this hazard — only a local run on a machine with the
corpus checked out can trigger it. Recommended follow-up if the file is kept long-term: either
add it to `HashTableSaturationCollectionDefinition` (accepting it becomes correlated with the
dedicated saturation test) or exclude it from default `dotnet test` runs (e.g. a trait/category
filter) and document that it must be run standalone.

### 6.3 — AC-7 real-corpus recheck result: 73,627 → 60,226, and why that is a PASS, not a new defect

Re-ran `F005RealCorpusSaturationCheck` alone (standalone, per §6.2's isolation requirement)
against `artefacts/20260615_live_run/save` on the post-fix build:

```
WAV files processed              : 2291 (0 failed/skipped)
Total decodes                    : 42,429
Decodes with '<' hash placeholder: 3,258
Reject count DELTA               : 60,226   (was 73,627 pre-fix — an 18% reduction)
```

At first glance this still looks "impossible" under this dev-task's own §1 framing ("there
cannot be more discarded Type-4-callsign-saves than there are decoded messages in total") — 60,226
still exceeds 42,429. **It is not a second defect; that framing was itself imprecise.**
Traced the real `ft8_lib/ft8/message.c` (upstream, `C:\Temp\ft8_lib_headers\ft8\message.c`) call
sites for `save_callsign()` (which calls `hash_if->save_hash` → our `cb_save_hash` →
`hash_table_add`) on the DECODE side (the shared, session-scoped table; the ENCODE-side call
sites at lines 251/713/723/864 use a separate per-call local table per design D1 and never touch
the shared counter):

- `unpack28` (line 838) — called from `ftx_message_decode_std`, **once for `call_to` and once for
  `call_de`**, i.e. up to **2 saves per decoded standard (Type 1/2) message**, not the 1 this
  dev-task's original framing assumed. (Special tokens like "CQ"/"DE"/"QRZ" and 22-bit hash
  references return early, before reaching the save — so not literally every field saves, but the
  large majority of real basecall fields do.)
- `unpack58` (line 892) — called from `ftx_message_decode_nonstd`, once for the Type 4 message's
  full-text callsign (this dev-task's original 1-save-per-Type-4-message assumption was correct
  for THIS message type alone).

So the true upper bound on `hash_table_add` calls across a session is **up to ~2× total decodes**
(dominated by standard-message `call_to`/`call_de` pairs, which vastly outnumber Type 4 messages
on a real band), not 1× as this dev-task's §1 arithmetic assumed. Against that corrected bound
(~84,858 for this corpus), 60,226 is entirely plausible: a real 9.5h multi-hour band recording
plausibly hears far more than 256 distinct stations, so once the table fills (early in the
session), essentially every later decode of a station not among the lucky first 256 — standard
call_to AND call_de alike, not just nonstandard ones — is a genuine, correctly-counted
reject-for-lack-of-room, repeated every time that station is re-heard (there is no eviction, by
design, D3).

**What the 73,627 → 60,226 reduction DOES confirm:** it is the exact, isolated effect of this
fix — repeat announcements of callsigns already resolved into the table (the specific D-012
overcounting bug) no longer inflate the counter. The remaining 60,226 is a different, legitimate
signal: the true count of genuinely-new (but already-full) callsign registration attempts, now
counted correctly per the spec's stated intent. Confirmed via the unit-level regression (§4.1/AC-3)
that the specific mechanism this dev-task targets is fixed; the real-corpus number's remaining
magnitude is fully explained by upstream `ft8_lib` behaviour outside this defect's scope, not
evidence of any remaining bug in `hash_table_add`.

**Not actioned, flagged for awareness only:** the F-005 spec's "Reject count reflects discarded
announcements once the table is full" wording is accurate but the surrounding design/dev-task
narrative in this repo (this file's own §1, and implicitly F-005's proposal/design docs) has
consistently described the metric as "Type 4 announcement" specific. It is not — it also reflects
discarded standard-callsign registrations. This is a documentation-precision nit for whoever next
touches F-005's design.md or the operator-facing description of this metric, not a code change;
out of scope for D-012.

---

## 7. References

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` lines 567–586 (`hash_table_add`, the defect) and
  545–553 (`hash_table_lookup`'s existing probe-limit-guard pattern this fix mirrors).
- `openspec/changes/f-005-hash-table-saturation-diagnostic/specs/hashed-callsign-resolution/spec.md`
  — "Reject count reflects discarded announcements once the table is full" scenario, whose
  "not already present in the table" wording the fixed code will finally satisfy.
- `openspec/changes/archive/2026-07-05-f-001-hashed-callsign-resolution/` — original design and
  implementation of `hash_table_add`; D-012 is a defect in that code, surfaced by F-005.
- `tests/OpenWSFZ.Ft8.Tests/HashedCallsignResolutionTests.cs` — existing saturation test to
  extend/companion.
- `tests/OpenWSFZ.Ft8.Tests/F005RealCorpusSaturationCheck.cs` — QA's one-off real-corpus
  verification harness that found this; points at `artefacts/20260615_live_run/save`
  (gitignored, local-only, NFR-021).
- QA review + live verification of `feat/f-005-hash-table-saturation-diagnostic`, 2026-07-06 —
  full session: unit-level review found the F-005 change itself sound; a follow-up dev-task
  (`dev-tasks/2026-07-06-f-005-status-endpoint-test-coverage.md`) closed a Web-layer test-coverage
  gap; this defect was found only after replaying a genuine real-world corpus, which is the
  reason that step was worth doing despite the wiring already being unit-tested.
