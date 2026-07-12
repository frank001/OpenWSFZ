#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig.Internal;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Serial RTS/DTR implementation of <see cref="IPttController"/> (FR-056).
///
/// <para>
/// PTT is asserted/de-asserted by toggling a raw RTS or DTR control line (per
/// <c>AppConfig.Ptt.SerialLine</c>) on its own, independently-configured serial port
/// (<c>AppConfig.Ptt.SerialPort</c>) — entirely independent of any CAT connection or
/// <see cref="ICatPttGate"/> (design.md Decision 5 of the <c>cat-tx-ptt</c> change). TX
/// audio is played via the same shared <see cref="WasapiTxPlayer"/> helper
/// <see cref="AudioOnlyPttController"/> uses.
/// </para>
///
/// <para>
/// Sequencing mirrors <see cref="CatPttController"/> exactly: <c>KeyDownAsync</c>
/// asserts the line → waits <c>LeadTimeMs</c> → plays audio → awaits completion.
/// <c>KeyUpAsync</c> stops playback → waits <c>TailTimeMs</c> → de-asserts the line.
/// A <see cref="PttWatchdog"/> guards the entire asserted period.
/// </para>
///
/// <para>
/// The serial port is opened lazily on first use and kept open for the controller's
/// lifetime; a port-open failure propagates as an exception from <c>KeyDownAsync</c>
/// rather than silently skipping PTT assertion (task 9.5). Changing
/// <c>AppConfig.Ptt.SerialPort</c> while the daemon is running does not reopen an
/// already-open port — unlike CAT's serial port, this is not hot-reloaded.
/// </para>
///
/// <para>Registered as a singleton in DI by <c>Program.cs</c> when
/// <c>AppConfig.Ptt.Method == "SerialRtsDtr"</c>.</para>
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class SerialRtsDtrPttController : IPttController
{
    // Baud rate is irrelevant for RTS/DTR-only PTT keying — no data is ever exchanged
    // on the TX/RX pins, only the RTS/DTR control lines are toggled. Kept at a
    // conventional default purely because System.IO.Ports.SerialPort's constructor
    // requires one; PttConfig deliberately has no baudRate field for this reason.
    private const int DefaultBaudRate = 9600;

    private enum SerialLine { Rts, Dtr }

    private readonly IConfigStore                              _configStore;
    private readonly ILogger<SerialRtsDtrPttController>        _logger;
    private readonly ISerialPort                                _port;
    private readonly SemaphoreSlim                               _portLock = new(1, 1);
    private readonly WasapiTxPlayer                              _player;
    private readonly PttWatchdog                                 _watchdog;

    // Internal seam — replaced in tests with a delegate that does not open WASAPI.
    // Production constructor leaves this null, triggering the real WASAPI path.
    private readonly Func<float[], string?, CancellationToken, Task>? _playerOverride;

    private float[]?      _audioSamples;
    private volatile bool _pttAsserted;

    // The line actually asserted by the most recent KeyDownAsync, remembered so
    // KeyUpAsync/ForceReleaseAsync de-assert the SAME line even if AppConfig.Ptt.SerialLine
    // changes mid-transmission — de-asserting the wrong line would leave the originally-
    // asserted one stuck high, which is exactly the failure mode this change exists to prevent.
    private SerialLine? _assertedLine;

    // ── Call-serialisation (design.md Decision 6 amendment, task 17.2) ─────────
    // See CatPttController's identical field for the full rationale: a second concurrent
    // caller of this DI singleton (e.g. the Settings-page Test button) must not be able to
    // interleave with an in-flight real transmission. _txLock is held for the ENTIRE
    // KeyDownAsync → KeyUpAsync critical section, released exactly once per acquire by
    // whichever of KeyUpAsync / ForceReleaseAsync / DisposeAsync (or KeyDownAsync's own
    // catch block, for a pre-assert failure) actually performs the release. Distinct from
    // _portLock above, which only guards the lazy port-open step.
    private readonly SemaphoreSlim _txLock = new(1, 1);
    private volatile bool          _txLockHeld;

    // ── Constructors ─────────────────────────────────────────────────────────

    /// <summary>Production constructor — opens a real serial port from config.</summary>
    public SerialRtsDtrPttController(
        IConfigStore                          configStore,
        ILogger<SerialRtsDtrPttController>    logger)
        : this(
              configStore,
              logger,
              new SerialPortWrapper(configStore.Current.Ptt.SerialPort, DefaultBaudRate),
              playerOverride: null)
    {
    }

    /// <summary>
    /// Internal test constructor — injects a fake <see cref="ISerialPort"/> and, optionally,
    /// a delegate in place of the real WASAPI path (mirroring
    /// <see cref="AudioOnlyPttController"/>'s/<see cref="CatPttController"/>'s own seams).
    /// </summary>
    internal SerialRtsDtrPttController(
        IConfigStore                                        configStore,
        ILogger<SerialRtsDtrPttController>                  logger,
        ISerialPort                                          serialPort,
        Func<float[], string?, CancellationToken, Task>?    playerOverride = null)
    {
        _configStore    = configStore;
        _logger         = logger;
        _port           = serialPort;
        _playerOverride = playerOverride;
        _player         = new WasapiTxPlayer(logger);
        _watchdog       = new PttWatchdog(logger, nameof(SerialRtsDtrPttController));
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
    /// Begins transmission: opens the configured serial port if not already open,
    /// asserts the configured RTS/DTR line, waits <c>LeadTimeMs</c>, then plays the
    /// pre-loaded audio buffer and awaits completion.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown when <see cref="LoadAudio"/> has not been called before this method.
    /// PTT is NOT asserted in this case.
    /// </exception>
    /// <exception cref="Exception">
    /// Propagates any exception from opening the serial port (task 9.5) — a configured
    /// port that does not exist or is already in use SHALL NOT silently skip PTT
    /// assertion and proceed to play audio.
    /// </exception>
    public async Task KeyDownAsync(CancellationToken ct = default)
    {
        var samples = _audioSamples
            ?? throw new InvalidOperationException(
                "LoadAudio must be called before KeyDownAsync. " +
                "Call LoadAudio with the synthesised TX audio buffer first.");

        var ptt      = _configStore.Current.Ptt;
        var deviceId = _configStore.Current.AudioOutputDeviceId;

        // task 17.2: acquire the call-serialisation lock before touching the line at all,
        // so a second concurrent caller blocks here until this cycle's KeyUpAsync completes.
        await _txLock.WaitAsync(ct).ConfigureAwait(false);
        _txLockHeld = true;

        try
        {
            await EnsurePortOpenAsync(ct).ConfigureAwait(false); // throws on open failure

            var line = ResolveLine(ptt.SerialLine);
            SetLine(line, asserted: true);
            _assertedLine = line;
            _pttAsserted  = true;
            _watchdog.Arm(ptt.WatchdogTimeoutMs, ForceReleaseAsync);
            _logger.LogInformation(
                "SerialRtsDtrPttController: KeyDown — PTT asserted ({Line}).", line);

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
                // must still de-assert the line before the exception reaches the caller.
                // KeyUpAsync releases _txLock itself (via ReleaseTxLockOnce) as part of that.
                await KeyUpAsync(CancellationToken.None).ConfigureAwait(false);
                throw;
            }
        }
        catch
        {
            // Either the port failed to open or SetLine/assert never happened (PTT never
            // asserted, so KeyUpAsync above never ran and never released the lock), or the
            // inner catch already ran KeyUpAsync, which already released it —
            // ReleaseTxLockOnce is idempotent either way (task 17.2).
            ReleaseTxLockOnce();
            throw;
        }
    }

    /// <summary>
    /// Ends transmission: stops any in-progress playback, waits <c>TailTimeMs</c>, then
    /// de-asserts the line that was asserted by the most recent <see cref="KeyDownAsync"/>.
    /// Safe to call when PTT is not asserted — treated as a no-op beyond stopping
    /// playback and disarming the watchdog.
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

        if (_assertedLine is { } line)
            SetLine(line, asserted: false);

        _pttAsserted  = false;
        _logger.LogInformation(
            "SerialRtsDtrPttController: KeyUp — PTT released ({Line}).", _assertedLine);
        _assertedLine = null;
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

        if (_assertedLine is { } line)
            SetLine(line, asserted: false);
        _assertedLine = null;
        ReleaseTxLockOnce();
    }

    /// <summary>
    /// Forces line de-assertion if still asserted, releases the audio device handle,
    /// and closes/disposes the serial port.
    /// </summary>
    public async ValueTask DisposeAsync()
    {
        _watchdog.Dispose();

        if (_pttAsserted && _assertedLine is { } line)
        {
            try
            {
                SetLine(line, asserted: false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex,
                    "SerialRtsDtrPttController: line de-assertion during DisposeAsync threw — ignoring.");
            }
            ReleaseTxLockOnce();
        }
        _pttAsserted  = false;
        _assertedLine = null;

        await _player.DisposeAsync().ConfigureAwait(false);

        try
        {
            if (_port.IsOpen) _port.Close();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "SerialRtsDtrPttController: serial port close during DisposeAsync threw — ignoring.");
        }
        try
        {
            _port.Dispose();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "SerialRtsDtrPttController: serial port dispose during DisposeAsync threw — ignoring.");
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

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

    private async Task EnsurePortOpenAsync(CancellationToken ct)
    {
        if (_port.IsOpen) return;

        await _portLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            if (!_port.IsOpen)
                _port.Open(); // throws on failure — propagates directly (task 9.5)
        }
        finally
        {
            _portLock.Release();
        }
    }

    private SerialLine ResolveLine(string configured)
    {
        if (string.Equals(configured, "Dtr", StringComparison.OrdinalIgnoreCase)) return SerialLine.Dtr;
        if (string.Equals(configured, "Rts", StringComparison.OrdinalIgnoreCase)) return SerialLine.Rts;

        _logger.LogWarning(
            "SerialRtsDtrPttController: ptt.serialLine '{SerialLine}' is not recognised " +
            "(expected Rts or Dtr) — falling back to Rts.", configured);
        return SerialLine.Rts;
    }

    private void SetLine(SerialLine line, bool asserted)
    {
        if (line == SerialLine.Dtr)
            _port.DtrEnable = asserted;
        else
            _port.RtsEnable = asserted;
    }
}
#endif
