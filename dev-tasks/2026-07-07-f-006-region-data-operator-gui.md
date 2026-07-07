# DEV TASK — F-006: add the operator-facing GUI the change was missing (status + refresh + lookup)

**Date:** 2026-07-07
**Prepared by:** QA Engineer
**Found during:** QA review of `feat/f-006-region-lookup-country-file-refresh` (uncommitted working
tree at review time), before merge.
**Severity:** Blocker — not a defect in the code that exists, but the change as submitted ships a
backend capability an operator has no way to reach. Confirmed directly by the Captain (fresh
compile, cleared browser cache, no control found anywhere in the app) and traced to a scope
regression: an earlier exploration session (not captured in any committed artifact — the proposal's
own GitHub issue thread and this project's memory notes were both checked and contain no record of
it) had already decided a GUI affordance was necessary, specifically because
`callsign-regions.json` is an operator-maintained working document. `proposal.md`/`design.md` as
submitted instead declare "no GUI, deferred to fast-follow" as a Non-Goal — that text needs
correcting, not just supplementing.
**OpenSpec change:** `openspec/changes/f-006-region-lookup-country-file-refresh/` — this change has
**not** merged yet, so this is a same-branch expansion of its own scope, not a follow-up change.
**Branch:** continue on the existing `feat/f-006-region-lookup-country-file-refresh` branch — do
not open a new one.

---

## 1. Context

