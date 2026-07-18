## 1. `ICallsignRegionStore` additive API (Decisions 1 & 2)

- [x] 1.1 Add `CallsignRegionMatch(RegionInfo Region, int MatchedPrefixLength)` record to
      `src/OpenWSFZ.Abstractions/CallsignRegionEntry.cs` (or a new file alongside it).
- [x] 1.2 Add `CallsignRegionMatch? TryMatchPrefix(string callsignToken)` to
      `ICallsignRegionStore` (`src/OpenWSFZ.Abstractions/ICallsignRegionStore.cs`).
- [x] 1.3 Implement `TryMatchPrefix` in `CallsignRegionStore.cs`, reusing the existing
      longest-prefix-match loop; reimplement `TryGetRegion` as `TryMatchPrefix(token)?.Region` so
      there is exactly one matching implementation.
- [x] 1.4 Add `bool IsSeedData { get; }` to `ICallsignRegionStore`; set `false` in
      `CallsignRegionStore` the moment a real on-disk `callsign-regions.json` is loaded at startup
      (as opposed to falling back to `CallsignRegionDefaults.Entries`), and set `false` after any
      successful `SaveAsync` (the region-data-refresh path). Starts `true` on a fresh
      seed-data-only daemon.
- [x] 1.5 Unit tests: `TryMatchPrefix` returns the same `RegionInfo` as `TryGetRegion` for existing
      cases plus the matched-prefix length for a representative set of entries; `IsSeedData` is
      `true` on fresh seed data, `false` after loading a real file, `false` after `SaveAsync`.
