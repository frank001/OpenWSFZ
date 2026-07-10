namespace OpenWSFZ.Abstractions;

/// <summary>
/// Daemon-owned, ephemeral, shared filter state for <c>#decodes-table</c> and the automation
/// engagement-decision point in <c>QsoAnswererService</c>/<c>QsoCallerService</c>
/// (<c>decode-panel-filtering</c> capability, design.md Decision 1). Nine independent axes,
/// always AND'd together: four attribute allow-lists (DXCC entity, Continent, CQ Zone, ITU
/// Zone) and five worked-before tri-state selections, one per
/// <c>qso-confirmation-band-awareness</c> dimension (Contact/Country/Continent/CqZone/ItuZone).
/// </summary>
/// <remarks>
/// <c>null</c> (not an empty set) means "no restriction on this axis" — the default,
/// all-selected state. An empty, non-null set means "nothing passes this axis," a valid state
/// an operator can reach by unchecking every value in a popup, distinct from an axis that has
/// never been touched. See <see cref="DecodeFilterEvaluator"/> for the evaluation predicate.
/// <para>
/// design.md Decision 1 specifies these axes as <c>IReadOnlySet&lt;T&gt;?</c>; the concrete
/// <see cref="HashSet{T}"/>? used here is an implementation detail, not a behavioural
/// deviation — <c>System.Text.Json</c>'s source generator cannot deserialise an interface-typed
/// collection (<c>IReadOnlySet&lt;T&gt;</c> has no public constructor/factory it can target),
/// which every axis here must support since <see cref="DecodeFilterState"/> is both a REST
/// request/response body and a WebSocket payload.
/// </para>
/// </remarks>
/// <param name="AllowedEntities">DXCC entity allow-list, or <c>null</c> for no restriction.</param>
/// <param name="AllowedContinents">Continent-code allow-list, or <c>null</c> for no restriction.</param>
/// <param name="AllowedCqZones">CQ zone allow-list, or <c>null</c> for no restriction.</param>
/// <param name="AllowedItuZones">ITU zone allow-list, or <c>null</c> for no restriction.</param>
/// <param name="ContactStates">Contact (Ctc) worked-before selection, or <c>null</c> for no restriction.</param>
/// <param name="CountryStates">Country (DXCC) worked-before selection, or <c>null</c> for no restriction.</param>
/// <param name="ContinentStates">Continent (Cnt) worked-before selection, or <c>null</c> for no restriction.</param>
/// <param name="CqZoneStates">CQ Zone worked-before selection, or <c>null</c> for no restriction.</param>
/// <param name="ItuZoneStates">ITU Zone worked-before selection, or <c>null</c> for no restriction.</param>
public sealed record DecodeFilterState(
    HashSet<string>?            AllowedEntities   = null,
    HashSet<string>?            AllowedContinents = null,
    HashSet<int>?               AllowedCqZones    = null,
    HashSet<int>?               AllowedItuZones   = null,
    HashSet<WorkedBeforeState>? ContactStates     = null,
    HashSet<WorkedBeforeState>? CountryStates     = null,
    HashSet<WorkedBeforeState>? ContinentStates   = null,
    HashSet<WorkedBeforeState>? CqZoneStates      = null,
    HashSet<WorkedBeforeState>? ItuZoneStates     = null)
{
    /// <summary>The all-<c>null</c> default — no restriction on any axis, every decode passes.</summary>
    public static readonly DecodeFilterState Unfiltered = new();
}