The backend half of F-006 (`ICountryFileSource`, `ICountryFileConverter`,
`CallsignRegionStore.SaveAsync`, `POST /api/v1/region-data/refresh`) is sound — independently
verified during review (901/901 tests green, `openspec validate --strict` clean, live end-to-end
refresh against the real country-files.com release confirmed in the change's own task 5.2). That
part does not need rework.

What's missing is any way for an operator to *use* it. The Captain, the developer, and I discussed
three tiers of GUI investment (see the review conversation for full reasoning); the Captain has
selected the middle tier:

1. ~~Refresh button only~~ — rejected as too thin (no visibility into whether it worked).
2. **Status summary** (entry count, last-refresh outcome/timestamp/release version) — **in scope**.
3. **Read-only lookup tool** (type a callsign, see what it currently resolves to, including CQ/ITU
   zone) — **in scope**.
4. ~~Full view + add/edit/delete individual records, persisted~~ — explicitly **out of scope**.
   29,013 entries after a real refresh is not a hand-editable table the way the 5–10-row
   Frequencies tab is, `SaveAsync` is a whole-list atomic replace with no per-entry CRUD contract,
   and enabling manual edits would require a provenance/merge-on-refresh data-model change
   (distinguishing operator-edited entries from country-file-sourced ones) that is its own change,
   not a GUI addition to this one. Do not build toward this in the current task — no provenance
   field, no per-entry endpoints.

Existing precedent to mirror, all found directly in the current codebase:

- `web/js/settings.js` lines 662–691 (`catRetryBtn` click handler) — the exact
  disable-button/relabel/await-POST/show-feedback/re-enable-in-`finally` pattern a "Refresh region
  data" button should follow. `showFeedback`/`clearFeedback` (lines 1004–1012) are generic helpers
  shared across the form, not CAT-specific.
- `web/js/settings.js` lines 976–984 (`logsOpenFullBtn`) and `web/settings.html` lines 549–566 (Logs
  tab) — pattern for a read-only diagnostic panel fed by a `GET` endpoint.
- `web/settings.html` lines 521–547 (Frequencies tab) — the closest sibling capability (an
  operator-editable list backed by its own REST endpoint) already ships with a full GUI tab in this
  same file. This is the concrete fact that undercuts the submitted proposal's "backend proven
  first, GUI is fast-follow" reasoning — the nearest analogous feature in this exact codebase was
  never held to that bar.

---

## 2. Actions

### 2.1 — Correct the OpenSpec artifacts first

- `proposal.md`: remove the "No GUI affordance ships in this change... deferred to a fast-follow
  change" Non-Goal. Replace with an accurate statement of scope: status summary + refresh trigger +
  read-only lookup tool ship in this change; full CRUD editing of individual entries is the
  deferred item.
- `design.md`: add a decision entry (mirroring the existing Decision 1–5 style) documenting *why*
  the GUI scope landed where it did — reference the three-tier discussion above so a future reader
  doesn't have to reconstruct it. Also add a short Context note that the original "no GUI" framing
  was a scope regression against an earlier (uncaptured) decision, corrected during QA review before
  merge — worth stating plainly so this doesn't happen again silently.
- `tasks.md`: add a new numbered section (e.g. "## 6. Operator-facing GUI") covering the items
  below, so the task list actually reflects what shipped.
- `specs/region-lookup-data-refresh/spec.md`: add ADDED requirements/scenarios for:
  - An operator can view the current region-data status (entry count, last-refresh outcome) from
    the running daemon's GUI.
  - An operator can look up how a specific callsign currently resolves (entity, continent, CQ/ITU
    zone if present, or "no match") for diagnostic purposes, without needing to decode a live
    signal.
  - Run `openspec validate --strict` on the change again after these edits before requesting
    re-review — do not assume the earlier clean run still applies once requirements change.

### 2.2 — Backend: region-data status endpoint

Add `GET /api/v1/region-data/status` to `WebApp.cs`, alongside the existing refresh endpoint
(566–628). Suggested response shape (adjust names to taste, but keep it in `AppJsonContext.cs`
following the `RegionRefreshResponse` registration pattern at line 57):

```csharp
public sealed record RegionDataStatusResponse(
    int      EntryCount,
    bool     HasRefreshedThisSession,
    DateTimeOffset? LastRefreshUtc,
    bool?    LastRefreshSucceeded,
    string?  LastReleaseVersion,
    string?  LastErrorMessage);
```

- `EntryCount` — always available (`regionStore.Entries.Count`), regardless of whether a refresh
  has ever run this session (seed data or a previously-saved file both count).
- The `LastRefresh*`/`LastError*` fields describe *this daemon session's* refresh history only (no
  new persistence needed — resets on restart, which is fine and consistent with "refresh is never
  automatic").
- Implementation: a simple mutable local variable captured by both the existing
  `POST /api/v1/region-data/refresh` handler and this new `GET` handler (same closure-capture
  pattern already used for `regionRefreshLogger` at line 568) — update it on both the success path
  (line ~604, after `SaveAsync`) and the two existing failure paths (lines 582–587, 597–602). No
  change to `ICallsignRegionStore`/`CallsignRegionStore` needed for this endpoint.
- Test: extend `RegionDataRefreshApiTests.cs` (or a new sibling file) covering: status before any
  refresh (entry count reflects seed/loaded data, `HasRefreshedThisSession = false`), status after a
  successful refresh, and status after a failed refresh (fetch and conversion failure cases both) —
  mirroring the existing three-test structure in that file.

### 2.3 — Backend: read-only lookup endpoint

Add `GET /api/v1/region-data/lookup?callsign={token}` to `WebApp.cs`. This needs the matched
entry's CQ/ITU zone, which today's `ICallsignRegionStore.TryGetRegion` doesn't expose (it returns
`RegionInfo`, which only carries `Continent`/`Entity`/`Synthetic` — see
`CallsignRegionEntry.cs` lines 49–52). Two ways to close that gap; pick whichever you think fits
better, but don't duplicate the longest-prefix-match logic in `WebApp.cs` as a third option:

- **(a) Extend `RegionInfo` itself** with nullable `CqZone`/`ItuZone` fields, and update
  `CallsignRegionStore.TryGetRegion`'s return (line 59) and `FixedCallsignRegionStore`'s mirror
  (line 39) to populate them from `best`. Cheapest change — only two construction sites in the
  entire codebase construct `RegionInfo` directly (confirmed by a repo-wide search), and the
  decode-result WebSocket/REST payload gains two additional nullable fields that existing frontend
  code (`web/js/main.js`) can simply ignore. No interface change.
- **(b) Add a new `ICallsignRegionStore` method** (e.g. `CallsignRegionEntry? TryGetMatchingEntry(string
  callsignToken)`) that returns the full matched entry, and have `TryGetRegion` call it internally
  (single source of truth for the matching logic). Keeps the decode-result payload shape completely
  untouched, at the cost of an interface change touching all four implementations
  (`CallsignRegionStore`, `FixedCallsignRegionStore`, `ThrowingCallsignRegionStore`,
  `TestCallsignRegionStore` in `RegionDataRefreshApiTests.cs`).

