using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// decode-early-batch-panel (design.md D5): the pure, deterministic rule that decides which early rows the cycle's final
/// decode (batch 1) <b>confirms</b>.
///
/// <para>
/// Rule: for each final row, in order, take the still-unmatched early row with the <b>same message text</b> and the
/// smallest <c>|Δf|</c>, provided <c>|Δf| &lt;= <see cref="MaxFrequencyDeltaHz"/></c>; on a tie in <c>|Δf|</c> the
/// <b>earlier</b> early row wins. One-to-one: an early row confirms at most one final row and the reverse. Every early row
/// that is not taken is <b>unconfirmed</b>. No state, no clock, no randomness.
/// </para>
/// </summary>
internal static class EarlyDecodeMatcher
{
    /// <summary>The largest frequency difference, in Hz, between an early row and a final row that still counts as the same signal.</summary>
    internal const int MaxFrequencyDeltaHz = 10;

    /// <summary>
    /// Matches <paramref name="early"/> against <paramref name="final"/> (the visible batch-1 rows, in the order they are
    /// published). Returns one resolution per early row, in the early rows' order.
    /// </summary>
    internal static IReadOnlyList<EarlyResolution> Match(
        IReadOnlyList<EarlyRow> early, IReadOnlyList<DecodeResult> final)
    {
        var finalIndexOfEarly = new int[early.Count];
        Array.Fill(finalIndexOfEarly, -1);

        for (int f = 0; f < final.Count; f++)
        {
            int best      = -1;
            int bestDelta = int.MaxValue;
            for (int e = 0; e < early.Count; e++)
            {
                if (finalIndexOfEarly[e] >= 0) continue;                         // already matched
                var candidate = early[e].Decode;
                if (!string.Equals(candidate.Message, final[f].Message, StringComparison.Ordinal)) continue;
                int delta = Math.Abs(candidate.FreqHz - final[f].FreqHz);
                if (delta > MaxFrequencyDeltaHz) continue;
                if (delta < bestDelta)                                           // strict <: a tie keeps the earlier early row
                {
                    best      = e;
                    bestDelta = delta;
                }
            }
            if (best >= 0) finalIndexOfEarly[best] = f;
        }

        var result = new List<EarlyResolution>(early.Count);
        for (int e = 0; e < early.Count; e++)
            result.Add(finalIndexOfEarly[e] >= 0
                ? new EarlyResolution(early[e].EarlyId, EarlyResolution.Confirmed, finalIndexOfEarly[e])
                : new EarlyResolution(early[e].EarlyId, EarlyResolution.Unconfirmed));
        return result;
    }
}
