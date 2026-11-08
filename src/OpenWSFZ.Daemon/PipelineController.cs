using System.Threading.Channels;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using OpenWSFZ.Ft8;

namespace OpenWSFZ.Daemon;

/// <summary>
/// A running cycle framer that the <see cref="PipelineController"/> can start once and stop. The real implementation wraps a
/// <see cref="CycleFramer"/> (<see cref="CycleFramerRunner"/>); tests substitute a fake that counts live framers.
/// </summary>
public interface IPipelineFramer
{
    /// <summary>Starts reading samples. Called exactly once, by the controller's start step.</summary>
    void Start();

    /// <summary>Cancels the framer and waits (bounded) for it to finish. Safe to call more than once.</summary>
    Task StopAsync();
}

/// <summary>
/// The only owner of the capture pipeline (issue #266, FR-097, FR-098): the single place that constructs a <see cref="CycleFramer"/>
/// (through its framer factory), holds the framer slot, starts and stops capture, resets the monitors and holds the semaphore.
/// <para>
/// <see cref="ReconcileAsync"/> is <b>level-triggered</b>: inside the semaphore it reads the CURRENT configuration and converges on it
/// (run iff <c>AudioDeviceId</c> is non-null and <c>DecodingEnabled</c> is true), so the order in which concurrent callers reach the
/// semaphore does not matter. "Running" is this class's own record that it started a pipeline and has not stopped it; a capture that has
/// since died still counts as running (the capture-recovery coordinator retries it with <c>forceRestart</c>).
/// </para>
/// <para>
/// At most one framer is alive at every step. The start step stops anything it finds in the slot before starting (R4) and logs one
/// Warning if it had to; no normal path reaches that Warning. Logs carry device identifiers, reasons and counts only (NFR-021).
/// </para>
/// </summary>
public sealed class PipelineController
{
    private readonly IConfigStore            _config;
    private readonly Action<string>          _startCapture;
    private readonly Func<Task>              _stopCapture;
    private readonly Func<IPipelineFramer>   _framerFactory;
    private readonly Action                  _resetMonitors;
    private readonly ILogger                 _logger;
    private readonly SemaphoreSlim           _gate = new(1, 1);

    private IPipelineFramer? _framer;          // the framer slot: written only in this class
    private string?          _runningDevice;   // the owner's record of "a pipeline was started on this device and not stopped"
    private bool             _shutDown;

