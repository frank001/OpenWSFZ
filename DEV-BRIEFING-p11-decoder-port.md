# Developer Briefing — p11 Decoder Port

**Issued by:** QA Engineer  
**Date:** 2026-05-29  
**Branch target:** `feat/p11-decoder-port` (branch from `main`)  
**Prerequisites:** `main` is clean; the p10 merge is in place; the G6 gate is wired and RED

---

## Context

The FT8 decoder produces **zero real decodes** from on-air signals (0 of 887 WSJT-X decodes recovered across 42 cycles) and **281 false positives** — messages with impossible signal reports (`+4011`, `+2159`) and structurally invalid callsigns (`07WNYS`, `0H21AM`).

The architect's recovery plan identified two independent problems:

| Problem | Root cause | Already fixed? |
|---|---|---|
| CRC computed over 77 bits instead of 82 | `Crc14.Verify(91)` vs `Crc14.VerifyFt8()` | ✅ D14 — `VerifyFt8` is in `main` |
| False positives displayed with impossible content | No message content validation after LDPC+CRC | ❌ Part 1 below |
| Zero real decodes | DSP produces random LLRs from real signals due to FFT spectral leakage | ❌ Part 2 below |

Deliver **Part 1 first** (small, isolated). Deliver **Part 2** on the same branch immediately after; both ship together as `p11`.

---

## Part 1 — Immediate fix: message content validation

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Effort:** ~40 lines of code + tests  
**Risk:** None to DSP; only adds filters that real FT8 messages always pass

### Why bogus messages slip through CRC

CRC-14 has a false-positive rate of 1 in 16 384 per candidate. The LDPC decoder produces occasional convergence to arbitrary codewords (because it receives random LLRs from the broken DSP). With ~280 convergences across 42 cycles, roughly 17 accidentally pass CRC-14 over 82 bits — and because the message content is never checked, all are displayed verbatim.

Every false positive examined has **at least one** of the following:

- **Impossible SNR report**: `+4011`, `+2159`, `+1937` — the FT8 standard encodes SNR reports as `val − 35 dB` where `val ∈ [1, 60]`, covering −34 to +25 dB. Values in the corpus false positives have `val` in the range 1300–4100 — three orders of magnitude above the valid ceiling.

- **Invalid callsign structure**: In the FT8 base-37 callsign encoding the 6-character padded form always has a **digit at position 2 (0-indexed)** and **letters or space at positions 3–5**. `07WNYS` has a letter at position 2 (`'W'`); `0H21AM` has a digit at position 3 (`'1'`). No valid amateur radio callsign can arise from a correctly decoded Type 1 message that fails these two checks.

### Changes required

#### 1a. Add two private validators to `MessageUnpacker`

Place these after the existing `ReadBits` helper:

```csharp
/// <summary>
/// Returns true if <paramref name="packed"/> decodes to a valid FT8 callsign
/// per the base-37 encoding invariant (Franke &amp; Taylor 2019 §4.1):
/// position 2 of the 6-character padded form must be a digit ('0'–'9') and
/// positions 3–5 must be letters (A–Z) or space.
/// Special packed values ≤ 2 (DE, QRZ, CQ) are always valid.
/// </summary>
private static bool IsValidCallsign28(ulong packed)
{
    if (packed <= 2) return true; // DE / QRZ / CQ

    ulong p = packed - 3;
    Span<char> chars = stackalloc char[6];
    for (int i = 5; i >= 0; i--)
    {
        chars[i] = CallAlphabet[(int)(p % 37)];
        p /= 37;
    }

    // Position 2 must be a digit.
    if (!char.IsDigit(chars[2])) return false;

    // Positions 3–5 must not be digits.
    for (int i = 3; i <= 5; i++)
        if (char.IsDigit(chars[i])) return false;

    return true;
}

/// <summary>
/// Returns true if the 15-bit extra field is within the documented FT8 encoding range.
/// For signal reports (bit 14 = 1): valid val ∈ [1, 60] (RRR / RR73 / 73 / SNR −34 to +25 dB).
/// For grid squares (bit 14 = 0): valid val &lt; 32 724 (standard grids + R-prefix contest range).
/// </summary>
private static bool IsValidExtra15(ulong packed)
{
    bool isReport = (packed & 0x4000UL) != 0;
    ulong val     = packed & 0x3FFFUL;

    return isReport
        ? val >= 1 && val <= 60   // covers RRR/RR73/73 and SNR −34 to +25 dB
        : val < 32_724;           // standard 4-char grids + R-prefix contest range
}
```

#### 1b. Call the validators in `UnpackType1Or2OrNull`

`TryUnpack` already calls `UnpackType1Or2OrNull`, which already returns `null` for unsupported sub-types. Extend it to return `null` for invalid content before producing any string:

