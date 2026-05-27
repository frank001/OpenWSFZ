using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: LdpcDecoderTests
/// </summary>
public sealed class LdpcDecoderTests
{
    // ── CRC-14 tests ─────────────────────────────────────────────────────────

    [Fact]
    public void Crc14_KnownVector_AllZeroMessage_ProducesZeroCrc()
    {
        // Standard CRC-14 of an all-zero 77-bit message is 0:
        // feedback is always (0 >> 13) ^ 0 = 0, so the polynomial is never applied
        // and the register remains 0 throughout. This is the canonical reference
        // vector that distinguishes the correct WSJT-X algorithm from incorrect ones.
        var bits = new byte[77]; // all zero
        uint crc = Crc14.Compute(bits, 77);
        crc.Should().Be(0u,
            "standard CRC-14 of an all-zero message must be 0 per the FT8 specification");
    }

    [Fact]
    public void Crc14_RoundTrip_Verifies()
    {
        // Build a random 77-bit message, compute CRC, append it, verify.
        var rng  = new Random(123);
        var msg  = new byte[91];
        for (int i = 0; i < 77; i++) msg[i] = (byte)(rng.Next(2));

        uint crc = Crc14.Compute(msg, 77);
        // Append 14 CRC bits MSB-first.
        for (int i = 0; i < 14; i++)
            msg[77 + i] = (byte)((crc >> (13 - i)) & 1);

        bool ok = Crc14.Verify(msg, 91);
        ok.Should().BeTrue("appended CRC should verify against its own message");
    }

    [Fact]
    public void Crc14_FlippedBit_Fails()
    {
        var rng = new Random(456);
        var msg = new byte[91];
        for (int i = 0; i < 77; i++) msg[i] = (byte)(rng.Next(2));

        uint crc = Crc14.Compute(msg, 77);
        for (int i = 0; i < 14; i++)
            msg[77 + i] = (byte)((crc >> (13 - i)) & 1);

        // Flip one message bit.
        msg[10] ^= 1;

        bool ok = Crc14.Verify(msg, 91);
        ok.Should().BeFalse("flipping a message bit should invalidate the CRC");
    }

    // ── LDPC decoder tests ───────────────────────────────────────────────────

    [Fact]
    public void LdpcDecoder_StrongLlrs_ConvergesAndPassesParity()
    {
        // Build strong LLRs (large magnitude → confident bits) for a zero codeword.
        // A zero codeword (all bits = 0) always satisfies any linear parity-check code.
        var llr = new float[LdpcDecoder.CodeLength];
        for (int i = 0; i < llr.Length; i++)
            llr[i] = 10f; // strong positive → bit 0

        var result = LdpcDecoder.Decode(llr);

        result.Should().NotBeNull("strong LLRs for an all-zero codeword should converge");
        result!.Length.Should().Be(LdpcDecoder.InfoBits);
        result.Should().AllSatisfy(b => b.Should().Be(0));
    }

    [Fact]
    public void LdpcDecoder_RandomNoiseLlrs_FalsePositiveRateBelow1In1000()
    {
        // Generate 1 000 random LLR vectors; check how many pass parity + CRC.
        var rng         = new Random(789);
        int falsePasses = 0;

        for (int trial = 0; trial < 1000; trial++)
        {
            var llr = new float[LdpcDecoder.CodeLength];
            for (int i = 0; i < llr.Length; i++)
                llr[i] = (float)(rng.NextDouble() * 4.0 - 2.0); // ±2 — weak/noisy

            var result = LdpcDecoder.Decode(llr);
            if (result is not null)
            {
                // Count only those that also pass CRC-14 (91-bit block).
                // For a random 87-bit decode, build the 91-bit block and check CRC.
                // (A result that passes parity but fails CRC is the realistic false-positive.)
                var block = new byte[91];
                Array.Copy(result, block, Math.Min(result.Length, 91));
                if (Crc14.Verify(block, 91)) falsePasses++;
            }
        }

        falsePasses.Should().BeLessThan(1,
            "random noise should almost never produce a valid LDPC+CRC decode");
    }

