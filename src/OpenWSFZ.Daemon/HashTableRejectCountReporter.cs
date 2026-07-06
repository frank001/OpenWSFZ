using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Writes the native session-scoped callsign hash-table reject count to the log as a single
/// end-of-session summary line at graceful daemon shutdown
/// (f-005-hash-table-saturation-diagnostic, design.md D2).
///
/// <para>
/// Extracted from <c>Program.cs</c>'s <c>ApplicationStopping</c> hook so the log-line wiring —
/// the exact thing the change's Risk 1 warns could be silently skipped or forgotten — is unit
/// testable without booting the full daemon host.
/// </para>
/// </summary>
internal static class HashTableRejectCountReporter
{
    /// <summary>
    /// Reads the reject count via <paramref name="rejectCountProvider"/> and logs it once at
    /// Information level. A non-zero value means the 256-slot table saturated during the session.
    /// <para>
    /// Any failure reading the native counter is swallowed (logged at Warning) so a best-effort
    /// diagnostic read can never block or fault the shutdown path.
    /// </para>
    /// </summary>
    /// <param name="logger">Destination logger (the daemon's startup/program logger).</param>
    /// <param name="rejectCountProvider">
    /// Supplies the current native reject count — production passes
    /// <c>() =&gt; ft8Decoder.GetHashTableRejectCount()</c>.
    /// </param>
    public static void Report(ILogger logger, Func<int> rejectCountProvider)
    {
        try
        {
            int rejectCount = rejectCountProvider();
            logger.LogInformation(
                "Hash table reject count (session): {RejectCount}. " +
                "Non-zero means the 256-slot callsign hash table saturated and one or more " +
                "Type 4 announcements could not be stored (f-005).",
                rejectCount);
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex,
                "Could not read the native hash-table reject count at shutdown.");
        }
    }
}
