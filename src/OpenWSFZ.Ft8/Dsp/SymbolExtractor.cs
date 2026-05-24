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
    /// Builds a log-energy grid <c>[symbol, tone]</c> for the 79 symbols of an FT8
    /// transmission whose lowest tone sits at <paramref name="baseFrequencyHz"/>.
    /// </summary>
    /// <param name="pcm">Full 15-second PCM buffer (must be ≥ <paramref name="startSample"/> + 79 × 1920 samples).</param>
    /// <param name="startSample">Sample index at which the first symbol begins.</param>
    /// <param name="baseFrequencyHz">Frequency of the lowest (tone 0) bin, in Hz.</param>
    /// <returns>A <c>float[79, 8]</c> array of log-energies (natural log).</returns>
    public static float[,] Extract(ReadOnlySpan<float> pcm, int startSample, double baseFrequencyHz)
    {
        var grid = new float[SymbolCount, ToneCount];

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            int offset = startSample + sym * SamplesPerSymbol;
            if (offset + SamplesPerSymbol > pcm.Length)
                break;

            var window = pcm.Slice(offset, SamplesPerSymbol);

            for (int tone = 0; tone < ToneCount; tone++)
            {
                double freq   = baseFrequencyHz + tone * ToneSpacingHz;
                float  energy = GoertzelDetector.ComputeEnergy(window, freq, SampleRate);

                // Convert to log-energy (add small epsilon to avoid log(0)).
                grid[sym, tone] = MathF.Log(energy + 1e-10f);
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
            if (offset + SamplesPerSymbol > pcm.Length) break;

            pcm.Slice(offset, SamplesPerSymbol).CopyTo(re);
            Array.Clear(re, SamplesPerSymbol, FftSizePadded - SamplesPerSymbol);
            Array.Clear(im, 0, FftSizePadded);

            FftCompute.Fft(re, im);

            for (int bin = 0; bin < SpecBins; bin++)
                result[sym, bin] = re[bin] * re[bin] + im[bin] * im[bin];
        }
    }

    /// <summary>
    /// Extracts a 79 × 8 log-energy grid from a pre-computed spectrogram by mapping
    /// each FT8 tone to its nearest FFT bin.
    ///
    /// For each of the 79 symbols, the energy for tone <c>t</c> is taken from
    /// FFT bin <c>baseBin + t</c> where
    /// <c>baseBin = (int)Math.Round(baseFrequencyHz * FftSizePadded / SampleRate)</c>.
    /// </summary>
    /// <param name="spectrogram">
    /// Output of <see cref="ComputeSpectrogram"/>: <c>float[SymbolCount, SpecBins]</c>.
    /// </param>
    /// <param name="baseBin">
    /// Bin index of the lowest tone.  Compute as
    /// <c>(int)Math.Round(baseFrequencyHz * FftSizePadded / SampleRate)</c>.
    /// </param>
    internal static float[,] ExtractFromSpectrogram(float[,] spectrogram, int baseBin)
    {
        int symCount = spectrogram.GetLength(0); // 79
        int specBins = spectrogram.GetLength(1); // 1 024
        var grid     = new float[symCount, ToneCount];

        for (int sym = 0; sym < symCount; sym++)
        for (int tone = 0; tone < ToneCount; tone++)
        {
            int   bin    = baseBin + tone;
            float energy = (uint)bin < (uint)specBins ? spectrogram[sym, bin] : 0f;
            grid[sym, tone] = MathF.Log(energy + 1e-10f);
        }

        return grid;
    }
}
