# DEV TASK — `engagement-target-validation` live-verification findings (task 7.3)

**Date:** 2026-07-17
**OpenSpec change:** `engagement-target-validation` (not yet archived; still on `feat/engagement-target-validation`)
**Branch:** `feat/engagement-target-validation`
**Status:** Mixed — Finding A is fixed and merged into this branch already; Findings B and C are
**open**, found during the Captain's live manual-verification pass (task 7.3) after Finding A's fix
was believed complete.
**Found by:** QA, via live/manual verification (task 7.3) plus log analysis of two consecutive
daemon sessions (`logs/openswfz-20260717T110622Z.log`, `logs/openswfz-20260717T185140Z.log`).
**Severity:** **High** for Finding B — the capability is currently rejecting genuine, well-formed
real callsigns in normal operation, which is the exact failure mode this capability exists to
*prevent*, not cause. Moderate for Finding C (unrelated crash, self-recovering, one-off so far).

---

## Context — how this was found

`engagement-target-validation` was implemented and all 22 `tasks.md` items were checked off,
including a first pass at task 7.3 (manual verification). The Captain then ran the daemon live and
hit **Finding A** immediately: a genuine Spanish callsign (`EC5M`) was rejected on every engage
attempt. That was root-caused and fixed same-session (see below — already committed to this
branch). A second live session after the fix confirmed the specific `EC5M`-class bug was gone
(two full real QSOs completed with the same shape class: `UT5MD`, `R2AL`), **but also surfaced six
more rejections in the same session**, and the Captain has now confirmed directly: **these are also
real calls, incorrectly rejected.** Root cause for this second wave is not yet identified — see
Finding B for why, and what's needed to unblock it.

---

## Finding A (CLOSED — already fixed on this branch)

### What happened

`EC5M` — a genuine, well-formed Spanish callsign — was rejected on every single engage attempt,
with the dialog: *"'EC5M' matched region prefix 'EC5' (Spain) but the remainder 'M' is not a valid
digit-run+suffix."* Log evidence: `logs/openswfz-20260717T110622Z.log`, 6 of 7 `engage-decode`
calls returned `409` between `20:31:17` and `20:34:20`.

### Root cause

`EngagementTargetValidator`'s original algorithm unconditionally required the remainder (the part
of the base callsign after the matched region-store prefix) to itself start with a digit-run. Real
country-files.com data frequently breaks a single DXCC entity down by call-district, baking the
mandatory call-area digit directly into the matched prefix (`"EC5"` for a specific Spanish call
district, rather than a bare `"EC"`). When that happens the remainder no longer owns a digit to
contribute — the callsign's mandatory digit is already accounted for. The original algorithm
rejected essentially every genuine callsign whose region-store match happened to include its
call-area digit.

### Fix (already applied, this branch)

`src/OpenWSFZ.Daemon/EngagementTargetValidator.cs`, `RemainderFitsGrammar` (lines 63–90): now
inspects the matched prefix for a digit first (`ContainsDigit`, lines 92–97) —
- prefix contains a digit → remainder validated as suffix-only, 0 to `SuffixLengthMax` letters
  (`IsValidSuffix`, lines 100–106);
- prefix contains no digit → original digit-run(1..`DigitRunMax`)-then-suffix shape.

