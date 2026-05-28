namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Extracts the 79 × 8 log-energy grid from a 15-second 12 kHz mono PCM buffer.
///
/// FT8 parameters (Franke &amp; Taylor 2019):
///   Symbol duration : 1/6.25 s ≈ 0.160 s → 1 920 samples at 12 000 Hz
///   Tone count      : 8  (3 bits/symbol)
///   Tone spacing    : 6.25 Hz
///   Symbol count    : 79 per transmission (7 + 29 + 7 + 29 + 7 data symbols)
///
/// The grid is built for a specific frequency <em>offset</em> — the lowest tone of
/// the candidate transmission.  <see cref="CostasSynchroniser"/> calls this for
/// each candidate offset found during correlation.
/// </summary>
internal static class SymbolExtractor
{
    /// <summary>FT8 tone spacing in Hz.</summary>
    public const double ToneSpacingHz = 6.25;

    /// <summary>Number of tones per symbol (8-FSK).</summary>
    public const int ToneCount = 8;

    /// <summary>Number of symbols per FT8 transmission.</summary>
    public const int SymbolCount = 79;

    /// <summary>Sample rate expected by this extractor.</summary>
    public const int SampleRate = 12_000;

    /// <summary>Samples per symbol at 12 kHz / 6.25 Hz.</summary>
    /// <remarks>
    /// Cast <em>after</em> the floating-point division — <c>(int)ToneSpacingHz</c> would
    /// truncate 6.25 to 6, giving 12000/6 = 2000 (wrong). Dividing first yields exactly
    /// 1920.0; the explicit <c>(int)</c> cast of that result is safe and is a valid
    /// compile-time constant expression.
    /// </remarks>
    public const int SamplesPerSymbol = (int)(SampleRate / ToneSpacingHz); // 1920

    /// <summary>
    /// FFT size used by the spectrogram path.  1 920 samples are zero-padded to this
    /// value (the next power of 2) before the FFT.  Bin spacing = 12 000 / 2 048 ≈ 5.859 Hz.
    /// The frequency error versus the exact 6.25 Hz spacing is ≤ 3 Hz per tone — negligible
    /// for FT8 tone discrimination.
    /// </summary>
    internal const int FftSizePadded = 2048;

    /// <summary>Number of unique positive-frequency bins in the zero-padded FFT.</summary>
    internal const int SpecBins = FftSizePadded / 2; // 1 024

    /// <summary>
    /// Width of the log-energy grid returned by <see cref="Extract"/> and
    /// <see cref="ExtractFromSpectrogram"/>: 8 signal tones + 7 guard columns so that
    /// any <c>freqShift</c> in 0–7 keeps all 8 signal tones within bounds without
    /// requiring modulo-8 wrapping.  (D4)
    /// </summary>
    public const int GridWidth = ToneCount + 7; // 15

    /// <summary>
    /// Builds a log-energy grid <c>[symbol, column]</c> for the 79 symbols of an FT8
    /// transmission whose lowest tone sits at <paramref name="baseFrequencyHz"/>.
    ///
    /// The grid has <see cref="GridWidth"/> = 15 columns.  Columns 0–7 correspond to
    /// the 8 FT8 tones at <c>baseFrequencyHz + c × 6.25 Hz</c>.  The extra 7 columns
    /// (8–14) allow <see cref="CostasSynchroniser"/> to use frequency offsets up to 7
    /// without wrapping.  (D4)
    /// </summary>
    /// <param name="pcm">Full 15-second PCM buffer (must be ≥ <paramref name="startSample"/> + 79 × 1920 samples).</param>
    /// <param name="startSample">Sample index at which the first symbol begins.</param>
    /// <param name="baseFrequencyHz">Frequency of the lowest (tone 0) column, in Hz.</param>
    /// <returns>A <c>float[79, 15]</c> array of log-energies (natural log).</returns>
    public static float[,] Extract(ReadOnlySpan<float> pcm, int startSample, double baseFrequencyHz)
    {
        var grid = new float[SymbolCount, GridWidth];

        // p8: pre-compute the 15 Goertzel coefficients once per Extract call.
        // Saves GridWidth × (SymbolCount − 1) = 15 × 78 = 1,170 MathF.Cos evaluations.
        var coeffs = new float[GridWidth];
        for (int col = 0; col < GridWidth; col++)
            coeffs[col] = GoertzelDetector.Coeff(baseFrequencyHz + col * ToneSpacingHz, SampleRate);

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            int offset = startSample + sym * SamplesPerSymbol;
            if (offset + SamplesPerSymbol > pcm.Length)
                break;

            var window = pcm.Slice(offset, SamplesPerSymbol);

            for (int col = 0; col < GridWidth; col++)
            {
                float energy = GoertzelDetector.ComputeEnergyWithCoeff(window, coeffs[col]);
                grid[sym, col] = MathF.Log(energy + 1e-10f);
            }
        }

