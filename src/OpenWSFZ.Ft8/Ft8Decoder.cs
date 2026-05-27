using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Dsp;

namespace OpenWSFZ.Ft8;

/// <summary>
/// Cleanroom FT8 decoder implementing <see cref="IModeDecoder"/>.
///
/// Pipeline per cycle (hybrid FFT + Goertzel):
///   1. For each symbol-aligned time offset, compute a 79 × 1 024 FFT spectrogram
///      once via <see cref="SymbolExtractor.FillSpectrogram"/>.
///   2. Sweep candidate base frequencies (50–3000 Hz, steps of 6.25 Hz).
///      For each step, extract a 79 × 15 log-energy grid from the spectrogram
///      (<see cref="SymbolExtractor.ExtractFromSpectrogram"/>) and run
///      <see cref="CostasSynchroniser.FindCandidates"/> to find Costas sync hits.
///   3. For each Costas candidate, recompute the 79 × 15 grid via Goertzel
///      (<see cref="SymbolExtractor.Extract"/>) at the exact tone frequencies.
///      Goertzel eliminates the spectral leakage that the zero-padded FFT path
///      introduces (FT8 tones align on 1920-pt DFT bins, not 2048-pt bins).
///   4. Derive 174 soft LLRs from the Goertzel grid, run <see cref="LdpcDecoder"/>,
///      verify with <see cref="Crc14"/>, unpack with <see cref="MessageUnpacker"/>.
///   5. De-duplicate messages; return the unique set as <see cref="DecodeResult"/> records.
/// </summary>
public sealed class Ft8Decoder : IModeDecoder
{
    private const int    SampleRate      = SymbolExtractor.SampleRate;       // 12 000 Hz
    private const double ToneSpacing    = SymbolExtractor.ToneSpacingHz;   // 6.25 Hz
    private const int    SymbolCount    = SymbolExtractor.SymbolCount;      // 79
    private const int    SamplesPerSymbol = SymbolExtractor.SamplesPerSymbol; // 1 920
    private const int    InfoBits     = LdpcDecoder.InfoBits;            // 91
    private const int    MsgBits      = 77;
    private const int    CrcBits      = 14;
    private const int    CodeLength   = LdpcDecoder.CodeLength;          // 174
    private const int    SpecBins     = SymbolExtractor.SpecBins;        // 1 024

    // Frequency sweep parameters.
    private const double MinFreqHz    = 50.0;
    private const double MaxFreqHz    = 3000.0;

    // Costas sync threshold (tune for sensitivity vs. false-alarm rate).
    private const float  SyncThreshold = 0.45f;

    // Time-domain sweep: maximum start sample such that the first two Costas arrays
    // (positions 0–6 and 36–42) still fit fully in the buffer.
    // Second Costas array occupies symbols 36–42 → last sample index = (42+1)×1920 − 1 = 82 559.
    // Signals starting beyond this offset have only one Costas array present → score ≤ 7/21 = 0.33,
    // below SyncThreshold, so sweeping further is futile without lowering the threshold.
    private const int SecondCostasEnd = (42 + 1) * SamplesPerSymbol; // 82 560

    private readonly IClock              _clock;
    private readonly ILogger<Ft8Decoder>? _logger;

    // Pre-allocated spectrogram buffer — 79 × 1 024 floats ≈ 316 KB.
    // Allocated once at construction to avoid LOH allocations on every decode cycle.
    // Safe to share across DecodeAsync invocations: CycleFramer emits windows serially
    // (one at a time) so DecodeAsync is never called concurrently on the same instance.
    private readonly float[,] _spectrogram = new float[SymbolCount, SpecBins];

