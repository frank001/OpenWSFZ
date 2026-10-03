# #192: `QsoCallerService.TryParseResponder` accepts `RR73`/`RRR` as a Maidenhead grid

**Date:** 2026-09-28
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (sign-off required before merge, HK-010)
**Status:** Proposed. Per HK-011, needs the Captain's explicit sign-off before pickup.
**Branch:** new branch off `main`, name at the Developer's/Captain's discretion.
**GitHub:** #192 (filed 2026-09-27, latent — 0 occurrences in production; see §1.3).

---

## 0. Executive summary

`TryParseResponder`'s third-token classifier (`src/OpenWSFZ.Daemon/QsoCallerService.cs:1432-1434`)
treats any token whose first two characters are letters as a Maidenhead grid square. `RR73` and
`RRR` both satisfy that test — `RR` are letters, and `RR73`'s trailing `73` happens to also satisfy
the digit half of a genuine 4-character grid's shape, so this isn't just a loose regex, the token is
format-ambiguous. A late `OURS PARTNER RR73` (or `RRR`) arriving while `PARTNER` is unengaged would
be accepted as a valid CQ response and its `grid` output set to the literal string `"RR73"`, which
would then be written to `GRIDSQUARE=RR73` in the ADIF log if that QSO proceeded.
`WebApp.cs:1791` already excludes these exact tokens by exact-string match before any grid handling
at its own call site — `TryParseResponder` has no equivalent exclusion. This task adds it.

## 1. Precise scope

### 1.1 The defect, exactly

`src/OpenWSFZ.Daemon/QsoCallerService.cs`, `TryParseResponder` (`:1404-1447`):

```
1431:        var thirdToken = parts[2];
1432:        var isGrid   = thirdToken.Length >= 2
1433:                       && char.IsLetter(thirdToken[0])
1434:                       && char.IsLetter(thirdToken[1]);
1435:        var isReport = IsSignalReport(thirdToken);
1436:        if (!isGrid && !isReport)
1437:            return false;
```

`isGrid` has no exclusion for the reserved FT8 sign-off tokens `RR73`/`RRR`. Contrast
`src/OpenWSFZ.Web/WebApp.cs:1791-1797`, which checks these tokens by exact string match (case
insensitive) *before* any grid/report classification at its own call site:

```
1791:                    if (info.Equals("RR73", StringComparison.OrdinalIgnoreCase))
...
1797:                    else if (info.Equals("RRR", StringComparison.OrdinalIgnoreCase) || IsRReport(info))
```

`TryParseResponder` has no such exclusion, so its `isGrid` test alone determines the outcome for
these tokens, and it says yes.

### 1.2 The fix

Add the same two exact-match exclusions to `isGrid`'s condition, mirroring `WebApp.cs`'s own
convention rather than inventing a new one:

```csharp
var isGrid   = thirdToken.Length >= 2
               && char.IsLetter(thirdToken[0])
               && char.IsLetter(thirdToken[1])
               && !thirdToken.Equals("RR73", StringComparison.OrdinalIgnoreCase)
               && !thirdToken.Equals("RRR", StringComparison.OrdinalIgnoreCase);
```

With this change, `RR73`/`RRR` as a third token: `isGrid` → false, `isReport` → false (neither
starts with `+`/`-`/`R+`/`R-`), so `TryParseResponder` returns `false` — the same outcome the
existing test already asserts for a bare `"73"` third token
(`QsoCallerServiceTests.cs:1494-1504`, `TryParseResponder_Rejects73AsThirdToken`). This is a
**rejection** fix, not a re-routing fix: it stops `RR73`/`RRR` from being misread as a grid; it does
not make `TryParseResponder` itself handle them as a sign-off (that is `WebApp.cs`'s job at its own
call site, unaffected by this change).

### 1.3 What this is NOT, and why — read this before touching anything else nearby

`TryParseResponder`'s own docstring (`:1395-1403`) records a **Captain decision, 2026-08-27**: this
call site ("site 6", the unengaged `WaitAnswer` state, no partner bound yet) is *deliberately*
restricted from the L1 (2-token acceptance) / L2 (bracket-strip normalisation) extensions applied at
partner-bound sites 1–5, because G3 measured a 71.02% CP-lower-bound false-fire rate for an
own-hash-equivalent match with no partner bound at this exact site. The docstring explicitly warns:
*"do not 'fix' it as a missed call site without a new recorded decision."*