`openspec/changes/engagement-target-validation/design.md` (Decision 3) and
`specs/engagement-target-validation/spec.md` (new scenario: "Matched prefix already contains the
call-area digit — remainder is suffix-only") updated to match. `tasks.md` task 3.5 documents the
correction. Four new regression tests in
`tests/OpenWSFZ.Daemon.Tests/EngagementTargetValidatorTests.cs` cover the `EC5M` shape plus
digit-carrying-prefix edge cases (extra digit in remainder, remainder too long, empty remainder).

### Live confirmation

`logs/openswfz-20260717T185140Z.log`, post-fix session: two full real QSOs completed end-to-end
with the identical bug class (digit embedded in the matched region prefix) — `UT5MD` (Ukraine,
`"UT5"`-shaped match) and `R2AL` (Russia, `"R2"`-shaped match) — CQ answer through to `RR73`/`73`
completion, zero rejections for either. This specific defect is confirmed fixed.

---

## Finding B (OPEN — real calls still being rejected after Finding A's fix)

### What happened

Same post-fix session (`logs/openswfz-20260717T185140Z.log`) that confirmed Finding A's fix also
logged **six more `409` rejections**, spread across the session rather than clustered:

```
20:58:55.225  409
20:59:48.365  409
21:00:02.444  409
21:02:14.437  409
21:05:17.700  409
21:10:49.083  409
```

(13 of the 19 `engage-decode` attempts that session succeeded; 6 didn't.) The Captain has confirmed
directly, after being asked, that **these were also real calls** — not a case of the gate correctly
catching genuine garbage.

### Root cause — **not yet identified**

This is the actual gap QA needs a developer to close. Root-causing is currently **blocked by a
missing diagnostic**: unlike the automated hard-skip paths, the manual `engage-decode` 409 path
never logs which callsign was rejected or why.

- `QsoAnswererService.HandleIdleAsync`'s CQ-scan loop **does** log a skip line on rejection
  (`_logger.LogInformation("QsoAnswererService: skipping auto-answer CQ candidate {Callsign} —
  {Reason}", ...)`), and `QsoCallerService`'s First-mode responder loop does the same.
- `WebApp.cs`'s manual `engage-decode` endpoint (both dispatch points — CQ-row branch around
  line 1387–1393, directed-message branch around line 1435–1441) returns the `409` with the reason
  **in the HTTP response body only**. ASP.NET Core's request logging records the status code
  (`409`) but never the response body, so the rejected callsign and reason are invisible in the
  daemon log — recoverable only by asking the operator to screenshot the confirmation dialog at the
  moment it happens, which doesn't scale past a single lucky catch (Finding A) and has already
  failed to produce a second repro (this finding).

**Recommended first step, before attempting any algorithm change:** add a log line at both `409`
return points in `WebApp.cs` mirroring the pattern already used in `QsoAnswererService`/
`QsoCallerService`. This is a pure observability addition — no behaviour change, low risk — and
should be done **before** the next live session so the next occurrence is diagnosable from the log
alone.

**STATUS: DONE (2026-07-17, same day, this branch).** Added at both `409` return points —
`WebApp.cs`'s CQ-row branch (~line 1397) and directed-message branch (~line 1449) — via a
closed-over `engageDecodeLogger` (category `"OpenWSFZ.Web.EngageDecodeApi"`, following the
existing `tuneLogger` pattern in the same file — `ILogger<WebApp>` doesn't compile since `WebApp`
is itself a static class):

```csharp
engageDecodeLogger.LogInformation(
    "engage-decode: rejecting CQ-row engagement target '{Callsign}' — {Reason}",
    partnerCallsign, cqValidation.RejectionReason);
```

Full suite re-verified green after this addition (243/243 Web, 533/533 Daemon — one
`SelectResponderAsync_PhaseSemanticsCorrect` flake on the first run, confirmed pre-existing/
real-clock-timing-dependent and unrelated: passed in isolation and on full-suite re-run; `WebApp.cs`
doesn't touch `QsoCallerService` — 294/294 Ft8). **Next live session's rejections will now show the
callsign and reason directly in the daemon log — no screenshot needed to root-cause the remaining
open half of this finding.**

### A structural hypothesis worth investigating once real repro data exists

Not confirmed, but worth putting in front of whoever picks this up, because if it holds it points
at a deeper design issue than a one-line patch:

`EngagementTargetValidator` determines where the "digit-run+suffix" tail begins purely from **the
matched region-store prefix's length** — i.e., the split point is whatever the region table says it
is, entry by entry. `Ft8Decoder.TryParseCallsignShape` (`src/OpenWSFZ.Ft8/Ft8Decoder.cs:774`,
called from `IsCallsignShapeInvalid` at line 738) — the pre-existing, already-battle-tested decode-
acceptance grammar check that `engagement-target-validation` is explicitly supposed to be
*consistent with* — determines the same boundary completely differently: by scanning the callsign
itself backward from its **last digit**, independent of any external prefix table.

These two approaches can disagree whenever a region-store entry's prefix boundary doesn't land
exactly where the callsign's own last-digit-anchored digit-run naturally falls — for example (
**illustrative, not confirmed against tonight's actual rejected calls**) a region table entry like
`"TM1"` (one digit) for a callsign whose genuine digit-run is longer or positioned differently than
that one digit implies, e.g. `TM100XYZ`: matched prefix `"TM1"` contains a digit → remainder
`"00XYZ"` is checked as *suffix-only* (letters required) → the leading `"00"` fails that check →
rejected, even though `Ft8Decoder`'s own last-digit-anchored parse of the same callsign (digit-run
`"100"`, suffix `"XYZ"`) would accept it cleanly. Any region-table entry whose prefix boundary
falls **inside** a callsign's true digit-run (rather than exactly before or after it) reproduces
this same disagreement.

If tonight's specific rejections turn out to match this shape (multi-digit call area, region-store
prefix consuming only part of it), the fix is a redesign, not a patch: make the validator anchor its
digit-run/suffix parse on the callsign's own structure (same last-digit-backward logic
`TryParseCallsignShape` already uses) and use the matched region prefix only to confirm the parsed
grammar-prefix component is consistent with (e.g. starts with, or is a prefix of) the matched
region entry — rather than using the matched region prefix's length as the authoritative split
point. This would also need `Ft8Decoder.TryParseCallsignShape` promoted out of `Ft8Decoder` the same
way `StripPortableSuffix` already was (task 2.1), rather than reimplementing it a third time.