Response shape, e.g.:

```csharp
public sealed record RegionLookupResponse(
    bool     Matched,
    string?  Entity,
    string?  Continent,
    int?     CqZone,
    int?     ItuZone,
    bool     Synthetic);
```

- No match → `Matched: false`, all other fields `null`/`false` — mirrors how the decode pipeline
  already treats a lookup miss as "Unknown," just made explicit for this diagnostic view.
- Test: new test file or addition to `CallsignRegionStoreTests.cs` (if you take approach (a) or
  (b)) covering a known prefix match (zones populated), the synthetic `Q`-series entry (zones
  `null`, `Synthetic: true`), and an unmatched token (`Matched: false`) — plus an endpoint-level test
  in `OpenWSFZ.Web.Tests` following `RegionDataRefreshApiTests.cs`'s conventions.

### 2.4 — Backend: fix the refresh endpoint's error-handling asymmetry (bundle this in — same PR)

`POST /api/v1/region-data/refresh` (`WebApp.cs` line ~604) wraps the fetch and conversion steps in
matching try/catch → `regionRefreshLogger.LogWarning` → `Results.Problem(502, ...)` blocks, but the
subsequent `await regionStore.SaveAsync(converted, ct)` call has no equivalent guard. A write
failure (disk full, permissions, AV lock) would propagate as an unhandled 500 instead of the same
logged-and-reported pattern its two siblings get. Data integrity isn't at risk (`SaveAsync` is
atomic), but wrap this call the same way for consistency, and add a test forcing a `SaveAsync`
failure (e.g. a fake `ICallsignRegionStore` whose `SaveAsync` throws) to `RegionDataRefreshApiTests.cs`
to close the one untested path in that file.

### 2.5 — Frontend: GUI section

