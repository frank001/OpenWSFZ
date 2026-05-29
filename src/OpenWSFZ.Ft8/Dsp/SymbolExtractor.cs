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
    // ── Bluestein chirp-Z pre-computed tables ────────────────────────────────
    //
    // The Bluestein algorithm computes an N-point DFT for arbitrary N using a
    // power-of-two FFT as a subroutine.  For N = 1 920: the next power of 2
    // above 2N − 1 = 3 839 is 4 096.
    //
    // Identity: X[k] = exp(−jπk²/N) · (a ⋆ h)[k]
    //   where a[n] = x[n] · exp(−jπn²/N)   (chirp-modulated input)
    //         h[n] = exp(+jπn²/N)           (chirp filter, even-symmetric)
    //
    // The convolution is computed as IFFT(FFT(a) · FFT(h)).
    // Since |exp(−jπk²/N)| = 1, |X[k]|² = |(a ⋆ h)[k]|² — no output-chirp
    // multiplication is needed when only squared magnitudes are required.
    //
    // Reference: kgoba/ft8_lib — the 1 920-point DFT is the key insight that
    // aligns bin spacing (12 000/1 920 = 6.25 Hz) with FT8 tone spacing.

    /// <summary>FFT size for the Bluestein convolution (≥ 2 × 1920 − 1 = 3839; next power of 2).</summary>
    private const int BluesteinFftSize = 4096;

    // Chirp tables (initialised once in the static constructor).
    // s_chirpRe[n] = cos(−πn²/N),  s_chirpIm[n] = sin(−πn²/N)
    private static readonly float[] s_chirpRe;
    private static readonly float[] s_chirpIm;

    // Frequency-domain Bluestein filter: FFT of h[n] = exp(+jπn²/N), padded to BluesteinFftSize.
    private static readonly float[] s_filterFftRe;
    private static readonly float[] s_filterFftIm;

    static SymbolExtractor()
    {
        int N = SamplesPerSymbol; // 1 920
        int M = BluesteinFftSize; // 4 096

        s_chirpRe = new float[N];
        s_chirpIm = new float[N];

        var hRe = new float[M];
        var hIm = new float[M];

        for (int n = 0; n < N; n++)
        {
            double angle = Math.PI * (double)n * n / N;  // πn²/N

            s_chirpRe[n] = (float)Math.Cos(-angle);  // exp(−jπn²/N) real
            s_chirpIm[n] = (float)Math.Sin(-angle);  // exp(−jπn²/N) imag

            float hRen = (float)Math.Cos(angle);     // exp(+jπn²/N) real
            float hImn = (float)Math.Sin(angle);     // exp(+jπn²/N) imag

            hRe[n] = hRen;
            hIm[n] = hImn;

            if (n > 0)
            {
                // Wrap-around for negative-index chirp values.
                // h[−n] = exp(+jπ(−n)²/N) = exp(+jπn²/N) = h[n].
                hRe[M - n] = hRen;
                hIm[M - n] = hImn;
            }
        }

        // Pre-compute FFT of the filter kernel (done once at startup).
        FftCompute.Fft(hRe, hIm);
        s_filterFftRe = hRe;
        s_filterFftIm = hIm;
    }
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
    /// FFT size used by the legacy <see cref="FillSpectrogram"/> / <see cref="ComputeSpectrogram"/>
    /// path.  1 920 samples are zero-padded to this value (the next power of 2) before the FFT.
    /// Bin spacing = 12 000 / 2 048 ≈ 5.859 Hz — NOT aligned with FT8 tone spacing (6.25 Hz).
    /// </summary>
    internal const int FftSizePadded = 2048;

    /// <summary>Number of unique positive-frequency bins in the legacy zero-padded FFT.</summary>
    internal const int SpecBins = FftSizePadded / 2; // 1 024

    /// <summary>
    /// Number of unique positive-frequency bins in the exact 1 920-point DFT.
    /// Bin spacing = 12 000 / 1 920 = 6.25 Hz — exactly equal to FT8 tone spacing.
    /// Each FT8 tone falls on exactly one bin with no spectral leakage.
    /// </summary>
    internal const int ExactSpecBins = SamplesPerSymbol / 2; // 960

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
    /// Fills <paramref name="result"/> with a 1 920-point exact-DFT spectrogram
    /// for the 79 symbol windows starting at <paramref name="startSample"/>.
    ///
    /// <para>
    /// Uses the Bluestein chirp-Z algorithm to compute the 1 920-point DFT via a
    /// 4 096-point FFT as a subroutine.  Bin spacing = 12 000 / 1 920 = <b>6.25 Hz</b>
    /// exactly — each FT8 tone falls on exactly one bin with no spectral leakage.
    /// The 2 048-point zero-padded FFT previously used by <see cref="FillSpectrogram"/>
    /// had bin spacing ≈ 5.859 Hz, splitting each FT8 tone across two bins and
    /// corrupting the LLRs fed to the LDPC decoder.
    /// </para>
    ///
    /// <para>
    /// Since |exp(−jπk²/N)| = 1, the squared magnitudes of the Bluestein output
    /// equal the squared magnitudes of the true DFT — no output-chirp multiplication
    /// is needed.
    /// </para>
    ///
    /// <para>
    /// Pre-computed tables (<c>s_chirpRe/Im</c>, <c>s_filterFftRe/Im</c>) are
    /// initialised once in the static constructor and shared across all calls.
    /// Thread-safe for concurrent reads.
    /// </para>
    /// </summary>
    /// <param name="pcm">Full PCM buffer.</param>
    /// <param name="startSample">First sample of the first symbol.</param>
    /// <param name="result">
    /// Pre-allocated <c>float[SymbolCount, ExactSpecBins]</c> (79 × 960) buffer to fill.
    /// Out-of-bounds symbol rows are zeroed as a stale-data guard (D5).
    /// </param>
    internal static void FillSpectrogramExact(
        ReadOnlySpan<float> pcm, int startSample, float[,] result)
    {
        int N = SamplesPerSymbol; // 1 920
        int M = BluesteinFftSize; // 4 096

        // Per-call work buffers — allocated here to be thread-safe in Parallel.For.
        var aRe = new float[M];
        var aIm = new float[M];

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            int offset = startSample + sym * SamplesPerSymbol;

            if (offset + SamplesPerSymbol > pcm.Length)
            {
                // Zero guard — prevents stale data from a previous startSample
                // iteration from producing phantom Costas hits. (D5)
                for (int bin = 0; bin < ExactSpecBins; bin++)
                    result[sym, bin] = 0f;
                continue;
            }

            // ── Step 1: chirp-modulate input into zero-padded buffer ──────────
            // a[n] = x[n] · exp(−jπn²/N) = x[n] · (s_chirpRe[n] + j·s_chirpIm[n])
            // Zero-padding aRe/aIm[N..M-1] ensures the circular convolution acts
            // as a linear convolution over the support [0..N-1].
            for (int n = 0; n < N; n++)
            {
                float xn = pcm[offset + n];
                aRe[n] = xn * s_chirpRe[n];
                aIm[n] = xn * s_chirpIm[n];
            }
            Array.Clear(aRe, N, M - N);
            Array.Clear(aIm, N, M - N);

            // ── Step 2: FFT of chirp-modulated input ──────────────────────────
            FftCompute.Fft(aRe, aIm);

            // ── Step 3: Pointwise multiply by pre-computed filter FFT ─────────
            // (aRe + j·aIm) ← (aRe + j·aIm) · (s_filterFftRe + j·s_filterFftIm)
            for (int k = 0; k < M; k++)
            {
                float re = aRe[k] * s_filterFftRe[k] - aIm[k] * s_filterFftIm[k];
                float im = aRe[k] * s_filterFftIm[k] + aIm[k] * s_filterFftRe[k];
                aRe[k] = re;
                aIm[k] = im;
            }

            // ── Step 4: IFFT via conjugate trick — conj(FFT(conj(Y))) / M ─────
            for (int k = 0; k < M; k++) aIm[k] = -aIm[k]; // conjugate
            FftCompute.Fft(aRe, aIm);
            float invM = 1f / M;
            for (int k = 0; k < M; k++)
            {
                aRe[k] *=  invM;
                aIm[k] = -aIm[k] * invM; // re-conjugate and scale
            }

            // ── Step 5: Store |y[k]|² for positive-frequency bins ─────────────
            // |X[k]|² = |y[k]|² because |exp(−jπk²/N)| = 1.
            for (int bin = 0; bin < ExactSpecBins; bin++)
            {
                float re = aRe[bin];
                float im = aIm[bin];
                result[sym, bin] = re * re + im * im;
            }
        }
    }

    /// <summary>
    /// Extracts a 79 × 15 log-energy grid from a pre-computed exact-DFT spectrogram.
    ///
    /// <para>
    /// With the 1 920-point DFT, bin spacing equals FT8 tone spacing (6.25 Hz exactly).
    /// Each FT8 tone at <c>baseHz + c × 6.25 Hz</c> falls on exactly bin
    /// <c>round((baseHz + c × ToneSpacingHz) / ToneSpacingHz)</c> — integer arithmetic,
    /// no rounding error, no leakage correction needed.
    /// </para>
    ///
    /// <para>
    /// The grid is 15 columns wide (not 8) so that any <c>freqShift</c> in 0–7 used
    /// by <see cref="CostasSynchroniser"/> or <c>Ft8Decoder.ComputeLlrs</c> accesses
    /// valid columns without modulo-8 wrapping.  (D4)
    /// </para>
    /// </summary>
    /// <param name="spectrogram">
    /// Output of <see cref="FillSpectrogramExact"/>: <c>float[SymbolCount, ExactSpecBins]</c>.
    /// </param>
    /// <param name="baseHz">
    /// Frequency of the lowest tone (column 0), in Hz.
    /// </param>
    internal static float[,] ExtractFromSpectrogram(float[,] spectrogram, double baseHz)
    {
        int symCount = spectrogram.GetLength(0); // 79
        int specBins = spectrogram.GetLength(1); // 960
        var grid     = new float[symCount, GridWidth]; // 79 × 15

        for (int sym = 0; sym < symCount; sym++)
        for (int col = 0; col < GridWidth; col++)
        {
            // Exact bin — no rounding error with the 1 920-point DFT.
            int   bin    = (int)Math.Round((baseHz + col * ToneSpacingHz) / ToneSpacingHz);
            float energy = (uint)bin < (uint)specBins ? spectrogram[sym, bin] : 0f;
            grid[sym, col] = MathF.Log(energy + 1e-10f);
        }

        return grid;
    }
}
