# QA Review — p5-ft8-decoder

**Reviewer:** QA (Round 5, 2026-05-25)
**Branch:** `feat/p5-ft8-decoder`
**Scope:** dev-briefings 16–23 (B1/B2/B3 blockers, perf work, shutdown fix, hot-path logging removal, silence-guard diagnostics)
**Verdict:** ✅ APPROVED — no blockers; 3 advisories carried forward

---

## Round 5 — Dev-briefings 16–23 Review

### CI Status

All three CI legs pass on the latest push (`9d28e99`).

| Gate | ubuntu-latest | macos-latest | windows-latest |
|---|---|---|---|
| G1 — Build | ✅ | ✅ | ✅ |
| G3 — Traceability | ✅ | ✅ | ✅ |
| G5 — Licence | ✅ | ✅ | ✅ |

Test suite: **100 passed, 1 skipped** (WAV fixture — known, tracked), 0 failed.

---

### What Was Reviewed

| Area | Assessment |
|---|---|
| **B1 — CycleFramer natural source-end** | ✅ `output.TryComplete()` removed from the non-cancellation path. Test T2 (`RunAsync_SourceEndsNaturally_DoesNotCompleteOutputChannel`) present and correct. |
| **B2 — Restart semaphore** | ✅ `restartSemaphore = new SemaphoreSlim(1, 1)` present. `RestartPipelineAsync` helper wraps all three caller paths (`CaptureFailed`, `OnSaved`, watchdog). `ApplicationStopping` acquires semaphore before teardown. |
| **B3 — AudioWatchdog singleton** | ✅ Watchdog constructed once in `WebApp.Create`; passed to `HandleAsync` as an injected parameter. Per-connection construction removed. Test T3 present. |
| **R1 — ComputeLeadingSamples ms offset** | ✅ Early `return 0` removed. Test T1 (`ComputeLeadingSamples_AtBoundaryWithNonZeroMilliseconds_IncludesSubSecondOffset`) present and covers `Second%15==0, Millisecond=750`. |
| **R2 — SendWithTimeoutAsync CloseAsync** | ✅ Both `OperationCanceledException` catch blocks in `SendWithTimeoutAsync` now call `ws.Abort()` instead of `ws.CloseAsync(…, default)`. |
| **A1 — Hann window periodic form** | ✅ `FftSize - 1` → `FftSize`; docstring explains reasoning. Applied to both the `SpectrumAnalyser` path and the new `FillSpectrogram` path. |
| **A3 — ReadAllAsync no CT** | ✅ `stoppingToken` threaded through to `ReadAllAsync` and propagated into `DecodeAsync`. Shutdown exits the pump at cancellation boundary, not at decode completion. |
| **FftCompute.cs — shared FFT utility** | ✅ Extracted correctly. Both `SpectrumAnalyser` and `SymbolExtractor` delegate to `FftCompute.Fft`. No logic duplication. |
| **FillSpectrogram / spectrogram path** | ✅ `_spectrogram` pre-allocated at construction (316 KB on LOH, once per decoder instance). `FillSpectrogram` writes into the buffer; `re`/`im` work arrays (8 KB each, SOH) allocated per call — acceptable. |
| **rAF throttle — main.js** | ✅ `pendingSpectrumBins` + `spectrumRafPending` flag correctly coalesce rapid WebSocket messages into a single `putImageData` per animation frame. |
| **WasapiAudioSource cleanup** | ✅ Hot-path diagnostic calls removed. `StopRecording` and `Dispose` run on background thread-pool threads with 3 s timeout each; STA thread is no longer blocked by slow driver shutdown. |
| **LeftChannelSampleProvider** | ✅ Correctly extracts left channel at index `i * 2` from interleaved stereo. `_stereoBuffer` growth condition is safe (`stereoCount = count * 2`; normal 2048-sample reads do not trigger growth). |
| **Silence-guard / window-emission logs** | Promoted to `Information` — see A2 below. |
| **appScope / AbortAll** | ✅ Scope ID scopes `AbortAll` to the owning `WebApp` instance. Integration-test isolation is correct. `ConcurrentDictionary<WebSocket, Guid>` value type change is internal — no public API break. |
| **New tests (T1, T2, T3)** | ✅ All three required tests present, correctly named, and test the right behaviours. |

