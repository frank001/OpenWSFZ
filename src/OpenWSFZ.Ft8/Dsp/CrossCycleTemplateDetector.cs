using System.Buffers;

namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// XC-BUILD R5: the known-message (template) detector. A message that is known in full fixes all 79 tones, so no LDPC is needed: the statistic is the mean over the 79 symbols of
/// <c>P[known tone] / mean over the 8 bins of P</c> (noise alone is about 1, a perfect signal approaches 8), searched over a window around a prior's position, keeping the maximum.
///
/// <para>
/// Managed C# only (no native code). It is a port of the desk detector, QA's <c>qa/xc-template/xt_lib.py</c> (<c>s_e</c>, <c>shift_baseband</c>, <c>search</c>) on
/// <c>qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py</c> (<c>downconvert_decimate</c>, <c>correlate_symbols</c>, lines 101 to 157): mix to baseband at the carrier, a 61-tap Hann-windowed-sinc low-pass
/// (900 Hz at 12 kHz, unit DC gain), decimate by 6 to 2000 Hz, then per symbol a 320-point DFT at bins 0 to 7 (6.25 Hz apart), symbols outside the buffer zero-padded. The fixtures
/// (<c>dev-tasks/2026-11-13-xc-template-fixtures.json</c>) pin the numbers: S_E* within 1e-3 relative and the argmax equal.
/// </para>
///
/// <para>
/// Two things are done differently from the reference for speed, and neither changes a number beyond double rounding: (1) the DFT of a symbol's 320 samples is ROLLED from one start time
/// to the next (the 25 start times are 20 samples apart): the update drops 20 samples, adds 20 and rotates, instead of a new 320 x 8 product; (2) the mixer and the frequency shift use a phasor
/// recurrence re-seeded from an exact <c>sin</c>/<c>cos</c> every 256 samples.
/// </para>
///
/// <para>Pure and thread-safe: no shared mutable state (scratch arrays come from <see cref="ArrayPool{T}.Shared"/>), so any number of templates can be searched in parallel.</para>
/// </summary>
internal static class CrossCycleTemplateDetector
{
    /// <summary>The audio sample rate of the 15 s cycle buffer.</summary>
    internal const int SampleRateHz = 12_000;

    /// <summary>Samples in the cycle buffer (15 s at <see cref="SampleRateHz"/>).</summary>
    internal const int BufferSamples = 180_000;

    /// <summary>The decimation factor to the baseband rate (<c>REFINE_DECIM_FINE</c>).</summary>
    internal const int Decimation = 6;

    /// <summary>The baseband rate, <see cref="SampleRateHz"/> / <see cref="Decimation"/>.</summary>
    internal const int BasebandRateHz = SampleRateHz / Decimation;

    /// <summary>Baseband samples per symbol (0.16 s at 2000 Hz): 2000 / 320 = 6.25 Hz, the tone spacing exactly, so the 8 tones sit on exactly orthogonal bins.</summary>
    internal const int SymbolSamples = 320;

    /// <summary>FT8 channel symbols per message.</summary>
    internal const int SymbolCount = 79;

    /// <summary>Tones (bins) per symbol.</summary>
    internal const int ToneCount = 8;

    /// <summary>The low-pass length (<c>REFINE_LP_TAPS_FINE</c>).</summary>
    internal const int LowPassTaps = 61;

    /// <summary>The low-pass cut-off in Hz (<c>REFINE_LP_CUTOFF_FINE_HZ</c>).</summary>
    internal const double LowPassCutoffHz = 900.0;

    /// <summary>
    /// The frozen start-minus-dt, in seconds: the start of symbol 0 in the cycle buffer is the published dt plus this. It is TA-CHECK's frozen difference between WSJT-X's dt convention and the product's
    /// start convention (XC-TEMPLATE / XC-BUILD spec R5; the fixtures' <c>calibration_start_minus_dt_s</c>).
    /// </summary>
    internal const double CalibrationStartMinusDtS = 0.48;

    /// <summary>The search half-window in frequency (XC-TEMPLATE A1.3: inside the +-3.125 Hz gate) and its step.</summary>
    internal const double FreqHalfWindowHz = 3.0, FreqStepHz = 0.5;

