**User-facing:** yes

## Why

Live testing on 2026-07-16 (`logs/openswfz-20260716T194057Z.log:686-761`) engaged and transmitted twice
to `6KER05BPPBQ` — a decoded token that is not a plausible amateur radio callsign — before the
operator manually aborted. No gate anywhere between "decode displayed" and "decode transmitted"
checks callsign plausibility beyond the existing, deliberately permissive shape grammar
(`callsign-structure-validation`), which exists to protect genuine rare/special-event calls from
being silently dropped and must not be tightened. Separately, the app already loads a comprehensive
real-world prefix table (`ICallsignRegionStore`, sourced from country-files.com, ~29,013 entries once
an operator has run a region-data refresh) but only ever asks "did *any* prefix match?" — a boolean
used solely for advisory display and an optional decode-visibility filter. Confirmed live: `"6K"`
(Republic of Korea) is a genuine entry in the loaded table, so that boolean check passed even though
the other nine characters of the token are nonsense. Nothing today asks whether the matched prefix
explains the *entire* token — that gap is what let a bogus target reach TX, arm AP-decode
constraints, and come within one confirmation of being logged to `ADIF.log` as a worked contact.

## What Changes

- New gate, checked only at the point a decode becomes a **TX-engagement target** — manual
  `POST /api/v1/tx/engage-decode`, `QsoAnswererService` auto-answer arming, and
  `QsoCallerService` responder matching — before a callsign can be transmitted to, before AP-decode
  constraints are armed for it, and before it could ever reach `AdifLogWriter`.
- The gate activates only when `ICallsignRegionStore` holds real/comprehensive data (not the small
  seed table). When only seed data is loaded, the gate no-ops and today's fully permissive
  engagement behaviour is preserved unchanged.
- When real data is loaded: find the longest region-store prefix match for the candidate token. If
  no prefix matches at all, do **not** reject (an unlisted-but-potentially-real prefix is not treated
  as invalid). If a prefix does match, the remainder of the token immediately following that
  prefix must conform to the existing digit-run + suffix grammar already defined by
  `ICallsignGrammarStore` (`callsign-grammar.json`) — reused, not duplicated. If it doesn't fit,
  the engagement attempt is rejected with an operator-visible signal; the underlying decode is
  otherwise untouched.
- Explicitly **not** changed: decoder tuning parameters (Pass-1 Score Floor / OSD Correlation
  Threshold / OSD Max Hard Errors — R&R-validated, orthogonal concern), the
  `callsign-structure-validation` capability itself (decode acceptance / `ALL.TXT` / decode-panel
  visibility stays exactly as permissive as today), and the `region-lookup` capability's existing
  "advisory, never gates decode acceptance" guarantee — this is a new decision point (engagement
  eligibility), not a change to decode acceptance, so that guarantee is not contradicted.

## Capabilities

### New Capabilities
- `engagement-target-validation`: gates whether a decoded callsign token may be armed as a live
  TX-engagement target (manual engage-decode, auto-answer, responder-matching), using the
  already-loaded region-lookup prefix table anchored against the existing callsign-grammar
  digit-run/suffix rules — distinct from, and strictly narrower than, decode acceptance.

### Modified Capabilities
(none — `callsign-structure-validation` and `region-lookup` requirements are unchanged; this change
only adds a new consumer of `ICallsignRegionStore`/`ICallsignGrammarStore` at a decision point that
did not previously exist)

## Impact

- `src/OpenWSFZ.Web/WebApp.cs` — `engage-decode` endpoint dispatch (~1302-1440): new validation call
  before dispatching to `AnswerCqAsync`/directed-message engagement.
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `ArmPendingTarget`/`AnswerCqAsync` (~294-423) auto-answer
  arming path; `ApplyApConstraints` call site (~861) must not be reached for a rejected target.
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — responder-matching path (`TryParseResponder` /
  `RetryOrAbortAsync` region, ~1224-1292) gets the equivalent check.
- `src/OpenWSFZ.Daemon/CallsignRegionStore.cs` / `CallsignRegionDefaults.cs` — needs a reliable
  real-data-vs-seed-data signal exposed for the new gate to consult (none exists today).
- No change to `Ft8Decoder.cs`'s `IsPlausibleMessage`/`IsCallsignShapeInvalid`, no change to
  `ALL.TXT` output, no change to decode-panel visibility or worked-before indicators.