---

### A1 — Advisory · Untracked advisory A2 from dev-briefing-16 (tone-index modulo wrap)

`CostasSynchroniser.FindCandidates` still produces candidates with `FreqBinOffset` 1–7.
`ComputeLlrs` wraps those offsets modulo 8 (`(t + freqShift) % 8`), reading lower-frequency
bins from the same 8-element grid. These candidates produce incorrect LLRs, almost
always fail LDPC/CRC, and are discarded — but they waste decode work.

This was advisory in dev-briefing-16 and remains unaddressed. Track as a known
follow-up item for a later phase. **Does not block merge.**

---

### A2 — Advisory · Window-emission log at `Information` level

**File:** `src/OpenWSFZ.Ft8/CycleFramer.cs`

The `"Window emitted ({Samples} samples)."` message was promoted to `Information` by
dev-briefing-23 to confirm windows were flowing. At that level it appears in the
default console output every 15 seconds (240 lines/hour) with no actionable content
for operators.

Now that the silence-guard diagnosis is complete, this should revert to `LogDebug`.
**Does not block merge**, but the line should land at `Debug` before p5 is archived.

---

### A3 — Advisory · `AudioWatchdog._silentWindows` has no thread-safety mechanism

**File:** `src/OpenWSFZ.Web/AudioWatchdog.cs`, line 21

`_silentWindows` is a plain `int` with no `Interlocked` or locking. Two concurrent
heartbeat loops (one per connected WebSocket client) can race on the read-modify-write:

```csharp
if (++_silentWindows >= _threshold)
{
    _silentWindows = 0;
    await _onRestart();
}
```

If two clients simultaneously see `_silentWindows = 2` and both increment past threshold,
both fire `_onRestart()`. The `restartSemaphore` in `Program.cs` serialises the restarts,
so the second restart runs immediately after the first — no data loss, but an unnecessary
double restart occurs.

The race is probabilistic (5-second heartbeat windows, unlikely to collide in practice)
and the damage is bounded. Test T3 tests sequential calls, not true concurrency.

Mitigation options: `Interlocked.Increment` + `Interlocked.Exchange`, or a `lock` around
the whole tick body.

**Does not block merge.** Should be addressed in the next phase that touches `AudioWatchdog`.

---

### Checklist for Merge

- [x] All Round 4 blockers resolved (B5, A1, A2 from Round 4)
- [x] All dev-briefing-16 blockers resolved (B1, B2, B3)
- [x] All dev-briefing-16 recommended fixes resolved (R1, R2)
- [x] Required tests T1, T2, T3 present and passing
- [x] CI green — all 3 legs pass
- [x] 100 tests pass, 0 failures
- [ ] A2 (window-emission log): revert `LogInformation` → `LogDebug` in `CycleFramer.cs` before archiving *(non-blocking — can merge as-is)*

**Ready to merge to `main`.**

---

**Reviewer:** QA (Round 4, 2026-05-24)
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Spectrum visualisation — dev-briefing-15 implementation
**Verdict:** ❌ RETURN TO DEVELOPER — 1 blocker (CI failure); 2 advisories

---

## Round 4 — Spectrum Visualisation Review

### CI Status

Gate G3 (Traceability check, Linux) is **failing**. All other gates pass.

```
FAIL: 1 requirement(s) not mapped to any test:
  FR-021
```

---

### B5 — BLOCKER · FR-021 test display names do not match the scanner regex

**File:** `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs`, lines 124, 150, 200

