## 1. Clear-cadence defect fix

- [x] 1.1 Remove the unconditional `SendToAllEnabledAsync(WsjtxDatagram.EncodeClear(AppId))` call
  from `ExternalReportingService.DecodeLoopAsync` (`ExternalReportingService.cs:395`). Decode
  datagrams continue to be sent per-cycle, unchanged.
- [x] 1.2 Add a Clear datagram send to `ExternalReportingService.StopAsync`, alongside the existing
  `SendCloseToAllAsync()` call (`ExternalReportingService.cs:222-246`), so a Clear reaches every
  enabled target on graceful shutdown before sockets close.
- [x] 1.3 Update `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`:
  - [x] 1.3.1 Replace `Decode_AllResultsSuppressed_StillSendsClear` (currently asserts "Clear must
    still fire every cycle") with a test asserting the opposite invariant: no Clear datagram is
    ever sent from the decode loop, regardless of how many decodes in a batch are suppressed.
  - [x] 1.3.2 Check `TwoEnabledTargets_BothReceiveDecode` (`:146-157`) and any other test expecting
    a Clear+Decode pairing per cycle; update expectations to Decode-only.
  - [x] 1.3.3 Add a new test confirming `StopAsync` sends a Clear datagram to every enabled target
    (alongside the existing Close-on-shutdown coverage).

## 2. Config schema

- [x] 2.1 Add `RestrictExternalRepliesToDecodeFilter` (bool, default `false`) to
  `ExternalReportingConfig` (`src/OpenWSFZ.Abstractions/ExternalReportingConfig.cs`), following the
  existing `HonourInboundCommands` `[JsonConstructor]` pattern exactly.
- [x] 2.2 Add/extend round-trip tests in `tests/OpenWSFZ.Config.Tests/ExternalReportingConfigTests.cs`
  for the new field (default `false`; missing-key-on-an-existing-`externalReporting`-object
  deserialises to `false`).
- [x] 2.3 Confirm `tests/OpenWSFZ.Web.Tests/ExternalReportingConfigValidationTests.cs` needs no new
  case (no new validation constraint — plain bool) or add one if it does. **Confirmed: no new case
  needed** — the field is a plain bool with no range/format constraint, unlike `port`.

## 3. QsoAnswererService — external-reply filter bypass

- [x] 3.1 In `TryEngageExternal` (`QsoAnswererService.cs:359-413`), read
  `_configStore.Current.ExternalReporting?.RestrictExternalRepliesToDecodeFilter ?? false` and make
  the existing `DecodeFilterEvaluator.IsVisible` check conditional on it — bypass entirely when
  `false` (default).
- [x] 3.2 Update `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs`:
  - [x] 3.2.1 Amend `TryEngageExternal_FilteredOutCallsign_NoOp` to explicitly set
    `RestrictExternalRepliesToDecodeFilter = true`. (Renamed to
    `TryEngageExternal_FilteredOutCallsign_RestrictOptedIn_NoOp` for clarity.)
  - [x] 3.2.2 Add `TryEngageExternal_FilteredOutCallsign_DefaultEngagesAnyway` — same filtered-out
    setup, flag left at its default (`false`) — assert `engaged` is `true`.
  - [x] 3.2.3 Add a regression test confirming a synthetic/unknown-region callsign named in an
    external Reply still never reaches TX regardless of the new flag's value — **escalated to the
    Captain rather than decided unilaterally** (per this task's own instruction): investigation
    showed `TryEngageExternal` has no Region-based gate of its own — reachability is governed
    entirely by the pre-existing, upstream `DecodeNoiseSuppressionFilter` (applied once in the
    decode-pump loop before any fan-out, identically for the internal auto-answer path). Captain's
    decision: **leave as-is**, no redundant check added — not a gap introduced by this change.
    Added `TryEngageExternal_SyntheticRegionCq_NoOwnRegionGate` to document/pin down this boundary
    instead.

## 4. QsoCallerService — external-reply filter bypass (requires refactor)

- [x] 4.1 Extract the state-transition body of `SelectResponderAsync`
  (`QsoCallerService.cs:335-363` — the `responseIsAPhase`/`_pendingResponder*` assignment and
  wakeup) into a private `SelectResponderCore(string callsign, double frequencyHz, DateTimeOffset
  responseCycleStart, DecodeResult? recentDecode)`. (Returns `bool`, re-checking `WaitAnswer`
  under the lock — mirrors `QsoAnswererService.ArmPendingTarget`'s identical pattern, since the
  two call sites now only verify state in an earlier, separate lock acquisition.)
- [x] 4.2 `SelectResponderAsync` keeps its existing, unconditional `DecodeFilterEvaluator.IsVisible`
  check (`:328-333`) and then calls `SelectResponderCore` — behaviour for the manual/browser path
  must be unchanged.
- [x] 4.3 In `TryEngageExternalResponder` (`:383-413`), add a filter check reading
  `_configStore.Current.ExternalReporting?.RestrictExternalRepliesToDecodeFilter ?? false` against
  `_recentResponderDecodes` directly (mirroring task 3.1's pattern), then call
  `SelectResponderCore` directly — bypassing `SelectResponderAsync`'s own gate when the flag is at
  its default (`false`).
- [x] 4.4 Confirm no existing `QsoCallerServiceTests.cs` coverage of `SelectResponderAsync`
  regresses from the extraction (pure refactor — identical behaviour for the manual path). All 61
  pre-existing tests in this file pass unchanged after the refactor.
- [x] 4.5 Add tests for `TryEngageExternalResponder`'s filter-bypass behaviour (new file or
  additions to whichever file already covers this method) mirroring 3.2.1/3.2.2: filtered-out +
  flag `true` rejects; filtered-out + flag `false` (default) engages. Also added a third test
  confirming the manual `SelectResponderAsync` path is unaffected by the new flag's default.

## 5. Settings UI

- [x] 5.1 `web/settings.html` — add a new checkbox inside `#ext-rep-inbound-fieldset`
  (`:798-814`), nested under/beside "Honour inbound commands", labelled "Restrict external Reply to
  the current decode-panel filter" with explanatory hint text (unchecked/default = honour
  regardless of the panel filter).
- [x] 5.2 `web/js/settings.js`:
  - [x] 5.2.1 New `const extRepRestrictReplies` element lookup alongside line 118.
  - [x] 5.2.2 Load/pre-fill alongside line 886.
  - [x] 5.2.3 Dirty-state snapshot alongside line 401.
  - [x] 5.2.4 Save payload alongside line 1331.
- [x] 5.3 (Optional, not required) Consider visually disabling the new checkbox when "Honour inbound
  commands" is unchecked, since it has no effect either way in that state. **Implemented** —
  `updateExtRepRestrictRepliesVisibility()`, wired the same way as the other dependent-field
  visibility helpers already in this file (`updateDecodeLogVisibility`/`updateLoggingVisibility`).

## 6. Documentation

- [x] 6.1 `REQUIREMENTS.md` — amend FR-053 (Clear cadence corrected) and FR-054 (external-reply
  filter conditionality); add a revision-history row per the existing convention, noting the
  Clear-cadence item corrects a defect present since the capability's original 2026-07-12
  implementation (row 1.31). Added row 1.44.
- [x] 6.2 Confirm `**User-facing:** yes` is present in `proposal.md` (already set) and bump
  `VERSION` per the minor-version-per-user-facing-feature rule at merge/archive time, following
  this project's established timing convention (check current `main` state before deciding
  merge-time vs. archive-time). **Decided: pre-merge**, per `fix-version-bump-gate-timing`
  (row 1.39) — `tools/check_version_bump.py` enforces the bump in the same PR that first
  introduces a user-facing change's `proposal.md` into `main`'s history, which this PR does.
  Bumped `VERSION` 0.44 → 0.45.

