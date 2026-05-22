using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Dsp;

namespace OpenWSFZ.Ft8;

/// <summary>
/// Cleanroom FT8 decoder implementing <see cref="IModeDecoder"/>.
///
/// Pipeline per cycle:
///   1. Sweep candidate base frequencies across the audio passband (50–3000 Hz,
///      steps of one tone width = 6.25 Hz).
///   2. For each candidate frequency, extract the 79×8 log-energy grid via
///      <see cref="SymbolExtractor"/>.
///   3. Run <see cref="CostasSynchroniser"/> to find sync candidates in the grid.
///   4. For each sync candidate, derive LLRs from the log-energy grid, run
///      <see cref="LdpcDecoder"/>, verify with <see cref="Crc14"/>, unpack with
///      <see cref="MessageUnpacker"/>.
///   5. De-duplicate messages; return the unique set as <see cref="DecodeResult"/> records.
/// </summary>
public sealed class Ft8Decoder : IModeDecoder
{
    private const int    SampleRate   = SymbolExtractor.SampleRate;      // 12 000 Hz
    private const double ToneSpacing  = SymbolExtractor.ToneSpacingHz;  // 6.25 Hz
    private const int    SymbolCount  = SymbolExtractor.SymbolCount;     // 79
    private const int    InfoBits     = LdpcDecoder.InfoBits;            // 91
    private const int    MsgBits      = 77;
    private const int    CrcBits      = 14;
    private const int    CodeLength   = LdpcDecoder.CodeLength;          // 174

    // Frequency sweep parameters.
    private const double MinFreqHz    = 50.0;
    private const double MaxFreqHz    = 3000.0;

    // Costas sync threshold (tune for sensitivity vs. false-alarm rate).
    private const float  SyncThreshold = 0.45f;

    private readonly IClock _clock;

    public Ft8Decoder(IClock clock) => _clock = clock;