    /// <summary>The search half-window in start time and its step (inside the 0.12 s gate).</summary>
    internal const double DtHalfWindowS = 0.12, DtStepS = 0.01;

    /// <summary>The number of frequency steps (13) and start times (25) in the search window.</summary>
    internal const int FreqSteps = 13, DtSteps = 25;

    private const int DtStrideSamples = 20;          // DtStepS x BasebandRateHz: the roll between neighbouring start times
    private const int PhasorReseedBlock = 256;       // samples between exact sin/cos re-seeds of the phasor recurrences

    /// <summary>The coherent SNR conversion from one 6.25 Hz tone bin to a 2500 Hz noise bandwidth (<c>CF_SNR_BIN_TO_2500_DB</c> in the native coherent fallback).</summary>
    internal const double SnrBinTo2500Db = -26.0206;

    /// <summary>The lowest SNR the coherent estimate reports (<c>CF_SNR_FLOOR_DB</c>).</summary>
    internal const double SnrFloorDb = -30.0;

    /// <summary>The result of a window search: the maximum statistic and its position (absolute frequency in Hz; dt in the same convention as the centre dt that was passed in).</summary>
    /// <param name="SStar">S_E*, the maximum of S_E over the window.</param>
    /// <param name="FreqHz">The frequency of the argmax, Hz.</param>
    /// <param name="Dt">The dt of the argmax, seconds.</param>
    internal readonly record struct SearchResult(double SStar, double FreqHz, double Dt);

    private static readonly double[] Taps = DesignLowPassHann(LowPassTaps, LowPassCutoffHz, SampleRateHz);

    /// <summary>The 61 low-pass taps (a copy), for the fixtures' check.</summary>
    internal static double[] LowPassTapsCopy() => (double[])Taps.Clone();

    // The 320 x 8 DFT matrix W[n][b] = exp(-j 2 pi n b / 320): cos and sin parts, row n, column b.
    private static readonly double[] DftCos = new double[SymbolSamples * ToneCount];
    private static readonly double[] DftSin = new double[SymbolSamples * ToneCount];

    // The rotation applied after a roll of DtStrideSamples samples: exp(+j 2 pi b 20 / 320), per bin.
    private static readonly double[] RollCos = new double[ToneCount];
    private static readonly double[] RollSin = new double[ToneCount];

    static CrossCycleTemplateDetector()
    {
        for (int n = 0; n < SymbolSamples; n++)
        {
            for (int b = 0; b < ToneCount; b++)
            {
                double theta = 2.0 * Math.PI * ((n * b) % SymbolSamples) / SymbolSamples;
                DftCos[n * ToneCount + b] = Math.Cos(theta);
                DftSin[n * ToneCount + b] = Math.Sin(theta);   // W = cos - j sin
            }
        }
        for (int b = 0; b < ToneCount; b++)
        {
            double theta = 2.0 * Math.PI * b * DtStrideSamples / SymbolSamples;
            RollCos[b] = Math.Cos(theta);
            RollSin[b] = Math.Sin(theta);
        }
    }

    /// <summary>Hann-windowed-sinc low-pass, unit DC gain: the same design as <c>coherent_extract.design_lowpass_hann</c> (and the native <c>design_lowpass_hann</c>).</summary>
    internal static double[] DesignLowPassHann(int ntaps, double cutoffHz, double fsHz)
    {
        int mid = ntaps / 2;
        double fc = cutoffHz / fsHz;
        var taps = new double[ntaps];
        double sum = 0.0;
        for (int n = 0; n < ntaps; n++)
        {
            int k = n - mid;
            double sinc = k == 0 ? 2.0 * fc : Math.Sin(2.0 * Math.PI * fc * k) / (Math.PI * k);
            double window = 0.5 - 0.5 * Math.Cos(2.0 * Math.PI * n / (ntaps - 1));
            taps[n] = sinc * window;
            sum += taps[n];
        }
        if (sum != 0.0)
            for (int n = 0; n < ntaps; n++) taps[n] /= sum;
        return taps;
    }

    /// <summary>
    /// The window's frequency offsets, Hz, ascending (13 values, -3.0 to +3.0). The reference's <c>df_grid</c>.
    /// </summary>
    internal static double FreqOffsetHz(int index) => (index - FreqSteps / 2) * FreqStepHz;

