# QA Review — Branch `feat/p7-p6-logging-and-display`

**Reviewer**: QA  
**Date**: 2026-05-26  
**Updated**: 2026-05-27  
**Verdict**: ✅ **All defects resolved — ready for re-review**

The p6 (file logging) and p7 (device display name) infrastructure changes are sound, and the two
in-session fixes (`ReadFully = false`, `LoggingConfig` null guard) are correct. The blocking issues
are in the FT8 decode pipeline, which was validated only against silence and synthetic grids —
never against a real signal. Live testing against WSJT-X on the same audio device exposed
six defects. Three additional defects (D7–D9) were found and fixed during the follow-up session.

**Fix status**: 182 tests, 0 failures, 0 skipped. Fixture test `DecodeAsync_WavFixture_ReturnsKnownDecodes`
passes in 2 seconds using a synthetic encoder + the full decoder pipeline.

---

## Defects — Required Fixes Before Merge

### D1 — Spectrum display: wrong dBFS mapping range
**File**: `src/OpenWSFZ.Daemon/Program.cs` (spectrum publish block)  
**Severity**: Blocker — makes the waterfall functionally useless

The current mapping is `[-120, 0] dBFS → intensity [0, 255]`. FT8 signals at typical SDR/microphone
levels sit at roughly **-70 to -85 dBFS per FFT bin**. At those levels the mapping produces
intensities 64–106, which are visually indistinguishable from the noise floor at ~64.
The result is the uniform blue-cyan wash seen in the screenshot — signals cannot be identified
by eye.

WSJT-X applies adaptive dynamic-range normalisation; OpenWSFZ uses a fixed linear map.

**Required fix**  
Either narrow the fixed range to something like `[-100, -20] dBFS → [0, 255]`:

```csharp
// In the spectrumAnalyser.SpectrumReady handler in Program.cs:
const float DbMin = -100f;
const float DbMax = -20f;
const float DbRange = DbMax - DbMin;

var db = magnitudes[i];
if (db < DbMin) db = DbMin;
if (db > DbMax) db = DbMax;
bins[i] = (int)MathF.Round((db - DbMin) / DbRange * 255f);
```

Or compute an adaptive noise floor per frame (e.g. the 10th-percentile bin value) and normalise
relative to it. Either approach will make FT8 signal clusters visually distinct from the noise floor.

---

### D2 — Spurious `DE DE AA00` false-positive decode: all-zeros codeword vulnerability
**File**: `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (after CRC verification)  
**Severity**: High — decoder produces invalid output from pure noise

**Root cause**  
Three facts combine to create a false decode whenever all 174 LDPC LLRs happen to be positive:

1. **LDPC parity**: the all-zeros codeword `[0,0,…,0]` trivially satisfies every check equation
   (`0 XOR 0 XOR … = 0`), so `ParityCheck` returns `true`.
2. **CRC-14**: `Crc14.Compute` uses initial register value `0`; therefore `Crc14.Compute(77 zero bits) = 0`.
   The appended CRC field is also `0`, so `Crc14.Verify` returns `true`.
3. **Message unpacker**: `DecodeCallsign28(0) → "DE"`, grid `0 → "AA00"`, giving the observed
   output `DE DE AA00`.

Any noise frame or very-weak signal that drives all LLRs slightly positive will hit this path.
The decode seen at `19:11:30 +0 +0.0 69 DE DE AA00` in the screenshot is this false positive.

**Required fix** — add one guard after the CRC check in `Ft8Decoder.DecodeAsync`:

```csharp
bool crcOk = Crc14.Verify(decoded, 91);
if (!crcOk) continue;

// Guard: the all-zeros 91-bit block trivially satisfies LDPC parity and CRC-14
// (initial register = 0).  No valid FT8 transmission encodes to all zeros.
bool allZeros = true;
for (int z = 0; z < decoded.Length; z++)
    if (decoded[z] != 0) { allZeros = false; break; }
