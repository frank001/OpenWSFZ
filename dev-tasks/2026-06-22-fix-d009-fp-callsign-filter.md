# Developer Handoff — D-009-R2: Residual FP Callsign Filter Gaps

**Date:** 2026-06-22  
**Prepared by:** QA Engineer  
**Defect ID:** D-009-R2 (residual gap in `IsPlausibleMessage` after the D-009 initial fix)  

---

## 1. Context

During live QSO testing on `feat/gui-tx-panel` (clean loopback — WSJT-X directly
connected to OpenWSFZ via VB-Audio, no transceiver, no RF), three false-positive
messages were observed in OpenWSFZ's `ALL.TXT` output. These messages passed
`IsPlausibleMessage` (D9-R1 through D9-R4) and appeared in both the UI decode
table and `ALL.TXT`:

| Message | Why it passed | Issue |
|---|---|---|
| `TJ9AUD/R 625YFE/R BN34` | `625YFE` base=6 chars ≤ 6 → not oversized | Digit-first callsign uncaught |
| `CQ EJLD ZE8SBP/P QK71` | token0=`CQ` → 4-token rule admits; grid not validated | All-letter callsign uncaught; grid `QK71` (Q > R) not checked |
| `20IOD F83TQH/R AF03` | `20IOD` base=5 chars ≤ 6 → not oversized | Two-digit-prefix callsign uncaught |

**Secondary hazard from `CQ EJLD ZE8SBP/P QK71`:** If this FP appeared first in
the decode batch, `HandleIdleAsync` would have set `partner = "EJLD"` and
transmitted `EJLD PD2FZ/P JO33` — a message directed at a phantom callsign.
In the recorded session this was averted by decode ordering; it cannot be relied upon.

**Unfiltered FP rate:** approximately 0.5 per decode cycle in this clean single-signal
environment — above the 0.042/slot measured under the S5 AWGN-only scenario. The
discrepancy arises because the strong direct-digital signal (SNR ~75 dB) produces
significant pass-2 subtraction residuals that the existing filter was not calibrated against.

The two new rules required are:

- **D9-R5** — Callsign structural validation: a callsign base (before `/suffix`) must
  contain at least one digit AND must not begin with two or more consecutive digits.  
  Catches: `EJLD` (no digit), `625YFE` (three leading digits), `20IOD` (two leading digits).

- **D9-R6** — 4-token CQ grid validation: the fourth token of a `CQ … … GRID` message
  must be a valid Maidenhead locator (letters A–R, then two digits).  
  Catches: `CQ EJLD ZE8SBP/P QK71` (`Q` > `R`).

This is a **separate change** from the TX panel disarm fix (`2026-06-22-fix-tx-panel-disarm.md`).

---

## 2. Branch

**`fix/d009-fp-callsign-filter-r2`** — branch from `main`.

---

## 3. Actions

All changes are in `src/OpenWSFZ.Ft8/Ft8Decoder.cs`.

### 3.1 — Add `IsCallsignStructurallyInvalid` helper

Add after the existing `IsCallsignOversized` method (around line 520):

```csharp
/// <summary>
/// Returns <c>true</c> when <paramref name="token"/> is a callsign-position token
/// whose base callsign has an impossible structure for any ITU-licensed amateur station
/// (D9-R5 guard — structural complement to the D9-R3 length guard).
/// </summary>
/// <remarks>
/// <para>
/// Exempt cases (always returns <c>false</c>):
/// <list type="bullet">
///   <item>Hash-reference tokens beginning with <c>&lt;</c> (e.g. <c>&lt;...&gt;</c>).</item>
///   <item>Short pseudo-callsigns with ≤ 3 characters (CQ, DE, QRZ).</item>
/// </list>
/// </para>
/// <para>
/// A valid Type 1 base callsign must contain exactly one digit, with an optional
/// single-digit or single-letter prefix (e.g. <c>4X</c>, <c>9A</c>, <c>G</c>, <c>VK</c>).
/// Two structural invariants hold for all valid callsigns:
/// <list type="bullet">
///   <item>At least one digit must be present (rules out <c>EJLD</c>, <c>AAAA</c>).</item>
///   <item>The base may not begin with two or more consecutive digits (rules out
///         <c>625YFE</c>, <c>20IOD</c>; single-digit prefixes such as <c>4X</c>,
///         <c>9A</c> remain valid).</item>
/// </list>
/// </para>
/// </remarks>
private static bool IsCallsignStructurallyInvalid(string token)
{
    if (token.StartsWith('<')) return false;   // hash reference — never structurally invalid
    if (token.Length <= 3)    return false;    // CQ / DE / QRZ / very short call — exempt

    // Strip portable suffix so we inspect only the base callsign.
    int    slashPos = token.IndexOf('/');
    string baseCall = slashPos >= 0 ? token[..slashPos] : token;

    // Invariant (a): base must contain at least one digit.
    bool hasDigit = false;
    foreach (char c in baseCall)
    {
        if (char.IsAsciiDigit(c)) { hasDigit = true; break; }
    }
    if (!hasDigit) return true;   // no digit → structurally invalid

    // Invariant (b): base must not start with two or more consecutive digits.
    // Single-digit prefixes (4X, 9A, 2E, etc.) are valid.
    if (baseCall.Length >= 2 &&
        char.IsAsciiDigit(baseCall[0]) &&
        char.IsAsciiDigit(baseCall[1]))
        return true;   // two leading digits → structurally invalid

    return false;
}
```