    /// <summary>The window's start-time offsets, seconds, ascending (25 values, -0.12 to +0.12). The reference's <c>dt_grid</c>.</summary>
    internal static double DtOffsetS(int index) => (index - DtSteps / 2) * DtStepS;

    /// <summary>
    /// S_E* over the window around (<paramref name="centreFreqHz"/>, <paramref name="centreDt"/>) on <paramref name="pcm"/> for the message whose 79 tones are <paramref name="tones"/>,
    /// and the argmax. The search order and the strict greater-than are the reference's (frequency outer, start time inner, the first maximum wins).
    /// </summary>
    /// <param name="pcm">The cycle buffer, 180 000 samples at 12 kHz. Read only.</param>
    /// <param name="centreFreqHz">The prior's frequency, Hz (the carrier of the one downconvert).</param>
    /// <param name="centreDt">The prior's dt in the published convention; the start of symbol 0 is <c>dt + <see cref="CalibrationStartMinusDtS"/></c>.</param>
    /// <param name="tones">The 79 known tones, each 0 to 7.</param>
    internal static SearchResult Search(ReadOnlySpan<float> pcm, double centreFreqHz, double centreDt, ReadOnlySpan<byte> tones)
    {
        var grid = new double[FreqSteps * DtSteps];
        Grid(pcm, centreFreqHz, centreDt, tones, grid);

        double best = -1.0;
        int bestF = 0, bestK = 0;
        for (int fi = 0; fi < FreqSteps; fi++)
        {
            for (int k = 0; k < DtSteps; k++)
            {
                double v = grid[fi * DtSteps + k];
                if (v > best) { best = v; bestF = fi; bestK = k; }
            }
        }
        return new SearchResult(best, centreFreqHz + FreqOffsetHz(bestF), centreDt + DtOffsetS(bestK));
    }

    /// <summary>
    /// S_E at every position of the window, row-major <c>[frequency index * 25 + start-time index]</c> (13 x 25 = 325 values), by one downconvert at the centre and the shifted baseband for the other
    /// frequencies. <see cref="Search"/> takes the maximum; the tests compare cells with a direct computation.
    /// </summary>
    internal static void Grid(ReadOnlySpan<float> pcm, double centreFreqHz, double centreDt, ReadOnlySpan<byte> tones, double[] gridOut)
    {
        if (tones.Length != SymbolCount) throw new ArgumentException("A message has exactly 79 tones.", nameof(tones));
        if (gridOut.Length < FreqSteps * DtSteps) throw new ArgumentException("gridOut must hold 13 x 25 values.", nameof(gridOut));

        int n2k = (pcm.Length + Decimation - 1) / Decimation;
        double[] bbRe = ArrayPool<double>.Shared.Rent(n2k), bbIm = ArrayPool<double>.Shared.Rent(n2k);
        double[] sbRe = ArrayPool<double>.Shared.Rent(n2k), sbIm = ArrayPool<double>.Shared.Rent(n2k);
        try
        {
            DownconvertDecimate(pcm, centreFreqHz, bbRe, bbIm);

            // The start sample of every start time in the window, exactly as the reference forms it: round((dt_c + e + calibration) x 2000), banker's rounding as numpy's round.
            Span<int> starts = stackalloc int[DtSteps];
            for (int k = 0; k < DtSteps; k++)
                starts[k] = (int)Math.Round((centreDt + DtOffsetS(k) + CalibrationStartMinusDtS) * BasebandRateHz);

            for (int fi = 0; fi < FreqSteps; fi++)
            {
                var row = gridOut.AsSpan(fi * DtSteps, DtSteps);
                row.Clear();
                ShiftBaseband(bbRe, bbIm, n2k, FreqOffsetHz(fi), sbRe, sbIm);
                AccumulateRatios(sbRe, sbIm, n2k, starts, tones, row);
                for (int k = 0; k < DtSteps; k++) row[k] /= SymbolCount;
            }
        }
        finally
        {
            ArrayPool<double>.Shared.Return(bbRe); ArrayPool<double>.Shared.Return(bbIm);
            ArrayPool<double>.Shared.Return(sbRe); ArrayPool<double>.Shared.Return(sbIm);
        }
    }