if (allZeros) continue;
```

---

### D3 — Zero-padding from 1920 to 2048 samples misaligns high-numbered FT8 tones
**File**: `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs` — `FillSpectrogram` / `ExtractFromSpectrogram`  
**Severity**: High — degrades decoder SNR for real signals; explains missed decodes

**Root cause**  
`FillSpectrogram` zero-pads each 1920-sample symbol window to 2048 before the FFT. This changes
the bin spacing from the natural **6.25 Hz** (= 12000 / 1920, which perfectly tiles with FT8 tone
spacing) to **5.859 Hz** (= 12000 / 2048). FT8 tones are at multiples of 6.25 Hz; the extracted
bin indices `baseBin + t` are at multiples of 5.859 Hz. The drift accumulates:

| Tone index | Tone freq (for base 1500 Hz) | Nearest FFT bin freq | Offset |
|---|---|---|---|
| 0 | 1500.00 Hz | 1500.00 Hz | 0.00 Hz |
| 1 | 1506.25 Hz | 1505.86 Hz | 0.39 Hz |
| 3 | 1518.75 Hz | 1517.58 Hz | 1.17 Hz |
| 5 | 1531.25 Hz | 1529.30 Hz | 1.95 Hz |
| 7 | 1543.75 Hz | 1541.02 Hz | **2.73 Hz** |

For tone 7, the signal energy is split across two adjacent FFT bins. The bin that
`ExtractFromSpectrogram` reads captures only **~51% of the tone's energy** (−2.9 dB). For symbols
that encode tone 7, the LLRs for bits b₂ and b₀ are weakened accordingly. At −20 to −24 dB
WSJT-X SNR this is enough to prevent convergence of the LDPC decoder.

WSJT-X computes per-tone energy at the exact FT8 frequency using the Goertzel algorithm, which
is unaffected by FFT bin alignment. OpenWSFZ already has this as `SymbolExtractor.Extract`.

**Option A — one-line fix in `ExtractFromSpectrogram`**  
Instead of assuming tones are spaced at FFT-bin intervals, compute the nearest bin to the actual
tone frequency:

```csharp
// Current (wrong for t > 0 when bin spacing ≠ tone spacing):
int bin = baseBin + tone;

// Fixed: find the bin nearest to the actual FT8 tone frequency:
// baseBin was computed as round(baseHz * FftSizePadded / SampleRate).
// For tone t, the actual frequency is baseHz + t * ToneSpacingHz.
// Recalculate the bin for that exact frequency.
int bin = (int)Math.Round((baseHz + tone * ToneSpacingHz) * FftSizePadded / SampleRate);
```

This requires passing `baseHz` into `ExtractFromSpectrogram` (currently it only receives
`baseBin`). Adjust the signature accordingly.

**Option B — revert to Goertzel for the decode path**  
Replace `FillSpectrogram` + `ExtractFromSpectrogram` with `SymbolExtractor.Extract` (Goertzel).
Exact, spec-conformant. Slower but correct. Revisit the P1 optimisation only after the WAV fixture
test confirms acceptable decode rates.

---

### D4 — `freqShift % 8` wrapping corrupts LLRs when the Costas offset is non-zero
**Files**: `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (`ComputeLlrs`); `src/OpenWSFZ.Ft8/Dsp/CostasSynchroniser.cs`  
**Severity**: Medium — silently corrupts decode candidates; test suite does not catch it

**Root cause**  
`CostasSynchroniser.FindCandidates` sweeps `freqShift = 0..7` and returns candidates where the
Costas pattern score exceeds the threshold. The returned `FreqBinOffset` is fed to `ComputeLlrs`:

```csharp
float e6 = grid[s, (6 + freqShift) % 8];  // wraps for freqShift >= 2
float e7 = grid[s, (7 + freqShift) % 8];  // wraps for freqShift >= 1
```

For `freqShift = 2`, the signal's physical tones 6 and 7 lie at grid columns 8 and 9 — **outside
the 8-column grid**. The `% 8` wrap reads columns 0 and 1 instead, which contain energy from bins
2–3 tone-spacings below the signal's base frequency. All LLR terms that involve `e6` or `e7` are
corrupted.

The outer frequency sweep (6.25 Hz steps) does provide a `freqShift = 0` candidate for most real
signals, so decodes are not always lost. But the corrupt `freqShift > 0` candidates waste LDPC
iterations, and at marginal SNR the `freqShift = 0` candidate may score below the 0.45 Costas
threshold while a wrapped candidate scores above it — inverting which path is attempted.