---

### 3.2 — Wire D9-R5 into `IsPlausibleMessage` for 2-token and 3-token messages

In the existing 2-token branch, add `IsCallsignStructurallyInvalid` alongside the
existing `IsCallsignOversized` checks:

```csharp
// 2-token message: "TOKEN0 TOKEN1"
string token0 = text[..firstSpace];
string token1 = text[(firstSpace + 1)..];
if (IsCallsignOversized(token0)          || IsCallsignOversized(token1) ||
    IsCallsignStructurallyInvalid(token0) || IsCallsignStructurallyInvalid(token1))
    return false;
```

In the existing 3-token branch:

```csharp
// Exactly 3-token message: "TOKEN0 TOKEN1 TOKEN2"
string token0 = text[..firstSpace];
string token1 = text[(firstSpace + 1)..secondSpace];
if (IsCallsignOversized(token0)          || IsCallsignOversized(token1) ||
    IsCallsignStructurallyInvalid(token0) || IsCallsignStructurallyInvalid(token1))
    return false;
```

The 3-token TOKEN2 (grid or report) is already handled by D9-R4; no change needed there.

---

### 3.3 — Wire D9-R6 into `IsPlausibleMessage` for 4-token CQ messages

In the existing 4-token branch (currently only checks `token0.Equals("CQ")`), add
Maidenhead validation of the fourth token:

```csharp
// Exactly 4-token message: "TOKEN0 TOKEN1 TOKEN2 TOKEN3"
// Valid form: "CQ <modifier> <callsign> <grid>" (e.g. "CQ DX Q1ABC FN42").
string token0 = text[..firstSpace];
if (!token0.Equals("CQ", StringComparison.Ordinal))
    return false;

// D9-R6: the fourth token of a CQ message must be a valid Maidenhead locator.
// Reuses the same A-R letter constraint already applied in the 3-token grid path.
string token3 = text[(thirdSpace + 1)..];
if (token3.Length == 4 &&
    char.IsAsciiLetter(token3[0]) && char.IsAsciiLetter(token3[1]) &&
    char.IsAsciiDigit(token3[2])  && char.IsAsciiDigit(token3[3]))
{
    // Letters must be in [A-R] (Maidenhead indices 0–17).
    if (char.ToUpperInvariant(token3[0]) > 'R' || char.ToUpperInvariant(token3[1]) > 'R')
        return false;
}
// If token3 is not 4 chars (e.g. very short or absent), accept — caller may have
// non-standard form. The length+letter+digit pattern is the only validated variant.
```

---

### 3.4 — Update `IsPlausibleMessage` XML doc comment

Append two new `<para>` blocks to the `<remarks>` section of `IsPlausibleMessage`:

```csharp
/// <para>
/// D9-R5 — structural callsign validation: a callsign-position base token must
/// contain at least one digit and must not begin with two or more consecutive
/// digits.  Catches <c>EJLD</c> (no digit), <c>625YFE</c> (three leading digits),
/// and <c>20IOD</c> (two leading digits).  Applied to both tokens of 2-token
/// messages and to tokens 0–1 of 3-token messages.
/// </para>
/// <para>
/// D9-R6 — 4-token CQ grid validation: the fourth token of a <c>CQ … … GRID</c>
/// message must be a valid Maidenhead locator (A–R letters, then two digits).
/// Catches <c>CQ EJLD ZE8SBP/P QK71</c> where <c>Q</c> &gt; <c>R</c>.
/// </para>
```

---

### 3.5 — Tests

