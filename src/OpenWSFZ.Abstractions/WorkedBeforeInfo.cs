namespace OpenWSFZ.Abstractions;

/// <summary>
/// Advisory "worked before" state resolved for a decoded callsign-position token
/// (<c>qso-confirmation</c> capability), attached to the decode-result payload alongside
/// <see cref="RegionInfo"/>. Three independent, differently-scoped booleans:
/// <list type="bullet">
///   <item><see cref="Call"/> — this exact station (or a portable-suffixed variant) has been
///   logged before, anywhere in <c>ADIF.log</c>'s history.</item>
///   <item><see cref="Country"/> — this station's DXCC entity has been logged before
///   (a different station, same country).</item>
///   <item><see cref="Region"/> — this station's continent has been logged before (a different
///   station, possibly a different country, same continent). Strictly coarser than
///   <see cref="Country"/>.</item>
/// </list>
/// Never affects decode acceptance — a resolution failure of any kind degrades to
/// <see cref="None"/> (all three <c>false</c>), matching the <c>region-lookup</c> capability's
/// existing advisory-only guarantee.
/// </summary>
/// <param name="Call">Whether this callsign (or a portable-suffixed variant of it) has been worked before.</param>
/// <param name="Country">Whether this callsign's resolved DXCC entity has been worked before.</param>
/// <param name="Region">Whether this callsign's resolved continent has been worked before.</param>
public sealed record WorkedBeforeInfo(bool Call, bool Country, bool Region)
{
    /// <summary>The all-false default — "never worked before on any axis".</summary>
    public static readonly WorkedBeforeInfo None = new(false, false, false);
}
