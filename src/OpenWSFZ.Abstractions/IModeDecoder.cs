namespace OpenWSFZ.Abstractions;

/// <summary>
/// Decodes one 15-second cycle of PCM audio into a sequence of mode-specific messages.
/// Implemented by <c>OpenWSFZ.Ft8.Ft8Decoder</c>.
/// </summary>
public interface IModeDecoder
{
    /// <summary>
    /// Decodes a single FT8 cycle buffer using a caller-supplied cycle-start timestamp.
    /// </summary>
    /// <param name="pcm">
    /// Exactly 180 000 samples (15 s × 12 000 Hz) of 32-bit float mono PCM,
    /// values in the range <c>[-1.0, +1.0]</c>.
    /// </param>
    /// <param name="cycleStart">
    /// The UTC instant at which the 15-second FT8 window began, as recorded by
    /// <c>CycleFramer</c>.  Using the framer-supplied value avoids the wall-clock
    /// race condition that occurs when the timestamp is sampled inside the decoder
    /// after the cycle boundary may already have passed.
    /// </param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>
    /// All decoded messages found in this cycle. Returns an empty list — never <c>null</c> —
    /// when no valid FT8 transmissions are detected.
    /// </returns>
    Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, DateTime cycleStart, CancellationToken ct = default);

    /// <summary>
    /// Decodes a single FT8 cycle buffer, inferring the cycle-start timestamp from
    /// <see cref="DateTime.UtcNow"/> aligned to the nearest 15-second UTC boundary.
    /// </summary>
    /// <remarks>
    /// Prefer the <c>DecodeAsync(pcm, cycleStart, ct)</c> overload in production code.
    /// This overload is susceptible to a wall-clock race: if the calling thread is
    /// delayed past a 15-second boundary, <c>AlignToCycleStart</c> may snap to the start
    /// of the <em>next</em> cycle, producing timestamps 15 seconds ahead of the actual
    /// transmission window.
    /// </remarks>
    /// <param name="pcm">
    /// Exactly 180 000 samples (15 s × 12 000 Hz) of 32-bit float mono PCM.
    /// </param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>All decoded messages; never <c>null</c>.</returns>
    Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default);
}