- [x] 1.6 **Correction found in QA code review (2026-07-17, dev-task
      `2026-07-17-engagement-target-validation-qa-review-findings`, Finding E):** `LoadAsync`'s
      file-present branch set `IsSeedData = false` unconditionally the moment any on-disk file was
      read — including the very file the file-absent branch itself had just seed-written on the
      daemon's first-ever run. Since that write leaves the file present for every later launch,
      this meant any daemon restarted even once, ever, reported `IsSeedData == false` regardless of
      whether an operator had ever refreshed — silently defeating Decision 2's "no behaviour change
      on seed data" goal from the second launch onward. Fixed by persisting an explicit provenance
      marker (`isSeedData: bool`) inside `callsign-regions.json` itself
      (`CallsignRegionsFile.IsSeedData`, `CallsignJsonContext.cs`): the seed-write branch writes it
      `true`; `SaveAsync` always writes it `false`; the file-present load branch reads the marker
      from the file's own content. A pre-existing file predating this marker deserialises it as
      `false` (documented migration choice — see `design.md` Decision 2's correction note). Three
      new tests in `CallsignRegionStoreTests.cs`: seed-write-then-restart stays `true`;
      refresh-then-restart reports `false`; pre-existing file with no marker migrates to `false`.

## 2. Portable-suffix helper extraction

- [x] 2.1 Promote `Ft8Decoder.StripPortableSuffix` (`src/OpenWSFZ.Ft8/Ft8Decoder.cs:868`) out of
      `Ft8Decoder` into a shared static location reachable from `OpenWSFZ.Daemon` (e.g.
      `OpenWSFZ.Abstractions`), and update `Ft8Decoder` to call the shared version. Confirm
      existing `Ft8Decoder` shape-grammar tests still pass unmodified — this is a pure relocation,
      no behaviour change.

## 3. `IEngagementTargetValidator` (Decisions 3 & 4)

- [x] 3.1 Define `IEngagementTargetValidator` in `OpenWSFZ.Abstractions` with
      `EngagementValidationResult Validate(string callsignToken)`, where
      `EngagementValidationResult` is `Allowed` or `Rejected(string Reason)`.
- [x] 3.2 Implement `EngagementTargetValidator` in `OpenWSFZ.Daemon`, injecting
      `ICallsignRegionStore` and `ICallsignGrammarStore`. Algorithm: `IsSeedData` short-circuit →
      `Allowed`; strip portable suffix (task 2.1's shared helper); `TryMatchPrefix`; no match →
      `Allowed`; match found → validate remainder against `grammarStore.Current.DigitRunMax` /
      `SuffixLengthMax` (digit-run first, consuming 1..DigitRunMax digits, then 0..SuffixLengthMax
      letters, consuming the entire remainder) → `Allowed`/`Rejected`.
- [x] 3.3 Register `IEngagementTargetValidator` → `EngagementTargetValidator` in DI wiring
      (`Program.cs`, alongside the existing `ICallsignRegionStore`/`ICallsignGrammarStore`
      registrations).
- [x] 3.4 Unit tests covering all five spec scenarios directly against the validator: real prefix +
      valid remainder → `Allowed`; real prefix (`"6K"`) + invalid remainder (the exact
      `6KER05BPPBQ` incident shape) → `Rejected`; no prefix match at all → `Allowed`;
      `IsSeedData == true` → `Allowed` unconditionally regardless of token; portable-suffix token
      validated on base call only.
- [x] 3.5 **Correction found live during task 7.3's manual verification (2026-07-17):** the
      original `RemainderFitsGrammar` unconditionally required the remainder to start with a
      digit-run, assuming a matched region-store prefix is always purely alphabetic. Real
      country-files.com data commonly isn't — it breaks a single DXCC entity down by call-district
      with the digit baked into the matched prefix itself (e.g. `"EC5"` for a specific Spanish call
      district). This rejected essentially every genuine callsign whose match happened to include
      its call-area digit — observed live rejecting `EC5M` and five more real calls in one short
      session ("for every CQ I want to engage I get a warning"). Fixed: `RemainderFitsGrammar` now
      inspects the matched prefix for a digit first — prefix-has-digit → remainder is
      suffix-only (0..`SuffixLengthMax` letters); prefix-has-no-digit → original digit-run+suffix
      shape. `6KER05BPPBQ` still rejects correctly (its remainder is 9 characters, over
      `SuffixLengthMax` either way). `design.md` Decision 3 and `specs/engagement-target-validation/
      spec.md` updated with a new scenario and the corrected requirement text; 4 new regression
      unit tests added (`EngagementTargetValidatorTests.cs`) covering the `EC5M` case plus
      digit-carrying-prefix edge cases (extra digit in remainder, remainder too long, empty
      remainder).
- [x] 3.6 **Correction found in QA code review (2026-07-17, dev-task
      `2026-07-17-engagement-target-validation-qa-review-findings`, Finding D — likely root cause
      of the live-verification dev-task's still-open Finding B):** task 3.5's fix assumed a digit
      inside the matched prefix always means the whole mandatory call-area digit was already
      consumed by the prefix. False for any DXCC entity whose region-store prefix is itself
      digit-leading as part of the entity identifier rather than the call-district marker (e.g.
      `"3A"` for Monaco; genuine calls `3A2...` — the `'2'` is the real call-area digit, still owned
      by the remainder). Fixed: `RemainderFitsGrammar` now tries **both** remainder shapes when the
      matched prefix contains a digit (letters-only suffix, or digit-run-then-suffix via the new
      `FitsDigitRunThenSuffix` helper) and rejects only if neither fits. `design.md` Decision 3 and
      `specs/engagement-target-validation/spec.md` updated with a new scenario. Three new regression
      tests (`EngagementTargetValidatorTests.cs`): `3A2XYZ` (Allowed), a `TM100XYZ`-shaped case
      (Allowed, matched prefix's digit-run boundary lands inside the true digit-run), and an
      explicit neither-shape-fits-still-Rejected regression re-confirming `6KER05BPPBQ`. **Not yet
      re-verified against a live region-data-refreshed daemon** — re-run task 7.3 before considering
      Finding B closed.

## 4. Manual engagement — `POST /api/v1/tx/engage-decode` (`WebApp.cs`)

- [x] 4.1 Add an optional `confirm: bool` field to the `engage-decode` request DTO.
- [x] 4.2 At the dispatch point(s) that extract the target callsign (`WebApp.cs` ~1369-1440, both
      the CQ-row and directed-message branches), call `IEngagementTargetValidator.Validate` before
      calling into `IQsoController`. On `Rejected` with `confirm != true`, return an error response
      (reason + `requiresConfirmation: true`) and do not call the controller. On `Rejected` with
      `confirm == true`, proceed as today. On `Allowed`, proceed as today (no behaviour change).
- [x] 4.3 Frontend: surface the confirmation prompt when `requiresConfirmation` comes back (decode
      panel double-click handler), re-issuing the request with `confirm: true` on operator
      acceptance. Exact wording/UX at implementer's discretion, per design.md's open question.
- [x] 4.4 Integration test (`tests/OpenWSFZ.Web.Tests/`, likely `EngageDecodeEndpointTests.cs`):
      first request against a rejected target returns the confirmation-required error and does not
      arm/transmit; a follow-up request with `confirm: true` arms the target.
- [x] 4.5 **Correction found in QA code review (2026-07-17, dev-task
      `2026-07-17-engagement-target-validation-qa-review-findings`, Finding F):** the endpoint's
      unconditional "abort any in-progress QSO" step ran *before* task 4.2's validation check, so a
      rejected, unconfirmed target still aborted the operator's prior in-progress QSO for nothing.
      Fixed: extracted the abort into an `AbortIfNotIdleAsync` local function, called only once a
      target is Allowed or explicitly confirmed — immediately before the dispatch it actually gates
      (`AnswerCqAsync`/`EngageAtAsync`) — for both the CQ-row and directed-message branches. The
      `73`-only and not-addressed-to-us branches don't validate a target, so they still abort
      unconditionally, unchanged. `design.md` Decision 4 and
      `specs/engagement-target-validation/spec.md` updated with a new scenario. Two new integration
      tests (`EngageDecodeEndpointTests.cs`) starting from a non-`Idle` state with an active
      partner: a rejected CQ-row target and a rejected directed-message target each leave
      `AbortAsync` uncalled and the prior QSO's state/partner unchanged after the `409`.

## 5. Automated engagement — `QsoAnswererService` and `QsoCallerService`

- [x] 5.1 `QsoAnswererService`: inject `IEngagementTargetValidator`; call it in the CQ auto-answer
      scan path (feeding `ArmPendingTarget`, `QsoAnswererService.cs` ~294-423) before arming. On
      `Rejected`, skip the candidate (log line), do not arm, do not call
      `ApplyApConstraints` (~861), continue scanning.
- [x] 5.2 `QsoCallerService`: inject `IEngagementTargetValidator`; call it in the responder-matching
      path (`TryParseResponder`/equivalent, ~1224-1292) before treating a reply as the active
      partner. On `Rejected`, do not arm the responder as the QSO partner.
- [x] 5.3 Unit tests for both services: a `Rejected` candidate is never armed, no TX is scheduled,
      no AP constraints are armed, and scanning/matching continues for subsequent candidates
      exactly as it does today for any other non-matching candidate.

## 6. Confirm no regression to unrelated capabilities

- [x] 6.1 Confirm `Ft8Decoder.IsPlausibleMessage`/`IsCallsignShapeInvalid`, `ALL.TXT` output, decode
      panel visibility, and `WorkedBeforeIndex`/region display are byte-for-byte unchanged by this
      change — no test modifications expected in `Ft8DecoderTests.cs`,
      `DecodeFilterEvaluatorTests.cs`, `WorkedBeforeIndexTests.cs`, or `RegionLookupTests.cs` beyond
      what tasks 1.x/2.1 already touch.
- [x] 6.2 Re-run the live incident shape as a regression test end-to-end (unit/integration level,
      not necessarily hardware): a decode result carrying `"6KER05BPPBQ"` with real region data
      loaded is (a) still present in a simulated `ALL.TXT`/decode-panel feed, and (b) rejected by
      `IEngagementTargetValidator` when engagement is attempted.

## 7. Verification

- [x] 7.1 `dotnet build` / `dotnet test` — full suite green, new tests included.
- [x] 7.2 `python3 tools/pre_merge_check.py` — run before declaring this ready for merge (per
      standing QA rule; covers Gate G9a, Release build, full suite, Gate G3 requirement
      traceability, `openspec validate --strict --all`, and a real AOT publish). Result: PASS
      WITH WARNINGS — G9a/build/tests/G3/G8 all PASS; AOT publish WARN only, due to this
      machine's local MSVC linker toolchain being incomplete (`vswhere.exe` not found), a
      pre-existing environment gap unrelated to this change. Confirmed not code-related: the
      first run surfaced two real IL2026/IL3050 AOT-trimming errors from `Results.Json(...)`
      calls in `WebApp.cs` using the reflection-based overload instead of the source-gen
      `JsonTypeInfo` one; fixed by passing `AppJsonContext.Default.EngagementRejectedResponse`
      explicitly — the re-run then got past code generation entirely and failed only at the
      native `link.exe` invocation stage.
      **Re-run 2026-07-17 after landing Findings D/E/F (dev-task
      `2026-07-17-engagement-target-validation-qa-review-findings`):** PASS WITH WARNINGS again —
      G9a/build/tests/G3/G8 all PASS (full suite, 1102 non-skipped tests including the new
      regression coverage for D/E/F); AOT publish WARN only, same pre-existing local-toolchain gap
      (`vswhere.exe` not found), unrelated to this change.
- [x] 7.3 Manual/hardware verification. **Done 2026-07-17/18, real station** (against the
      Captain's own daemon — real CAT, real WASAPI capture, real 29,013-entry country-files.com
      `callsign-regions.json`, real `POST /api/v1/tx/engage-decode` — not a mock/unit test). Ran
      via `POST /api/v1/tx/engage-decode` probes against the running production daemon (Debug
      build carrying the D/E/F fixes, launched on the Captain's normal port 8080):
      - **Finding D confirmed live:** `3A2TEST` (Monaco — the exact digit-leading-entity shape
        Finding D fixed, matched against the Captain's real `"3A"` entry) → `200` Allowed. `EC5TEST`
        (Spain, Finding A's shape) → `200` Allowed. `DL1TEST` (no-digit-prefix baseline) → `200`
        Allowed. The original incident shape, reproduced against the real `"6K"` entry
        (`6KERTESTX`) → `409` Rejected with the correct reason, and a real Finding-A-shaped
        digit-carrying-prefix reject (`EC5A1B`) → `409` Rejected. All five matched expectations.
      - **Finding E confirmed live:** triggered a genuine graceful production restart via
        `POST /api/v1/system/restart` (spawn-replacement-then-stop, the real operator-facing
        mechanism — not a simulated restart). Re-ran the `6KERTESTX` reject probe against the
        freshly-restarted instance: still `409` Rejected, proving `IsSeedData` correctly persisted
        `false` across a real restart rather than silently drifting back to gate-inactive.
      - **Finding F:** not separately live-exercised — it's a pure `WebApp.cs` ordering fix,
        independent of decoder/region-data specifics (unlike D/E, it wasn't found via live testing
        in the first place), and is already covered by two integration tests
        (`EngageDecodeEndpointTests.cs`) with a controllable mock `IQsoController`, which is a
        better instrument for it than real hardware timing.
      - **Incident during this pass, disclosed in full:** the first probe batch's "arm an Allowed
        target, then immediately abort" safety plan assumed `ArmPendingTarget`'s phase gate gives a
        multi-second buffer before a pending target is eligible to fire. It doesn't when
        `cycleStartUtc` is supplied as raw "now" rather than a properly-offset real cycle
        boundary — the target became eligible on the very next processing tick. Real PTT briefly
        keyed (`SerialRtsDtrPttController: KeyDown — PTT asserted (Rts)`, ~60-70 ms, well under one
        FT8 symbol, no coherent audio transmitted) for one probe (`DL1TEST`) before the abort's
        `KeyUpAsync` released it. Two other probes in the same batch were cancelled before PTT
        genuinely keyed. Root cause understood and fixed for the second batch (proper
        `floor15`/phase-mismatch cycle-start computation, matching
        `qa/engage-window-live-verify`'s pattern) — verified with a live 3-second Idle-state
        polling window before abort, zero PTT activity. Daemon confirmed back to clean `Idle` after
        every probe, both before and after the restart.