        return grid;
    }

    /// <summary>
    /// Pre-computes a power spectrogram for all 79 symbol windows starting at
    /// <paramref name="startSample"/>.
    ///
    /// <para>
    /// Each 1 920-sample symbol window is zero-padded to 2 048 samples and passed
    /// through a radix-2 FFT.  The squared magnitudes of the 1 024 positive-frequency
    /// bins are stored in the returned array.
    /// </para>
    ///
    /// <para>
    /// Bin <c>k</c> corresponds to frequency <c>k × 12 000 / 2 048 ≈ k × 5.859 Hz</c>.
    /// To find the bin for a target frequency <c>f</c>:
    /// <c>bin = (int)Math.Round(f * FftSizePadded / SampleRate)</c>.
    /// </para>
    ///
    /// <para>
    /// Call this <strong>once per time-domain start position</strong>; then call
    /// <see cref="ExtractFromSpectrogram"/> for each candidate base frequency.
    /// This reduces per-decode work from O(F·S·T·N) to O(S·T·N log N), where
    /// F = frequency sweep width (~473 steps), S = symbol count (79),
    /// T = time sweep positions (52), N = FFT size (2 048).
    /// </para>
    /// </summary>
    /// <returns>
    /// A <c>float[SymbolCount, SpecBins]</c> array of squared FFT magnitudes.
    /// </returns>
    internal static float[,] ComputeSpectrogram(ReadOnlySpan<float> pcm, int startSample)
    {
        var result = new float[SymbolCount, SpecBins];
        var re     = new float[FftSizePadded];
        var im     = new float[FftSizePadded];

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            int offset = startSample + sym * SamplesPerSymbol;
            if (offset + SamplesPerSymbol > pcm.Length) break;

            // Copy 1 920 samples into the FFT buffer; the remaining 128 stay zero (padding).
            pcm.Slice(offset, SamplesPerSymbol).CopyTo(re);
            Array.Clear(re, SamplesPerSymbol, FftSizePadded - SamplesPerSymbol); // zero pad
            Array.Clear(im, 0, FftSizePadded);

            FftCompute.Fft(re, im);

            for (int bin = 0; bin < SpecBins; bin++)
                result[sym, bin] = re[bin] * re[bin] + im[bin] * im[bin];
        }

        return result;
    }

    /// <summary>
    /// Fills <paramref name="result"/> with the power spectrogram for the 79 symbol windows
    /// starting at <paramref name="startSample"/>.
    ///
    /// <para>
    /// Functionally identical to <see cref="ComputeSpectrogram"/> but writes into a
    /// caller-provided buffer instead of allocating a new array.  Use this overload
    /// from long-running paths (e.g. <c>Ft8Decoder.DecodeAsync</c>) to avoid 316 KB
    /// LOH allocations on every call.
    /// </para>
    /// </summary>
    /// <param name="pcm">Full PCM buffer.</param>
    /// <param name="startSample">First sample of the first symbol.</param>
    /// <param name="result">
    /// Pre-allocated <c>float[SymbolCount, SpecBins]</c> buffer to fill.
    /// All elements are fully overwritten for symbols within the buffer bounds;
    /// symbols that would fall outside <paramref name="pcm"/> leave the corresponding
    /// rows unchanged (same guard as <see cref="ComputeSpectrogram"/>).
    /// </param>
    internal static void FillSpectrogram(ReadOnlySpan<float> pcm, int startSample, float[,] result)
    {
        var re = new float[FftSizePadded];
        var im = new float[FftSizePadded];

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            int offset = startSample + sym * SamplesPerSymbol;
            if (offset + SamplesPerSymbol > pcm.Length)
            {
                // Zero any row that falls outside the buffer. Without this, stale data
                // from a previous startSample iteration (the pre-allocated _spectrogram
                // buffer in Ft8Decoder is reused across time-sweep positions) can satisfy
                // Costas correlation checks and produce phantom decode candidates. (D5)
                for (int bin = 0; bin < SpecBins; bin++)
                    result[sym, bin] = 0f;
                continue;
            }

            pcm.Slice(offset, SamplesPerSymbol).CopyTo(re);
            Array.Clear(re, SamplesPerSymbol, FftSizePadded - SamplesPerSymbol);
            Array.Clear(im, 0, FftSizePadded);

            FftCompute.Fft(re, im);

            for (int bin = 0; bin < SpecBins; bin++)
                result[sym, bin] = re[bin] * re[bin] + im[bin] * im[bin];
        }
    }

    /// <summary>
    /// Extracts a 79 × 15 log-energy grid from a pre-computed spectrogram.
    ///
    /// <para>
    /// Each column <c>c</c> (0–14) is mapped to the FFT bin nearest to the exact
    /// FT8 tone frequency <c>baseHz + c × 6.25 Hz</c>:
    /// <code>bin = (int)Math.Round((baseHz + c × ToneSpacingHz) × FftSizePadded / SampleRate)</code>
    /// This corrects the bin-alignment error that arose when the old implementation
    /// simply added <c>c</c> to <c>baseBin</c> — valid only when the FFT bin spacing
    /// equals the FT8 tone spacing (6.25 Hz), but the zero-padded FFT has bin spacing
    /// ≈ 5.859 Hz, causing drift of up to −2.9 dB at tone 7.  (D3)
    /// </para>
    ///
    /// <para>
    /// The grid is 15 columns wide (not 8) so that any <c>freqShift</c> in 0–7 used
    /// by <see cref="CostasSynchroniser"/> or <c>Ft8Decoder.ComputeLlrs</c> accesses
    /// valid columns without modulo-8 wrapping.  (D4)
    /// </para>
    /// </summary>
    /// <param name="spectrogram">
    /// Output of <see cref="ComputeSpectrogram"/>: <c>float[SymbolCount, SpecBins]</c>.
    /// </param>
    /// <param name="baseHz">
    /// Frequency of the lowest tone (column 0), in Hz.
    /// </param>
    internal static float[,] ExtractFromSpectrogram(float[,] spectrogram, double baseHz)
    {
        int symCount = spectrogram.GetLength(0); // 79
        int specBins = spectrogram.GetLength(1); // 1 024
        var grid     = new float[symCount, GridWidth]; // 79 × 15

        for (int sym = 0; sym < symCount; sym++)
        for (int col = 0; col < GridWidth; col++)
        {
            // Exact bin for this column's tone frequency. (D3)
            int   bin    = (int)Math.Round((baseHz + col * ToneSpacingHz) * FftSizePadded / SampleRate);
            float energy = (uint)bin < (uint)specBins ? spectrogram[sym, bin] : 0f;
            grid[sym, col] = MathF.Log(energy + 1e-10f);
        }

        return grid;
    }
}