    /// <inheritdoc/>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default)
    {
        ct.ThrowIfCancellationRequested();

        // Guard: if the signal is below the noise floor, there is nothing to decode.
        // This also prevents the all-zero codeword from being accepted as a valid message.
        if (ComputeRms(pcm) < 1e-6f)
            return Task.FromResult<IReadOnlyList<DecodeResult>>([]);

        // Capture cycle-start time before the (potentially slow) decode.
        var cycleStart = AlignToCycleStart(_clock.UtcNow);
        string timeStr = cycleStart.ToString("HH:mm:ss");

        var results = new List<DecodeResult>();
        var seen    = new HashSet<string>(StringComparer.Ordinal);

        // Sweep base frequencies in steps of one tone spacing.
        for (double baseHz = MinFreqHz; baseHz <= MaxFreqHz; baseHz += ToneSpacing)
        {
            ct.ThrowIfCancellationRequested();

            var grid       = SymbolExtractor.Extract(pcm, startSample: 0, baseFrequencyHz: baseHz);
            var candidates = CostasSynchroniser.FindCandidates(grid, SyncThreshold);

            foreach (var cand in candidates)
            {
                ct.ThrowIfCancellationRequested();

                double actualBase = baseHz + cand.FreqBinOffset * ToneSpacing;
                int    freqHz     = (int)Math.Round(actualBase + 3 * ToneSpacing); // centre tone

                // Derive soft LLRs from the energy grid.
                var llr = ComputeLlrs(grid, cand.FreqBinOffset);

                // LDPC decode.
                var decoded = LdpcDecoder.Decode(llr);
                if (decoded is null) continue;

                // CRC-14 check: decoded is exactly 91 bytes (77 msg bits + 14 CRC bits).
                // bits[0..76]  = message payload
                // bits[77..90] = appended CRC-14
                bool crcOk = Crc14.Verify(decoded, 91);
                if (!crcOk) continue;

                // Unpack the 77-bit message payload.
                var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
                string msg  = MessageUnpacker.Unpack(msgBits);

                // De-duplicate.
                if (!seen.Add(msg)) continue;

                // Estimate SNR: peak log-energy minus noise floor estimate.
                float snrEst = EstimateSnr(grid);

                results.Add(new DecodeResult(
                    Time:    timeStr,
                    Snr:     (int)Math.Round(snrEst),
                    Dt:      0.0,      // timing offset — requires sub-symbol sync (future work)
                    FreqHz:  freqHz,
                    Message: msg));
            }
        }

        return Task.FromResult<IReadOnlyList<DecodeResult>>(results);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Derives 174 LLRs from the 79×8 log-energy grid for the given frequency shift.
    /// For each of the 79 data symbol positions, the LLR for each of the 3 bits encoded
    /// by the 8-FSK symbol is the log-ratio of the energy at the '1' tone vs the '0' tone.
    ///
    /// In FT8 the 79 symbols carry: 21 Costas (known) + 58 data symbols → 174 code bits.
    /// </summary>
    private static float[] ComputeLlrs(float[,] grid, int freqShift)
    {
        // Data symbol positions: all 79 positions minus the 21 Costas symbols.
        // Costas positions: 0-6, 36-42, 72-78 (3 × 7 = 21 symbols).
        var dataSym = new List<int>(58);
        for (int s = 0; s < SymbolCount; s++)
        {
            bool isCostas = (s < 7) || (s >= 36 && s < 43) || (s >= 72 && s < 79);
            if (!isCostas) dataSym.Add(s);
        }

        var llr = new float[CodeLength];
        int bitIdx = 0;

        for (int di = 0; di < dataSym.Count && bitIdx + 2 < CodeLength; di++)
        {
            int s = dataSym[di];

            // Log-energies for the 8 tones at this symbol.
            float e0 = grid[s, (0 + freqShift) % 8];
            float e1 = grid[s, (1 + freqShift) % 8];
            float e2 = grid[s, (2 + freqShift) % 8];
            float e3 = grid[s, (3 + freqShift) % 8];
            float e4 = grid[s, (4 + freqShift) % 8];
            float e5 = grid[s, (5 + freqShift) % 8];
            float e6 = grid[s, (6 + freqShift) % 8];
            float e7 = grid[s, (7 + freqShift) % 8];

            // 3-bit Gray code: bit2 (MSB), bit1, bit0 (LSB).
            // Sum log-energies for symbols where bit=0 vs bit=1.
            // Tone encoding: tone t encodes Gray(t).
            // Gray codes: 0=000, 1=001, 2=011, 3=010, 4=110, 5=111, 6=101, 7=100.
            // Bit 2 (MSB) = 0 for tones 0-3, 1 for tones 4-7.
            float b2_0 = LogSumExp(e0, e1, e2, e3);
            float b2_1 = LogSumExp(e4, e5, e6, e7);

            // Bit 1 = 0 for tones 0-1,6-7; 1 for tones 2-5.
            float b1_0 = LogSumExp(e0, e1, e6, e7);
            float b1_1 = LogSumExp(e2, e3, e4, e5);

            // Bit 0 (LSB) = 0 for tones 0,3,4,7; 1 for tones 1,2,5,6.
            float b0_0 = LogSumExp(e0, e3, e4, e7);
            float b0_1 = LogSumExp(e1, e2, e5, e6);

            // LLR positive → bit=0.
            llr[bitIdx++] = b2_0 - b2_1;
            llr[bitIdx++] = b1_0 - b1_1;
            llr[bitIdx++] = b0_0 - b0_1;
        }

        return llr;
    }

    private static float LogSumExp(float a, float b, float c, float d)
    {
        float maxV = MathF.Max(MathF.Max(a, b), MathF.Max(c, d));
        return maxV + MathF.Log(
            MathF.Exp(a - maxV) + MathF.Exp(b - maxV) +
            MathF.Exp(c - maxV) + MathF.Exp(d - maxV));
    }

    private static float EstimateSnr(float[,] grid)
    {
        // Simple estimate: mean peak log-energy of data symbols minus mean of off-tones.
        float peakSum = 0f, noiseSum = 0f;
        int   count   = 0;

        for (int s = 0; s < SymbolCount; s++)
        {
            float max = float.MinValue, sum = 0f;
            for (int t = 0; t < 8; t++)
            {
                float e = grid[s, t];
                if (e > max) max = e;
                sum += e;
            }
            peakSum  += max;
            noiseSum += (sum - max) / 7f;
            count++;
        }

        return count == 0 ? 0f : (peakSum - noiseSum) / count;
    }

    private static float ComputeRms(float[] pcm)
    {
        if (pcm.Length == 0) return 0f;
        double sum = 0.0;
        foreach (float s in pcm) sum += s * s;
        return (float)Math.Sqrt(sum / pcm.Length);
    }

    private static DateTime AlignToCycleStart(DateTime utc)
    {
        // FT8 cycles start at even 15-second boundaries.
        int totalSeconds = utc.Second + utc.Minute * 60;
        int aligned      = (totalSeconds / 15) * 15;
        int deltaSeconds = totalSeconds - aligned;
        return utc.AddSeconds(-deltaSeconds).AddMilliseconds(-utc.Millisecond);
    }
}