**Root cause:** `TestAssemblyScanner.ExtractIds` uses the regex:

```
^((?:FR|NFR)-\d{3})(?:\s*,\s*((?:FR|NFR)-\d{3}))*\s*:
```

This requires the requirement ID to be followed **immediately** by optional whitespace and
then a colon. The developer placed "Case N" between the ID and the colon, which prevents
the scanner from recognising the tag.

| Line | Current (broken) | Required |
|---|---|---|
| 124 | `"FR-021 Case 1: CaptureManager logs Information …"` | `"FR-021: Case 1 — CaptureManager logs Information …"` |
| 150 | `"FR-021 Case 2: CaptureManager logs Warning …"` | `"FR-021: Case 2 — CaptureManager logs Warning …"` |
| 200 | `"FR-021 Case 3: CaptureManager logs Error with exception …"` | `"FR-021: Case 3 — CaptureManager logs Error with exception …"` |

Move "Case N" to the right of the colon, separated by " — " for readability.
The assertion messages inside each test that repeat the old format should be updated
to match, though they do not affect the scanner.

**Fix is trivial — three one-line display name changes.**

---

### A1 — Advisory · FR-008 debt not discharged

**File:** `traceability-debt.md` line 32; `tests/OpenWSFZ.Ft8.Tests/SpectrumAnalyserTests.cs`

FR-008 (Waterfall display — live spectrogram of audio input) is now implemented.
The debt file rule states: *"Remove an ID from this file once its implementing phase's
tests arrive."* The implementing tests exist (`SpectrumAnalyserTests`) but carry no
`FR-008` display name, so the tool cannot discharge the exemption automatically.

**Required:**

1. Add `[Fact(DisplayName = "FR-008: ...")]` to at least the T-1 (sine wave peak) and
   T-3 (fires once per FftSize) tests — these most directly demonstrate that the live
   spectrum is computed and delivered. T-2 (silence floor) may share the tag or carry
   its own `FR-008` entry.

2. Remove `FR-008` from `traceability-debt.md`.

This is advisory only because the debt file exemption currently prevents a CI failure.
However, leaving the debt untagged indefinitely is contrary to the project's traceability
discipline. Address in this same commit alongside B5.

---

### A2 — Advisory · Stale JSDoc in `main.js`

**File:** `web/js/main.js`, line 4

```
 * - Paints the waterfall canvas placeholder.
```

This module no longer paints a placeholder. It initialises a live `WaterfallRenderer`.
Update the comment accordingly. One line change.

---

### What Was Reviewed

| Area | Assessment |
|---|---|
| `SpectrumAnalyser.cs` | ✅ Matches briefing exactly. FFT, Hann window, `Reset()` all correct. |
| `SpectrumEventBus.cs` | ✅ Correct. `HasClients` exposure is a reasonable design choice. |
| `WebSocketHub` additions | ✅ `HasClients`, `BroadcastSpectrum` correctly implemented. |
| `AppJsonContext.cs` | ✅ `WsSpectrumMessage` and `int[]` registered. |
| `Program.cs` wiring | ✅ `Push` present; `Reset()` called in all 3 restart locations; `using` added. |
| `spectrum.js` | ✅ Matches briefing. `copyWithin` scroll correct. Alpha pre-initialised. Colormap correct. Frequency axis correct. |
| `main.js` | ✅ Placeholder removed. `spectrum` event handled before `decode`. `WaterfallRenderer` instantiated. |
| `app.css` | ✅ `cursor: crosshair` added. |
| `SpectrumAnalyserTests.cs` | ✅ T-1, T-2, T-3 all present and correctly written. Peak bin, silence floor, fire-count assertions are meaningful. |
| `CaptureManagerTests.cs` | ❌ FR-021 display names use wrong format — see B5. |

---

### Checklist for Re-submission

