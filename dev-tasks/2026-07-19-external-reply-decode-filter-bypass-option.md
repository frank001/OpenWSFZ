# Developer Handoff — Decode-panel filter silently blocks GridTracker's "Reply" command

**Date:** 2026-07-19
**Prepared by:** QA Engineer
**Status:** New change required — product decision from the Captain, not a plain defect fix
**Scope:** `QsoAnswererService.TryEngageExternal`, `QsoCallerService.TryEngageExternalResponder` /
`SelectResponderAsync`, `ExternalReportingConfig`, External Programs settings tab.

---

## 1. Context

The Captain reported: *"the filtering is affecting the communication with GridTracker in a weird
way. By default all traffic should be sent to external programs unless the operator chooses not
to. Create an option in the External Programs settings page for this functionality."*

I traced this before writing anything, since the Captain's phrasing ("traffic ... sent to
external programs") pointed at the outbound broadcaster and that turned out **not** to be where
the coupling actually lives.

**What is NOT the cause (checked and ruled out):**
- Outbound Decode/Status/QSOLogged datagrams (`ExternalReportingService`) are **not** gated by
  `DecodeFilterState`/`DecodeFilterEvaluator` (`decode-panel-filtering`) at all. They pass through
  `DecodeNoiseSuppressionFilter` (a *different*, two-axis operator setting on the Region-data tab)
  plus `ExternalReportingService`'s own unconditional synthetic/unknown-region exclusion
  (`IsSuppressedCallsign`, `ExternalReportingService.cs:189-199`) — both already correct and
  functioning as designed (`dev-tasks/2026-07-12-gridtracker-udp-reporting-review-fixes.md`,
  §4). No change needed here.

**What IS the cause:**

When GridTracker2 (or JTAlert, etc.) sends an inbound **Reply** datagram asking the daemon to
engage a specific decoded station, that request is rejected if the named callsign is currently
hidden under the operator's own decode-panel filter (`DecodeFilterState`, the multi-axis
band/entity/worked-before popup filter). This is **deliberate, spec'd, tested behaviour** —
not an oversight:

- `QsoAnswererService.TryEngageExternal` (`src/OpenWSFZ.Daemon/QsoAnswererService.cs:396-402`)
  calls `DecodeFilterEvaluator.IsVisible(r, filterState)` and returns `false` (no-op) if the
  matching CQ is filtered out. Spec'd at `openspec/specs/qso-answerer/spec.md:221-225`
  ("External reply to a filtered-out callsign is a no-op") and tested at
  `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs:177-196`.
