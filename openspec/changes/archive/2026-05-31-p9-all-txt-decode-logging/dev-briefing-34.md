# Developer Briefing — p9-all-txt-decode-logging (Round 34)

**Date:** 2026-05-28  
**Issued by:** QA  
**Branch:** `feat/p9-all-txt-decode-logging`  
**Scope:** Live smoke-test findings — three defects: D16, D17, D18

---

## Summary

The live smoke test against a real 40 m FT8 session (2026-05-28 18:38:15 UTC, 7.074 MHz)
reveals three defects.  D16 and D17 are mechanical format corrections to `AllTxtWriter`;
they are to be fixed first so that subsequent live runs produce a clean reference file.
D18 is the primary concern and requires diagnostic investigation before any fix attempt.

| ID | Severity | Description |
|----|----------|-------------|
| D16 | Medium | `AllTxtWriter` emits a 5-character DT field; WSJT-X uses 4 |
| D17 | Low | `AllTxtWriter` emits LF-only line endings; WSJT-X uses CRLF |
| D18 | **Critical** | Decoder produces zero real FT8 decodes and ~12 false positives/cycle from live audio; WSJT-X decoded 42 real stations from the same source simultaneously |

---

## 1. D16 — DT Field Width (5 chars vs 4 chars)

### Root cause

`AllTxtWriter.AppendAsync` line 75 uses `{result.Dt,5:F1}`.  The WSJT-X format uses a
**4-character DT field**.  The spec (`specs/decode-log/spec.md`) was written incorrectly
as `{dt,5:F1}` and the implementation faithfully followed the spec.  Both the code and
the spec require correction.

### Evidence

```
WSJT-X:       260528_183815     7.074 Rx FT8      2  0.2 1275 CQ Q9FF JO75
Application:  260528_183815     0.000 Rx FT8      3   1.3 1431 CQ 1TJK  BE00
                                                       ^^^^ 5-char DT field
```

### Fix

**`src/OpenWSFZ.Daemon/AllTxtWriter.cs` — line 75:**
```csharp
// Before:
string line = $"{timestamp}     {dialMhz:F3} Rx FT8 {result.Snr,6} {result.Dt,5:F1} {result.FreqHz,4} {result.Message}";
// After:
string line = $"{timestamp}     {dialMhz:F3} Rx FT8 {result.Snr,6} {result.Dt,4:F1} {result.FreqHz,4} {result.Message}";
```

**`tests/OpenWSFZ.Daemon.Tests/AllTxtWriterTests.cs` — test FR-028 line format:**

Update the expected string in task 5.2.  The corrected expected line is:

```
260528_172930     7.074 Rx FT8      3  0.2 2252 Q4DSA QD1BER JO22
```

(2 spaces before `0.2`: 1-char field separator + 1-char left-pad of `0.2` in a 4-char field.)

**`openspec/changes/p9-all-txt-decode-logging/specs/decode-log/spec.md`:**

In the "Correct column alignment matches WSJT-X" scenario, update the expected line and
remove the erroneous parenthetical note about "3 spaces before '0.2'".

---

## 2. D17 — Line Endings (LF vs CRLF)

### Root cause

`AllTxtWriter.cs` line 62 sets `NewLine = "\n"` on the `StreamWriter`.  WSJT-X writes
`\r\n` (CRLF).  Third-party tools that parse ALL.TXT on Windows (log viewers, cluster
aggregators) typically expect CRLF.

### Fix

**`src/OpenWSFZ.Daemon/AllTxtWriter.cs` — line 62:**
```csharp
// Before:
NewLine = "\n"
// After:
NewLine = "\r\n"
```

No test changes required — existing tests assert line *content* via `File.ReadAllLines`,
which strips line endings.

---

## 3. D18 — Zero Real FT8 Decodes from Live Audio

### Symptom

During the 18:38:15 UTC cycle on 2026-05-28, WSJT-X decoded 42 real FT8 stations from
7.074 MHz.  The application, operating on the same audio device simultaneously, produced
~12 decode lines per cycle over 19 cycles.  Not one matches any WSJT-X decode.

| Metric | WSJT-X | Application |
|--------|--------|-------------|
| Decodes per cycle | 42 | ~12 |
| Valid amateur callsigns | 42/42 (100 %) | 0/~12 (0 %) |
| SNR range | −21 to +19 dB | 2–6 dB (suspiciously uniform) |
| Out-of-range report values | 0 | majority |
| Overlap with WSJT-X frequencies | — | 0 |