- [ ] Fix **B5**: rename the three FR-021 test display names so the colon follows the ID directly
- [ ] Fix **A1**: add `FR-008` display names to SpectrumAnalyserTests; remove `FR-008` from debt file
- [ ] Fix **A2**: update the stale JSDoc comment in `main.js`
- [ ] Run `dotnet test -c Release` locally — confirm 0 failed
- [ ] Push — confirm Gate G3 goes green

---

**Reviewer:** QA (Round 3, 2026-05-22)
**Branch:** `feat/p5-ft8-decoder`
**Verdict:** ✅ ALL BLOCKERS RESOLVED — B4 fix applied 2026-05-22; ready for draft PR

---

## Progress Summary

| Item | Status |
|---|---|
| B2 — `InfoBits = 91`, `Crc14.Verify(decoded, 91)` | ✅ Applied |
| B3 — `SamplesPerSymbol = 2000` (should be 1920) | ✅ Applied (`(int)(SampleRate / ToneSpacingHz)`) |
| S3 — `Array.IndexOf` removed; `VarNeighboursIdx` pre-computed | ✅ Applied |
| B1 — heartbeat test cross-contamination | ✅ Applied |
| S1 — dead code in `DecodeCallsign28` | ✅ Applied |
| S2 — `innerHTML` XSS in `main.js` | ✅ Applied |
| Time-domain search gap | ✅ Documented as known v1 limitation; tracked as task 4.2-bis |
| S4 — concurrent `SendAsync` race | ✅ Tracked as task 14.1 |
| **B4 — `Crc14.Compute` algorithm mismatch** | ✅ Applied (2026-05-22) |

**Test suite:** ✅ 120 passed, 1 skipped (WAV fixture), 0 failed.

The pipeline is structurally complete. The remaining blocker is a single incorrect
implementation of a well-specified algorithm.

---

## Root Cause — Round 3

### B4 · `Crc14.Compute` does not implement the FT8 CRC-14 algorithm

**File:** `src/OpenWSFZ.Ft8/Dsp/Crc14.cs`

The CRC implementation is self-consistent — the round-trip unit tests pass — but it
computes a *different* value from the algorithm used by every FT8 transmitter (WSJT-X
and compatible software). Because the CRC bits embedded in a decoded WSJT-X transmission
are computed by the standard algorithm, and `Verify` uses the non-standard one, the
comparison will always fail for any real FT8 signal. LDPC may converge correctly; the
result is silently discarded at the CRC gate.

#### The algorithm error

The standard FT8 CRC-14 (Franke & Taylor 2019 / WSJT-X):

```
for each incoming bit:
    feedback = (MSB of current register) XOR incoming_bit
    register = (register << 1) AND 0x3FFF   ← shift out old MSB, new LSB is 0
    if feedback == 1: register XOR= 0x2757
```

The feedback is driven by the **old MSB** (the bit that is about to leave the register)
XORed with the incoming data bit.

The developer's implementation:

```csharp
crc = ((crc << 1) | bit) & Mask;                   // shift left, insert bit at LSB
if ((crc & (1u << (Bits - 1))) != 0)               // check NEW bit-13 (= old bit-12)
    crc ^= Poly;
```

The feedback here is driven by **new bit 13** — which is the *old bit 12*, not the old
bit 13 XORed with the incoming bit. The check is one bit position wrong and the incoming
bit is stored in the register directly rather than consumed as feedback. This is a
structurally different algorithm.

A second error follows: after the main loop, the code runs a 14-iteration flush:

```csharp
for (int i = 0; i < Bits; i++)
{
    crc <<= 1;
    if ((crc & (1u << Bits)) != 0)
        crc ^= Poly;
}
```

The FT8 CRC specification has no flush. The register state after processing the 77
message bits is the CRC directly. The flush produces an unspecified additional transform
that further diverges the output from the standard value.

#### Verified divergence — identical 3-bit input, both algorithms traced

