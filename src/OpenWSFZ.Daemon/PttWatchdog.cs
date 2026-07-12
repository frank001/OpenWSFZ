using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Mechanism-agnostic PTT failsafe watchdog (FR-056, design.md Decision 4), shared by
/// <c>CatPttController</c> and <c>SerialRtsDtrPttController</c> — the two
/// <c>IPttController</c> implementations that assert a real physical PTT signal.
///
/// <para>
/// <see cref="Arm"/> starts a timer the instant PTT is asserted. If <see cref="Disarm"/>
/// has not been called before <c>watchdogTimeoutMs</c> elapses, the watchdog invokes the
/// supplied forced-release callback and logs at Error (including the elapsed hold
/// duration) — the last line of defence against a stuck key-down leaving a real
/// transmitter keyed indefinitely. Does not apply to <c>AudioOnlyPttController</c>, which
/// asserts no independent physical PTT signal (VOX keying is the rig's own responsibility).
/// </para>
///
/// <para>
/// Deliberately has no dependency on WASAPI or any PTT-assertion mechanism — it is a
/// plain timer + callback so it can be unit-tested (task 12.8) without requiring
/// <c>WASAPI_SUPPORTED</c> or Windows.
/// </para>
/// </summary>
internal sealed class PttWatchdog : IDisposable
{
    private readonly ILogger _logger;
    private readonly string  _controllerName;
    private readonly object  _gate = new();

    private Timer?      _timer;
    private DateTime     _armedAtUtc;
    private Func<Task>?  _forceReleaseAsync;

    /// <param name="logger">Logger used for the Error-level watchdog-fired message.</param>
    /// <param name="controllerName">
    /// Name of the owning controller (e.g. <c>"CatPttController"</c>), included in the
    /// watchdog-fired log line so hardware-acceptance testing can identify which
    /// mechanism tripped.
    /// </param>
    public PttWatchdog(ILogger logger, string controllerName)
    {
        _logger         = logger;
        _controllerName = controllerName;
    }

    /// <summary>
    /// Arms the watchdog. Call the instant PTT is asserted in <c>KeyDownAsync</c>.
    /// Re-arming an already-armed watchdog replaces the pending timer.
    /// </summary>
    /// <param name="watchdogTimeoutMs">Milliseconds before the watchdog fires.</param>
    /// <param name="forceReleaseAsync">
    /// Invoked if the watchdog fires — SHALL force PTT release, bypassing any configured
    /// tail time.
    /// </param>
    public void Arm(int watchdogTimeoutMs, Func<Task> forceReleaseAsync)
    {
        lock (_gate)
        {
            _forceReleaseAsync = forceReleaseAsync;
            _armedAtUtc        = DateTime.UtcNow;
            _timer?.Dispose();
            _timer = new Timer(OnFired, null, watchdogTimeoutMs, Timeout.Infinite);
        }
    }

    /// <summary>
    /// Disarms the watchdog. Call the instant <c>KeyUpAsync</c> begins its release step,
    /// so a race between a normal, in-time release and the watchdog firing cannot occur.
    /// Safe to call when not armed.
    /// </summary>
    public void Disarm()
    {
        lock (_gate)
        {
            _timer?.Dispose();
            _timer             = null;
            _forceReleaseAsync = null;
        }
    }

    private void OnFired(object? state)
    {
        Func<Task>? callback;
        TimeSpan    elapsed;

        lock (_gate)
        {
            // Disarmed between the timer firing and this callback running — no-op.
            if (_timer is null) return;

            callback = _forceReleaseAsync;
            elapsed  = DateTime.UtcNow - _armedAtUtc;

            _timer.Dispose();
            _timer             = null;
            _forceReleaseAsync = null;
        }

        if (callback is null) return;

        _logger.LogError(
            "{Controller}: watchdog fired after {ElapsedMs} ms — forcing PTT release.",
            _controllerName, (int)elapsed.TotalMilliseconds);

        // Fire-and-forget: OnFired runs on a ThreadPool timer thread with no async path
        // back to a caller. Observe the task so a fault in the forced-release path itself
        // is logged rather than becoming an unobserved task exception.
        _ = callback().ContinueWith(
            t => _logger.LogError(t.Exception,
                "{Controller}: forced watchdog release threw.", _controllerName),
            CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted,
            TaskScheduler.Default);
    }

    public void Dispose() => Disarm();
}
