# D-009 OSD False-Positive Filter — Architectural Review

**Date:** 2026-06-20  
**Raised by:** QA  
**Defect:** D-009 — OSD false-positive callsign filter  
**Status:** Blocked on architectural decision; cannot proceed to R5 developer handoff without architect sign-off on approach

---

## 1. Background

OSD (Ordered Statistics Decoding) was added in shim 20260025 (commit `d70aad5`) to extend
the decoder's sensitivity floor from approximately −21 dB to −27 dB. OSD finds codewords by
exhaustive near-neighbour search over the LDPC parity matrix rather than belief propagation,
and checks each candidate with a CRC-14 pass. The rate of CRC-14 false alarms is approximately
1 in 16 384 per candidate, which is non-trivial over a full decode sweep of ~140 candidates.

D-009 was opened when S5 (noise-only scenario) revealed that the unthresholded OSD path
produced false decodes at rates up to 75% of slots (threshold 0.10, shim 20260026). The
strategy has been to gate OSD output using two mechanisms:

1. **Correlation score gate** (`OSD_CORR_THRESHOLD` in `decode.c`) — normalised inner product
   of the candidate codeword against the received LLR vector, range [−1, +1]. Candidates below
   the threshold are discarded before leaving the native layer.

2. **Text-layer plausibility filter** (`Ft8Decoder.IsPlausibleMessage` in C#) — structural
   checks on the decoded message string, applied to all results from the native library.

---

## 2. Calibration history and current state

The correlation gate has been stepped from 0.10 to 0.40 in 0.05 increments. The S5
(noise-only, 12 slots) false-positive count at each step:

| Threshold | S5 FP events / 12 slots | Notes |
|---|---|---|
| 0.10 | 9 (75.0%) | Initial; S7 P0 ~85% |
| 0.15 | >0 | R3; exact count not recorded (run aborted) |
| 0.20 | 3 (25.0%) | Calibration step |
| 0.25 | 2 (16.7%) | Calibration step |
| 0.30 | 1 (8.3%) | Calibration step |
| 0.35 | ~1 / 12 slots | Calibration step; extended test (22 runs) yielded 3 FP events |
| **0.40** | **0** | S5 FP eliminated; **S7 P0 regressed to ~57% (from 85% baseline)** |

The current branch (`fix/d009-fp-callsign-filter`, shim 20260028) is set to 0.35 for
investigation. The committed DLL is at 0.10 (for FP data collection; must be rebuilt before
any merge).

The calibration has found no threshold value that simultaneously achieves:
- **AC5:** 0 FP events on S5 (requires ≥ 0.40)
- **AC6:** S7 co-channel decode quality not materially regressed (requires ≤ 0.35 — P0 at 57%
  at threshold 0.40 vs 85% at baseline)

This is the calibration ceiling. The text-layer filter must close the gap.

---

## 3. FP corpus analysis at threshold 0.10

An extended S5 run at threshold 0.10 (shim rebuilt locally) produced 17 unique false-positive
messages. These fall into four structurally distinct categories.

### Category A — Single-token garbled (1 message)

```
P?4+S35G2QSB7
```

Contains `?` and `+`, which are not valid FT8 message characters. Single-token output. No
valid FT8 message type produces a single-token string.

**Why it passes the current filter:** The D9-R2 hex-dump rule requires ≥ 16 characters; this
is 13. The per-token oversized check requires at least one space (2-token branch) — there is
none. The final catch-all `if (spaces != 2) return true` accepts it unconditionally.

---

### Category B — 5-token garbled (3 unique messages)

```
JB6X H/R 9T4ZCN/R R OF29
RQ3 RX/R BV6UAS/R R MF99
447DUI/P CQ ATZB R GQ23
```

Five space-separated tokens. No valid Standard QSO or CQ message type exceeds 4 tokens.

**Why it passes:** The code explicitly comments `// 5+ token messages: not validated here`
and falls through to `if (spaces != 2) return true`.

---

### Category C — `CQ <hash>` 2-token (1 unique message, seen twice)

```
CQ <...>
```

Two tokens. `CQ` followed by a hash-notation reference. A station calling CQ always
broadcasts its full callsign; `CQ <hash>` is not a reachable FT8 message type.

**Why it passes:** In the 2-token branch, `IsCallsignOversized("CQ")` returns `false`
(≤ 3 chars, explicitly exempted). `IsCallsignOversized("<...>")` returns `false` (starts
with `<`, the hash-reference exemption). Neither fires. Falls through to catch-all.

---

### Category D — 3-token with `/P` or `/R` callsign suffix (9 messages)

```
3L6FSV/P  H58BHH    NP05    ← token0 = /P
H84QBC/R  6G3TFB    NM92    ← token0 = /R
5N4CQC    YT5LGM/R  MI39    ← token1 = /R
526NDS/P  947GRK/P  CC80    ← both /P
1X8XN/R   P69LWI    FN77    ← token0 = /R
293BPK/P  AJ5TRQ    QC28    ← token0 = /P
808OSW/P  ZS5TPZ    DG27    ← token0 = /P
142CDX/P  4N9ERP    OM12    ← token0 = /P
LC4QLD    26OTD/R   RA54    ← token1 = /R
```

All nine are structurally valid `CALLSIGN CALLSIGN GRID` 3-token messages. Base callsigns
are ≤ 6 characters. Grid locators pass the Maidenhead field letter check (both letters ≤ R).
The existing filter has no lever to reject them.

**Significance:** At threshold 0.35 (the highest value that preserves S7 decode quality),
**all three FPs observed across 22 extended S5 runs were Category D.** Categories A, B, C,
and E do not emerge until the threshold falls below 0.30.

---

### Category E — 3-token, no suffix, structurally indistinguishable from valid traffic (2 messages)

```
VN0PCH 8B2PRR IA31
4N6MOJ FR9MKS GK58
```

Valid-looking callsigns (≤ 6 chars), valid grids. Nothing structurally anomalous. These are
the irreducible hard cases that no text-layer rule can catch. They are suppressed at threshold
0.40 by the correlation gate alone; they do not appear in FP data at threshold 0.35.

---

### Summary

| Category | FPs at 0.10 | FPs at 0.35 | Safe text rule? |
|---|---|---|---|
| A — single-token garbled | 1 | 0 | ✅ Yes — no valid FT8 is ever single-token |
| B — 5-token garbled | 3 unique | 0 | ✅ Yes — no valid FT8 exceeds 4 tokens |
| C — `CQ <hash>` | 1 unique | 0 | ✅ Yes — not a reachable FT8 message type |
| D — 3-token /P or /R | 9 | 3 (all FPs) | ⚠️ See Section 4 |
| E — 3-token no-slash, valid-looking | 2 | 0 | ❌ No text rule possible |

Categories A, B, C can be closed with zero false-negative risk. Category D is the
architectural decision. Category E is not tractable at the text layer.

---

## 4. The architectural problem with Category D

### Why a blanket /P and /R rule is unsafe

`Ft8Decoder.IsPlausibleMessage` is called at line 229 of `Ft8Decoder.cs` on **every result
returned by the native library**, regardless of whether it was decoded by standard
BP+LDPC or by OSD:

```csharp
foreach (ref readonly Ft8NativeResult nr in native.AsSpan())
{
    string msg = nr.Message.TrimEnd();
    if (!seen.Add(msg)) continue;
    if (!IsPlausibleMessage(msg))   // ← applied to ALL decodes
        continue;
    results.Add(...);
}
```

A blanket rule rejecting 3-token non-CQ messages containing `/P` or `/R` would therefore
also suppress valid decodes from standard LDPC. In real FT8 operation, portable (`/P`)
stations are common — SOTA activators, island DX expeditions, portable field operations.
When a `/P` station (e.g. `W1ABC/P`) calls CQ and a second station responds:

```
W1ABC/P  K2DEF   -07    ← token0 carries /P — would be rejected
K2DEF    W1ABC/P -14    ← token1 carries /P — would be rejected
```

Both exchange steps would be filtered, making OpenWSFZ unable to decode any message that
references a portable station's callsign. This is not a narrow edge case; it is a systematic
false negative for an entire class of amateur operation.

The `/R` case (rover) is safer on HF — `/R` is used almost exclusively in VHF/UHF contest
operation and essentially never appears in HF FT8 — but `/P` cannot be handled the same way.

### Root cause

The filter lacks the information it needs: **whether the decode was OSD-derived or
standard-LDPC-derived.** OSD /P and /R outputs are false alarms. Standard LDPC /P and /R
outputs are valid traffic. The same text string has different semantics depending on its
decode origin, and `IsPlausibleMessage` currently cannot distinguish between them.

---

## 5. Three architectural paths

### Path 1 — OSD-origin flag in the native result struct (recommended)

Add a boolean field `IsOsdDerived` to `Ft8NativeResult` (the P/Invoke struct). Set it to
`true` in `decode.c` only when the OSD path produces the accepted codeword. In the C#
layer, pass this flag alongside the message string to a new `IsPlausibleOsdMessage` check
(or extend `IsPlausibleMessage` with an `isOsdDerived` parameter) and apply the /P and /R
filter only when the flag is set.

```
FT8NativeResult
  ├─ Message: string
  ├─ Snr: int
  ├─ FreqHz: float
  ├─ Dt: float
  └─ IsOsdDerived: bool   ← new field
```

**Implications:**
- Requires a shim version bump (struct layout change, ABI break). Correct version: 20260028
  (already allocated for this D-009 fix); the bump is already priced in.
- The OSD path in `decode.c` is a well-contained code block; setting the flag is a two-line
  change in each of the two OSD call sites.
- The C# struct `Ft8NativeResult` gains one field; the marshal layout changes by 4 bytes
  (or 1 byte with `[MarshalAs(UnmanagedType.I1)]` for compactness — architect to advise on
  preferred layout).
- `IsPlausibleMessage` signature changes, affecting its unit tests. The D009 tests will need
  an `isOsdDerived` parameter added to all call sites.
- **False negative risk: zero.** The /P and /R filter fires only on OSD outputs.
- **Category E residual:** at threshold 0.35, Category E FPs do not appear (suppressed by
  correlation gate). If the threshold is ever lowered below 0.30, Category E becomes relevant
  and will require either a higher threshold or further investigation.

### Path 2 — SNR-gated filter in the C# caller (pragmatic shortcut)

Standard BP+LDPC succeeds to approximately −21 dB. Below that, OSD is the only decode path.
`nr.Snr` is available at the `IsPlausibleMessage` call site. Apply the /P and /R filter
only when `nr.Snr < −21` (or a conservatively chosen value such as −22 dB).

```csharp
if (!IsPlausibleMessage(msg, isLowSnr: nr.Snr < -21))
    continue;
```

**Implications:**
- No shim change. No ABI break. No additional fields.
- False negative risk: small but non-zero. A legitimate `/P` station at −22 dB or below
  (mountain-top SOTA, remote island DX) would be suppressed. In practice this band is rare;
  in principle it is a product regression.
- The SNR boundary (−21 dB) is an approximation. The exact crossover varies with noise
  conditions, K_MAX_PASSES, and OSD depth. A conservative value (e.g. −23 dB) reduces the
  false negative rate at the cost of a slightly wider OSD FP window.
- Does not cleanly distinguish OSD from LDPC for the small window where both can succeed.

### Path 3 — Raise threshold to 0.40 and accept the S7 regression

No text-layer change. Accept that:
- AC5 (0 FP events on S5) is met.
- S7 P0 (Δ7 Hz equal-SNR co-channel, 2-stack) decodes at ~57% rather than 85%.

**Implications:**
- Simplest implementation; no new code paths.
- The S7 regression is documented and informational (the analyse.py reports S7 as
  "informational — no AIAG threshold is defined for co-channel separation"), so it is not a
  formal gate failure.
- The regression is nonetheless measurable and real. At 0.40, the OSD threshold is
  suppressing valid CQ-at-1500-Hz candidates in the presence of 1507-Hz interference —
  exactly the case OSD was introduced to solve. The fix erodes part of OSD's benefit.

---

## 6. Comparison

| Criterion | Path 1 (OSD flag) | Path 2 (SNR gate) | Path 3 (0.40 threshold) |
|---|---|---|---|
| AC5: 0 FP events on S5 | ✅ | ✅ | ✅ |
| AC6: S7 co-channel not regressed | ✅ (stay at 0.35) | ✅ (stay at 0.35) | ❌ P0 −28 pp regression |
| False negatives for /P QSOs | None | Rare (< −21 dB) | None |
| Shim version bump required | Yes (struct change) | No | No |
| Code complexity delta | Low | Low | None |
| Architecturally correct | ✅ | Acceptable | N/A |

---

## 7. Scope of safe rules (independent of path chosen)

Regardless of which path is selected for Category D, the following three rules should be
added to `IsPlausibleMessage`. They carry zero false-negative risk and clean up Categories
A, B, and C unconditionally:

**Rule A — Reject single-token messages.**
No valid FT8 decoded message is ever a single token (no spaces). Any string with no space
character is either a hex-dump (already handled by D9-R2 if long enough) or an OSD
codeword that mapped to a garbage message type. `if (!text.Contains(' ')) return false`.

**Rule B — Reject 5+ token messages.**
No valid Standard QSO or CQ message type exceeds 4 tokens. The current code explicitly
leaves 5+ token messages unvalidated. Add a rejection branch after the 4-token check.

**Rule C — Reject `CQ <hash>` 2-token messages.**
In the 2-token branch, if `token0 == "CQ"` and `token1.StartsWith('<')`, the message is
not a reachable FT8 format. CQ calls always carry the calling station's full callsign.

These three rules require no shim change and no parameter change to `IsPlausibleMessage`.
They should be committed regardless of the path chosen for Category D.

---

## 8. Recommendation

**Path 1** is the correct architectural solution. The flag is small (1 bit on the wire),
the change in `decode.c` is localised to two OSD call sites, and it eliminates the
fundamental ambiguity that makes text-layer filtering of OSD output unsafe. The shim bump
is already budgeted for this change.

**Path 2** is an acceptable interim if the architect judges the shim change disproportionate.
The false negative risk for /P QSOs at extreme low SNR is real but very small in practice.

**Path 3** is the fallback if neither text-layer approach is approved. The S7 P0 regression
is documented and does not formally block merge (S7 is informational), but it represents a
genuine product quality reduction in the co-channel case OSD was specifically introduced
to improve.

---

## 9. Questions for the architect

1. Is the `Ft8NativeResult` struct layout change (Path 1) acceptable at this stage, or is
   there a preference to avoid P/Invoke ABI changes outside a scheduled refactor?

2. If Path 2, what SNR boundary is appropriate? −21 dB (theoretical LDPC floor) or a
   more conservative value such as −23 or −24 dB?

3. Should the `/R` rover suffix be treated differently from `/P` (i.e., rejected
   unconditionally on HF regardless of decode origin, given `/R` is essentially never
   used in HF FT8 operation)? This would close 4 of the 9 Category D cases without any
   architectural change.

4. Category E (2 structurally-valid-looking FPs at threshold 0.10; 0 at threshold 0.35):
   is the current plan — correlation gate at 0.35 plus text rules — sufficient, or should
   Category E be formally tracked as a residual risk?
