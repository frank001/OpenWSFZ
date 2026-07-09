namespace OpenWSFZ.Abstractions;

/// <summary>
/// Advisory "worked before" state resolved for a decoded callsign-position token
/// (<c>qso-confirmation</c> capability), attached to the decode-result payload alongside
/// <see cref="RegionInfo"/>. Five independent, differently-scoped tri-state dimensions
/// (<c>qso-confirmation-band-awareness</c> design.md Decision 1):
/// <list type="bullet">
///   <item><see cref="Contact"/> — this exact station (or a portable-suffixed variant) has been
///   logged before, anywhere in <c>ADIF.log</c>'s history.</item>
///   <item><see cref="Country"/> — this station's DXCC entity has been logged before
///   (a different station, same country).</item>
///   <item><see cref="Continent"/> — this station's continent has been logged before (a different
///   station, possibly a different country, same continent). Strictly coarser than
///   <see cref="Country"/>.</item>
///   <item><see cref="CqZone"/> — this station's CQ zone has been logged before.</item>
///   <item><see cref="ItuZone"/> — this station's ITU zone has been logged before.</item>
/// </list>
/// Each dimension resolves to one of three states (<see cref="WorkedBeforeState"/>): never
/// worked (on this axis, any band), worked on a different band than the session's current
/// active band, or worked on the current band — any current-band match wins over a
/// different-band-only match. Never affects decode acceptance — a resolution failure of any
/// kind degrades to <see cref="None"/> (all five <see cref="WorkedBeforeState.Never"/>),
/// matching the <c>region-lookup</c> capability's existing advisory-only guarantee.
/// </summary>
/// <param name="Contact">Whether this callsign (or a portable-suffixed variant of it) has been worked before, band-aware.</param>
/// <param name="Country">Whether this callsign's resolved DXCC entity has been worked before, band-aware.</param>
/// <param name="Continent">Whether this callsign's resolved continent has been worked before, band-aware.</param>
/// <param name="CqZone">Whether this callsign's resolved CQ zone has been worked before, band-aware.</param>
/// <param name="ItuZone">Whether this callsign's resolved ITU zone has been worked before, band-aware.</param>
public sealed record WorkedBeforeInfo(
    WorkedBeforeState Contact,
    WorkedBeforeState Country,
    WorkedBeforeState Continent,
    WorkedBeforeState CqZone,
    WorkedBeforeState ItuZone)
{
    /// <summary>The all-<see cref="WorkedBeforeState.Never"/> default — "never worked before on any axis".</summary>
    public static readonly WorkedBeforeInfo None = new(
        WorkedBeforeState.Never, WorkedBeforeState.Never, WorkedBeforeState.Never,
        WorkedBeforeState.Never, WorkedBeforeState.Never);
}
