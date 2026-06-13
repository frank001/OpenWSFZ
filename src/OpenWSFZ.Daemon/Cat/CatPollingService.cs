using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon.Cat;

/// <summary>
/// Background service that polls rig frequency via <see cref="IRadioConnection"/>
/// and keeps <see cref="CatState"/> up to date (FR-032, FR-034, FR-045).
///
/// <para>
/// Lifecycle:
/// <list type="bullet">
///   <item>If <c>Cat.Enabled = false</c>, sets status to <see cref="CatConnectionStatus.Disabled"/>
///         and waits without opening any port.</item>
///   <item>Otherwise, creates a connection via <see cref="RigModelFactory"/>, connects,
///         and enters the poll loop.</item>
///   <item>Any connection or poll failure is logged at Warning and status set to
///         Error; polling is then <em>suspended</em> — no further attempts are made
///         until a CAT config field changes (port, baud, rigModel, enabled toggle).
///         This ensures the daemon does not hammer an unresponsive radio.</item>
///   <item>Config changes (port, baud, rigModel, enabled toggle) clear the
///         suspension and take effect without a daemon restart.</item>
/// </list>
/// </para>
///
/// <para>
/// Also implements <see cref="ICatTuner"/> (FR-045): <see cref="SetDialFrequencyAsync"/>
/// sends a frequency-set command on the currently active connection and updates
/// <see cref="CatState"/> optimistically.
/// </para>
/// </summary>
public class CatPollingService : IHostedService, IAsyncDisposable, ICatTuner
{
    private static readonly TimeSpan RetryDelay = TimeSpan.FromSeconds(2);

    /// <summary>
    /// Time to pause after a successful <see cref="IRadioConnection.ConnectAsync"/>
    /// before issuing the first <see cref="IRadioConnection.GetDialFrequencyMhzAsync"/>
    /// poll.
    ///
    /// <para>
    /// Rationale: the probe command sent during <c>ConnectAsync</c> is <c>FA;\r</c>.
    /// The radio answers <c>FA&lt;hz&gt;;</c> (consumed by <c>ReadTo(";")</c>), but
    /// some Kenwood and Yaesu firmware then process the <c>\r</c> separately and emit
    /// a trailing acknowledgement byte (<c>;</c> or <c>?;</c>) a few milliseconds
    /// later.  If the very first poll's <c>DiscardInBuffer()</c> executes before that
    /// byte has reached the OS receive buffer, it escapes the flush.  <c>ReadTo(";")</c>
    /// then reads it immediately and returns <c>raw=''</c>, which fails the <c>FA</c>
    /// prefix check and raises a spurious "connection lost" event — permanently
    /// suspending polling until a config change.
    /// </para>
    ///
    /// <para>
    /// Waiting here gives the trailing byte time to land in the OS buffer so that the
    /// first poll's <c>DiscardInBuffer()</c> can flush it before the exchange begins.
    /// 150 ms is sufficient for any realistic radio response time over a USB-Serial
    /// adapter at common baud rates (4 800 – 57 600).
    /// </para>
    ///
    /// <para>
    /// Override to <see cref="TimeSpan.Zero"/> in test subclasses to eliminate
    /// the latency from the unit-test run.
    /// </para>
    /// </summary>
    protected virtual TimeSpan PostConnectSettleDelay => TimeSpan.FromMilliseconds(150);

    private readonly CatState                   _catState;
    private readonly IConfigStore               _configStore;
    private readonly CatEventBus                _catEventBus;
    private readonly ILogger<CatPollingService> _logger;
    private readonly ILoggerFactory             _loggerFactory;

    private CancellationTokenSource? _cts;
    private Task?                    _pollingTask;

    // The active connection; set by the poll loop, read by SetDialFrequencyAsync.
    // Volatile ensures the reference is visible across threads.
    private volatile IRadioConnection? _activeConnection;

    // Serialises concurrent GetDialFrequencyMhzAsync (poll loop) and
    // SetDialFrequencyMhzAsync (HTTP request) on the same IRadioConnection
    // to prevent interleaved command / response sequences (F-006 Root B).
    private readonly SemaphoreSlim _connectionLock = new(1, 1);