**This hypothesis needs real data to confirm or rule out — do not implement the redesign blind.**
Get the callsign log line in first, capture the next occurrence, and check whether the actual
rejected calls fit this shape before deciding whether it's this or something else entirely (e.g. a
Decision-4-acknowledged coarse-vs-specific region-table mismatch, which already has an accepted
manual-path override and wouldn't need an algorithm change at all).

### Tests required (once root cause is confirmed)

- A regression unit test in `EngagementTargetValidatorTests.cs` reproducing the exact real-world
  shape(s) found, once known.
- If the redesign hypothesis is confirmed: full re-verification of the existing digit-in-prefix
  regression tests (Finding A's four tests) plus the original `6KER05BPPBQ` incident test, since a
  parsing-anchor change is a bigger surface than the Finding A patch was.

**UPDATE 2026-07-17/18 — root cause found and fixed, NOT via the redesign hypothesized above.**
QA's code review (`dev-tasks/2026-07-17-engagement-target-validation-qa-review-findings.md`,
Finding D) found the actual defect: `RemainderFitsGrammar` picked exactly one remainder shape from
whether the matched prefix contained a digit, wrongly assuming a prefix digit always means the
callsign's whole call-area digit was consumed by the prefix. False for entities whose region-store
prefix is itself digit-leading as part of the entity identifier (concrete, already-shipping
example: Monaco's `"3A"` — real calls are `3A2...`, so the `'2'` is the real call-area digit, still
owned by the remainder). Fixed by trying both remainder shapes when the prefix carries a digit,
rejecting only if neither fits — the narrower fix, not the `TryParseCallsignShape`-anchored
redesign this section speculated about; that redesign was correctly never attempted blind, per this
section's own caution. **Live-verified 2026-07-17/18** against the Captain's real, running daemon
(real CAT, real 29,013-entry `callsign-regions.json`): `3A2TEST` (the Monaco/`3A` shape) now
engages cleanly (`200` Allowed); the `6K`-incident shape still correctly `409` Rejects. See
`openspec/changes/engagement-target-validation/tasks.md` task 7.3 for the full live-verification
record, including the six-test probe battery and the graceful-restart re-check.
**Caveat, for honesty:** this proves the *mechanism* (digit-in-prefix mishandling) is fixed and
demonstrates it live on a real digit-leading-entity call — it does not independently prove the
*specific* six calls rejected in the 2026-07-17 evening session were this exact shape, since no log
line ever captured those six calls' actual callsigns (the diagnostic logging fix landed the same
session, but the one live session run since then — `logs/openswfz-20260717T213403Z.log`, analysed
separately — saw zero rejections at all, so there was nothing further to compare against). Treat
Finding B as **resolved by strong circumstantial evidence** (the exact bug class is fixed and
proven live on real data) rather than a byte-for-byte replay of the original six incidents.

---

## Finding C (OPEN, low urgency — unrelated to this capability)

### What happened

