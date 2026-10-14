## Context

`IsPlausibleMessage` (`src/OpenWSFZ.Ft8/Ft8Decoder.cs`) is a managed false-decode filter applied after the decode. Three
legitimate forms are rejected (proposal). The Architect's spec (`qa/rr-study/2026-10-10-1600-architect-to-qa-spec-plausibility-fix.md`,
§1) fixes the rules; this file records the decisions around them.

## Decisions

### D1. Acceptance-only, proven mechanically

Each rule only turns a rejection into an acceptance. That is a claim about a nested set of conditions, so it is checked by
PV-0b (old accepts ⇒ new accepts over about 125,000 real texts plus the spec §2 negatives), run **before** any replay, not
argued from the diff.

### D2. #226: either half may be the base call

Today's rule is kept as branch (a). Branch (b) is added: L is a prefix shape and R is a callsign shape. The prefix grammar is the
one `TryParseCallsignShape` already uses (1-4 alphanumerics with at least one letter), so no new grammar is invented. The
exclusion check applies to the half that is the base, plus L under (b), so a reserved prefix cannot be laundered through
`RESERVED/Q1ABC`. Two or more `/` stay as today; QA reports their count from the A desk data.

### D3. #227: the modifier is exempt only in this one message shape

`IsCallsignShapeInvalid` is called on token 1 of every 3-token message, which is why a 4-letter modifier fails today. The
exemption is therefore applied in the 3-token branch **only when token 0 is `CQ` and token 1 is a modifier**, not inside
`IsCallsignShapeInvalid`. The accept SHALL short-circuit **before** the last-field rule (`:984-985`), which would otherwise
reject a call in the last position. The Developer must keep the order: the other rules (hex dump, 5+ tokens) still run first.

### D4. #228: keep the other 4-token rejection

A non-`CQ` 4-token message stays rejected unless token 2 is exactly `R` and token 3 is a valid grid (`[A-R]{2}[0-9]{2}`, so
`SS42` is out). Tokens 0 and 1 are each a hash reference or shape-valid. The false-alarm evidence for the old blanket rule
(D-009 R2, Category A) predates the OSD sign fix (#215), so the comment is corrected rather than the old evidence relied on;
PV-3 and PV-4 measure the actual false-accept cost of the new rule.

### D5. Validation is product-path, pre-registered, and scoped by form

OLD (`origin/main`) and NEW (the Developer's build) run the same native DLL (shim 20260060); only the managed filter differs.
Both run through the product path (two-stage call, plausibility, dedup), because the filter's acceptances change what the residual
pass subtracts. Bars (spec §4, §4b; every number's source is stated there per HK-038):

- PV-0 desk (A re-run), PV-0b mechanical proof, PV-1 no loss ≤ max(0.5 %, 3φ) with φ from an OLD-vs-OLD leg, PV-2 gain (descriptive),
  PV-3 per form for #226 and #227 (`F_f` ≤ 0.10 × `G_f`) with #228 descriptive, PV-4 noise (a gross check only).
- Stop rules are scoped (HK-025(ab)): PV-1 fired holds the PR; PV-3 or PV-4 fired holds the forms that fired; PV-0/PV-0b fired
  goes back to the Developer before any replay.

### D6. Region lookup

The region lookup is advisory and untouched. QA checks that it does not throw on the new forms (`QA4/Q1ABC`, `CQ POTA Q1ABC`).
A poor region for those forms is a separate issue, not a blocker.

## Risks

- A real false decode of one of the new forms is now displayed instead of dropped. Bounded by PV-3/PV-4; one night, one band.
- The new forms enter the QSO layer's input: QA checks that no QSO state machine treats `CQ <mod> <call>` or `PREFIX/CALL` as a
  grid or report (#192 is a known related defect, out of scope).
