namespace OpenWSFZ.Abstractions;

/// <summary>
/// A single prefix-range → region mapping entry in <c>callsign-regions.json</c>,
/// modelled on the ham-radio-community "country file" (<c>cty.dat</c>-style)
/// convention. Advisory only — never affects decode accept/reject decisions.
/// </summary>
/// <param name="PrefixStart">
/// Lower bound (inclusive) of the prefix range this entry covers, compared
/// lexicographically against a callsign token's leading characters of the same length.
/// </param>
/// <param name="PrefixEnd">Upper bound (inclusive) of the prefix range. Must be the same length as <paramref name="PrefixStart"/>.</param>
/// <param name="Entity">Country/administration (or entity) name, e.g. <c>"Monaco"</c>.</param>
/// <param name="Continent">
/// Continent code (e.g. <c>"EU"</c>), or <c>null</c> when not yet sourced (acceptable —
/// see <c>region-lookup</c> capability's partial-coverage non-goal) or not applicable
/// (the synthetic entry).
/// </param>
/// <param name="CqZone">CQ zone number, or <c>null</c> when not sourced.</param>
/// <param name="ItuZone">ITU zone number, or <c>null</c> when not sourced.</param>
/// <param name="Synthetic">
/// <c>true</c> for the dedicated entry mapping this project's synthetic-callsign
/// convention (NFR-021, the <c>Q</c>-prefix series) to the distinct
/// <c>"Synthetic (R&amp;R Study)"</c> region, so synthetic test traffic is never
/// misattributed to a real entity.
/// </param>
public sealed record CallsignRegionEntry(
    string  PrefixStart,
    string  PrefixEnd,
    string  Entity,
    string? Continent,
    int?    CqZone,
    int?    ItuZone,
    bool    Synthetic = false);

/// <summary>
/// The resolved region for a decoded callsign-position token, attached to the
/// decode-result payload for GUI display (<c>region-lookup</c> capability).
/// </summary>
/// <param name="Continent">
/// Continent code, or <c>null</c> for the synthetic region (no continent segment
/// is rendered for synthetic entries).
/// </param>
/// <param name="Entity">Country/administration name, or the synthetic label <c>"Synthetic (R&amp;R Study)"</c>.</param>
/// <param name="Synthetic">
/// <c>true</c> when this is the project's synthetic-callsign region — the frontend
/// renders <see cref="Entity"/> verbatim with no continent prefix in this case.
/// </param>
/// <param name="CqZone">
/// CQ zone number of the matched entry, or <c>null</c> when not sourced or not applicable
/// (e.g. the synthetic entry). Not rendered by the main decode-result table; surfaced for the
/// region-data lookup diagnostic tool (region-lookup-data-refresh).
/// </param>
/// <param name="ItuZone">
/// ITU zone number of the matched entry, or <c>null</c> when not sourced or not applicable
/// (e.g. the synthetic entry). Not rendered by the main decode-result table; surfaced for the
/// region-data lookup diagnostic tool (region-lookup-data-refresh).
/// </param>
public sealed record RegionInfo(
    string? Continent,
    string  Entity,
    bool    Synthetic,
    int?    CqZone  = null,
    int?    ItuZone = null);

/// <summary>
/// A resolved region-store prefix match, pairing the matched <see cref="RegionInfo"/> with the
/// length of the prefix range that matched (<c>engagement-target-validation</c> capability).
/// Needed alongside <see cref="RegionInfo"/> so a consumer can determine exactly where the match
/// ends within the original token — <see cref="RegionInfo"/> alone carries no positional
/// information.
/// </summary>
/// <param name="Region">The matched region, identical to what <see cref="ICallsignRegionStore.TryGetRegion"/> would return.</param>
/// <param name="MatchedPrefixLength">
/// The length, in characters, of the matched <see cref="CallsignRegionEntry.PrefixStart"/> range —
/// i.e. the index into the original token immediately following the matched prefix.
/// </param>
public sealed record CallsignRegionMatch(RegionInfo Region, int MatchedPrefixLength);
