## 1. Country-file conversion components

- [x] 1.1 Add `ICountryFileSource` (fetch current release from country-files.com over HTTPS,
      returning XML text ready for `ICountryFileConverter`) and a concrete HTTP-based
      implementation. Per design.md's Addendum: the release is a ZIP archive
      (`https://www.country-files.com/cty/download/cty_plist.zip`, a stable URL that always serves
      the current release) containing `cty.plist` (an XML property list); the HTTP implementation
      downloads the ZIP and extracts `cty.plist` in-memory before returning its XML text. This
      ZIP-extraction step is fully internal to the HTTP implementation — the interface contract
      itself is unchanged (still XML text in, on success).
- [x] 1.2 Add `ICountryFileConverter` (pure function: XML document → `IReadOnlyList<
      CallsignRegionEntry>`), with a mode flag/parameter selecting whether individual-callsign
      (`=`-flagged) source rows are dropped (`prefixBlocksOnly: true`, for
      `CallsignRegionDefaults.cs` regeneration) or passed through (default, for the runtime
      refresh path).
- [x] 1.3 Converter validates required per-entry fields (entity name, CQ zone, ITU zone,
      continent, prefix) are present and throws/reports a clear error on an unexpected or
      malformed XML shape, rather than silently defaulting missing data to `null`.
- [x] 1.4 Unit tests for the converter using small, hand-written fixture XML documents (fictional
      Q-prefix/placeholder entities and prefixes only — no real country-file content copied into
      a committed test fixture, per NFR-021). Cover: normal prefix-block entry, an
      individual-callsign-flagged entry (both included and dropped depending on mode), and a
      malformed/incomplete entry producing a clear conversion failure.
      (`CountryFilePlistConverterTests.cs`, 12 tests.)
