namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Computes a power spectrum from a stream of 12 kHz mono float samples.
///
/// Accumulates samples into a 2048-point ring buffer. After every 2048 new
/// samples, applies a Hann window, runs a radix-2 Cooley-Tukey FFT, converts
/// to dBFS, and invokes <see cref="SpectrumReady"/> with the first
/// <see cref="OutputBinCount"/> magnitude values (covering 0–2994 Hz at 12 kHz).
///
/// Not thread-safe — Push must be called from a single thread.
/// </summary>
public sealed class SpectrumAnalyser
{
    public const int FftSize        = 2048;
    public const int SampleRate     = 12_000;
    public const int OutputBinCount = 512;   // bins 0–511 → 0–2994 Hz

    private static readonly float[] HannWindow = BuildHannWindow();

    private readonly float[] _ringBuffer = new float[FftSize];
    private int _writePos;
    private int _accumulated;

    /// <summary>
    /// Invoked after every 2048 new samples with the computed dBFS magnitudes
    /// (length = <see cref="OutputBinCount"/>). Values are in the range
    /// [<c>−120f</c>, <c>0f</c>], where <c>−120f</c> represents silence.
    /// </summary>
    public Action<float[]>? SpectrumReady { get; set; }

    /// <summary>
    /// Push a chunk of 12 kHz mono samples into the analyser.
    /// May invoke <see cref="SpectrumReady"/> synchronously before returning.
    /// </summary>
    public void Push(ReadOnlySpan<float> chunk)
    {
        foreach (var sample in chunk)
        {
            _ringBuffer[_writePos] = sample;
            _writePos = (_writePos + 1) % FftSize;
            _accumulated++;

            if (_accumulated >= FftSize)
            {
                _accumulated = 0;
                Compute();
            }
        }
    }

    /// <summary>
    /// Clears the ring buffer and resets the accumulation counter.
    /// Call after any pipeline restart to prevent stale samples from a prior
    /// capture session contaminating the first post-restart FFT window.
    /// </summary>
    public void Reset()
    {
        Array.Clear(_ringBuffer, 0, FftSize);
        _writePos    = 0;
        _accumulated = 0;
    }

    private void Compute()
    {
        // Copy ring buffer in chronological order and apply Hann window.
        // _writePos is the oldest slot (next write target in a full ring).
        var re = new float[FftSize];
        var im = new float[FftSize]; // stays zero — real input

        for (var i = 0; i < FftSize; i++)
        {
            var srcIdx = (_writePos + i) % FftSize;
            re[i] = _ringBuffer[srcIdx] * HannWindow[i];
        }

        Fft(re, im);

        // Convert to dBFS; extract first OutputBinCount bins.
        // Normalisation factor: 2 / FftSize (one-sided spectrum, Hann compensation omitted
        // — display is for visualisation only, not calibrated level measurement).
        var magnitudes = new float[OutputBinCount];
        const float scale = 2f / FftSize;
        for (var i = 0; i < OutputBinCount; i++)
        {
            var mag = MathF.Sqrt(re[i] * re[i] + im[i] * im[i]) * scale;
            magnitudes[i] = mag > 0f
                ? MathF.Max(20f * MathF.Log10(mag), -120f)
                : -120f;
        }

        SpectrumReady?.Invoke(magnitudes);
    }

    // ── FFT ───────────────────────────────────────────────────────────────────

    // Delegates to the shared FftCompute utility so the algorithm is not duplicated
    // between this class and SymbolExtractor's spectrogram path.
    private static void Fft(float[] re, float[] im) => FftCompute.Fft(re, im);

    private static float[] BuildHannWindow()
    {
        var w = new float[FftSize];
        // Periodic (not symmetric) Hann window — correct for spectral analysis.
        // Symmetric form uses (N-1) in the denominator and introduces a small
        // discontinuity that increases spectral leakage.
        for (var i = 0; i < FftSize; i++)
            w[i] = 0.5f * (1f - MathF.Cos(2f * MathF.PI * i / FftSize));
        return w;
    }
}
