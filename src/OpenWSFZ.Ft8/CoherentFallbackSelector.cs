using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8;

/// <summary>
/// COH-FALLBACK Stage 2, R6'' (Architect spec section 12, A12.1): which of a cycle's fallback outputs are published.
/// A candidate publishes when its BP output is CRC-valid, its payload is not one the ordinary decode produced, and its F1b is at
/// or below T1 (<see cref="CohFallbackState.NewGated"/>). Several candidates can carry the SAME payload (one signal found at two
/// lattice positions); of those, the one published is <b>the first, in candidate order, whose fine-sync estimate is not at the
/// window edge</b>, because an estimate on the edge of the search window is the one most likely to be a truncated, biased argmax. If every
/// member sits on the edge, the first of them is published. Deterministic: the same rows give the same selection.
/// </summary>
internal static class CoherentFallbackSelector
{
    /// <summary>Bytes of the 77-bit payload that identify a message (the first 10 of the 12 the native side reports).</summary>
    private const int PayloadKeyBytes = 10;

    /// <summary>
    /// The rows to publish, in candidate order. <paramref name="rows"/> is in candidate order, as
    /// <see cref="CohFallbackRunResult.Rows"/> is.
    /// </summary>
    public static IReadOnlyList<CohFallbackRow> Select(IReadOnlyList<CohFallbackRow> rows)
    {
        ArgumentNullException.ThrowIfNull(rows);

        // payload -> index of the row chosen so far
        var chosen = new Dictionary<string, int>(StringComparer.Ordinal);
        for (int i = 0; i < rows.Count; i++)
        {
            var row = rows[i];
            if (!row.IsPublishable) continue;   // NewGated, or a GatedOut row the audio merge admitted (COH-GATE-G R-F4)

            string key = Convert.ToHexString(row.Payload, 0, PayloadKeyBytes);
            if (!chosen.TryGetValue(key, out int at))
                chosen[key] = i;
            else if (rows[at].Edge && !row.Edge)
                chosen[key] = i;   // the first non-edge member replaces an edge one; later members never replace a non-edge one
        }

        var picked = chosen.Values.ToList();
        picked.Sort();
        return picked.Select(i => rows[i]).ToList();
    }
}
