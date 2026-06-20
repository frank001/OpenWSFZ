# D-009 Handoff — OSD False Positive Filter (UI & ALL.TXT)

**Date:** 2026-06-20  
**Raised by:** QA (live observation during S8 R&R gate run, shim 20260025)  
**Defect ID:** D-009  
**Severity:** High — gate-blocking (S5 FP rate 91.67% vs 6.0% threshold at full S1–S8 gate
run `6e821fa`, 2026-06-20); user-visible in ALL.TXT / UI; does not corrupt ADIF log or
trigger erroneous TX, but gate cannot pass until resolved  

---

## 1. Context

The OSD fallback introduced at shim 20260025 (`fix/d001-osd-fallback`, merged `1809ce7`)
substantially improved D-001 decode rate (S7: 51.61% → 80.22%). As a known tradeoff, OSD
evaluates up to 529 trial codewords per candidate; in a busy band (S8 scene, 12 simultaneous
signals) pass 2 consistently hits the 200-candidate cap. A non-trivial fraction of those
candidates produce a valid LDPC CRC-14 by chance and decode to garbage messages that reach
ALL.TXT and the UI.

**S5 gate measurement (full run `6e821fa`, 2026-06-20):** S5 FP rate = 91.67% (11 FP decode
events across 4 of 12 noise-only slots; threshold ≤ 6.0%).  Gate-blocking FAIL.  Affected
slots: P0 trials 0–2 (11:16:15–11:16:45Z), P1 trial 1 (11:17:15Z).  All spurious decodes
are at reported SNR −23 to −28 dB from pure AWGN.

Observed examples (S5 noise-only run and live S8 run, 2026-06-20):

| Message | Category |
|---|---|
| `CQ ETRHB0I3RYO` | CQ with garbage callsign (11 chars) |
| `CQ GKC5JNL82FW` | CQ with garbage callsign (11 chars) |
| `UDWA9WGLHX <...> RR73` | Garbage sender callsign (10 chars, 5-char suffix) |
| `<...> 1RY8RU98FJ9 RRR` | Garbage callsign in hash-position (11 chars) |
| `DDK4NYWXBIU RRR` | Free-text / garbage callsign (11 chars) |
| `586A8555F2A13462F6` | Hex dump — unrecognised message type |
| `1DA5713612BD5A3C22` | Hex dump — unrecognised message type |
| `` (blank) | Empty message — LDPC converged, no valid message type |

FP rate: approximately 2–3 per 12-signal S8 cycle. FPs do **not** affect the TP gate
metric (analyse.py matches against truth.csv only). However, they are visible to the
user in ALL.TXT and the WebSocket UI message list, which erodes trust in V1.

WSJT-X exhibits the same phenomenon (OSD-induced FPs are documented in the WSJT-X
reflector archives); however, OpenWSFZ's user base may not share the expert context that
treats FPs as an expected protocol artefact.

---

## 2. Branch Name

```
fix/d009-fp-callsign-filter
```

Base off `main` at HEAD (`6e821fa`).

---

## 3. Actions

### 3.1 Filter insertion point

`src/OpenWSFZ.Ft8/Ft8Decoder.cs` — extend `IsPlausibleMessage(string? text)`.

The method is already the designated plausibility gate (line ~344). It is called for every
decoded message before it is added to the result list and before ANY downstream path
(WebSocket broadcast, ALL.TXT, QsoAnswererService). Adding the new rules here applies the
filter to all consumers in one place.

Do **not** add filtering in `AllTxtWriter.cs` or the WebSocket layer — the decoder is the
correct authority on what constitutes a valid decode.

### 3.2 New filter rules — implement as early-return cases in `IsPlausibleMessage`

Add the following cases **before** the existing `spaces != 2` early-out, in the order
listed. Each case returns `false` (reject).

#### Rule D9-R1 — Blank / whitespace message

```csharp
if (string.IsNullOrWhiteSpace(text)) return false;
```

Catches: empty string, strings of spaces (LDPC converged but message type produced no
printable text). Note: `text is null` already returns `false` at the existing first line;
this rule extends it to whitespace-only strings.

#### Rule D9-R2 — Hex dump (unrecognised message type)

