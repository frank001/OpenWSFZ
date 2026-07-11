using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Pure, static suppression gate for the <c>decode-noise-suppression</c> capability. Computes the
/// subset of a decode-cycle's <see cref="DecodeResult"/> list that should remain visible/engageable
/// after applying the operator's persisted Unknown-region and R&amp;R-synthetic suppression
/// settings.
///
/// <para>
/// Called exactly once per decode cycle from the daemon's decode-pump loop
/// (<c>Program.cs</c>), immediately after <c>Ft8Decoder.DecodeAsync</c> returns and before any
/// fan-out — the same filtered list is fed to the decode-panel WebSocket broadcast and both QSO
/// controller channels (design.md Decision 1). <c>ALL.TXT</c> continues to receive the unfiltered
/// <see cref="DecodeResult"/> list unchanged; this filter is never applied to it.
/// </para>
///
/// <para>
/// Deliberately a new, separate, operator-opt-in stage — not a change to <c>region-lookup</c>'s own
/// resolution logic (which is unmodified and still reaches <c>ALL.TXT</c>/the decode-result payload
/// exactly as before) and not a new axis of the ephemeral, per-session
/// <c>DecodeFilterState</c>/<c>DecodeFilterEvaluator</c> column filter (<c>decode-panel-filtering</c>
/// capability), which continues to apply downstream of this gate, unaffected (design.md Decisions
/// 1–2, Risks).
/// </para>
/// </summary>
public static class DecodeNoiseSuppressionFilter
{
    /// <summary>
    /// Returns the subset of <paramref name="results"/> that should remain visible/engageable
    /// after applying <paramref name="config"/>. Order and identity of surviving elements are
    /// preserved; nothing is ever added or duplicated.
    /// </summary>
    /// <param name="results">The raw decode-cycle results, as returned by the decoder.</param>
    /// <param name="config">The persisted decode-noise-suppression settings.</param>
    /// <param name="regionStore">
    /// Consulted only to resolve <see cref="DecodeNoiseSuppressionConfig.SuppressUnknownRegion"/>'s
    /// live default when its persisted value is <c>null</c> (see
    /// <see cref="ResolveEffectiveSuppressUnknownRegion"/>).
    /// </param>
    public static IReadOnlyList<DecodeResult> Apply(
        IReadOnlyList<DecodeResult>    results,
        DecodeNoiseSuppressionConfig   config,
        ICallsignRegionStore           regionStore)
    {
        if (results.Count == 0)
            return results;

        var suppressUnknown   = ResolveEffectiveSuppressUnknownRegion(config.SuppressUnknownRegion, regionStore);
        var suppressSynthetic = config.SuppressSynthetic;

        // Fast path: neither rule active — no allocation, return the input list as-is.
        if (!suppressUnknown && !suppressSynthetic)
            return results;

        List<DecodeResult>? visible = null;
        for (var i = 0; i < results.Count; i++)
        {
            var result     = results[i];
            var suppressed =
                (suppressUnknown   && result.Region is null) ||
                (suppressSynthetic && result.Region is { Synthetic: true });

            if (suppressed)
            {
                // First suppressed element found: lazily materialise the output list, seeded
                // with everything kept so far, so the common case (nothing suppressed this
                // cycle) never allocates.
                visible ??= new List<DecodeResult>(results.Take(i));
            }
            else
            {
                visible?.Add(result);
            }
        }

        return visible ?? results;
    }

    /// <summary>
    /// Resolves the effective (applied) value of the Unknown-region suppression setting
    /// (design.md Decision 3). Thin pass-through to
    /// <see cref="DecodeNoiseSuppressionDefaults.ResolveEffectiveSuppressUnknownRegion"/> — kept
    /// as a member here too so callers within the daemon can reach it via this filter's own
    /// surface, without a second implementation. See that method's doc comment for the resolution
    /// rule; see its containing type's doc comment for why the shared logic lives in
    /// <c>OpenWSFZ.Abstractions</c> rather than here (task 3.4 / the settings page's
    /// live-effective-value display in <c>OpenWSFZ.Web</c> needs the identical computation and
    /// cannot reference <c>OpenWSFZ.Daemon</c>).
    /// </summary>
    public static bool ResolveEffectiveSuppressUnknownRegion(bool? persisted, ICallsignRegionStore regionStore) =>
        DecodeNoiseSuppressionDefaults.ResolveEffectiveSuppressUnknownRegion(persisted, regionStore);
}