```csharp
private static string? UnpackType1Or2OrNull(ReadOnlySpan<byte> bits)
{
    int n3 = (bits[71] << 2) | (bits[72] << 1) | bits[73];
    if (n3 > 3) return null;

    ulong c1 = ReadBits(bits, 0,  28);
    ulong c2 = ReadBits(bits, 28, 28);
    ulong rg = ReadBits(bits, 56, 15);

    if (!IsValidCallsign28(c1)) return null;
    if (!IsValidCallsign28(c2)) return null;
    if (!IsValidExtra15(rg))    return null;

    return UnpackType1(bits);
}
```

`Ft8Decoder` already does `if (msg is null) continue` after `TryUnpack`, so validated-out messages are silently discarded with no further change.

#### 1c. Tests required

Add to `tests/OpenWSFZ.Ft8.Tests/MessageUnpackerTests.cs` (or create it), citing **FR-029** in every display name:

| Test | Expected result |
|---|---|
| Valid Type 1 message with real callsigns and SNR in [−24, +24] | Returns decoded string |
| Extra field val = 2194 (SNR "+2159") with `isReport=true` | Returns `null` |
| Extra field val = 4052 (SNR "+4017") with `isReport=true` | Returns `null` |
| Callsign packed value that decodes to `07WNYS` (letter at position 2) | Returns `null` |
| Callsign packed value that decodes to `0H21AM` (digit at position 3) | Returns `null` |
| Special packed values 0, 1, 2 (DE, QRZ, CQ) | Returns `null` from callsign validation — `false` |
| Valid grid square `FN13` (val = 5530) | Passes extra validation |
| Grid val ≥ 32 724 | Returns `null` |
| Type 1 message where callsign 1 is valid but callsign 2 is bogus | Returns `null` |

Run the harness locally after Part 1 to confirm the false-positive count drops materially. Update `findings.md` with the new count.

---

## Part 2 — p11-decoder-port: replace the DSP core

### The problem in one sentence

`FillSpectrogram` uses a **2048-point zero-padded FFT** on 1920-sample windows. The FFT bin spacing is 12 000 / 2 048 ≈ **5.859 Hz**, but FT8 tone spacing is **6.25 Hz exactly**. Each tone falls *between* two bins, so its energy is split across both — spectral leakage. Every symbol energy estimate is wrong by up to 3 dB, the LLRs fed to LDPC are unreliable, and LDPC never converges to the correct codeword.

`kgoba/ft8_lib` avoids this entirely by using a **1920-point DFT** (bin spacing = 12 000 / 1920 = **6.25 Hz exactly**). Each FT8 tone falls on a single bin with no leakage.

### What stays

Do **not** touch these; they are correct:

| Component | File | Status |
|---|---|---|
| Decoder interface | `Ft8Decoder.cs` public API | Keep as-is |
| Cycle framing | `CycleFramer.cs` | Keep |
| LDPC min-sum decoder | `Dsp/LdpcDecoder.cs` | Keep (the H matrix, algorithm, and `CountInitialParityFailures` are all correct) |
| CRC verification | `Dsp/Crc14.cs` — `VerifyFt8` | Keep |
| Message unpacking | `Dsp/MessageUnpacker.cs` | Keep (+ Part 1 validation) |
| Gray code LLR mapping | `Ft8Decoder.ComputeLlrs` | Keep (D13 fix is correct) |
| ALL.TXT writer | `Daemon/AllTxtWriter.cs` | Keep |
| Audio pipeline | `CycleFramer`, `Program.cs` | Keep |

### What is replaced

| Component | File | Action |
|---|---|---|
| Spectrogram computation | `Dsp/SymbolExtractor.FillSpectrogram` / `ComputeSpectrogram` | Replace FFT with 1920-point DFT (see §P2.1) |
| FFT infrastructure used only by spectrogram | `Dsp/FftCompute.cs` | Remove if no longer referenced; otherwise leave |
| Spectrogram extraction | `Dsp/SymbolExtractor.ExtractFromSpectrogram` | Simplify — with exact bins, just index directly (see §P2.2) |
| Outer decode loop | `Ft8Decoder.DecodeAsync` | Revise the spectrogram call (see §P2.3) |

`CostasSynchroniser`, `GoertzelDetector`, and the Goertzel extraction path (`SymbolExtractor.Extract`) are **kept**; the Goertzel path is already used for LLR extraction and produces correct energies. The only change is to also use exact-frequency energies for candidate detection.

---

### P2.1 — Replace `FillSpectrogram` with a 1920-point exact-DFT spectrogram

**Reference:** `kgoba/ft8_lib` — `ft8/decode.c`, function `get_spectrum` / the spectrogram loop.

