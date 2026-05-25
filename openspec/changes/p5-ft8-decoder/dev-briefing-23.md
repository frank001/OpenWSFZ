# Developer Briefing — p5-ft8-decoder (Round 23)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Targeted diagnostics to determine why no decodes and no visible waterfall are produced

---

## Situation

After dev-briefing-22 (diagnostic logging removal), the application runs cleanly with
acceptable performance. Two symptoms remain:

1. **No FT8 messages decoded** — no `Ft8Decoder` log entries appear at all.
2. **No visible waterfall** — the canvas appears blank (uniformly black).

Code inspection confirms the pipeline is correctly wired end-to-end. The absence of
_any_ `Ft8Decoder` log entry — including `"Cycle X: 0 decode(s) found."` — is the
critical clue. This line is at `LogInformation` and would appear even with zero results,
**unless the RMS silence guard fires first**:

```csharp
if (rms < 1e-6f)
{
    _logger?.LogDebug("Cycle skipped — RMS {Rms:E3} is below silence guard.", rms);
    return ...
}
```

That guard logs at `LogDebug`, invisible at `Information`. Similarly, `CycleFramer`'s
window-emission log is at `LogDebug`. These two invisible log lines mean we cannot
currently distinguish between:

- **Scenario A** — `DecodeAsync` is being called but audio is silent (RMS guard fires).
  A silent audio stream also produces all-zero spectrum bins → black waterfall → user
  perceives "no waterfall." Most likely root cause: Voicemeeter Out B2 is not receiving
  the WAV player's output.

- **Scenario B** — `CycleFramer` is not emitting windows (some runtime condition not
  visible in static analysis), so the decode pump never calls `DecodeAsync`.

The fix for this briefing is two log-level promotions — one in `CycleFramer`, one in
`Ft8Decoder` — that fire at most once per 15-second cycle and will immediately resolve
the ambiguity.

---

## Tasks

### D1 — Promote `CycleFramer` window-emission log to `LogInformation`

**File:** `src/OpenWSFZ.Ft8/CycleFramer.cs`

```csharp
// Before:
_logger?.LogDebug("Window emitted ({Samples} samples).", SamplesPerCycle);

// After:
_logger?.LogInformation("Window emitted ({Samples} samples).", SamplesPerCycle);
```

**Purpose:** If windows are being emitted, we will see one entry per 15-second cycle.
If no entry appears, Scenario B is confirmed and further investigation of the framer is
required.

---

### D2 — Promote silence-guard log to `LogInformation` and include RMS value

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

```csharp
// Before:
_logger?.LogDebug("Cycle skipped — RMS {Rms:E3} is below silence guard.", rms);

// After:
_logger?.LogInformation("Cycle skipped — RMS {Rms:E3} is below silence guard (threshold 1e-6).", rms);
```

**Purpose:** If audio is silent (Scenario A), we will see one entry per cycle with the
actual RMS value. Combined with D1, this produces one of three outcomes:

| D1 appears | D2 appears | Conclusion |
|---|---|---|
| ✓ Window emitted | ✓ Cycle skipped | Audio is silent — fix Voicemeeter routing |
| ✓ Window emitted | ✗ (neither) | Audio present but 0 decodes — decoder bug or timing |
| ✗ Neither | — | CycleFramer not emitting — pipeline structural fault |

---

## What to check after running with these changes

Run the application, play the FT8 WAV at the correct UTC alignment, and observe the
server log for the first 30 seconds after the first 15-second cycle completes.

**Expected log (healthy pipeline with audio):**

```
[info] CycleFramer — Window emitted (180000 samples).
[info] Ft8Decoder  — Cycle 16:47:00: 3 decode(s) found.
```

**Expected log (pipeline healthy but audio is silence):**

```
[info] CycleFramer — Window emitted (180000 samples).
[info] Ft8Decoder  — Cycle skipped — RMS 0.000E+000 is below silence guard (threshold 1e-6).
```

In the second case: the decoder is working correctly but Voicemeeter is not routing audio
to the B2 output bus. Verify that the WAV player is outputting through Voicemeeter and
that Voicemeeter's B2 bus is receiving it (not merely monitoring it on the A bus).

**Expected log (pipeline broken — CycleFramer not emitting):**

```
(no "Window emitted" entry after the expected cycle boundary)
```

In this case: escalate to QA for a further briefing.

---

## Summary

| Task | File | Change |
|---|---|---|
| D1 | `CycleFramer.cs` | Promote "Window emitted" from `LogDebug` → `LogInformation` |
| D2 | `Ft8Decoder.cs` | Promote silence guard from `LogDebug` → `LogInformation`; include threshold in message |
