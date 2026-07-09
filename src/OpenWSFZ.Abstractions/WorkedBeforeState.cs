using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Tri-state, band-aware result of a single worked-before axis comparison
/// (<c>qso-confirmation</c> capability, <c>qso-confirmation-band-awareness</c> design.md
/// Decision 1). Mirrors the WSJT-X/JTAlert-style "worked before, by band" indication the
/// Captain specifically pointed to as the target behaviour.
/// </summary>
/// <remarks>
/// Serialised via <see cref="JsonStringEnumConverter{TEnum}"/>. Each member carries an explicit
/// <see cref="JsonStringEnumMemberNameAttribute"/> pinning its wire value to lowerCamelCase
/// (<c>"never"</c>/<c>"differentBand"</c>/<c>"thisBand"</c>), matching <c>web/js/main.js</c>'s
/// <c>makeWorkedBeforeCell</c> string comparisons.
/// <para>
/// Do not rely on <c>AppJsonContext</c>'s <c>CamelCase</c> <c>PropertyNamingPolicy</c> to cover
/// this — that option only renames JSON *properties*, not enum *values*. A bare
/// <c>JsonStringEnumConverter&lt;TEnum&gt;</c> with no naming policy serialises the exact
/// PascalCase member name (<c>"ThisBand"</c>, not <c>"thisBand"</c>) — confirmed the hard way:
/// this shipped once without the explicit names below and every worked-before indicator in the
/// live UI rendered empty, because the frontend's string comparisons never matched the
/// PascalCase wire values it actually received. The codebase's <see cref="TxRole"/>/
/// <see cref="CallerPartnerSelectMode"/> enums are not a working counter-example: every call
/// site that puts a role/mode on the wire does so via a plain <c>string</c> property populated
/// with <c>.ToString().ToLowerInvariant()</c> (see <c>WebApp.cs</c>) — their
/// <c>JsonStringEnumConverter</c> attributes are never actually exercised for wire
/// serialisation, so they set no real precedent either way.
/// </para>
/// </remarks>
[JsonConverter(typeof(JsonStringEnumConverter<WorkedBeforeState>))]
public enum WorkedBeforeState
{
    /// <summary>Never worked on this axis, on any band.</summary>
    [JsonStringEnumMemberName("never")]
    Never,

    /// <summary>Worked on this axis, but not on the session's current active band.</summary>
    [JsonStringEnumMemberName("differentBand")]
    DifferentBand,

    /// <summary>Worked on this axis, on the session's current active band.</summary>
    [JsonStringEnumMemberName("thisBand")]
    ThisBand,
}