**The test is self-referential**: `BuildPerfectCostasGrid` and `BuildSyntheticFt8Pcm` both use
the same `(pattern[i] + freqShift) % 8` wrapping. They test the code's *own behaviour*, not
whether it handles a genuine FT8 signal. They cannot catch this defect.

**Required fix**  
Widen the extracted grid from 8 to **15 columns** (`baseBin` to `baseBin + 14`), so any
`freqShift 0–7` keeps all 8 signal tones within bounds:

```csharp
// ExtractFromSpectrogram: change ToneCount → ToneCount + 7
var grid = new float[symCount, ToneCount + 7]; // 15 columns

// ComputeLlrs: no change needed — (t + freqShift) for t in 0..7, freqShift in 0..7
// gives indices 0..14, all within the wider grid.
```

Update the `CostasSynchroniser` tests to use real FT8-spec tone placement (no wrapping in the
test helper) to prevent the same self-referential defect reappearing in future tests.

---

### D5 — `FillSpectrogram` leaves stale rows for `startSample > 28 320`
**File**: `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs` — `FillSpectrogram`  
**Severity**: Low — can cause false positives at late time-sweep positions; typical signals unaffected

For `startSample > 28 320` (15 of the 52 sweep positions) the signal extends beyond the 180 000-
sample buffer, and `FillSpectrogram` cannot fill every symbol row. Rows it skips are left with data
from the previous `startSample` iteration. Those stale rows may accidentally satisfy Costas
correlation checks, producing spurious decode candidates.

**Required fix**  
Zero out the rows that cannot be filled:

```csharp
for (int sym = 0; sym < SymbolCount; sym++)
{
    int offset = startSample + sym * SamplesPerSymbol;
    if (offset + SamplesPerSymbol > pcm.Length)
    {
        // Zero any row that falls outside the buffer to prevent stale data from
        // a previous startSample iteration producing artefact Costas correlations.
        for (int bin = 0; bin < SpecBins; bin++)
            result[sym, bin] = 0f;
        continue;
    }
    // ... existing FFT code ...
}
```

---

## D6 — No end-to-end decoder test *(Critical — required before merge)*

**File**: `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs`

`DecodeAsync_WavFixture_ReturnsKnownDecodes` is permanently skipped with `Skip = "WAV fixture not
yet committed — see task 8.1"`. **This is the only test that validates the decoder against real
FT8 audio.** Defects D2–D5 were not caught by CI because the test that would catch them was never
activated.

**Required before merge**

1. Record (or download from the WSJT-X test vectors) a 15-second 12 kHz mono float-32 PCM clip
   that starts at a UTC 15-second boundary and contains at least one decodable FT8 signal at
   SNR ≥ −15 dB.
2. Commit the raw PCM as `tests/OpenWSFZ.Ft8.Tests/Fixtures/ft8-sample.raw` and a reference
   decode list as `tests/OpenWSFZ.Ft8.Tests/Fixtures/ft8-sample.ref`.
3. Remove the `Skip` attribute from `DecodeAsync_WavFixture_ReturnsKnownDecodes`.
4. Confirm the test passes in CI before raising the PR for final review.

If the test fails after applying D1–D5 fixes, the P1 optimisation (`FillSpectrogram` with
zero-padding) should be reverted to the Goertzel path (`SymbolExtractor.Extract`) which is
spec-exact.

---

## D7 — Incorrect LDPC(174,91) parity-check matrix *(found and fixed 2026-05-27)*

**File**: `src/OpenWSFZ.Ft8/Dsp/LdpcDecoder.cs`  
**Severity**: Blocker — caused 100% miss rate on all FT8 decodes

The embedded 87-row H matrix was missing column indices 91–99 and 104. A valid FT8 codeword
satisfies the TRUE 87 check equations; the corrupt matrix rejected every valid codeword → `Decode`
always returned `null`.

**Fix**: Replace with correct 83-row ft8_lib (kgoba) matrix and update `LdpcEncode` in
`TestFt8Encoder` to use the pre-computed generator matrix instead of Gaussian elimination
(the parity sub-matrix was not full-rank for the ft8_lib convention). `CheckCount` changed
87 → 83. Commit: `550acc1`.

