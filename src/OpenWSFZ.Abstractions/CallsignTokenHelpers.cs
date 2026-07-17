namespace OpenWSFZ.Abstractions;

/// <summary>
/// Shared, dependency-free helpers for manipulating callsign-position tokens. Promoted out of
/// <c>OpenWSFZ.Ft8.Ft8Decoder</c> (engagement-target-validation, task 2.1) so
/// <c>OpenWSFZ.Daemon</c>'s <c>EngagementTargetValidator</c> can reuse the exact same
/// portable-suffix split <c>Ft8Decoder</c> already uses for shape-grammar evaluation, without a
/// second, potentially-drifting copy of the logic.
/// </summary>
public static class CallsignTokenHelpers
{
    /// <summary>
    /// Splits off a <c>/</c>-delimited portable suffix (e.g. <c>/P</c>, <c>/M</c>, <c>/QRP</c>, or
    /// a compound second callsign), returning only the base callsign before the slash.
    /// </summary>
    /// <param name="token">The callsign-position token to strip.</param>
    /// <returns><paramref name="token"/> unchanged if it contains no <c>/</c>, otherwise everything before the first <c>/</c>.</returns>
    public static string StripPortableSuffix(string token)
    {
        int slashPos = token.IndexOf('/');
        return slashPos >= 0 ? token[..slashPos] : token;
    }
}
