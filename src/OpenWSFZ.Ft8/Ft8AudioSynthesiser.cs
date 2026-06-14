namespace OpenWSFZ.Ft8;

/// <summary>
/// Synthesises a mono float32 PCM audio buffer representing a single FT8 transmission
/// from a sequence of 79 GFSK tone indices.
///
/// <para>
/// FT8 audio parameters (fixed by the FT8 specification):
/// <list type="bullet">
///   <item>Symbol rate: 6.25 baud → 160 ms per symbol</item>
///   <item>Tone spacing: 6.25 Hz per tone index step</item>
///   <item>Total symbols: 79 → duration 79 × 160 ms = 12 640 ms</item>
///   <item>Output sample rate: 48 000 Hz</item>
///   <item>Samples per symbol: 48 000 / 6.25 = 7 680</item>
///   <item>Total output samples: 79 × 7 680 = 606 720</item>
/// </list>
/// </para>
///
/// <para>
/// The synthesiser uses a <strong>rectangular frequency pulse</strong> (no Gaussian shaping)
/// for simplicity.  Continuous-phase FM is maintained across symbol boundaries: the
/// instantaneous phase accumulates from the first sample of symbol 0 to the last sample
/// of symbol 78, with no phase reset between symbols.  This ensures the waveform has no
/// phase discontinuities at symbol boundaries, as required by FT8 continuous-phase GFSK.
/// </para>
///
/// <para>
/// Output amplitude is normalised to ±0.5 peak (−6 dBFS) to provide headroom when the
/// signal is mixed or played at full device volume.
/// </para>
/// </summary>
public sealed class Ft8AudioSynthesiser
{
    /// <summary>Sample rate of the synthesised output in Hz.</summary>
    public const int SampleRateHz = 48_000;

    /// <summary>FT8 tone spacing in Hz per tone index step.</summary>
    public const double ToneSpacingHz = 6.25;

    /// <summary>FT8 symbol rate in baud (symbols per second).</summary>
    public const double SymbolRateBaud = 6.25;

    /// <summary>Number of output samples per FT8 symbol: 48 000 / 6.25 = 7 680.</summary>
    public const int SamplesPerSymbol = 7_680;

    /// <summary>Total number of FT8 symbols in one transmission.</summary>
    public const int SymbolCount = 79;

    /// <summary>
    /// Total number of output samples: <see cref="SymbolCount"/> × <see cref="SamplesPerSymbol"/>
    /// = 606 720.
    /// </summary>
    public const int TotalSampleCount = SymbolCount * SamplesPerSymbol; // 606 720

    /// <summary>Peak amplitude of the output signal (−6 dBFS).</summary>
    private const float Amplitude = 0.5f;

    /// <summary>
    /// Synthesises a 48 000 Hz mono float32 PCM buffer from 79 FT8 tone indices.
    /// </summary>
    /// <param name="tones">
    /// Array of exactly 79 tone indices, each in [0, 7], as returned by
    /// <c>Ft8LibInterop.EncodeMessage</c>.
    /// </param>
    /// <param name="baseFrequencyHz">
    /// Audio frequency (Hz) assigned to tone index 0.
    /// Tone index <c>t</c> transmits at <c>baseFrequencyHz + t × 6.25 Hz</c>.
    /// </param>
    /// <returns>
    /// <see cref="float"/> array of length 606 720 — 12.64 seconds of 48 kHz mono PCM,
    /// amplitude normalised to ±0.5.
    /// </returns>
    /// <exception cref="ArgumentException">
    /// Thrown when <paramref name="tones"/> does not contain exactly 79 elements,
    /// or when any tone index is outside [0, 7].
    /// </exception>
    /// <exception cref="ArgumentOutOfRangeException">
    /// Thrown when <paramref name="baseFrequencyHz"/> is negative.
    /// </exception>
    public float[] Synthesise(byte[] tones, double baseFrequencyHz)
    {
        if (tones is null)
            throw new ArgumentNullException(nameof(tones));
        if (tones.Length != SymbolCount)
            throw new ArgumentException(
                $"tones must contain exactly {SymbolCount} elements; got {tones.Length}.",
                nameof(tones));
        foreach (var t in tones)
        {
            if (t > 7)
                throw new ArgumentException(
                    $"All tone indices must be in [0, 7]; found {t}.",
                    nameof(tones));
        }
        if (baseFrequencyHz < 0)
            throw new ArgumentOutOfRangeException(nameof(baseFrequencyHz),
                "Base frequency must be non-negative.");

        var output = new float[TotalSampleCount];

        // Phase accumulator (radians). Initialised to zero; accumulates across all
        // 79 symbols to maintain continuous-phase FM (no phase reset at boundaries).
        double phase = 0.0;

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            // Instantaneous frequency for this symbol
            double freq            = baseFrequencyHz + tones[sym] * ToneSpacingHz;
            // Phase increment per sample: 2π × f / Fs
            double phaseIncPerSample = 2.0 * Math.PI * freq / SampleRateHz;

            int baseIndex = sym * SamplesPerSymbol;
            for (int s = 0; s < SamplesPerSymbol; s++)
            {
                output[baseIndex + s] = Amplitude * (float)Math.Sin(phase);
                phase += phaseIncPerSample;
            }
        }

        return output;
    }
}