All application decodes exhibit one or more of: digit-starting callsigns (`1TJK`,
`3BFW`), numerically impossible RSL reports (`+2158`, `+4011`, `+8113`), and anomalously
uniform low SNR.  These are CRC-14 false positives — random bit patterns that cleared a
1-in-16,384 probability test by coincidence.

### Why the false-positive count is anomalous

With `MaxCandidatesPerSweep = 2`, 102 time steps, and 60 baseHz steps, the theoretical
ceiling is 12,240 LDPC evaluations per cycle.  At CRC-14 false-pass probability 1/16,384
the expected false-positive rate is **≈ 0.75/cycle**.  Observed rate is **≈ 12/cycle —
16× the random expectation**.  This indicates either:

(a) Substantially more LDPC evaluations are occurring than the ceiling suggests (i.e. the
    Costas gate is admitting far more candidates than expected), or  
(b) The audio content has structure that produces near-codeword LLR vectors, making CRC
    coincidences more likely than uniformly random.

In either case, the concurrent absence of any real signal decode points to a defect in
the **audio path** rather than in the DSP logic.

### Why the unit tests are not affected

The test suite exercises the full DSP pipeline with programmatically generated float PCM
at exactly 12,000 Hz, single-tone signals, known amplitude.  Unit tests passing confirms
that Goertzel, LLR computation, and LDPC are logically correct given *ideal* input.
A defect in the audio delivery layer — wrong sample rate, wrong channel count, wrong
sample format — would pass unnoticed by any existing test.

### Hypotheses — in priority order

**H1 — Audio format mismatch (most likely)**

The decoder expects **12,000 Hz mono float32 PCM**.  If the capture layer delivers audio
in a different format without correcting it, all Goertzel energies are computed at the
wrong frequencies and all FT8 symbol-timing windows are misaligned.

| Mismatch | Observable effect |
|----------|-------------------|
| Captured at 48,000 Hz, treated as 12,000 Hz | FT8 tones appear at 4× expected frequency; the 15-second window only covers 3.26 s of real audio |
| Stereo interleaved, treated as mono | Effective sample rate appears halved; alternating channel samples introduce systematic distortion |
| 16-bit integer samples, not normalised to float [-1, 1] | Amplitude 32,768× too large; absolute `maxE` values shift dramatically but Costas score (relative) is largely unaffected |

The first two mismatches fully explain both symptoms: real signals are scrambled beyond
recognition (→ zero real decodes) while incidental structure in the mangled audio
occasionally satisfies the Costas pattern by chance (→ false positives).

**H2 — Costas gate too permissive for live audio**

For ideal white noise, the expected Costas score is ≈ 0.125 (well below the 0.45
threshold).  Structured audio — carrier leakage, 50/60 Hz interference, or the dense
signal environment of a busy 40 m FT8 band — can produce scores significantly above
0.125 without a genuine Costas sync being present.  This would increase the LDPC
evaluation count above the theoretical ceiling and explain the elevated false-positive
rate.  However, it cannot alone explain the absence of real signal decodes; it is most
likely a contributing factor compounding H1.

**H3 — `MaxCandidatesPerSweep = 2` dropping real signals at crowded frequencies**

On a busy band, multiple real signals may share the same (time-step, baseHz) bucket.
Capping at 2 candidates could drop the third and fourth strongest.  This would reduce
real decode count but not to zero across 60 frequency buckets — it is insufficient on
its own to explain 0/42 real signals.

### Required diagnostics — report before attempting any fix

Add temporary `LogDebug`-level instrumentation (do not remove existing production
logging; add new statements that can be deleted after diagnosis is complete).  Run one
live decode cycle on the 40 m FT8 band, capture the output, and report the three values
below.

---

**Diagnostic 1 — PCM window statistics**

Location: `Ft8Decoder.DecodeAsync`, at the point where the PCM array is received and
before the sweep loop begins.

```csharp
// TEMPORARY D18 DIAGNOSTIC — remove after investigation
if (_logger.IsEnabled(LogLevel.Debug))
{
    float min = float.MaxValue, max = float.MinValue, sumSq = 0f;
    foreach (var s in pcm) { min = MathF.Min(min, s); max = MathF.Max(max, s); sumSq += s * s; }
    float rms = MathF.Sqrt(sumSq / pcm.Length);
    _logger.LogDebug("[D18-1] PCM count={Count} min={Min:F4} max={Max:F4} rms={Rms:F4}",
        pcm.Length, min, max, rms);
}
```

