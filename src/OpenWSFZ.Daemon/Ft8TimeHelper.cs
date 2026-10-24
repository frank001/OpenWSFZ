namespace OpenWSFZ.Daemon;

/// <summary>
/// Utility helpers for FT8 transmission timing (qso-log-dialog, task 4.3).
/// </summary>
internal static class Ft8TimeHelper
{
    /// <summary>
    /// Returns the FT8 cycle boundary immediately at or before <paramref name="utcNow"/>
    /// (i.e., floors the timestamp to the nearest 15-second boundary).
    /// <para>
    /// Used to derive the <c>QsoEndUtc</c> timestamp for the <c>qsoReview</c> WebSocket event:
    /// when the state machine enters <c>Tx73</c> / <c>TxRr73</c>, the 73 transmission is about
    /// to start at the next cycle boundary, which for practical purposes is well approximated
    /// by the floor of the current wall-clock time to 15 seconds.
    /// </para>
    /// </summary>
    internal static DateTime DeriveFt8CycleStartUtc(DateTime utcNow) =>
        new DateTime(
            utcNow.Year,
            utcNow.Month,
            utcNow.Day,
            utcNow.Hour,
            utcNow.Minute,
            (utcNow.Second / 15) * 15,
            0,
            DateTimeKind.Utc);

    /// <summary>
    /// Computes how many leading samples of a synthesised transmission buffer fit before the
    /// current 15-second FT8 cycle window closes, given <paramref name="now"/>.
    /// <para>
    /// Used by <c>QsoAnswererService.TransmitAsync</c> and <c>QsoCallerService.TransmitAsync</c>
    /// (D-CALLER-021: manual engages fire unconditionally once the phase is correct, but the
    /// transmission itself must never key past the window boundary) to truncate a transmission
    /// that starts late in its window, instead of always playing the full synthesised clip.
    /// </para>
    /// </summary>
    /// <param name="now">The moment the transmission is about to begin.</param>
    /// <param name="totalSampleCount">Length of the fully-synthesised sample buffer.</param>
    /// <param name="sampleRateHz">Sample rate of the buffer, in Hz.</param>
    /// <returns>
    /// The number of leading samples that fit before the window boundary, clamped to
    /// <c>[0, totalSampleCount]</c>. Zero means the window has already closed.
    /// </returns>
    internal static int ClampSampleCountToWindowBoundary(
        DateTimeOffset now, int totalSampleCount, int sampleRateHz)
    {
        var windowStart = new DateTimeOffset(
            now.Year, now.Month, now.Day, now.Hour, now.Minute, (now.Second / 15) * 15, 0,
            TimeSpan.Zero);
        var windowBoundary = windowStart + TimeSpan.FromSeconds(15);
        var remaining      = windowBoundary - now;
        if (remaining <= TimeSpan.Zero)
            return 0;

        // Integer tick arithmetic (#259): 12.64 s x 48 kHz must be exactly 606,720, not 606,719
        // from a floating-point truncation, or a whole clip starting at 2.36 s would be trimmed.
        var remainingSamples = remaining.Ticks * sampleRateHz / TimeSpan.TicksPerSecond;
        return (int)Math.Clamp(remainingSamples, 0, totalSampleCount);
    }

    // ── Late-start time alignment (#259) ─────────────────────────────────────────

    /// <summary>
    /// Nominal offset of the first symbol inside an on-time transmission (WSJT-X starts its tones
    /// 0.5 s into the slot). A late start skips <c>offset - this</c> of the clip so every
    /// remaining symbol still lands where a decoder expects it.
    /// </summary>
    private const long NominalStartTicks = TimeSpan.TicksPerSecond / 2;

    /// <summary>
    /// WSJT-X's cut-off: no transmission starts at or after this offset into the slot (11.25 s),
    /// because what would remain is too short to decode.
    /// </summary>
    internal static readonly TimeSpan LastStartOffset = TimeSpan.FromSeconds(11.25);

    /// <summary>The outcome of <see cref="AlignLateStart"/>.</summary>
    /// <param name="ShouldKey"><c>false</c> when the start is at or after the 11.25 s cut-off.</param>
    /// <param name="Offset">Time since the start of the current 15 s slot.</param>
    /// <param name="SkipSamples">Leading samples of the clip to drop (0 for an on-time start).</param>
    /// <param name="LoadSamples">Samples to load after the skip (0 when not keyed).</param>
    internal readonly record struct LateStartAlignment(
        bool ShouldKey, TimeSpan Offset, int SkipSamples, int LoadSamples);

    /// <summary>Time elapsed since the start of the 15 s FT8 slot that contains <paramref name="now"/>.</summary>
    internal static TimeSpan OffsetIntoSlot(DateTimeOffset now)
    {
        var utc         = now.ToUniversalTime();
        var windowStart = new DateTimeOffset(
            utc.Year, utc.Month, utc.Day, utc.Hour, utc.Minute, (utc.Second / 15) * 15, 0,
            TimeSpan.Zero);
        return utc - windowStart;
    }

    /// <summary><c>true</c> when a start at <paramref name="now"/> is at or after the 11.25 s cut-off.</summary>
    internal static bool IsPastLastStart(DateTimeOffset now) => OffsetIntoSlot(now) >= LastStartOffset;