- `QsoCallerService.TryEngageExternalResponder` (`QsoCallerService.cs:383-413`) delegates to the
  shared `SelectResponderAsync` (`QsoCallerService.cs:316-363`), which itself applies the identical
  `DecodeFilterEvaluator.IsVisible` gate at lines 328-333. Spec'd at
  `openspec/specs/qso-caller/spec.md:173-178` ("None mode — SelectResponderAsync rejects a
  filtered-out callsign"). **Correction to my own initial read:** I first told the Captain this
  Caller-role path was unfiltered (an asymmetry) — that was wrong; I hadn't yet followed the
  delegation into `SelectResponderAsync`. Both roles already reject a filtered-out external Reply,
  consistently. There is no asymmetry to fix — only a new opt-in bypass to add, symmetrically, to
  both.

So: the operator narrows the decode panel for their own viewing convenience (e.g. hide
already-confirmed entities, or restrict to certain zones), then clicks Reply in GridTracker on a
station outside that filter — and the daemon silently does nothing. No error reaches GridTracker;
only an Information-level log line on the daemon side explains why. That is the "weird" behaviour
reported.

**Disposition confirmed with the Captain:** the new setting must cover *both* roles symmetrically
(not Answerer-only), so it has one consistent meaning regardless of which controller is currently
active.

---

## 2. Required change

Add an opt-in `ExternalReportingConfig` field, default `false` (i.e. **default behaviour changes**
to match the Captain's stated preference — external Reply is honoured for any decoded, otherwise-
eligible station, ignoring the decode-panel filter, unless the operator explicitly opts into the
stricter behaviour):

```csharp
// src/OpenWSFZ.Abstractions/ExternalReportingConfig.cs
public sealed record ExternalReportingConfig
{
    [JsonConstructor]
    public ExternalReportingConfig(
        bool                                    enabled                             = false,
        IReadOnlyList<ExternalReportingTarget>? targets                             = null,
        bool                                    honourInboundCommands               = false,
        bool                                    restrictExternalRepliesToDecodeFilter = false)
    {
        Enabled                               = enabled;
        Targets                               = targets ?? [];
        HonourInboundCommands                = honourInboundCommands;
        RestrictExternalRepliesToDecodeFilter = restrictExternalRepliesToDecodeFilter;
    }

    // ... existing members unchanged ...

    /// <summary>
    /// When <c>false</c> (default), an inbound Reply naming a callsign that is currently hidden
    /// under the operator's decode-panel filter (<c>DecodeFilterState</c>) is still honoured —
    /// an explicit external command is treated as authoritative regardless of what the operator
    /// happens to have filtered from their own view. When <c>true</c>, the pre-existing stricter
    /// behaviour is preserved: a filtered-out callsign is rejected exactly as an unrecognised one
    /// would be. Only meaningful when <c>honourInboundCommands</c> is also <c>true</c> — Reply is
    /// discarded entirely before this flag is ever consulted otherwise.
    /// </summary>
    public bool RestrictExternalRepliesToDecodeFilter { get; init; } = false;
}
```

Naming is a suggestion, not a mandate — pick whatever reads best, but keep the **default-permits**
direction: unchecked/`false` must mean "send/engage everything," matching the Captain's explicit
ask, not the other way around.

### 2.1 What must stay exactly as-is (do not touch)

- The **manual, human-driven** paths — a browser operator double-clicking a row, `POST
  /api/v1/tx/select-responder`, `POST /api/v1/tx/engage-decode` — must keep respecting the
  decode-panel filter unconditionally, always. This new setting affects **only** requests arriving
  through the `external-reporting` inbound-command path.
- The internal auto-answer CQ scan (`QsoAnswererService`'s `HandleIdleAsync`,
  `DecodeFilterEvaluator.IsVisible` check at `QsoAnswererService.cs:805`) and the internal
  auto-call responder scan (`QsoCallerService.cs:745-752`) are automation preferences, not external
  communication — leave both unconditionally filtered, untouched by this flag.
- `ExternalReportingService`'s own absolute synthetic/unknown-region exclusion
  (`IsSuppressedCallsign`) is a separate, non-negotiable guarantee (Captain's prior directive, no
  exceptions) — this new setting must never be able to override it. A synthetic/unknown-region
  callsign named in an inbound Reply should still fail to engage regardless of this flag's value
  (worth an explicit test — see §4).

### 2.2 `QsoAnswererService.TryEngageExternal` — straightforward

This method's filter check is already self-contained (its own inline scan, not shared with
`HandleIdleAsync`'s auto-answer loop). Just make the `IsVisible` check conditional:

```csharp
var restrictToFilter = _configStore.Current.ExternalReporting?.RestrictExternalRepliesToDecodeFilter ?? false;
var filterState       = _decodeFilterStore?.Current ?? DecodeFilterState.Unfiltered;
...
if (restrictToFilter && !DecodeFilterEvaluator.IsVisible(r, filterState))
{
    _logger.LogInformation(/* unchanged message */);
    return Task.FromResult(false);
}
```

### 2.3 `QsoCallerService` — needs a small refactor, your call on exact shape

`TryEngageExternalResponder` reuses `SelectResponderAsync` "unmodified" by design (existing doc
comment, `QsoCallerService.cs:365-382`, referencing the original `gridtracker-udp-reporting`
design.md Decision 4). But `SelectResponderAsync`'s filter gate is baked into the same method that
also does the state transition, and that method is **also** the public seam the manual
`POST /api/v1/tx/select-responder` endpoint calls — which must keep filtering unconditionally
(§2.1). You cannot just make `SelectResponderAsync`'s existing check conditional on the new flag,
because that would also loosen the manual/browser path, which must not change.

Suggested shape (adjust to taste): extract the state-transition body of `SelectResponderAsync`
(lines ~335-363 — the `responseIsAPhase`/`_pendingResponder*` assignment and wakeup) into a private
helper, e.g. `SelectResponderCore(string callsign, double frequencyHz, DateTimeOffset
responseCycleStart, DecodeResult? recentDecode)`. `SelectResponderAsync` keeps its existing,
unconditional filter check (§2.1) and then calls the core. `TryEngageExternalResponder` performs
its **own** conditional filter check (reading `RestrictExternalRepliesToDecodeFilter`, mirroring
§2.2) against `_recentResponderDecodes` directly, then calls the same private core — bypassing
`SelectResponderAsync`'s own gate entirely when the flag is at its default (`false`). This keeps
the state-transition logic in exactly one place while letting the two call sites disagree about
when the filter applies. If you find a cleaner shape, use it — the requirement is just: manual
path always filters, external-Reply path filters only when the new setting is `true`, and the
actual "arm the pending responder" logic is not duplicated.

---

## 3. Settings UI — `web/settings.html` / `web/js/settings.js`

Add a new checkbox inside the existing `#ext-rep-inbound-fieldset` (`web/settings.html:798-814`),
nested under/beside "Honour inbound commands" since it's only meaningful when that one is checked:

```html
<div class="field-group">
  <label class="checkbox-label">
    <input type="checkbox" id="ext-rep-restrict-replies-to-filter" />
    Restrict external Reply to the current decode-panel filter
  </label>
  <p class="field-hint">
    Unchecked (default): a third-party program can Reply to any currently decoded station,
    regardless of what your own decode-panel filter is hiding. Checked: an external Reply naming a
    filtered-out station is ignored, matching the decode panel's own visibility exactly. Only
    applies while "Honour inbound commands" above is also checked.
  </p>
</div>
```

`web/js/settings.js` — three spots, mirroring `extRepHonourInbound`'s existing pattern exactly:

1. New `const` alongside line 118:
   `const extRepRestrictReplies = /** @type {HTMLInputElement} */ (document.getElementById('ext-rep-restrict-replies-to-filter'));`
2. Load (pre-fill), alongside line 886:
   `if (extRepRestrictReplies) extRepRestrictReplies.checked = extRep.restrictExternalRepliesToDecodeFilter ?? false;`
3. Dirty-state snapshot, alongside line 401:
   `restrictExternalRepliesToDecodeFilter: extRepRestrictReplies?.checked ?? false,`
4. Save payload, alongside line 1331:
   `restrictExternalRepliesToDecodeFilter: extRepRestrictReplies?.checked ?? false,`

Consider whether the checkbox should be visually disabled when "Honour inbound commands" is
unchecked (it has no effect either way, but disabling avoids a confusing "why doesn't this do
anything" moment) — your call, not a hard requirement.

---

## 4. Tests

- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs`:
  - Amend `TryEngageExternal_FilteredOutCallsign_NoOp` (line 177) to explicitly set
    `RestrictExternalRepliesToDecodeFilter = true` in its config, since that is now what makes the
    scenario reject.
  - Add `TryEngageExternal_FilteredOutCallsign_DefaultEngagesAnyway` — same filtered-out setup, but
    `RestrictExternalRepliesToDecodeFilter` left at its default (`false`) — assert `engaged` is
    `true`.
  - Add a regression test that a **synthetic/unknown-region** callsign named in an external Reply
    still fails to engage regardless of the new flag's value (§2.1's non-negotiable exclusion) —
    check whatever this codebase currently uses to represent synthetic callsigns in this test file
    (region resolution isn't wired into these unit tests today; if `TryEngageExternal` itself has
    no region awareness, confirm with the design in §2.1 whether this exclusion needs to move
    here, or whether it is already adequately covered by `ExternalReportingService` never being
    able to *originate* the Reply for such a station in the first place — flag back to QA if this
    reveals a real gap rather than deciding unilaterally).
- New test file or additions to whatever covers `QsoCallerService`'s external-reply path today
  (I did not find a dedicated `QsoCallerServiceExternalReplyTests.cs` — check
  `QsoCallerServiceTests.cs` for existing `TryEngageExternalResponder` coverage before assuming
  none exists) — mirror the same two scenarios: filtered-out + restrict-flag-true rejects,
  filtered-out + restrict-flag-false (default) engages.
- `tests/OpenWSFZ.Config.Tests/ExternalReportingConfigTests.cs` — round-trip test for the new field
  (default `false`, missing-key-deserialises-to-`false`), mirroring existing coverage for
  `honourInboundCommands`.
- `tests/OpenWSFZ.Web.Tests/ExternalReportingConfigValidationTests.cs` — check whether this needs a
  new case; likely not (no new validation constraint, just a bool), but confirm.

**Per project policy (decode-panel-filtering live-verification):** this change touches the
answerer/caller filtering hook directly (`DecodeFilterEvaluator`/`DecodeFilterState` consulted at
a new conditional call site in both services). Re-run
`qa/decode-filter-synth-verify/live_verify_9_axes.py` before this merges, in addition to the unit
coverage above — do not treat unit tests alone as sufficient here.

---

## 5. Documentation

This changes previously-shipped, spec'd, tested behaviour (`gridtracker-udp-reporting`, FR-054,
archived) at the Captain's explicit request — it needs a proper OpenSpec change, not a silent
patch:

- Open a new change (suggested name: `external-reply-decode-filter-bypass`, or your preference).
  `**User-facing:** yes` — it's a new Settings-page checkbox and a default-behaviour change for
  anyone using GridTracker's Reply command today with a narrowed decode-panel filter.
- Delta specs to amend:
  - `openspec/specs/qso-answerer/spec.md` — amend the "External reply to a filtered-out callsign
    is a no-op" scenario (line 221) to be conditional on
    `externalReporting.restrictExternalRepliesToDecodeFilter = true`; add a new scenario for the
    default (`false`) case bypassing the filter.
  - `openspec/specs/qso-caller/spec.md` — same amendment to the "None mode — SelectResponderAsync
    rejects a filtered-out callsign" scenario (line 173), scoped explicitly to the
    external-Reply entry point only (the manual/browser entry point is unaffected — make sure the
    delta spec is precise about which caller of `SelectResponderAsync` the exception applies to).
  - `openspec/specs/external-reporting/spec.md` — add the new config field (near the existing
    `honourInboundCommands` documentation, ~line 245-268) and a new Settings-page requirement
    clause (~line 319) for the checkbox.
- `REQUIREMENTS.md` — amend **FR-054** (it currently says "engaging a named, currently-decoded,
  non-filtered-out CQ" — that clause becomes conditional) and add a revision-history row per the
  existing convention (see rows 1.35/1.36/1.38 for the "found during pre-merge review, bump before
  merge" pattern if this lands before archiving, or the archive-time pattern otherwise — check
  current `main` state before deciding which).
- Bump `VERSION` per the minor-version-per-user-facing-feature rule once merged/archived (not
  before — follow the same timing convention documented in REQUIREMENTS.md's own changelog rows).

---

## 6. Acceptance Criteria

- [ ] **AC-1:** Default config (`restrictExternalRepliesToDecodeFilter` absent/`false`): an
  external Reply naming a filtered-out-but-otherwise-valid callsign engages successfully, on both
  Answerer and Caller roles.
- [ ] **AC-2:** `restrictExternalRepliesToDecodeFilter: true`: behaviour is identical to today —
  a filtered-out callsign is rejected, on both roles.
- [ ] **AC-3:** The manual/browser engagement paths (`POST /api/v1/tx/select-responder`, `POST
  /api/v1/tx/engage-decode`, double-click) are unaffected by this flag in either state — always
  filtered, exactly as today.
- [ ] **AC-4:** The internal auto-answer/auto-call automation paths are unaffected by this flag in
  either state — always filtered, exactly as today.
- [ ] **AC-5:** The absolute synthetic/unknown-region exclusion on all external output is
  unaffected — confirmed not overridable by this or any other setting.
- [ ] **AC-6:** `qa/decode-filter-synth-verify/live_verify_9_axes.py` re-run and passing.
- [ ] **AC-7:** `openspec validate --strict --all` passes.
- [ ] **AC-8:** Full test suite green; no regression in existing `QsoAnswererServiceExternalReplyTests`,
  `QsoCallerServiceTests`, `ExternalReportingConfigTests`.
- [ ] **AC-9:** `python3 tools/pre_merge_check.py` clean before this is called ready for merge
  (HK-006).

---

## 7. References

- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:359-413` (`TryEngageExternal`).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:316-413` (`SelectResponderAsync`,
  `TryEngageExternalResponder`).
- `src/OpenWSFZ.Abstractions/ExternalReportingConfig.cs`.
- `web/settings.html:798-814`, `web/js/settings.js:118,398-402,884-887,1328-1332`.
- `openspec/specs/qso-answerer/spec.md:185-233` (FR-054's delta), `openspec/specs/qso-caller/spec.md:96-186`.
- `openspec/specs/external-reporting/spec.md:263-336`.
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceExternalReplyTests.cs`.
- `dev-tasks/2026-07-12-gridtracker-udp-reporting-review-fixes.md` — the prior review that
  established the absolute synthetic/unknown-region exclusion this change must not weaken.
- Decode-filter live-verify policy (project memory
  `decode-panel-filtering-live-verification-policy.md`).