- [x] 1.5 Unit tests for `ICountryFileSource`'s HTTP implementation using a fake/mocked HTTP
      handler (no test depends on live network access to country-files.com) — cover success
      (a small in-memory fixture ZIP containing a fixture `cty.plist`), non-success HTTP status,
      network-failure/timeout cases, and a malformed-ZIP/missing-`cty.plist`-entry case (per
      design.md's Addendum, the HTTP implementation unzips internally).
      (`HttpCountryFileSourceTests.cs`, 9 tests.)

## 2. Store support for runtime replacement

- [x] 2.1 Add `SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken
      cancellationToken = default)` to `ICallsignRegionStore`, mirroring `IFrequencyStore
      .SaveAsync`'s contract.
- [x] 2.2 Implement `CallsignRegionStore.SaveAsync` by reusing the existing private atomic
      write-to-temp-then-rename logic (currently `WriteAsync`, called today only from
      `LoadAsync`'s missing-file path); update `Entries` only after a successful write.
- [x] 2.3 Add/extend `tests/OpenWSFZ.Daemon.Tests/CallsignRegionStoreTests.cs` to cover:
      successful `SaveAsync` updates both the in-memory table and the on-disk file; a failed
      write (e.g. simulated I/O error) leaves the previous in-memory table and on-disk file
      unchanged.
- [x] 2.4 Update `tests/OpenWSFZ.Ft8.Tests/FixedCallsignRegionStore.cs` (the test fake) if it
      needs a no-op/trivial `SaveAsync` implementation to satisfy the updated interface.
      (Implemented as a real, functional in-memory replacement rather than a bare no-op — trivial
      either way, and slightly more useful to any future test. `ThrowingCallsignRegionStore` also
      updated, throwing per its existing contract.)
- [x] 2.5 **(Discovered during task 5.2's live verification, not originally scoped.)**
      `CallsignRegionStore.SaveAsync` guarantees the mandatory synthetic `Q`-series entry
      (region-lookup's unconditional "Synthetic Q-prefix callsigns resolve to a distinct synthetic
      region" requirement) survives any caller's replacement list, appending it from
      `CallsignRegionDefaults.Entries` when absent. A real country-file release naturally contains
      no `Q`-series entry, so without this the first live refresh would have silently regressed
      that pre-existing requirement. See design.md's Addendum 2. Regression tests added to
      `CallsignRegionStoreTests.cs` (preservation + no-duplication cases); re-verified live after
      the fix (task 5.2).

## 3. Refresh endpoint

- [x] 3.1 Add `POST /api/v1/region-data/refresh` to `WebApp.cs`, following the existing endpoint
      conventions (see `POST /api/v1/frequencies`, `POST /api/v1/prop-modes`) — composes
      `ICountryFileSource` → `ICountryFileConverter` (pass-through mode) → `ICallsignRegionStore
      .SaveAsync`.
- [x] 3.2 On fetch failure: log a Warning, leave existing region data untouched, return a
      non-success response to the caller. (`Results.Problem`, HTTP 502.)
- [x] 3.3 On conversion failure: log a Warning, leave existing region data untouched, return a
      non-success response to the caller. (`Results.Problem`, HTTP 502.)
- [x] 3.4 On success: return a response indicating success (consider including a summary count of
      converted entries and/or the source release's version/date if present in the XML — exact
      shape left to implementer's judgement per design.md's Open Questions).
      (`RegionRefreshResponse(Success, EntryCount, ReleaseVersion)` — `EntryCount` reports the
      actual post-save active count per task 2.5, not the raw pre-save converted count;
      `ReleaseVersion` best-effort-extracted from the release's `VERyyyymmdd` marker entry.)
- [x] 3.5 Register `ICountryFileSource`/`ICountryFileConverter` in DI alongside the existing
      `ICallsignRegionStore` registration in `Program.cs`.
- [x] 3.6 Integration test (or endpoint-level test consistent with this project's existing
      `WebApp.cs` endpoint test conventions) exercising the refresh endpoint end-to-end against a
      faked `ICountryFileSource`, covering success, fetch-failure, and conversion-failure paths.
      (`RegionDataRefreshApiTests.cs`, 3 tests.)

## 4. Committed fallback data (optional, additive)

- [x] 4.1 Decide whether to expand `CallsignRegionDefaults.cs` in this change (optional per
      design.md's Open Questions) using the `prefixBlocksOnly` conversion mode against a snapshot
      of the current release.
      **Decision: not expanded in this change.** `CallsignRegionDefaults.cs` is left exactly as
      today (~38 hand-curated entries); the refresh mechanism alone already lets an operator reach
      full DXCC coverage immediately on first use, which was the proposal's actual goal. Expanding
      the committed fallback is a separate, purely additive follow-up with its own review surface
      (regenerating ~38+ hand-picked rows from a live snapshot) and isn't required for this
      change's capability to work end-to-end.
- [ ] 4.2 If expanding: regenerate `CallsignRegionDefaults.cs`'s entries, preserving the existing
      mandatory synthetic `Q`-series entry (NFR-021) unchanged.
      **Not applicable this change** — see 4.1's decision. Left for a future follow-up change.
- [x] 4.3 Add a regression test asserting no entry in `CallsignRegionDefaults.Entries` is
      derived from an individual-callsign (`=`-flagged) source row — i.e. every non-synthetic
      entry represents a genuine prefix block, not a specific full callsign. This test protects
      the git-committed fallback specifically (per design.md Decision 2) and MUST pass regardless
      of whether Task 4.1/4.2 are done this change or a follow-up.
      **Scope note**: this is a plain, fast, in-memory unit test over the static compiled-in
      `CallsignRegionDefaults.Entries` list (a shape assertion, e.g. prefix-block length/charset
      bounds vs. full-callsign shape) — no network access, no corpus fixture, no R&R-harness
      replay, no off-air data, and no multi-hour run of any kind. It runs in milliseconds as part
      of the normal `dotnet test` pass.
      (`CallsignRegionDefaultsTests.cs`, 12 tests — includes a sanity check of the shape heuristic
      itself against known prefix-block and known full-callsign shapes.)

## 5. Verification

- [x] 5.1 Run the full existing test suite; confirm no existing `region-lookup` requirement's
      test coverage regresses (existing `CallsignRegionStoreTests`, decoder tests referencing
      region lookup, etc.). Full solution suite: 901/901 passed, 0 failed.
- [x] 5.2 Manually exercise `POST /api/v1/region-data/refresh` against the live
      country-files.com XML release at least once during development, confirming a real,
      successful end-to-end refresh (this is the one point in the workflow where live-network
      verification is appropriate, since it's exactly what the feature does in production).
      Ran via a disposable scratch harness (not committed) hitting the real endpoint over loopback
      HTTP with the real `HttpCountryFileSource`/`CountryFilePlistConverter`/`CallsignRegionStore`:
      fetched and converted 29,012 real entries from release CTY-3622 (`VER20260629`), installed
      29,013 active (including the guaranteed synthetic entry, task 2.5), verified real-prefix
      lookups (`3A2XYZ`→Monaco/EU, `K1ABC`→United States/NA, `VE3XYZ`→Canada/NA,
      `PY2XYZ`→Brazil/SA) and the synthetic lookup (`Q1TEST`→"Synthetic (R&R Study)") all resolved
      correctly, and confirmed the on-disk `callsign-regions.json` was written (5.76 MB). This run
      is also what surfaced task 2.5's defect before the fix (first run: `Q1TEST`→"Unknown").
- [x] 5.3 Confirm `openspec validate --strict` passes for this change before requesting review.

## 6. Operator-facing GUI

**(Added post-review — see design.md's Context correction and Decision 6.)** The backend-only
submission of this change left an operator with no way to trigger a refresh, confirm it worked, or
inspect what the region table currently resolves for a given callsign. This section closes that
gap at the scope the Captain selected: status summary + refresh trigger + read-only lookup tool.
Full per-entry CRUD editing remains explicitly out of scope (Decision 6).

- [x] 6.1 Add `GET /api/v1/region-data/status` to `WebApp.cs`, returning entry count and
      this-session refresh history (`hasRefreshedThisSession`, `lastRefreshUtc`,
      `lastRefreshSucceeded`, `lastReleaseVersion`, `lastErrorMessage`) via a mutable
      closure-captured state variable updated by both the refresh endpoint's success and failure
      paths. No new persistence — resets on daemon restart, consistent with "refresh is never
      automatic."
- [x] 6.2 Wrap `POST /api/v1/region-data/refresh`'s `SaveAsync` call in the same
      log-and-report-502 pattern its fetch/convert siblings already use, closing the one
      untested/unguarded failure path in that endpoint (disk full, permissions, AV lock).
- [x] 6.3 Extend `RegionInfo` with nullable `CqZone`/`ItuZone` fields (design.md's option (a) —
      cheaper than a new store method, no interface change); update
      `CallsignRegionStore.TryGetRegion` and `FixedCallsignRegionStore.TryGetRegion` to populate
      them from the matched entry.
- [x] 6.4 Add `GET /api/v1/region-data/lookup?callsign={token}` to `WebApp.cs`, returning
      `Matched`/`Entity`/`Continent`/`CqZone`/`ItuZone`/`Synthetic` for the supplied callsign token
      via `ICallsignRegionStore.TryGetRegion` — the same matching logic the decode pipeline uses,
      not a duplicated implementation.
- [x] 6.5 Add a "Region data" tab to `web/settings.html` (mirroring the Frequencies/Logs tab
      markup) with: a status summary populated from 6.1 on page load, a refresh button following
      `catRetryBtn`'s disable/relabel/await/feedback/re-enable pattern, and a lookup tool
      (text input + button + result panel) calling 6.4.
- [x] 6.6 Add `getRegionDataStatus()`, `postRegionDataRefresh()`, `getRegionDataLookup(callsign)`
      to `web/js/api.js`; wire element refs, click handlers, and initial status population into
      `web/js/settings.js`.
- [x] 6.7 Tests: extend `RegionDataRefreshApiTests.cs` with status-endpoint coverage (never
      refreshed, refreshed successfully, refresh failed), lookup-endpoint coverage (known prefix
      with zones, synthetic entry, unmatched token), and a forced-`SaveAsync`-failure case for
      6.2. Extend `CallsignRegionStoreTests.cs` with `TryGetRegion` zone-population coverage.
- [ ] 6.8 Manual verification (no frontend test harness exists in this repo — see
      `dev-tasks/2026-07-05-settings-logs-tab-panel-too-narrow.md` for the established
      screenshot-based convention this task follows): fresh load, refresh success, refresh
      failure, lookup tool (known prefix / synthetic / unmatched), and no visual regression to
      other tabs. Before/after screenshots attached to the PR.
      **Partial**: no headless-browser tool was available in the implementing session, so the
      functional wiring was verified end-to-end at the HTTP layer instead of via browser
      screenshots — a live daemon was launched, `POST /api/v1/region-data/refresh` was run for
      real against country-files.com (29,013 entries installed, release `20260629`), and
      `GET .../status` and `GET .../lookup` were confirmed to return exactly the shapes
      `settings.js` consumes (known prefix with zones, synthetic entry with null zones, unmatched
      → `Matched: false`) both before and after the refresh; `settings.html`/`settings.js`/`api.js`
      were confirmed served correctly with the new tab markup and functions present. The one
      thing **not** independently confirmed is the actual rendered appearance in a browser
      (layout, no visual regression to other tabs) — screenshots per this task's own convention
      still need to be captured by a human reviewer before merge.
- [x] 6.9 Run `openspec validate --strict` again after the spec edits below — do not assume the
      earlier clean run still applies once requirements changed.
