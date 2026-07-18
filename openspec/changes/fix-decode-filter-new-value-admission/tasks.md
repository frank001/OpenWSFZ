## 1. `IDecodeFilterStore` — admission API and internal tracking

- [x] 1.1 Add `DecodeFilterState? AdmitNewValues(DecodeResult decode)` to
      `src/OpenWSFZ.Abstractions/IDecodeFilterStore.cs`, documented per design.md Decision 1.
- [x] 1.2 In `DecodeFilterStore` (`src/OpenWSFZ.Web/WebApp.cs`), add four private
      `HashSet<T>` fields tracking entities/continents/CQ-zones/ITU-zones seen this session
      (design.md Decision 2), plus a private `readonly object _lock` guarding both `Set` and the
      new method.
- [x] 1.3 Implement `AdmitNewValues`: for each of the decode's four resolved attribute values not
      yet in that axis's "seen" set, record it as seen; if the axis's current allow-list is
      non-null AND non-empty, build a **new** `HashSet<T>` (copy + add — never mutate the
      referenced set in place, design.md Decision 3) and stage a `with`-updated
      `DecodeFilterState`. Do NOT admit into a `null` axis (no-op, matches existing default) or an
      explicitly empty (`[]`) axis (design.md Decision 5). Return the updated state only if at
      least one axis actually changed; otherwise return `null`. All reads/writes of `_current`
      and the seen-sets happen under `_lock`.
- [x] 1.4 Confirm (do not modify) that `DecodeFilterEvaluator.IsVisible` / `isDecodeVisible` and
      `DecodeFilterState`'s wire shape are untouched by this change.

## 2. Daemon wiring — decode pump hook and broadcast

- [x] 2.1 Add `DecodeFilterEventBus` (`src/OpenWSFZ.Web/DecodeFilterEventBus.cs`), mirroring
      `DecodeEventBus`'s shape exactly (`appScope`-guarded façade over
      `WebSocketHub.BroadcastDecodeFilterChanged`).
- [x] 2.2 In `src/OpenWSFZ.Daemon/Program.cs`, construct
      `var decodeFilterEventBus = new DecodeFilterEventBus(appScope);` alongside the existing
      `decodeEventBus` (near line 301), before `WebApp.Create`.
- [x] 2.3 Resolve `IDecodeFilterStore` inside the `ApplicationStarted` callback that starts the
      decode pump (alongside where `stoppingToken` is captured, ~line 703), via
      `app.Services.GetRequiredService<IDecodeFilterStore>()`.
- [x] 2.4 In the decode pump's `await foreach` loop, after computing `visibleResults` and before
      the `qsoAnswererChannel`/`qsoCallerChannel`/`externalReportingChannel` fan-out (~line
      752–758): call `decodeFilterStore.AdmitNewValues(r)` for each `r` in `visibleResults`,
      track the last non-null returned state, and if any admission occurred, call
      `decodeFilterEventBus.Publish(finalState)` **once** per batch (coalesced, not once per
      admitted value or per decode — design.md Decision 4 / Risks).
- [x] 2.5 Confirm this hook runs identically whether or not any browser tab is connected
      (no conditional on `WebSocketHub.HasClients` gating the admission decision itself — only
      the broadcast is a no-op with zero clients, admission must still happen).

## 3. Unit tests (`OpenWSFZ.Web.Tests`)

- [x] 3.1 First-seen value on a narrowed-but-non-empty axis is admitted (all four attribute axes,
      independently).
- [x] 3.2 First-seen value on an untouched (`null`) axis is a no-op: `AdmitNewValues` returns
      `null`, axis remains `null`.
- [x] 3.3 First-seen value on an explicitly empty (`[]`) axis is NOT admitted: axis remains `[]`,
      `AdmitNewValues` returns `null` for that axis's contribution (design.md Decision 5 /
      Requirement Scenario "An explicitly empty axis never auto-admits").
- [x] 3.4 An already-seen, already-excluded value is never re-admitted on a later decode.
- [x] 3.5 A decode touching multiple axes simultaneously (e.g. new entity AND new CQ zone in one
      `DecodeResult`) admits both in a single call, returning one combined updated state.
