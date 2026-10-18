namespace OpenWSFZ.Abstractions;

/// <summary>
/// third-pass-deep (#240, B6): the third pass's process-lifetime counters and the decoding depth the decoder is
/// actually using, served on <c>GET /api/v1/status</c> as <c>thirdPass</c>. Separate from the residual pass's counters.
/// Counters are only ever incremented while <see cref="DecodingDepth"/> is <c>Deep</c>; with <c>Normal</c> they stay 0.
/// </summary>
/// <param name="DecodingDepth">The value the decoder is using now: <c>"Normal"</c> or <c>"Deep"</c> (read back from the decoder, not from the config file).</param>
/// <param name="Runs">Third passes started (outcome <c>ran</c>, <c>abandoned</c> or <c>failed</c>). Skips are not runs.</param>
/// <param name="SkippedNoNew">Skipped because the residual pass returned no new decode (or none could be subtracted).</param>
/// <param name="SkippedAbandoned">Skipped because the residual pass was abandoned or failed.</param>
/// <param name="Abandoned">Started, then abandoned on the cycle budget (nothing published).</param>
/// <param name="Failed">Started, then failed with a contained exception (nothing published).</param>
/// <param name="Decodes">Decodes published as batch 3.</param>
public sealed record ThirdPassStatus(
    string DecodingDepth,
    long   Runs,
    long   SkippedNoNew,
    long   SkippedAbandoned,
    long   Abandoned,
    long   Failed,
    long   Decodes);
