using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon.Cat;

/// <summary>
/// Background service that polls rig frequency via <see cref="IRadioConnection"/>
/// and keeps <see cref="CatState"/> up to date (FR-032, FR-034).
///
/// <para>
/// Lifecycle:
/// <list type="bullet">
///   <item>If <c>Cat.Enabled = false</c>, sets status to <see cref="CatConnectionStatus.Disabled"/>
///         and exits without opening any port.</item>
///   <item>Otherwise, creates a connection via <see cref="RigModelFactory"/>, connects,
///         and enters the poll loop.</item>
///   <item>Any connection or poll failure is logged at Warning, status set to Error,
///         and the loop retries after a 2-second back-off.</item>
///   <item>Config changes (port, baud, rigModel, enabled toggle) take effect
///         within two poll intervals without a daemon restart.</item>
/// </list>
/// </para>
/// </summary>
public class CatPollingService : IHostedService, IAsyncDisposable
{
    private static readonly TimeSpan RetryDelay = TimeSpan.FromSeconds(2);

    private readonly CatState              _catState;
    private readonly IConfigStore          _configStore;
    private readonly CatEventBus           _catEventBus;
    private readonly ILogger<CatPollingService> _logger;

    private CancellationTokenSource? _cts;
    private Task?                    _pollingTask;

    public CatPollingService(
        CatState                    catState,
        IConfigStore                configStore,
        CatEventBus                 catEventBus,
        ILogger<CatPollingService>  logger)
    {
        _catState    = catState;
        _configStore = configStore;
        _catEventBus = catEventBus;
        _logger      = logger;
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
        await StopAsync(CancellationToken.None).ConfigureAwait(false);
        _cts?.Dispose();
    }

    // ── Core poll loop ────────────────────────────────────────────────────────

    private async Task RunAsync(CancellationToken ct)
    {
        IRadioConnection? connection    = null;
        CatConfig?        lastConfig    = null;
        double?           lastEmittedFreq   = null;
        CatConnectionStatus lastEmittedStatus = CatConnectionStatus.Disabled;

        try
        {
            while (!ct.IsCancellationRequested)
            {
                var config = _configStore.Current.Cat ?? new CatConfig();

                // ── Detect config change (task 7.4) ───────────────────────────
                if (lastConfig is not null && config != lastConfig)
                {
                    _logger.LogInformation(
                        "CAT config changed — reconnecting with new parameters.");
                    if (connection is not null)
                    {
                        await SafeDisconnectAsync(connection).ConfigureAwait(false);
                        connection = null;
                    }
                }
                lastConfig = config;

                // ── Disabled path ─────────────────────────────────────────────
                if (!config.Enabled)
                {
                    _catState.Update(null, CatConnectionStatus.Disabled);
                    EmitIfChanged(ref lastEmittedFreq, ref lastEmittedStatus,
                                  null, CatConnectionStatus.Disabled);
                    await Task.Delay(TimeSpan.FromSeconds(1), ct).ConfigureAwait(false);
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
                        EmitIfChanged(ref lastEmittedFreq, ref lastEmittedStatus,
                                      null, CatConnectionStatus.Disabled);
                        await Task.Delay(RetryDelay, ct).ConfigureAwait(false);
                        continue;
                    }

                    _catState.Update(null, CatConnectionStatus.Connecting);
                    EmitIfChanged(ref lastEmittedFreq, ref lastEmittedStatus,
                                  null, CatConnectionStatus.Connecting);

                    try
                    {
                        await connection.ConnectAsync(ct).ConfigureAwait(false);
                        _logger.LogInformation(
                            "CAT connected via {RigModel}.", config.RigModel);
                    }
                    catch (OperationCanceledException) when (ct.IsCancellationRequested)
                    {
                        break;
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex,
                            "CAT: failed to connect via {RigModel} — {Message}. Retrying in {Delay} s.",
                            config.RigModel, ex.Message, RetryDelay.TotalSeconds);
                        _catState.Update(null, CatConnectionStatus.Error);
                        EmitIfChanged(ref lastEmittedFreq, ref lastEmittedStatus,
                                      null, CatConnectionStatus.Error);
                        await SafeDisconnectAsync(connection).ConfigureAwait(false);
                        connection = null;
                        await Task.Delay(RetryDelay, ct).ConfigureAwait(false);
                        continue;
                    }
                }

                // ── Poll frequency ────────────────────────────────────────────
                try
                {
                    var freq = await connection.GetDialFrequencyMhzAsync(ct).ConfigureAwait(false);
                    _catState.Update(freq, CatConnectionStatus.Connected);
                    EmitIfChanged(ref lastEmittedFreq, ref lastEmittedStatus,
                                  freq, CatConnectionStatus.Connected);

                    // FR-039: persist last-known frequency across restarts when changed by ≥ 1 Hz.
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
                    _logger.LogWarning(ex,
                        "CAT: frequency poll failed via {RigModel} — {Message}. Retrying in {Delay} s.",
                        config.RigModel, ex.Message, RetryDelay.TotalSeconds);
                    _catState.Update(null, CatConnectionStatus.Error);
                    EmitIfChanged(ref lastEmittedFreq, ref lastEmittedStatus,
                                  null, CatConnectionStatus.Error);
                    await SafeDisconnectAsync(connection).ConfigureAwait(false);
                    connection = null;
                    await Task.Delay(RetryDelay, ct).ConfigureAwait(false);
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
    private void EmitIfChanged(
        ref double?             lastFreq,
        ref CatConnectionStatus lastStatus,
        double?                 newFreq,
        CatConnectionStatus     newStatus)
    {
        var freqChanged   = HasFreqChanged(lastFreq, newFreq);
        var statusChanged = lastStatus != newStatus;

        if (!freqChanged && !statusChanged) return;

        lastFreq   = newFreq;
        lastStatus = newStatus;

        _catEventBus.Publish(newStatus, newFreq);
    }

    private static bool HasFreqChanged(double? prev, double? next)
    {
        if (prev is null && next is null) return false;
        if (prev is null || next is null) return true;
        return Math.Abs(prev.Value - next.Value) * 1_000_000.0 >= 1.0; // ≥ 1 Hz
    }
}
