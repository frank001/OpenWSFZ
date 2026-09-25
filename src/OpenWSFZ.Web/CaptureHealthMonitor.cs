using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Web;

/// <summary>
/// Immutable per-window capture-health snapshot published by <see cref="CaptureHealthMonitor"/>
/// (design.md Decision 1, capture-stall-detection-unattended #188). <c>GET /api/v1/status</c>,
/// the initial WebSocket <c>status</c> event, and every WebSocket <c>heartbeat</c> frame all read
/// the same instance via <see cref="CaptureHealthMonitor.Current"/>, so the three surfaces can
/// never disagree (design.md Decisions 4 and 6).
/// </summary>
/// <param name="CaptureActive">Mirrors <c>CaptureManager.IsCapturing</c> as of this window.</param>
/// <param name="DataFlowing">
/// Whether at least one audio chunk (of any amplitude) was received during this window
/// (design.md Decision 3 — the last <em>completed</em> window; <c>false</c> before the first
/// window completes).
/// </param>
/// <param name="AudioActive">
/// Equal to <paramref name="DataFlowing"/> — Captain-ratified Option A (design.md Decision 4):
/// <c>audioActive</c> has exactly one meaning, everywhere, and it is this one.
/// </param>
/// <param name="WindowEndedAt">Wall-clock instant this window's evaluation completed.</param>
public sealed record CaptureHealthSnapshot(
    bool           CaptureActive,
    bool           DataFlowing,
    bool           AudioActive,
    DateTimeOffset WindowEndedAt)
{
    /// <summary>
    /// The snapshot reported by every surface when no <see cref="CaptureHealthMonitor"/> is
    /// wired up at all (e.g. a minimal test fixture that passes neither a
    /// <c>CaptureManager</c> nor a <c>DataFlowMonitor</c> into <c>WebApp.Create</c>) — matches
    /// the all-<c>false</c> defaults every one of these fields carried before this type existed.
    /// </summary>
    public static readonly CaptureHealthSnapshot Empty =
        new(CaptureActive: false, DataFlowing: false, AudioActive: false, WindowEndedAt: default);
}

/// <summary>
/// Daemon-lifetime ticker that owns the 5-second per-window capture-health evaluation
/// (design.md Decision 1, capture-stall-detection-unattended #188).
///
/// <para>
/// Before this change, the same evaluation ran inside <c>WebSocketHub.HandleAsync</c>'s
/// per-connection heartbeat loop, which ran zero times with no browser tab connected and
/// over-ticked the shared <see cref="AudioWatchdog"/> when N ≥ 2 clients were connected (each
/// connection's own 5 s timer drained the same singleton monitors independently). This type is
/// the single owner: every <see cref="WindowInterval"/>, regardless of connected WebSocket
/// client count — including zero — it consumes <see cref="DataFlowMonitor"/> exactly once,
/// ticks the watchdog exactly once, and publishes an immutable <see cref="CaptureHealthSnapshot"/>
/// that every other consumer reads via <see cref="Current"/>.
/// </para>
///
/// <para>
/// <see cref="TickOnceAsync"/> is the unit under test: it performs exactly one window's
/// evaluation without depending on wall-clock time, so a unit test can call it directly N times
/// to simulate N windows (design D1, tasks.md U3/U4/U6/U7) instead of waiting through real 5 s
/// sleeps (gate G10). <see cref="Start"/>/<see cref="DisposeAsync"/> drive the production
/// scheduling loop — a real <see cref="PeriodicTimer"/> that calls <see cref="TickOnceAsync"/>
/// once per real-time tick.
/// </para>
/// </summary>
public sealed class CaptureHealthMonitor : IAsyncDisposable
{
    /// <summary>The per-window evaluation interval (design.md Decision 5).</summary>
    public static readonly TimeSpan WindowInterval = TimeSpan.FromSeconds(5);

    private readonly Func<bool>      _isCapturing;
    private readonly DataFlowMonitor _dataFlowMonitor;
    private readonly AudioWatchdog?  _watchdog;
    private readonly ILogger         _logger;
    private readonly TimeProvider    _timeProvider;

    private volatile CaptureHealthSnapshot _snapshot;

    private CancellationTokenSource? _cts;
    private Task?                    _loopTask;

    /// <param name="isCapturing">
    /// Returns whether a capture session is currently active — typically
    /// <c>() =&gt; captureManager.IsCapturing</c>.
    /// </param>
    /// <param name="dataFlowMonitor">Consumed exactly once per window (design D1 step 1).</param>
    /// <param name="watchdog">
    /// Ticked exactly once per window (design D1 step 2). May be <c>null</c> when capture wiring
    /// is absent — the ticker still runs and publishes snapshots, it just never advances a
    /// watchdog or reports a nonzero <see cref="WatchdogRestartCount"/>.
    /// </param>
    /// <param name="logger">Logger the <c>Heartbeat:</c> line (design D5) is written to.</param>
    /// <param name="timeProvider">
    /// Clock used only for <see cref="CaptureHealthSnapshot.WindowEndedAt"/>. Defaults to
    /// <see cref="TimeProvider.System"/>.
    /// </param>
    /// <remarks>
    /// Internal, not public: <paramref name="watchdog"/> is the <c>internal</c>
    /// <see cref="AudioWatchdog"/> type, so a public constructor here would be a CS0051
    /// accessibility violation. <see cref="CaptureHealthMonitor"/> itself must stay
    /// <see langword="public"/> (it appears in <c>WebApp.Create</c>'s public signature and its
    /// <see cref="Current"/>/<see cref="WatchdogRestartCount"/> are read publicly), but only
    /// <c>OpenWSFZ.Web</c>, <c>OpenWSFZ.Daemon</c>, and <c>OpenWSFZ.Web.Tests</c> (all granted
    /// <c>InternalsVisibleTo</c>) can construct one — which matches reality, since only they can
    /// supply a valid <see cref="AudioWatchdog"/>.
    /// </remarks>
    internal CaptureHealthMonitor(
        Func<bool>       isCapturing,
        DataFlowMonitor  dataFlowMonitor,
        AudioWatchdog?   watchdog,
        ILogger          logger,
        TimeProvider?    timeProvider = null)
    {
        _isCapturing     = isCapturing;
        _dataFlowMonitor = dataFlowMonitor;
        _watchdog        = watchdog;
        _logger          = logger;
        _timeProvider    = timeProvider ?? TimeProvider.System;

        _snapshot = CaptureHealthSnapshot.Empty with { WindowEndedAt = _timeProvider.GetUtcNow() };
    }

