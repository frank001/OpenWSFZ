namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction over the push-to-talk (PTT) mechanism used to key the transmitter.
///
/// <para>
/// v1 implementation (<c>AudioOnlyPttController</c>) drives PTT via audio output only:
/// <see cref="KeyDownAsync"/> starts WASAPI audio playback; <see cref="KeyUpAsync"/>
/// stops it.  For that implementation, forgetting to call <see cref="KeyUpAsync"/> after a
/// normal transmission is harmless because playback has, by construction, already finished.
/// The CAT/serial implementations (<c>CatPttController</c>, <c>SerialRtsDtrPttController</c>)
/// do <b>not</b> share that property: <see cref="KeyDownAsync"/> asserts PTT and returns once
/// playback completes, but the transmitter line stays physically asserted until a
/// <b>separate</b> <see cref="KeyUpAsync"/> call de-asserts it (after waiting
/// <c>TailTimeMs</c>). Future implementations can add further keying mechanisms without
/// changing the <see cref="QsoAnswererService"/> state machine.
/// </para>
///
/// <para>
/// <b>Contract:</b> every call to <see cref="KeyDownAsync"/> MUST be followed by exactly one
/// call to <see cref="KeyUpAsync"/> in the caller's <i>normal-completion</i> path — not only
/// on abort/cancellation. Skipping it is not "harmless cleanup you can defer"; on CAT/serial
/// implementations it leaves the rig transmitting until <c>PttWatchdog</c>'s 20-second
/// failsafe eventually forces a release, which is far too late to hold FT8 slot timing. See
/// dev-task <c>2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md</c> for the incident this
/// note was added to prevent from recurring.
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
    /// Loads the TX audio buffer that will be played by the next <see cref="KeyDownAsync"/>
    /// call.  Must be called before <see cref="KeyDownAsync"/>.
    /// </summary>
    /// <param name="samples">
    /// Mono float32 PCM at 48 000 Hz, amplitude in [−0.5, +0.5].
    /// </param>
    void LoadAudio(float[] samples);

    /// <summary>
    /// Begins transmission. For <c>AudioOnlyPttController</c>, starts WASAPI playback
    /// of the pre-loaded audio buffer. For the CAT/serial implementations, asserts the PTT
    /// line/command and plays the pre-loaded audio, returning once playback completes — the
    /// PTT line/command remains asserted after this method returns; only
    /// <see cref="KeyUpAsync"/> releases it. Callers MUST call <see cref="KeyUpAsync"/> after
    /// every call to this method on the normal-completion path, not only on abort.
    /// </summary>
    /// <param name="ct">Cancellation token; cancellation stops the transmission.</param>
    /// <exception cref="InvalidOperationException">
    /// Thrown if <see cref="LoadAudio"/> has not been called before this method.
    /// </exception>
    Task KeyDownAsync(CancellationToken ct = default);

    /// <summary>
    /// Ends transmission and releases the audio device handle (or equivalent resource); for
    /// the CAT/serial implementations, also de-asserts the PTT line/command after waiting
    /// <c>TailTimeMs</c>. Safe to call when no transmission is in progress — treated as a
    /// no-op. Callers MUST call this exactly once after every <see cref="KeyDownAsync"/> call
    /// in their normal-completion path — do not rely on <c>PttWatchdog</c>'s failsafe timeout
    /// as the ordinary release mechanism.
    /// </summary>
    /// <param name="ct">Cancellation token.</param>
    Task KeyUpAsync(CancellationToken ct = default);
}
