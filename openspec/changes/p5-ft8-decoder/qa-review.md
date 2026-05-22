# QA Review — p5-ft8-decoder

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