## 7. Verification

- [x] 7.1 Re-run `qa/decode-filter-synth-verify/live_verify_9_axes.py` — this change touches the
  answerer/caller decode-filtering hook directly (per project policy on any change touching
  `DecodeFilterState`/`DecodeFilterEvaluator`/`IDecodeFilterStore` or that hook). **PASS** — all
  9 axes + New-Value-Admission scenarios, run against a real isolated daemon with a real virtual
  audio cable (VB-CABLE/Voicemeeter detected in this environment). Report committed:
  `qa/decode-filter-synth-verify/live-reports/2026-07-19T165830Z-384e30e.md`.
- [x] 7.2 Live-confirm the Clear-cadence fix against a real GridTracker2 instance: run a patched
  build for several minutes and confirm spots accumulate on the map instead of shrinking every
  cycle — no automated test in this repo drives a real GridTracker2 process, so this is the only
  way to be sure the fix resolves the originally reported symptom. **PASS, confirmed by the
  Captain** — screenshot supplied 2026-07-19 of GridTracker2's world map after a few minutes of
  `owsfz` running against a real virtual-audio-cable feed: dozens of accumulated spots spread
  across Europe/Asia/the Pacific with QSO lines drawn, not the near-empty, ~15s-flickering map the
  pre-fix every-cycle Clear would have produced (a Clear-every-cycle defect could never accumulate
  more than one cycle's worth of spots at any instant). The removal itself is also proven by
  `Decode_AllResultsSuppressed_NeverSendsClear`/`TwoEnabledTargets_BothReceiveDecode` and
  `StopAsync_SendsClearToEveryEnabledTarget` (Section 1).
- [x] 7.3 `openspec validate --strict --all` passes.
- [x] 7.4 `python3 tools/pre_merge_check.py` clean (HK-006) before this is called ready for merge.
  First run surfaced a real gap: Gate G9a (doc/VERSION consistency) failed — `README.md` and
  `REQUIREMENTS.md`'s "current release is v0.44" anchor sentences hadn't been updated alongside
  the `VERSION` bump to 0.45 (task 6.2). Fixed both; re-run is clean:
  `PASS G9a/build/tests/G3/G8/self-contained-publish`, `SKIP AOT publish (--skip-aot)` — the AOT
  gap is the pre-existing, already-logged N9 backlog item (Windows WASAPI native-AOT toolchain
  gap, `vswhere.exe`/MSVC linker missing), not something introduced by this change. **Result:
  READY.**
