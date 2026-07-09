using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Tri-state, band-aware result of a single worked-before axis comparison
/// (<c>qso-confirmation</c> capability, <c>qso-confirmation-band-awareness</c> design.md
/// Decision 1). Mirrors the WSJT-X/JTAlert-style "worked before, by band" indication the
/// Captain specifically pointed to as the target behaviour.
/// </summary>
/// <remarks>
/// Serialised via <see cref="JsonStringEnumConverter{TEnum}"/> with no explicit naming
/// policy — <c>AppJsonContext</c>'s <c>CamelCase</c> source-gen option is honoured
/// automatically (mirrors <see cref="TxRole"/>/<see cref="CallerPartnerSelectMode"/>'s
/// existing precedent), producing wire values <c>"never"</c>/<c>"differentBand"</c>/
/// <c>"thisBand"</c>.
/// </remarks>
[JsonConverter(typeof(JsonStringEnumConverter<WorkedBeforeState>))]
public enum WorkedBeforeState
{
    /// <summary>Never worked on this axis, on any band.</summary>
    Never,

    /// <summary>Worked on this axis, but not on the session's current active band.</summary>
    DifferentBand,

    /// <summary>Worked on this axis, on the session's current active band.</summary>
    ThisBand,
}
