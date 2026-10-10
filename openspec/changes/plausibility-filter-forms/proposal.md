**User-facing:** yes

## Why

STRONG-MISS follow-up A (`qa/rr-study/2026-10-10-1500-…-followup-a-result.md`, QA `fdd43a15`) ran the product's own
`Ft8Decoder.IsPlausibleMessage` over every WSJT-X row of endurance night `20261009_1752`. It would reject **1,805 of
30,978** non-`;` WSJT-X-only rows (5.83 % [5.57, 6.09]) and **0 of 62,340 matched rows**. Three legitimate forms are
rejected (all numbers are upper bounds from one night):

| Issue | Form | Rejected WSJT-X-only rows | Cause (on `origin/main` `8256a48f`) |
|---|---|---:|---|
| #226 | compound `PREFIX/CALL` (e.g. `QA4/Q1ABC`) | ≤ 1,217 | `IsCallsignShapeInvalid` always parses the part before `/` as the base call (`Ft8Decoder.cs:1074-1075`, `:1083`); a bare prefix has no suffix letters |
| #227 | `CQ <modifier> <call>` with no grid (e.g. `CQ POTA Q1ABC`) | ≤ 513 | a 4-letter modifier fails the callsign-shape check on token 1; the last-field rule (`:984-985`) then rejects the call |
| #228 | `CALL CALL R GRID` (e.g. `Q1ABC Q2XYZ R FN42`) | ≤ 14 | 4-token branch rejects every non-`CQ` message (`:933-934`); the stated reason ("not Type 1") is wrong, ft8_lib renders this form (`message.c:952-953`) |

The Captain's go ("option 2 first", Architect's window; confirmed in QA's window 2026-10-10 ~16:10Z): fix these three
before any further investigation. The Architect's spec is `qa/rr-study/2026-10-10-1600-architect-to-qa-spec-plausibility-fix.md`
(`arch/plausibility-fix`), with amendment 1 (QA's (k) review, accepted in full).

## What Changes

Managed code only, `src/OpenWSFZ.Ft8/Ft8Decoder.cs`; **nothing in `native/`**. Three **acceptance-only** changes: each makes the
filter accept a legitimate form it rejects today, and **no text accepted today may be rejected afterwards**.

- **#226:** for a token with exactly one `/`, shape-valid if the left half parses as a callsign (today's rule), **or** the
  right half parses as a callsign shape and the left half is a prefix shape (1-4 alphanumerics, at least one letter).
- **#227:** accept `CQ <modifier> <call>` (modifier: 1-4 letters A-Z, or exactly 3 digits; call shape-valid), the modifier
  exempt from the callsign-shape check in this case only.
- **#228:** accept a non-`CQ` 4-token message `T0 T1 R GRID` where `GRID` matches `[A-R]{2}[0-9]{2}` and `T0`, `T1` are each a hash
  reference or shape-valid. Correct the wrong comment at `:930-931`, noting that the rule's D-009 evidence predates the
  OSD sign fix (#215).

Not changed: 5+ tokens, `CQ <hash>`, hex dump, single token, bad-grid letters, dB-report and terminal rules, the region
lookup (advisory), tokens with two or more `/`.

## Impact

- **Code:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs` and its unit tests. Version bump per the usual gate (G9b).
- **User-facing:** the decode panel and ALL.TXT gain rows of these forms that were silently dropped.
- 🔴 **New data era on deploy:** the station's OpenWSFZ output gains forms it never had. Matched and OWS-only counts must not
  be pooled across the deploy cycle; QA opens the era on the board as with OSD-FIX.
- **Out of scope:** #225 (DXpedition/contest unpacking), #192 (RR73 parsed as a grid). Separate changes.
- **Validation (QA, offline, before the PR):** `design.md` D5 and `tasks.md` §4; bars PV-0, PV-0b, PV-1 (with the OLD-vs-OLD
  floor), PV-2, PV-3 per form, PV-4, frozen in the Architect's spec §4 and §4b.