```csharp
// Single-token string ≥ 16 chars whose every character is an uppercase hex digit.
// ft8_lib renders unrecognised message types as a raw hex string (no spaces).
if (text.Length >= 16 && !text.Contains(' ') && IsAllUpperHex(text)) return false;
```

Helper:
```csharp
private static bool IsAllUpperHex(string s)
{
    foreach (char c in s)
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F')))
            return false;
    return true;
}
```

Catches: `586A8555F2A13462F6`, `1DA5713612BD5A3C22`, and any future hex-dump output.
Threshold of 16 chars gives generous headroom above the longest valid unspaced callsign
token (10 chars including `/` portable suffix).

#### Rule D9-R3 — Oversized callsign token

In a well-formed FT8 Type 1 message the base callsign packs into 28 bits. ft8_lib's
`pack_basecall` encodes at most 6 base characters; with a portable n12 extension
(`/P`, `/M`, `/R`, `/MM`, `/QRP`) the rendered string reaches at most 10 characters
(e.g., `VK9ABC/QRP`). Any callsign-position token whose base length (before `/`) exceeds
6 characters, OR whose total length (including `/suffix`) exceeds 10, has not been
produced by valid Type 1 callsign packing and should be rejected.

```csharp
// Apply to every space-separated token that is in a callsign position:
// i.e., not a known terminal (73, RR73, RRR), not a dB report ([R][+-]NN),
// not a Maidenhead grid (4 chars), not a hash placeholder (<...>).
// CQ/DE/QRZ pseudo-callsigns are exempt (length ≤ 3).
```

Apply to messages with 2 tokens (CQ pattern) and 3 tokens (Standard QSO pattern):

**2-token messages** (`"CQ CALLSIGN"` / `"DE CALLSIGN"` / `"QRZ CALLSIGN"`):
- Token 0 must be `CQ`, `DE`, or `QRZ` — already implies this is a CQ-type message.
- Token 1 is the callsign. Apply: `IsCallsignOversized(token1)`.

**3-token messages** (Standard QSO):
- Token 0 is sender callsign. Apply `IsCallsignOversized(token0)` unless it is `<...>`.
- Token 1 is addressed callsign. Apply `IsCallsignOversized(token1)` unless it is `<...>`.

`IsCallsignOversized`:
```csharp
private static bool IsCallsignOversized(string token)
{
    if (token.StartsWith('<')) return false;   // hash reference — never oversized
    if (token.Length <= 3)    return false;    // CQ/DE/QRZ/short calls — exempt

    // Split on '/' to isolate base callsign from portable suffix.
    int slashPos = token.IndexOf('/');
    string baseCall = slashPos >= 0 ? token[..slashPos] : token;

    // Base callsign from standard Type 1 packing: max 6 chars.
    // Rendered token with /suffix: max 10 chars (6-char base + '/' + up to 3-char suffix).
    return baseCall.Length > 6 || token.Length > 10;
}
```

Catches:
- `ETRHB0I3RYO` (11 chars, base 11) → oversized ✓
- `GKC5JNL82FW` (11 chars, base 11) → oversized ✓
- `1RY8RU98FJ9` (11 chars, base 11) → oversized ✓
- `DDK4NYWXBIU` (11 chars, base 11) → oversized ✓
- `ELUX7QIYUCF` (11 chars, base 11) → oversized ✓
- `UDWA9WGLHX` (10 chars, base 10 > 6) → oversized ✓

Does NOT reject (correctly):
- `Q1ABC` (5 chars) — valid Q-prefix test call ✓
- `VK9ABC` (6 chars) — valid 6-char DX call ✓
- `VK9ABC/P` (8 chars, base 6) — valid portable ✓
- `VK9/K1JT` — note: `VK9` base is 3 chars, `/K1JT` is suffix — base ≤ 6, total ≤ 10 ✓
- `3DA0MN` (6 chars) — valid Swaziland prefix ✓
- `<...>` — hash reference, exempt ✓

### 3.3 Ordering within `IsPlausibleMessage`

Insert Rules D9-R1, D9-R2, D9-R3 at the **top** of the method body, before the existing
`spaces` counting loop. This ensures they run on every message regardless of token count.

The existing logic (3-token Maidenhead validation, dB-report validation) is unchanged and
continues to run after these early guards.

### 3.4 Log the filtered messages

Extend the existing `LogDebug` in `Ft8Decoder.DecodeAsync` that logs filtered messages:

