namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction over the push-to-talk (PTT) mechanism used to key the transmitter.
///
/// <para>
/// v1 implementation (<c>AudioOnlyPttController</c>) drives PTT via audio output only:
/// <see cref="KeyDownAsync"/> starts WASAPI audio playback; <see cref="KeyUpAsync"/>
/// stops it.  Future implementations can add serial-port, CAT, or VOX keying without
/// changing the <see cref="QsoAnswererService"/> state machine.
/// </para>
///
/// <para>
/// The pre-synthesised TX audio buffer is supplied via a separate
/// <c>LoadAudio(float[] samples)</c> method on the concrete implementation before
/// <see cref="KeyDownAsync"/> is called.  This separates audio preparation (done at
/// encode time) from transmission start (done at the cycle boundary).
/// </para>
///
/// <para>Implementations are registered in the DI container as singletons.</para>
/// </summary>
public interface IPttController : IAsyncDisposable
{
    /// <summary>
    /// Begins transmission. For <c>AudioOnlyPttController</c>, starts WASAPI playback
    /// of the pre-loaded audio buffer.
    /// </summary>
    /// <param name="ct">Cancellation token; cancellation stops the transmission.</param>
    /// <exception cref="InvalidOperationException">
    /// Thrown by <c>AudioOnlyPttController</c> if <c>LoadAudio</c> has not been called.
    /// </exception>
    Task KeyDownAsync(CancellationToken ct = default);

    /// <summary>
    /// Ends transmission and releases the audio device handle (or equivalent resource).
    /// Safe to call when no transmission is in progress — treated as a no-op.
    /// </summary>
    /// <param name="ct">Cancellation token.</param>
    Task KeyUpAsync(CancellationToken ct = default);
}