    // Last values broadcast to clients via _catEventBus.  Promoted from
    // RunAsync-local variables to class fields so SetDialFrequencyAsync can
    // update the comparison baseline after an optimistic tune, allowing the
    // poll loop to publish a correction event when the rig silently ignores
    // the command (F-006 Root C).
    private double?             _lastBroadcastFreq;
    private CatConnectionStatus _lastBroadcastStatus;

    public CatPollingService(
        CatState                    catState,
        IConfigStore                configStore,
        CatEventBus                 catEventBus,
        ILogger<CatPollingService>  logger,
        ILoggerFactory              loggerFactory)
    {
        _catState      = catState;
        _configStore   = configStore;
        _catEventBus   = catEventBus;
        _logger        = logger;
        _loggerFactory = loggerFactory;
    }

    // ── IHostedService ────────────────────────────────────────────────────────

    /// <summary>
    /// Starts the CAT polling background task.
    /// Returns immediately; polling runs on the thread pool.
    /// </summary>
    public Task StartAsync(CancellationToken cancellationToken)
    {
        _cts         = new CancellationTokenSource();
        _pollingTask = Task.Run(() => RunAsync(_cts.Token), CancellationToken.None);
        return Task.CompletedTask;
    }

    /// <summary>
    /// Cancels the poll loop and waits for it to finish (up to 3 seconds).
    /// </summary>
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        if (_cts is null) return;

        await _cts.CancelAsync().ConfigureAwait(false);