```csharp
// Already present — just ensure new cases reach this line.
_logger?.LogDebug(
    "Cycle {Time}: filtered implausible message '{Message}' (false-positive guard).",
    timeStr, msg);
```

No new log statement is needed; the existing one fires for any `IsPlausibleMessage`
returning `false`.

---

## 4. Tests

Add `tests/OpenWSFZ.Ft8.Tests/D009FpFilterTests.cs`. Pattern follows `D005MessageTrimTests.cs`
— use the `IFt8NativeInterop` injection seam; no native DLL is loaded.

All callsigns in the "accept" cases that are not garbage must use Q-prefix synthetics
(NFR-021). Garbage callsigns under test are not real assignments and may be used as-is.

### 4.1 `IsPlausibleMessage` unit tests — direct static call

```
// Rule D9-R1: Blank/whitespace — must reject
[null, "", "   ", "\t"]

// Rule D9-R2: Hex dump — must reject
["586A8555F2A13462F6", "1DA5713612BD5A3C22", "0000000000000000"]

// Rule D9-R3: Oversized callsign in CQ message — must reject
["CQ ETRHB0I3RYO", "CQ GKC5JNL82FW", "CQ ELUX7QIYUCF"]

// Rule D9-R3: Oversized callsign in Standard QSO — must reject
["UDWA9WGLHX <...> RR73", "DDK4NYWXBIU Q9XYZ RR73", "1RY8RU98FJ9 Q1ABC R-05"]

// Rule D9-R3: Oversized in addressee position — must reject
["Q1ABC ETRHB0I3RYO R-10", "Q9XYZ 1RY8RU98FJ9 73"]

// Must NOT reject (valid messages)
["CQ Q1ABC FN42", "Q1ABC Q9XYZ -10", "Q9XYZ Q1AW RR73",
 "Q1AW Q1ABC +05", "CQ Q9XYZ EN37",
 "<...> Q9XYZ RR73",          // hash sender
 "Q1ABC <...> R-08",          // hash addressee
 "CQ VK9AA OC12",             // 5-char DX call
 "CQ 3DA0MN KH51",            // digit-prefix DX call (6 chars)
 "VK9AA Q1ABC -15",           // 5-char DX in sender position
 "Q1ABC VK9AA/P RR73"]        // 8-char portable in addressee position
```

### 4.2 Integration test via fake interop

Add one `[Fact]` that drives `Ft8Decoder.DecodeAsync` with a fake interop returning a mix
of valid and garbage messages, and asserts that the `IReadOnlyList<DecodeResult>` returned
contains only the valid ones. Pattern: see `D005MessageTrimTests.FakeNativeInterop`.

---

## 5. Acceptance Criteria

- **AC1** — `dotnet test` passes with 0 failures (all 471 + new D-009 tests green).
- **AC2** — `IsPlausibleMessage` returns `false` for every message in the "must reject" list in §4.1.
- **AC3** — `IsPlausibleMessage` returns `true` for every message in the "must NOT reject" list in §4.1.
- **AC4** — No change to `Ft8NativeResult`, `DecodeResult`, `AllTxtWriter`, or any WebSocket/UI layer — the filter lives solely in `Ft8Decoder.IsPlausibleMessage`.
- **AC5** — The `IsCallsignOversized` and `IsAllUpperHex` helpers are `private static` methods on `Ft8Decoder` (consistent with existing `IsDbReport`).
- **AC6** — `dotnet build OpenWSFZ.slnx -c Release` produces 0 errors, 0 warnings.

---

## 6. References

- Defect: D-009 (raised 2026-06-20, live S8 R&R run at shim 20260025)
- Causally related fix: `fix/d001-osd-fallback` (merged `1809ce7`, shim 20260025)
- OSD design decision: MEMORY.md §D-001 status, shim 20260025 comment in `Ft8LibInterop.cs`
- Existing plausibility filter: `Ft8Decoder.IsPlausibleMessage` (line ~344)
- Existing test pattern: `D005MessageTrimTests.cs`
- QA analysis artefact: `logs/openswfz-20260620T103508Z.log`, `ALL.TXT` (2026-06-20 S8 run)
- Captain's decision (2026-06-20): Tier 1 callsign-length filter for V1; CRC confidence
  threshold retained as Tier 2 option if tier 1 proves insufficient.
