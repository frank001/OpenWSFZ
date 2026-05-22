namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Computes the energy at a single target frequency over a sample window using the
/// Goertzel algorithm (a single-bin DFT). More efficient than a full FFT when only
/// a small number of frequency bins are needed.
/// </summary>
internal static class GoertzelDetector
{
    /// <summary>
    /// Computes the squared magnitude (energy proxy) of a single frequency bin.
    /// </summary>
    /// <param name="samples">PCM sample window (mono float, any range).</param>
    /// <param name="targetFrequencyHz">The frequency to probe, in Hz.</param>
    /// <param name="sampleRateHz">Sample rate of <paramref name="samples"/>, in Hz.</param>
    /// <returns>Squared magnitude — proportional to energy at the target frequency.</returns>
    public static float ComputeEnergy(ReadOnlySpan<float> samples, double targetFrequencyHz, double sampleRateHz)
    {
        // Pre-compute the Goertzel coefficient in single precision.
        // float is sufficient for the ~6 Hz tone-spacing resolution of FT8 at 12 kHz,
        // and is 2-3× faster than double on modern JIT — necessary because the
        // time-domain sweep in Ft8Decoder multiplies this call count by ~50.
        float coeff = 2.0f * MathF.Cos(2.0f * MathF.PI * (float)(targetFrequencyHz / sampleRateHz));

        float s1 = 0f;
        float s2 = 0f;

        foreach (var sample in samples)
        {
            float s0 = sample + coeff * s1 - s2;
            s2 = s1;
            s1 = s0;
        }

        // Squared magnitude: |X|² = s1² + s2² - coeff·s1·s2
        return s1 * s1 + s2 * s2 - coeff * s1 * s2;
    }
}