```
2026-07-17 21:05:26.312 +02:00 [ERR] QsoAnswererService: unexpected error in state "Idle"; resetting to Idle.
System.UnauthorizedAccessException: Access to the path is denied.
   at System.IO.FileSystem.MoveFile(String sourceFullPath, String destFullPath, Boolean overwrite)
   at OpenWSFZ.Config.JsonConfigStore.SaveAsync(AppConfig config, CancellationToken ct) in JsonConfigStore.cs:line 91
   at OpenWSFZ.Daemon.QsoAnswererService.ExecuteTxAnswerAsync(...) in QsoAnswererService.cs:line 849
   at OpenWSFZ.Daemon.QsoAnswererService.HandleIdleAsync(...) in QsoAnswererService.cs:line 732
   at OpenWSFZ.Daemon.QsoAnswererService.ProcessBatchAsync(...) in QsoAnswererService.cs:line 583
   at OpenWSFZ.Daemon.QsoAnswererService.ExecuteAsync(...) in QsoAnswererService.cs:line 495
```

Only occurrence in either log session. The daemon recovered cleanly on its own (reset to Idle,
answered the same partner's next CQ 2.4 seconds later without operator intervention).

### Root cause

**Confirmed, and confirmed unrelated to `engagement-target-validation`** — this code path predates
this change entirely (it's the Task 4.1/4.2 waterfall-cursor `TxAudioOffsetHz` auto-update logic).
`JsonConfigStore.SaveAsync`'s atomic write-then-rename (`File.Move(tmp, _path, overwrite: true)` at
`JsonConfigStore.cs:91`) hit a transient `UnauthorizedAccessException` — the classic Windows
symptom of something else (antivirus real-time scan, backup software, OneDrive, etc.) briefly
holding `config.json` open at the exact moment of rename. `SaveAsync` deliberately re-throws on
failure so callers know ("Clean up the temp file on failure; re-throw so the caller knows" —
`JsonConfigStore.cs:96-101`), which is correct in general, but this particular call site
(`QsoAnswererService.ExecuteTxAnswerAsync`, line 849) is **not** wrapped in a try/catch the way the
sibling `AnswerCqAsync`'s own `SaveAsync` call already is (`QsoAnswererService.cs:301-312`,
`try { ... } catch (Exception ex) { _logger.LogWarning(...); }`) — so a transient lock here silently
drops that entire TX cycle (no answer sent, no operator-facing indication beyond the log) instead
of degrading gracefully like the `AnswerCqAsync` path does.

### Recommended fix (separate, small, standalone dev-task — do not fold into `engagement-target-validation`)

Wrap the `_configStore.SaveAsync(...)` call at `QsoAnswererService.cs:849` in the same
try/catch-and-log pattern `AnswerCqAsync` already uses, so a future transient file lock logs a
warning and continues (falling back to using `frequencyHz` for `txFreqHz` without persisting the
cursor update) instead of aborting the whole TX attempt for that cycle. One regression test:
simulate `IConfigStore.SaveAsync` throwing and assert the TX still proceeds (mirrors whatever
existing test coverage `AnswerCqAsync`'s equivalent try/catch has, if any — check first).

---

## References

- `logs/openswfz-20260717T110622Z.log` — Finding A's original incident (lines ~6470-6790 for the
  six pre-fix `409`s; the `EC5M` screenshot is user-supplied, not itself in the log).
- `logs/openswfz-20260717T185140Z.log` — post-fix session: Finding A's live confirmation (`UT5MD`/
  `R2AL` full QSOs, lines ~190-580), Finding B's six new rejections (lines 823, 929, 967, 1206,
  1480, 1963), Finding C's crash (lines 1506-1513).
- `src/OpenWSFZ.Daemon/EngagementTargetValidator.cs` — Finding A's fix.
- `src/OpenWSFZ.Web/WebApp.cs:1369-1447` — manual `engage-decode` dispatch; Finding B's missing
  log line goes here.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:711-813` (`IsCallsignShapeInvalid`/`TryParseCallsignShape`) —
  the existing, pre-existing grammar-anchoring logic Finding B's hypothesis proposes reusing.
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:294-313` (`AnswerCqAsync`'s try/catch) — the pattern
  Finding C's fix should mirror; `:849` — the unguarded call site.
- `src/OpenWSFZ.Config/JsonConfigStore.cs:56-105` (`SaveAsync`) — Finding C's throw site.
- `openspec/changes/engagement-target-validation/{design.md,tasks.md,specs/engagement-target-validation/spec.md}` —
  Finding A's spec/design corrections (task 3.5).
