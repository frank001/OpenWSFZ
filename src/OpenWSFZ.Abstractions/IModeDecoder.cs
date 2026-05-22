namespace OpenWSFZ.Abstractions;

/// <summary>
/// Decodes one 15-second cycle of PCM audio into a sequence of mode-specific messages.
/// Implemented by <c>OpenWSFZ.Ft8.Ft8Decoder</c>.
/// </summary>
public interface IModeDecoder
{
    /// <summary>
    /// Decodes a single FT8 cycle buffer.
    /// </summary>
    /// <param name="pcm">
    /// Exactly 180 000 samples (15 s × 12 000 Hz) of 32-bit float mono PCM,
    /// values in the range <c>[-1.0, +1.0]</c>.
    /// </param>
    /// <param name="ct">Cancellation token; throws <see cref="OperationCanceledException"/> if cancelled.</param>
    /// <returns>
    /// All decoded messages found in this cycle. Returns an empty list — never <c>null</c> —
    /// when no valid FT8 transmissions are detected.
    /// </returns>
    Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default);
}
