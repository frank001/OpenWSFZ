## 1. Before screenshot (per HK-005 ordering)

- [x] 1.1 Capture a screenshot of the current Region data settings tab (status/refresh + lookup
      fieldsets only, no suppression controls yet) and save it alongside the change artifacts for
      later before/after comparison.
      Done: `qa/uat-tmp/decode-noise-suppression-before-region-data.png`, captured via a scratch
      Playwright script against a scratch daemon instance (separate port/config/build output so
      the Captain's real running instance was never touched).

## 2. Config model & persistence

- [x] 2.1 Add `DecodeNoiseSuppressionConfig` record (`SuppressUnknownRegion: bool? = null`,
      `SuppressSynthetic: bool = true`) to the existing `IConfigStore`-backed configuration model,
      following the same section pattern as `Decoder`/`DecodeLog`.
      Done: `src/OpenWSFZ.Abstractions/DecodeNoiseSuppressionConfig.cs` (non-nullable
      `AppConfig.DecodeNoiseSuppression` section, `DecodeLog`-style, `[JsonConstructor]` default
      guard for `SuppressSynthetic` mirroring `DecoderConfig`'s Lesson 6 pattern); registered in
      both `ConfigJsonContext` and `AppJsonContext`.
- [x] 2.2 Confirm existing `JsonConfigStore` first-run/missing-key handling produces the correct
      defaults for installs upgrading from a config file that predates this section (no explicit
      migration script should be needed — verify with a test reading an old-format config).
      Done: `Load()` null-guard added in `JsonConfigStore.cs` (mirrors `Logging`/`DecodeLog`/
      `RemoteAccess`); 4 new tests in `JsonConfigStoreTests.cs` covering fresh-config defaults,
      whole-key-absent, round-trip, and partial-object defaults — all passing.

## 3. Backend suppression gate

- [x] 3.1 Implement `DecodeNoiseSuppressionFilter` (pure, static, unit-testable) in
      `OpenWSFZ.Daemon`: given `IReadOnlyList<DecodeResult>`, the current
      `DecodeNoiseSuppressionConfig`, and `ICallsignRegionStore` (for resolving the Unknown
      setting's live default when unset), return the subset of decodes that should be
      visible/engageable.
      Done: `src/OpenWSFZ.Daemon/DecodeNoiseSuppressionFilter.cs`.
- [x] 3.2 Wire the filter into the decode-pump loop in `Program.cs`: compute `visibleResults` once
      per cycle immediately after `ft8Decoder.DecodeAsync` returns; pass `visibleResults` to
      `decodeEventBus.Publish` and to the `DecodeBatch` written to both `qsoAnswererChannel` and
      `qsoCallerChannel`; continue passing the unfiltered `results` to `allTxtWriter.AppendAsync`
      unchanged.
      Done: `src/OpenWSFZ.Daemon/Program.cs` decode-pump loop (~line 545).
- [x] 3.3 Add a code comment at the filter call site (and in `region-lookup`'s
      `TryGetRegion`/decode-pump vicinity as appropriate) noting that this is a deliberate,
      operator-opt-in exception to the `region-lookup` capability's "reaches ALL.TXT and the UI"
      invariant — so a future reader doesn't mistake it for a regression.
      Done: comment at the `Program.cs` call site + a `<para>` added to `ICallsignRegionStore`'s
      XML doc pointing future readers at `DecodeNoiseSuppressionFilter`.
- [x] 3.4 Expose the live-resolved effective value of the Unknown setting (not just the raw
      persisted `bool?`) via whatever mechanism the settings page already uses to read current
      config (needed for task 4.2's live display), reusing the entry-count check that backs
      `GET /api/v1/region-data/status`.
      Done: new `EffectiveSuppressUnknownRegion` field on `RegionDataStatusResponse`, computed via
      a new shared `DecodeNoiseSuppressionDefaults.ResolveEffectiveSuppressUnknownRegion` helper
      in `OpenWSFZ.Abstractions` (single source of truth reused by both `OpenWSFZ.Web`'s status
      endpoint and `OpenWSFZ.Daemon`'s filter — `OpenWSFZ.Web` cannot reference `OpenWSFZ.Daemon`,
      so the shared logic had to live in `Abstractions`, not in the filter itself).

## 4. Settings page UI

- [x] 4.1 Add two checkboxes to the Region data settings tab (`web/settings.html`): "Suppress
      Unknown region/DXCC decodes" and "Suppress R&R Synthetic decodes", in a clearly labeled
      fieldset distinct from the existing status/refresh and lookup fieldsets.
      Done: `#decode-noise-suppression-fieldset` in `web/settings.html`, mirroring the
      `checkbox-label`/`field-hint` markup used elsewhere on the page.
- [x] 4.2 Wire both checkboxes in `web/js/settings.js`: load/display the live-resolved effective
      value (per task 3.4) on page load and after a region-data refresh completes; save explicit
      operator changes through the existing settings-save round-trip (same `JsonConfigStore`
      pattern/serialized `SaveAsync` used elsewhere on this tab). Confirm the Unknown checkbox is
      never disabled in either code path — no `disabled` attribute is ever set on it.
      Done: `_suppressUnknownRegionRaw` tri-state tracker + `renderRegionDataStatus` extension +
      Save payload wiring in `web/js/settings.js`. Live-verified end-to-end against a scratch
      daemon (0-entry and 38-entry region tables): never disabled, correct auto-default in both
      states, explicit choice survives Save+reload even with an empty region table (no console
      errors) — see `qa/uat-tmp/decode-noise-suppression-*.png` and
      `qa/uat-tmp/verify-suppression-ui.mjs`.
- [x] 4.3 Confirm the R&R-synthetic checkbox needs no live-recompute step (plain persisted boolean,
      no data-presence dependency) — simpler load/save path than 4.2's Unknown checkbox.
      Confirmed: plain `noise.suppressSynthetic ?? true` load / `suppressSynthetic.checked` save,
      no status-endpoint dependency. Live-verified checked-by-default.

## 5. After screenshot (per HK-005 ordering)

- [x] 5.1 Capture a screenshot of the Region data settings tab showing both new controls (one with
      region data absent showing the Unknown checkbox unchecked-but-interactive, one after a
      refresh showing it auto-reflecting enabled), for before/after comparison against task 1.1.
      Done, both against a scratch daemon with a genuinely empty (`[]`) region table:
      `qa/uat-tmp/decode-noise-suppression-after-region-data-absent.png` (0 entries, Unknown
      unchecked-but-interactive) and `qa/uat-tmp/decode-noise-suppression-after-region-data-refresh.png`
      (clicked the real "Refresh region data" button — a genuine live fetch against
      country-files.com succeeded, 29,013 entries — Unknown checkbox live-flipped to checked with
      no page reload, "Region data refreshed ✓" feedback, no console errors). Also kept
      `decode-noise-suppression-after-region-data-seed-present.png` (fresh-install seed data, 38
      entries) as a third reference point. Scripts: `qa/uat-tmp/verify-live-refresh.mjs`,
      `qa/uat-tmp/verify-suppression-ui.mjs`.

## 6. Automated test coverage

- [x] 6.1 Unit tests for `DecodeNoiseSuppressionFilter`: null-region decode suppressed/not per
      setting state; `Region.Synthetic == true` decode suppressed/not per setting state; a decode
      matching neither rule always passes through; both rules active simultaneously on a mixed
      batch.
      Done: `tests/OpenWSFZ.Daemon.Tests/DecodeNoiseSuppressionFilterTests.cs`.
- [x] 6.2 Unit tests for the Unknown-setting default resolution: unset + empty region table → not
      suppressed; unset + populated region table → suppressed; explicit `true`/`false` is honored
      regardless of region-table state; an explicit choice made before data exists is still honored
      after data is later loaded.
      Done: same file — `ResolveEffectiveSuppressUnknownRegion_*` tests, using a mutable
      `StubRegionStore` to flip empty→populated mid-test.
- [x] 6.3 Integration test on the `Program.cs` decode-pump wiring (or the narrowest feasible seam):
      confirm `ALL.TXT` receives a decode that the decode-panel broadcast and QSO-controller
      batches do not, when a suppression rule is active — proving the ALL.TXT/panel divergence
      described in design.md Decision 1 actually holds.
      Done (narrowest feasible seam — `Program.cs` top-level statements aren't directly
      unit-testable): `Apply_UnfilteredInputRetainsSuppressedDecode_ThatFilteredOutputOmits`
      proves `Apply` never mutates its input (the same list Program.cs passes unfiltered to
      `allTxtWriter.AppendAsync`) while its filtered output (what the panel/QSO-controller
      channels receive) omits the suppressed decode. All 15 tests in this file pass
      (`dotnet test` against a scratch build — see note below on the Captain's live daemon
      lock).
- [x] 6.4 Settings-page test (existing frontend test harness) covering: checkbox never disabled;
      checked/unchecked state persists across a reload; Unknown checkbox reflects the live
      effective value including the auto-computed default.
      Done: extracted the checkbox-display resolution into a new DOM-free pure function
      (`web/js/decodeNoiseSuppression.js`'s `resolveUnknownCheckboxDisplay`, mirroring the
      `decodeFilter.js`/`isDecodeVisible` precedent) and unit-tested it via `node --test`
      (`decodeNoiseSuppression.test.js`, 4/4 passing; full `web/js` suite 25/25). "Never
      disabled" and "persists across reload" are DOM/server-round-trip behaviors outside what the
      DOM-free harness can exercise directly (no jsdom/Playwright dependency in this repo's `web/js`
      test setup) — covered instead by live end-to-end verification against a real running daemon
      (`qa/uat-tmp/verify-suppression-ui.mjs`, `qa/uat-tmp/verify-live-refresh.mjs`; see task 5.1's
      notes) confirming both properties hold against real config-file round-trips and a real
      country-files.com refresh.

## 7. Mandatory live verification

- [x] 7.1 Because this change alters the input batch delivered to `QsoAnswererService` and
      `QsoCallerService`, re-run `qa/decode-filter-synth-verify/live_verify_9_axes.py` (real
      isolated daemon, real virtual-audio-cable injection, real native decoder, real API) before
      merge, per the standing decode-panel-filtering live-verification policy. Confirm its
      generated report shows no regression on the existing nine filter axes now that the new
      upstream suppression stage sits in front of them.
      Done: built `src/OpenWSFZ.Daemon -c Release` (includes `DecodeNoiseSuppressionFilter`) and
      ran the script against real VB-CABLE/Voicemeeter hardware present on this machine. Result:
      **PASS**, all 9 axes green, independent daemon-log cross-check matched exactly (9/9/0) — no
      regression now that the new suppression gate sits upstream of `DecodeFilterEvaluator` (the
      isolated fixture's decodes all resolve to real, non-null, non-synthetic regions, so the new
      gate is confirmed a true no-op for this matrix, as expected). Report committed:
      `qa/decode-filter-synth-verify/live-reports/2026-07-11T173215Z-497e733.md`.

## 8. Documentation

- [x] 8.1 Update any operator-facing settings documentation/help text describing the Region data
      tab to include the two new controls and their default-behavior nuance (Unknown control's
      data-presence-dependent default vs. its always-interactive state).
      Done via the in-app `field-hint` text added in `web/settings.html` (task 4.1) — confirmed
      this is the established, precedent-matching form of "operator-facing settings
      documentation/help text" in this repo (e.g. `decoder-settings-page`, `lan-remote-access`
      document themselves the same way; there is no separate standalone prose doc enumerating
      Settings-page controls the way `docs/cat-control-operator-guide.md` does for CAT). The
      README's feature-changelog table is developer/project bookkeeping, not operator-facing help
      text, and is already stale for several other already-merged features (f-006, decode-panel-
      filtering, adif-qso-confirmation are all absent from it) — out of scope to backfill here.
