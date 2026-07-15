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

        var remainingSamples = (int)(remaining.TotalSeconds * sampleRateHz);
        return Math.Clamp(remainingSamples, 0, totalSampleCount);
    }
}
