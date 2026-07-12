#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// CAT-command implementation of <see cref="IPttController"/> (FR-056).
///
/// <para>
/// PTT is asserted/de-asserted via <see cref="ICatPttGate"/> (implemented by
/// <c>CatPollingService</c>, guaranteeing every command is serialised against the CAT
/// poll loop — see design.md Decision 1 of the <c>cat-tx-ptt</c> change). TX audio is
/// played via the same shared <see cref="WasapiTxPlayer"/> helper
/// <see cref="AudioOnlyPttController"/> uses.
/// </para>
///
/// <para>
/// <c>KeyDownAsync</c> sequence: assert PTT → wait <c>LeadTimeMs</c> → play audio →
/// await completion. <c>KeyUpAsync</c> sequence: stop playback → wait <c>TailTimeMs</c>
/// → release PTT. A <see cref="PttWatchdog"/> guards the entire asserted period —
/// see its own remarks for the failsafe contract. PTT is guaranteed released on any
/// exception during <c>KeyDownAsync</c>, on cancellation, on a watchdog trip, and on
/// <see cref="DisposeAsync"/>.
/// </para>
///
/// <para>Registered as a singleton in DI by <c>Program.cs</c> when
/// <c>AppConfig.Ptt.Method == "CatCommand"</c>.</para>
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class CatPttController : IPttController
{
    private readonly ICatPttGate                       _pttGate;
    private readonly IConfigStore                       _configStore;
    private readonly ILogger<CatPttController>          _logger;
    private readonly WasapiTxPlayer                     _player;
    private readonly PttWatchdog                        _watchdog;

    // Internal seam — replaced in tests with a delegate that does not open WASAPI.
    // Production constructor leaves this null, triggering the real WASAPI path.
    // Mirrors AudioOnlyPttController's own test seam exactly.
    private readonly Func<float[], string?, CancellationToken, Task>? _playerOverride;

    private float[]? _audioSamples;

    // True from the instant ICatPttGate.SetPttAsync(true) returns until PTT has been
    // released (normally, by exception, by watchdog, or by DisposeAsync). Guards against
    // a double release racing between KeyUpAsync and a watchdog trip.
    private volatile bool _pttAsserted;

    // ── Call-serialisation (design.md Decision 6 amendment, task 17.2) ─────────
    //
    // KeyDownAsync/KeyUpAsync were originally written assuming exactly one caller (the
    // active QsoAnswererService/QsoCallerService) ever calls them. The Settings-page Test
    // button (POST /api/v1/ptt/test) is a second, independent caller of this same DI
    // singleton. Without a guard here, a Test click racing a real in-progress transmission
    // could re-arm the shared watchdog and — worse — its own short KeyUpAsync could
    // de-assert PTT mid-transmission, physically unkeying a real over-the-air transmission.
    // _txLock is held for the ENTIRE KeyDownAsync → KeyUpAsync critical section (not just
    // KeyDownAsync itself), so a second caller's KeyDownAsync cannot begin asserting PTT
    // until the first caller's KeyUpAsync has fully completed. Released exactly once per
    // successful acquire by whichever of KeyUpAsync / ForceReleaseAsync / DisposeAsync (or
    // KeyDownAsync's own catch block, for a pre-assert failure) actually performs the
    // release — see ReleaseTxLockOnce.
    private readonly SemaphoreSlim _txLock = new(1, 1);
    private volatile bool          _txLockHeld;

    // ── Constructors ─────────────────────────────────────────────────────────

    /// <summary>Production constructor — uses the real CAT gate and real WASAPI output.</summary>
    public CatPttController(
        ICatPttGate                pttGate,
        IConfigStore                configStore,
        ILogger<CatPttController>   logger)
    {
        _pttGate        = pttGate;
        _configStore    = configStore;
        _logger         = logger;
        _playerOverride = null;
        _player         = new WasapiTxPlayer(logger);
        _watchdog       = new PttWatchdog(logger, nameof(CatPttController));
    }

    /// <summary>
    /// Internal test constructor — injects a delegate in place of the real WASAPI path,
    /// mirroring <see cref="AudioOnlyPttController"/>'s own test seam. <paramref name="pttGate"/>
    /// is typically a mock so tests can assert call order/values without a real CAT link.
    /// </summary>
    internal CatPttController(
        ICatPttGate                                       pttGate,
        IConfigStore                                       configStore,
        ILogger<CatPttController>                          logger,
        Func<float[], string?, CancellationToken, Task>    playerOverride)
    {
        _pttGate        = pttGate;
        _configStore    = configStore;
        _logger         = logger;
        _playerOverride = playerOverride;
        _player         = new WasapiTxPlayer(logger);
        _watchdog       = new PttWatchdog(logger, nameof(CatPttController));
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /// <summary>
    /// Sets the TX audio buffer that will be played on the next <see cref="KeyDownAsync"/> call.
    /// Must be called before <see cref="KeyDownAsync"/>.
    /// </summary>
    /// <param name="samples">
    /// Mono float32 PCM at 48 000 Hz, amplitude in [−0.5, +0.5].
    /// </param>
    public void LoadAudio(float[] samples)
    {
        ArgumentNullException.ThrowIfNull(samples);
        _audioSamples = samples;
        _logger.LogDebug("TX audio loaded: {Samples} samples ({DurationMs:F0} ms).",
            samples.Length,
            samples.Length * 1000.0 / 48_000);
    }

    /// <summary>
    /// Begins transmission: asserts PTT via <see cref="ICatPttGate"/>, waits
    /// <c>LeadTimeMs</c>, then plays the pre-loaded audio buffer and awaits completion.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown when <see cref="LoadAudio"/> has not been called before this method.
    /// PTT is NOT asserted in this case.
    /// </exception>
    public async Task KeyDownAsync(CancellationToken ct = default)
    {
        var samples = _audioSamples
            ?? throw new InvalidOperationException(
                "LoadAudio must be called before KeyDownAsync. " +
                "Call LoadAudio with the synthesised TX audio buffer first.");

        var ptt      = _configStore.Current.Ptt;
        var deviceId = _configStore.Current.AudioOutputDeviceId;

        // task 17.2: acquire the call-serialisation lock before touching PTT at all, so a
        // second concurrent caller blocks here until this cycle's KeyUpAsync completes.
        await _txLock.WaitAsync(ct).ConfigureAwait(false);
        _txLockHeld = true;

        try
        {
            await _pttGate.SetPttAsync(true, ct).ConfigureAwait(false);
            _pttAsserted = true;
            _watchdog.Arm(ptt.WatchdogTimeoutMs, ForceReleaseAsync);
            _logger.LogInformation("CatPttController: KeyDown — PTT asserted (CAT).");

            try
            {
                if (ptt.LeadTimeMs > 0)
                    await Task.Delay(ptt.LeadTimeMs, ct).ConfigureAwait(false);

                if (_playerOverride is not null)
                    await _playerOverride(samples, deviceId, ct).ConfigureAwait(false);
                else
                    await _player.PlayAsync(samples, deviceId, ct).ConfigureAwait(false);
            }
            catch
            {
                // Any failure during the lead-time wait or playback (including cancellation)
                // must still release PTT before the exception reaches the caller. KeyUpAsync
                // releases _txLock itself (via ReleaseTxLockOnce) as part of that release.
                await KeyUpAsync(CancellationToken.None).ConfigureAwait(false);
                throw;
            }
        }
        catch
        {
            // Either SetPttAsync(true) itself failed (PTT was never asserted, so KeyUpAsync
            // above never ran and never released the lock), or the inner catch already ran
            // KeyUpAsync, which already released it — ReleaseTxLockOnce is idempotent either
            // way (task 17.2).
            ReleaseTxLockOnce();
            throw;
        }
    }

    /// <summary>
    /// Ends transmission: stops any in-progress playback, waits <c>TailTimeMs</c>, then
    /// releases PTT via <see cref="ICatPttGate"/>. Safe to call when PTT is not asserted
    /// — treated as a no-op beyond stopping playback and disarming the watchdog.
    /// </summary>
    public async Task KeyUpAsync(CancellationToken ct = default)
    {
        _watchdog.Disarm();

        if (_playerOverride is null)
            await _player.StopAsync(ct).ConfigureAwait(false);

        if (!_pttAsserted) return;

        var ptt = _configStore.Current.Ptt;
        if (ptt.TailTimeMs > 0)
            await Task.Delay(ptt.TailTimeMs, CancellationToken.None).ConfigureAwait(false);

        await _pttGate.SetPttAsync(false, CancellationToken.None).ConfigureAwait(false);
        _pttAsserted = false;
        _logger.LogInformation("CatPttController: KeyUp — PTT released (CAT).");
        ReleaseTxLockOnce();
    }

    /// <summary>
    /// Watchdog-forced release (design.md Decision 4): bypasses <c>TailTimeMs</c> entirely.
    /// </summary>
    private async Task ForceReleaseAsync()
    {
        if (!_pttAsserted) return;
        _pttAsserted = false; // set first so a racing KeyUpAsync becomes a no-op

        if (_playerOverride is null)
            await _player.StopAsync(CancellationToken.None).ConfigureAwait(false);

        await _pttGate.SetPttAsync(false, CancellationToken.None).ConfigureAwait(false);
        ReleaseTxLockOnce();
    }

    /// <summary>
    /// Forces PTT release if still asserted and releases the audio device handle.
    /// </summary>
    public async ValueTask DisposeAsync()
    {
        _watchdog.Dispose();

        if (_pttAsserted)
        {
            _pttAsserted = false;
            try
            {
                await _pttGate.SetPttAsync(false, CancellationToken.None).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex,
                    "CatPttController: PTT release during DisposeAsync threw — ignoring.");
            }
            ReleaseTxLockOnce();
        }

        await _player.DisposeAsync().ConfigureAwait(false);
    }

    /// <summary>
    /// Releases <see cref="_txLock"/> at most once per acquire (task 17.2). Guards against
    /// double-release when KeyUpAsync, a watchdog-forced <see cref="ForceReleaseAsync"/>, and
    /// <see cref="DisposeAsync"/> can each be the one that actually performs the release for
    /// a given KeyDownAsync→KeyUpAsync cycle.
    /// </summary>
    private void ReleaseTxLockOnce()
    {
        if (!_txLockHeld) return;
        _txLockHeld = false;
        _txLock.Release();
    }
}
#endif