**This task does not touch that.** The `RR73`/`RRR`-as-grid defect is orthogonal to L1/L2 — it is a
false *positive* classification of a specific reserved token, not a missing acceptance path — and
the fix above does not extend, narrow, or otherwise interact with the L1/L2 restriction. Do not fold
the two together in the same PR or use this task as licence to revisit 2026-08-27's decision.

Also out of scope: `WebApp.cs`'s own RR73/RRR/report handling (`:1791-1802`) is already correct and
is not touched by this task, other than being cited as the pattern to mirror.

## 2. Tests

Add two new `[Fact]`s to `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`, directly after
`TryParseResponder_Rejects73AsThirdToken` (`:1494-1504`), matching its exact shape:

```csharp
[Fact(DisplayName = "TryParseResponder: rejects RR73 as third token (not a Maidenhead grid)")]
public void TryParseResponder_RejectsRr73AsThirdToken()
{
    // "RR73" is a QSO sign-off message, not a grid square, even though its first two
    // characters are letters — #192.
    var result = QsoCallerService.TryParseResponder(
        "PD2FZ/P Q1ABC RR73", "PD2FZ/P",
        out var partner, out _, out var grid);

    result.Should().BeFalse();
    partner.Should().BeEmpty();
    grid.Should().BeNull();
}

[Fact(DisplayName = "TryParseResponder: rejects RRR as third token (not a Maidenhead grid)")]
public void TryParseResponder_RejectsRrrAsThirdToken()
{
    var result = QsoCallerService.TryParseResponder(
        "PD2FZ/P Q1ABC RRR", "PD2FZ/P",
        out var partner, out _, out var grid);

    result.Should().BeFalse();
    partner.Should().BeEmpty();
    grid.Should().BeNull();
}
```

Run the existing `QsoCallerServiceTests` in full and confirm no regression — in particular, the
genuine-grid acceptance tests (e.g. the `Q1TST JO22` case referenced at `:1648`) must still pass,
since `JO22` is unaffected by the new exclusion (it isn't `RR73` or `RRR`).

## 3. Rigour controls

1. **Exact-match exclusion only** — do not generalise to a regex or a "looks like a sign-off" heuristic;
   match `WebApp.cs`'s own convention (`.Equals(..., OrdinalIgnoreCase)`) exactly, for the same reason
   that file uses it: these are two specific reserved protocol tokens, not a class of strings.
2. **Do not change `IsSignalReport`** — it is correct and unaffected.
3. **Do not touch the L1/L2 site-6 restriction** — see §1.3.
4. **Zero production occurrences to date** (0 QSOs logged with `GRIDSQUARE=RR73`/`RRR` across
   OpenWSFZ's `ADIF.log` (873 QSOs + 2 test logs) and WSJT-X's own logs (820 + 641), checked
   2026-09-27) — this is a latent-defect fix, not a live-data cleanup. No existing ADIF records need
   correction.

## 4. Deliverables

1. The four-line exclusion added to `isGrid` in `TryParseResponder` (`:1432-1434` → 6 lines).
2. Two new regression tests per §2, passing.
3. Full `QsoCallerServiceTests` run green, no regressions on the existing grid/report acceptance tests.
4. A short PR description confirming `git diff --stat main -- src/` shows only
   `QsoCallerService.cs`'s 2-line classifier change, and `tests/` shows only the two new Facts.

QA verifies against this task before recommending merge (HK-002/HK-006); the Captain signs off the
merge itself (HK-010).

## 5. References

| Reference | Content |
|---|---|
| `src/OpenWSFZ.Daemon/QsoCallerService.cs:1395-1447` | `TryParseResponder`, full method + docstring (site-6 L1/L2 restriction, 2026-08-27) |
| `src/OpenWSFZ.Web/WebApp.cs:1791-1802` | The correct exact-match exclusion pattern to mirror |
| `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1494-1504` | `TryParseResponder_Rejects73AsThirdToken` — the pattern the two new tests follow |
| `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs:1648` | Existing genuine-grid (`JO22`) acceptance case — must still pass |
| `BOARD.md` §"Waiting on the Captain" / GitHub #192 | Original finding, 2026-09-27; 0 production occurrences confirmed |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
