using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// A completed decode cycle: the authoritative UTC cycle-start timestamp and the
/// list of decode results (empty when the silence guard fired).
/// </summary>
/// <param name="CycleStart">UTC instant at which the CycleFramer began accumulating this window.</param>
/// <param name="Results">Decoded messages; empty when the RMS silence guard fired.</param>
public sealed record DecodeBatch(
    DateTimeOffset              CycleStart,
    IReadOnlyList<DecodeResult> Results);