- [x] 3.6 Concurrency: parallel `AdmitNewValues`/`Set` calls from multiple threads do not corrupt
      the underlying `HashSet<T>` instances or lose an admission (e.g. `Task.WhenAll` over many
      concurrent calls, then assert final state contains every expected value).
  - **Flake found and fixed post-merge-prep** (Captain caught it live): the original single test
    interleaved 20 `Set()` calls built as `store.Set(store.Current with { ... })` — an unlocked
    read-modify-write. Since `Set()` is a documented whole-object replace (last-write-wins,
    design.md Decision 3's Risks/Trade-offs), a `Set()` call that captured a stale snapshot could
    silently overwrite concurrently-landed `AdmitNewValues` admissions. Reproduced deterministically
    (failed on iteration 0 of a 40x in-process stress loop, `count=198` vs. expected `201`) — this
    was a bug in the test's assertion, not in `DecodeFilterStore`. Split into two tests: pure
    `AdmitNewValues` concurrency (no admission may ever be lost — asserted and stress-verified 40x
    with zero failures) and `AdmitNewValues`-racing-`Set()` (asserts no throw/corruption only, not
    survival of every admission, matching the documented last-write-wins contract) — also
    stress-verified 40x with zero failures. Full solution suite green afterward (1297 tests).
- [x] 3.7 Give every new test's `[Fact]`/`[Theory]` a `DisplayName` (or method name, per this
      project's existing convention — check `DecodeFilterEvaluatorTests.cs` for the pattern used)
      leading with `"FR-061: "` (Gate G3 — see §6.1 below for the new requirement ID).

## 4. Frontend — comment/doc cleanup only (no behavioral change)

- [x] 4.1 Update `web/js/main.js`'s `FILTER_AXES`/`seenEntities`-adjacent comments to state plainly
      that this client-side tracking is for popup checkbox candidates only and is no longer
      load-bearing for filter correctness — the daemon is authoritative for admission. No
      functional change to `main.js`, `decodeFilter.js`, or `decodeFilter.test.js`.
- [ ] 4.2 Manually verify (real browser) that the existing "any `decodeFilterChanged` event
      re-evaluates every rendered row" behavior already picks up a daemon-driven auto-admission
      with no code change — confirms the "no delta needed for `web-frontend`" claim in
      proposal.md is actually true, not just assumed.
  - **Blocked on human action, not code:** this repo has no browser-automation tooling (no
    Playwright/Selenium/WebDriver anywhere), so this can't be driven by the implementer. Partial
    substitute evidence gathered instead: (a) code inspection of `main.js`'s `decodeFilterChanged`
    WS handler shows it merges `event.payload` into `currentDecodeFilter` and calls
    `reapplyDecodeFilterToRenderedRows()`/`refreshOpenFilterPopupIfAny()` unconditionally, with no
    branch on what triggered the event; (b) the existing
    `DecodeFilterWebSocketBroadcastTests.PostDecodeFilter_BroadcastsDecodeFilterChangedEvent`
    integration test proves the exact frame shape a daemon-driven admission broadcast also uses.
    Genuinely open — Captain to click through in a real browser before archiving.

## 5. Live verification (standing policy)

- [x] 5.1 Add a new scenario to `qa/decode-filter-synth-verify/live_verify_9_axes.py`: narrow a
      DXCC-entity (or continent/CQz/ITz) axis to exclude at least one already-seen value, then
      inject a synthetic decode for a station resolving to an entity/continent/zone never before
      seen this run, and assert it is (a) visible in the decode table and (b) still engageable by
      the active QSO controller service — not silently excluded.
- [x] 5.2 Re-run `qa/decode-filter-synth-verify/live_verify_9_axes.py` in full (real isolated
      daemon, real virtual-audio-cable injection, real native decoder, real API) per the standing
      `decode-panel-filtering` live-verification policy. Attach the report.
      Result: **PASS**, all 11 scenarios (9 axes + 2 new-value-admission checks). Report:
      `qa/decode-filter-synth-verify/live-reports/2026-07-18T113345Z-6ba513e.md`.

## 6. Requirements, version, and gate compliance

- [x] 6.1 Add **FR-061** to `REQUIREMENTS.md` describing daemon-side auto-admission of
      previously-unseen attribute values into a narrowed-but-non-empty `DecodeFilterState` axis,
      including the explicit-empty-axis exception (design.md Decision 5), following the exact
      table-row format of neighboring FR entries (e.g. FR-060).
  - Not omitted this time — the last two changes touching this filtering hook each shipped
    without their required `**User-facing:**` declaration or VERSION bump and had to be
    corrected post-merge (see `fix-jump-in-rr73-adif-capture` and
    `engagement-target-validation` in project history). Do it here, first, not as a follow-up.
- [x] 6.2 Add a changelog row to `REQUIREMENTS.md`'s version-history table describing this fix,
      with an explicit `**User-facing:** yes` (an operator narrowing a decode-panel filter axis
      will now keep seeing/engaging brand-new entities/zones they haven't yet explicitly excluded
      — a real behavior change from today's silent-hide) and bump **VERSION** accordingly (minor
      version per the project's existing user-facing-feature rule).
- [x] 6.3 Run `python3 tools/pre_merge_check.py` and resolve every FAIL/WARN before declaring this
      ready for review — do not rely on reading `REQUIREMENTS.md`/`tasks.md` content alone (HK-006).
      Result: PASS on G9a, Solution build (Release), full test suite (1296 tests, 0 failed),
      G3 traceability, G8 openspec validate. One WARN: AOT publish — local `vswhere.exe`/MSVC
      linker toolchain missing on this machine, flagged by the script itself as an environment
      gap, not a code regression (this change touches no AOT/native-interop code). Not resolved
      — a toolchain install is outside this change's scope; flagged to the Captain.
- [x] 6.4 Run `openspec validate --strict --all` and confirm a clean pass.

## 7. QA re-review

- [x] 7.1 QA confirms: the `IDecodeFilterStore.AdmitNewValues` unit tests actually exercise the
      lock/copy-on-write path (not just single-threaded happy paths), the decode-pump hook fires
      before the QSO-controller fan-out (not after), the explicit-empty-axis exception is real and
      tested, `live_verify_9_axes.py`'s new scenario passes against real hardware, and FR-061 plus
      the changelog/VERSION bump are present before this is archived.
  - Confirmed: `DecodeFilterStoreAdmitNewValuesTests.ParallelAdmitNewValuesAndSetCalls_...`
    (tests/OpenWSFZ.Web.Tests) fires 200 concurrent `AdmitNewValues` calls interleaved with 20
    concurrent `Set` calls via `Task.WhenAll`, then asserts all 200 distinct entities landed with
    no loss/corruption — genuinely exercises the lock/copy-on-write path, not just single-threaded
    happy paths.
  - Confirmed: `Program.cs`'s `AdmitNewValues` loop runs immediately after
    `DecodeNoiseSuppressionFilter.Apply`/`decodeEventBus.Publish`/`allTxtWriter.AppendAsync` and
    strictly before `qsoAnswererChannel.Writer.TryWrite(batch)` /
    `qsoCallerChannel.Writer.TryWrite(batch)` — same-cycle admission before fan-out, as required.
  - Confirmed: `FirstSeenValue_ExplicitlyEmptyAxis_IsNotAdmitted` (test 3.3) and the requirement
    spec's "An explicit empty axis never auto-admits" scenario both exist and pass.
  - Confirmed: `live_verify_9_axes.py`'s Phase 7 ran against a real isolated daemon + VB-CABLE —
    PASS, report `qa/decode-filter-synth-verify/live-reports/2026-07-18T113345Z-6ba513e.md`.
  - Confirmed: FR-061 (REQUIREMENTS.md), changelog row 1.40, and VERSION v0.41 are all present
    and Gate G9a/G3/G8 all pass per `tools/pre_merge_check.py` (task 6.3).
  - **Not confirmed, flagged to Captain:** task 4.2's real-browser click-through — this
    environment has no browser-automation tooling (no Playwright/Selenium anywhere in the repo),
    so it could only be verified by code-inspection (the `decodeFilterChanged` WS handler in
    `main.js` treats every frame identically regardless of origin) plus the existing
    `DecodeFilterWebSocketBroadcastTests` integration test, not by literally watching a browser
    tab update. Genuinely open before archive.