| Step | Developer (`0x0005` after 3 bits) | Standard / WSJT-X (`0x13F2` after 3 bits) |
|---|---|---|
| Initial | 0x0000 | 0x0000 |
| bit=1 | 0x0001 | **0x2757** (feedback=1→XOR poly) |
| bit=0 | 0x0002 | **0x29F9** |
| bit=1 | 0x0005 | **0x13F2** |

The values diverge at the very first bit. For a real WSJT-X-encoded message the
reference CRC (bits[77..90] of the LDPC output) is computed by the standard algorithm;
`Crc14.Verify` will never produce a match.

#### Why the unit tests do not catch this

`Crc14_RoundTrip_Verifies` calls `Compute` to produce a CRC, appends it, and calls
`Verify` to check. Both calls use the same (wrong) algorithm, so they agree with each
other. The test proves internal consistency, not correctness against the specification.
A test with a known reference vector from a WSJT-X transmission or the specification
appendix would have caught this immediately.

#### Required fix — replace `Compute`; remove the flush; `Verify` unchanged

```csharp
public static uint Compute(ReadOnlySpan<byte> bits, int bitCount)
{
    uint crc = 0u;

    for (int i = 0; i < bitCount; i++)
    {
        uint bit      = bits[i] & 1u;
        // Standard CRC-14: feedback is old MSB XOR incoming bit.
        uint feedback = ((crc >> (Bits - 1)) ^ bit) & 1u;
        crc           = (crc << 1) & Mask;   // shift left; old MSB is discarded
        if (feedback != 0)
            crc ^= Poly;
    }

    // No flush — the register state after bitCount iterations is the CRC.
    return crc;
}
```

`Verify` is structurally correct (compute CRC over first 77 bits, compare to last 14)
and requires no changes.

#### Unit test update required

After fixing `Compute`, add a reference-vector test to prevent regression. Use the
known CRC of an all-zero 77-bit message under the correct algorithm (0x0000 — the
standard CRC of all-zeros is 0, since feedback is always 0 when register and data are
both 0). Update the existing test name to reflect what is actually being asserted:

```csharp
[Fact]
public void Crc14_KnownVector_AllZeroMessage_ProducesZeroCrc()
{
    var bits = new byte[77]; // all zero
    uint crc = Crc14.Compute(bits, 77);
    crc.Should().Be(0u,
        "standard CRC-14 of an all-zero message is 0: feedback is always 0^0=0, " +
        "so the polynomial is never applied and the register remains 0");
}
```

The round-trip test (`Crc14_RoundTrip_Verifies`) and the flipped-bit test
(`Crc14_FlippedBit_Fails`) continue to be valid after the fix and require no changes.

---

## Build & Test Status (Round 3 — post B4 fix)

| Gate | Result |
|---|---|
| `dotnet build -c Release` | ✅ 0 errors, 0 warnings |
| `dotnet test -c Release` (full suite) | ✅ 120 passed, 1 skipped (WAV fixture), 0 failed |

---

## Checklist for Re-Submission

- [x] Fix **B4**: Replace `Crc14.Compute` with the standard feedback algorithm; remove the flush loop
- [x] Add `Crc14_KnownVector_AllZeroMessage_ProducesZeroCrc` reference-vector test
- [x] Run `dotnet test -c Release` — 0 failed, 120 passed, 1 skipped ✅
- [ ] Open draft PR to `main` (task 13.5)

---

## Note — WAV Fixture Remains the Critical Missing Safety Net

Every defect found across three review rounds — the 2000-sample window, the wrong CRC
boundary, and now the wrong CRC algorithm — survived the unit-test suite undetected
because all three tests use synthetic data that cannot distinguish a correct
implementation from a self-consistent-but-wrong one. Tasks 8.1 and 8.2 (committing
`ft8-sample.wav` and enabling task 7.3) must be treated as blockers for the *next*
phase, not optional polish. One real 15-second WAV fixture would have caught all three
of these in the first round of review.
