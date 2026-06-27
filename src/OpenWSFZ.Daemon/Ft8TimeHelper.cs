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
}