        if (_pollingTask is not null)
        {
            try
            {
                await _pollingTask.WaitAsync(TimeSpan.FromSeconds(3), CancellationToken.None)
                                  .ConfigureAwait(false);
            }
            catch (TimeoutException) { /* loop did not finish in time — acceptable on shutdown */ }
            catch (OperationCanceledException) { /* expected */ }
        }
    }

    // ── IAsyncDisposable ─────────────────────────────────────────────────────

    public async ValueTask DisposeAsync()
    {
        // Atomically take ownership of _cts so a second call sees null and
        // exits immediately — prevents the double-dispose ObjectDisposedException
        // that arises when the DI container tracks the same CatPollingService
        // instance twice (once via AddSingleton, once via the AddHostedService
        // factory) and calls DisposeAsync on both tracked references (F-003).
        var cts = Interlocked.Exchange(ref _cts, null);
        if (cts is null) return;   // never started, or already disposed

        await cts.CancelAsync().ConfigureAwait(false);

        if (_pollingTask is not null)
        {
            try
            {
                await _pollingTask.WaitAsync(TimeSpan.FromSeconds(3), CancellationToken.None)
                                  .ConfigureAwait(false);
            }
            catch (TimeoutException) { /* loop did not finish in time — acceptable on shutdown */ }
            catch (OperationCanceledException) { /* expected */ }
        }

        cts.Dispose();
    }

    // ── ICatTuner ─────────────────────────────────────────────────────────────

    /// <inheritdoc/>
    public async Task SetDialFrequencyAsync(
        double            frequencyMHz,
        CancellationToken cancellationToken = default)
    {
        var conn = _activeConnection
            ?? throw new InvalidOperationException(
                "No active rig connection — CAT is not yet connected.");

        // Acquire the connection lock so the poll loop cannot interleave its
        // GetDialFrequencyMhzAsync I/O with this set command (F-006 Root B).
        await _connectionLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            // Re-check after lock acquisition: _activeConnection may have been
            // nulled by the poll loop's error handler between the fast pre-check
            // above and here (TOCTOU guard).
            conn = _activeConnection
                ?? throw new InvalidOperationException(
                    "No active rig connection — CAT is not yet connected.");

            _logger.LogInformation(
                "CAT: dispatching tune command — {FreqMHz:F3} MHz via {ConnType}.",
                frequencyMHz, conn.GetType().Name);

            await conn.SetDialFrequencyMhzAsync(frequencyMHz, cancellationToken)
                      .ConfigureAwait(false);

            _logger.LogInformation(
                "CAT: tune command sent — {FreqMHz:F3} MHz (rig will confirm on next poll).",
                frequencyMHz);

            // Optimistic update: push the requested frequency to the status bar
            // immediately so the operator sees a response before the next poll
            // cycle confirms it.
            // Also advance _lastBroadcastFreq so the poll loop can detect a rig
            // that silently ignores the command — if the next poll returns the
            // old frequency, HasFreqChanged fires and a correction event is
            // published (F-006 Root C).
            _catState.Update(frequencyMHz, _catState.Status);
            _lastBroadcastFreq = frequencyMHz;
            _catEventBus.Publish(_catState.Status, frequencyMHz);
        }
        finally
        {
            _connectionLock.Release();
        }
    }

    // ── Core poll loop ────────────────────────────────────────────────────────

    private async Task RunAsync(CancellationToken ct)
    {
        IRadioConnection? connection            = null;
        CatConfig?        lastConfig            = null;
        // Set to true after any connect or poll failure; cleared only when a CAT
        // config field changes or the disabled path is entered.  While set, the
        // loop idles without attempting further connections so the daemon does not
        // hammer an unresponsive radio.
        bool              suspendedAfterFailure = false;

        try
        {
            while (!ct.IsCancellationRequested)
            {
                var config = _configStore.Current.Cat ?? new CatConfig();

                // ── Detect config change (task 7.4) ───────────────────────────
                // HasConnectionConfigChanged deliberately excludes LastPolledFrequencyMHz
                // so that the FR-039 persist of the last-polled frequency does not
                // trigger a needless reconnect on every poll cycle (F-010).
                if (lastConfig is not null && HasConnectionConfigChanged(lastConfig, config))
                {
                    _logger.LogInformation(
                        "CAT config changed — reconnecting with new parameters.");
                    suspendedAfterFailure = false;   // operator changed config — allow retry
                    if (connection is not null)
                    {
                        _activeConnection = null;
                        await SafeDisconnectAsync(connection).ConfigureAwait(false);
                        connection = null;
                    }
                }
                lastConfig = config;

                // ── Disabled path ─────────────────────────────────────────────
                // CAT and audio decoding are independent subsystems: an operator may
                // legitimately run CAT without an audio device (frequency display,
                // PTT control, etc.).  The disabled path is entered only when the
                // operator has explicitly set Enabled = false in config.
                // An existing connection is closed when the operator disables CAT.
                if (!config.Enabled)
                {
                    if (connection is not null)
                    {
                        _activeConnection = null;
                        await SafeDisconnectAsync(connection).ConfigureAwait(false);
                        connection = null;
                    }
                    suspendedAfterFailure = false;   // entering disabled resets failure state
                    _catState.Update(null, CatConnectionStatus.Disabled);
                    EmitIfChanged(null, CatConnectionStatus.Disabled);
                    await Task.Delay(TimeSpan.FromSeconds(1), ct).ConfigureAwait(false);
                    continue;
                }

                // ── Suspended after failure — idle until config changes ───────
                // A prior connect or poll failure has been logged.  Do not hammer
                // the radio: wait here until HasConnectionConfigChanged clears the
                // flag (see config-change block above).  200 ms keeps the config-change
                // response time short while avoiding a busy-loop.
                if (suspendedAfterFailure)
                {
                    await Task.Delay(TimeSpan.FromMilliseconds(200), ct).ConfigureAwait(false);
                    continue;
                }

                // ── Validate poll interval ────────────────────────────────────
                var interval = config.PollIntervalSeconds;
                if (interval < 1 || interval > 60)
                {
                    var clamped = Math.Clamp(interval, 1, 60);
                    _logger.LogWarning(
                        "CAT: pollIntervalSeconds {Original} is out of range [1, 60] — clamped to {Clamped}.",
                        interval, clamped);
                    interval = clamped;
                }

                // ── Ensure connected ──────────────────────────────────────────
                if (connection is null || !connection.IsConnected)
                {
                    connection = CreateConnection(config);
                    if (connection is null)
                    {
                        // Unknown rigModel — disable CAT.
                        _catState.Update(null, CatConnectionStatus.Disabled);
                        EmitIfChanged(null, CatConnectionStatus.Disabled);
                        await Task.Delay(RetryDelay, ct).ConfigureAwait(false);
                        continue;
                    }

                    _catState.Update(null, CatConnectionStatus.Connecting);
                    EmitIfChanged(null, CatConnectionStatus.Connecting);

                    try
                    {
                        await connection.ConnectAsync(ct).ConfigureAwait(false);
                        _activeConnection = connection; // expose to SetDialFrequencyAsync
                        _logger.LogInformation(
                            "CAT connected via {RigModel}.", config.RigModel);

                        // Settle delay — see PostConnectSettleDelay for full rationale.
                        // Must run inside the connected try-block so that an
                        // OperationCanceledException during the delay is handled by
                        // the existing OCE catch rather than the generic Exception catch.
                        await Task.Delay(PostConnectSettleDelay, ct).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException) when (ct.IsCancellationRequested)
                    {
                        break;
                    }
                    catch (Exception ex)
                    {
                        // TimeoutException means the port opened but the radio is off or
                        // the CAT cable is disconnected — a normal operator condition, not a
                        // software fault.  Log at Information without the exception object
                        // (no stack trace) and guide the operator toward the real remedy.
                        // All other exceptions (port in use, port not found, …) indicate a
                        // configuration problem and are logged at Warning.
                        if (ex is TimeoutException)
                            _logger.LogInformation(
                                "CAT: no response from radio via {RigModel} — radio may be off " +
                                "or CAT cable disconnected. Polling suspended; turn on the radio " +
                                "to reconnect.",
                                config.RigModel);
                        else
                            _logger.LogWarning(
                                "CAT: could not connect via {RigModel} — {Message}. " +
                                "Polling suspended; check the CAT port settings to retry.",
                                config.RigModel, ex.Message);

                        _catState.Update(null, CatConnectionStatus.Error);
                        _activeConnection = null;
                        EmitIfChanged(null, CatConnectionStatus.Error);
                        await SafeDisconnectAsync(connection).ConfigureAwait(false);
                        connection            = null;
                        suspendedAfterFailure = true;
                        continue;
                    }
                }

                // ── Poll frequency ────────────────────────────────────────────
                // Acquire _connectionLock across the I/O exchange to serialise
                // with any concurrent SetDialFrequencyAsync call (F-006 Root B).
                // If WaitAsync itself is cancelled (ct already fired), the OCE
                // propagates to the outer catch; the lock was never acquired so
                // no Release() is needed.
                try
                {
                    await _connectionLock.WaitAsync(ct).ConfigureAwait(false);
                    double freq;
                    try
                    {
                        freq = await connection.GetDialFrequencyMhzAsync(ct).ConfigureAwait(false);
                        _catState.Update(freq, CatConnectionStatus.Connected);
                        // EmitIfChanged is called while the lock is held so that
                        // _lastBroadcastFreq is updated atomically with respect to
                        // any concurrent SetDialFrequencyAsync (F-006 Root C).
                        EmitIfChanged(freq, CatConnectionStatus.Connected);
                    }
                    finally
                    {
                        _connectionLock.Release();
                    }

                    // FR-039: persist last-known frequency across restarts when
                    // changed by ≥ 1 Hz.  ConfigStore I/O is independent of the
                    // rig connection and can safely run outside the lock.
                    var storedLast = _configStore.Current.Cat?.LastPolledFrequencyMHz;
                    if (HasFreqChanged(storedLast, freq))
                    {
                        var updated = _configStore.Current with
                        {
                            Cat = (_configStore.Current.Cat ?? new CatConfig()) with
                            {
                                LastPolledFrequencyMHz = freq
                            }
                        };
                        // Fire-and-forget — a failed persist is not fatal.
                        _ = _configStore.SaveAsync(updated, CancellationToken.None)
                                        .ContinueWith(t => _logger.LogWarning(
                                            "CAT: failed to persist last-known frequency: {Msg}",
                                            t.Exception?.GetBaseException().Message),
                                            TaskContinuationOptions.OnlyOnFaulted);
                    }
                }
                catch (OperationCanceledException) when (ct.IsCancellationRequested)
                {
                    break;
                }
                catch (Exception ex)
                {
                    // Radio became unreachable mid-session — an operator condition,
                    // not a software fault.  Log at Warning (unexpected during a live
                    // session) but without the exception object so no stack trace is
                    // emitted; the message already contains the relevant description.
                    _logger.LogWarning(
                        "CAT: radio connection lost via {RigModel} — {Message}. " +
                        "Polling suspended; check the radio and CAT cable.",
                        config.RigModel, ex.Message);
                    _catState.Update(null, CatConnectionStatus.Error);
                    _activeConnection = null;
                    EmitIfChanged(null, CatConnectionStatus.Error);
                    await SafeDisconnectAsync(connection).ConfigureAwait(false);
                    connection            = null;
                    suspendedAfterFailure = true;
                    continue;
                }

                await Task.Delay(TimeSpan.FromSeconds(interval), ct).ConfigureAwait(false);
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown.
        }
        finally
        {
            _activeConnection = null;
            if (connection is not null)
                await SafeDisconnectAsync(connection).ConfigureAwait(false);
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Creates the <see cref="IRadioConnection"/> for the given <paramref name="config"/>.
    /// Returns <c>null</c> if the rig model is unrecognised.
    /// Protected virtual to allow injection of test doubles in unit tests.
    /// </summary>
    protected virtual IRadioConnection? CreateConnection(CatConfig config)
    {
        try
        {
            return RigModelFactory.Create(config);
        }
        catch (ArgumentException ex)
        {
            _logger.LogWarning(
                "CAT: unrecognised rigModel '{RigModel}' — disabling CAT. {Message}",
                config.RigModel, ex.Message);
            return null;
        }
    }

    private static async Task SafeDisconnectAsync(IRadioConnection connection)
    {
        try
        {
            await connection.DisconnectAsync().ConfigureAwait(false);
        }
        catch { /* best-effort */ }
        finally
        {
            (connection as IDisposable)?.Dispose();
        }
    }

    /// <summary>
    /// Emits a <c>cat_status</c> WebSocket event only when frequency changed by ≥ 1 Hz
    /// or connection status changed (D5).
    /// </summary>
    private void EmitIfChanged(double? newFreq, CatConnectionStatus newStatus)
    {
        var freqChanged   = HasFreqChanged(_lastBroadcastFreq, newFreq);
        var statusChanged = _lastBroadcastStatus != newStatus;

        if (!freqChanged && !statusChanged) return;

        _lastBroadcastFreq   = newFreq;
        _lastBroadcastStatus = newStatus;

        _catEventBus.Publish(newStatus, newFreq);
    }

    /// <summary>
    /// Returns <c>true</c> only when a field that governs the physical rig
    /// connection has changed.  <see cref="CatConfig.LastPolledFrequencyMHz"/>
    /// is intentionally excluded: it is updated by the FR-039 frequency-persist
    /// path and must not cause a reconnect (F-010).
    /// </summary>
    private static bool HasConnectionConfigChanged(CatConfig prev, CatConfig next)
        => prev.Enabled             != next.Enabled
        || prev.RigModel            != next.RigModel
        || prev.SerialPort          != next.SerialPort
        || prev.BaudRate            != next.BaudRate
        || prev.RigctldHost         != next.RigctldHost
        || prev.RigctldPort         != next.RigctldPort
        || prev.PollIntervalSeconds != next.PollIntervalSeconds;

    private static bool HasFreqChanged(double? prev, double? next)
    {
        if (prev is null && next is null) return false;
        if (prev is null || next is null) return true;
        return Math.Abs(prev.Value - next.Value) * 1_000_000.0 >= 1.0; // ≥ 1 Hz
    }
}
