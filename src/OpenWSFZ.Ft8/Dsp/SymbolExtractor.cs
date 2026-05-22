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
}
