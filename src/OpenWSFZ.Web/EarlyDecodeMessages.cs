using System.Text.Json.Serialization;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// decode-early-batch-panel (design.md D5): one row of the <b>early</b> batch, as the decode panel receives it. The
/// <see cref="EarlyId"/> is unique within the daemon's lifetime; the batch-1 <c>decode</c> frame refers to it in its
/// optional <c>resolves</c> list.
/// </summary>
/// <param name="EarlyId">Unique id of this early row (a daemon-lifetime counter).</param>
/// <param name="Decode">The decode, mapped exactly like a batch-1 row.</param>
public sealed record EarlyRow(long EarlyId, DecodeResult Decode);

/// <summary>
/// decode-early-batch-panel (design.md D5): what became of one early row once the cycle's final decode (batch 1) was
/// known. Carried in the batch-1 <c>decode</c> frame's optional <c>resolves</c> list, so the confirmation and the final
/// rows reach the panel in ONE frame (no paint between "early row removed" and "final row added").
/// </summary>
/// <param name="EarlyId">The early row this refers to.</param>
/// <param name="Outcome"><c>"confirmed"</c> (the final decode agrees) or <c>"unconfirmed"</c> (it does not).</param>
/// <param name="FinalIndex">For <c>confirmed</c>: the index, in the same frame's <c>payload</c>, of the final row that replaces it. Omitted otherwise.</param>
public sealed record EarlyResolution(
    long   EarlyId,
    string Outcome,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] int? FinalIndex = null)
{
    /// <summary>The outcome of an early row that the final decode confirmed.</summary>
    public const string Confirmed = "confirmed";

    /// <summary>The outcome of an early row that the final decode did not confirm.</summary>
    public const string Unconfirmed = "unconfirmed";
}

/// <summary>Envelope for <c>decode-early</c> WebSocket text frames (panel only; decode-early-batch-panel D5).</summary>
internal sealed record WsEarlyDecodeMessage(string Type, List<EarlyRow> Payload);