    /// <summary>
    /// S_E at ONE position: a direct downconvert at <paramref name="freqHz"/> and the 79 x 8 correlation at the start <c>round((dt + calibration) x 2000)</c>. The fixtures use it to localise a porting error
    /// (the per-symbol bin powers at the true position); the stage uses it for the SNR of a detection.
    /// </summary>
    internal static double StatisticAt(ReadOnlySpan<float> pcm, double freqHz, double dt, ReadOnlySpan<byte> tones)
    {
        var p = new double[SymbolCount * ToneCount];
        BinPowersAt(pcm, freqHz, dt, p);
        return StatisticFromPowers(p, tones);
    }

    /// <summary>The 79 x 8 bin powers <c>P[k][b] = |X_k[b]|^2</c> at one position (row-major, <c>k * 8 + b</c>), a direct downconvert at <paramref name="freqHz"/>.</summary>
    internal static void BinPowersAt(ReadOnlySpan<float> pcm, double freqHz, double dt, Span<double> p)
    {
        if (p.Length < SymbolCount * ToneCount) throw new ArgumentException("p must hold 79 x 8 values.", nameof(p));
        int n2k = (pcm.Length + Decimation - 1) / Decimation;
        double[] bbRe = ArrayPool<double>.Shared.Rent(n2k), bbIm = ArrayPool<double>.Shared.Rent(n2k);
        try
        {
            DownconvertDecimate(pcm, freqHz, bbRe, bbIm);
            int start = (int)Math.Round((dt + CalibrationStartMinusDtS) * BasebandRateHz);
            Span<double> xr = stackalloc double[ToneCount], xi = stackalloc double[ToneCount];
            for (int k = 0; k < SymbolCount; k++)
            {
                ChunkDft(bbRe, bbIm, n2k, start + k * SymbolSamples, xr, xi);
                for (int b = 0; b < ToneCount; b++) p[k * ToneCount + b] = xr[b] * xr[b] + xi[b] * xi[b];
            }
        }
        finally
        {
            ArrayPool<double>.Shared.Return(bbRe); ArrayPool<double>.Shared.Return(bbIm);
        }
    }

    /// <summary>S_E from the 79 x 8 powers: the mean over symbols of <c>P[tone] / (sum_b P / 8)</c>; a symbol without power counts 1.</summary>
    internal static double StatisticFromPowers(ReadOnlySpan<double> p, ReadOnlySpan<byte> tones)
    {
        double sum = 0.0;
        for (int k = 0; k < SymbolCount; k++) sum += Ratio(p.Slice(k * ToneCount, ToneCount), tones[k]);
        return sum / SymbolCount;
    }

    private static double Ratio(ReadOnlySpan<double> bins, int tone)
    {
        double den = 0.0;
        for (int b = 0; b < ToneCount; b++) den += bins[b];
        den /= ToneCount;
        return den > 0.0 ? bins[tone] / den : 1.0;
    }

    /// <summary>
    /// The coherent SNR in dB (2500 Hz reference) of the template at (<paramref name="freqHz"/>, <paramref name="dt"/>): the managed equivalent of the native <c>cf_snr_db</c> that every fallback row's SNR
    /// comes from (<c>coherent_fallback.c</c>: selected tone's mean power S + N, every other tone's N, SNR = (S/N) x (6.25 / 2500); floored at <see cref="SnrFloorDb"/>), rounded half away from zero as the
    /// native <c>lround</c> does (<c>ft8_shim.c</c>: <c>o->snr_db = (int)lround(isfinite(snr) ? snr : CF_SNR_FLOOR_DB)</c>).
    /// </summary>
    internal static int CoherentSnrDb(ReadOnlySpan<float> pcm, double freqHz, double dt, ReadOnlySpan<byte> tones)
    {
        var p = new double[SymbolCount * ToneCount];
        BinPowersAt(pcm, freqHz, dt, p);
        return CoherentSnrDbFromPowers(p, tones);
    }

