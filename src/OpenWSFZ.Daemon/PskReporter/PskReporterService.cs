using System.Threading.Channels;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon.PskReporter;

/// <summary>
/// Opt-in upload of this station's own decodes to PSK Reporter (issue #262, capability <c>psk-reporter-upload</c>).
/// <para>
/// Inert until <c>pskReporter.enabled</c> is true: while disabled no socket is created, no host is resolved, no timer runs and nothing
/// is queued (batches that arrive are discarded unread). Enabling (also at run time, through the configuration store) creates ONE IPv4
/// UDP socket and a one-second tick; disabling disposes both. The decision logic lives in <see cref="PskReporterEngine"/>; this class only
/// reads the channel, ticks, and sends. A failure here never reaches the decode pump, which only writes to a bounded DropOldest queue.
/// </para>
/// </summary>
internal sealed class PskReporterService : IHostedService, IDisposable
{
    /// <summary>How often a due window or a full datagram is looked for while enabled.</summary>
    public static readonly TimeSpan TickInterval = TimeSpan.FromSeconds(1);

    /// <summary>Upper bound of the random delay before the first window of an enabled period.</summary>
    public static readonly TimeSpan MaxFirstSendOffset = TimeSpan.FromSeconds(60);

    private readonly ChannelReader<DecodeBatch> _reader;
    private readonly IConfigStore               _config;
    private readonly IClock                     _clock;
    private readonly PskTransportFactory        _transportFactory;
    private readonly Func<TimeSpan>             _firstSendOffset;
    private readonly TimeSpan                   _tickInterval;
    private readonly PskReporterEngine          _engine;
    private readonly ILogger<PskReporterService> _logger;

    private readonly object _stateGate = new();
    private readonly SemaphoreSlim _sendLock = new(1, 1);
    private IPskTransport?          _transport;
    private (string Host, int Port) _transportTarget;
    private CancellationTokenSource? _tickCts;
    private Task?                    _tickTask;
    private CancellationTokenSource? _stopCts;
    private Task?                    _readTask;
    private int                      _disposed;

    /// <param name="reader">The service's own queue (<c>LateBatch.CreateQsoQueue</c> sizing: 10 with the coherent fallback on, 8 off).</param>
    /// <param name="config">Read for <c>pskReporter</c> on start and on every save.</param>
    /// <param name="clock">UTC clock (a fake in tests).</param>
    /// <param name="transportFactory">Creates the UDP socket; called once per enabled period.</param>
    /// <param name="identity">The receiver identity (<c>tx.callsign</c>, <c>tx.grid</c>, antenna, software string).</param>
    /// <param name="logger">Counts only; never a callsign.</param>
    /// <param name="firstSendOffset">The 0 to 60 s offset of the first window (random in production).</param>
    /// <param name="tickInterval">How often a due window is looked for while enabled (1 s; a test passes a long one to drive the flush by hand).</param>
    public PskReporterService(
        ChannelReader<DecodeBatch> reader,
        IConfigStore config,
        IClock clock,
        PskTransportFactory transportFactory,
        Func<PskIdentity> identity,
        ILogger<PskReporterService> logger,
        Func<TimeSpan>? firstSendOffset = null,
        TimeSpan? tickInterval = null)
    {
        _tickInterval     = tickInterval ?? TickInterval;
        _reader           = reader ?? throw new ArgumentNullException(nameof(reader));
        _config           = config ?? throw new ArgumentNullException(nameof(config));
        _clock            = clock  ?? throw new ArgumentNullException(nameof(clock));
        _transportFactory = transportFactory ?? throw new ArgumentNullException(nameof(transportFactory));
        _logger           = logger ?? throw new ArgumentNullException(nameof(logger));
        _firstSendOffset  = firstSendOffset ?? (() => TimeSpan.FromSeconds(Random.Shared.NextDouble() * MaxFirstSendOffset.TotalSeconds));
        _engine           = new PskReporterEngine(identity, logger, (uint)Random.Shared.NextInt64(0, uint.MaxValue + 1L));
    }

    /// <summary>The decision engine (exposed for tests).</summary>
    internal PskReporterEngine Engine => _engine;

    /// <summary>Whether an enabled period is running now (a socket exists).</summary>
    internal bool IsActive { get { lock (_stateGate) return _transport is not null; } }

    /// <inheritdoc />
    public Task StartAsync(CancellationToken cancellationToken)
    {
        _stopCts  = new CancellationTokenSource();
        _config.OnSaved += OnConfigSaved;
        ApplyConfig();
        _readTask = Task.Run(() => ReadLoopAsync(_stopCts.Token));
        return Task.CompletedTask;
    }