The ft8_lib approach: compute the DFT of each 1920-sample symbol window at the **exact** 6.25 Hz bins covering the decode bandwidth (50 Hz to ~3 100 Hz → bins 8 to 496). Since 1920 is not a power of 2, use one of the following strategies (choose one):

#### Option A — Bluestein chirp-Z FFT (recommended)

The Bluestein algorithm computes an N-point DFT for arbitrary N using a `2^k`-point FFT as a subroutine, where `2^k ≥ 2N − 1`. For N = 1920: `2^k ≥ 3 839` → use a **4096-point FFT** (already available via `FftCompute`).

Steps:
1. Pre-compute the chirp sequence `w[n] = exp(−jπn²/N)` for n = 0 … N−1 (done once at startup).
2. For each symbol window `x[n]`:
   - Multiply: `a[n] = x[n] · w*[n]`
   - Zero-pad `a` to length 4096
   - Convolve with the chirp filter (FFT → multiply → IFFT in the 4096-point domain)
   - Multiply output by `w*[n]` to obtain the 1920-point DFT
3. Extract squared magnitudes for bins 8 to 496 (50 Hz to 3 100 Hz).

This is the cleanest approach and reuses the existing `FftCompute.Fft`.

#### Option B — Mixed-radix FFT at size 1920

1920 = 2^7 × 3 × 5. A split-radix or Cooley–Tukey implementation for this factorisation is available as open source (e.g. `kiss_fft` mixed-radix in C, trivially translated). This avoids the Bluestein overhead but requires implementing mixed-radix twiddle factor computation.

#### Option C — Goertzel bank (simplest to implement, slower)

For candidate detection only — not LLR extraction (that already uses Goertzel correctly). Compute Goertzel at the ~60 discrete frequencies needed for the outer frequency sweep (50 Hz to 3 000 Hz at 50 Hz steps = 59 frequencies × 15 tones = 885 Goertzel evaluations per symbol × 79 symbols per time position). At 1920 samples per Goertzel this is ~135 M multiply-adds per time position × 102 positions ≈ 14 billion operations per cycle. This is too slow unless heavily parallelised; use Option A or B instead.

**New method signature** (replaces `FillSpectrogram`):

```csharp
/// <summary>
/// Fills <paramref name="result"/> with a 1920-point exact-DFT spectrogram
/// for the 79 symbol windows starting at <paramref name="startSample"/>.
/// Bin spacing = 12 000 / 1920 = 6.25 Hz; each FT8 tone falls on exactly
/// one bin with no spectral leakage.
/// </summary>
/// <param name="result">
/// Pre-allocated float[SymbolCount, ExactBins] where ExactBins = 960 (half of 1920).
/// </param>
internal static void FillSpectrogramExact(
    ReadOnlySpan<float> pcm, int startSample, float[,] result)
```

Update `SpecBins` from 1024 to 960 (or introduce `ExactSpecBins = SamplesPerSymbol / 2 = 960`).

---

### P2.2 — Simplify `ExtractFromSpectrogram`

With exact 6.25 Hz bins, each FT8 tone at `baseHz + c × 6.25 Hz` falls on **exactly** bin `round((baseHz + c × 6.25) × 1920 / 12000) = round((baseHz + c × 6.25) / 6.25)`. No rounding error, no leakage correction needed.

```csharp
internal static float[,] ExtractFromSpectrogram(float[,] spectrogram, double baseHz)
{
    int symCount = spectrogram.GetLength(0); // 79
    int specBins = spectrogram.GetLength(1); // 960
    var grid     = new float[symCount, GridWidth]; // 79 × 15

    for (int sym = 0; sym < symCount; sym++)
    for (int col = 0; col < GridWidth; col++)
    {
        // Exact bin — no rounding error with the 1920-point DFT.
        int   bin    = (int)Math.Round((baseHz + col * ToneSpacingHz) / ToneSpacingHz);
        float energy = (uint)bin < (uint)specBins ? spectrogram[sym, bin] : 0f;
        grid[sym, col] = MathF.Log(energy + 1e-10f);
    }

    return grid;
}
```

Remove the D3 note; it is no longer relevant.

---

### P2.3 — Update `Ft8Decoder.DecodeAsync`

The outer parallel loop structure, time sweep, frequency sweep, Costas scoring, and LLR computation are all correct. The only change is the spectrogram call:

```csharp
// Before:
SymbolExtractor.FillSpectrogram(pcm, startSample, spectrogram);

// After:
SymbolExtractor.FillSpectrogramExact(pcm, startSample, spectrogram);
```

And the pre-allocated buffer dimensions change from `float[SymbolCount, SpecBins]` (79 × 1024) to `float[SymbolCount, ExactSpecBins]` (79 × 960).