    /// <summary>The same from the 79 x 8 powers (the part that mirrors <c>cf_snr_db</c>).</summary>
    internal static int CoherentSnrDbFromPowers(ReadOnlySpan<double> p, ReadOnlySpan<byte> tones)
    {
        double sel = 0.0, oth = 0.0;
        for (int k = 0; k < SymbolCount; k++)
        {
            for (int b = 0; b < ToneCount; b++)
            {
                if (b == tones[k]) sel += p[k * ToneCount + b]; else oth += p[k * ToneCount + b];
            }
        }
        sel /= SymbolCount;
        oth /= SymbolCount * (ToneCount - 1);
        double snr;
        if (!(oth > 0.0)) snr = SnrFloorDb;                         // NaN in the native, which the caller maps to the floor
        else
        {
            double sig = sel - oth;
            if (!(sig > 0.0)) snr = SnrFloorDb;
            else snr = Math.Max(SnrFloorDb, 10.0 * Math.Log10(sig / oth) + SnrBinTo2500Db);
        }
        return (int)Math.Round(snr, MidpointRounding.AwayFromZero);
    }

    /// <summary>
    /// <c>downconvert_decimate</c>: mix to baseband at <paramref name="carrierHz"/>, low-pass, keep every sixth sample. Output index m is the reference's <c>convolve(mixed, taps, 'same')[6 m]</c>
    /// (symmetric odd-length taps: <c>sum_t taps[t] mixed[6m - 30 + t]</c>, zero outside the buffer).
    /// </summary>
    internal static void DownconvertDecimate(ReadOnlySpan<float> pcm, double carrierHz, double[] outRe, double[] outIm)
    {
        int n = pcm.Length;
        int n2k = (n + Decimation - 1) / Decimation;
        double[] mRe = ArrayPool<double>.Shared.Rent(n), mIm = ArrayPool<double>.Shared.Rent(n);
        try
        {
            double w = 2.0 * Math.PI * carrierHz / SampleRateHz;
            double stepC = Math.Cos(w), stepS = Math.Sin(w);   // exp(-j w) = stepC - j stepS
            double c = 1.0, s = 0.0;                           // exp(-j w n) = c - j s
            for (int i = 0; i < n; i++)
            {
                if (i % PhasorReseedBlock == 0) { (double sn, double cs) = Math.SinCos(w * i); c = cs; s = sn; }
                double x = pcm[i];
                mRe[i] = x * c;
                mIm[i] = -x * s;
                double nc = c * stepC - s * stepS;             // (c - j s)(stepC - j stepS) = (c stepC - s stepS) - j (c stepS + s stepC)
                double ns = c * stepS + s * stepC;
                c = nc; s = ns;
            }

            int half = LowPassTaps / 2;
            for (int m = 0; m < n2k; m++)
            {
                int centre = m * Decimation;
                int first = centre - half;
                double accRe = 0.0, accIm = 0.0;
                if (first >= 0 && first + LowPassTaps <= n)
                {
                    for (int t = 0; t < LowPassTaps; t++)
                    {
                        double tap = Taps[t];
                        accRe += tap * mRe[first + t];
                        accIm += tap * mIm[first + t];
                    }
                }
                else
                {
                    for (int t = 0; t < LowPassTaps; t++)
                    {
                        int idx = first + t;
                        if ((uint)idx >= (uint)n) continue;
                        double tap = Taps[t];
                        accRe += tap * mRe[idx];
                        accIm += tap * mIm[idx];
                    }
                }
                outRe[m] = accRe;
                outIm[m] = accIm;
            }
        }
        finally
        {
            ArrayPool<double>.Shared.Return(mRe); ArrayPool<double>.Shared.Return(mIm);
        }
    }

    /// <summary>The decimated baseband of a carrier <paramref name="deltaHz"/> higher: <c>bb[n] x exp(-j 2 pi delta n / 2000)</c> (the reference's <c>shift_baseband</c>; absolute index n).</summary>
    private static void ShiftBaseband(double[] re, double[] im, int n, double deltaHz, double[] outRe, double[] outIm)
    {
        if (deltaHz == 0.0)
        {
            Array.Copy(re, outRe, n);
            Array.Copy(im, outIm, n);
            return;
        }
        double w = 2.0 * Math.PI * deltaHz / BasebandRateHz;
        double stepC = Math.Cos(w), stepS = Math.Sin(w);
        double c = 1.0, s = 0.0;                               // exp(-j w n) = c - j s
        for (int i = 0; i < n; i++)
        {
            if (i % PhasorReseedBlock == 0) { (double sn, double cs) = Math.SinCos(w * i); c = cs; s = sn; }
            outRe[i] = re[i] * c + im[i] * s;                  // (re + j im)(c - j s)
            outIm[i] = im[i] * c - re[i] * s;
            double nc = c * stepC - s * stepS;
            double ns = c * stepS + s * stepC;
            c = nc; s = ns;
        }
    }