    // ── End-to-end encode → decode round-trip ────────────────────────────────

    [Fact]
    public void LdpcEncode_GeneratorMatrix_ProducesValidCodeword()
    {
        // Encode a known FT8 message and verify all 83 parity checks pass.
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);

        codeword.Length.Should().Be(174, "LDPC(174,91) codeword must be 174 bits");

        // Verify all check equations.
        int failCount = 0;
        for (int r = 0; r < LdpcDecoder.CheckCount; r++)
        {
            int parity = 0;
            foreach (int j in LdpcDecoder.H[r])
                parity ^= codeword[j];
            if (parity != 0) failCount++;
        }
        failCount.Should().Be(0, "every check equation must be satisfied by a valid codeword");
    }

    [Fact]
    public void LdpcDecode_FromPerfectLlrs_ReturnsCorrectInfoBits()
    {
        // Build a valid codeword, convert to ideal LLRs, decode, check info bits.
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);

        // Perfect LLRs: large positive = bit 0, large negative = bit 1.
        var llr = new float[174];
        for (int i = 0; i < 174; i++)
            llr[i] = codeword[i] == 0 ? +10f : -10f;

        var decoded = LdpcDecoder.Decode(llr);

        decoded.Should().NotBeNull("perfect LLRs for a valid codeword must decode");
        decoded!.Length.Should().Be(91);
        decoded.Should().BeEquivalentTo(infoBits,
            "decoded info bits must match the original 91 info bits");
    }

    [Fact]
    public void GoertzelLlrs_SyntheticPcm_LdpcDecodesCorrectly()
    {
        // Full encode → Goertzel grid → LLR → LDPC decode.
        // Verifies the Goertzel extraction path (used by Ft8Decoder.DecodeAsync) produces
        // LLRs with correct signs — the previous zero-padded FFT path had 23/174 wrong-sign
        // LLRs due to spectral leakage (FT8 tones align exactly on 1920-pt bins, not 2048-pt).
        const double baseFreqHz = 1500.0;
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: 0);

        // Goertzel extraction — exact frequencies, no leakage.
        float[,] grid = SymbolExtractor.Extract(pcm, startSample: 0, baseFreqHz);

        // Find Costas — expects freqShift=0.
        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.45f);
        candidates.Should().NotBeEmpty("Costas sync must detect the signal");
        int freqShift = candidates[0].FreqBinOffset;

        // Build LLRs from the grid (mirror of Ft8Decoder.ComputeLlrs).
        var dataSym = new List<int>();
        for (int s = 0; s < 79; s++)
        {
            bool isCostas = (s < 7) || (s >= 36 && s < 43) || (s >= 72 && s < 79);
            if (!isCostas) dataSym.Add(s);
        }
        dataSym.Should().HaveCount(58);

        var llr = new float[174];
        int bitIdx = 0;
        for (int di = 0; di < 58; di++)
        {
            int s = dataSym[di];
            float e0 = grid[s, freqShift + 0], e1 = grid[s, freqShift + 1],
                  e2 = grid[s, freqShift + 2], e3 = grid[s, freqShift + 3],
                  e4 = grid[s, freqShift + 4], e5 = grid[s, freqShift + 5],
                  e6 = grid[s, freqShift + 6], e7 = grid[s, freqShift + 7];

            static float LSE(float a, float b, float c, float d)
            {
                float m = MathF.Max(MathF.Max(a, b), MathF.Max(c, d));
                return m + MathF.Log(MathF.Exp(a-m)+MathF.Exp(b-m)+MathF.Exp(c-m)+MathF.Exp(d-m));
            }

            llr[bitIdx++] = LSE(e0,e1,e2,e3) - LSE(e4,e5,e6,e7);  // bit 2: b2=0→tones 0-3
            llr[bitIdx++] = LSE(e0,e1,e6,e7) - LSE(e2,e3,e4,e5);  // bit 1: b1=0→tones 0,1,6,7
            llr[bitIdx++] = LSE(e0,e3,e5,e6) - LSE(e1,e2,e4,e7);  // bit 0: b0=0→tones 0,3,5,6
        }

        // Verify LLR sign quality before asserting decode.
        byte[] expectedCw = TestFt8Encoder.LdpcEncode(infoBits);
        int wrongSign = 0;
        for (int i = 0; i < 174; i++)
            if ((llr[i] >= 0 ? 0 : 1) != expectedCw[i]) wrongSign++;
        wrongSign.Should().Be(0, $"Goertzel LLRs must have correct signs for all 174 bits; got {wrongSign} wrong");

        // LDPC decode.
        var decoded = LdpcDecoder.Decode(llr);
        decoded.Should().NotBeNull("Goertzel LLRs for a valid codeword must converge in LDPC");

        // CRC-14 must pass.
        bool crcOk = Crc14.Verify(decoded!, 91);
        crcOk.Should().BeTrue("decoded info bits must pass CRC-14");
    }

    [Fact]
    public void GoertzelGrid_SyntheticPcm_MaxEnergyAtCorrectTone()
    {
        // Verify the Goertzel grid has max energy at the correct tone for every data symbol.
        // With exact-frequency Goertzel there should be zero wrong-tone readings on a
        // clean synthetic signal (no noise, no inter-symbol interference).
        const double baseFreqHz = 1500.0;
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: 0);

        float[,] grid = SymbolExtractor.Extract(pcm, startSample: 0, baseFreqHz);

        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.45f);
        candidates.Should().NotBeEmpty("Costas sync must find the signal");
        int freqShift = candidates[0].FreqBinOffset;

        var dataSym = new List<int>();
        for (int s = 0; s < 79; s++)
        {
            bool isCostas = (s < 7) || (s >= 36 && s < 43) || (s >= 72 && s < 79);
            if (!isCostas) dataSym.Add(s);
        }

        int wrongTone = 0;
        for (int di = 0; di < dataSym.Count; di++)
        {
            int s   = dataSym[di];
            int sym = symbols[s];
            int maxTone = 0;
            for (int t = 1; t < 8; t++)
                if (grid[s, freqShift + t] > grid[s, freqShift + maxTone]) maxTone = t;
            if (maxTone != sym) wrongTone++;
        }

        wrongTone.Should().Be(0,
            "Goertzel extraction on a clean synthetic signal must have max energy at the correct tone for every data symbol");
    }

    [Fact]
    public void CostasSync_SyntheticPcm_FindsCandidateAtBaseFrequency()
    {
        // Generate a synthetic FT8 frame at 1500 Hz, run Goertzel extraction, check Costas is found.
        const double baseFreqHz = 1500.0;
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: 0);

        // Goertzel extraction at exactly 1500 Hz.
        float[,] grid = SymbolExtractor.Extract(pcm, startSample: 0, baseFreqHz);

        // Check Costas at symbol 0 (freqShift=0): max energy should be at the Costas tone.
        ReadOnlySpan<int> costas = [3, 1, 4, 0, 6, 5, 2];
        for (int i = 0; i < 7; i++)
        {
            int expectedTone = costas[i];
            float costasE = grid[i, expectedTone];
            float maxE    = float.MinValue;
            for (int t = 0; t < 8; t++) if (grid[i, t] > maxE) maxE = grid[i, t];
            costasE.Should().BeGreaterThanOrEqualTo(maxE - 0.5f,
                $"Costas symbol {i}: expected max energy at tone {expectedTone}, got {costasE:F3} vs max {maxE:F3}");
        }

        // Run full FindCandidates.
        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.45f);
        candidates.Should().NotBeEmpty("the Costas synchroniser must find the signal at freqShift=0");
        candidates[0].FreqBinOffset.Should().Be(0, "no sub-tone offset for baseFreqHz-aligned signal");
        candidates[0].Score.Should().BeGreaterThan(0.8f, "clean synthetic signal should score > 0.8");
    }
}
