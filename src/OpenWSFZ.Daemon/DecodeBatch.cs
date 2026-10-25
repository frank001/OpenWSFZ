using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// A completed decode cycle: the authoritative UTC cycle-start timestamp and the
/// list of decode results (empty when the silence guard fired).
/// </summary>
/// <param name="CycleStart">UTC instant at which the CycleFramer began accumulating this window.</param>
/// <param name="Results">Decoded messages; empty when the RMS silence guard fired.</param>
/// <param name="BatchNumber">
/// late-batches-in-qso: 1 for a cycle's first (or only) batch; 2, 3 or 4 for a supplementary batch of the SAME cycle
/// (residual pass, third pass, coherent fallback). Only a batch 1 is a cycle for the QSO services; a supplementary batch counts as heard
/// but never as a missed response. Defaults to 1 so every existing constructor call stays valid.
/// </param>
/// <param name="DialFrequencyMHz">
/// psk-reporter-upload (#262): the dial frequency (MHz) at the cycle's capture, as the pump resolved it for this cycle, or <c>null</c> when
/// none was known (the PSK Reporter upload then reports nothing for the batch). Defaults to <c>null</c> so every existing constructor call
/// stays valid; the pump sets it, never the consumers, so a CAT retune between capture and delivery cannot move a record's band.
/// </param>
public sealed record DecodeBatch(
    DateTimeOffset              CycleStart,
    IReadOnlyList<DecodeResult> Results,
    int                         BatchNumber = 1,
    double?                     DialFrequencyMHz = null);
