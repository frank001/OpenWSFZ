## 0. Prerequisite

- [x] 0.1 Confirm `qso-confirmation-band-awareness` is implemented and merged first — this
      change's worked-before filter axes and `WorkedBeforeState` enum do not exist without it.
      Do not begin task group 1 until that change's tasks 1–5 (backend data model) are done, at
      minimum.

## 1. `DecodeFilterState` and evaluation predicate (C#)

- [x] 1.1 Add `DecodeFilterState` record to `src/OpenWSFZ.Abstractions/` (four nullable
      attribute-allow-list sets, five nullable worked-before-state sets, `Unfiltered` static
      default per design.md Decision 1).
- [x] 1.2 Add `DecodeFilterEvaluator.IsVisible(DecodeResult, DecodeFilterState) : bool` — AND
      across all active (non-null) axes; unresolved attribute values fail open on
      attribute-allow-list axes; absent `WorkedBefore` treated as `Never` on worked-before axes.
- [x] 1.3 Unit tests: each axis independently (pass/fail), combinations, fail-open-on-unresolved,
      absent-WorkedBefore-as-Never, and the `Unfiltered` default passing everything.

## 2. `IDecodeFilterStore` and API surface

- [x] 2.1 New `IDecodeFilterStore` singleton (in-memory only, no persistence — explicitly not an
      `IConfigStore` implementer) holding the current `DecodeFilterState`, defaulting to
      `Unfiltered`.
- [x] 2.2 `GET /api/v1/decode-filter` — returns current state.
- [x] 2.3 `POST /api/v1/decode-filter` — whole-object replace (matches the existing `POST
      /api/v1/config` convention, not a new partial-patch style), updates the store, and pushes
      a `decodeFilterChanged` WebSocket event via the existing `WebSocketHub` broadcast mechanism.
- [x] 2.4 Integration tests: GET returns default on fresh daemon; POST updates and is reflected
      on next GET; POST triggers a WebSocket broadcast to all connected test clients; state does
      not survive a simulated daemon restart (fresh `IDecodeFilterStore` instance).

## 3. Automation gating — `QsoAnswererService`

- [x] 3.1 Inject `IDecodeFilterStore` into `QsoAnswererService` (optional constructor parameter,
      matching this codebase's established pattern for optional collaborators — see D-013's
      `ICatState?` precedent).
- [x] 3.2 In the `Idle`-state CQ-scanning logic: skip any CQ whose callsign fails
      `DecodeFilterEvaluator.IsVisible` against the current filter state; select the first
      non-filtered-out CQ; remain in `Idle` (no transmission) if every CQ in the cycle is
      filtered out.
- [x] 3.3 Confirm the filter is read once per decision (at the moment of selecting which CQ to
      engage), not re-checked at any later point in the same QSO's lifecycle.