    /// <summary>
    /// For one frequency (the shifted baseband): add, into <paramref name="ratioSum"/>[k] (k = start time index), the per-symbol ratios of all 79 symbols. A symbol whose chunks stay inside the
    /// buffer for every start time is ROLLED from one start to the next; any other symbol is computed directly with zero padding.
    /// </summary>
    private static void AccumulateRatios(double[] re, double[] im, int n, ReadOnlySpan<int> starts, ReadOnlySpan<byte> tones, Span<double> ratioSum)
    {
        Span<double> xr = stackalloc double[ToneCount], xi = stackalloc double[ToneCount];
        Span<double> bins = stackalloc double[ToneCount];
        for (int sym = 0; sym < SymbolCount; sym++)
        {
            int tone = tones[sym];
            int offset = sym * SymbolSamples;
            for (int k = 0; k < DtSteps; k++)
            {
                int s = starts[k] + offset;
                bool rolled = false;
                if (k > 0 && starts[k] - starts[k - 1] == DtStrideSamples)
                {
                    int prev = s - DtStrideSamples;
                    if (prev >= 0 && s + SymbolSamples <= n)
                    {
                        Roll(re, im, prev, xr, xi);
                        rolled = true;
                    }
                }
                if (!rolled) ChunkDft(re, im, n, s, xr, xi);
                for (int b = 0; b < ToneCount; b++) bins[b] = xr[b] * xr[b] + xi[b] * xi[b];
                ratioSum[k] += Ratio(bins, tone);
            }
        }
    }

    /// <summary>
    /// The 8 bins of the 320-sample chunk starting at <paramref name="start"/>, with samples outside [0, n) as zero (<c>correlate_symbols</c>): <c>X[b] = sum_m x[start + m] exp(-j 2 pi b m / 320)</c>.
    /// </summary>
    private static void ChunkDft(double[] re, double[] im, int n, int start, Span<double> xr, Span<double> xi)
    {
        xr.Clear(); xi.Clear();
        int lo = Math.Max(start, 0), hi = Math.Min(start + SymbolSamples, n);
        for (int idx = lo; idx < hi; idx++)
        {
            int m = idx - start;
            double a = re[idx], bq = im[idx];
            int row = m * ToneCount;
            for (int b = 0; b < ToneCount; b++)
            {
                double c = DftCos[row + b], sn = DftSin[row + b];
                xr[b] += a * c + bq * sn;                      // (a + j bq)(c - j sn)
                xi[b] += bq * c - a * sn;
            }
        }
    }

    /// <summary>
    /// Roll a chunk's bins from start <paramref name="prev"/> to <c>prev + 20</c> in place: <c>X' = exp(+j 2 pi b 20 / 320) x (X + sum_{i&lt;20} (x[prev + 320 + i] - x[prev + i]) W[i][b])</c>.
    /// The caller guarantees <c>prev &gt;= 0</c> and <c>prev + 340 &lt;= n</c>; <paramref name="xr"/>/<paramref name="xi"/> hold the bins of the chunk at <paramref name="prev"/>.
    /// </summary>
    private static void Roll(double[] re, double[] im, int prev, Span<double> xr, Span<double> xi)
    {
        for (int i = 0; i < DtStrideSamples; i++)
        {
            double dr = re[prev + SymbolSamples + i] - re[prev + i];
            double di = im[prev + SymbolSamples + i] - im[prev + i];
            int row = i * ToneCount;
            for (int b = 0; b < ToneCount; b++)
            {
                double c = DftCos[row + b], sn = DftSin[row + b];
                xr[b] += dr * c + di * sn;
                xi[b] += di * c - dr * sn;
            }
        }
        for (int b = 0; b < ToneCount; b++)
        {
            double r = xr[b], q = xi[b];
            xr[b] = r * RollCos[b] - q * RollSin[b];           // (r + j q)(cos + j sin)
            xi[b] = r * RollSin[b] + q * RollCos[b];
        }
    }
}