No other change to `Ft8Decoder.cs` is required.

---

### P2.4 — ft8_lib source reference

Clone `https://github.com/kgoba/ft8_lib` at the current `main` HEAD. The relevant files are:

| ft8_lib file | What it contains | Mapped to |
|---|---|---|
| `ft8/decode.c` | Top-level decode loop, spectrogram, LLR extraction | `Ft8Decoder.cs`, `SymbolExtractor.cs` |
| `ft8/decode.h` | Public API | `Ft8Decoder.cs` interface |
| `ft8/crc.c` | CRC-14 over 82 bits | `Dsp/Crc14.cs` — already ported correctly |
| `ft8/ldpc.c` | Min-sum belief propagation | `Dsp/LdpcDecoder.cs` — already ported correctly |
| `ft8/unpack.c` | Message unpacking | `Dsp/MessageUnpacker.cs` — already ported, Part 1 adds validation |
| `ft8/constants.c` | H matrix, Gray map, Costas pattern | `Dsp/LdpcDecoder.cs`, `Dsp/CostasSynchroniser.cs` — already correct |

**Focus exclusively on `ft8/decode.c`** — specifically the `get_spectrum` / `compute_wf` function that builds the spectrogram using the 1920-point DFT, and the `ft8_find_sync` candidate-detection loop. Everything else is already correctly ported.

The critical function to understand and translate is whichever function in ft8_lib computes:
```c
// for each symbol window s and each frequency bin f:
wf[s][f] = log(|DFT(window_s, f)|^2 + epsilon)
```
where the DFT is at 6.25 Hz resolution. That is the sole missing piece.

---

### P2.5 — Validation gate (non-negotiable)

The G6 `RealSignalFixtureTests` are the acceptance criterion. The port is **done** when:

1. `dotnet test -c Release` passes with `Failed: 0` — specifically, all three G6 fixture tests must go **green** (i.e. the decoder recovers the synthetic fixture answer-key messages, e.g. `CQ Q1ABC FN42`, `Q1ABC Q9XYZ -10`, from the committed WAVs).
2. No existing test regresses.
3. Build: 0 errors, 0 warnings.

Run the replay harness locally against the full 42-WAV corpus and report the new recovery rate in `findings.md`. Target: ≥ 80% recovery (WSJT-X typically decodes the same signals across implementations when the DFT is correct; 100% is not required because WSJT-X uses additional techniques such as iterative subtraction that we are not porting in Phase 2A).

---

### P2.6 — What to preserve from the current DSP

| Decision | Keep | Rationale |
|---|---|---|
| D4 — GridWidth = 15 columns | ✅ | Allows freqShift 0–7 without wrapping |
| D11 — Half-symbol time sweep (step = 960) | ✅ | Correct — D11 analysis was sound |
| D12 — 50 Hz outer frequency step | ✅ | Correct |
| D13 — kFT8_Gray_map Gray code | ✅ | Correct |
| D14 — 82-bit CRC (`VerifyFt8`) | ✅ | Correct |
| D18 — Softmax Costas scoring | ✅ | Correct — keep the formula; it changes only whether a given spectrum triggers a Costas hit, not the energies themselves |
| D3 — FFT bin-rounding correction | ❌ Remove | Unnecessary with exact-DFT bins |
| 2048-point zero-padded FFT spectrogram | ❌ Replace | The root cause of 0% recovery |

---

## Commit strategy

```
feat(p11): Part 1 — MessageUnpacker content validation (callsign + report range)
test(p11): Part 1 — MessageUnpackerTests for invalid callsign and out-of-range report
feat(p11): Part 2 — 1920-point exact-DFT spectrogram (Bluestein / mixed-radix)
test(p11): Part 2 — SymbolExtractorTests exact bin alignment
```

Do not combine Part 1 and Part 2 in a single commit. QA will re-review after Part 1 is submitted; Part 2 follows once Part 1 is approved.

---

## Definition of done

- [ ] Part 1: `MessageUnpacker.TryUnpack` returns `null` for impossible SNR reports and invalid callsign structure; tests green
- [ ] Part 1: Harness re-run shows false positives materially reduced (target: 0); `findings.md` updated
- [ ] Part 2: `FillSpectrogramExact` implemented using 1920-point DFT; 2048-point path removed
- [ ] Part 2: G6 gate is **GREEN** — all three `RealSignalFixtureTests` pass
- [ ] Part 2: Full 42-WAV harness recovery rate ≥ 80% recorded in `findings.md`
- [ ] Part 2: `dotnet build -c Release` → 0 errors, 0 warnings
- [ ] Part 2: `dotnet test -c Release` → 0 failures (G6 green + all existing tests pass)
- [ ] QA re-review passed; branch merged to `main`