    public Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger = null)
    {
        _clock  = clock;
        _logger = logger;
    }

    /// <inheritdoc/>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default)
    {
        ct.ThrowIfCancellationRequested();

        // Guard: if the signal is below the noise floor, there is nothing to decode.
        // This also prevents the all-zero codeword from being accepted as a valid message.
        var rms = ComputeRms(pcm);
        if (rms < 1e-6f)
        {
            _logger?.LogInformation("Cycle skipped — RMS {Rms:E3} is below silence guard (threshold 1e-6).", rms);
            return Task.FromResult<IReadOnlyList<DecodeResult>>([]);
        }

        // Capture cycle-start time before the (potentially slow) decode.
        var cycleStart = AlignToCycleStart(_clock.UtcNow);
        string timeStr = cycleStart.ToString("HH:mm:ss");

        _logger?.LogDebug(
            "Starting decode for cycle {Time}; pcm = {Samples} samples, RMS = {Rms:E3}.",
            timeStr, pcm.Length, rms);

        var results = new List<DecodeResult>();
        var seen    = new HashSet<string>(StringComparer.Ordinal);

        // Time-domain sweep: try each symbol-aligned start position from 0 up to the
        // latest offset where the first two Costas arrays (positions 0–6 and 36–42)
        // both fit within the buffer.  This covers:
        //   • On-air signals with up to ~8 s clock skew (NTP is typically < 0.5 s).
        //   • Pre-recorded WAV files played back without UTC alignment (Voicemeeter tests).
        // The third Costas array (positions 72–78) may be absent for late-starting signals;
        // the maximum achievable Costas score is then 14/21 ≈ 0.67, still above SyncThreshold.
        int maxStartSample = Math.Max(0, pcm.Length - SecondCostasEnd);

        for (int startSample = 0; startSample <= maxStartSample; startSample += SamplesPerSymbol)
        {
            _logger?.LogTrace(
                "Time-domain sweep: startSample = {Start} / {Max} ({StartS:F2} s).",
                startSample, maxStartSample, (double)startSample / SampleRate);

            // P1: pre-compute 79 FFTs once for this time offset.
            // W1: FillSpectrogram writes into the pre-allocated instance field (_spectrogram)
            // instead of allocating a new 316 KB LOH array, eliminating GC pressure.
            SymbolExtractor.FillSpectrogram(pcm, startSample, _spectrogram);

            // Sweep base frequencies for Costas candidate detection.
            for (double baseHz = MinFreqHz; baseHz <= MaxFreqHz; baseHz += ToneSpacing)
            {
                ct.ThrowIfCancellationRequested();

                // FFT-based coarse grid for fast Costas correlation.
                // bin alignment corrected per D3 (Math.Round, not simple offset).
                var fftGrid    = SymbolExtractor.ExtractFromSpectrogram(_spectrogram, baseHz);
                var candidates = CostasSynchroniser.FindCandidates(fftGrid, SyncThreshold);

                foreach (var cand in candidates)
                {
                    ct.ThrowIfCancellationRequested();

                    // Candidate's exact signal base (tone 0 frequency).
                    double actualBase = baseHz + cand.FreqBinOffset * ToneSpacing;
                    int    freqHz     = (int)Math.Round(actualBase + 3 * ToneSpacing); // centre tone

                    // Goertzel exact-frequency grid for the confirmed candidate.
                    // FT8 tones are exact multiples of 6.25 Hz (align on 1920-pt DFT
                    // bins) but NOT on 2048-pt bins, so the FFT grid has spectral
                    // leakage that corrupts LLR signs.  Goertzel evaluates the DFT at
                    // the precise tone frequencies — zero leakage, correct LLR signs.
                    // Only called for confirmed Costas hits, so overhead is negligible.
                    // Column 0 of the returned grid is signal tone 0 → freqShift = 0.
                    float[,] grid = SymbolExtractor.Extract(pcm, startSample, actualBase);

                    // Derive soft LLRs from the Goertzel grid (freqShift = 0).
                    var llr = ComputeLlrs(grid, freqShift: 0);

                    // LDPC decode.
                    var decoded = LdpcDecoder.Decode(llr);
                    if (decoded is null) continue;

                    // CRC-14 check: decoded is exactly 91 bytes (77 msg bits + 14 CRC bits).
                    // bits[0..76]  = message payload
                    // bits[77..90] = appended CRC-14
                    bool crcOk = Crc14.Verify(decoded, 91);
                    if (!crcOk) continue;

                    // Guard: the all-zeros 91-bit block trivially satisfies LDPC parity and
                    // CRC-14 (initial register = 0). No valid FT8 transmission encodes to all
                    // zeros; this check prevents a noise burst with all-positive LLRs from
                    // producing the spurious "DE DE AA00" decode. (D2)
                    bool allZeros = true;
                    for (int z = 0; z < decoded.Length; z++)
                        if (decoded[z] != 0) { allZeros = false; break; }
                    if (allZeros) continue;

                    // Unpack the 77-bit message payload.
                    var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
                    string msg  = MessageUnpacker.Unpack(msgBits);

                    // De-duplicate across the full time+frequency sweep.
                    if (!seen.Add(msg)) continue;

                    // Estimate SNR: peak log-energy minus noise floor (freqShift = 0).
                    float snrEst = EstimateSnr(grid, freqShift: 0);

                    // Dt: seconds from the UTC cycle boundary to where the signal was found.
                    double dt = (double)startSample / SampleRate;

                    results.Add(new DecodeResult(
                        Time:    timeStr,
                        Snr:     (int)Math.Round(snrEst),
                        Dt:      Math.Round(dt, 1),
                        FreqHz:  freqHz,
                        Message: msg));
                }
            }
        }

        _logger?.LogInformation(
            "Cycle {Time}: {Count} decode(s) found.", timeStr, results.Count);

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
            // The grid is GridWidth = 15 columns wide; freqShift 0–7 maps to columns
            // freqShift..freqShift+7, all within bounds — no % 8 wrapping needed. (D4)
            float e0 = grid[s, freqShift + 0];
            float e1 = grid[s, freqShift + 1];
            float e2 = grid[s, freqShift + 2];
            float e3 = grid[s, freqShift + 3];
            float e4 = grid[s, freqShift + 4];
            float e5 = grid[s, freqShift + 5];
            float e6 = grid[s, freqShift + 6];
            float e7 = grid[s, freqShift + 7];

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

            // Bit 0 (LSB) = 0 for tones 0,3,5,6; 1 for tones 1,2,4,7.
            // Inverse Gray table: tone 4 → binary 111 (b0=1), tone 5 → 110 (b0=0),
            // tone 6 → 100 (b0=0), tone 7 → 101 (b0=1).
            float b0_0 = LogSumExp(e0, e3, e5, e6);
            float b0_1 = LogSumExp(e1, e2, e4, e7);

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

    private static float EstimateSnr(float[,] grid, int freqShift)
    {
        // Simple estimate: mean peak log-energy of data symbols minus mean of off-tones.
        // Only the 8 signal columns [freqShift, freqShift + 8) are relevant. (D4)
        const int tones = 8;
        float peakSum = 0f, noiseSum = 0f;
        int   count   = 0;

        for (int s = 0; s < SymbolCount; s++)
        {
            float max = float.MinValue, sum = 0f;
            for (int t = freqShift; t < freqShift + tones; t++)
            {
                float e = grid[s, t];
                if (e > max) max = e;
                sum += e;
            }
            peakSum  += max;
            noiseSum += (sum - max) / (tones - 1f);
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
