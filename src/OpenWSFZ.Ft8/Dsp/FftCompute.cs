namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Shared radix-2 Cooley-Tukey in-place FFT for power-of-2 sizes.
/// Used by both <see cref="SpectrumAnalyser"/> (waterfall display) and
/// <see cref="SymbolExtractor"/> (FT8 decode spectrogram path).
/// </summary>
internal static class FftCompute
{
    /// <summary>
    /// In-place radix-2 DIT FFT.  <paramref name="re"/> and <paramref name="im"/> must be
    /// the same length, which must be a power of two.
    /// </summary>
    internal static void Fft(float[] re, float[] im)
    {
        var n = re.Length;

        // Bit-reversal permutation.
        for (int i = 1, j = 0; i < n; i++)
        {
            var bit = n >> 1;
            for (; (j & bit) != 0; bit >>= 1) j ^= bit;
            j ^= bit;
            if (i < j)
            {
                (re[i], re[j]) = (re[j], re[i]);
                (im[i], im[j]) = (im[j], im[i]);
            }
        }

        // Butterfly passes.
        for (var len = 2; len <= n; len <<= 1)
        {
            var ang = -2f * MathF.PI / len;
            var wRe = MathF.Cos(ang);
            var wIm = MathF.Sin(ang);

            for (var i = 0; i < n; i += len)
            {
                var curRe = 1f;
                var curIm = 0f;
                for (var j = 0; j < len / 2; j++)
                {
                    var uRe = re[i + j];
                    var uIm = im[i + j];
                    var vRe = re[i + j + len / 2] * curRe - im[i + j + len / 2] * curIm;
                    var vIm = re[i + j + len / 2] * curIm + im[i + j + len / 2] * curRe;

                    re[i + j]           = uRe + vRe;
                    im[i + j]           = uIm + vIm;
                    re[i + j + len / 2] = uRe - vRe;
                    im[i + j + len / 2] = uIm - vIm;

                    var nextRe = curRe * wRe - curIm * wIm;
                    curIm      = curRe * wIm + curIm * wRe;
                    curRe      = nextRe;
                }
            }
        }
    }
}
