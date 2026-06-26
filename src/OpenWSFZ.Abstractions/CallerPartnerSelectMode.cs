using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Determines how <c>QsoCallerService</c> selects a responding station while in
/// <c>WaitAnswer</c>.
/// </summary>
[JsonConverter(typeof(JsonStringEnumConverter<CallerPartnerSelectMode>))]
public enum CallerPartnerSelectMode
{
    /// <summary>
    /// Auto-engage the first station that responds to the CQ (default).
    /// </summary>
    First = 0,

    /// <summary>
    /// Operator manually selects a responder by clicking a highlighted decode-table row.
    /// </summary>
    None = 1,
}