- [x] 3.4 Unit tests: filtered-out CQ skipped in favour of the next one; all-filtered-out cycle
      behaves identically to an empty cycle; filter change after engagement does not abort an
      in-progress QSO; no `IDecodeFilterStore` supplied (null) behaves as fully unfiltered (no
      regression for callers not yet updated, mirroring D-013's backward-compatibility posture).

## 4. Automation gating — `QsoCallerService`

- [x] 4.1 Inject `IDecodeFilterStore` into `QsoCallerService`, same pattern as 3.1.
- [x] 4.2 In the `WaitAnswer`-state responder-scanning logic (`CallerPartnerSelect = First`):
      skip any responder whose callsign fails the filter; select the first non-filtered-out one;
      treat an all-filtered-out cycle identically to a genuinely empty cycle for retry/watchdog
      accounting.
- [x] 4.3 In `SelectResponderAsync` (`CallerPartnerSelect = None`): reject a call naming a
      currently filtered-out callsign — no `_pendingResponder` stored, no state transition.
- [x] 4.4 Unit tests mirroring 3.4, plus the `None`-mode rejection case from 4.3.

## 5. Frontend — clickable headers, filter popups, row visibility

- [x] 5.1 `web/js/main.js`: port `DecodeFilterEvaluator.IsVisible` to `isDecodeVisible(decode,
      filterState)`, structurally identical to the C# version — mirrored unit tests alongside
      the C# ones (design.md Decision 2's accepted drift-risk mitigation).
      **Implementation note:** the predicate and `UNFILTERED_DECODE_FILTER` were extracted into
      a new DOM-free module, `web/js/decodeFilter.js` (imported by `main.js`), specifically so
      it can be exercised without a browser. Testing approach confirmed with the Captain: this
      repo had zero JS test infrastructure (no `package.json`, no runner) before this task; we
      chose Node's built-in `node --test` + `node:assert` — zero new dependencies — over adding
      a full framework (e.g. Vitest) or skipping JS-side tests. `web/js/package.json` is a
      dependency-free `{"type":"module"}` marker only (no npm install, no lockfile), needed so
      Node resolves `import`/`export` correctly; the browser ignores it entirely. Tests:
      `web/js/decodeFilter.test.js` (21 cases, 1:1 mirrored with
      `DecodeFilterEvaluatorTests.cs`'s 21) — run via `node --test web/js/decodeFilter.test.js`.
- [x] 5.2 `web/index.html`/`web/js/main.js`: make the five worked-before column headers
      clickable; DXCC/Cnt/CQz/ITz open a two-section popup, Ctc opens a one-section (worked-before
      only) popup.
- [x] 5.3 Popup: attribute allow-list section populated from values relevant to the current
      session (windowing choice per design.md Decision 4 — document whichever is chosen);
      worked-before section as three checkboxes (Never/DifferentBand/ThisBand).
      **Windowing choice:** session-seen (not just currently-rendered/capped rows) — `main.js`
      tracks `seenEntities`/`seenContinents`/`seenCqZones`/`seenItuZones` `Set`s populated as
      each decode arrives, independent of `MAX_DECODE_ROWS` row-capping, so a value that has
      scrolled off the table is still offered as a filter checkbox.
- [x] 5.4 On any popup change: `POST /api/v1/decode-filter` with the updated state.
- [x] 5.5 On `decodeFilterChanged` WebSocket event: re-evaluate every currently-rendered row via
      `isDecodeVisible`, show/hide accordingly; update any open popup's reflected state if the
      change came from another client.
- [x] 5.6 `web/css/app.css`: popup styling, hidden-row styling.
- [x] 5.7 Manual/screenshot verification: open two browser tabs, change the filter in one,
      confirm the other tab's table and popup state update without a reload.
      **Verified against the real daemon** (built `OpenWSFZ.Daemon.exe`, launched on an isolated
      `--config`/`--port` so the operator's live `%APPDATA%\OpenWSFZ\` config was never touched),
      driven with Playwright (`qa/uat-tmp`'s existing `playwright-core` install — no new
      dependency): (1) clicking DXCC opens a two-section popup (attribute allow-list +
      worked-before), clicking Ctc opens a one-section (worked-before only) popup — screenshots
      confirm correct dark-theme rendering, anchored under the clicked header; (2) tab A issues
      `POST /api/v1/decode-filter`, tab B (WS-only, never touched the popup) receives the
      `decodeFilterChanged` frame and, on opening its own Ctc popup afterward with no reload,
      shows the exact pushed state (`contactStates:["never"]` → only "Never worked" checked) —
      confirmed both via `$$eval` checkbox-state inspection and a screenshot. Screenshots
      retained in `qa/uat-tmp/` for review. Task 6.4 (live-decode TX-automation E2E) was not
      attempted this way — see its note.
- [x] 5.8 Popup UI polish per `dev-tasks/2026-07-10-decode-panel-filtering-popup-ui-polish.md`
      (Captain feedback + one QA-found defect, held the merge until fixed):
      (1) `app.css` — added `.decode-filter-popup-row input[type="checkbox"]` (`width: auto;
      margin: 0; cursor: pointer; accent-color: var(--color-accent);`), mirroring the
      `.checkbox-label`/`.waterfall-hold-label` precedents, fixing inconsistent checkbox
      rendered widths (89px vs 13px) caused by the global `input, select { width: 100% }` rule;
      (2) `main.js` — added "Select All"/"Select None" buttons above the attribute allow-list
      checkboxes (DXCC/Cnt/CQz/ITz only, not Ctc, not the worked-before section), producing
      exactly the same `null`/`[]` wire representations the per-checkbox handler already used;
      (3) fixed `decodeFilter.test.js`'s header comment (`**/`  self-closing its own block
      comment), which had silently prevented all 21 JS tests from ever executing.
      **Re-verified against the real daemon** (isolated `--config`/`--port`, same approach as
      5.7): dispatched a synthetic `decode` WS frame via a captured-`WebSocket` Playwright
      script (no app code changes needed) to populate the DXCC allow-list with 3 entities,
      confirmed via `getBoundingClientRect()` that all worked-before/allow-list checkboxes in
      both the DXCC and Ctc popups now render at a uniform 13px, confirmed Select All → `GET
      /api/v1/decode-filter` returns `allowedEntities: null` and Select None → `[]` (screenshots:
      `qa/uat-tmp/popup-dxcc-polished.png`, `popup-dxcc-select-all.png`,
      `popup-dxcc-select-none.png`, `popup-ctc-polished.png`), and confirmed the Ctc popup has
      zero `.decode-filter-popup-select-row` elements (out of scope, untouched). `node --test
      web/js/decodeFilter.test.js` now reports `tests 21 / pass 21 / fail 0`.
      Per Captain's decision on the dev-task's open question, also closed the "nothing runs this
      automatically" gap: added a `"test": "node --test *.test.js"` script to
      `web/js/package.json` (run from `web/js/`), and a new `JS unit tests (web/js)` step in
      `.github/workflows/ci.yml`'s `build-test` job (Linux leg only, alongside the other
      single-run gates — no `setup-node`/install needed, the suite has zero npm dependencies).
      **QA re-review (2026-07-10): approved, zero outstanding findings** — independently
      re-measured checkbox geometry (`getBoundingClientRect`), re-ran `node --test
      web/js/*.test.js` (21/21) and the full `dotnet test`/`openspec validate --strict --all`
      suites, and confirmed the Select All/None wire semantics against a live `GET
      /api/v1/decode-filter` round-trip before approving.

## 6. Verification

- [x] 6.1 `dotnet build OpenWSFZ.slnx -c Release` — 0 warnings, 0 errors.
- [x] 6.2 `dotnet test OpenWSFZ.slnx -c Release` — full suite green, no regressions in existing
      `qso-answerer`/`qso-caller` test coverage. (1006/1006, including 62 new tests from this
      change: 21 `DecodeFilterEvaluatorTests`, 5 `DecodeFilterEndpointTests`/WS broadcast, 5 new
      `QsoAnswererServiceTests`, 6 new `QsoCallerServiceTests`, plus 21 mirrored JS tests run
      separately via `node --test`, not part of the dotnet count.)
- [x] 6.3 `openspec validate --strict --all` — passing, including this change's delta specs.
      (51/51.)
- [x] 6.4 End-to-end manual check: with TX automation enabled, filter out a station's DXCC entity,
      confirm a CQ from that entity is neither answered nor highlighted as engageable, while a CQ
      from a non-filtered entity is answered normally in the same session.
      **Fully closed by QA in two tiers (2026-07-10)** — see `qa-verification-report.md` (this
      change's directory) for the complete narrative:
      1. **In-process tier**, deliberately kept **outside** `OpenWSFZ.slnx`/`dotnet test` — a
         manually-run script, not a regression-suite addition: `qa/decode-filter-synth-verify/`.
         Covers all nine `DecodeFilterState` axes (one real-synthesised-and-decoded scenario each,
         against `QsoAnswererService`'s CQ-scan gate), the all-candidates-filtered-out case, and
         `QsoCallerService`'s three distinct gating mechanisms (`First`-mode skip, `First`-mode
         all-filtered, `None`-mode `SelectResponderAsync` rejection) — 13 scenarios, all passing.
         Real decoder/real automation classes, but in-process — no real daemon, no real audio
         hardware.
      2. **Live hardware-in-the-loop tier**, closing the remainder of this task's original scope:
         `qa/decode-filter-synth-verify/live_verify_9_axes.py` runs the full nine-axis matrix
         against a real, isolated `OpenWSFZ.Daemon` process, with genuinely synthesised audio
         played into a real virtual audio cable (VB-CABLE/Voicemeeter) the daemon captures over
         its real WASAPI pipeline, decoded by the real native decoder, and answered via a real
         `IPttController.KeyDownAsync` → real WASAPI TX playback — verified through the real HTTP
         API, independently cross-checked against the daemon's own log. **9/9 axes pass.**
         Reporting is automatic (every run writes its own timestamped report to
         `qa/decode-filter-synth-verify/live-reports/`) and a standing policy
         (`MEMORY.md` → `decode-panel-filtering-live-verification-policy.md`) now requires this
         script be re-run before merge on any future change touching this capability.
      **What remains out of scope, by deliberate decision, not oversight**: real physical RF
      hardware and a real serial/CAT-keyed PTT line — a daemon-wide concern, not specific to
      filtering. Prior note, kept for history: the underlying logic this check exercises is also
      covered at the unit level — see the `decode-panel-filtering` tests added to
      `QsoAnswererServiceTests.cs` (task 3.4) and `QsoCallerServiceTests.cs` (task 4.4), which
      drive the same `DecodeFilterEvaluator.IsVisible` gate with hand-typed `DecodeResult`s rather
      than real synthesised-and-decoded audio.