    /// <summary>
    /// Time-aligns a transmission that starts late in its slot, as WSJT-X does: the START of the
    /// clip is skipped so each symbol stays at its slot-relative time, instead of playing the clip
    /// from its first symbol and cutting the tail at the boundary (which would shift every symbol
    /// by the lateness, far outside a decoder's +-2.5 s sync search).
    /// <list type="bullet">
    /// <item>offset &lt;= slot - clip length (2.36 s for the 12.64 s clip): the whole clip, nothing skipped.</item>
    /// <item>up to the 11.25 s cut-off: skip <c>round((offset - 0.5 s) x rate)</c> samples, load the rest.</item>
    /// <item>offset &gt;= 11.25 s: do not key.</item>
    /// </list>
    /// Pure integer tick arithmetic, so the boundaries are exact.
    /// </summary>
    /// <param name="now">The moment the transmission is about to begin.</param>
    /// <param name="totalSampleCount">Length of the fully-synthesised clip.</param>
    /// <param name="sampleRateHz">Sample rate of the clip, in Hz.</param>
    internal static LateStartAlignment AlignLateStart(
        DateTimeOffset now, int totalSampleCount, int sampleRateHz)
    {
        var offset      = OffsetIntoSlot(now);
        var offsetTicks = offset.Ticks;

        if (offsetTicks >= LastStartOffset.Ticks)
            return new LateStartAlignment(false, offset, 0, 0);

        // Whole-clip threshold: offset <= slot - clip, i.e. offset * rate <= (slot*rate - total) seconds.
        var slotSamples = 15L * sampleRateHz;
        if (offsetTicks * sampleRateHz <= (slotSamples - totalSampleCount) * TimeSpan.TicksPerSecond)
            return new LateStartAlignment(true, offset, 0, totalSampleCount);

        // round((offset - 0.5 s) x rate), half up, in integer ticks.
        var skipNumerator = (offsetTicks - NominalStartTicks) * sampleRateHz;
        var skip = (int)Math.Clamp(
            (skipNumerator + TimeSpan.TicksPerSecond / 2) / TimeSpan.TicksPerSecond,
            0, totalSampleCount);
        return new LateStartAlignment(true, offset, skip, totalSampleCount - skip);
    }

    // ── Ramp where the clip is cut (#259, Architect Amendment 1) ────────────────

    /// <summary>
    /// Length of the raised-cosine ramp, in samples (5 ms at 48 kHz). The synthesiser has no
    /// envelope, so a clip cut at an arbitrary phase would step by up to +-0.5: a key click.
    /// </summary>
    internal const int RampSamples = 240;

    /// <summary>
    /// Gain of the fade-in at index <paramref name="i"/> (0 to <see cref="RampSamples"/> - 1):
    /// <c>0.5 x (1 - cos(pi x i / 239))</c>, so sample 0 is 0 and sample 239 is exactly 1.
    /// </summary>
    internal static double RampGain(int i)
        => 0.5 * (1.0 - Math.Cos(Math.PI * i / (RampSamples - 1)));

    /// <summary>Applies the raised-cosine fade-in to the first <see cref="RampSamples"/> samples, in place.</summary>
    internal static void ApplyFadeIn(float[] samples)
    {
        var n = Math.Min(RampSamples, samples.Length);
        for (var i = 0; i < n; i++)
            samples[i] = (float)(samples[i] * RampGain(i));
    }

    /// <summary>Applies the mirrored fade-out to the last <see cref="RampSamples"/> samples, in place.</summary>
    internal static void ApplyFadeOut(float[] samples)
    {
        var n = Math.Min(RampSamples, samples.Length);
        for (var j = 0; j < n; j++)
            samples[samples.Length - n + j] =
                (float)(samples[samples.Length - n + j] * RampGain(RampSamples - 1 - j));
    }

    /// <summary>The result of <see cref="ApplyLateStart"/>.</summary>
    /// <param name="Alignment">The decision (offset, skip, load, whether to key).</param>
    /// <param name="Samples">The samples to play, or <c>null</c> when not keyed. The input
    /// array itself when nothing was skipped; otherwise a new array.</param>
    internal readonly record struct LateStartResult(LateStartAlignment Alignment, float[]? Samples);

    /// <summary>
    /// <see cref="AlignLateStart"/> applied to <paramref name="clip"/>: drops the skipped leading
    /// samples and fades the new start in. A clip that is not skipped is returned untouched (the
    /// same array, no fade); the input array is never modified.
    /// </summary>
    internal static LateStartResult ApplyLateStart(DateTimeOffset now, float[] clip, int sampleRateHz)
    {
        var alignment = AlignLateStart(now, clip.Length, sampleRateHz);
        if (!alignment.ShouldKey) return new LateStartResult(alignment, null);
        if (alignment.SkipSamples == 0) return new LateStartResult(alignment, clip);

        var cut = clip[alignment.SkipSamples..];
        ApplyFadeIn(cut);
        return new LateStartResult(alignment, cut);
    }

    /// <summary>
    /// The window-boundary safety net (<see cref="ClampSampleCountToWindowBoundary"/>) applied to
    /// <paramref name="samples"/>: when it cuts the tail, the new tail is faded out. An uncut buffer
    /// is returned untouched (the same array); the input array is never modified.
    /// </summary>
    /// <param name="cutSamples">How many samples the clamp removed (0 when none).</param>
    internal static float[] ClampToWindowBoundary(
        DateTimeOffset now, float[] samples, int sampleRateHz, out int cutSamples)
    {
        var keep = ClampSampleCountToWindowBoundary(now, samples.Length, sampleRateHz);
        cutSamples = samples.Length - keep;
        if (cutSamples == 0) return samples;
        if (keep == 0) return [];

        var cut = samples[..keep];
        ApplyFadeOut(cut);
        return cut;
    }
}