Add a new tab to `web/settings.html` (recommended: its own "Region data" tab, mirroring the
Frequencies/Logs tab markup at lines 521–566 — the combination of a status summary, a refresh
button, and a lookup tool is enough distinct content to justify its own tab rather than crowding
into Logging, but this is your and the Captain's call, not a hard requirement). Contents:

1. **Status summary** (read-only text, populated from `GET /api/v1/region-data/status` on page
   load): entry count, and either "Not refreshed this session — using seed/existing data" or
   "Last refreshed: {timestamp}, release {version}, {N} entries" / "Last refresh attempt failed:
   {error}" depending on the response.
2. **Refresh button**: mirror `catRetryBtn`'s pattern exactly (`web/js/settings.js` lines 662–691)
   — disable + relabel while in flight, `postRegionDataRefresh()`, `showFeedback` on
   success/failure, re-fetch and re-render the status summary on success, re-enable in `finally`.
3. **Lookup tool**: a text input + button + result panel. On click, call the new lookup endpoint
   and render Entity/Continent/CQ zone/ITU zone/Synthetic, or a clear "No match — resolves to
   Unknown" message. No auto-refresh/polling needed (unlike the Logs tail) — this is an on-demand
   diagnostic, not a live view.

`web/js/api.js` additions (follow the existing `fetchJson`-based patterns, e.g. `getFrequencies`/
`postFrequencies` at lines 132–147): `getRegionDataStatus()`, `postRegionDataRefresh()`,
`getRegionDataLookup(callsign)`.

`web/js/settings.js` additions: element refs, click handlers, and initial status population on
load — following the existing `const ... = document.getElementById(...)` + event-listener
conventions used throughout the file.

### 2.6 — Manual verification (no frontend test harness exists in this repo)

This repo has no `*.spec.js`/Playwright coverage for `settings.js` — same gap noted in the
`2026-07-05-settings-logs-tab-panel-too-narrow.md` dev-task. Verify manually and attach
before/after screenshots to the PR, matching that task's convention:

- Fresh load: status summary shows the current entry count and "not refreshed this session."
- Click Refresh: button disables/relabels, then shows success feedback and an updated status
  summary with entry count, release version, and timestamp.
- Simulate a refresh failure (e.g. temporarily point at an unreachable host, or use a network
  throttle) and confirm the button re-enables with a clear error message, and the status summary
  does not claim a false success.
- Lookup tool: try a known real prefix (e.g. one from `CallsignRegionDefaults`), the synthetic
  `Q`-series prefix, and an unmatched token — confirm each renders correctly.
- Confirm the other tabs are not visually regressed by the new tab (same check as the prior
  Logs-tab-width dev-task — screenshot comparison).

---

## 3. Acceptance Criteria

- [ ] **AC-1** `openspec validate --strict` passes on the updated change, including the corrected
  Non-Goal text and the new ADDED requirements/scenarios in `region-lookup-data-refresh/spec.md`.
- [ ] **AC-2** `GET /api/v1/region-data/status` returns entry count and last-refresh
  outcome/timestamp/release-version/error fields correctly in all three states: never refreshed
  this session, refreshed successfully, refresh failed. Covered by new tests.
- [ ] **AC-3** `GET /api/v1/region-data/lookup` correctly resolves a known real prefix (with zones),
  the synthetic `Q`-series entry (zones `null`, `Synthetic: true`), and an unmatched token
  (`Matched: false`). Covered by new tests at both the store/logic level and the endpoint level.
- [ ] **AC-4** `POST /api/v1/region-data/refresh`'s `SaveAsync` call is now wrapped consistently
  with its fetch/convert siblings; a forced `SaveAsync` failure is covered by a new test.
- [ ] **AC-5** The new GUI section renders, the refresh button follows the disable/relabel/feedback
  pattern, the lookup tool works for all three cases above, and the status summary updates after a
  successful refresh — confirmed manually with before/after screenshots attached to the PR.
- [ ] **AC-6** No existing test regresses; full solution suite reported (was 901/901 at last review;
  expect this number to grow with the new tests above).
- [ ] **AC-7** No provenance field, per-entry CRUD endpoint, or merge-on-refresh logic was added —
  confirm the scope stayed at status + refresh + lookup, not full editing.

---

## 4. References

- Prior QA review of `feat/f-006-region-lookup-country-file-refresh`, 2026-07-07 — full backend
  review (converter, HTTP source, store `SaveAsync`, refresh endpoint) found sound and independently
  verified (901/901 tests, `openspec validate --strict` clean, live refresh confirmed per the
  change's own task 5.2). The GUI gap and the `SaveAsync` error-handling asymmetry were the two
  findings from that review.
- `openspec/changes/f-006-region-lookup-country-file-refresh/proposal.md` — the Non-Goal text to
  correct ("No GUI affordance ships in this change...").
- `openspec/changes/f-006-region-lookup-country-file-refresh/design.md` — Decisions 1–5 (style to
  mirror for the new decision entry), design.md's own Addendum 2 (the synthetic-entry
  `SaveAsync` guarantee — relevant context for why the lookup tool's synthetic-entry test case
  matters).
- `src/OpenWSFZ.Web/WebApp.cs` lines 566–628 — the existing refresh endpoint to extend.
- `src/OpenWSFZ.Web/AppJsonContext.cs` line 57 — `RegionRefreshResponse` registration pattern to
  follow for the two new response types.
- `src/OpenWSFZ.Abstractions/CallsignRegionEntry.cs` lines 27–52 — `CallsignRegionEntry`/`RegionInfo`
  shapes; the fork point for the lookup endpoint's CQ/ITU zone data (§2.3 options (a)/(b)).
- `src/OpenWSFZ.Daemon/CallsignRegionStore.cs` line 59, `tests/OpenWSFZ.Ft8.Tests/FixedCallsignRegionStore.cs`
  line 39 — the two existing `RegionInfo` construction sites.
- `web/js/settings.js` lines 662–691 (`catRetryBtn`), 976–984 (`logsOpenFullBtn`), 1004–1012
  (`showFeedback`/`clearFeedback`) — GUI patterns to mirror.
- `web/settings.html` lines 521–566 (Frequencies and Logs tabs) — GUI markup patterns to mirror.
- `dev-tasks/2026-07-05-settings-logs-tab-panel-too-narrow.md` — precedent for this repo's
  manual-screenshot verification convention in the absence of a frontend test harness.