**Expected values for correct 12,000 Hz mono float audio:**

| Field | Expected range | Out-of-range interpretation |
|-------|---------------|----------------------------|
| `count` | ~180,000 ± 2 % | ≪ 180,000 → wrong sample rate or short capture |
| `min/max` | ± 0.05 to ± 1.0 | > ± 1.0 → not normalised; ≈ ± 32768 → int16 passed as float |
| `rms` | 0.005 – 0.3 | < 0.001 → near-silence or wrong device |

---

**Diagnostic 2 — Costas score at a known real-signal position**

WSJT-X decoded a signal at **731 Hz, DT ≈ 0.1 s** during the 18:38:15 cycle.  In the
sweep grid this corresponds to `baseHz = 700`, `freqShift = 5` (5 × 6.25 Hz = 31.25 Hz
→ 731.25 Hz ≈ 731 Hz), `startSample ≈ 1,200`.

Location: `CostasSynchroniser.Evaluate` (or the inner sweep body in `Ft8Decoder`),
add a conditional log for this specific candidate:

```csharp
// TEMPORARY D18 DIAGNOSTIC — remove after investigation
bool isKnownSignal = Math.Abs(baseHz - 700) < 1 && freqShift == 5 &&
                     startSample is >= 960 and <= 1440;
if (isKnownSignal && _logger.IsEnabled(LogLevel.Debug))
    _logger.LogDebug("[D18-2] Costas at 731 Hz startSample={S}: score={Score:F4} maxE={MaxE:F2}",
        startSample, score, maxE);
```

**Interpretation:**

| score | Diagnosis |
|-------|-----------|
| < 0.45 | Costas gate suppresses this real signal — evaluate whether threshold needs reduction |
| ≥ 0.45 | Costas passes; proceed to Diagnostic 3 |

---

**Diagnostic 3 — Initial LDPC parity failures at the 731 Hz candidate**

Location: `LdpcDecoder.Decode`, at the point where `CountInitialParityFailures` is called
(or add the call if not already present for this code path).  Log for the D18-2 candidate
only.

```csharp
// TEMPORARY D18 DIAGNOSTIC — remove after investigation
_logger.LogDebug("[D18-3] LDPC initial parity failures at 731 Hz: {Count}/83", initialFails);
```

**Interpretation:**

| `initialFails` | Diagnosis |
|---------------|-----------|
| 0 – 20 | LLRs are plausible; LDPC should converge on a real signal |
| ≈ 41 | Systematic LLR sign inversion — all soft bits are backwards |
| ≈ 83 | LLRs are essentially random — Goertzel or symbol extraction is receiving garbage |

---

### What to report back

Paste the raw log lines for D18-1, D18-2, and D18-3.  Do not interpret them; QA will
issue fix instructions based on the measurements.  Do not attempt to fix D18 before
reporting these values — the correct fix depends entirely on which hypothesis is confirmed
by the data.

---

## 4. Implementation Plan

### D16 + D17 — do first (green build required before D18 diagnostics)

| Step | Action |
|------|--------|
| 1 | `AllTxtWriter.cs` line 75: `{result.Dt,5:F1}` → `{result.Dt,4:F1}` |
| 2 | `AllTxtWriter.cs` line 62: `NewLine = "\n"` → `NewLine = "\r\n"` |
| 3 | `AllTxtWriterTests.cs`: update task 5.2 expected string (2 spaces before `0.2`) |
| 4 | `specs/decode-log/spec.md`: update column alignment scenario and remove erroneous DT-width note |
| 5 | `dotnet build -c Release` — 0 errors, 0 warnings |
| 6 | `dotnet test -c Release` — all tests green |
| 7 | Commit D16 + D17 to `feat/p9-all-txt-decode-logging` |

### D18 — diagnostic run (no fix yet)

| Step | Action |
|------|--------|
| 1 | Add D18-1, D18-2, D18-3 debug log statements as specified above |
| 2 | Set log level to Debug for `OpenWSFZ.Ft8` and `OpenWSFZ.Daemon` namespaces |
| 3 | Run one live 15-second decode cycle with 7.074 MHz audio |
| 4 | Capture the three `[D18-x]` log lines and report back to QA |
| 5 | QA issues fix brief based on measurements |
| 6 | Remove all `// TEMPORARY D18 DIAGNOSTIC` instrumentation in the same commit as the fix |