    /// <inheritdoc />
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _config.OnSaved -= OnConfigSaved;
        // Shutdown is order-independent: the host may call Dispose before StopAsync (or either twice). A disposed service has already
        // cancelled its reader and released its socket, so there is nothing left to stop.
        if (Volatile.Read(ref _disposed) == 1) return;
        try { _stopCts?.Cancel(); }
        catch (ObjectDisposedException) { /* disposed concurrently: already cancelled */ }
        if (_readTask is not null)
        {
            try { await _readTask.WaitAsync(cancellationToken).ConfigureAwait(false); }
            catch (OperationCanceledException) { }
        }
        Deactivate();
    }

    /// <inheritdoc />
    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) == 1) return;
        _config.OnSaved -= OnConfigSaved;
        try { _stopCts?.Cancel(); }
        catch (ObjectDisposedException) { }
        _stopCts?.Dispose();
        Deactivate();
        _sendLock.Dispose();
    }

    /// <summary>
    /// Runs on the caller's thread inside <c>IConfigStore.OnSaved</c>, which is unguarded: nothing thrown here may fail a Settings save.
    /// </summary>
    private void OnConfigSaved(AppConfig _)
    {
        try { ApplyConfig(); }
        catch (Exception ex)
        {
            _logger.LogWarning("psk-reporter: the configuration change could not be applied ({Error}).", ex.GetType().Name);
        }
    }

    /// <summary>Brings the socket and tick in line with the current configuration (idempotent).</summary>
    private void ApplyConfig()
    {
        var cfg = _config.Current.PskReporter ?? new PskReporterConfig();
        lock (_stateGate)
        {
            var target = (cfg.Host, cfg.Port);
            if (!cfg.Enabled)
            {
                DeactivateUnsafe();
                return;
            }
            if (_transport is not null && _transportTarget == target) return;   // already running for this target

            DeactivateUnsafe();                                                   // a changed host or port is a new socket
            _transport       = _transportFactory(cfg.Host, cfg.Port);            // once per enabled period, never per window
            _transportTarget = target;
            _engine.Activate(_clock.UtcNow, _firstSendOffset());
            _tickCts  = new CancellationTokenSource();
            var token = _tickCts.Token;
            _tickTask = Task.Run(() => TickLoopAsync(token));
            _logger.LogInformation("psk-reporter: upload enabled (one IPv4 UDP socket, a datagram at most every 5 minutes).");
        }
    }

    private void Deactivate()
    {
        lock (_stateGate) DeactivateUnsafe();
    }

    private void DeactivateUnsafe()
    {
        if (_transport is null) return;
        _tickCts?.Cancel();
        _tickCts?.Dispose();
        _tickCts  = null;
        _tickTask = null;
        _engine.Deactivate();
        _transport.Dispose();
        _transport = null;
        _logger.LogInformation("psk-reporter: upload disabled.");
    }

    private async Task ReadLoopAsync(CancellationToken ct)
    {
        try
        {
            await foreach (var batch in _reader.ReadAllAsync(ct).ConfigureAwait(false))
            {
                try
                {
                    if (!IsActive) continue;                       // disabled: discard unread, queue nothing
                    _engine.Ingest(batch, _clock.UtcNow);
                    await FlushAsync(ct).ConfigureAwait(false);    // a full datagram goes at once
                }
                catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
                catch (Exception ex)
                {
                    _logger.LogWarning("psk-reporter: a batch could not be processed ({Error}).", ex.GetType().Name);
                }
            }
        }
        catch (OperationCanceledException) { }
    }

    private async Task TickLoopAsync(CancellationToken ct)
    {
        using var timer = new PeriodicTimer(_tickInterval);
        try
        {
            while (await timer.WaitForNextTickAsync(ct).ConfigureAwait(false))
            {
                try { await FlushAsync(ct).ConfigureAwait(false); }
                catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
                catch (Exception ex) { _logger.LogWarning("psk-reporter: a send window failed ({Error}).", ex.GetType().Name); }
            }
        }
        catch (OperationCanceledException) { }
    }

    /// <summary>Sends every datagram that is due now (the window's, then any further full ones). Serialised by a lock.</summary>
    internal async Task FlushAsync(CancellationToken ct)
    {
        await _sendLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            while (true)
            {
                IPskTransport? transport;
                lock (_stateGate) transport = _transport;
                if (transport is null) return;

                var now      = _clock.UtcNow;
                var datagram = _engine.Prepare(now);
                if (datagram is null) return;

                try
                {
                    await transport.SendAsync(datagram.Bytes, ct).ConfigureAwait(false);
                    _engine.Complete(datagram, sent: true, _clock.UtcNow);
                }
                catch (OperationCanceledException) when (ct.IsCancellationRequested)
                {
                    _engine.Complete(datagram, sent: false, _clock.UtcNow);
                    throw;
                }
                catch (Exception ex)
                {
                    _engine.Complete(datagram, sent: false, _clock.UtcNow, ex);
                    return;                                         // retry at the next window
                }
            }
        }
        finally { _sendLock.Release(); }
    }
}