Add to `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderPlausibilityTests.cs`
(or `D009FpFilterTests.cs` — whichever contains the `IsPlausibleMessage` unit tests):

```csharp
// D9-R5: callsigns with no digit are rejected
[Theory]
[InlineData("EJLD Q1ABC JO33")]       // token0 has no digit
[InlineData("Q1ABC EJLD JO33")]       // token1 has no digit
[InlineData("CQ EJLD")]               // 2-token, token1 has no digit
public void IsPlausibleMessage_AllLetterCallsign_ReturnsFalse(string msg)
    => Assert.False(Ft8Decoder.IsPlausibleMessage(msg));

// D9-R5: callsigns starting with two or more digits are rejected
[Theory]
[InlineData("TJ9AUD/R 625YFE/R BN34")]  // 625YFE starts with 625
[InlineData("20IOD F83TQH/R AF03")]     // 20IOD starts with 20
[InlineData("CQ 625YFE")]               // 2-token
public void IsPlausibleMessage_MultiDigitPrefixCallsign_ReturnsFalse(string msg)
    => Assert.False(Ft8Decoder.IsPlausibleMessage(msg));

// D9-R5: single-digit-prefix callsigns are accepted (4X, 9A, 2E style)
[Theory]
[InlineData("4X1AB Q1TST JO33")]
[InlineData("9A1ABC Q2TST JO33")]
[InlineData("2E0ABC Q3TST JO33")]
[InlineData("CQ 4X1ABC JO33")]
public void IsPlausibleMessage_SingleDigitPrefixCallsign_ReturnsTrue(string msg)
    => Assert.True(Ft8Decoder.IsPlausibleMessage(msg));

// D9-R6: 4-token CQ with grid letter beyond R is rejected
[Theory]
[InlineData("CQ DX Q1ABC SK71")]    // S > R
[InlineData("CQ EJLD Q1ABC QK71")] // Q > R (the observed FP)
public void IsPlausibleMessage_4TokenCqGridBeyondR_ReturnsFalse(string msg)
    => Assert.False(Ft8Decoder.IsPlausibleMessage(msg));

// D9-R6: 4-token CQ with valid grid is accepted
[Theory]
[InlineData("CQ DX Q1ABC JO33")]
[InlineData("CQ NA Q9XYZ FN42")]
public void IsPlausibleMessage_4TokenCqValidGrid_ReturnsTrue(string msg)
    => Assert.True(Ft8Decoder.IsPlausibleMessage(msg));
```

---

## 4. Acceptance Criteria

- [ ] **AC-1:** `IsPlausibleMessage("TJ9AUD/R 625YFE/R BN34")` → `false`.
- [ ] **AC-2:** `IsPlausibleMessage("CQ EJLD ZE8SBP/P QK71")` → `false`.
- [ ] **AC-3:** `IsPlausibleMessage("20IOD F83TQH/R AF03")` → `false`.
- [ ] **AC-4:** `IsPlausibleMessage("4X1AB Q1TST JO33")` → `true` (single-digit prefix not affected).
- [ ] **AC-5:** `IsPlausibleMessage("CQ DX Q1ABC JO33")` → `true` (valid 4-token CQ not affected).
- [ ] **AC-6:** All existing `Ft8DecoderPlausibilityTests` and `D009FpFilterTests` remain green.
- [ ] **AC-7:** S5 FP rate in the next R&R gate run does not increase above 0.042/slot (±CI).
  The D9-R5/R6 rules add rejection — FP rate should stay equal or improve.
- [ ] **AC-8:** `dotnet test OpenWSFZ.slnx -c Release` — all tests pass, zero failures.
- [ ] **AC-9:** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings.

---

## 5. References

- Prior D-009 fix: `dev-tasks/2026-06-20-d009-fp-callsign-filter.md`; merged at `ef16040` (shim 20260029)
- Live session evidence: `logs/openswfz-20260622T163949Z.log` (git-ignored);
  `ALL.TXT` (git-ignored) — FP messages appeared at cycles 164045, 164345, 164645
- `IsPlausibleMessage` source: `src/OpenWSFZ.Ft8/Ft8Decoder.cs` lines 361–481
- S5 baseline FP rate (reference): 0.042/slot at K_MIN_SCORE_PASS2=10 (shim 20260029);
  see `qa/rr-study/results/d009-investigation-2026-06-21/report.md`
- NFR-021: callsign pattern `625YFE`, `EJLD`, `20IOD` are OSD CRC-14 coincidences,
  not real callsigns; committing them is prohibited — hence the filter must catch them
