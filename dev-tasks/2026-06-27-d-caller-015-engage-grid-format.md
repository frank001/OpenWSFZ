# D-CALLER-015 — engage-decode aborts active session on GRID-format message (422)

**Date:** 2026-06-27
**Raised by:** QA engineer (analysis of `logs/openswfz-20260627T162622Z.log`)
**Severity:** High — active QSO session is destroyed with no recovery; operator is left in Idle with
a 422 and no feedback beyond the browser console.

---

## 1. Context

`POST /api/v1/tx/engage-decode` (`WebApp.cs`) dispatches the double-clicked decode row to one of
four handlers (AnswerCqAsync, EngageAtAsync variants, or abort-only). The dispatch is done in
**two steps**: Step 1 unconditionally aborts any active session; Step 2 parses the message and
dispatches.

Case B of Step 2 handles messages addressed to our callsign (`OURCALL PARTNER INFO`). It
recognises `INFO` tokens: `+NN`/`-NN` (plain SNR), `R+NN`/`R-NN`/`RRR` (R-report),
`RR73`, `73`. It does NOT recognise **grid squares** (e.g. `JO33`).

The FT8 first-exchange CQ-response format is:
```
OURCALL THEIRCALL THEIRGRID   ← they answer our CQ with their grid square
```
This is a valid mid-session row that the operator may wish to double-click. When they do:
- Step 1 aborts the active session (e.g. `WaitRr73` — **destroying a live QSO**)
- Step 2 reaches the `else` branch → `Results.UnprocessableEntity()` (422)

The session is gone. The operator gets nothing useful.

**Observed instance (2026-06-27T18:29:30):**
- State: `WaitRr73`, partner: `PD3QA`
- Operator double-clicked row `PD2FZ/P PD2FZ JO33`
- Result: `WaitRr73` aborted, 422 returned, session lost

The `QsoCallerService` already handles this message format correctly in auto-mode
(`TryParseResponder` at 18:30:45 in the same log). The gap is in the manual engage-decode path.

---

## 2. Branch name

`fix/d-caller-015-engage-grid-format`

---

## 3. Actions

### 3.1 — Add an `IsGridSquare` helper in `WebApp.cs`

Alongside the existing `IsPlainSnr` and `IsRReport` local functions (inside the Case B `else if`
block in the `engage-decode` endpoint, around line 920), add:

```csharp
static bool IsGridSquare(string s) =>
    (s.Length == 4 || s.Length == 6)
    && char.IsLetter(s[0]) && char.IsLetter(s[1])
    && char.IsDigit(s[2])  && char.IsDigit(s[3])
    && (s.Length == 4 || (char.IsLetter(s[4]) && char.IsLetter(s[5])));
```

This matches the 4-character Maidenhead subsquare (`JO33`) and the 6-character extended square
(`JO33aa`). Both are valid FT8 grid tokens.

### 3.2 — Add a grid-square branch in Case B

In the dispatch chain inside Case B (immediately after the `else if (IsPlainSnr(info))` block,
before the `else { return Results.UnprocessableEntity(); }` fallthrough), insert:

```csharp
else if (IsGridSquare(info))
{
    // OURCALL PARTNER GRID: partner is answering our CQ with their grid.
    // Semantically equivalent to a plain-SNR first exchange — respond with our report.
    await qsoController.EngageAtAsync(
        partner, req.FrequencyHz, cycleStart, EngagePoint.SendReport, ct)
        .ConfigureAwait(false);
}
```

### 3.3 — Add unit tests in `tests/OpenWSFZ.Web.Tests/`

Add tests to the existing `EngageDecodeEndpointTests` class (or equivalent) covering:

**Test A — Grid-square row fires EngageAtAsync(SendReport).**
Send `POST /api/v1/tx/engage-decode` with body `{"message":"Q1ABC Q9XYZ JO33","frequencyHz":500,
"cycleStartUtc":"..."}` and `ourCallsign = "Q1ABC"`. Assert HTTP 200 and that
`IQsoController.EngageAtAsync` was called with `EngagePoint.SendReport`.

**Test B — 6-character extended grid square is also accepted.**
Same as Test A but `info = "JO33aa"`. Assert 200 and `EngageAtAsync(SendReport)`.

**Test C — Non-grid 4-char token still returns 422.**
Body `{"message":"Q1ABC Q9XYZ AB12","frequencyHz":500,...}` where `"AB12"` starts with letters
(grid pattern) — this DOES match `IsGridSquare`, so it should return 200. Pick a genuinely
unrecognised 4-char token such as `"BLAH"` (letters only, not a valid grid) for the 422 case.
Assert HTTP 422 and that `EngageAtAsync` was NOT called.

**Test D — Regression: plain-SNR still works alongside grid branch.**
`info = "+07"` → 200 + `EngageAtAsync(SendReport)`. Ensures the new branch did not disturb the
existing dispatch order.

---

## 4. Acceptance criteria

**AC-1.** `POST /api/v1/tx/engage-decode` with a `OURCALL PARTNER GRID` body (4- or 6-character
Maidenhead grid) returns HTTP 200 and triggers `EngageAtAsync(SendReport)`.

**AC-2.** When an active session is in progress and the body is a grid-format row, the abort
(Step 1) still runs — but the subsequent `EngageAtAsync(SendReport)` call then re-engages
correctly. The net result is `TxReport` (not `Idle` with a 422).

**AC-3.** Existing dispatch cases (plain SNR, R-report, RRR, RR73, 73) are unaffected.

**AC-4.** Genuinely unrecognised `INFO` tokens (e.g. free-text bleed-through) still return 422.

**AC-5.** Build: `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

**AC-6.** Full test suite: 0 failures (≥720 passed; new tests add to the count).

---

## 5. References

- `logs/openswfz-20260627T162622Z.log` — session in which the defect was triggered (18:29:30
  engage-decode: abort WaitRr73 + 422 on `PD2FZ/P PD2FZ JO33`)
- `src/OpenWSFZ.Web/WebApp.cs` — `POST /api/v1/tx/engage-decode` endpoint (~lines 834–980);
  Case B dispatch chain (~lines 912–957)
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — `TryParseResponder` method handles the same
  `OURCALL PARTNER GRID` format correctly in auto-mode (reference for the semantics)
- D-CALLER-012 review (2026-06-27) — introduced the engage-decode endpoint; the grid case was
  an undetected gap at review time
- D-CALLER-013 review (2026-06-27) — QA review confirmed D-CALLER-013 is not involved;
  this defect pre-dates it
- D-CALLER-014 (annex, D-CALLER-013 task doc) — separate loopback phase-collision observation;
  no code change required; not related
