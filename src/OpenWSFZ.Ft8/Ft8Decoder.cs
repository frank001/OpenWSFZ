using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Dsp;

namespace OpenWSFZ.Ft8;

/// <summary>
/// Cleanroom FT8 decoder implementing <see cref="IModeDecoder"/>.
///
/// Pipeline per cycle (exact-DFT spectrogram):
///   1. For each symbol-aligned time offset, compute a 79 × 960 exact-DFT spectrogram
///      once via <see cref="SymbolExtractor.FillSpectrogramExact"/>.
///   2. Sweep candidate base frequencies (50–3 000 Hz, steps of 50 Hz).
///      Extract a 79 × 15 log-energy grid via <see cref="SymbolExtractor.ExtractFromSpectrogram"/>
///      and run <see cref="CostasSynchroniser.FindCandidates"/> to find Costas sync hits.
///   3. For each Costas candidate, re-extract the 79 × 15 grid from the same spectrogram
///      at the exact candidate base frequency, derive 174 soft LLRs via
///      <see cref="ComputeLlrs"/>, run <see cref="LdpcDecoder"/>, verify with
///      <see cref="Crc14"/>, unpack with <see cref="MessageUnpacker"/>.
///   4. De-duplicate messages; return the unique set as <see cref="DecodeResult"/> records.
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
    private const int    ExactSpecBins = SymbolExtractor.ExactSpecBins;  // 960

    // Frequency sweep parameters.
    private const double MinFreqHz    = 50.0;
    private const double MaxFreqHz    = 3000.0;

    // Outer frequency sweep step: one full 8-tone signal band = 8 × 6.25 = 50 Hz.
    //
    // The CostasSynchroniser sweeps freqShift 0–7 within each 15-wide grid window,
    // covering the 8 × 6.25 = 50 Hz band with 6.25 Hz resolution.  Each real FT8
    // signal (whose tones are always on the 6.25 Hz grid) therefore falls in exactly
    // ONE (baseHz, freqShift) combination — no duplicates.
    //
    // Previously the outer loop stepped by ToneSpacing (6.25 Hz), causing every signal
    // to be detected 8 times (once per freqShift 0–7).  With a busy band of 15 signals
    // that inflated 15 Goertzel calls to ~120, and with 102 time positions the full
    // decode required several minutes.  With this fix the worst-case is ~15 Goertzel
    // calls per time position × 102 positions = ~1 530 calls, completing well within
    // the 15-second cycle budget.  (D12)
    private const double FreqSweepStep = ToneSpacing * 8; // 50.0 Hz

    // Costas sync threshold — must be strictly above the uniform-noise floor of 0.125.
    // Under uniform noise each of the 21 Costas symbols scores exp(E)/(8×exp(E)) = 1/8;
    // summing 21 contributions and dividing by maxPossible = 21 gives exactly 0.125.
    // A threshold of 0.20 sits comfortably above the noise floor while remaining below
    // 0.33 (three equal-power interferers), keeping false-alarm rates low on a crowded
    // 40 m band.  The CRC-14 gate (1-in-16 384 per LDPC run) provides the final filter.
    //
    // NOTE: on a busy 40 m band with many simultaneous signals the softmax LogSumAll
    // denominator is raised by adjacent-channel interference, depressing all Costas
    // scores below the theoretical noise floor (< 0.125).  Lowering the threshold
    // below 0.125 does not recover real signals — it only admits more noise candidates.
    // Proper multi-signal decoding requires iterative subtraction (ft8_lib Phase 2B).
    private const float  SyncThreshold = 0.20f;

    // Maximum candidates per (startSample, baseHz) sweep position.
    // Under crowded-band conditions the QW9END signal may rank below the top 2
    // for a given baseHz due to adjacent interferers with higher Costas scores.
    // Expanding to 8 (all freqShifts) ensures every candidate is attempted.
    private const int MaxCandidatesPerSweep = 8;

    // Time-domain sweep: maximum start sample such that the first two Costas arrays
    // (positions 0–6 and 36–42) still fit fully in the buffer.
    // Second Costas array occupies symbols 36–42 → last sample index = (42+1)×1920 − 1 = 82 559.
    // Signals starting beyond this offset have only one Costas array present → score ≤ 7/21 = 0.33,
    // below SyncThreshold, so sweeping further is futile without lowering the threshold.
    private const int SecondCostasEnd = (42 + 1) * SamplesPerSymbol; // 82 560

    // Time-domain sweep step: half a symbol period (960 samples = 80 ms).
    // Using a full symbol period (1920 samples) as the step means a signal whose dt
    // falls exactly halfway between two sweep positions has every symbol window contaminated
    // 50/50 with the adjacent symbol — LLRs lose sign reliability and LDPC diverges (D11).
    // At half-symbol step the worst-case contamination drops to 25 %, which is tolerable.
    // The extra time-sweep positions double the Costas scan count but not the Goertzel
    // calls (those are only made for confirmed Costas hits, still single-digit per offset).
    private const int TimeSweepStep = SamplesPerSymbol / 2; // 960

    private readonly IClock              _clock;
    private readonly ILogger<Ft8Decoder>? _logger;

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

        int maxStartSample = Math.Max(0, pcm.Length - SecondCostasEnd);
        int stepCount      = maxStartSample / TimeSweepStep + 1;

        // Thread-safe result accumulator.  Capacity hint avoids repeated resizing on
        // a typical busy-band cycle (expect O(10–50) unique messages).
        var bag = new System.Collections.Concurrent.ConcurrentBag<DecodeResult>();

        // Diagnostic counters — updated via Interlocked because the parallel body runs
        // on multiple threads.
        int diag_costas    = 0;
        int diag_ldpc      = 0;
        int diag_crc       = 0;
        int diag_paritySum = 0;

        var sw = System.Diagnostics.Stopwatch.StartNew();

        Parallel.For(0, stepCount, new ParallelOptions { CancellationToken = ct }, i =>
        {
            int startSample = i * TimeSweepStep;
            if (startSample > maxStartSample) return;

            _logger?.LogTrace(
                "Time-domain sweep: startSample = {Start} / {Max} ({StartS:F2} s).",
                startSample, maxStartSample, (double)startSample / SampleRate);

            // Per-iteration exact-DFT spectrogram buffer (~237 KB, 79 × 960 × 4 bytes).
            // Bluestein chirp-Z gives 1920-point DFT, bin spacing = 6.25 Hz exactly —
            // each FT8 tone falls on one bin with no spectral leakage.
            var spectrogram = new float[SymbolCount, ExactSpecBins];
            SymbolExtractor.FillSpectrogramExact(pcm, startSample, spectrogram);

            for (double baseHz = MinFreqHz; baseHz <= MaxFreqHz; baseHz += FreqSweepStep)
            {
                ct.ThrowIfCancellationRequested();

                var fftGrid    = SymbolExtractor.ExtractFromSpectrogram(spectrogram, baseHz);
                var candidates = CostasSynchroniser.FindCandidates(fftGrid, SyncThreshold);
                int take       = Math.Min(candidates.Count, MaxCandidatesPerSweep);

                for (int ci = 0; ci < take; ci++)
                {
                    ct.ThrowIfCancellationRequested();
                    var cand = candidates[ci];

                    Interlocked.Increment(ref diag_costas);

                    double actualBase = baseHz + cand.FreqBinOffset * ToneSpacing;
                    int    freqHz     = (int)Math.Round(actualBase + 3 * ToneSpacing);

                    _logger?.LogDebug(
                        "Costas hit: startSample={Start}, base={Base:F2} Hz, score={Score:F3}.",
                        startSample, actualBase, cand.Score);

                    // Use the exact-DFT spectrogram for LLR extraction.
                    // The 1920-pt Bluestein spectrogram gives zero inter-bin crosstalk for
                    // FT8-grid-aligned tones and correct carrier-offset handling (rounds to the
                    // nearest 6.25 Hz bin), matching ft8_lib's approach of using the same
                    // spectrogram for both Costas detection and symbol energy extraction.
                    float[,] grid = SymbolExtractor.ExtractFromSpectrogram(spectrogram, actualBase);
                    var llr       = ComputeLlrs(grid, freqShift: 0);

                    // No LLR clamping — strong-signal LLRs (~8-9) must dominate over
                    // interference (~2-3) so LDPC converges to the correct codeword.

                    Interlocked.Add(ref diag_paritySum, LdpcDecoder.CountInitialParityFailures(llr));

                    var decoded = LdpcDecoder.Decode(llr);
                    if (decoded is null) continue;
                    Interlocked.Increment(ref diag_ldpc);

                    bool crcOk = Crc14.VerifyFt8(decoded);
                    if (!crcOk) continue;

                    bool allZeros = true;
                    for (int z = 0; z < decoded.Length; z++)
                        if (decoded[z] != 0) { allZeros = false; break; }
                    if (allZeros) continue;

                    Interlocked.Increment(ref diag_crc);

                    var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
                    string? msg = MessageUnpacker.TryUnpack(msgBits);
                    if (msg is null) continue; // unsupported message type (i3=2,3,4,6,7) — skip silently

                    double dt = (double)startSample / SampleRate;
                    bag.Add(new DecodeResult(
                        Time:    timeStr,
                        Snr:     (int)Math.Round(EstimateSnr(grid, freqShift: 0)),
                        Dt:      Math.Round(dt, 1),
                        FreqHz:  freqHz,
                        Message: msg));
                }
            }
        });

        sw.Stop();

        // Merge bag results; apply de-duplication after parallel loop.
        foreach (var r in bag)
            if (seen.Add(r.Message))
                results.Add(r);

        float avgParity = diag_costas > 0 ? (float)diag_paritySum / diag_costas : 0f;
        _logger?.LogInformation(
            "Cycle {Time}: {Count} decode(s) found. " +
            "[diag] Costas candidates={Costas}, LDPC converged={Ldpc}, CRC passed={Crc}, " +
            "avg_initial_parity_fail={AvgParity:F1}/83, elapsed={Elapsed} ms.",
            timeStr, results.Count, diag_costas, diag_ldpc, diag_crc, avgParity, sw.ElapsedMilliseconds);

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

            // 3-bit Gray code using the FT8 kFT8_Gray_map from kgoba/ft8_lib:
            //   { 0, 1, 3, 2, 5, 6, 4, 7 }  (index = bits3, value = tone)
            // Inverse (tone → bits3):
            //   tone 0 → 0 (000)  tone 1 → 1 (001)  tone 2 → 3 (011)  tone 3 → 2 (010)
            //   tone 4 → 6 (110)  tone 5 → 4 (100)  tone 6 → 5 (101)  tone 7 → 7 (111)
            //
            // NOTE: this is NOT the standard G(n)=n^(n>>1) code.  They agree for binary
            // values 0–3 but differ for 4–7.  Using G(n) instead gives wrong LLR signs
            // for all b2=1 symbols (~50% of data symbols) and causes LDPC to never
            // converge on live FT8 signals.  (D13)
            //
            // Bit 2 (MSB) = 0 for tones {0,1,2,3}, 1 for tones {4,5,6,7}.
            float b2_0 = LogSumExp(e0, e1, e2, e3);
            float b2_1 = LogSumExp(e4, e5, e6, e7);

            // Bit 1 = 0 for tones {0,1,5,6}, 1 for tones {2,3,4,7}.
            float b1_0 = LogSumExp(e0, e1, e5, e6);
            float b1_1 = LogSumExp(e2, e3, e4, e7);

            // Bit 0 (LSB) = 0 for tones {0,3,4,5}, 1 for tones {1,2,6,7}.
            float b0_0 = LogSumExp(e0, e3, e4, e5);
            float b0_1 = LogSumExp(e1, e2, e6, e7);

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