    /// <param name="config">Read inside the semaphore on every reconcile.</param>
    /// <param name="startCapture">Starts capture on a device. Fire-and-forget by design: faults arrive through <c>CaptureFailed</c>; it must not block under the semaphore.</param>
    /// <param name="stopCapture">Stops capture.</param>
    /// <param name="framerFactory">Creates an unstarted framer.</param>
    /// <param name="resetMonitors">Resets the audio, data-flow and spectrum monitors before a start.</param>
    /// <param name="logger">Receives the start/stop lines.</param>
    public PipelineController(
        IConfigStore config,
        Action<string> startCapture,
        Func<Task> stopCapture,
        Func<IPipelineFramer> framerFactory,
        Action resetMonitors,
        ILogger logger)
    {
        _config        = config        ?? throw new ArgumentNullException(nameof(config));
        _startCapture  = startCapture  ?? throw new ArgumentNullException(nameof(startCapture));
        _stopCapture   = stopCapture   ?? throw new ArgumentNullException(nameof(stopCapture));
        _framerFactory = framerFactory ?? throw new ArgumentNullException(nameof(framerFactory));
        _resetMonitors = resetMonitors ?? throw new ArgumentNullException(nameof(resetMonitors));
        _logger        = logger        ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// The production wiring: real capture manager, real <see cref="CycleFramer"/>. This is the only place in the daemon that starts or
    /// stops capture or constructs a framer (the single-owner rule, FR-097).
    /// </summary>
    public static PipelineController Create(
        IConfigStore config,
        CaptureManager captureManager,
        IClock clock,
        ILoggerFactory loggerFactory,
        Func<double?> dialFreqProvider,
        Func<(bool Enabled, double CutSeconds)> earlyDecodeProvider,
        ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> framerOutput,
        ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> earlyOutput,
        Action resetMonitors,
        ILogger logger)
        => new(
            config,
            // StartAsync itself completes before the capture task runs; inner faults are reported via the
            // captureManager.CaptureFailed event. Fire-and-forget by design (never awaited under the semaphore).
            startCapture:  device => { _ = captureManager.StartAsync(device); },
            stopCapture:   () => captureManager.StopAsync(),
            framerFactory: () => new CycleFramerRunner(
                new CycleFramer(captureManager.Samples, clock, loggerFactory.CreateLogger<CycleFramer>(),
                    dialFreqProvider, earlyDecodeProvider),
                framerOutput, earlyOutput),
            resetMonitors: resetMonitors,
            logger:        logger);

    /// <summary>The device the owner believes a pipeline is running on, or <c>null</c>.</summary>
    public string? RunningDevice => Volatile.Read(ref _runningDevice);

    /// <summary>The framer slot (exposed to tests, which pre-seed it to exercise the R4 defence).</summary>
    internal IPipelineFramer? FramerSlot
    {
        get => _framer;
        set => _framer = value;
    }

    /// <summary>
    /// Converges the pipeline on the configuration read now, inside the semaphore.
    /// </summary>
    /// <param name="reason">Why (<c>config</c>, <c>capture-retry</c>, ...); goes into the log lines.</param>
    /// <param name="forceRestart">Stop and start again even if already running on the desired device (the capture-retry path). Does nothing while decoding is off.</param>
    public async Task ReconcileAsync(string reason, bool forceRestart = false)
    {
        await _gate.WaitAsync().ConfigureAwait(false);
        try
        {
            if (_shutDown) return;

            var cfg     = _config.Current;
            var desired = cfg.DecodingEnabled ? cfg.AudioDeviceId : null;

            if (desired is null)
            {
                if (_runningDevice is not null) await StopCoreAsync(reason).ConfigureAwait(false);
                return;
            }

            if (_runningDevice is not null)
            {
                if (_runningDevice == desired && !forceRestart) return;   // converged: leave it alone
                await StopCoreAsync(reason).ConfigureAwait(false);
            }

            await StartCoreAsync(desired, reason).ConfigureAwait(false);
        }
        finally { _gate.Release(); }
    }

    /// <summary>
    /// Shutdown, under the same semaphore (so it waits for an in-progress reconcile), in the order the daemon has always used: health
    /// monitor, framer, decoder dispose, capture stop, capture dispose. Later reconciles do nothing.
    /// </summary>
    public async Task ShutdownAsync(Func<Task> stopHealthMonitor, Action disposeDecoder, Func<Task> disposeCapture)
    {
        await _gate.WaitAsync().ConfigureAwait(false);
        try
        {
            _shutDown = true;
            await stopHealthMonitor().ConfigureAwait(false);
            await StopFramerAsync().ConfigureAwait(false);
            disposeDecoder();
            await _stopCapture().ConfigureAwait(false);
            _runningDevice = null;
            await disposeCapture().ConfigureAwait(false);
        }
        finally { _gate.Release(); }
    }

    // ── internals (call under the semaphore) ────────────────────────────────────────────────────────────────────────

    private async Task StopCoreAsync(string reason)
    {
        try { await StopFramerAsync().ConfigureAwait(false); }
        finally
        {
            try { await _stopCapture().ConfigureAwait(false); }
            finally { _runningDevice = null; }
        }
        _logger.LogInformation("Pipeline stopped (reason: {Reason}).", reason);
    }

    private async Task StartCoreAsync(string device, string reason)
    {
        // R4: never overwrite a live framer. Reconcile stops first on every normal path, so this is reachable only through the defence.
        if (_framer is not null)
        {
            _logger.LogWarning("Pipeline start found a framer still running; stopped it first (reason: {Reason}).", reason);
            await StopFramerAsync().ConfigureAwait(false);
        }

        _resetMonitors();
        _logger.LogInformation("Starting FT8 pipeline for device '{Device}'.", device);
        _startCapture(device);

        var framer = _framerFactory();
        _framer = framer;
        framer.Start();
        _runningDevice = device;
        _logger.LogInformation("Pipeline started on '{Device}' (reason: {Reason}).", device, reason);
    }

    private async Task StopFramerAsync()
    {
        var framer = _framer;
        if (framer is null) return;
        try { await framer.StopAsync().ConfigureAwait(false); }
        finally { _framer = null; }
    }
}

/// <summary>The production <see cref="IPipelineFramer"/>: one <see cref="CycleFramer"/> on its own task, stopped by cancellation.</summary>
internal sealed class CycleFramerRunner : IPipelineFramer
{
    /// <summary>How long a stop waits for the framer task before moving on.</summary>
    internal static readonly TimeSpan StopTimeout = TimeSpan.FromSeconds(3);

    private readonly CycleFramer _framer;
    private readonly ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> _output;
    private readonly ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> _early;
    private CancellationTokenSource? _cts;
    private Task? _task;

    public CycleFramerRunner(
        CycleFramer framer,
        ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> output,
        ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> early)
    {
        _framer = framer;
        _output = output;
        _early  = early;
    }

    public void Start()
    {
        _cts = new CancellationTokenSource();
        var ct = _cts.Token;
        _task = Task.Run(() => _framer.RunAsync(_output, _early, ct));
    }

    public async Task StopAsync()
    {
        var cts = _cts;
        if (cts is null) return;
        cts.Cancel();

        if (_task is { } task)
        {
            try { await task.WaitAsync(StopTimeout).ConfigureAwait(false); }
            catch (TimeoutException)           { }
            catch (OperationCanceledException) { }
            catch (Exception)                  { }
        }

        cts.Dispose();
        _cts  = null;
        _task = null;
    }
}