---

## D8 — Wrong Gray-code grouping for bit 0 LLR *(found and fixed 2026-05-27)*

**File**: `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — `ComputeLlrs`  
**Severity**: Blocker — 23/174 wrong-sign LLRs prevented LDPC convergence on any real signal

`ComputeLlrs` grouped tones {0,3,4,7} as b0=0 and {1,2,5,6} as b0=1. The correct inverse
Gray table gives b0=0 for tones {0,3,5,6} and b0=1 for {1,2,4,7}. Tones 4–7 all had the
wrong b0 assignment, affecting roughly half of all data symbols.

Note: the QA review originally marked "Gray-code bit mapping in `ComputeLlrs` — Correct" but
this was not verified against the inverse Gray table. The error was unmasked only when Goertzel
extraction was used (eliminating leakage as a confounding factor). Commit: `550acc1`.

---

## D9 — Costas false positives in silent FFT bands caused O(minutes) decode time *(found and fixed 2026-05-27)*

**File**: `src/OpenWSFZ.Ft8/Dsp/CostasSynchroniser.cs` — `ComputeCostasScore`  
**Severity**: High — made the hybrid FFT+Goertzel decode path impractical (~30 min per 15-s cycle)

When all 8 spectrogram columns have energy near `log(1e-10) ≈ −23` (silent band), the
soft-match criterion `costas >= maxE - 0.1f` is trivially satisfied (all values within 0.1),
producing a "perfect" Costas score of 21/21 ≈ 0.45 threshold. Each false positive triggered
a Goertzel call (79 × 15 × 1920 = 2.27M multiply-adds), and with ~193k false detections per
cycle the total ran for tens of minutes.

**Fix**: Gate `if (maxE < -18f) continue` before the soft-match check. Real signals produce
log-energy well above −10; the noise floor sits at −23. Commit: `550acc1`.

Also in this commit: `Ft8Decoder.DecodeAsync` switched to a **hybrid FFT+Goertzel** architecture —
FFT spectrogram for fast Costas correlation sweep (~473 steps), Goertzel only for confirmed
candidates (typically single-digit hits per time offset). Fixture test: 2 s (was >5 min).

---

## Changes confirmed correct — no action required

| Item | Assessment |
|---|---|
| `ReadFully = false` on `BufferedWaveProvider` | Correct fix. Prevents the drain loop from hanging. |
| `LoggingConfig` null guard in `JsonConfigStore.Load` | Correct fix. Handles pre-p6 config files. |
| Null guard in `configStore.OnSaved` handler | Correct fix. Consistent with initial apply. |
| `logs/` added to `.gitignore` | Correct. |
| `LogRotationService` — rotation boundary calculation | Correct. All 5 unit tests pass. |
| `LoggingPipeline.Apply` — Serilog re-apply on config save | Correct. |
| p7 `audioDeviceFriendlyName` migration in config | Correct. |
| LDPC min-sum implementation | Algorithmically correct. |
| CRC-14 polynomial and bit ordering | Correct per Franke & Taylor 2019. |
| Gray-code bit mapping in `ComputeLlrs` | **Corrected in D8** — original review verdict was incorrect; inverse Gray table confirmed fix is right. |
| `CycleFramer` UTC alignment (`ComputeLeadingSamples`) | Correct. |

---

## Suggested fix order

1. **D6** — commit the WAV fixture and un-skip the test first. It will fail on the unfixed
   code and give you a concrete target to pass.
2. **D2** — all-zeros guard. Two lines of code; removes the spurious decode immediately.
3. **D3** — bin-alignment fix in `ExtractFromSpectrogram` (Option A). One-line change plus
   signature update; will improve real-signal decode rate.
4. **D4** — widen the grid to 15 columns; update the Costas tests.
5. **D1** — fix the spectrum display dBFS range. The waterfall should immediately show
   distinct FT8 signal clusters once D3 is in place.
6. **D5** — zero stale rows. Low risk, small change.

Re-run the full test suite after each step. When the WAV fixture test passes and CI is green,
re-open for review.