    /// <summary>
    /// The most recently published snapshot. Never <c>null</c> — before the first window
    /// completes it is the all-<c>false</c> initial value set at construction.
    /// </summary>
    public CaptureHealthSnapshot Current => _snapshot;

    /// <summary>
    /// Process-lifetime count of watchdog-triggered restarts (design.md Decision 7). Reads
    /// straight from <see cref="AudioWatchdog.RestartCount"/> — the watchdog itself is the one
    /// source of truth, so there is no second counter that could drift from it.
    /// </summary>
    public int WatchdogRestartCount => _watchdog?.RestartCount ?? 0;

    /// <summary>
    /// Performs exactly one window's evaluation (design.md Decision 1, steps 1-4): consumes
    /// <see cref="DataFlowMonitor"/> once, ticks <see cref="AudioWatchdog"/> once, publishes the
    /// new snapshot, then writes the <c>Heartbeat:</c> line. Has no dependency on wall-clock
    /// time — safe to call directly and repeatedly from a unit test to simulate N windows.
    /// </summary>
    public async Task TickOnceAsync()
    {
        // Step 1: consume the data-flow window exactly once.
        var dataFlowing = _dataFlowMonitor.ConsumeAndReset();
        var captureActive = _isCapturing();

        // Step 2: tick the watchdog exactly once with this window's result.
        if (_watchdog is not null)
            await _watchdog.TickAsync(dataFlowing).ConfigureAwait(false);

        // Step 3: publish the snapshot. Decision 4 (Captain-ratified Option A): audioActive ==
        // dataFlowing of the last completed window, on every surface — not a separate signal.
        var snapshot = new CaptureHealthSnapshot(
            CaptureActive: captureActive,
            DataFlowing:   dataFlowing,
            AudioActive:   dataFlowing,
            WindowEndedAt: _timeProvider.GetUtcNow());
        _snapshot = snapshot;

        // Step 4: the Heartbeat: line — exact rendering preserved, lowercase, Information level,
        // once per window regardless of client count (design D5). Older QA supervisor scripts
        // string-match on this text; do not reformat it.
        //
        // Booleans are formatted explicitly as lowercase strings rather than passed as raw
        // `bool` template args. The pre-existing code this replaces relied on Serilog's own
        // scalar-value rendering happening to lowercase bool (".NET's plain bool.ToString() is
        // "True"/"False" — capitalised; observed lowercase output at
        // WebSocketHub.cs's predecessor line came from the Serilog sink specifically, not from
        // any provider-agnostic guarantee). Spelling it out here makes the exact rendering
        // reliable under any ILogger implementation, not just Serilog.
        _logger.LogInformation(
            "Heartbeat: captureActive={CaptureActive}, audioActive={AudioActive}, dataFlowing={DataFlowing}",
            snapshot.CaptureActive ? "true" : "false",
            snapshot.AudioActive   ? "true" : "false",
            snapshot.DataFlowing   ? "true" : "false");
    }

    /// <summary>
    /// Production scheduling loop: calls <see cref="TickOnceAsync"/> once per real
    /// <see cref="WindowInterval"/> tick until <paramref name="ct"/> is cancelled.
    /// </summary>
    private async Task RunAsync(CancellationToken ct)
    {
        using var timer = new PeriodicTimer(WindowInterval);
        try
        {
            while (await timer.WaitForNextTickAsync(ct).ConfigureAwait(false))
                await TickOnceAsync().ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            // Normal shutdown — see DisposeAsync.
        }
    }

    /// <summary>
    /// Starts the production ticker loop on a background task. Call once, after construction —
    /// safe to call before the host starts listening; the ticker has no dependency on Kestrel.
    /// </summary>
    public void Start()
    {
        _cts      = new CancellationTokenSource();
        _loopTask = Task.Run(() => RunAsync(_cts.Token));
    }

    /// <summary>
    /// Stops the ticker loop and waits (briefly) for any in-flight tick to finish.
    /// </summary>
    /// <remarks>
    /// 🔴 Must be called inside the same guard that already protects shutdown from a concurrent
    /// watchdog restart (<c>restartSemaphore</c> in <c>Program.cs</c>'s <c>ApplicationStopping</c>
    /// handler, design.md Risk 4) — and before <c>captureManager</c> is disposed. Otherwise the
    /// watchdog can fire a restart into a pipeline that is mid-teardown.
    /// </remarks>
    public async ValueTask DisposeAsync()
    {
        var cts = _cts;
        if (cts is null) return; // Start() was never called — nothing to stop.

        cts.Cancel();

        var task = _loopTask;
        if (task is not null)
        {
            try { await task.WaitAsync(TimeSpan.FromSeconds(3)).ConfigureAwait(false); }
            catch (TimeoutException) { }
            catch (OperationCanceledException) { }
        }

        cts.Dispose();
        _cts      = null;
        _loopTask = null;
    }
}
